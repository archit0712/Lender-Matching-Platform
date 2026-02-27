from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import Lender, PolicyRule, LenderProgram, RuleType, Operator

router = APIRouter()


# ─────────────────────────────────────────────
# REQUEST SCHEMAS (inline — simple enough)
# ─────────────────────────────────────────────

class PolicyRulePayload(BaseModel):
    rule_type:           RuleType
    operator:            Operator
    value:               str
    description:         Optional[str] = None
    applies_to_industry: Optional[str] = None
    is_hard_stop:        bool = True
    is_active:           bool = True
    source_quote:        Optional[str] = None


class LenderProgramPayload(BaseModel):
    name:        str
    min_amount:  Optional[float] = None
    max_amount:  Optional[float] = None
    credit_tier: Optional[str]  = None
    description: Optional[str]  = None


class LenderPayload(BaseModel):
    name:          str
    contact_name:  Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_active:     bool = True
    notes:         Optional[str] = None
    rules:         list[PolicyRulePayload]    = []
    programs:      list[LenderProgramPayload] = []


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _lender_to_dict(lender: Lender) -> dict:
    return {
        "id":            lender.id,
        "name":          lender.name,
        "contact_name":  lender.contact_name,
        "contact_email": lender.contact_email,
        "contact_phone": lender.contact_phone,
        "is_active":     lender.is_active,
        "notes":         lender.notes,
        "rules": [
            {
                "id":                   r.id,
                "lender_id":            r.lender_id,
                "rule_type":            r.rule_type,
                "operator":             r.operator,
                "value":                r.value,
                "description":          r.description,
                "applies_to_industry":  r.applies_to_industry,
                "is_hard_stop":         r.is_hard_stop,
                "is_active":            r.is_active,
                "source_quote":         r.source_quote,
            }
            for r in lender.rules
        ],
        "programs": [
            {
                "id":          p.id,
                "lender_id":   p.lender_id,
                "name":        p.name,
                "min_amount":  p.min_amount,
                "max_amount":  p.max_amount,
                "credit_tier": p.credit_tier,
                "description": p.description,
            }
            for p in lender.programs
        ],
    }


def _get_lender_or_404(lender_id: int, db: Session) -> Lender:
    lender = db.get(Lender, lender_id)
    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")
    return lender


# ─────────────────────────────────────────────
# LENDER CRUD
# ─────────────────────────────────────────────

@router.get("/")
def list_lenders(db: Session = Depends(get_db)):
    """Return all lenders with their rules and programs."""
    return [_lender_to_dict(l) for l in db.query(Lender).all()]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_lender(payload: LenderPayload, db: Session = Depends(get_db)):
    """Create a lender with optional initial rules and programs."""
    lender = Lender(**payload.model_dump(exclude={"rules", "programs"}))
    db.add(lender)
    db.flush()

    for r in payload.rules:
        db.add(PolicyRule(lender_id=lender.id, **r.model_dump()))
    for p in payload.programs:
        db.add(LenderProgram(lender_id=lender.id, **p.model_dump()))

    db.commit()
    db.refresh(lender)
    return _lender_to_dict(lender)


@router.get("/{lender_id}")
def get_lender(lender_id: int, db: Session = Depends(get_db)):
    return _lender_to_dict(_get_lender_or_404(lender_id, db))


@router.patch("/{lender_id}")
def update_lender(lender_id: int, payload: dict, db: Session = Depends(get_db)):
    """Partial update — only provided fields are changed."""
    lender = _get_lender_or_404(lender_id, db)
    for k, v in payload.items():
        if hasattr(lender, k):
            setattr(lender, k, v)
    db.commit()
    db.refresh(lender)
    return _lender_to_dict(lender)


@router.delete("/{lender_id}", status_code=204)
def delete_lender(lender_id: int, db: Session = Depends(get_db)):
    lender = _get_lender_or_404(lender_id, db)
    db.delete(lender)
    db.commit()


# ─────────────────────────────────────────────
# POLICY RULES
# ─────────────────────────────────────────────

@router.get("/{lender_id}/rules")
def list_rules(lender_id: int, db: Session = Depends(get_db)):
    _get_lender_or_404(lender_id, db)
    rules = db.query(PolicyRule).filter(PolicyRule.lender_id == lender_id).all()
    return [
        {
            "id": r.id, "lender_id": r.lender_id, "rule_type": r.rule_type,
            "operator": r.operator, "value": r.value, "description": r.description,
            "applies_to_industry": r.applies_to_industry, "is_hard_stop": r.is_hard_stop,
            "is_active": r.is_active, "source_quote": r.source_quote,
        }
        for r in rules
    ]


@router.post("/{lender_id}/rules", status_code=201)
def add_rule(lender_id: int, payload: PolicyRulePayload, db: Session = Depends(get_db)):
    """Add a single rule to an existing lender."""
    _get_lender_or_404(lender_id, db)
    rule = PolicyRule(lender_id=lender_id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "lender_id": rule.lender_id, "rule_type": rule.rule_type,
            "operator": rule.operator, "value": rule.value, "description": rule.description,
            "applies_to_industry": rule.applies_to_industry, "is_hard_stop": rule.is_hard_stop,
            "is_active": rule.is_active, "source_quote": rule.source_quote}


@router.put("/{lender_id}/rules/{rule_id}")
def update_rule(lender_id: int, rule_id: int, payload: PolicyRulePayload, db: Session = Depends(get_db)):
    """Full replace of a rule — used by the UI inline edit."""
    rule = db.get(PolicyRule, rule_id)
    if not rule or rule.lender_id != lender_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    for k, v in payload.model_dump().items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "rule_type": rule.rule_type, "value": rule.value}


@router.delete("/{lender_id}/rules/{rule_id}", status_code=204)
def delete_rule(lender_id: int, rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(PolicyRule, rule_id)
    if not rule or rule.lender_id != lender_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


# ─────────────────────────────────────────────
# PROGRAMS
# ─────────────────────────────────────────────

@router.post("/{lender_id}/programs", status_code=201)
def add_program(lender_id: int, payload: LenderProgramPayload, db: Session = Depends(get_db)):
    _get_lender_or_404(lender_id, db)
    program = LenderProgram(lender_id=lender_id, **payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return {"id": program.id, "lender_id": program.lender_id, "name": program.name,
            "min_amount": program.min_amount, "max_amount": program.max_amount,
            "credit_tier": program.credit_tier, "description": program.description}


@router.put("/{lender_id}/programs/{program_id}")
def update_program(lender_id: int, program_id: int, payload: LenderProgramPayload, db: Session = Depends(get_db)):
    program = db.get(LenderProgram, program_id)
    if not program or program.lender_id != lender_id:
        raise HTTPException(status_code=404, detail="Program not found")
    for k, v in payload.model_dump().items():
        setattr(program, k, v)
    db.commit()
    db.refresh(program)
    return {"id": program.id, "name": program.name}


@router.delete("/{lender_id}/programs/{program_id}", status_code=204)
def delete_program(lender_id: int, program_id: int, db: Session = Depends(get_db)):
    program = db.get(LenderProgram, program_id)
    if not program or program.lender_id != lender_id:
        raise HTTPException(status_code=404, detail="Program not found")
    db.delete(program)
    db.commit()