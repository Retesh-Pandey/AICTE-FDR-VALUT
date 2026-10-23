# IMPLEMENTATION.md — Smart FDR Lifecycle Management Portal (SIH26265)

> **Audience:** developers and AI coding agents (e.g., Google Antigravity).
> **Purpose:** an executable, phase-by-phase build spec. Read **Section 0 first**, then execute phases in order. Do not skip acceptance checks.

---

## 0. Agent Operating Instructions

### 0.1 Ground rules (apply to every task)

1. **Read `README.md` and this file before writing code.** This file is the source of truth for schema, statuses, endpoints, and workflow.
2. **Build vertical slices**, not layers. After each phase the app must run end-to-end.
3. **After every task:** run the relevant linter/tests and confirm the task's acceptance criteria before moving on. Tick the checkbox.
4. **Never invent data about real banks or AICTE rules.** All bank responses come from the labelled **SIMULATED** verifier. All intervals/stages are *configurable defaults*.
5. **Hard safety invariants (never violate):**
   - ❌ No code path may automatically release, invalidate, or mark an FDR non-compliant based only on a date or a submitted request.
   - ❌ OCR/validation results are *flags for review*, never fraud verdicts. UI copy must say "needs review", not "fraud".
   - ✅ Every status change writes an audit log row in the same DB transaction.
   - ✅ Role checks happen **server-side** on every protected endpoint.
   - ✅ Secrets only via environment variables. Never commit `.env`.
   - ✅ Uploaded files: validate type (PDF/JPG/PNG) and size (≤ 10 MB), store in a **private** bucket, serve via signed URLs.
6. **Keep three statuses separate** on an FDR: `instrument_status`, `verification_status`, `workflow_status`.
7. **Commit small, with clear messages** (`feat(ocr): add amount parser for Indian formatting`).
8. **If a requirement is ambiguous**, choose the simplest option consistent with this file, document the assumption in `docs/DECISIONS.md`, and continue.

### 0.2 Suggested Antigravity workflow

- Use the **Planning** mode for each phase: paste the phase's *Agent Prompt* (found at the end of each phase) and let the agent produce a plan; review it against the tasks listed.
- Parallelize across agents only along **non-overlapping directories** (e.g., one agent on `backend/app/services/ocr/`, another on `frontend/src/features/dashboard/`).
- Use the browser/test agent to run the **Phase 8 E2E scenarios** against the running app and capture screenshots into `docs/screenshots/`.
- Keep a running checklist in this file: change `[ ]` to `[x]` as tasks complete.

### 0.3 Definition of "done" for any task

- Code compiles / lint passes (`ruff`, `eslint`, `tsc --noEmit`)
- Unit tests for new logic exist and pass
- Acceptance criteria met
- Audit logging and role checks present where applicable
- No secrets, no real data

---

## 1. Scope

### MVP (must build)
- Roles: **Institution**, **Officer**, **Admin**
- FDR upload → OCR prefill → human confirm → submit
- Rule-based validation + duplicate detection (number and document hash)
- Mock bank verification via swappable adapter
- Maturity scheduler with 30/15/7-day + maturity notifications
- Renewal linking with history timeline
- Release request workflow with approvals
- Officer dashboard: summary cards, priority cases, filters, charts
- Hash-chained audit log
- Excel export
- Demo date simulation

### Stretch (only if ahead of schedule)
- Email notifications (Resend/SMTP)
- Hindi/English toggle (i18next)
- Maturity calendar view
- Admin UI for workflow config
- PDF notice generation

### Out of scope (document as future work)
Real bank APIs · AICTE system integration · government SSO · eSign/DSC · production hosting & certification.

---

## 2. Repository Layout (create exactly this)

```
fdr-portal/
├── README.md
├── IMPLEMENTATION.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .github/workflows/ci.yml
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/{config.py,security.py,deps.py,logging.py}
│   │   ├── db/{base.py,session.py,seed.py,models/}
│   │   ├── schemas/
│   │   ├── api/{auth,institutions,fdrs,ocr,verification,renewals,release,dashboard,reports,admin,audit}.py
│   │   ├── services/
│   │   │   ├── ocr/{preprocess.py,extract.py,parsers.py}
│   │   │   ├── validation/{rules.py,engine.py}
│   │   │   ├── verification/{base.py,mock.py}
│   │   │   ├── workflow/{config.py,machine.py}
│   │   │   ├── audit.py
│   │   │   ├── notifications.py
│   │   │   └── reports.py
│   │   └── jobs/{scheduler.py,maturity.py}
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── Dockerfile
│   ├── vite.config.ts
│   └── src/
│       ├── app/{router.tsx,providers.tsx}
│       ├── components/{ui,layout,fdr,charts}/
│       ├── features/{auth,fdr,dashboard,renewal,release,notifications,audit}/
│       ├── lib/{api.ts,utils.ts,i18n.ts}
│       └── locales/{en.json,hi.json}
├── sample-data/
└── docs/{DECISIONS.md,DEMO_SCRIPT.md,screenshots/}
```

---

## 3. Environment

`.env.example`:

```env
# Database / Supabase
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/postgres
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=          # server only
SUPABASE_JWT_SECRET=
STORAGE_BUCKET=fdr-documents

# App
ALLOWED_ORIGINS=http://localhost:5173
ENABLE_SIMULATED_DATE=true     # demo only
VERIFIER_MODE=mock             # mock | real
LLM_FALLBACK_ENABLED=false
MAX_UPLOAD_MB=10

# Maturity reminder milestones (days) - configurable defaults
REMINDER_DAYS=30,15,7

# Optional
RESEND_API_KEY=
SMTP_HOST=
SMTP_USER=
SMTP_PASS=

# Frontend
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

`requirements.txt` (starting point):

```
fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings
sqlalchemy>=2
alembic
psycopg[binary]
python-jose[cryptography]
python-multipart
httpx
supabase
pymupdf
pytesseract
opencv-python-headless
pillow
numpy
pandas
openpyxl
apscheduler
slowapi
pytest
pytest-asyncio
ruff
```

---

## 4. Database Schema

> Implement as **SQLAlchemy models + Alembic migration**. The SQL below is the reference.

```sql
-- Enums
CREATE TYPE user_role AS ENUM ('institution','officer','admin');
CREATE TYPE instrument_status AS ENUM ('submitted','active','renewal_due','matured','renewed','released');
CREATE TYPE verification_status AS ENUM ('pending','verified','discrepancy','rejected');
CREATE TYPE workflow_status AS ENUM ('none','renewal_review','release_requested','under_review',
                                     'conditions_checked','approval_pending','approved','rejected','completed');
CREATE TYPE severity AS ENUM ('info','warning','critical');

CREATE TABLE institutions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aicte_id      TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  region        TEXT,
  address       TEXT,
  contact_email TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE users (
  id             UUID PRIMARY KEY,               -- equals Supabase auth user id
  email          TEXT UNIQUE NOT NULL,
  full_name      TEXT,
  role           user_role NOT NULL,
  institution_id UUID REFERENCES institutions(id),
  created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE fdr_records (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id      UUID NOT NULL REFERENCES institutions(id),
  fdr_number          TEXT NOT NULL,
  bank_name           TEXT NOT NULL,
  branch              TEXT,
  amount              NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  issue_date          DATE NOT NULL,
  maturity_date       DATE NOT NULL,
  lien_info           TEXT,
  previous_fdr_id     UUID REFERENCES fdr_records(id),   -- renewal chain
  is_current          BOOLEAN NOT NULL DEFAULT TRUE,     -- false once superseded
  instrument_status   instrument_status NOT NULL DEFAULT 'submitted',
  verification_status verification_status NOT NULL DEFAULT 'pending',
  workflow_status     workflow_status NOT NULL DEFAULT 'none',
  submitted_by        UUID REFERENCES users(id),
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now(),
  CHECK (maturity_date > issue_date),
  UNIQUE (bank_name, fdr_number)
);
CREATE INDEX idx_fdr_inst ON fdr_records(institution_id);
CREATE INDEX idx_fdr_maturity ON fdr_records(maturity_date) WHERE is_current;

CREATE TABLE fdr_documents (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fdr_id         UUID REFERENCES fdr_records(id) ON DELETE CASCADE,
  storage_path   TEXT NOT NULL,
  doc_type       TEXT NOT NULL DEFAULT 'fdr_receipt',  -- fdr_receipt | renewal | release_support
  sha256         TEXT NOT NULL,
  ocr_raw_text   TEXT,
  extracted_json JSONB,             -- {field: {value, confidence}}
  uploaded_by    UUID REFERENCES users(id),
  uploaded_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_doc_hash ON fdr_documents(sha256);

CREATE TABLE verification_logs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fdr_id           UUID NOT NULL REFERENCES fdr_records(id),
  source           TEXT NOT NULL,                 -- 'SIMULATED_BANK' | 'MANUAL' | real adapter id
  submitted_values JSONB NOT NULL,
  confirmed_values JSONB,
  discrepancies    JSONB,                         -- [{field, submitted, confirmed}]
  outcome          verification_status NOT NULL,
  resolved_by      UUID REFERENCES users(id),
  resolution_note  TEXT,
  created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE release_requests (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fdr_id           UUID NOT NULL REFERENCES fdr_records(id),
  requested_by     UUID NOT NULL REFERENCES users(id),
  reason           TEXT NOT NULL,
  stage            workflow_status NOT NULL DEFAULT 'release_requested',
  assigned_officer UUID REFERENCES users(id),
  remarks          TEXT,
  created_at       TIMESTAMPTZ DEFAULT now(),
  updated_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE notifications (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id),
  fdr_id     UUID REFERENCES fdr_records(id),
  type       TEXT NOT NULL,                 -- maturity_30|maturity_15|maturity_7|matured|discrepancy|workflow
  milestone  TEXT,                          -- used for de-duplication
  message    TEXT NOT NULL,
  read_at    TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, fdr_id, milestone)
);

-- Append-only, hash-chained audit log
CREATE TABLE workflow_audit_logs (
  id          BIGSERIAL PRIMARY KEY,
  actor_id    UUID,
  actor_role  TEXT,
  action      TEXT NOT NULL,
  entity      TEXT NOT NULL,               -- 'fdr' | 'release_request' | 'document' ...
  entity_id   UUID,
  old_status  TEXT,
  new_status  TEXT,
  remarks     TEXT,
  payload     JSONB,
  created_at  TIMESTAMPTZ DEFAULT now(),
  prev_hash   TEXT,
  row_hash    TEXT NOT NULL
);
REVOKE UPDATE, DELETE ON workflow_audit_logs FROM PUBLIC;
```

### 4.1 Hash chain (implement in `services/audit.py`)

```
row_hash = SHA256( prev_hash || actor_id || action || entity || entity_id
                   || old_status || new_status || remarks || canonical_json(payload) || created_at_iso )
```

- Fetch the latest `row_hash` with `SELECT ... ORDER BY id DESC LIMIT 1 FOR UPDATE` inside the same transaction to avoid forks.
- `GET /audit/verify-chain` recomputes the chain and returns `{valid: bool, broken_at: id|null}`.
- Add a DB trigger or revoke grants so rows cannot be updated or deleted.

### 4.2 Row-Level Security (Supabase)

- `fdr_records`, `fdr_documents`, `release_requests`: institutions can `SELECT` only rows where `institution_id = (SELECT institution_id FROM users WHERE id = auth.uid())`. Officers/admins can read all.
- Backend still enforces roles; RLS is defense-in-depth.

---

## 5. Workflow Configuration

`services/workflow/config.py` — single source of truth, no hard-coded transitions elsewhere.

```python
RELEASE_WORKFLOW = {
    "release_requested": {"under_review":       {"roles": ["officer"]}},
    "under_review":      {"conditions_checked": {"roles": ["officer"]},
                          "rejected":           {"roles": ["officer"]}},
    "conditions_checked":{"approval_pending":   {"roles": ["officer"]},
                          "rejected":           {"roles": ["officer"]}},
    "approval_pending":  {"approved":           {"roles": ["admin"]},
                          "rejected":           {"roles": ["admin"]}},
    "approved":          {"completed":          {"roles": ["admin"]}},
}
RENEWAL_WORKFLOW = {
    "renewal_review": {"approved": {"roles": ["officer"]},
                       "rejected": {"roles": ["officer"]}},
}
REMINDER_DEFAULTS = [30, 15, 7]   # configurable defaults, not AICTE-prescribed
```

`machine.py` exposes `transition(entity, to_state, actor, remarks)` which:
1. Validates the transition exists and `actor.role` is allowed (else HTTP 403/409).
2. Requires `remarks` for `rejected` and `approved`.
3. Updates state, then writes an audit row — **same transaction**.
4. On `completed` for release: set `instrument_status = 'released'` **only** because a human admin drove it there.

---

## 6. Phases

> Time guidance assumes a 48-hour hackathon with 4 people. Adjust as needed.

### Phase 1 — Foundation (≈ hours 0–8)

**Tasks**
- [x] Scaffold repo per Section 2; add `.gitignore`, `.env.example`, `docker-compose.yml` (backend, frontend; DB via Supabase)
- [x] Backend: FastAPI app, config via `pydantic-settings`, CORS, health endpoint `GET /health`
- [x] SQLAlchemy models + Alembic initial migration per Section 4
- [x] JWT verification dependency (Supabase JWT) and `require_role(*roles)` dependency
- [x] `GET /me` returning user + role + institution
- [x] Frontend: Vite + TS + Tailwind + shadcn/ui; router with role-aware layout; login page using Supabase Auth; API client attaching JWT
- [x] Seed script: 3 institutions, users for each role, 6–10 FDRs in various states, mock bank table
- [x] CI: GitHub Actions running ruff, pytest, eslint, tsc

**Acceptance**
- [x] `docker compose up` starts both apps; Swagger at `/docs`
- [x] Logging in as each demo role shows a different navigation
- [x] Calling a protected endpoint without a token → 401; wrong role → 403

**Agent Prompt**
> Read IMPLEMENTATION.md sections 0–5. Implement Phase 1 exactly. Create the repo layout, backend skeleton with Supabase JWT auth and role dependency, SQLAlchemy models and Alembic migration from the reference SQL, the seed script, and the frontend skeleton with login and role-based layout. Run lint/tests and report what passes.

---

### Phase 2 — FDR Repository (≈ hours 8–18)

**Backend tasks**
- [ ] `POST /fdrs` (multipart: fields + file). Validate file type/size; compute SHA-256; upload to private bucket; create `fdr_records` (`instrument_status=submitted`, `verification_status=pending`) + `fdr_documents`; audit `fdr.created`
- [ ] `GET /fdrs` with filters `status`, `verification_status`, `institution_id`, `bank`, `q` (fdr_number/institution name), `maturity_before`, pagination + sorting; institutions auto-scoped to their own
- [ ] `GET /fdrs/{id}` returning record, documents (signed URLs, 5-min expiry), verification logs, renewal chain, audit entries
- [ ] `GET/POST /institutions`, `GET /institutions/{id}/fdrs` (officer/admin)

**Frontend tasks**
- [ ] FDR submission form (React Hook Form + Zod) with file dropzone
- [ ] FDR list (TanStack Table): search, status filters, sort, pagination
- [ ] FDR detail page: summary, three status badges, documents, history timeline placeholder
- [ ] Officer dashboard v1: cards (Total, Active, Expiring ≤ 30 days, Pending verification) via `GET /dashboard/summary`

**Acceptance**
- Institution can submit and see only its own FDRs; officer sees all
- Duplicate `(bank, fdr_number)` returns a clear 409 message
- Uploading a `.exe` or > 10 MB file is rejected
- Dashboard numbers match the DB

**Agent Prompt**
> Implement Phase 2 from IMPLEMENTATION.md. Build FDR create/list/detail endpoints with file validation, hashing, private storage and audit logging, then the React form, table and detail page. Enforce institution scoping server-side. Add tests for scoping, duplicate handling and upload validation.

---

### Phase 3 — OCR + Validation + Verification (≈ hours 18–28)

**OCR pipeline (`services/ocr/`)**

1. `preprocess.py`: PDF → page images (PyMuPDF). If PDF has embedded text, use it directly. Else OpenCV: grayscale → denoise → adaptive threshold → deskew.
2. `extract.py`: run Tesseract (`--psm 6`, `eng`); optionally PaddleOCR fallback if overall confidence is low.
3. `parsers.py`: pure functions, heavily unit-tested:
   - `parse_amount("Rs. 5,00,000.00") -> Decimal("500000.00")` (Indian lakh/crore grouping, `₹`, `Rs.`, `INR`)
   - `parse_date()` supporting `DD/MM/YYYY`, `DD-MM-YYYY`, `DD-Mon-YYYY`, `DD Month YYYY`
   - `find_fdr_number()` keyed off labels like "FDR No", "Receipt No", "Deposit A/c"
   - `match_bank()` fuzzy match against a configurable bank list
4. Output shape:
```json
{
  "fdr_number": {"value": "FDR123456", "confidence": 0.92},
  "bank_name":  {"value": "State Bank of India", "confidence": 0.88},
  "amount":     {"value": "500000.00", "confidence": 0.95},
  "issue_date": {"value": "2026-01-15", "confidence": 0.9},
  "maturity_date": {"value": "2027-01-15", "confidence": 0.9}
}
```
5. `POST /fdrs/ocr` accepts a file, returns the JSON above. Does **not** create an FDR.
6. *(Optional, behind `LLM_FALLBACK_ENABLED`)* vision-LLM extraction returning strict JSON when regex confidence is low. Results are still shown for human confirmation. Do not send real/sensitive documents to external APIs.

**Validation engine (`services/validation/`)**

Each rule returns `{rule, severity, field, message}`:

| Rule | Severity |
|---|---|
| Required fields missing | critical |
| `maturity_date <= issue_date` | critical |
| Amount ≤ 0 or below configured minimum | critical |
| Duplicate `(bank, fdr_number)` | critical |
| Document SHA-256 already attached to another FDR | warning |
| OCR value ≠ user-entered value (per field) | warning |
| Issue date in the future | warning |
| Low OCR confidence (< 0.6) on any field | info |

Wording must be neutral: *"Amount differs between document and entry — needs review"*.

**Verification adapter (`services/verification/`)**

```python
class BankVerifier(Protocol):
    source: str
    def verify(self, fdr_number: str, bank_name: str) -> ConfirmedDetails | None: ...
```

- `MockBankVerifier` reads from a seeded `mock_bank_records` table, `source = "SIMULATED_BANK"`.
- `POST /fdrs/{id}/verify` (officer): runs the verifier, compares fields, writes `verification_logs`, sets `verification_status` to `verified` or `discrepancy`, creates a notification on discrepancy, audits.
- `POST /fdrs/{id}/resolve-discrepancy` (officer): requires a note; sets `verified` or `rejected`; audits.
- Factory chooses implementation from `VERIFIER_MODE`.

**Frontend tasks**
- [ ] Submission form: upload → call OCR → prefill fields with confidence badges; low-confidence fields highlighted; user can edit
- [ ] Show validation flags in a panel before submit
- [ ] Officer FDR detail: "Run verification" button, side-by-side *Submitted vs Bank-confirmed (SIMULATED)* table, resolve form
- [ ] Notification bell with unread count (poll or Supabase Realtime)

**Acceptance**
- `sample-data/fdr_clean.pdf` prefills ≥ 4 of 5 fields correctly
- `parse_amount` and `parse_date` pass ≥ 25 unit-test cases including edge formats
- Mock verifier returning a different amount produces a `discrepancy` and a notification
- UI labels the verification source as **SIMULATED**

**Agent Prompt**
> Implement Phase 3. Build the OCR preprocessing and extraction pipeline with pure, unit-tested parsers (Indian number formats, multiple date formats), the rule-based validation engine with neutral wording, and the BankVerifier protocol with a clearly-labelled mock. Wire prefill, flags and the discrepancy review UI. Create 4 sample documents in sample-data/ (clean PDF, low-quality scan, amount-mismatch case, duplicate-number case).

---

### Phase 4 — Maturity Monitoring (≈ hours 24–30, overlaps Phase 3)

**Tasks**
- [ ] `jobs/maturity.py::run_maturity_check(today: date)` — a **pure function** taking the date as a parameter
- [ ] `jobs/scheduler.py`: APScheduler daily at 02:00 calling `run_maturity_check(effective_today())`
- [ ] `effective_today()` returns the real date unless a simulated offset is set (only when `ENABLE_SIMULATED_DATE=true`)
- [ ] `POST /admin/simulate-date` (admin) sets/clears the offset and immediately triggers a run; audit every use
- [ ] Notification de-duplication via `UNIQUE (user_id, fdr_id, milestone)`

**Job logic** for each current FDR where `instrument_status IN ('active','renewal_due')`:

| Condition | Action |
|---|---|
| `days_left == 30` (or within 30 and no 30-day notice sent) | Notify institution + officers (`maturity_30`) |
| ≤ 15 | Check whether a renewal exists (`previous_fdr_id` pointing here). If none, notify "renewal not received"; set `instrument_status = renewal_due` |
| ≤ 7 | Escalate to officers/admin (`maturity_7`) |
| `maturity_date <= today` | Set `instrument_status = matured`, notify "review required" (`matured`) |

> The job **only flags and notifies**. It must never release, invalidate, or alter verification/workflow statuses.

**Dashboard additions**
- [ ] `GET /dashboard/priority-cases`: ranked list — matured, then ≤ 7 days, then discrepancies, then pending verification > N days
- [ ] Charts: FDRs by status (donut), maturities by month (bar), amount by bank (bar)

**Acceptance**
- Running the job twice on the same date creates no duplicate notifications
- Simulating +25 days produces the correct milestone notifications for seeded FDRs
- Unit tests cover 31, 30, 16, 15, 8, 7, 1, 0, −1 days-left boundaries

**Agent Prompt**
> Implement Phase 4. Write run_maturity_check as a pure function with a date parameter, idempotent notifications, the simulated date endpoint guarded by an env flag, and boundary-value unit tests. Add priority-cases and chart endpoints and the dashboard charts. The job must never change release or verification state.

---

### Phase 5 — Renewal & Release Workflows (≈ hours 28–38)

**Renewal**
- [ ] `POST /fdrs/{id}/renew` (institution): new FDR fields + document, `previous_fdr_id = id`, new record `instrument_status=submitted`, `workflow_status=renewal_review`; runs OCR/validation/verification as in Phase 3; compares key fields (institution, amount) with the previous FDR and flags differences
- [ ] `POST /renewals/{id}/approve` (officer; remarks required): new record → `active`; old record → `instrument_status=renewed`, `is_current=false`; audit both
- [ ] Reject path keeps old FDR unchanged
- [ ] Frontend: renewal form from FDR detail; **timeline component** showing the chain old → new with dates, amounts, status

**Release**
- [ ] `POST /fdrs/{id}/release-request` (institution): creates `release_requests` row, sets FDR `workflow_status=release_requested`, notifies officers
- [ ] `POST /release/{id}/transition` body `{to_stage, remarks}` using `workflow/machine.py`
- [ ] Officer inbox: list of requests by stage with assigned officer
- [ ] Stage stepper UI showing the current stage, actor, remarks, timestamps
- [ ] On `completed`: set FDR `instrument_status=released` (admin-driven only)
- [ ] Block release request if there is an open renewal review (return a clear message)

**Acceptance**
- Invalid transitions return 409; wrong role returns 403
- Every transition produces an audit row with actor, old/new status, remarks
- Renewal approval updates both records atomically (transaction test)
- No endpoint can set `released` without passing through the state machine

**Agent Prompt**
> Implement Phase 5 using only the transition tables in workflow/config.py. Build renewal linking with atomic updates and the history timeline, and the release request flow with role-checked transitions and audit entries. Add tests for invalid transitions, role enforcement, and transactional integrity.

---

### Phase 6 — Reports, Audit UI, Polish (≈ hours 34–42)

**Tasks**
- [ ] `GET /reports/export?type=expiring|pending|renewed|released|all` → `.xlsx` (pandas + openpyxl) with formatted headers, Indian number format for amounts, and a "Generated on / by" sheet
- [ ] `GET /fdrs/{id}/audit` and an Audit tab on FDR detail
- [ ] `GET /audit/verify-chain` and an admin "Verify audit integrity" button showing ✅ / ❌
- [ ] Empty, loading, and error states on every page; toasts for actions
- [ ] Accessibility pass: labels, focus order, contrast, keyboard navigation
- [ ] *(Stretch)* i18next with `en.json` / `hi.json` for navigation, dashboard, and status labels
- [ ] *(Stretch)* Email notifications via Resend/SMTP

**Acceptance**
- Excel opens cleanly with correct filters applied
- Tampering with an audit row in the DB makes `verify-chain` report the broken id

---

### Phase 7 — Hardening (≈ hours 38–44)

- [ ] Rate limiting (`slowapi`) on upload/OCR/verify endpoints
- [ ] Input validation review; consistent error format `{error: {code, message, details}}`
- [ ] Verify RLS policies and that signed URLs expire
- [ ] Remove any debug endpoints from production config (`ENABLE_SIMULATED_DATE=false` in prod unless demoing)
- [ ] Structured logging, request IDs, optional Sentry
- [ ] Review: grep for any code path that sets `released`, `non-compliant`, or auto-approves

**Feature freeze at hour 44.** Only bug fixes afterward.

---

### Phase 8 — Testing, Deployment, Demo (≈ hours 40–48)

**Tests**
- Unit: parsers, validators, workflow transitions, maturity boundaries, audit hash
- API: scoping, role enforcement, upload validation, transactional renewal
- E2E (Playwright), one spec per demo scenario:
  1. New FDR with OCR prefill
  2. Discrepancy flag and resolution
  3. Date simulation → notifications → dashboard change
  4. Renewal with history timeline
  5. Release through approval with audit log
- Measure on your sample set and record in `docs/METRICS.md`: OCR field accuracy, registration time with/without OCR, missing-field detection rate, manual steps removed. **Report only measured numbers.**

**Deployment**
- [ ] Frontend → Vercel (set `VITE_*` variables)
- [ ] Backend → Render with Tesseract installed (use the Dockerfile: `apt-get install -y tesseract-ocr`)
- [ ] Run migrations + seed against the demo database
- [ ] Add a `scripts/reset_demo.sh` that restores seed data in one command
- [ ] Keep-alive ping before the demo (free-tier cold starts)

**Demo prep**
- [ ] `docs/DEMO_SCRIPT.md` with exact clicks and expected results
- [ ] Record a backup demo video
- [ ] Rehearse twice; test on venue Wi-Fi/hotspot

**Agent Prompt**
> Write Playwright specs for the five demo scenarios using the seeded data and sample documents, run them against the local stack, save screenshots to docs/screenshots/, and write docs/DEMO_SCRIPT.md from the passing flows. Then generate docs/METRICS.md from measured results only.

---

## 7. API Contract (summary)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/health` | public | |
| GET | `/me` | any | user, role, institution |
| GET/POST | `/institutions` | officer, admin | |
| GET | `/institutions/{id}/fdrs` | officer, admin | |
| POST | `/fdrs/ocr` | institution, officer | returns extraction only |
| POST | `/fdrs` | institution | multipart |
| GET | `/fdrs` | any (scoped) | filters, pagination |
| GET | `/fdrs/{id}` | any (scoped) | with history |
| POST | `/fdrs/{id}/verify` | officer | uses `BankVerifier` |
| POST | `/fdrs/{id}/resolve-discrepancy` | officer | note required |
| POST | `/fdrs/{id}/renew` | institution | |
| POST | `/renewals/{id}/approve` | officer | remarks required |
| POST | `/fdrs/{id}/release-request` | institution | |
| POST | `/release/{id}/transition` | officer, admin | per workflow config |
| GET | `/dashboard/summary` | officer, admin | |
| GET | `/dashboard/priority-cases` | officer, admin | |
| GET | `/notifications` · POST `/notifications/{id}/read` | any | |
| GET | `/reports/export` | officer, admin | xlsx |
| GET | `/fdrs/{id}/audit` | officer, admin (institution: own) | |
| GET | `/audit/verify-chain` | admin | |
| POST | `/admin/simulate-date` | admin | env-gated |

**Error format:** `{"error": {"code": "INVALID_TRANSITION", "message": "...", "details": {...}}}`

---

## 8. Frontend Pages

| Route | Role | Content |
|---|---|---|
| `/login` | public | Supabase Auth |
| `/dashboard` | officer, admin | cards, priority cases, charts |
| `/fdrs` | all (scoped) | searchable table + filters |
| `/fdrs/new` | institution | upload → OCR prefill → flags → submit |
| `/fdrs/:id` | all (scoped) | tabs: Overview · Documents · Verification · History · Audit |
| `/fdrs/:id/renew` | institution | renewal form |
| `/release` | officer, admin | request inbox + stage stepper |
| `/institutions` | officer, admin | list and detail |
| `/reports` | officer, admin | export buttons |
| `/admin` | admin | simulate date, audit integrity check |

**UI copy rules:** use "needs review", "discrepancy", "flagged for review". Never "fraud", "fake", or "invalid" for automated flags. Label simulated data **SIMULATED** in a visible badge.

---

## 9. Sample Data Checklist (`sample-data/`)

- [ ] `fdr_clean.pdf` — digitally generated, all fields legible
- [ ] `fdr_scan_lowquality.jpg` — slightly rotated, noisy scan
- [ ] `fdr_mismatch.pdf` — amount differs from the mock bank record
- [ ] `fdr_duplicate.pdf` — same FDR number as an existing record
- [ ] `fdr_renewal.pdf` — replacement for a seeded FDR
- [ ] `mock_bank_records.json` — fictional confirmed values keyed by `(bank, fdr_number)`

Use fictional institutions, numbers, and names only.

---

## 10. Risk Register

| Risk | Mitigation |
|---|---|
| OCR inaccurate on poor scans | OpenCV preprocessing, editable prefill, confidence flags, early testing on varied samples |
| Free-tier cold starts | Keep-alive ping, local fallback, backup video |
| Scope creep | Stretch list is frozen until Phase 7 passes; feature freeze at hour 44 |
| Audit log forks under concurrency | `FOR UPDATE` on last row inside the transaction |
| Demo data drift | `reset_demo.sh`, seeded deterministic data |
| Misleading claims | Report only measured metrics; label simulated components |

---

## 11. Final Definition of Done

- [ ] All 5 demo scenarios pass on the deployed URL without manual DB edits
- [ ] Three roles work with server-side enforcement; institutions cannot see others' FDRs
- [ ] Every status change has an audit row; `verify-chain` returns valid
- [ ] No code path auto-releases or auto-invalidates an FDR
- [ ] Excel export is correct
- [ ] CI green (ruff, pytest, eslint, tsc, Playwright)
- [ ] README, DEMO_SCRIPT, METRICS, and DECISIONS docs complete
- [ ] "Future work" slide lists: real bank APIs, AICTE/SSO integration, eSign, compliant hosting, security certification
