"""
Manual test — runs the full extraction + GPT-4o parsing pipeline.
Usage:
    python tests/test_parsing.py pdfs/2025_Program_Guidelines_UPDATED.pdf
"""
import sys, json
sys.path.insert(0, ".")

from app.services.pdf_extractor import extract_pdf
from app.services.llm_parser import parse_pdf_policy

if len(sys.argv) < 2:
    print("Usage: python tests/test_parsing.py <path_to_pdf>")
    sys.exit(1)

pdf_path = sys.argv[1]

# ── Step 1: Extract text from PDF ────────────────────────────
print(f"Extracting text from {pdf_path}...")
extracted = extract_pdf(pdf_path)
print(f"✓ Extracted {len(extracted.raw_text)} chars, {len(extracted.tables)} tables\n")

# ── Step 2: Send to GPT-4o ────────────────────────────────────
print("Sending to GPT-4o via instructor...")
print("(This takes 10-20 seconds)\n")
policy = parse_pdf_policy(extracted.full_content(), extracted.source_filename)

# ── Step 3: Print results ─────────────────────────────────────
print("=" * 60)
print(f"Lender:        {policy.lender_name}")
print(f"Contact:       {policy.contact_name} — {policy.contact_email}")
print(f"Phone:         {policy.contact_phone}")
print(f"Rules found:   {len(policy.rules)}")
print(f"Programs found:{len(policy.programs)}")
print("=" * 60)

print("\n── EXTRACTED RULES ───────────────────────────────────────")
for i, rule in enumerate(policy.rules, 1):
    status = "🔴 HARD STOP" if rule.is_hard_stop else "🟡 informational"
    industry = f" [{rule.applies_to_industry} only]" if rule.applies_to_industry else ""
    print(f"\n{i}. {rule.rule_type}{industry} {rule.operator} {rule.value}  {status}")
    print(f"   Description:  {rule.description}")
    print(f"   Source quote: \"{rule.source_quote[:100]}\"")

print("\n── EXTRACTED PROGRAMS ────────────────────────────────────")
for prog in policy.programs:
    amt_range = ""
    if prog.min_amount and prog.max_amount:
        amt_range = f"  ${prog.min_amount:,.0f} – ${prog.max_amount:,.0f}"
    elif prog.max_amount:
        amt_range = f"  up to ${prog.max_amount:,.0f}"
    elif prog.min_amount:
        amt_range = f"  from ${prog.min_amount:,.0f}"
    print(f"  • {prog.name}{amt_range}")
    if prog.description:
        print(f"    {prog.description[:100]}")

if policy.extraction_notes:
    print(f"\n── EXTRACTION NOTES ──────────────────────────────────────")
    print(f"  {policy.extraction_notes}")

# Also dump the raw JSON so you can see exactly what instructor returned
print("\n── RAW JSON OUTPUT ───────────────────────────────────────")
print(json.dumps(policy.model_dump(), indent=2))