# Lender Matching Platform — Frontend

Next.js frontend for **LenderMatch**: submit loan applications, view lender matches, manage lender policies, and ingest new lenders from PDF guidelines.

---

## Overview

The frontend is the user-facing side of the Lender Matching Platform. It talks to the FastAPI backend (see `../backend/README.md`) for:

- **Applications** — Multi-step application form; submit and view match results (list + detail with criteria).
- **Lenders** — List lenders, view lender detail with rules and programs; edit/delete rules (programs are view-only).
- **Ingestion** — Upload lender PDFs, list ingestions, review extracted rules/programs, and approve or reject.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | **Next.js 16** (App Router) |
| Language | **TypeScript** |
| UI | **React 19**, **Tailwind CSS 4**, **shadcn/ui** (Radix primitives) |
| HTTP | **axios** |
| Toasts | **sonner** |
| Icons | **lucide-react** |
| Font | **Inter** (next/font) |

---

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout: Nav + main; metadata (LenderMatch)
│   ├── page.tsx                # Home: 3 cards → Apply, Lenders, Upload PDF
│   ├── globals.css              # Tailwind + shadcn theme variables
│   ├── apply/
│   │   └── page.tsx            # New Application — 4-step form, submit → redirect to /applications/:id
│   ├── applications/
│   │   ├── page.tsx            # Applications list: table, status, eligibility, best fit, link to detail
│   │   └── [id]/page.tsx       # Application detail: borrower + loan summary, match results, criteria, re-run
│   ├── lenders/
│   │   ├── page.tsx            # Lender list: table, click row → detail
│   │   └── [id]/page.tsx       # Lender detail: rules (edit/delete) + programs (view-only) tabs
│   ├── ingest/
│   │   ├── page.tsx            # Upload PDF + list ingestions; link to review
│   │   └── [id]/page.tsx       # Ingestion review: extracted rules/programs, approve/reject (with optional edits)
│   └── ...
├── components/
│   ├── nav.tsx                 # Top nav: Home, New Application, Lender Policies, Upload PDF
│   └── ui/                     # shadcn components (badge, button, card, dialog, input, label, select, etc.)
├── lib/
│   ├── api.ts                  # All backend API calls (applications, lenders, ingest)
│   ├── types.ts                # TS interfaces: Application, Lender, Ingestion, form data, etc.
│   └── utils.ts                # cn() (classnames)
├── public/
├── package.json
├── next.config.ts              # reactCompiler: true
├── tsconfig.json
└── README.md                   # This file
```

---

## What’s Built

### 1. Home (`/`)

- **LenderMatch** heading and short tagline.
- Three cards: **New Application** → `/apply`, **Lender Policies** → `/lenders`, **Upload PDF** → `/ingest`.

### 2. New Application (`/apply`)

- **4-step wizard**: Business Info → Guarantor → Business Credit → Loan Request.
- **Business Info**: name, industry, state, years in business, revenue; “Number of trucks” when industry is trucking.
- **Guarantor**: name, FICO, ownership %, homeowner, CDL, bankruptcy (years since discharge when applicable).
- **Business Credit**: PayNet score, comparable credit amount (optional).
- **Loan Request**: amount, equipment type/year, mileage, private party toggle.
- Validation per step; on Submit, payload is sent via `submitApplication()` (POST `/applications`). On success, **redirects to `/applications/{id}`**.
- Progress indicator and Back/Next/Submit buttons.

### 3. Applications list (`/applications`)

- `listApplications()` → table with status badge, eligibility summary (X / N lenders), best fit score.
- Link each row to `/applications/[id]`. Refresh and “New Application” button.

### 4. Application detail (`/applications/[id]`)

- `getApplication(id)` → borrower summary, loan request summary, and **match results** per lender.
- Each lender: eligible yes/no, fit score, expandable **criteria** table (pass/fail, actual/required, explanation).
- **Re-run matching** button calls `rerunUnderwriting(id)`; toasts for success/error.

### 5. Lenders list (`/lenders`)

- `listLenders()` → table; click row → `/lenders/[id]`. Loading and error states with retry.

### 6. Lender detail (`/lenders/[id]`)

- `getLender(id)` → **Rules** tab: inline edit (value, description, is_hard_stop, is_active), save via `updateRule`, delete via `deleteRule`; toasts.
- **Programs** tab: read-only table (name, min/max amount, credit tier, description). Create/update/delete programs not implemented in the UI (backend supports it).

### 7. Ingest upload & list (`/ingest`)

- **Upload**: drag-and-drop or file picker; `uploadPDF(file)` → toast and redirect to `/ingest/[id]`.
- **List**: `listIngestions()` → table (filename, status, created_at); link to review page. Refresh and loading states.

### 8. Ingestion review (`/ingest/[id]`)

- `getIngestion(id)` → extracted lender name, rules, and programs (with source_quote). Polling while status is `PENDING_REVIEW` (extraction in progress).
- **Editable** rules/programs before approve (value, description, is_hard_stop, etc.).
- **Approve** → `approveIngestion(id, payload)` (creates Lender + rules + programs); **Reject** → `rejectIngestion(id)`. Toasts and redirect.

### 9. API client (`lib/api.ts`)

- **Applications**: `submitApplication`, `getApplication`, `listApplications`, `rerunUnderwriting`
- **Lenders**: `listLenders`, `getLender`, `updateRule`, `deleteRule`
- **Ingestion**: `uploadPDF`, `listIngestions`, `getIngestion`, `approveIngestion`, `rejectIngestion`

Base URL: `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001"`.

### 10. Types (`lib/types.ts`)

- **Lender**: `Lender`, `PolicyRule`, `LenderProgram`
- **Application**: `Application`, `Borrower`, `PersonalGuarantor`, `BusinessCredit`, `LoanRequest`, `MatchResult`, `CriteriaDetail`
- **Ingestion**: `Ingestion` with nested `extracted` (rules, programs, lender name, etc.)
- **Form**: `ApplicationFormData` — flat structure for the apply form, mapped to API payload in `api.ts`

### 11. Navigation & UI

- **Nav** highlights current route (Home, New Application, Lender Policies, Upload PDF).
- **Layout** wraps all pages with Nav + `<main className="max-w-6xl mx-auto px-6 py-8">`.
- **shadcn** components: Button, Card, Input, Label, Select, Switch, Badge, Dialog, Separator, Table, Sonner. Styling via Tailwind and `globals.css`.

---

## Possible Future Work

- **Lender programs CRUD in UI** — Backend supports create/update/delete programs; frontend lender detail only shows programs (read-only). Add forms and API calls for program management.
- **Environment** — Document `NEXT_PUBLIC_API_URL` in root `.env.example` for production.
- **Auth** — If the backend adds auth, add login/logout and send tokens (e.g. in axios interceptors).

---

## Setup & Run

### Prerequisites

- Node 18+
- Backend running (e.g. `uvicorn app.main:app --port 8001`). See `../backend/README.md`.

### Install and dev

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The app calls the API at `http://localhost:8001` unless you set `NEXT_PUBLIC_API_URL`.

### Build

```bash
npm run build
npm run start
```

### Lint

```bash
npm run lint
```

---

## Environment

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend base URL (default in code: `http://localhost:8001`) |

Create `.env.local` in `frontend/` to override (e.g. different port or deployed API).

---

## Summary

- **Done**: Home, 4-step apply form, applications list and detail (with match results and re-run), lenders list and detail (rule edit/delete, programs view-only), ingest upload + list + review/approve with editable rules, API client and types, nav, shadcn UI, Sonner toasts.
- **Optional next**: Program CRUD on lender detail, env docs, auth when backend supports it.
