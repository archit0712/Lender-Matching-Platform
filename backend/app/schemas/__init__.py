from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.models import RuleType, Operator, ApplicationStatus


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