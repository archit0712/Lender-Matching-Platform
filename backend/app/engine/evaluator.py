from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from app.models import PolicyRule, Operator, RuleType


@dataclass
class ApplicationContext:
    """Flat snapshot of everything the evaluator needs. Derived from ORM objects."""
    industry:           str
    state:              str
    years_in_business:  float
    annual_revenue:     float
    num_trucks:         int
    min_fico:           int
    has_bankruptcy:     bool
    bankruptcy_discharged_yrs: Optional[int]
    is_homeowner:       bool
    has_cdl:            bool
    paynet_score:       Optional[int]
    comparable_credit_amount: Optional[float]
    loan_amount:        float
    equipment_type:     str
    equipment_year:     Optional[int]
    mileage:            Optional[int]
    is_private_party:   bool
    equipment_age:      int = field(init=False, default=0)

    def __post_init__(self):
        current_year = datetime.utcnow().year
        self.equipment_age = (current_year - self.equipment_year) if self.equipment_year else 0


@dataclass
class CriteriaResult:
    rule_id:        int
    passed:         bool
    actual_value:   str
    required_value: str
    explanation:    str


class RuleEvaluator:
    """
    Dispatches to the correct handler based on rule_type.
    Adding a new rule type = add enum value + one _check_ method below.
    """

    def evaluate(self, rule: PolicyRule, ctx: ApplicationContext) -> CriteriaResult:
        # Skip rules that don't apply to this industry
        if rule.applies_to_industry:
            if rule.applies_to_industry.lower() not in ctx.industry.lower():
                return CriteriaResult(
                    rule_id=rule.id, passed=True,
                    actual_value="N/A", required_value="N/A",
                    explanation=f"Rule only applies to '{rule.applies_to_industry}' — skipped."
                )

        # Normalize rule_type to plain string regardless of how SQLAlchemy returns it
        # e.g. RuleType.MIN_FICO → "MIN_FICO"
        if hasattr(rule.rule_type, "value"):
            rule_type_key = rule.rule_type.value          # enum object → its string value
        elif isinstance(rule.rule_type, str) and "." in rule.rule_type:
            rule_type_key = rule.rule_type.split(".")[-1] # "RuleType.MIN_FICO" → "MIN_FICO"
        else:
            rule_type_key = rule.rule_type                # already plain string

        handler = getattr(self, f"_check_{rule_type_key}", self._check_unknown)
        passed, actual, required, explanation = handler(rule, ctx)
        return CriteriaResult(rule.id, passed, actual, required, explanation)

    def _compare(self, actual: float, operator: str, threshold: float) -> bool:
        return {
            Operator.GTE: actual >= threshold,
            Operator.LTE: actual <= threshold,
            Operator.EQ:  actual == threshold,
            Operator.NEQ: actual != threshold,
        }[operator]

    def _fmt(self, v: float) -> str:
        return f"{v:,.0f}"

    def _check_MIN_FICO(self, rule, ctx):
        t = float(rule.value)
        p = self._compare(ctx.min_fico, Operator.GTE, t)
        return (p, str(ctx.min_fico), rule.value,
                f"FICO score {ctx.min_fico} {'meets' if p else 'does not meet'} the minimum of {self._fmt(t)}.")

    def _check_MIN_PAYNET(self, rule, ctx):
        if ctx.paynet_score is None:
            return (False, "Not provided", rule.value,
                    f"PayNet score not provided; minimum required is {rule.value}.")
        t = float(rule.value)
        p = self._compare(ctx.paynet_score, Operator.GTE, t)
        return (p, str(ctx.paynet_score), rule.value,
                f"PayNet score {ctx.paynet_score} {'meets' if p else 'does not meet'} the minimum of {self._fmt(t)}.")

    def _check_MIN_YEARS_IN_BUSINESS(self, rule, ctx):
        t = float(rule.value)
        p = self._compare(ctx.years_in_business, Operator.GTE, t)
        return (p, str(ctx.years_in_business), rule.value,
                f"{ctx.years_in_business:.1f} years in business {'meets' if p else 'does not meet'} the minimum of {t:.0f} years.")

    def _check_MAX_LOAN_AMOUNT(self, rule, ctx):
        t = float(rule.value)
        p = self._compare(ctx.loan_amount, Operator.LTE, t)
        return (p, f"${self._fmt(ctx.loan_amount)}", f"${self._fmt(t)}",
                f"Loan amount ${self._fmt(ctx.loan_amount)} {'within' if p else 'exceeds'} the maximum of ${self._fmt(t)}.")

    def _check_MIN_LOAN_AMOUNT(self, rule, ctx):
        t = float(rule.value)
        p = self._compare(ctx.loan_amount, Operator.GTE, t)
        return (p, f"${self._fmt(ctx.loan_amount)}", f"${self._fmt(t)}",
                f"Loan amount ${self._fmt(ctx.loan_amount)} {'meets' if p else 'is below'} the minimum of ${self._fmt(t)}.")

    def _check_EQUIPMENT_MAX_AGE_YEARS(self, rule, ctx):
        if ctx.equipment_year is None:
            return (False, "Not provided", rule.value, "Equipment year not provided.")
        t = float(rule.value)
        p = self._compare(ctx.equipment_age, Operator.LTE, t)
        return (p, f"{ctx.equipment_age} years old", f"max {t:.0f} years old",
                f"Equipment is {ctx.equipment_age} years old — {'within' if p else 'exceeds'} the maximum of {t:.0f} years.")

    def _check_MAX_MILEAGE(self, rule, ctx):
        if ctx.mileage is None:
            return (True, "Not provided", rule.value, "Mileage not provided — assuming within limit.")
        t = float(rule.value)
        p = self._compare(ctx.mileage, Operator.LTE, t)
        return (p, f"{self._fmt(ctx.mileage)} miles", f"max {self._fmt(t)} miles",
                f"Mileage {self._fmt(ctx.mileage)} {'within' if p else 'exceeds'} the maximum of {self._fmt(t)} miles.")

    def _check_EXCLUDED_STATE(self, rule, ctx):
        excluded = rule.value.upper()
        p = ctx.state.upper() != excluded
        return (p, ctx.state, f"Not {excluded}",
                f"Business state '{ctx.state}' {'is not' if p else 'is'} excluded. Lender does not operate in {excluded}.")

    def _check_EXCLUDED_INDUSTRY(self, rule, ctx):
        excluded = rule.value.lower()
        p = excluded not in ctx.industry.lower()
        return (p, ctx.industry, f"Not {rule.value}",
                f"Industry '{ctx.industry}' {'is not' if p else 'is'} in the excluded category '{rule.value}'.")

    def _check_BANKRUPTCY_MIN_YEARS_DISCHARGED(self, rule, ctx):
        if not ctx.has_bankruptcy:
            return (True, "No bankruptcy", rule.value, "No bankruptcy on record — criterion met.")
        if ctx.bankruptcy_discharged_yrs is None:
            return (False, "Unknown", rule.value, "Bankruptcy present but discharge date not provided.")
        t = float(rule.value)
        p = self._compare(ctx.bankruptcy_discharged_yrs, Operator.GTE, t)
        return (p, f"{ctx.bankruptcy_discharged_yrs} years ago", f"{t:.0f}+ years ago",
                f"Bankruptcy discharged {ctx.bankruptcy_discharged_yrs} years ago {'meets' if p else 'does not meet'} the minimum of {t:.0f} years.")

    def _check_REQUIRES_HOMEOWNERSHIP(self, rule, ctx):
        p = ctx.is_homeowner
        return (p, "Yes" if p else "No", "Yes",
                f"Homeownership {'satisfied' if p else 'required but not present'}.")

    def _check_MIN_COMPARABLE_CREDIT_PCT(self, rule, ctx):
        if ctx.comparable_credit_amount is None:
            return (False, "Not provided", rule.value, "Comparable commercial credit not provided.")
        t = float(rule.value)
        required = ctx.loan_amount * (t / 100)
        p = ctx.comparable_credit_amount >= required
        return (p,
                f"${self._fmt(ctx.comparable_credit_amount)}",
                f"${self._fmt(required)} ({t:.0f}% of ${self._fmt(ctx.loan_amount)})",
                f"Comparable credit ${self._fmt(ctx.comparable_credit_amount)} {'meets' if p else 'does not meet'} "
                f"the required ${self._fmt(required)} ({t:.0f}% of loan).")

    def _check_TRUCKING_MIN_TRUCKS(self, rule, ctx):
        t = float(rule.value)
        actual = ctx.num_trucks or 0
        p = self._compare(actual, Operator.GTE, t)
        return (p, str(actual), rule.value,
                f"Fleet size of {actual} trucks {'meets' if p else 'does not meet'} the minimum of {t:.0f} trucks.")

    def _check_MAX_LOAN_AMOUNT_BY_INDUSTRY(self, rule, ctx):
        return self._check_MAX_LOAN_AMOUNT(rule, ctx)

    def _check_unknown(self, rule, ctx):
        return (False, "N/A", "N/A", f"Unknown rule type '{rule.rule_type}' — cannot evaluate.")