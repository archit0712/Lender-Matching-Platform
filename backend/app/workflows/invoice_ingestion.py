"""
invoice_ingestion.py — Hatchet workflow (hatchet-sdk v0.32+ standalone task API)

Same pattern as pdf_ingestion.py — one @hatchet.task that runs the full
extract → parse → save pipeline sequentially.

Reuses the shared pdf_extractor for text extraction and the invoice-specific
LLM parser for structured data extraction via GPT-4o.
"""
import base64
from hatchet_sdk import Context
from app.worker import hatchet
from app.services.invoice_parser import extract_and_parse_invoice_bytes
from app.database import SessionLocal
from app.models.invoices import Invoice, InvoiceIngestion, InvoiceLineItem


@hatchet.task(
    name="invoice-ingestion",
    execution_timeout="300s",   # 5 min total — OCR + GPT-4o can be slow
    retries=2,
)
def run_invoice_ingestion(input, ctx: Context) -> dict:
    """
    Full pipeline in one task:
      1. Decode PDF bytes from base64
      2. Extract text (pdfplumber → OCR fallback for scanned PDFs)
      3. Parse invoice with GPT-4o via instructor
      4. Save Invoice + InvoiceLineItems to DB, update ingestion status

    Input keys:
      pdf_base64    : base64-encoded PDF bytes
      filename      : original filename
      ingestion_id  : InvoiceIngestion row ID created before triggering
    """
    inp          = input.model_dump() if hasattr(input, "model_dump") else dict(input)
    filename     = inp["filename"]
    ingestion_id = inp["ingestion_id"]
    raw_bytes    = base64.b64decode(inp["pdf_base64"])

    # ── Steps 1+2: Extract text (with OCR fallback) + parse with GPT-4o ──
    ctx.log(f"[1/2] Extracting and parsing {filename} (OCR if needed)...")
    parsed = extract_and_parse_invoice_bytes(raw_bytes, filename)
    ctx.log(
        f"[1/2] Done — invoice #{parsed.invoice_number or 'N/A'}: "
        f"{len(parsed.line_items)} line items, total={parsed.total_amount}"
    )

    # ── Step 2: Save to DB ───────────────────────────────────
    ctx.log("[2/2] Saving to database...")
    db = SessionLocal()
    try:
        ingestion = db.get(InvoiceIngestion, ingestion_id)
        if not ingestion:
            raise ValueError(f"InvoiceIngestion row {ingestion_id} not found")

        # Store full extracted JSON for reference
        parsed_dict = parsed.model_dump()
        ingestion.extracted_json = parsed_dict

        # Create Invoice row (exclude non-DB fields)
        line_items_data = parsed_dict.pop("line_items", [])
        parsed_dict.pop("extraction_notes", None)

        invoice = Invoice(ingestion_id=ingestion_id, **parsed_dict)
        db.add(invoice)
        db.flush()  # get invoice.id

        # Create line item rows
        for li in line_items_data:
            db.add(InvoiceLineItem(invoice_id=invoice.id, **li))

        ingestion.status = "COMPLETED"
        db.commit()
        ctx.log(f"[2/2] Saved — invoice {invoice.id}, ingestion {ingestion_id} is COMPLETED")

    except Exception:
        db.rollback()
        # Mark ingestion as failed
        try:
            ingestion = db.get(InvoiceIngestion, ingestion_id)
            if ingestion:
                ingestion.status = "FAILED"
                ingestion.error_message = str(Exception)[:2000]
                db.commit()
        except Exception:
            db.rollback()
        raise  # let Hatchet handle the retry
    finally:
        db.close()

    return {
        "ingestion_id":   ingestion_id,
        "invoice_id":     str(invoice.id),
        "invoice_number": parsed.invoice_number,
        "line_item_count": len(parsed.line_items),
        "total_amount":   parsed.total_amount,
    }