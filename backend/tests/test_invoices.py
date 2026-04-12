"""
Manual test — runs the full extraction + GPT-4o invoice parsing pipeline.

Handles both native-text PDFs (pdfplumber) and scanned PDFs (OCR fallback).

Usage:
    cd backend
    python tests/test_invoice_parsing.py pdfs/Sacramento_County_Utilities.pdf

This does NOT require the API or Hatchet to be running.
It calls the pdf_extractor and invoice_parser services directly.
"""
import sys, json

sys.path.insert(0, ".")

from app.services.pdf_extractor import extract_pdf
from app.services.invoice_parser import (
    parse_invoice_text,
    _ocr_pdf_from_path,
    MIN_USEFUL_CHARS,
)

if len(sys.argv) < 2:
    print("Usage: python tests/test_invoice_parsing.py <path_to_pdf>")
    sys.exit(1)

pdf_path = sys.argv[1]

# ── Step 1: Extract text from PDF ────────────────────────────
print(f"\n{'='*60}")
print(f"  INVOICE EXTRACTION TEST")
print(f"  File: {pdf_path}")
print(f"{'='*60}")

print(f"\n[1/3] Extracting text from PDF...")
extracted = extract_pdf(pdf_path)
content = extracted.full_content()
extraction_method = "pdfplumber"

print(f"  pdfplumber: {len(content.strip())} chars, {len(extracted.tables)} tables, {extracted.page_count} pages")

# OCR fallback if pdfplumber got nothing useful
if len(content.strip()) < MIN_USEFUL_CHARS:
    print(f"  ⚠ pdfplumber returned < {MIN_USEFUL_CHARS} chars — scanned PDF detected")
    print(f"  Falling back to OCR (pdf2image + pytesseract)...")
    content = _ocr_pdf_from_path(pdf_path)
    extraction_method = "OCR (pytesseract)"
    print(f"  OCR: {len(content.strip())} chars extracted")
    if len(content.strip()) < MIN_USEFUL_CHARS:
        print(f"\n  ✗ FAILED: Neither pdfplumber nor OCR could extract text.")
        sys.exit(1)

print(f"  ✓ Using {extraction_method}")

# Show a preview of what GPT-4o will receive
print(f"\n── EXTRACTED TEXT PREVIEW (first 600 chars) ──────────────")
print(content[:600])
print("…\n")

# ── Step 2: Send to GPT-4o ────────────────────────────────────
print("[2/3] Sending to GPT-4o via instructor...")
print("  (This takes 10-30 seconds)\n")
invoice = parse_invoice_text(content, extracted.source_filename)
print("  ✓ GPT-4o extraction complete")

# ── Step 3: Print results ─────────────────────────────────────
print(f"\n{'='*60}")
print("  EXTRACTED INVOICE DATA")
print(f"{'='*60}")

# Header
print(f"\n  Invoice/Acct #: {invoice.invoice_number or '—'}")
print(f"  Invoice Date:   {invoice.invoice_date or '—'}")
print(f"  Due Date:       {invoice.due_date or '—'}")
print(f"  PO Number:      {invoice.po_number or '—'}")
print(f"  Currency:       {invoice.currency}")

# Vendor
print(f"\n── VENDOR / SELLER ──────────────────────────────────────")
print(f"  Name:     {invoice.vendor_name or '—'}")
print(f"  Address:  {invoice.vendor_address or '—'}")
print(f"  Tax ID:   {invoice.vendor_tax_id or '—'}")
print(f"  Email:    {invoice.vendor_email or '—'}")
print(f"  Phone:    {invoice.vendor_phone or '—'}")

# Buyer
print(f"\n── BUYER / BILL TO ──────────────────────────────────────")
print(f"  Name:     {invoice.buyer_name or '—'}")
print(f"  Address:  {invoice.buyer_address or '—'}")
print(f"  Tax ID:   {invoice.buyer_tax_id or '—'}")

# Ship-to
if invoice.ship_to_name or invoice.ship_to_address:
    print(f"\n── SHIP TO ──────────────────────────────────────────────")
    print(f"  Name:     {invoice.ship_to_name or '—'}")
    print(f"  Address:  {invoice.ship_to_address or '—'}")

# Line items
print(f"\n── LINE ITEMS ({len(invoice.line_items)}) ─────────────────────────────────")
if invoice.line_items:
    print(f"  {'#':<4} {'Description':<40} {'Qty':>6} {'Unit Price':>12} {'Amount':>12}")
    print(f"  {'─'*4} {'─'*40} {'─'*6} {'─'*12} {'─'*12}")

    for li in invoice.line_items:
        num = str(li.line_number or "")
        desc = (li.description or "—")[:40]
        qty = f"{li.quantity:.0f}" if li.quantity is not None else "—"
        price = f"${li.unit_price:,.2f}" if li.unit_price is not None else "—"
        amt = f"${li.amount:,.2f}" if li.amount is not None else "—"
        print(f"  {num:<4} {desc:<40} {qty:>6} {price:>12} {amt:>12}")
else:
    print("  (none extracted)")

# Totals
print(f"\n── TOTALS ───────────────────────────────────────────────")
def fmt(val, label, prefix="$"):
    if val is not None:
        print(f"  {label:<25} {prefix}{val:>12,.2f}")
    else:
        print(f"  {label:<25} {'—':>13}")

fmt(invoice.subtotal,        "Subtotal:")
fmt(invoice.discount_amount, "Discount:")
fmt(invoice.shipping_amount, "Shipping:")
if invoice.tax_rate is not None:
    print(f"  {'Tax Rate:':<25} {invoice.tax_rate:>12}%")
fmt(invoice.tax_amount,      "Tax Amount:")
print(f"  {'─'*40}")
fmt(invoice.total_amount,    "TOTAL:")
fmt(invoice.amount_due,      "Amount Due:")

# Payment
print(f"\n── PAYMENT ──────────────────────────────────────────────")
print(f"  Terms:   {invoice.payment_terms or '—'}")
print(f"  Method:  {invoice.payment_method or '—'}")
if invoice.bank_details:
    print(f"  Bank:    {invoice.bank_details}")

# Notes
if invoice.notes:
    print(f"\n── NOTES ────────────────────────────────────────────────")
    print(f"  {invoice.notes[:300]}")

# Extraction notes from GPT-4o
if invoice.extraction_notes:
    print(f"\n── EXTRACTION NOTES (from GPT-4o) ───────────────────────")
    print(f"  {invoice.extraction_notes}")

# ── Step 4: Validation ────────────────────────────────────────
print(f"\n── VALIDATION ───────────────────────────────────────────")
checks_passed = 0
checks_total = 0

def check(condition: bool, label: str):
    global checks_passed, checks_total
    checks_total += 1
    status = "✓" if condition else "✗"
    if condition:
        checks_passed += 1
    print(f"  {status} {label}")

check(invoice.invoice_number is not None, "Invoice/account number extracted")
check(invoice.vendor_name is not None,    "Vendor name extracted")
check(invoice.buyer_name is not None,     "Buyer/account holder name extracted")
check(invoice.total_amount is not None,   "Total amount extracted")
check(invoice.amount_due is not None,     "Amount due extracted")
check(invoice.due_date is not None,       "Due date extracted")
check(len(invoice.line_items) > 0,        "At least one line item/charge")

if invoice.total_amount and invoice.amount_due:
    diff = abs(invoice.total_amount - invoice.amount_due)
    check(diff < 0.02, f"Total ({invoice.total_amount:,.2f}) ≈ Amount Due ({invoice.amount_due:,.2f})")

if invoice.line_items:
    line_sum = sum(li.amount for li in invoice.line_items if li.amount is not None)
    if line_sum > 0 and invoice.subtotal:
        check(
            abs(line_sum - invoice.subtotal) < 5.0,
            f"Line items sum ({line_sum:,.2f}) ≈ Subtotal ({invoice.subtotal:,.2f})"
        )
    elif line_sum > 0 and invoice.total_amount:
        # Some bills don't have a separate subtotal
        check(
            line_sum <= invoice.total_amount * 1.1,
            f"Line items sum ({line_sum:,.2f}) ≤ Total ({invoice.total_amount:,.2f})"
        )

# Sacramento County specific checks (if this is that PDF)
if invoice.vendor_name and "sacramento" in invoice.vendor_name.lower():
    print(f"\n── SACRAMENTO COUNTY UTILITY BILL CHECKS ────────────────")
    check(
        invoice.invoice_number is not None and "50008285092" in str(invoice.invoice_number),
        f"Account number is 50008285092 (got: {invoice.invoice_number})"
    )
    check(
        invoice.amount_due is not None and abs(invoice.amount_due - 1231.46) < 0.02,
        f"Amount due is $1,231.46 (got: ${invoice.amount_due:,.2f})" if invoice.amount_due else "Amount due missing"
    )
    check(
        invoice.due_date is not None and "may" in invoice.due_date.lower() and "9" in invoice.due_date,
        f"Due date is May 9, 2026 (got: {invoice.due_date})"
    )
    check(
        invoice.buyer_name is not None and "prb" in invoice.buyer_name.lower(),
        f"Buyer is PRB Management LLC (got: {invoice.buyer_name})"
    )

print(f"\n  {checks_passed}/{checks_total} checks passed")

# ── Step 5: Dump raw JSON ─────────────────────────────────────
print(f"\n── RAW JSON OUTPUT ──────────────────────────────────────")
raw = invoice.model_dump()
print(json.dumps(raw, indent=2))

# ── Summary ───────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  Extraction method:  {extraction_method}")
print(f"  Text chars:         {len(content.strip()):,}")
print(f"  Vendor:             {invoice.vendor_name or '—'}")
print(f"  Buyer:              {invoice.buyer_name or '—'}")
print(f"  Line items:         {len(invoice.line_items)}")
print(f"  Total:              ${invoice.total_amount:,.2f}" if invoice.total_amount else "  Total:              —")
print(f"  Checks:             {checks_passed}/{checks_total} passed")
print(f"{'='*60}\n")