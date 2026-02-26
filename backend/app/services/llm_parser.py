"""
llm_parser.py

Responsibility: extracted PDF text → structured ParsedLenderPolicy
Uses instructor + GPT-4o to guarantee output matches our Pydantic schema.

Key design decisions:
  - ParsedLenderPolicy mirrors our DB models but is SEPARATE from them.
    This is intentional — the LLM output is unvalidated data pending human review.
    We only write to DB models after admin approval.
  - Every extracted rule includes a `source_quote` — the exact sentence from
    the PDF that the rule came from. This makes the admin review screen
    auditable: "why did the AI extract this rule?" → show the quote.
  - We tell GPT-4o to ignore operational FAQs (ACH, payment dates, etc.)
    and focus only on credit policy rules that affect loan eligibility.
"""
import instructor
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional
from app.config import settings
from app.models import RuleType, Operator


# ─────────────────────────────────────────────────────────────
# OUTPUT SCHEMA
# These Pydantic models define exactly what GPT-4o must return.
# instructor enforces this — if GPT-4o returns something that
# doesn't match, it retries with the validation error as feedback.
# ─────────────────────────────────────────────────────────────

class ExtractedRule(BaseModel):
    """One credit policy rule extracted from the PDF."""

    rule_type: RuleType = Field(
        description=(
            "The category of this rule. Must be one of the allowed enum values. "
            "Choose the most specific type that fits. "
            "Use MAX_LOAN_AMOUNT_BY_INDUSTRY when the limit only applies to a specific industry."
        )
    )
    operator: Operator = Field(
        description=(
            "How to compare the applicant value against the threshold. "
            "GTE = must be >= value (minimums like FICO, years). "
            "LTE = must be <= value (maximums like loan amount, mileage). "
            "EQ  = must equal value (boolean flags like homeownership). "
            "NEQ = must not equal value (exclusions like banned states/industries)."
        )
    )
    value: str = Field(
        description=(
            "The threshold value as a string. "
            "Numbers: no commas or currency symbols e.g. '680', '150000', '70'. "
            "States: two-letter code e.g. 'CA'. "
            "Boolean flags: 'true' or 'false'. "
            "Industry names: lowercase e.g. 'trucking', 'cannabis'."
        )
    )
    applies_to_industry: Optional[str] = Field(
        default=None,
        description=(
            "If this rule ONLY applies to a specific industry, name it in lowercase "
            "e.g. 'trucking', 'manufacturing', 'logging'. "
            "If it applies to all industries, leave this null."
        )
    )
    is_hard_stop: bool = Field(
        default=True,
        description=(
            "True if failing this rule makes the borrower ineligible (a hard rejection). "
            "False if it is informational or affects program tier but not outright eligibility."
        )
    )
    description: str = Field(
        description="A clear human-readable label for this rule shown in the admin UI."
    )
    source_quote: str = Field(
        description=(
            "The exact sentence or bullet point from the document this rule was extracted from. "
            "Copy it verbatim — this is used for audit/review purposes."
        )
    )


class ExtractedProgram(BaseModel):
    """A loan program or tier offered by this lender."""

    name: str = Field(description="Short name e.g. 'Tier 1 App Only', 'A-Credit $15K-$50K'")
    min_amount: Optional[float] = Field(default=None, description="Minimum loan amount in dollars, no symbols")
    max_amount: Optional[float] = Field(default=None, description="Maximum loan amount in dollars, no symbols")
    credit_tier: Optional[str] = Field(default=None, description="Credit tier label e.g. 'A', 'B', '1', '2'")
    description: Optional[str] = Field(default=None, description="Key requirements or rates for this program")


class ParsedLenderPolicy(BaseModel):
    """
    Complete structured output from one lender PDF.
    This is what gets returned from parse_pdf_policy() and
    stored with status=PENDING_REVIEW until admin approves.
    """
    lender_name:   str            = Field(description="Full legal name of the lender")
    contact_name:  Optional[str]  = Field(default=None, description="Primary contact person's name")
    contact_email: Optional[str]  = Field(default=None, description="Primary contact email")
    contact_phone: Optional[str]  = Field(default=None, description="Primary contact phone number")
    rules:         list[ExtractedRule]    = Field(default_factory=list, description="All extracted credit policy rules")
    programs:      list[ExtractedProgram] = Field(default_factory=list, description="All loan programs or tiers offered")
    extraction_notes: Optional[str] = Field(
        default=None,
        description=(
            "Any ambiguities, missing information, or items that need human review. "
            "E.g. 'Could not determine minimum loan amount — not specified in document.'"
        )
    )


# ─────────────────────────────────────────────────────────────
# THE PROMPT
# Separated from the code so it's easy to iterate on.
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a financial document analyst specializing in equipment finance credit policies.

Your job is to extract structured credit policy rules from lender guideline documents.

WHAT TO EXTRACT:
- Minimum credit score requirements (FICO, PayNet, TransUnion)
- Minimum years in business
- Minimum/maximum loan amounts (overall and per industry)
- Equipment age or mileage limits
- Geographic restrictions (excluded states)
- Industry exclusions or restrictions
- Bankruptcy requirements
- Homeownership requirements
- Fleet size requirements (e.g. minimum number of trucks)
- Any other rule that determines whether a borrower is eligible

WHAT TO IGNORE:
- Payment methods (ACH, check, wire)
- Documentation checklists (tax returns, bank statements) — these are process requirements not eligibility rules
- FAQ items about how the loan works after funding
- Insurance requirements after closing
- Contact information (capture separately in contact fields)

RULES FOR EXTRACTION:
1. Extract GLOBAL rules once — if the same rule (e.g. MIN_FICO 700) appears in multiple
   tiers or programs, extract it ONCE as a global rule, not once per tier
2. Only create separate rules when the VALUE is genuinely different across contexts
   e.g. MIN_FICO 680 globally but MIN_FICO 700 for trucking → two rules
3. If a rule applies only to a specific industry (e.g. trucking), set applies_to_industry
4. Do NOT create duplicate rules with the same rule_type + operator + value + applies_to_industry
5. Use source_quote to copy the exact text the rule came from
6. When unsure whether something is a hard stop, default to true
7. Note any ambiguities in extraction_notes
8. Tier/program descriptions are informational — do not repeat the same threshold
   as separate rules just because it appears in multiple tier descriptions

ALLOWED rule_type VALUES:
MIN_FICO, MIN_PAYNET, MIN_YEARS_IN_BUSINESS, MAX_LOAN_AMOUNT, MIN_LOAN_AMOUNT,
EQUIPMENT_MAX_AGE_YEARS, MAX_MILEAGE, EXCLUDED_STATE, EXCLUDED_INDUSTRY,
BANKRUPTCY_MIN_YEARS_DISCHARGED, REQUIRES_HOMEOWNERSHIP, MIN_COMPARABLE_CREDIT_PCT,
TRUCKING_MIN_TRUCKS, MAX_LOAN_AMOUNT_BY_INDUSTRY
"""

def _build_user_prompt(content: str, filename: str) -> str:
    return f"""Extract all credit policy rules from this lender guideline document.

Document filename: {filename}

Document content:
{content}

Remember: extract EVERY eligibility rule as a separate rule object. 
If a rule has different thresholds for different industries, create one rule per industry.
"""


# ─────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────────────────────

def _post_process(policy: ParsedLenderPolicy) -> ParsedLenderPolicy:
    """
    Minimal cleanup only — we preserve all extracted rules for admin review.
    The admin UI is where deduplication and corrections happen.

    Only fix here: REQUIRES_HOMEOWNERSHIP rules that mention "Non Homeowner"
    are clearly mislabelled — the Non Homeowner Program is for people WITHOUT
    homeownership, so these cannot be hard stops.
    """
    for rule in policy.rules:
        if (
            rule.rule_type == RuleType.REQUIRES_HOMEOWNERSHIP
            and "non homeowner" in (rule.description or "").lower()
        ):
            rule.is_hard_stop = False

    return policy


def parse_pdf_policy(extracted_content: str, filename: str) -> ParsedLenderPolicy:
    """
    Send extracted PDF content to GPT-4o and get back a structured policy.

    Args:
        extracted_content : the full_content() string from ExtractedPDF
        filename          : original PDF filename (used in the prompt for context)

    Returns:
        ParsedLenderPolicy — guaranteed valid by instructor, ready for admin review

    Raises:
        instructor.exceptions.InstructorRetryException : if GPT-4o fails after max_retries
        openai.APIError                                : if the API call itself fails
    """
    # instructor wraps the standard OpenAI client.
    # mode=instructor.Mode.JSON tells it to use JSON mode for reliability.
    client = instructor.from_openai(
        OpenAI(api_key=settings.openai_api_key),
        mode=instructor.Mode.JSON,
    )

    policy = client.chat.completions.create(
        model="gpt-4o",
        max_retries=3,           # instructor retries this many times if validation fails
        response_model=ParsedLenderPolicy,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_user_prompt(extracted_content, filename)},
        ],
        temperature=0,           # 0 = deterministic, no creativity, just extraction
    )

    return policy