from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.models import RuleType, Operator, ApplicationStatus
from uuid import UUID

class PersonalGuarantorCreate(BaseModel):
    full_name:                 str
    fico_score:                int   = Field(..., ge=300, le=850)
    ownership_pct:             float = Field(..., ge=0, le=100)
    has_bankruptcy:            bool  = False
    bankruptcy_discharged_yrs: Optional[int]  = None
    is_homeowner:              bool  = False
    has_cdl:                   bool  = False
    years_cdl:                 Optional[int]  = None

    @model_validator(mode="after")
    def check_bankruptcy(self):
        if self.has_bankruptcy and self.bankruptcy_discharged_yrs is None:
            raise ValueError("bankruptcy_discharged_yrs required when has_bankruptcy is True")
        return self


class BusinessCreditCreate(BaseModel):
    paynet_score:             Optional[int]   = None
    trade_lines:              Optional[int]   = None
    comparable_credit_amount: Optional[float] = None


class BorrowerCreate(BaseModel):
    business_name:     str
    industry:          str
    state:             str   = Field(..., min_length=2, max_length=2)
    years_in_business: float = Field(..., ge=0)
    annual_revenue:    Optional[float] = None
    num_trucks:        Optional[int]   = None
    guarantors:        list[PersonalGuarantorCreate]
    biz_credit:        Optional[BusinessCreditCreate] = None


class LoanRequestCreate(BaseModel):
    amount:           float = Field(..., gt=0)
    term_months:      Optional[int]  = None
    equipment_type:   str
    equipment_year:   Optional[int]  = None
    equipment_make:   Optional[str]  = None
    equipment_model:  Optional[str]  = None
    mileage:          Optional[int]  = None
    is_private_party: bool = False


class ApplicationCreate(BaseModel):
    borrower:     BorrowerCreate
    loan_request: LoanRequestCreate



# ---------------------------------------------------------------------------
# Line Item
# ---------------------------------------------------------------------------
class InvoiceLineItemBase(BaseModel):
    line_number: Optional[int] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    discount: Optional[float] = None
    tax: Optional[float] = None
    amount: Optional[float] = None
 
 
class InvoiceLineItemOut(InvoiceLineItemBase):
    id: UUID
 
    class Config:
        from_attributes = True
 
 
# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------
class InvoiceBase(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    po_number: Optional[str] = None
    currency: Optional[str] = "USD"
 
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    vendor_email: Optional[str] = None
    vendor_phone: Optional[str] = None
 
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_tax_id: Optional[str] = None
 
    ship_to_name: Optional[str] = None
    ship_to_address: Optional[str] = None
 
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    tax_rate: Optional[float] = None
    discount_amount: Optional[float] = None
    shipping_amount: Optional[float] = None
    total_amount: Optional[float] = None
    amount_due: Optional[float] = None
 
    payment_terms: Optional[str] = None
    payment_method: Optional[str] = None
    bank_details: Optional[str] = None
    notes: Optional[str] = None
 
 
class InvoiceOut(InvoiceBase):
    id: UUID
    ingestion_id: Optional[UUID] = None
    line_items: list[InvoiceLineItemOut] = []
    created_at: datetime
    updated_at: datetime
 
    class Config:
        from_attributes = True
 
 
class InvoiceUpdate(BaseModel):
    """Partial update — only included fields are changed."""
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    po_number: Optional[str] = None
    currency: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    amount_due: Optional[float] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
 
 
# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
class InvoiceIngestionOut(BaseModel):
    id: UUID
    filename: str
    status: str
    extracted_json: Optional[dict] = None
    error_message: Optional[str] = None
    invoice: Optional[InvoiceOut] = None
    created_at: datetime
    updated_at: datetime
 
    class Config:
        from_attributes = True
 
 
class InvoiceIngestionListItem(BaseModel):
    id: UUID
    filename: str
    status: str
    created_at: datetime
 
    class Config:
        from_attributes = True