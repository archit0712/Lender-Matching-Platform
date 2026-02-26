"""
ingest.py — PDF upload and ingestion management endpoints

POST /ingest/pdf          → upload PDF, trigger Hatchet workflow
GET  /ingest/             → list all ingestion records
GET  /ingest/{id}         → get one ingestion with its extracted rules
POST /ingest/{id}/approve → admin approves: writes rules to DB as live PolicyRules
POST /ingest/{id}/reject  → admin rejects: marks ingestion as rejected
"""
import base64
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    PDFIngestion, IngestionStatus,
    Lender, PolicyRule, LenderProgram
)
from app.worker import hatchet

router = APIRouter()

MAX_PDF_SIZE = 10 * 1024 * 1024  # 10MB


# ── Upload + trigger workflow ─────────────────────────────────

@router.post("/pdf", status_code=status.HTTP_202_ACCEPTED)
async def upload_pdf(
    file: UploadFile = File(...),
    db:   Session    = Depends(get_db),
):
    """
    Accepts a PDF upload, creates a PENDING_REVIEW ingestion record,
    triggers the Hatchet workflow, and returns immediately.

    The client gets back a workflow_run_id to poll for status.
    This endpoint returns 202 Accepted (not 201 Created) because
    the work happens asynchronously — the result isn't ready yet.
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    raw_bytes = await file.read()

    if len(raw_bytes) > MAX_PDF_SIZE:
        raise HTTPException(status_code=400, detail="PDF exceeds 10MB limit")

    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="PDF file is empty")

    # Create ingestion record in DB first so we have an ID to pass to the workflow
    ingestion = PDFIngestion(
        filename=file.filename,
        status=IngestionStatus.PENDING_REVIEW,
    )
    db.add(ingestion)
    db.commit()
    db.refresh(ingestion)

    # Encode PDF as base64 — Hatchet workflow inputs must be JSON-serializable
    file_bytes_b64 = base64.b64encode(raw_bytes).decode("utf-8")

    from app.workflows.pdf_ingestion import run_pdf_ingestion
    import asyncio

    payload = {
        "file_bytes_b64": file_bytes_b64,
        "filename":       file.filename,
        "ingestion_id":   ingestion.id,
    }

    # Try every known trigger method for this SDK version
    workflow_run = None
    last_error   = None
    loop         = asyncio.get_event_loop()

    for method_name in ["run_no_wait", "run", "spawn", "trigger"]:
        method = getattr(run_pdf_ingestion, method_name, None)
        if method is None:
            continue
        try:
            workflow_run = await loop.run_in_executor(None, lambda m=method: m(payload))
            break
        except Exception as e:
            last_error = f"{method_name}: {e}"
            continue

    if workflow_run is None:
        # Fallback — log available methods for debugging
        available = [m for m in dir(run_pdf_ingestion) if not m.startswith("_")]
        raise HTTPException(
            status_code=500,
            detail=f"Could not trigger workflow. Available methods: {available}. Last error: {last_error}"
        )

    # Store the Hatchet run ID so we can link to the dashboard
    # Store run ID — attribute name varies by SDK version
    run_id = getattr(workflow_run, "workflow_run_id", None) or getattr(workflow_run, "run_id", str(workflow_run))
    ingestion.workflow_run_id = run_id    
    db.commit()

    return {
        "ingestion_id":    ingestion.id,
        "filename":        file.filename,
        "status":          ingestion.status,
        "workflow_run_id": workflow_run.workflow_run_id,
        "message":         "PDF uploaded. Extraction is running — poll GET /ingest/{id} for results.",
    }


# ── List all ingestions ───────────────────────────────────────

@router.get("/")
def list_ingestions(db: Session = Depends(get_db)):
    """Returns all PDF ingestion records, newest first."""
    records = db.query(PDFIngestion).order_by(PDFIngestion.created_at.desc()).all()
    return [
        {
            "id":              r.id,
            "filename":        r.filename,
            "status":          r.status,
            "lender_id":       r.lender_id,
            "workflow_run_id": r.workflow_run_id,
            "created_at":      r.created_at,
        }
        for r in records
    ]


# ── Get one ingestion with extracted rules ────────────────────

@router.get("/{ingestion_id}")
def get_ingestion(ingestion_id: int, db: Session = Depends(get_db)):
    """
    Returns the ingestion record + the full extracted JSON.
    This is what the admin review screen loads.
    """
    ingestion = db.get(PDFIngestion, ingestion_id)
    if not ingestion:
        raise HTTPException(status_code=404, detail="Ingestion not found")

    extracted = json.loads(ingestion.extracted_json) if ingestion.extracted_json else None

    return {
        "id":              ingestion.id,
        "filename":        ingestion.filename,
        "status":          ingestion.status,
        "lender_id":       ingestion.lender_id,
        "workflow_run_id": ingestion.workflow_run_id,
        "error_message":   ingestion.error_message,
        "created_at":      ingestion.created_at,
        "extracted":       extracted,   # full GPT-4o output: lender_name, rules[], programs[]
    }


# ── Admin approve ─────────────────────────────────────────────

@router.post("/{ingestion_id}/approve")
def approve_ingestion(
    ingestion_id: int,
    payload: dict,          # {"rules": [...], "programs": [...]}
    db: Session = Depends(get_db),
):
    """
    Admin has reviewed the extracted rules and approved them.

    The frontend sends back the (possibly edited) list of rules and programs.
    We create the Lender + PolicyRule + LenderProgram rows and mark the
    ingestion as APPROVED.

    This is the moment extracted data becomes live in the matching engine.
    """
    ingestion = db.get(PDFIngestion, ingestion_id)
    if not ingestion:
        raise HTTPException(status_code=404, detail="Ingestion not found")
    if ingestion.status == IngestionStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Already approved")

    raw = json.loads(ingestion.extracted_json) if ingestion.extracted_json else {}

    # Create the Lender row
    lender = Lender(
        name=          payload.get("lender_name",  raw.get("lender_name", "Unknown")),
        contact_name=  payload.get("contact_name",  raw.get("contact_name")),
        contact_email= payload.get("contact_email", raw.get("contact_email")),
        contact_phone= payload.get("contact_phone", raw.get("contact_phone")),
        is_active=True,
    )
    db.add(lender)
    db.flush()   # get lender.id before adding rules

    # Write approved rules — frontend sends back only the rules admin kept/edited
    approved_rules = payload.get("rules", raw.get("rules", []))
    for r in approved_rules:
        db.add(PolicyRule(
            lender_id=           lender.id,
            rule_type=           r["rule_type"],
            operator=            r["operator"],
            value=               r["value"],
            description=         r.get("description"),
            applies_to_industry= r.get("applies_to_industry"),
            is_hard_stop=        r.get("is_hard_stop", True),
            source_quote=        r.get("source_quote"),
            is_active=True,
        ))

    # Write programs
    approved_programs = payload.get("programs", raw.get("programs", []))
    for p in approved_programs:
        db.add(LenderProgram(
            lender_id=   lender.id,
            name=        p["name"],
            min_amount=  p.get("min_amount"),
            max_amount=  p.get("max_amount"),
            credit_tier= p.get("credit_tier"),
            description= p.get("description"),
        ))

    # Mark ingestion as approved and link to the new lender
    ingestion.status    = IngestionStatus.APPROVED
    ingestion.lender_id = lender.id
    db.commit()

    return {
        "message":    f"Lender '{lender.name}' created with {len(approved_rules)} rules",
        "lender_id":  lender.id,
        "rule_count": len(approved_rules),
    }


# ── Admin reject ──────────────────────────────────────────────

@router.post("/{ingestion_id}/reject")
def reject_ingestion(ingestion_id: int, db: Session = Depends(get_db)):
    """Admin rejects the extraction — no rules are written to DB."""
    ingestion = db.get(PDFIngestion, ingestion_id)
    if not ingestion:
        raise HTTPException(status_code=404, detail="Ingestion not found")

    ingestion.status = IngestionStatus.REJECTED
    db.commit()
    return {"message": "Ingestion rejected. No rules were created."}