


# ============================================================
# backend/seed.py
# ============================================================
"""
Run once to populate lender policies:
  python seed.py

Each LENDER block below is the template for adding a new lender.
Steps when a new PDF arrives:
  1. Read the PDF
  2. Copy the LENDER block, fill in name/contact
  3. Translate each guideline into a rules[] entry
  4. Run: python seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine, Base
from app.models import Lender, PolicyRule, LenderProgram, RuleType, Operator

Base.metadata.create_all(bind=engine)
db = SessionLocal()


def seed_lender(data: dict):
    """Idempotent: skip if lender with same name already exists."""
    existing = db.query(Lender).filter(Lender.name == data["name"]).first()
    if existing:
        print(f"  ↳ Skipping '{data['name']}' — already exists.")
        return

    lender = Lender(
        name=data["name"],
        contact_name=data.get("contact_name"),
        contact_email=data.get("contact_email"),
        contact_phone=data.get("contact_phone"),
        notes=data.get("notes"),
    )
    db.add(lender)
    db.flush()

    for r in data.get("rules", []):
        db.add(PolicyRule(lender_id=lender.id, **r))

    for p in data.get("programs", []):
        db.add(LenderProgram(lender_id=lender.id, **p))

    db.commit()
    print(f"  ✓ Seeded '{data['name']}' with {len(data.get('rules',[]))} rules.")


# ────────────────────────────────────────────────────────────
# FALCON EQUIPMENT FINANCE
# Source: Falcon Rates & Programs (November 2025)
# ────────────────────────────────────────────────────────────
seed_lender({
    "name":          "Falcon Equipment Finance",
    "contact_name":  "Emma Tickner",
    "contact_email": "ETickner@FalconEquipmentFinance.com",
    "contact_phone": "651-332-6517",
    "notes":         "A division of Falcon National Bank. St. Cloud, MN.",
    "rules": [
        # ── Global credit rules (apply to all industries) ──
        {
            "rule_type":   RuleType.MIN_YEARS_IN_BUSINESS,
            "operator":    Operator.GTE,
            "value":       "3",
            "description": "Minimum 3 years in business (references verified)",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.MIN_FICO,
            "operator":    Operator.GTE,
            "value":       "680",
            "description": "Minimum FICO score of 680",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.MIN_PAYNET,
            "operator":    Operator.GTE,
            "value":       "660",
            "description": "Minimum PayNet Masterscore of 660",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.MIN_COMPARABLE_CREDIT_PCT,
            "operator":    Operator.GTE,
            "value":       "70",
            "description": "Comparable commercial installment credit >= 70% of requested amount",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.BANKRUPTCY_MIN_YEARS_DISCHARGED,
            "operator":    Operator.GTE,
            "value":       "15",
            "description": "Bankruptcy must be dismissed or discharged 15+ years ago",
            "is_hard_stop": True,
        },
        # ── Industry-specific loan amount caps ──
        {
            "rule_type":            RuleType.MAX_LOAN_AMOUNT_BY_INDUSTRY,
            "operator":             Operator.LTE,
            "value":                "150000",
            "applies_to_industry":  "trucking",
            "description":          "App only up to $150,000 for trucking and logging (A/B credits only)",
            "is_hard_stop":         True,
        },
        {
            "rule_type":            RuleType.MAX_LOAN_AMOUNT_BY_INDUSTRY,
            "operator":             Operator.LTE,
            "value":                "150000",
            "applies_to_industry":  "logging",
            "description":          "App only up to $150,000 for logging",
            "is_hard_stop":         True,
        },
        {
            "rule_type":            RuleType.MAX_LOAN_AMOUNT_BY_INDUSTRY,
            "operator":             Operator.LTE,
            "value":                "250000",
            "applies_to_industry":  "commercial",
            "description":          "App only up to $250,000 for commercial transactions",
            "is_hard_stop":         True,
        },
        {
            "rule_type":            RuleType.MAX_LOAN_AMOUNT_BY_INDUSTRY,
            "operator":             Operator.LTE,
            "value":                "350000",
            "applies_to_industry":  "manufacturing",
            "description":          "App only up to $350,000 for manufacturing (machine tools, woodworking)",
            "is_hard_stop":         True,
        },
        # ── Trucking-specific stricter rules (A/B credits only) ──
        {
            "rule_type":            RuleType.MIN_YEARS_IN_BUSINESS,
            "operator":             Operator.GTE,
            "value":                "5",
            "applies_to_industry":  "trucking",
            "description":          "Trucking: must have 5+ years in business",
            "is_hard_stop":         True,
        },
        {
            "rule_type":            RuleType.MIN_FICO,
            "operator":             Operator.GTE,
            "value":                "700",
            "applies_to_industry":  "trucking",
            "description":          "Trucking: FICO 700 or better",
            "is_hard_stop":         True,
        },
        {
            "rule_type":            RuleType.MIN_PAYNET,
            "operator":             Operator.GTE,
            "value":                "680",
            "applies_to_industry":  "trucking",
            "description":          "Trucking: PayNet Masterscore 680 or better",
            "is_hard_stop":         True,
        },
        {
            "rule_type":            RuleType.TRUCKING_MIN_TRUCKS,
            "operator":             Operator.GTE,
            "value":                "5",
            "applies_to_industry":  "trucking",
            "description":          "Trucking: currently operating 5 or more trucks",
            "is_hard_stop":         True,
        },
        {
            "rule_type":            RuleType.EQUIPMENT_MAX_AGE_YEARS,
            "operator":             Operator.LTE,
            "value":                "10",
            "applies_to_industry":  "trucking",
            "description":          "Trucking: Class 8 trucks and trailers must be 10 years old or newer",
            "is_hard_stop":         True,
        },
    ],
    "programs": [
        {"name": "A-Credit $15K–$50K",    "min_amount": 15000,  "max_amount": 50000,  "credit_tier": "A", "description": "Rate: 9.00%"},
        {"name": "A-Credit $50K–$150K",   "min_amount": 50001,  "max_amount": 150000, "credit_tier": "A", "description": "Rate: 8.25%"},
        {"name": "A-Credit $150K+",       "min_amount": 150001, "max_amount": None,   "credit_tier": "A", "description": "Rate: 7.75%"},
        {"name": "B-Credit $15K–$50K",    "min_amount": 15000,  "max_amount": 50000,  "credit_tier": "B", "description": "Rate: 9.75%"},
        {"name": "B-Credit $50K–$150K",   "min_amount": 50001,  "max_amount": 150000, "credit_tier": "B", "description": "Rate: 9.00%"},
        {"name": "B-Credit $150K+",       "min_amount": 150001, "max_amount": None,   "credit_tier": "B", "description": "Rate: 8.25%"},
        {"name": "C-Credit $15K–$50K",    "min_amount": 15000,  "max_amount": 50000,  "credit_tier": "C", "description": "Rate: 10.50%"},
        {"name": "D-Credit",              "min_amount": 15000,  "max_amount": None,   "credit_tier": "D", "description": "Rates from 11.75%"},
        {"name": "E-Credit",              "min_amount": 15000,  "max_amount": None,   "credit_tier": "E", "description": "Rates from 13.75%"},
    ],
})


# ────────────────────────────────────────────────────────────
# CITIZENS BANK
# Source: Citizens Bank Equipment Finance Program 2025
# ────────────────────────────────────────────────────────────
seed_lender({
    "name":          "Citizens Bank",
    "contact_name":  "Joey Walter",
    "contact_email": "joey.walter@thecitizensbank.net",
    "contact_phone": "501-451-5113",
    "notes":         "Arkansas-based. No California. No cannabis. Applicants must be US citizens.",
    "rules": [
        {
            "rule_type":   RuleType.MIN_FICO,
            "operator":    Operator.GTE,
            "value":       "700",
            "description": "Minimum 700 TransUnion credit score",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.MIN_YEARS_IN_BUSINESS,
            "operator":    Operator.GTE,
            "value":       "2",
            "description": "Minimum 2 years in business",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.BANKRUPTCY_MIN_YEARS_DISCHARGED,
            "operator":    Operator.GTE,
            "value":       "5",
            "description": "Bankruptcy must be discharged 5+ years ago",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.EXCLUDED_STATE,
            "operator":    Operator.NEQ,
            "value":       "CA",
            "description": "Citizens Bank does not provide financing in California",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.EXCLUDED_INDUSTRY,
            "operator":    Operator.NEQ,
            "value":       "cannabis",
            "description": "Cannabis-related equipment/businesses are not financed",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.MAX_MILEAGE,
            "operator":    Operator.LTE,
            "value":       "600000",
            "applies_to_industry": "trucking",
            "description": "Class 8 trucks: mileage over 600,001 not desired",
            "is_hard_stop": True,
        },
        {
            "rule_type":   RuleType.REQUIRES_HOMEOWNERSHIP,
            "operator":    Operator.EQ,
            "value":       "true",
            "description": "Non-homeowner program requires homeownership (Tier 1/2)",
            "is_hard_stop": False,  # informational — affects tier, not eligibility outright
        },
    ],
    "programs": [
        {
            "name":        "Tier 1 — App Only",
            "min_amount":  None,
            "max_amount":  75000,
            "credit_tier": "1",
            "description": "Up to $75K total relationship. 700+ credit, homeownership required.",
        },
        {
            "name":        "Tier 2 — App Only (Startup)",
            "min_amount":  None,
            "max_amount":  50000,
            "credit_tier": "2",
            "description": "Up to $50K. Start-up or non-homeowner program. GPS required.",
        },
        {
            "name":        "Tier 3 — Full Financials",
            "min_amount":  75001,
            "max_amount":  1000000,
            "credit_tier": "3",
            "description": "$75K–$1M. Requires last 2 years business + personal tax returns.",
        },
    ],
})


print("\nSeeding complete.")
db.close()