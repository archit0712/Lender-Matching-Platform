"""
invoice_parser.py

Responsibility: extracted PDF text → structured ParsedInvoice
Uses instructor + GPT-4o to guarantee output matches our Pydantic schema.

Design follows the same pattern as llm_parser.py but for invoices:
  - ParsedInvoice is separate from DB models (unvalidated LLM output).
  - We reuse pdf_extractor.py for text extraction — no duplicated pdfplumber code.
  - Falls back to OCR (pdf2image + pytesseract) when pdfplumber returns no text
    (common with scanned invoices / utility bills).
  - Every field is Optional because real invoices are messy; the LLM extracts
    what it can find and leaves the rest null.
"""

import io
import logging
import tempfile
import os
from pathlib import Path
from typing import Optional

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.services.pdf_extractor import extract_pdf, extract_pdf_from_bytes, ExtractedPDF
from pdf2image import convert_from_path
import pytesseract
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# OUTPUT SCHEMA
# instructor enforces this — if GPT-4o returns something that
# doesn't match, it retries with the validation error as feedback.
# ─────────────────────────────────────────────────────────────

class ParsedLineItem(BaseModel):
    """One line item from an invoice."""
    line_number: Optional[int] = Field(default=None, description="Sequential line number on the invoice")
    description: Optional[str] = Field(default=None, description="Item or service description")
    sku: Optional[str] = Field(default=None, description="SKU, item code, or part number if present")
    quantity: Optional[float] = Field(default=None, description="Quantity as a number, no units")
    unit: Optional[str] = Field(default=None, description="Unit of measure e.g. 'ea', 'hr', 'kg', 'lot'")
    unit_price: Optional[float] = Field(default=None, description="Price per unit, numeric only, no currency symbols")
    discount: Optional[float] = Field(default=None, description="Discount amount for this line, numeric only")
    tax: Optional[float] = Field(default=None, description="Tax amount for this line, numeric only")
    amount: Optional[float] = Field(default=None, description="Line total (qty × price − discount + tax), numeric only")


class ParsedInvoice(BaseModel):
    """
    Complete structured output from one invoice PDF.
    This is what gets stored as extracted_json on InvoiceIngestion
    and used to populate the Invoice + InvoiceLineItem DB rows.
    """

    # ── Reference numbers ────────────────────────────────────
    invoice_number: Optional[str] = Field(default=None, description="Invoice number, account number, or bill ID")
    invoice_date: Optional[str] = Field(default=None, description="Invoice/bill date as it appears in the document")
    due_date: Optional[str] = Field(default=None, description="Payment due date as it appears in the document")
    po_number: Optional[str] = Field(default=None, description="Purchase order number if present")
    currency: str = Field(default="USD", description="ISO 4217 currency code e.g. 'USD', 'EUR', 'GBP'")

    # ── Vendor (seller) ──────────────────────────────────────
    vendor_name: Optional[str] = Field(default=None, description="Full legal name of the vendor/seller/utility provider")
    vendor_address: Optional[str] = Field(default=None, description="Full vendor address as one string")
    vendor_tax_id: Optional[str] = Field(default=None, description="Vendor tax ID / EIN / VAT number")
    vendor_email: Optional[str] = Field(default=None, description="Vendor email address")
    vendor_phone: Optional[str] = Field(default=None, description="Vendor phone number")

    # ── Buyer (bill-to) ──────────────────────────────────────
    buyer_name: Optional[str] = Field(default=None, description="Full name of the buyer / bill-to party / account holder")
    buyer_address: Optional[str] = Field(default=None, description="Full buyer/service address as one string")
    buyer_tax_id: Optional[str] = Field(default=None, description="Buyer tax ID / EIN if present")

    # ── Ship-to (optional) ───────────────────────────────────
    ship_to_name: Optional[str] = Field(default=None, description="Ship-to name if different from buyer")
    ship_to_address: Optional[str] = Field(default=None, description="Ship-to address if different from buyer")

    # ── Totals ───────────────────────────────────────────────
    subtotal: Optional[float] = Field(default=None, description="Subtotal before tax/discount/shipping, numeric only")
    tax_amount: Optional[float] = Field(default=None, description="Total tax amount, numeric only")
    tax_rate: Optional[float] = Field(default=None, description="Tax rate as a percentage number e.g. 8.5 for 8.5%")
    discount_amount: Optional[float] = Field(default=None, description="Total discount amount, numeric only")
    shipping_amount: Optional[float] = Field(default=None, description="Shipping/freight amount, numeric only")
    total_amount: Optional[float] = Field(default=None, description="Grand total / total amount due, numeric only")
    amount_due: Optional[float] = Field(default=None, description="Amount due (may differ from total if partial payment or credits), numeric only")

    # ── Payment ──────────────────────────────────────────────
    payment_terms: Optional[str] = Field(default=None, description="Payment terms e.g. 'Net 30', 'Due on receipt', or specific date")
    payment_method: Optional[str] = Field(default=None, description="Accepted payment method if stated")
    bank_details: Optional[str] = Field(default=None, description="Bank/wire transfer details if present")

    notes: Optional[str] = Field(default=None, description="Any notes, terms, or comments from the invoice")

    # ── Line items ───────────────────────────────────────────
    line_items: list[ParsedLineItem] = Field(default_factory=list, description="All line items / charges on the invoice")

    # ── Extraction metadata ──────────────────────────────────
    extraction_notes: Optional[str] = Field(
        default=None,
        description=(
            "Any ambiguities or issues encountered during extraction. "
            "E.g. 'Tax rate not explicitly stated, calculated from subtotal and tax amount.'"
        ),
    )


# ─────────────────────────────────────────────────────────────
# OCR FALLBACK FOR SCANNED PDFs
# ─────────────────────────────────────────────────────────────

def _ocr_pdf_from_path(file_path: str) -> str:
    """Convert PDF pages to images and run OCR. Returns extracted text."""


    logger.info(f"Running OCR on {file_path}...")
    images = convert_from_path(file_path, dpi=300)
    pages = []
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img)
        if text.strip():
            pages.append(f"[Page {i + 1}]\n{text.strip()}")
    return "\n\n".join(pages)


def _ocr_pdf_from_bytes(pdf_bytes: bytes) -> str:
    """Same as _ocr_pdf_from_path but accepts raw bytes."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        return _ocr_pdf_from_path(tmp_path)
    finally:
        os.unlink(tmp_path)


MIN_USEFUL_CHARS = 50  # pdfplumber output below this is considered empty


# ─────────────────────────────────────────────────────────────
# THE PROMPT
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert invoice data extraction assistant.

Your job is to extract ALL structured data from invoice documents with precision.
This includes commercial invoices, utility bills, service statements, and any billing document.

WHAT TO EXTRACT:
- Invoice identifiers: invoice number (or account number for utility bills), date, due date, PO number
- Vendor/seller: name, full address, tax ID, email, phone
- Buyer/bill-to: name, full address, tax ID
- Ship-to: name and address (only if different from buyer)
- Every line item or charge: description, quantity, unit, unit price, line total
- Totals: subtotal, tax (amount and rate), discount, shipping, grand total, amount due
- Payment terms: Net 30, due on receipt, specific due date, etc.
- Payment method and bank/wire details if present
- Currency: detect from symbols ($, €, £) or explicit mentions; default to USD

RULES:
1. Return numeric values ONLY as numbers — no currency symbols, commas, or units.
   "$1,234.56" → 1234.56
2. Return dates in the format they appear in the document — do not reformat.
3. If a field is not present in the document, leave it null. NEVER fabricate data.
4. For addresses, combine all lines into a single string.
5. Tax rate should be a percentage number: 8.5 for 8.5%, not 0.085.
6. If amount_due is not explicitly stated, assume it equals total_amount.
7. Line items should preserve the order they appear in the document.
8. If the line item amount is not stated but qty and unit_price are, calculate it.
9. For utility bills: treat each service charge (water, sewer, stormwater, etc.) as a line item.
10. For utility bills: use the account number as invoice_number if no invoice number exists.
11. Note any ambiguities or issues in extraction_notes.
"""


def _build_user_prompt(content: str, filename: str) -> str:
    return f"""Extract all data from this invoice/billing document.

Document filename: {filename}

Document content:
{content}

Extract every field you can find. For line items, capture all charges or rows.
If you find multiple interpretations for a value, pick the most likely one and note the ambiguity.
"""


# ─────────────────────────────────────────────────────────────
# POST-PROCESSING
# ─────────────────────────────────────────────────────────────

def _post_process(invoice: ParsedInvoice) -> ParsedInvoice:
    """
    Light cleanup after LLM extraction. We keep it minimal because
    the frontend shows the raw data for human review.
    """
    # Ensure line_number is set sequentially if missing
    for i, item in enumerate(invoice.line_items):
        if item.line_number is None:
            item.line_number = i + 1

    # If amount_due is missing but total_amount exists, copy it
    if invoice.amount_due is None and invoice.total_amount is not None:
        invoice.amount_due = invoice.total_amount

    # Calculate subtotal from line items if missing
    if invoice.subtotal is None and invoice.line_items:
        line_amounts = [li.amount for li in invoice.line_items if li.amount is not None]
        if line_amounts:
            invoice.subtotal = round(sum(line_amounts), 2)

    return invoice


# ─────────────────────────────────────────────────────────────
# MAIN FUNCTIONS
# ─────────────────────────────────────────────────────────────

def parse_invoice_text(extracted_content: str, filename: str) -> ParsedInvoice:
    """
    Send extracted PDF content to GPT-4o and get back a structured invoice.

    Args:
        extracted_content : text content from the PDF (pdfplumber or OCR)
        filename          : original PDF filename (used in the prompt for context)

    Returns:
        ParsedInvoice — guaranteed valid by instructor, ready for review/storage

    Raises:
        instructor.exceptions.InstructorRetryException : if GPT-4o fails after max_retries
        openai.APIError                                : if the API call itself fails
    """
    client = instructor.from_openai(
        OpenAI(api_key=settings.openai_api_key),
        mode=instructor.Mode.JSON,
    )

    invoice = client.chat.completions.create(
        model="gpt-4o",
        max_retries=3,
        response_model=ParsedInvoice,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(extracted_content, filename)},
        ],
        temperature=0,
    )

    return _post_process(invoice)


def extract_and_parse_invoice(file_path: str) -> ParsedInvoice:
    """
    Full pipeline: PDF file path → text extraction (with OCR fallback) → ParsedInvoice.
    """
    # Try pdfplumber first (fast, no GPU needed)
    extracted: ExtractedPDF = extract_pdf(file_path)
    content = extracted.full_content()

    # If pdfplumber got almost nothing, this is likely a scanned PDF — use OCR
    if len(content.strip()) < MIN_USEFUL_CHARS:
        logger.info(
            f"pdfplumber extracted only {len(content.strip())} chars — "
            f"falling back to OCR for {file_path}"
        )
        content = _ocr_pdf_from_path(file_path)
        if len(content.strip()) < MIN_USEFUL_CHARS:
            raise ValueError(
                f"Could not extract text from {file_path} "
                f"(pdfplumber and OCR both returned < {MIN_USEFUL_CHARS} chars)"
            )

    return parse_invoice_text(content, extracted.source_filename)


def extract_and_parse_invoice_bytes(file_bytes: bytes, filename: str) -> ParsedInvoice:
    """
    Full pipeline: PDF bytes → text extraction (with OCR fallback) → ParsedInvoice.
    """
    # Try pdfplumber first
    extracted: ExtractedPDF = extract_pdf_from_bytes(file_bytes, filename)
    content = extracted.full_content()

    # OCR fallback for scanned PDFs
    if len(content.strip()) < MIN_USEFUL_CHARS:
        logger.info(
            f"pdfplumber extracted only {len(content.strip())} chars — "
            f"falling back to OCR for {filename}"
        )
        content = _ocr_pdf_from_bytes(file_bytes)
        if len(content.strip()) < MIN_USEFUL_CHARS:
            raise ValueError(
                f"Could not extract text from {filename} "
                f"(pdfplumber and OCR both returned < {MIN_USEFUL_CHARS} chars)"
            )

    return parse_invoice_text(content, filename)