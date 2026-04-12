"""
Invoice extraction models.

Add these to your existing backend/app/models/__init__.py imports:

    from app.models.invoice import Invoice, InvoiceLineItem, InvoiceIngestion
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    DateTime,
    Text,
    ForeignKey,
    Enum as SAEnum,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base  # reuse existing Base


# ---------------------------------------------------------------------------
# Invoice Ingestion — tracks PDF upload + extraction status
# ---------------------------------------------------------------------------
class InvoiceIngestion(Base):
    __tablename__ = "invoice_ingestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    status = Column(
        SAEnum(
            "PENDING", "PROCESSING", "COMPLETED", "FAILED",
            name="invoice_ingestion_status",
        ),
        default="PENDING",
        nullable=False,
    )
    extracted_json = Column(JSON, nullable=True)   # raw GPT-4o output
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # one ingestion → one invoice (created after extraction succeeds)
    invoice = relationship("Invoice", back_populates="ingestion", uselist=False)


# ---------------------------------------------------------------------------
# Invoice — structured header data
# ---------------------------------------------------------------------------
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingestion_id = Column(
        UUID(as_uuid=True), ForeignKey("invoice_ingestions.id"), nullable=True
    )

    # ----- header fields -----
    invoice_number = Column(String, nullable=True)
    invoice_date = Column(String, nullable=True)      # kept as string for flexibility
    due_date = Column(String, nullable=True)
    po_number = Column(String, nullable=True)
    currency = Column(String, default="USD")

    # vendor / seller
    vendor_name = Column(String, nullable=True)
    vendor_address = Column(Text, nullable=True)
    vendor_tax_id = Column(String, nullable=True)
    vendor_email = Column(String, nullable=True)
    vendor_phone = Column(String, nullable=True)

    # buyer / bill-to
    buyer_name = Column(String, nullable=True)
    buyer_address = Column(Text, nullable=True)
    buyer_tax_id = Column(String, nullable=True)

    # ship-to (optional)
    ship_to_name = Column(String, nullable=True)
    ship_to_address = Column(Text, nullable=True)

    # totals
    subtotal = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    tax_rate = Column(Float, nullable=True)            # percentage
    discount_amount = Column(Float, nullable=True)
    shipping_amount = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True)
    amount_due = Column(Float, nullable=True)

    # payment
    payment_terms = Column(String, nullable=True)      # e.g. "Net 30"
    payment_method = Column(String, nullable=True)
    bank_details = Column(Text, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    ingestion = relationship("InvoiceIngestion", back_populates="invoice")
    line_items = relationship(
        "InvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLineItem.line_number",
    )


# ---------------------------------------------------------------------------
# Invoice Line Item
# ---------------------------------------------------------------------------
class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    line_number = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    sku = Column(String, nullable=True)
    quantity = Column(Float, nullable=True)
    unit = Column(String, nullable=True)               # e.g. "ea", "hr", "kg"
    unit_price = Column(Float, nullable=True)
    discount = Column(Float, nullable=True)
    tax = Column(Float, nullable=True)
    amount = Column(Float, nullable=True)              # qty × price − discount + tax

    invoice = relationship("Invoice", back_populates="line_items")