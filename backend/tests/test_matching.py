"""
Test the matching engine end to end against real lender rules in the DB.

Run with:
    python tests/test_matching.py

What we're verifying:
  A) Strong applicant   → eligible, high fit score
  B) Low FICO           → ineligible, FICO rule fails
  C) Trucking/few trucks→ ineligible, trucking-specific rules fail

Each test prints a clear PASS/FAIL so you can spot issues immediately.
"""
import sys, json, requests

BASE = "http://localhost:8001"


def submit(label: str, payload: dict) -> dict:
    r = requests.post(f"{BASE}/applications", json=payload)
    if r.status_code not in (200, 201):
        print(f"\n❌ {label} — HTTP {r.status_code}")
        print(r.text)
        sys.exit(1)
    return r.json()


def print_results(label: str, data: dict, expected_eligible: bool):
    print(f"\n{'='*60}")
    print(f"Application: {label}")
    print(f"Status: {data['status']}")
    print(f"{'='*60}")

    results = data.get("results", [])
    if not results:
        print("⚠️  No match results returned — matching engine may not have run")
        return

    for result in results:
        lender  = result["lender"]["name"]
        eligible = result["is_eligible"]
        score    = result["fit_score"]
        icon     = "✅" if eligible else "❌"

        print(f"\n{icon} {lender}  |  fit score: {score:.1f}")

        # Print failing criteria
        failures = [c for c in result["criteria"] if not c["passed"]]
        passes   = [c for c in result["criteria"] if c["passed"]]

        if failures:
            print(f"   FAILED rules ({len(failures)}):")
            for c in failures:
                print(f"     ✗ {c['explanation']}")

        print(f"   PASSED rules: {len(passes)}")

        # Verify expectation
        if eligible == expected_eligible:
            print(f"   ✅ CORRECT — expected {'eligible' if expected_eligible else 'ineligible'}")
        else:
            print(f"   ❌ WRONG   — expected {'eligible' if expected_eligible else 'ineligible'} but got {'eligible' if eligible else 'ineligible'}")


# ── Application A: Strong applicant ──────────────────────────
# Should PASS all Falcon rules
A = submit("A — Strong applicant (should PASS)", {
    "borrower": {
        "business_name":     "Acme Manufacturing Co",
        "industry":          "manufacturing",
        "state":             "TX",
        "years_in_business": 8,
        "annual_revenue":    2000000,
        "num_trucks":        0,
        "guarantors": [{
            "full_name":                 "Jane Smith",
            "fico_score":                740,
            "ownership_pct":             100,
            "has_bankruptcy":            False,
            "is_homeowner":              True,
            "has_cdl":                   False,
        }],
        "biz_credit": {
            "paynet_score":             710,
            "comparable_credit_amount": 280000,  # 80% of loan amount — passes 70% rule
        }
    },
    "loan_request": {
        "amount":          350000,
        "equipment_type":  "machine_tool",
        "equipment_year":  2020,
        "is_private_party": False,
    }
})
print_results("A — Strong applicant (should PASS)", A, expected_eligible=True)


# ── Application B: Low FICO ───────────────────────────────────
# Should FAIL — FICO 620 is below Falcon's minimum of 680
B = submit("B — Low FICO (should FAIL)", {
    "borrower": {
        "business_name":     "Budget Equipment LLC",
        "industry":          "commercial",
        "state":             "FL",
        "years_in_business": 5,
        "annual_revenue":    800000,
        "num_trucks":        0,
        "guarantors": [{
            "full_name":                 "Bob Jones",
            "fico_score":                620,       # ← below 680 minimum
            "ownership_pct":             100,
            "has_bankruptcy":            False,
            "is_homeowner":              True,
            "has_cdl":                   False,
        }],
        "biz_credit": {
            "paynet_score":             670,
            "comparable_credit_amount": 175000,
        }
    },
    "loan_request": {
        "amount":          200000,
        "equipment_type":  "forklift",
        "equipment_year":  2019,
        "is_private_party": False,
    }
})
print_results("B — Low FICO 620 (should FAIL)", B, expected_eligible=False)


# ── Application C: Trucking — not enough trucks ───────────────
# Should FAIL — only 3 trucks, Falcon requires 5+ for trucking
C = submit("C — Trucking/few trucks (should FAIL)", {
    "borrower": {
        "business_name":     "Small Haul Trucking",
        "industry":          "trucking",
        "state":             "OH",
        "years_in_business": 6,
        "annual_revenue":    500000,
        "num_trucks":        3,         # ← below 5 truck minimum
        "guarantors": [{
            "full_name":                 "Mike Davis",
            "fico_score":                720,
            "ownership_pct":             100,
            "has_bankruptcy":            False,
            "is_homeowner":              True,
            "has_cdl":                   True,
            "years_cdl":                 8,
        }],
        "biz_credit": {
            "paynet_score":             690,
            "comparable_credit_amount": 100000,
        }
    },
    "loan_request": {
        "amount":          120000,
        "equipment_type":  "class_8_truck",
        "equipment_year":  2019,        # 7 years old — within 10 year limit
        "mileage":         350000,
        "is_private_party": False,
    }
})
print_results("C — Trucking/3 trucks (should FAIL)", C, expected_eligible=False)

print(f"\n{'='*60}")
print("Done. Review results above.")
print("Each application should show CORRECT next to the eligibility verdict.")
print(f"{'='*60}\n")