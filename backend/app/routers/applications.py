from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import (
    Application, Borrower, PersonalGuarantor,
    BusinessCredit, LoanRequest, ApplicationStatus
)
from app.schemas import ApplicationCreate
from app.engine.matcher import LenderMatcher

router = APIRouter()


def _get_orm(app_id: int, db: Session):
    """Load full ORM object with all relationships — used by the matcher."""
    return (
        db.query(Application)
        .options(
            joinedload(Application.borrower)
                .joinedload(Borrower.guarantors),
            joinedload(Application.borrower)
                .joinedload(Borrower.biz_credit),
            joinedload(Application.loan_request),
            joinedload(Application.results),
        )
        .filter(Application.id == app_id)
        .first()
    )


def _load_full(app_id: int, db: Session):
    """Eagerly load all nested relationships and return as plain dict."""
    app = (
        db.query(Application)
        .options(
            joinedload(Application.borrower)
                .joinedload(Borrower.guarantors),
            joinedload(Application.borrower)
                .joinedload(Borrower.biz_credit),
            joinedload(Application.loan_request),
            joinedload(Application.results),
        )
        .filter(Application.id == app_id)
        .first()
    )
    if not app:
        return None

    return {
        "id":     app.id,
        "status": app.status,
        "created_at": app.created_at,
        "borrower": {
            "id":                app.borrower.id,
            "business_name":     app.borrower.business_name,
            "industry":          app.borrower.industry,
            "state":             app.borrower.state,
            "years_in_business": app.borrower.years_in_business,
            "annual_revenue":    app.borrower.annual_revenue,
            "num_trucks":        app.borrower.num_trucks,
            "guarantors": [
                {
                    "id":           g.id,
                    "full_name":    g.full_name,
                    "fico_score":   g.fico_score,
                    "ownership_pct": g.ownership_pct,
                    "has_bankruptcy": g.has_bankruptcy,
                    "is_homeowner": g.is_homeowner,
                    "has_cdl":      g.has_cdl,
                }
                for g in app.borrower.guarantors
            ],
            "biz_credit": {
                "paynet_score":             app.borrower.biz_credit.paynet_score,
                "comparable_credit_amount": app.borrower.biz_credit.comparable_credit_amount,
            } if app.borrower.biz_credit else None,
        },
        "loan_request": {
            "id":             app.loan_request.id,
            "amount":         app.loan_request.amount,
            "equipment_type": app.loan_request.equipment_type,
            "equipment_year": app.loan_request.equipment_year,
            "mileage":        app.loan_request.mileage,
            "is_private_party": app.loan_request.is_private_party,
        },
        "results": [
            {
                "id":          r.id,
                "lender_id":   r.lender_id,
                "lender":      {"id": r.lender.id, "name": r.lender.name},
                "is_eligible": r.is_eligible,
                "fit_score":   r.fit_score,
                "criteria": [
                    {
                        "rule_id":        c.rule_id,
                        "passed":         c.passed,
                        "actual_value":   c.actual_value,
                        "required_value": c.required_value,
                        "explanation":    c.explanation,
                    }
                    for c in r.criteria
                ] if r.criteria else [],
            }
            for r in app.results
        ],
    }


@router.post("/", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    b_data = payload.borrower

    # 1. Borrower
    borrower = Borrower(**b_data.model_dump(exclude={"guarantors", "biz_credit"}))
    db.add(borrower)
    db.flush()

    for g in b_data.guarantors:
        db.add(PersonalGuarantor(borrower_id=borrower.id, **g.model_dump()))

    if b_data.biz_credit:
        db.add(BusinessCredit(borrower_id=borrower.id, **b_data.biz_credit.model_dump()))

    # 2. Loan request
    loan = LoanRequest(**payload.loan_request.model_dump())
    db.add(loan)
    db.flush()

    # 3. Application
    app = Application(
        borrower_id=borrower.id,
        loan_request_id=loan.id,
        status=ApplicationStatus.SUBMITTED,
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    # 4. Run matching engine — pass ORM object, not dict
    try:
        orm_app = _get_orm(app.id, db)
        LenderMatcher(db).run(orm_app)
    except Exception as e:
        app.status = ApplicationStatus.ERROR
        db.commit()
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")

    return _load_full(app.id, db)


@router.get("/")
def list_applications(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    apps = db.query(Application).offset(skip).limit(limit).all()
    return [_load_full(a.id, db) for a in apps]


@router.get("/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    result = _load_full(app_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


@router.post("/{app_id}/run")
def rerun_underwriting(app_id: int, db: Session = Depends(get_db)):
    """Re-run matching on existing application — useful after editing lender policies."""
    app = _load_full(app_id, db)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    LenderMatcher(db).run(_get_orm(app_id, db))
    return _load_full(app_id, db)