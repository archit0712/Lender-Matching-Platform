"""
pdf_ingestion.py — Hatchet workflow (hatchet-sdk v0.32+ standalone task API)

In this version of the SDK, hatchet.task() creates a standalone workflow.
We run all three steps (extract → parse → save) sequentially within one task.
Retries apply to the whole task — if GPT-4o fails, the entire pipeline retries.
"""
import base64
import json
from hatchet_sdk import Context
from app.worker import hatchet
from app.services.pdf_extractor import extract_pdf_from_bytes
from app.services.llm_parser import parse_pdf_policy
from app.database import SessionLocal
from app.models import PDFIngestion, IngestionStatus


@hatchet.task(
    name="pdf-ingestion",
    execution_timeout="300s",   # 5 min total — GPT-4o can be slow
    retries=2,
)
def run_pdf_ingestion(input, ctx: Context) -> dict:
    """
    Full pipeline in one task:
      1. Decode PDF bytes from base64
      2. Extract text + tables with pdfplumber
      3. Parse rules with GPT-4o via instructor
      4. Save to DB with PENDING_REVIEW status

    Input keys:
      file_bytes_b64 : base64-encoded PDF bytes
      filename       : original filename
      ingestion_id   : PDFIngestion row ID created before triggering
    """
    # Input is a Pydantic EmptyModel — convert to dict first
    inp          = input.model_dump() if hasattr(input, "model_dump") else dict(input)
    filename     = inp["filename"]
    ingestion_id = inp["ingestion_id"]
    raw_bytes    = base64.b64decode(inp["file_bytes_b64"])

    # ── Step 1: Extract ───────────────────────────────────────
    ctx.log(f"[1/3] Extracting text from {filename}...")
    extracted = extract_pdf_from_bytes(raw_bytes, filename)
    content   = extracted.full_content()
    ctx.log(f"[1/3] Done — {len(content)} chars, {len(extracted.tables)} tables")

    # ── Step 2: Parse with GPT-4o ────────────────────────────
    ctx.log("[2/3] Sending to GPT-4o...")
    policy = parse_pdf_policy(content, filename)
    ctx.log(f"[2/3] Done — {policy.lender_name}: {len(policy.rules)} rules, {len(policy.programs)} programs")

    # ── Step 3: Save to DB ───────────────────────────────────
    ctx.log("[3/3] Saving to database...")
    db = SessionLocal()
    try:
        ingestion = db.get(PDFIngestion, ingestion_id)
        if not ingestion:
            raise ValueError(f"PDFIngestion row {ingestion_id} not found")

        ingestion.extracted_json = policy.model_dump_json()
        ingestion.status         = IngestionStatus.PENDING_REVIEW
        db.commit()
        ctx.log(f"[3/3] Saved — ingestion {ingestion_id} is PENDING_REVIEW")
    finally:
        db.close()

    return {
        "ingestion_id":  ingestion_id,
        "lender_name":   policy.lender_name,
        "rule_count":    len(policy.rules),
        "program_count": len(policy.programs),
    }