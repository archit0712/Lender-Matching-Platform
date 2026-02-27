# Lender Matching Platform — Frontend

Next.js frontend for **LenderMatch**: submit loan applications, view lender matches, manage lender policies, and ingest new lenders from PDF guidelines.

---

## Overview

The frontend is the user-facing side of the Lender Matching Platform. It talks to the FastAPI backend (see `../backend/README.md`) for:

- **Applications** — Multi-step application form; submit and get matched to lenders.
- **Lenders** — List lenders, view/edit rules and programs (API ready; UI partially or not yet built).
- **Ingestion** — Upload lender PDFs, review extracted rules, approve/reject (API ready; UI not yet built).

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | **Next.js 16** (App Router) |
| Language | **TypeScript** |
| UI | **React 19**, **Tailwind CSS 4**, **shadcn/ui** (Radix primitives) |
| HTTP | **axios** |
| Toasts | **sonner** |
| Font | **Inter** (next/font) |

---

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout: Nav + main; metadata (LenderMatch)
│   ├── page.tsx            # Home: 3 cards → Apply, Lenders, Upload PDF
│   ├── globals.css         # Tailwind + shadcn theme variables
│   ├── apply/
│   │   └── page.tsx        # New Application — 4-step form, submit → redirect to /applications/:id
│   ├── lenders/            # (not yet) Lender list + detail + rule edit
│   ├── ingest/             # (not yet) PDF upload + review/approve
│   └── applications/       # (not yet) Application list + detail (match results)
├── components/
│   ├── nav.tsx             # Top nav: Home, New Application, Lender Policies, Upload PDF
│   └── ui/                 # shadcn components
│       ├── badge.tsx
│       ├── button.tsx
│       ├── card.tsx
│       ├── dialog.tsx
│       ├── input.tsx
│       ├── label.tsx
│       ├── select.tsx
│       ├── separator.tsx
│       ├── sonner.tsx
│       ├── switch.tsx
│       └── table.tsx
├── lib/
│   ├── api.ts              # All backend API calls (applications, lenders, ingest)
│   ├── types.ts            # TS interfaces: Application, Lender, Ingestion, form data, etc.
│   └── utils.ts            # cn() (classnames)
├── public/
├── package.json
├── next.config.ts          # reactCompiler: true
├── tsconfig.json
└── README.md                # This file
```

---

## What’s Built Today

### 1. Home (`/`)

- **LenderMatch** heading and short tagline.
- Three cards:
  - **New Application** → `/apply`
  - **Lender Policies** → `/lenders`
  - **Upload PDF** → `/ingest`

### 2. New Application (`/apply`)

- **4-step wizard**: Business Info → Guarantor → Business Credit → Loan Request.
- **Business Info**: name, industry, state, years in business, revenue; “Number of trucks” only when industry is trucking.
- **Guarantor**: name, FICO, ownership %, homeowner, CDL, bankruptcy (with years since discharge when applicable).
- **Business Credit**: PayNet score, comparable credit amount (optional).
- **Loan Request**: amount, equipment type/year, mileage, private party toggle.
- **Validation** per step; on Submit, payload is sent via `submitApplication()` (POST `/applications`). On success, **redirects to `/applications/{id}`** (that page is not implemented yet — will 404).
- Progress indicator and Back/Next/Submit buttons.

### 3. API client (`lib/api.ts`)

Fully wired for:

- **Applications**: `submitApplication`, `getApplication`, `listApplications`, `rerunUnderwriting`
- **Lenders**: `listLenders`, `getLender`, `updateRule`, `deleteRule`
- **Ingestion**: `uploadPDF`, `listIngestions`, `getIngestion`, `approveIngestion`, `rejectIngestion`

Base URL: `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001"`.

### 4. Types (`lib/types.ts`)

- **Lender**: `Lender`, `PolicyRule`, `LenderProgram`
- **Application**: `Application`, `Borrower`, `PersonalGuarantor`, `BusinessCredit`, `LoanRequest`, `MatchResult`, `CriteriaDetail`
- **Ingestion**: `Ingestion` with nested `extracted` (rules, programs, lender name, etc.)
- **Form**: `ApplicationFormData` — flat structure used by the apply form and mapped to API payload in `api.ts`

### 5. Navigation & layout

- **Nav** highlights current route (Home, New Application, Lender Policies, Upload PDF).
- **Layout** wraps all pages with Nav + `<main className="max-w-6xl mx-auto px-6 py-8">`.

### 6. UI components

- shadcn-based: Button, Card, Input, Label, Select, Switch, Badge, Dialog, Separator, Table, Sonner (toasts). Styling via Tailwind and `globals.css` theme.

---

## What’s Not Built Yet (Future Work)

These are the natural next steps given the existing API and types:

1. **Application result page** (`/applications/[id]`)
   - After submit, the app redirects here but the route doesn’t exist.
   - **Suggested**: Load `getApplication(id)`, show borrower + loan request summary and a **match results** list (lender name, eligible yes/no, fit score, expandable criteria per lender). Optionally a “Re-run matching” button calling `rerunUnderwriting(id)`.

2. **Applications list** (`/applications` or linked from home)
   - **Suggested**: `listApplications()`, table or cards with link to `/applications/[id]`.

3. **Lender Policies** (`/lenders`)
   - **Suggested**: `listLenders()` → table of lenders; click → lender detail page with rules and programs; inline edit/delete rules using `updateRule`, `deleteRule` (and equivalent for programs if backend supports).

4. **Lender detail** (`/lenders/[id]`)
   - Show one lender with rules and programs; edit rules (value, description, is_active, is_hard_stop), add/remove rules or programs as the API allows.

5. **PDF ingest** (`/ingest`)
   - **Upload**: `uploadPDF(file)` → show ingestion_id and workflow_run_id; optional polling or status.
   - **List**: `listIngestions()` → table of ingestions (filename, status, created_at).
   - **Review**: `getIngestion(id)` → show extracted lender name, rules, programs (with source_quote); allow approve (with optional edits) via `approveIngestion(id, payload)` or reject via `rejectIngestion(id)`.

6. **Error handling & toasts**
   - Use Sonner in layout; on API errors (e.g. submit failure), show a toast and/or inline message (apply page already shows inline submit error).

7. **Environment**
   - Document `NEXT_PUBLIC_API_URL` for production (e.g. in `.env.example`).

8. **Auth (optional)**
   - If the backend adds auth, add login/logout and send tokens (e.g. in axios interceptors).

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

Open [http://localhost:3000](http://localhost:3000). The app will call the API at `http://localhost:8001` unless you set `NEXT_PUBLIC_API_URL`.

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
| `NEXT_PUBLIC_API_URL` | Backend base URL (default: `http://localhost:8001`) |

Create `.env.local` in `frontend/` if you need to override (e.g. for a different port or deployed API).

---

## Summary

- **Done**: Home, 4-step apply form, API client and types for applications/lenders/ingest, nav, shadcn UI.
- **Next**: Application result page (`/applications/[id]`), applications list, lenders list/detail and rule editing, ingest upload + list + review/approve, and consistent error/toast handling. The backend and frontend API layer are ready for these screens.
