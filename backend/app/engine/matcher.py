from typing import Optional
from sqlalchemy.orm import Session
from app.models import (
    Application, Lender, LenderProgram,
    MatchResult, CriteriaDetail, ApplicationStatus
)
from app.engine.evaluator import RuleEvaluator, ApplicationContext, CriteriaResult


def _build_context(app: Application) -> ApplicationContext:
    """Flatten ORM objects into a simple dataclass. Uses lowest FICO across guarantors."""
    b  = app.borrower
    lr = app.loan_request
    gs = b.guarantors
    bc = b.biz_credit

    min_fico = min((g.fico_score for g in gs), default=0)
    worst_g  = next((g for g in gs if g.fico_score == min_fico), None)

    return ApplicationContext(
        industry           = b.industry,
        state              = b.state,
        years_in_business  = b.years_in_business,
        annual_revenue     = b.annual_revenue or 0,
        num_trucks         = b.num_trucks or 0,
        min_fico           = min_fico,
        has_bankruptcy     = worst_g.has_bankruptcy if worst_g else False,
        bankruptcy_discharged_yrs = worst_g.bankruptcy_discharged_yrs if worst_g else None,
        is_homeowner       = all(g.is_homeowner for g in gs) if gs else False,
        has_cdl            = any(g.has_cdl for g in gs) if gs else False,
        paynet_score       = bc.paynet_score if bc else None,
        comparable_credit_amount = bc.comparable_credit_amount if bc else None,
        loan_amount        = lr.amount,
        equipment_type     = lr.equipment_type,
        equipment_year     = lr.equipment_year,
        mileage            = lr.mileage,
        is_private_party   = lr.is_private_party,
    )


def _best_program(lender: Lender, ctx: ApplicationContext) -> Optional[LenderProgram]:
    """Pick the program whose amount range contains the loan amount."""
    eligible = [
        p for p in lender.programs
        if (p.min_amount is None or ctx.loan_amount >= p.min_amount)
        and (p.max_amount is None or ctx.loan_amount <= p.max_amount)
    ]
    return eligible[0] if eligible else (lender.programs[0] if lender.programs else None)


def _calculate_fit_score(criteria: list[CriteriaResult], active_rules) -> float:
    """
    0-100 score:
      70 pts — pass rate across hard stop rules
      30 pts — margin bonuses for FICO and PayNet headroom above minimums
    """
    rule_map = {r.id: r for r in active_rules}

    hard_criteria = [
        c for c in criteria
        if not c.explanation.startswith("Rule only applies")
        and rule_map.get(c.rule_id) and rule_map[c.rule_id].is_hard_stop
    ]
    if not hard_criteria:
        return 100.0

    pass_rate  = sum(1 for c in hard_criteria if c.passed) / len(hard_criteria)
    base_score = pass_rate * 70

    fico_bonus = paynet_bonus = 0.0
    for c in criteria:
        if "FICO" in c.explanation and c.passed:
            try:
                fico_bonus = min(15.0, (float(c.actual_value) - float(c.required_value)) / float(c.required_value) * 100)
            except (ValueError, ZeroDivisionError):
                pass
        if "PayNet" in c.explanation and c.passed:
            try:
                paynet_bonus = min(15.0, (float(c.actual_value) - float(c.required_value)) / float(c.required_value) * 100)
            except (ValueError, ZeroDivisionError):
                pass

    return round(min(100.0, base_score + fico_bonus + paynet_bonus), 2)


class LenderMatcher:
    def __init__(self, db: Session):
        self.db        = db
        self.evaluator = RuleEvaluator()

    def run(self, app: Application) -> list[MatchResult]:
        """
        Main entry point.
        Evaluates all active lenders against the application.
        Persists MatchResult + CriteriaDetail rows.
        Returns results sorted by fit_score descending.
        """
        ctx     = _build_context(app)
        lenders = self.db.query(Lender).filter(Lender.is_active == True).all()

        # Clear previous results if re-running
        for old in app.results:
            self.db.delete(old)
        self.db.flush()

        saved = []

        for lender in lenders:
            active_rules = [r for r in lender.rules if r.is_active]
            criteria     = [self.evaluator.evaluate(rule, ctx) for rule in active_rules]

            # Ineligible if any hard stop rule fails
            hard_stop_fails = [
                c for c in criteria
                if not c.passed
                and not c.explanation.startswith("Rule only applies")
                and any(r.id == c.rule_id and r.is_hard_stop for r in active_rules)
            ]
            is_eligible = len(hard_stop_fails) == 0
            fit_score   = _calculate_fit_score(criteria, active_rules)
            program     = _best_program(lender, ctx)

            result = MatchResult(
                application_id=app.id,
                lender_id=lender.id,
                program_id=program.id if program else None,
                is_eligible=is_eligible,
                fit_score=fit_score,
            )
            self.db.add(result)
            self.db.flush()

            for c in criteria:
                self.db.add(CriteriaDetail(
                    match_result_id=result.id,
                    rule_id=c.rule_id,
                    passed=c.passed,
                    actual_value=c.actual_value,
                    required_value=c.required_value,
                    explanation=c.explanation,
                ))

            saved.append(result)

        app.status = ApplicationStatus.MATCHED
        self.db.commit()

        for r in saved:
            self.db.refresh(r)

        return sorted(saved, key=lambda r: r.fit_score, reverse=True)