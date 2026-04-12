"""add invoice tables

Revision ID: 0002_add_invoices
Revises: <FILL_IN_YOUR_LATEST_REVISION_ID>
Create Date: 2026-04-11

To use:
  1. Replace 'Revises' above with your current head revision ID
     (run `alembic heads` to find it).
  2. Copy this file into backend/alembic/versions/
  3. Run `alembic upgrade head`
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "0002_add_invoices"
down_revision = '41ce143ad072'  # ← REPLACE with your current head revision
branch_labels = None
depends_on = None

# One shared PG ENUM instance: explicit .create() + reuse on the column so the
# dialect does not emit CREATE TYPE again during create_table.
invoice_ingestion_status_enum = postgresql.ENUM(
    "PENDING",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    name="invoice_ingestion_status",
    create_type=False,
)


def upgrade() -> None:
    invoice_ingestion_status_enum.create(op.get_bind(), checkfirst=True)

    # -- invoice_ingestions --
    op.create_table(
        "invoice_ingestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column(
            "status",
            invoice_ingestion_status_enum,
            nullable=False,
            server_default=sa.text("'PENDING'::invoice_ingestion_status"),
        ),
        sa.Column("extracted_json", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # -- invoices --
    op.create_table(
        "invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ingestion_id",
            UUID(as_uuid=True),
            sa.ForeignKey("invoice_ingestions.id"),
            nullable=True,
        ),
        sa.Column("invoice_number", sa.String, nullable=True),
        sa.Column("invoice_date", sa.String, nullable=True),
        sa.Column("due_date", sa.String, nullable=True),
        sa.Column("po_number", sa.String, nullable=True),
        sa.Column("currency", sa.String, server_default="USD"),
        sa.Column("vendor_name", sa.String, nullable=True),
        sa.Column("vendor_address", sa.Text, nullable=True),
        sa.Column("vendor_tax_id", sa.String, nullable=True),
        sa.Column("vendor_email", sa.String, nullable=True),
        sa.Column("vendor_phone", sa.String, nullable=True),
        sa.Column("buyer_name", sa.String, nullable=True),
        sa.Column("buyer_address", sa.Text, nullable=True),
        sa.Column("buyer_tax_id", sa.String, nullable=True),
        sa.Column("ship_to_name", sa.String, nullable=True),
        sa.Column("ship_to_address", sa.Text, nullable=True),
        sa.Column("subtotal", sa.Float, nullable=True),
        sa.Column("tax_amount", sa.Float, nullable=True),
        sa.Column("tax_rate", sa.Float, nullable=True),
        sa.Column("discount_amount", sa.Float, nullable=True),
        sa.Column("shipping_amount", sa.Float, nullable=True),
        sa.Column("total_amount", sa.Float, nullable=True),
        sa.Column("amount_due", sa.Float, nullable=True),
        sa.Column("payment_terms", sa.String, nullable=True),
        sa.Column("payment_method", sa.String, nullable=True),
        sa.Column("bank_details", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # -- invoice_line_items --
    op.create_table(
        "invoice_line_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sku", sa.String, nullable=True),
        sa.Column("quantity", sa.Float, nullable=True),
        sa.Column("unit", sa.String, nullable=True),
        sa.Column("unit_price", sa.Float, nullable=True),
        sa.Column("discount", sa.Float, nullable=True),
        sa.Column("tax", sa.Float, nullable=True),
        sa.Column("amount", sa.Float, nullable=True),
    )

    op.create_index("ix_invoice_line_items_invoice_id", "invoice_line_items", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("invoice_line_items")
    op.drop_table("invoices")
    op.drop_table("invoice_ingestions")
    invoice_ingestion_status_enum.drop(op.get_bind(), checkfirst=True)