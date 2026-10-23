# 🏛️ Smart FDR Lifecycle Management Portal

> **Smart India Hackathon 2026 · Problem Statement SIH26265 — Streamline of Security Deposit / FDR Portal**
> A centralized portal that manages the complete lifecycle of institutional security deposits (FDRs): submission → OCR-assisted verification → maturity monitoring → renewal → controlled release, with a tamper-evident audit trail.

---

## 📌 Table of Contents

1. [Problem](#-problem)
2. [Solution Overview](#-solution-overview)
3. [Key Features](#-key-features)
4. [System Architecture](#-system-architecture)
5. [Tech Stack](#-tech-stack)
6. [Repository Structure](#-repository-structure)
7. [Getting Started](#-getting-started)
8. [Environment Variables](#-environment-variables)
9. [Demo Accounts & Data](#-demo-accounts--data)
10. [Demo Walkthrough](#-demo-walkthrough)
11. [API Overview](#-api-overview)
12. [Data Model](#-data-model)
13. [Security & Compliance Design](#-security--compliance-design)
14. [Testing](#-testing)
15. [Roadmap](#-roadmap)
16. [Limitations & Disclaimers](#-limitations--disclaimers)
17. [Team](#-team)

---

## ❗ Problem

AICTE regulates technical institutions in India. As part of certain approval and compliance processes, institutions may need to maintain security deposits as **Fixed Deposit Receipts (FDRs)**. Managing these through scattered spreadsheets, emails, and manual records leads to:

- Maturity dates missed because nobody is alerted in time
- Officials searching emails and files to find the current status of a deposit
- Renewal history that is hard to trace
- Release requests stalled due to incomplete documents or approval history
- Manual, error-prone data entry and no consistent verification

> These are illustrative scenarios, not claims about a specific AICTE incident.

## 💡 Solution Overview

Treat every FDR as a **record that moves through a defined lifecycle**, not just an uploaded PDF.

```
Submit → Auto-extract (OCR) → Validate → Verify → Monitor → Renew / Release → Audit
```

The portal automates the repetitive work (data extraction, rule checks, deadline tracking, notifications) while **keeping humans in control of every decision** (verification outcomes, renewals, and releases require authorized officer action).

## ✨ Key Features

| # | Feature | What it does |
|---|---|---|
| 1 | **Centralized FDR repository** | Searchable database of all institutions and FDRs with unique identifiers and tenant isolation |
| 2 | **OCR-assisted data entry** | Extracts 9 key fields (FDR no., bank, IFSC, branch, amount, interest rate, issue date, maturity date, lien info) from text/scanned PDFs/images for human review |
| 3 | **Rule-based validation** | Flags missing fields, invalid date order, duplicate references, duplicate documents, and mismatches |
| 4 | **Simulated Bank Adapter** | Clearly labeled simulated verification adapter comparing submitted values against bank-confirmed values |
| 5 | **Automated Maturity Monitoring** | Background scheduled runner (APScheduler) generates idempotent reminders at 30 / 15 / 7 days before maturity and flags matured instruments |
| 6 | **Renewal & replacement** | New FDR linked to the previous one; full version history preserved |
| 7 | **Controlled release workflow** | Multi-stage approval state machine with role enforcement; never automatic |
| 8 | **Officer dashboard** | Live counts, priority review cases, filters, telemetry charts, maturity radar |
| 9 | **Reports & exports** | Excel export of expiring, pending, renewed, and released FDRs with tenant filtering |
| 10 | **Tamper-evident audit log** | Append-only, SHA-256 hash-chained audit ledger with verification endpoints |
| 11 | **Bilingual UI & Dark/Light Theme**| Instant English / Hindi translation switch and Dark / Light theme toggle |
| 12 | **Secure Storage & Data Protection**| Fernet encryption at rest for documents, streaming size enforcement, magic byte validation, and expiring signed download URLs |
| 13 | **Intake Classification & Safe Escalation**| Classifies documents (likely FDR, needs review, likely unrelated, unreadable, OCR unavailable); explains readable content with masked non-sensitive snippets; human-in-the-loop 7-strike temporary hold policy with appeals and unfreeze |

### Design principles

- **Flags are warnings, not verdicts.** A mismatch or duplicate triggers review — it is not proof of fraud.
- **OCR never establishes authenticity.** It only assists data entry and requires mandatory human confirmation.
- **System outages never penalize users.** An unavailable OCR engine or unreadable file is never counted as an unrelated submission strike.
- **Maturity ≠ invalid.** Reaching maturity flags the instrument for review under the applicable rules.
- **No automatic release.** A date passing or a request being submitted never releases an FDR.
- **Tenant isolation by design.** Institutions can only view and manage their own deposits and documents. Read access is preserved even during upload review holds.

## 🧱 System Architecture

```mermaid
flowchart LR
    subgraph Client
        UI[React 18 + Vite + TS<br/>Bilingual & Dark/Light UI]
    end

    subgraph Backend[FastAPI Backend]
        API[Secure REST API + RBAC]
        AUTH[Password Auth + DB Roles]
        OCR[OCR Pipeline<br/>PyMuPDF + PIL + Tesseract]
        VAL[Validation Engine]
        VER[Simulated Bank Adapter]
        WF[Multi-Stage State Machine]
        SCH[APScheduler<br/>Automatic Maturity Job]
        STO[Encrypted Storage Service<br/>Fernet at Rest + Signed URLs]
        AUD[Audit Service<br/>SHA-256 Hash-Chained]
    end

    subgraph Storage & DB
        DB[(PostgreSQL / SQLite)]
        FILES[(Encrypted Vault Storage)]
    end

    UI -->|JWT Bearer| API
    API --> AUTH
    API --> OCR --> VAL --> VER
    API --> WF --> AUD
    SCH --> DB
    API --> DB
    API --> STO --> FILES
    AUD --> DB
```

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons, Recharts, Custom I18n & Theme Providers |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, slowapi (rate-limiting), cryptography (Fernet) |
| **Database** | SQLite (development/local) / PostgreSQL (production) |
| **OCR & Processing** | PyMuPDF (fitz), pypdf, Pillow (grayscale/contrast enhancement), pytesseract |
| **Automation** | APScheduler (in-process automated maturity monitor) |
| **DevOps** | Docker Compose, Multi-stage Dockerfiles |
| **Testing** | pytest, pytest-asyncio, HTTPX |

## 📁 Repository Structure

```
fdr-portal/
├── README.md
├── IMPLEMENTATION.md
├── docker-compose.yml
├── .env.example
├── .github/workflows/ci.yml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/            # config, security (JWT), deps, logging
│   │   ├── db/              # session, base, models/, seed.py
│   │   ├── schemas/         # Pydantic models
│   │   ├── api/             # routers: auth, institutions, fdrs, ocr,
│   │   │                    #   verification, renewals, release,
│   │   │                    #   dashboard, reports, admin
│   │   ├── services/
│   │   │   ├── ocr/         # preprocess.py, extract.py, parsers.py
│   │   │   ├── validation/  # rules.py, engine.py
│   │   │   ├── verification/# base.py, mock.py
│   │   │   ├── workflow/    # config.py, machine.py
│   │   │   ├── audit.py
│   │   │   ├── notifications.py
│   │   │   └── reports.py
│   │   └── jobs/            # scheduler.py, maturity.py
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             # router, providers
│   │   ├── components/      # ui/, layout/, fdr/, charts/
│   │   ├── features/        # auth, fdr, dashboard, renewal, release, notifications
│   │   ├── lib/             # api client, utils, i18n
│   │   └── locales/         # en.json, hi.json
│   └── package.json
├── sample-data/             # sample FDR PDFs/scans for demo & tests
└── docs/                    # architecture diagrams, screenshots, demo script
```

## 🚀 Getting Started

### Prerequisites

- Node.js 20+ and npm (or pnpm)
- Python 3.11+
- Docker & Docker Compose (recommended — includes Tesseract OCR out-of-the-box)
- **Tesseract OCR (for scanned PDF / image OCR in non-Docker local environments)**:
  - **Linux (Ubuntu/Debian)**: `sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-eng poppler-utils`
  - **macOS (Homebrew)**: `brew install tesseract`
  - **Windows**: Install the Windows installer binary from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki), add `C:\Program Files\Tesseract-OCR` to your system PATH, or set `TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"` in `.env`.
  - **Verification**: Run `tesseract --version` in terminal.
  - **OCR Health Diagnostic**: Check `GET http://localhost:8000/health/ocr` (or `/api/v1/health/ocr`) to verify that PyMuPDF, Pillow, pytesseract, and the Tesseract executable are functional.
  - *Note on Assistive OCR*: Selectable/embedded-text PDFs are extracted directly via PyMuPDF/pypdf without needing Tesseract. For scanned documents, if Tesseract is not installed on the host, the portal reports `status: "ocr_unavailable"` with clear guidance to input FDR fields manually, rather than falsely labeling the customer's document as unreadable or corrupted. OCR is strictly assistive and never proves document authenticity.
  - 📖 For complete OCR configuration details, classification categories, privacy rules, and the 7-strike escalation policy, see [OCR Setup & Intake Guide](docs/OCR_SETUP_AND_INTAKE_GUIDE.md).

### 🏦 Simulated Bank Verification Adapter (Demo Mode)

> ⚠️ **IMPORTANT DISCLAIMER — SIMULATED DATA ONLY**:
> Bank verification in this portal uses a simulated adapter (`VERIFIER_MODE=mock`) comparing against **fictional, synthetic sample records**. It does **NOT** connect to real bank core systems and must **NEVER** be described as actual bank approval or proof that an FDR is genuine. Live bank integration would require an officially sanctioned banking gateway adapter and regulatory approval, which is out of scope for this demo.

- **How it works**: Compares submitted FDR parameters (FDR number, bank name, amount, maturity date) against synthetic records in `MockBankRecord`.
- **Outcomes**: Returns structured outcome (`match`, `mismatch`, or `not_found`), field-by-field comparisons, and an explicit disclaimer banner: `SIMULATED — NOT BANK CONFIRMATION`.
- **Human In The Loop**: Unknown FDRs remain in `pending` review; mismatches are flagged as `discrepancy`. The adapter never silently approves unknown instruments. Officers make authoritative determinations with mandatory audit notes.
- **Adding / Modifying Mock Bank Records**: Edit `backend/app/db/seed.py` (under `# 9. Mock Bank Records`) or insert into `mock_bank_records` table using Alembic/SQL. Fictional examples:
  - `39482019482` (SBI) — exact match (₹1,50,00,000.00)
  - `PNB77492011` (PNB) — exact match (₹50,00,000.00)
  - `CAN88910244` (Canara Bank) — exact match (₹75,00,000.00)
  - `ICIC5501928` (ICICI Bank) — amount mismatch (submitted ₹45,00,000 vs bank ₹40,00,000)

### 1. Clone and configure

```bash
git clone <your-repo-url> fdr-portal
cd fdr-portal
cp .env.example .env        # fill in values (see Environment Variables)
```

### 2. Run with Docker (recommended)

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

### 3. Or run manually

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed          # loads demo institutions, users, FDRs, mock bank data
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

### 4. Supabase Auth & Database Setup (PostgreSQL with RLS)

To connect the application to Supabase:

1. **Create a Supabase Project**:
   - In your Supabase Dashboard, create a new project.
   - Obtain your Project URL, anon public key, service-role secret key, and PostgreSQL connection string.
2. **Apply Row Level Security (RLS) & Schema Migration**:
   - Open the Supabase **SQL Editor**.
   - Copy and execute the repeatable migration script:
     `
     backend/alembic/supabase_rls_setup.sql
     `
   - This script creates all required enums, tables, cryptographic audit triggers, and strict RLS policies ensuring that:
     - Institution users are strictly isolated to their own institution's records.
     - Officers and Admins have regulatory inspection and verification rights.
     - Role and institution self-escalation is blocked at the database trigger level.
3. **Configure Environment Variables**:
   - In ackend/.env:
     `ash
     DATABASE_URL=postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
     SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
     SUPABASE_ANON_KEY=[YOUR-ANON-PUBLIC-KEY]
     SUPABASE_SERVICE_KEY=[YOUR-SERVICE-ROLE-KEY] # Server-side only! Never expose to frontend
     SUPABASE_JWT_SECRET=[YOUR-SUPABASE-JWT-SECRET]
     `
   - In rontend/.env:
     `ash
     VITE_API_URL=http://localhost:8000
     VITE_SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
     VITE_SUPABASE_ANON_KEY=[YOUR-ANON-PUBLIC-KEY] # Public key only
     `
4. **Seed Demonstration Data (Safe & Non-Destructive)**:
   `ash
   cd backend
   python -m app.db.seed
   `

## 🔐 Environment Variables

See `.env.example`. Required values:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (Supabase) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Public key used by the frontend |
| `SUPABASE_SERVICE_KEY` | **Server-only** key; never expose to the frontend |
| `SUPABASE_JWT_SECRET` | Used by the backend to verify JWTs |
| `STORAGE_BUCKET` | Private bucket name (e.g. `fdr-documents`) |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) |
| `ENABLE_SIMULATED_DATE` | `true` in demo only; enables `/admin/simulate-date` |
| `VERIFIER_MODE` | `mock` (default) or `real` |
| `LLM_FALLBACK_ENABLED` | `false` by default; optional extraction fallback |
| `SMTP_*` / `RESEND_API_KEY` | Optional email notifications |
| `VITE_API_URL` | Frontend → backend URL |

> ⚠️ Never commit `.env`. Never use real bank or institution data in demo environments.

## 👥 Demo Accounts & Data

Created by `python -m app.db.seed`:

| Role | Email | Password | Purpose |
|---|---|---|---|
| Institution Custodian | `institution@demo.test` | `Demo@12345` | Upload and renew FDRs, request release |
| Vigilance Officer | `officer@demo.test` | `Demo@12345` | Review, verify, approve, resolve discrepancies |
| Sovereign Admin | `admin@demo.test` | `Demo@12345` | Manage users, workflow config, simulate date |

All passwords and data are **fictional, demo-only** values defined in the seed script. Bank responses come from a clearly labelled **SIMULATED** verifier. In production environments (`ENVIRONMENT=production`), demo login is automatically disabled.

## 🎬 Demo Walkthrough

1. **New FDR** — Log in as Institution (`institution@demo.test` / `Demo@12345`) → upload `sample-data/fdr_clean.pdf` → OCR prefills 9 fields → confirm and submit.
2. **Discrepancy** — Upload `sample-data/fdr_mismatch.pdf` → simulated bank returns a different amount → discrepancy flagged → Officer reviews and records resolution.
3. **Maturity alert** — Admin uses *Simulate Date* to jump forward → 30/15/7-day notifications appear in the bell and dashboard without releasing funds.
4. **Renewal** — Institution uploads a replacement FDR → linked to the previous one → Officer approves → history timeline shows both.
5. **Release** — Institution requests release → Officer moves it through review → approval → completed. The audit log shows every step.

After each scenario, watch the dashboard counters update.

## 🔌 API Overview

Interactive docs at `/docs`. Main groups:

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/change-password`, `GET /auth/me`, `POST /auth/demo-login` (dev only) |
| Institutions | `GET/POST /institutions`, `GET /institutions/{id}/fdrs` |
| FDRs | `POST /fdrs`, `GET /fdrs`, `GET /fdrs/{id}`, `GET /fdrs/documents/{id}/download` (signed URL or token) |
| OCR | `POST /fdrs/ocr` (9-field extraction + confidence + human review notice) |
| Verification | `POST /fdrs/{id}/verify`, `POST /fdrs/{id}/resolve-discrepancy` |
| Renewal | `POST /fdrs/{id}/renew`, `POST /renewals/{id}/approve` |
| Release | `POST /fdrs/{id}/release-request`, `POST /release/{id}/transition` |
| Dashboard | `GET /dashboard/summary`, `GET /dashboard/priority-cases`, `GET /dashboard/charts` |
| Reports | `GET /reports/export?type=` |
| Audit | `GET /fdrs/{id}/audit`, `GET /audit/verify-chain` |
| Admin (demo) | `POST /admin/simulate-date` (Admin-only, dev only) |

## 🗄️ Data Model

Core tables: `institutions`, `users`, `fdr_records`, `fdr_documents`, `verification_logs`, `release_requests`, `notifications`, `workflow_audit_logs`.

`fdr_records` carries three independent statuses:

- `instrument_status`: submitted · active · renewal_due · matured · renewed · released
- `verification_status`: pending · verified · discrepancy · rejected
- `workflow_status`: none · renewal_review · release_requested · under_review · approval_pending · approved · rejected · completed

Renewals are linked via `previous_fdr_id`. Full DDL is in [IMPLEMENTATION.md](./IMPLEMENTATION.md).

## 🛡️ Security & Compliance Design

- **Password-Based Authentication**: Secure login using PBKDF2-HMAC-SHA256 password hashing with salt; safe change password flow.
- **Strict Role-Based Access Control**: Evaluated on every request from database records, not trusting client-side tokens; full tenant isolation for institutions.
- **Production Readiness Gate**: Startup validator enforces production security (`ENVIRONMENT=production` fails safely if demo login or simulated date is enabled, or if default/weak keys are present).
- **Document Encryption at Rest**: AES-128-CBC / HMAC (Fernet) encryption at rest for all uploaded files using `DOCUMENT_ENCRYPTION_KEY`.
- **Private Document Access**: Expiring signed download tokens with timestamp validation, tenant-isolated authorization, and strict download checks.
- **Streaming Upload Security**: Enforces file size limits during chunked streaming, validates magic bytes (rejects renamed executables or spoofed MIME types), and sanitizes filenames.
- **Tamper-Evident Hash-Chained Audit Ledger**: Append-only SHA-256 chain where each audit entry links to the previous entry's hash, with verification endpoint `GET /audit/verify-chain`.
- **Scheduled Background Automation**: In-process background runner executes idempotent maturity checks; maturity milestone notifications (30/15/7d) never trigger automatic release.
- **Simulated Date Governance**: System date simulation is strictly restricted to Sovereign Admin in development environments; completely disabled in production.
- **Rate Limiting & Safe Logging**: Rate limits on authentication and OCR endpoints via `slowapi`; secrets, credentials, and raw document contents are never logged.

## 🧪 Testing

```bash
# Backend
cd backend && pytest -q

# Frontend lint + unit
cd frontend && npm run lint && npm test

# End-to-end (runs the 5 demo scenarios)
cd frontend && npx playwright test
```

Reported metrics come **only from the project's test set** (e.g., OCR field accuracy on sample documents, registration time with vs. without OCR, missing-field detection rate). No production-level improvement claims are made.

## 🗺️ Roadmap

**Hackathon MVP (this repo):** repository, OCR prefill, validation, mock verification, maturity alerts, renewal & release workflows, dashboard, Excel export, audit log.

**Future milestones (require external access/approvals):**

- Real bank verification APIs
- Integration with AICTE systems and government SSO (e.g., Keycloak-based)
- eSign / Digital Signature Certificate for approval orders
- Hosting on MeitY-empanelled / NIC infrastructure
- Celery + Redis, Temporal/Camunda for long-running approvals
- SMS / WhatsApp notifications
- OpenSearch, Prometheus + Grafana observability
- WCAG accessibility audit and security certification

## ⚠️ Limitations & Disclaimers

- Bank verification in this prototype is **simulated**; it is not connected to any real bank.
- Reminder intervals (30/15/7 days) and workflow stages are **configurable defaults**, not AICTE-prescribed timelines.
- OCR output is assistive and must be confirmed by a human; it does not prove a document is genuine.
- Dashboard figures in screenshots/docs are fictional examples.
- This is a hackathon prototype and has not undergone formal security certification.

## 👨‍💻 Team

| Name | Role |
|---|---|
| _Member 1_ | Frontend lead |
| _Member 2_ | Backend lead |
| _Member 3_ | Data / AI (OCR, validation, scheduler) |
| _Member 4_ | Full-stack / DevOps |

---

_Built for Smart India Hackathon 2026 — SIH26265._
