import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

from app.models.invoices import Invoice, InvoiceLineItem, InvoiceIngestion
# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class RuleType(str, enum.Enum):
    MIN_FICO                        = "MIN_FICO"
    MIN_PAYNET                      = "MIN_PAYNET"
    MIN_YEARS_IN_BUSINESS           = "MIN_YEARS_IN_BUSINESS"
    MAX_LOAN_AMOUNT                 = "MAX_LOAN_AMOUNT"
    MIN_LOAN_AMOUNT                 = "MIN_LOAN_AMOUNT"
    EQUIPMENT_MAX_AGE_YEARS         = "EQUIPMENT_MAX_AGE_YEARS"
    MAX_MILEAGE                     = "MAX_MILEAGE"
    EXCLUDED_STATE                  = "EXCLUDED_STATE"
    EXCLUDED_INDUSTRY               = "EXCLUDED_INDUSTRY"
    BANKRUPTCY_MIN_YEARS_DISCHARGED = "BANKRUPTCY_MIN_YEARS_DISCHARGED"
    REQUIRES_HOMEOWNERSHIP          = "REQUIRES_HOMEOWNERSHIP"
    MIN_COMPARABLE_CREDIT_PCT       = "MIN_COMPARABLE_CREDIT_PCT"
    TRUCKING_MIN_TRUCKS             = "TRUCKING_MIN_TRUCKS"
    MAX_LOAN_AMOUNT_BY_INDUSTRY     = "MAX_LOAN_AMOUNT_BY_INDUSTRY"


class Operator(str, enum.Enum):
    GTE = "GTE"
    LTE = "LTE"
    EQ  = "EQ"
    NEQ = "NEQ"


class ApplicationStatus(str, enum.Enum):
    DRAFT     = "DRAFT"
    SUBMITTED = "SUBMITTED"
    MATCHED   = "MATCHED"
    ERROR     = "ERROR"


class IngestionStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED       = "APPROVED"
    REJECTED       = "REJECTED"


# ─────────────────────────────────────────────
# LENDER & POLICY TABLES
# ─────────────────────────────────────────────

class Lender(Base):
    __tablename__ = "lenders"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:          Mapped[str]           = mapped_column(String(120), nullable=False)
    contact_name:  Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(40),  nullable=True)
    is_active:     Mapped[bool]          = mapped_column(Boolean, default=True)
    notes:         Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rules:    Mapped[list["PolicyRule"]]    = relationship("PolicyRule",    back_populates="lender", cascade="all, delete-orphan")
    programs: Mapped[list["LenderProgram"]] = relationship("LenderProgram", back_populates="lender", cascade="all, delete-orphan")
    results:  Mapped[list["MatchResult"]]   = relationship("MatchResult",   back_populates="lender")


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id:                   Mapped[int]           = mapped_column(Integer, primary_key=True)
    lender_id:            Mapped[int]           = mapped_column(ForeignKey("lenders.id"), nullable=False)
    rule_type:            Mapped[str]           = mapped_column(Enum(RuleType), nullable=False)
    operator:             Mapped[str]           = mapped_column(Enum(Operator), nullable=False)
    value:                Mapped[str]           = mapped_column(String(200), nullable=False)
    description:          Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applies_to_industry:  Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_hard_stop:         Mapped[bool]          = mapped_column(Boolean, default=True)
    is_active:            Mapped[bool]          = mapped_column(Boolean, default=True)
    source_quote:         Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lender:   Mapped["Lender"]               = relationship("Lender", back_populates="rules")
    criteria: Mapped[list["CriteriaDetail"]] = relationship("CriteriaDetail", back_populates="rule")


class LenderProgram(Base):
    __tablename__ = "lender_programs"

    id:          Mapped[int]            = mapped_column(Integer, primary_key=True)
    lender_id:   Mapped[int]            = mapped_column(ForeignKey("lenders.id"), nullable=False)
    name:        Mapped[str]            = mapped_column(String(100), nullable=False)
    min_amount:  Mapped[Optional[float]]= mapped_column(Float, nullable=True)
    max_amount:  Mapped[Optional[float]]= mapped_column(Float, nullable=True)
    credit_tier: Mapped[Optional[str]]  = mapped_column(String(20), nullable=True)
    description: Mapped[Optional[str]]  = mapped_column(Text, nullable=True)

    lender: Mapped["Lender"] = relationship("Lender", back_populates="programs")


class PDFIngestion(Base):
    __tablename__ = "pdf_ingestions"

    id:              Mapped[int]           = mapped_column(Integer, primary_key=True)
    filename:        Mapped[str]           = mapped_column(String(255), nullable=False)
    status:          Mapped[str]           = mapped_column(Enum(IngestionStatus), default=IngestionStatus.PENDING_REVIEW)
    extracted_json:  Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lender_id:       Mapped[Optional[int]] = mapped_column(ForeignKey("lenders.id"), nullable=True)
    workflow_run_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at:      Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:      Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lender: Mapped[Optional["Lender"]] = relationship("Lender")


# ─────────────────────────────────────────────
# APPLICATION TABLES
# ─────────────────────────────────────────────

class Borrower(Base):
    __tablename__ = "borrowers"

    id:                Mapped[int]            = mapped_column(Integer, primary_key=True)
    business_name:     Mapped[str]            = mapped_column(String(200), nullable=False)
    industry:          Mapped[str]            = mapped_column(String(100), nullable=False)
    state:             Mapped[str]            = mapped_column(String(2),   nullable=False)
    years_in_business: Mapped[float]          = mapped_column(Float, nullable=False)
    annual_revenue:    Mapped[Optional[float]]= mapped_column(Float, nullable=True)
    num_trucks:        Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)

    applications: Mapped[list["Application"]]       = relationship("Application", back_populates="borrower")
    guarantors:   Mapped[list["PersonalGuarantor"]] = relationship("PersonalGuarantor", back_populates="borrower", cascade="all, delete-orphan")
    biz_credit:   Mapped[Optional["BusinessCredit"]]= relationship("BusinessCredit", back_populates="borrower", uselist=False, cascade="all, delete-orphan")


class PersonalGuarantor(Base):
    __tablename__ = "personal_guarantors"

    id:                        Mapped[int]           = mapped_column(Integer, primary_key=True)
    borrower_id:               Mapped[int]           = mapped_column(ForeignKey("borrowers.id"), nullable=False)
    full_name:                 Mapped[str]           = mapped_column(String(200), nullable=False)
    fico_score:                Mapped[int]           = mapped_column(Integer, nullable=False)
    ownership_pct:             Mapped[float]         = mapped_column(Float, nullable=False)
    has_bankruptcy:            Mapped[bool]          = mapped_column(Boolean, default=False)
    bankruptcy_discharged_yrs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_homeowner:              Mapped[bool]          = mapped_column(Boolean, default=False)
    has_cdl:                   Mapped[bool]          = mapped_column(Boolean, default=False)
    years_cdl:                 Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="guarantors")


class BusinessCredit(Base):
    __tablename__ = "business_credits"

    id:                       Mapped[int]            = mapped_column(Integer, primary_key=True)
    borrower_id:              Mapped[int]            = mapped_column(ForeignKey("borrowers.id"), nullable=False, unique=True)
    paynet_score:             Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    trade_lines:              Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    comparable_credit_amount: Mapped[Optional[float]]= mapped_column(Float, nullable=True)

    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="biz_credit")


class LoanRequest(Base):
    __tablename__ = "loan_requests"

    id:               Mapped[int]            = mapped_column(Integer, primary_key=True)
    amount:           Mapped[float]          = mapped_column(Float, nullable=False)
    term_months:      Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    equipment_type:   Mapped[str]            = mapped_column(String(100), nullable=False)
    equipment_year:   Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    equipment_make:   Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    equipment_model:  Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    mileage:          Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    is_private_party: Mapped[bool]           = mapped_column(Boolean, default=False)

    application: Mapped[Optional["Application"]] = relationship("Application", back_populates="loan_request", uselist=False)


class Application(Base):
    __tablename__ = "applications"

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True)
    borrower_id:     Mapped[int]      = mapped_column(ForeignKey("borrowers.id"), nullable=False)
    loan_request_id: Mapped[int]      = mapped_column(ForeignKey("loan_requests.id"), nullable=False, unique=True)
    status:          Mapped[str]      = mapped_column(Enum(ApplicationStatus), default=ApplicationStatus.DRAFT)
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    borrower:     Mapped["Borrower"]          = relationship("Borrower", back_populates="applications")
    loan_request: Mapped["LoanRequest"]       = relationship("LoanRequest", back_populates="application")
    results:      Mapped[list["MatchResult"]] = relationship("MatchResult", back_populates="application", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# MATCH RESULT TABLES
# ─────────────────────────────────────────────

class MatchResult(Base):
    __tablename__ = "match_results"

    id:             Mapped[int]      = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int]      = mapped_column(ForeignKey("applications.id"), nullable=False)
    lender_id:      Mapped[int]      = mapped_column(ForeignKey("lenders.id"), nullable=False)
    program_id:     Mapped[Optional[int]] = mapped_column(ForeignKey("lender_programs.id"), nullable=True)
    is_eligible:    Mapped[bool]     = mapped_column(Boolean, nullable=False)
    fit_score:      Mapped[float]    = mapped_column(Float, nullable=False)
    created_at:     Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    application: Mapped["Application"]          = relationship("Application", back_populates="results")
    lender:      Mapped["Lender"]               = relationship("Lender", back_populates="results")
    program:     Mapped[Optional["LenderProgram"]] = relationship("LenderProgram")
    criteria:    Mapped[list["CriteriaDetail"]] = relationship("CriteriaDetail", back_populates="match_result", cascade="all, delete-orphan")


class CriteriaDetail(Base):
    __tablename__ = "criteria_details"

    id:              Mapped[int]           = mapped_column(Integer, primary_key=True)
    match_result_id: Mapped[int]           = mapped_column(ForeignKey("match_results.id"), nullable=False)
    rule_id:         Mapped[int]           = mapped_column(ForeignKey("policy_rules.id"), nullable=False)
    passed:          Mapped[bool]          = mapped_column(Boolean, nullable=False)
    actual_value:    Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    required_value:  Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    explanation:     Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    match_result: Mapped["MatchResult"] = relationship("MatchResult", back_populates="criteria")
    rule:         Mapped["PolicyRule"]  = relationship("PolicyRule",  back_populates="criteria")