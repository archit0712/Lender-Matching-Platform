# Lender Matching Platform — Backend

FastAPI backend for the **Lender Matching Platform**: equipment-finance lender policy ingestion (PDF → rules) and application-to-lender matching.

---

## Overview

The backend does two main things:

1. **Lender policy ingestion** — Upload lender guideline PDFs; extract text, parse credit rules with GPT-4o, and store them for admin review. After approval, rules become live in the matching engine.
2. **Application matching** — Accept loan applications (borrower + loan request), evaluate them against all active lenders’ policy rules, and return match results with eligibility and fit scores.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | **FastAPI** |
| DB | **PostgreSQL** (SQLAlchemy 2.0 ORM) |
| Migrations | **Alembic** |
| PDF extraction | **pdfplumber** |
| LLM parsing | **OpenAI GPT-4o** + **instructor** (structured output) |
| Async jobs | **Hatchet** (PDF ingestion workflow) |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, CORS, router registration
│   ├── config.py            # Pydantic settings (DB, OpenAI, Hatchet)
│   ├── database.py          # SQLAlchemy engine, SessionLocal, get_db
│   ├── worker.py            # Hatchet client + worker entry (run PDF workflow)
│   ├── models/              # SQLAlchemy models
│   │   └── __init__.py      # Lender, PolicyRule, LenderProgram, Borrower, Application, etc.
│   ├── schemas/             # Pydantic request/response schemas
│   │   └── __init__.py      # ApplicationCreate, BorrowerCreate, LoanRequestCreate, etc.
│   ├── routers/
│   │   ├── ingest.py        # PDF upload, list/get ingestion, approve/reject
│   │   ├── applications.py # Create application, list/get, re-run matching
│   │   └── lenders.py       # CRUD lenders, rules, programs
│   ├── engine/              # Matching logic
│   │   ├── matcher.py       # LenderMatcher — runs all lenders, persists MatchResult + CriteriaDetail
│   │   └── evaluator.py     # RuleEvaluator — evaluates each PolicyRule against ApplicationContext
│   ├── workflows/
│   │   └── pdf_ingestion.py # Hatchet task: extract → parse (GPT-4o) → save to DB
│   └── services/
│       ├── pdf_extractor.py # pdfplumber extraction (text + tables) → ExtractedPDF
│       └── llm_parser.py     # instructor + GPT-4o → ParsedLenderPolicy (rules + programs)
├── alembic/                 # Migrations
│   ├── env.py
│   └── versions/
├── tests/
│   ├── test_matching.py     # E2E: submit applications, assert eligibility/fit
│   ├── test_extraction.py   # Manual: run PDF extraction on a file
│   └── test_llmparser.py    # Manual: full extract + parse pipeline
├── scripts/                 # Utilities (e.g. hatchet_task_attrs)
├── seed.py                  # Seed lenders (Falcon, Citizens) with rules/programs
├── requirements.txt
├── Dockerfile
└── README.md                # This file
```

---

## Data Model (Summary)

- **Lenders** — Name, contact, active flag. Have many **PolicyRule** and **LenderProgram**.
- **PolicyRule** — `rule_type` (e.g. `MIN_FICO`, `MAX_LOAN_AMOUNT`, `EXCLUDED_STATE`), `operator` (GTE/LTE/EQ/NEQ), `value`, optional `applies_to_industry`, `is_hard_stop`, `source_quote`.
- **LenderProgram** — Name, min/max amount, credit tier, description.
- **PDFIngestion** — Uploaded PDF metadata, `extracted_json` (GPT-4o output), status: `PENDING_REVIEW` → `APPROVED` or `REJECTED`.
- **Borrower** — Business name, industry, state, years in business, revenue, num_trucks; has **PersonalGuarantor**(s) and optional **BusinessCredit** (PayNet, comparable credit).
- **LoanRequest** — Amount, term, equipment type/year/mileage, private party flag.
- **Application** — Links one Borrower + one LoanRequest; status DRAFT → SUBMITTED → MATCHED (or ERROR).
- **MatchResult** — Per application per lender: `is_eligible`, `fit_score`, optional `program_id`; has many **CriteriaDetail** (per-rule pass/fail, actual/required, explanation).

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| **Health** | | |
| GET | `/health` | Service health check |
| **Ingestion** | | |
| POST | `/ingest/pdf` | Upload PDF → create ingestion, trigger Hatchet workflow (202 Accepted) |
| GET | `/ingest/` | List all ingestion records |
| GET | `/ingest/{id}` | Get one ingestion + full `extracted` JSON |
| POST | `/ingest/{id}/approve` | Approve: create Lender + PolicyRules + Programs, set status APPROVED |
| POST | `/ingest/{id}/reject` | Reject: set status REJECTED |
| **Applications** | | |
| POST | `/applications/` | Create borrower + loan request + application; run matching; return full application with results |
| GET | `/applications/` | List applications (with nested borrower, loan_request, results) |
| GET | `/applications/{id}` | Get one application with full detail |
| POST | `/applications/{id}/run` | Re-run matching for existing application |
| **Lenders** | | |
| GET | `/lenders/` | List all lenders with rules and programs |
| POST | `/lenders/` | Create lender (optional rules/programs) |
| GET | `/lenders/{id}` | Get one lender |
| PATCH | `/lenders/{id}` | Partial update lender |
| DELETE | `/lenders/{id}` | Delete lender (cascade rules/programs) |
| GET/POST/PUT/DELETE | `/lenders/{id}/rules` | List, add, update, delete policy rules |
| GET/POST/PUT/DELETE | `/lenders/{id}/programs` | List, add, update, delete programs |

---

## Rule Types (Evaluator)

The **RuleEvaluator** supports these `RuleType` values (see `app/models` and `app/engine/evaluator.py`):

- `MIN_FICO`, `MIN_PAYNET`, `MIN_YEARS_IN_BUSINESS`
- `MAX_LOAN_AMOUNT`, `MIN_LOAN_AMOUNT`, `MAX_LOAN_AMOUNT_BY_INDUSTRY`
- `EQUIPMENT_MAX_AGE_YEARS`, `MAX_MILEAGE`
- `EXCLUDED_STATE`, `EXCLUDED_INDUSTRY`
- `BANKRUPTCY_MIN_YEARS_DISCHARGED`, `REQUIRES_HOMEOWNERSHIP`
- `MIN_COMPARABLE_CREDIT_PCT`, `TRUCKING_MIN_TRUCKS`

Rules can be scoped with `applies_to_industry`. Fit score combines pass rate on hard-stop rules with small bonuses for FICO/PayNet headroom.

---

## PDF Ingestion Flow

1. **POST /ingest/pdf** — PDF file uploaded; `PDFIngestion` row created with `PENDING_REVIEW`; PDF bytes (base64) + `ingestion_id` sent to Hatchet workflow.
2. **Hatchet worker** runs `run_pdf_ingestion`:
   - Decode PDF, extract text + tables (`pdf_extractor`).
   - Parse with GPT-4o via `instructor` → `ParsedLenderPolicy` (rules + programs) (`llm_parser`).
   - Save `extracted_json` to `PDFIngestion`, keep status `PENDING_REVIEW`.
3. Client polls **GET /ingest/{id}** until `extracted` is present.
4. Admin reviews (and optionally edits) in UI; then **POST /ingest/{id}/approve** to create Lender + PolicyRules + LenderPrograms and set ingestion to `APPROVED`. Or **POST /ingest/{id}/reject**.

---

## Setup & Run

### Environment

Create a `.env` at the **project root** (parent of `backend/`) with:

- `DATABASE_URL` — PostgreSQL connection string (e.g. `postgresql://user:pass@localhost:5432/dbname`)
- `OPENAI_API_KEY` — For GPT-4o parsing
- `HATCHET_CLIENT_TOKEN` — For triggering and running the PDF ingestion workflow

### Database

```bash
cd backend
# Create DB and run migrations
alembic upgrade head
# Optional: seed lenders
python seed.py
```

### API server

```bash
uvicorn app.main:app --reload --port 8000
```

CORS is set to allow `http://localhost:3000` (frontend).

### Hatchet worker (for PDF ingestion)

Run in a separate terminal so the PDF workflow can execute:

```bash
python -m app.worker
```

### Docker

```bash
docker build -t lender-matching-backend .
docker run -p 8000:8000 --env-file ../.env lender-matching-backend
```

Note: Running the Hatchet worker inside the same container is possible but typically you’d run the worker as a separate process or container.

---

## Tests

- **test_matching.py** — Hits the running API at `http://localhost:8001`; submits strong applicant, low-FICO, and trucking/low-trucks applications; checks eligibility and fit scores. Run API on port 8001 (or change `BASE` in the test).
- **test_extraction.py** — `python tests/test_extraction.py path/to/file.pdf` — runs PDF extraction only.
- **test_llmparser.py** — `python tests/test_llmparser.py path/to/file.pdf` — runs full extract + GPT-4o parse pipeline (costs API calls).

---

## Seed Data

`seed.py` creates two example lenders with rules and programs:

- **Falcon Equipment Finance** — Global + industry-specific rules (trucking, logging, commercial, manufacturing), multiple credit tiers and programs.
- **Citizens Bank** — FICO, years in business, bankruptcy, excluded state (CA), excluded industry (cannabis), mileage, homeownership.

Run once after migrations: `python seed.py`. Idempotent by lender name.

---

## Summary

The backend provides:

- **Ingest** — PDF upload → async extraction + GPT-4o parsing → admin approve/reject → live lender rules.
- **Lenders** — Full CRUD and rule/program management.
- **Applications** — Create application with borrower + loan request; automatic matching; re-run matching on demand.
- **Matching engine** — RuleEvaluator + LenderMatcher with fit scoring and criteria detail for each application–lender pair.

All of this is wired for the frontend at `http://localhost:3000` and ready to extend with more rule types, workflows, or APIs as needed.
