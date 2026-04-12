"""
Invoice API router.

Register in your existing main.py:
    from app.routers.invoices import router as invoices_router
    app.include_router(invoices_router, prefix="/invoices", tags=["invoices"])
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.invoices import Invoice, InvoiceIngestion, InvoiceLineItem
from app.schemas import (
    InvoiceIngestionListItem,
    InvoiceIngestionOut,
    InvoiceOut,
    InvoiceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Upload PDF ─────────────────────────────────────────────────────────────
@router.post("/upload", status_code=202, response_model=InvoiceIngestionOut)
async def upload_invoice_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload an invoice PDF → create ingestion record → trigger async extraction."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    pdf_bytes = await file.read()

    # Create ingestion row
    ingestion = InvoiceIngestion(filename=file.filename, status="PENDING")
    db.add(ingestion)
    db.commit()
    db.refresh(ingestion)

    # Trigger Hatchet task (same pattern as POST /ingest/pdf — SDK method names vary)
    from app.workflows.invoice_ingestion import run_invoice_ingestion

    payload = {
        "ingestion_id": str(ingestion.id),
        "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
        "filename": file.filename,
    }
    workflow_run = None
    last_error = None
    loop = asyncio.get_event_loop()

    for method_name in ["run_no_wait", "run", "spawn", "trigger"]:
        method = getattr(run_invoice_ingestion, method_name, None)
        if method is None:
            continue
        try:
            workflow_run = await loop.run_in_executor(None, lambda m=method: m(payload))
            break
        except Exception as e:
            last_error = f"{method_name}: {e}"
            continue

    if workflow_run is None:
        logger.error(
            "Could not trigger invoice extraction workflow. Last error: %s",
            last_error,
        )
        ingestion.status = "FAILED"
        ingestion.error_message = (
            f"Workflow trigger failed: {last_error or 'no callable trigger method'}"
        )
        db.commit()
        raise HTTPException(502, "Failed to start extraction workflow.")

    return ingestion


# ── List ingestions ────────────────────────────────────────────────────────
@router.get("/ingestions", response_model=list[InvoiceIngestionListItem])
def list_invoice_ingestions(db: Session = Depends(get_db)):
    """List all invoice ingestion records (newest first)."""
    return (
        db.query(InvoiceIngestion)
        .order_by(InvoiceIngestion.created_at.desc())
        .all()
    )


# ── Get single ingestion (with extracted data + invoice) ──────────────────
@router.get("/ingestions/{ingestion_id}", response_model=InvoiceIngestionOut)
def get_invoice_ingestion(ingestion_id: UUID, db: Session = Depends(get_db)):
    """Get an ingestion record with its extracted JSON and linked invoice."""
    ingestion = (
        db.query(InvoiceIngestion)
        .options(
            joinedload(InvoiceIngestion.invoice).joinedload(Invoice.line_items)
        )
        .filter(InvoiceIngestion.id == ingestion_id)
        .first()
    )
    if not ingestion:
        raise HTTPException(404, "Ingestion not found.")
    return ingestion


# ── List invoices ──────────────────────────────────────────────────────────
@router.get("/", response_model=list[InvoiceOut])
def list_invoices(db: Session = Depends(get_db)):
    """List all extracted invoices (newest first)."""
    return (
        db.query(Invoice)
        .options(joinedload(Invoice.line_items))
        .order_by(Invoice.created_at.desc())
        .all()
    )


# ── Get single invoice ────────────────────────────────────────────────────
@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: UUID, db: Session = Depends(get_db)):
    """Get a single invoice with line items."""
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.line_items))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(404, "Invoice not found.")
    return invoice


# ── Update invoice (partial) ──────────────────────────────────────────────
@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: UUID,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
):
    """Partial update of invoice header fields (e.g. after manual review)."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)

    db.commit()
    db.refresh(invoice)
    return (
        db.query(Invoice)
        .options(joinedload(Invoice.line_items))
        .filter(Invoice.id == invoice_id)
        .first()
    )


# ── Delete invoice ─────────────────────────────────────────────────────────
@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: UUID, db: Session = Depends(get_db)):
    """Delete an invoice and its line items."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found.")
    db.delete(invoice)
    db.commit()


# ── Raw JSON export ────────────────────────────────────────────────────────
@router.get("/{invoice_id}/json")
def get_invoice_json(invoice_id: UUID, db: Session = Depends(get_db)):
    """Return the extracted invoice as a clean JSON object (for download/integration)."""
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.line_items))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(404, "Invoice not found.")

    schema = InvoiceOut.model_validate(invoice)
    return schema.model_dump(mode="json")