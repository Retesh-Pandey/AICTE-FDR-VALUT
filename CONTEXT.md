# CONTEXT.md — AICTE Smart FDR Lifecycle Management Portal

> This file is the project's working context for Antigravity. Keep it updated after every meaningful implementation phase. Record verified facts, not assumptions.

## 1. Project Identity

- **Project:** AICTE Smart FDR Lifecycle Management Portal
- **Problem Statement:** SIH26265 — Streamline of Security Deposit/FDR Portal
- **Goal:** Build a demonstrable 48-hour SIH MVP for managing institutional FDRs from submission through document processing, verification, maturity monitoring, renewal/replacement, authorized release, and audit history.

## 2. Reference Documents and Authority

Read these files before making significant changes:

1. `AICTE_Problem_Statement_Simplified.md` — business problem and expected outcome.
2. `README.md` — project overview, feature summary, stack, and high-level architecture.
3. `IMPLEMENTATION.md` — authoritative technical requirements, schema, API contracts, roles, state transitions, security, phases, and acceptance criteria.
4. `CONTEXT.md` — current verified progress and next action.

If other plans or blueprints exist, use them as supporting references. If documents conflict, document the conflict in `docs/DECISIONS.md`. Do not silently discard technical requirements.

## 3. Intended Technology Stack

Confirm actual workspace configuration before assuming a tool is installed.

- Frontend: React, Vite, TypeScript, Tailwind CSS; shadcn/ui and TanStack Query where appropriate.
- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic.
- Database: PostgreSQL, optionally Supabase-hosted.
- Document processing: Tesseract OCR, PyMuPDF, and OpenCV where appropriate.
- Scheduling: APScheduler or the implementation-specified equivalent.
- Reporting: pandas/openpyxl where required.
- Tests: pytest and suitable frontend tests.
- Deployment: follow the implementation plan and available environment.

## 4. User Roles

- **Institution:** Manage permitted institution/FDR records and submit requests.
- **Officer:** Review submissions, discrepancies, verification outcomes, and workflow requests.
- **Administrator:** Perform authorized administrative and final approval/completion actions.

All access control must be enforced on the backend. Hiding a frontend button is not authorization.

## 5. Core Lifecycle

1. Institution submits an FDR and supporting document.
2. System extracts available data and allows review/correction.
3. Backend validates fields and records discrepancies.
4. Verification is recorded using an authorized integration or clearly labelled simulated adapter.
5. Authorized officials review the record and its history.
6. System monitors maturity and relevant pending actions.
7. Renewal/replacement or release requests follow controlled workflows.
8. Important state changes are recorded in the required audit trail.

## 6. Non-Negotiable Rules

- OCR output is not proof of authenticity.
- A discrepancy is a review flag, not an automatic fraud verdict.
- Maturity does not automatically invalidate, release, or mark an FDR non-compliant.
- Never automatically release an FDR because a date passed or a request was submitted.
- Keep instrument status, verification status, and workflow status separate.
- Clearly label simulated bank responses and demo-only authentication.
- Validate inputs and uploads server-side; follow the specified file-size/type limits.
- Keep uploaded documents private.
- Never commit real secrets or credentials.
- Implement the full schema and workflows required by `IMPLEMENTATION.md`; do not simplify away required tables or approval stages.
- Audit records must be append-only and hash-chained as specified, with integrity verification.
- Keep audit writes transactionally consistent with associated state changes.
- Never claim a feature, integration, or test is working unless verified.

## 7. Strict Phase-Gate Workflow

Work one phase at a time:

1. State the phase objective and acceptance criteria.
2. Inspect relevant existing files.
3. Implement the current phase and required dependencies only.
4. Run relevant commands/tests and fix failures.
5. Report files changed, commands executed, results, limitations, and next steps.
6. Update this file and the build checklist with verified results.
7. Stop and wait for explicit approval before beginning the next phase.

Do not mark a requirement complete merely because code was generated. Require evidence from tests, a successful build, or a reproducible manual check.

## 8. Phase Plan

- **Phase 1:** Workspace inspection, architecture, configuration, setup, build plan.
- **Phase 2:** Complete database schema, models, migrations, validation schemas, demo seed data.
- **Phase 3:** Authentication, backend role enforcement, error handling, audit foundation.
- **Phase 4:** FDR submission, private uploads, OCR, editable extracted fields, validation.
- **Phase 5:** Dashboard, search/filter, FDR details, verification results, discrepancy review.
- **Phase 6:** Maturity monitoring, notifications, renewal and controlled release workflows.
- **Phase 7:** Reports/exports, audit-integrity verification, remaining required features.
- **Phase 8:** End-to-end tests, security checks, bug fixing, demo preparation, documentation.

Follow the exact acceptance criteria and dependencies in `IMPLEMENTATION.md`.

## 9. Current Progress — Update This Section

- **Current phase:** Phase 8 (Integration & Release-Readiness Review) Complete — ALL 8 PHASES VERIFIED.
- **Verified completed phases:**
  - **Phase 1:** Monorepo architecture, configuration, FastAPI app, base dependencies, Supabase/Demo JWT auth, role enforcement, and sovereign frontend.
  - **Phase 2:** Relational schema for all entities, Pydantic schemas, Alembic migrations to head (`d2b31e091f48`), comprehensive seed data across all 6 lifecycle statuses, check constraints, unique constraints, cascade deletes.
  - **Phase 3:** Standardized exception architecture, backend role authorization (`require_role`), institutional multi-tenant isolation (`verify_institution_access`), immutable audit trail inspection (`GET /fdrs/{id}/audit`), admin-only hash chain parity verification (`GET /audit/verify-chain`), and institutions management endpoints (`GET/POST /institutions`, `GET /institutions/{id}/fdrs`) with transactional audit logging.
  - **Phase 4:** FDR submission (`POST /fdrs`), private document storage (`StorageService`), server-side file type and size enforcement (<= 10MB, PDF/PNG/JPG only), assistive OCR extraction (`POST /fdrs/ocr`) with legal disclaimer, pure Indian financial parsers (`parse_amount` >= 25 unit test cases, `parse_date`, `find_fdr_number`, `match_bank`), rule-based validation engine with neutral wording ("needs review", never "fraud"), multi-tenant scoped querying (`GET /fdrs`), FDR details with signed URLs (`GET /fdrs/{id}`), authorized document streaming download (`GET /fdrs/documents/{id}/download`), and officer discrepancy resolution (`POST /fdrs/{id}/resolve-discrepancy`).
  - **Phase 5:** Dashboard, search/filter, FDR details, verification results, discrepancy review, live telemetry (`GET /dashboard/summary`), decoupled tri-part status display, loading/empty/error states.
  - **Phase 6:** Maturity monitoring pure engine (`run_maturity_check`), idempotent milestone notifications (30d, 15d, 7d, 0d), hackathon date simulation endpoint (`GET/POST /admin/simulate-date`), definitive 6-stage Release Workflow state machine (`RELEASE_WORKFLOW` and `RENEWAL_WORKFLOW`), atomic renewal replacement (`POST /renewals/{id}/approve` & `reject`), and frontend interactive steppers, date simulator modal, and live notification drawer.
  - **Phase 7:** Filtered reporting and Excel export (`GET /reports/data`, `GET /reports/export`) using pandas + openpyxl with formatted headers, Indian currency numbers, and Generation Metadata sheet; officer priority cases (`GET /dashboard/priority-cases`); portfolio distribution & bank concentration charts (`GET /dashboard/charts`); SHA-256 audit hash chain mathematical tamper detection (`test_audit_integrity_tamper.py`); audit immutability verification (rejection of mutation/deletion endpoints); frontend `/reports` and `/audit` pages.
  - **Phase 8:** Complete integration & release-readiness review against `IMPLEMENTATION.md`. Full 5-scenario E2E integration test suite (`test_e2e_scenarios.py`) verifying submission with OCR prefill, discrepancy resolution with mandatory notes, maturity date simulation with boundary notices, atomic renewal predecessor/successor linking, and controlled 6-stage release workflow with role-gated admin completion. Setup scripts (`scripts/reset_demo.ps1`, `scripts/reset_demo.sh`), comprehensive demonstration script (`docs/DEMO_SCRIPT.md`), measured performance metrics (`docs/METRICS.md`), and secret audit completed.
- **Last verified test/build results:**
  - Backend: Pytest **61/61 passed** in 13.95s across all 11 test suites.
  - Backend: Ruff lint 100% clean (`ruff check backend` -> All checks passed!).
  - Frontend: TypeScript `npm run typecheck` passed (0 errors); `npm run build` generated cleanly in 6.09s (`dist/index.html` 0.94 kB, `dist/assets/index-*.js` 401.03 kB, `dist/assets/index-*.css` 42.79 kB).
  - Database: Alembic migration head `d2b31e091f48` verified; `python -m app.db.seed` verified clean.
  - Security & Secrets: `.gitignore` protects `.env`, `uploads/`, `dist/`, `.venv/`. No real secrets or production API keys committed.
- **Phase 1 (Foundation & Design System):** ✅ COMPLETE
- **Phase 2 (Database Architecture & Safe Demo Seed):** ✅ COMPLETE
- **Phase 3 (Authentication, Authorization & Tamper-Evident Audit Foundation):** ✅ COMPLETE
- **Phase 4 (FDR Submission, OCR Processing & Discrepancy Engine):** ✅ COMPLETE
- **Phase 5 (Frontend Dashboard & FDR Management Screens):** ✅ COMPLETE
- **Phase 6 (Maturity Monitoring & Release/Renewal Workflow State Machine):** ✅ COMPLETE
- **Phase 7 (Reports/Exports & Audit-Integrity Verification):** ✅ COMPLETE
- **Phase 8 (End-to-End Tests, Security Checks & Release Readiness):** ✅ COMPLETE

- **Current blockers:** None. Ready for hackathon release demonstration.
- **Next action:** Present complete release-readiness review report to user.

## 10. Commands and Environment

- **Frontend dependencies:** `cmd /c npm install` (inside `frontend/`)
- **Frontend dev server:** `cmd /c npm run dev` (inside `frontend/`)
- **Frontend typecheck:** `cmd /c npm run typecheck` (inside `frontend/`)
- **Frontend production build:** `cmd /c npm run build` (inside `frontend/`)
- **Backend dependencies:** `.\.venv\Scripts\pip.exe install -r requirements.txt` (inside `backend/`)
- **Backend dev server:** `.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000` (inside `backend/`)
- **Backend linting:** `.\.venv\Scripts\ruff.exe check .` (inside `backend/`)
- **Database migrations:** `.\.venv\Scripts\alembic.exe upgrade head` (inside `backend/`)
- **Database seed:** `.\.venv\Scripts\python.exe -m app.db.seed` (inside `backend/`)
- **Backend automated tests:** `.\.venv\Scripts\pytest.exe -v` (inside `backend/`)

## 11. Decisions and Known Issues

- Complete architectural decisions documented in `docs/DECISIONS.md` (ADR-001 through ADR-006).
- Dual Authentication Architecture: Explicitly documented development demo login (`POST /auth/demo-login`) with pre-seeded accounts alongside Supabase HS256 JWT decoding. Development demo login is clearly isolated and labelled for hackathon evaluation and local testing.
- Assistive OCR Disclaimer: OCR output is strictly assistive for rapid data pre-filling; it is never treated as proof of document authenticity (`"disclaimer": "Assistive data entry only. Extraction does not prove document authenticity."`).
- Neutral Discrepancy Language: Validation discrepancy flags use strictly factual language ("needs review", "discrepancy detected") and never use accusatory terminology ("fraud", "fake", "forged").
- Institutional Scoping: Strictly enforced server-side. Institutions are forbidden from querying, submitting, or viewing any records outside their assigned `institution_id` (403 `CROSS_TENANT_FORBIDDEN`). Officers and Administrators hold cross-institutional oversight.
- Standardized Error Envelope: All errors conform strictly to `{"error": {"code": "...", "message": "...", "details": ...}}`.
- Transactional Audit Consistency: All state mutations (e.g. creating FDRs, resolving discrepancies, creating institutions) write to `workflow_audit_logs` in the same database transaction.
- Explicit Simulation Labeling: Bank verification queries and logs are clearly tagged `[SIMULATED]` in badges, logs, and tooltips to avoid confusion with live external CBS gateways.
- Tri-Part Decoupled Status Display: Instrument status (`active`, `renewal_due`, `matured`, `renewed`, `released`), Verification status (`verified`, `pending`, `discrepancy`, `rejected`), and Workflow status (`submitted`, `under_review`, `approved`, `release_requested`, `released`) are strictly decoupled across all views.

## 12. Update Log

- **2026-10-22 — Phase 5 Complete:**
  - **Files created/modified:** `backend/app/api/dashboard.py`, `backend/app/main.py`, `frontend/src/lib/api.ts`, `frontend/src/components/common/StatusBadges.tsx`, `frontend/src/features/dashboard/DashboardPage.tsx`, `frontend/src/features/fdr/FDRDetailPage.tsx`, `frontend/src/features/fdr/OCRIntakeStudio.tsx`, `frontend/src/app/router.tsx`.
  - **Backend Features:** Created `GET /dashboard/summary` telemetry endpoint returning live aggregations (`total_fdrs`, `active_fdrs`, `total_active_amount`, `expiring_30_days`, `pending_verification`, `flagged_discrepancies`, `matured_fdrs`, `recent_records`) automatically scoped to user role/institution. Mounted in `app/main.py`.
  - **Frontend Features:**
    - Connected `DashboardPage.tsx` to live backend telemetry (`api.getDashboardSummary()`) and paginated FDR records (`api.listFDRs()`).
    - Implemented real-time search (by FDR number, institution name, or bank name), filter by instrument status, filter by issuing bank, and refresh telemetry action.
    - Added comprehensive loading skeleton states, empty states (with reset filter CTA), error retry states, and success toasts.
    - Built comprehensive `FDRDetailPage.tsx` (`/fdrs/:id`) with tri-part decoupled status badges (`InstrumentBadge`, `VerificationBadge` with `[SIMULATED]` indicator, `WorkflowBadge`), deposit summary grid, document vault download links, simulated bank verification results table, Officer Discrepancy Resolution workbench (supporting `APPROVE`, `FLAG_DISCREPANCY`, `REJECT` with mandatory resolution audit notes), and cryptographic ledger audit trail.
    - Wired `OCRIntakeStudio.tsx` confidence indicators to live OCR extraction feedback.
  - **Verification:**
    - TypeScript compilation (`npm run typecheck`): 0 errors.
    - Production build (`npm run build`): Completed in 4.87s (`dist/index.html`, `dist/assets/index-*.js`, `dist/assets/index-*.css`).
    - Backend tests (`pytest`): 39/39 passing in 5.69s.
    - Code quality (`ruff check backend`): 100% clean.
  - **Status:** All Phase 5 requirements satisfied. Stopping for user review and approval before advancing to Phase 6.
- **2026-10-22 — Phase 6 Complete:**
  - **Files created/modified:**
    - `backend/app/services/workflow/config.py`: Definitive state transition maps `RELEASE_WORKFLOW` and `RENEWAL_WORKFLOW` defining exact stages (`release_requested` -> `under_review` -> `conditions_checked` -> `approval_pending` -> `approved` -> `completed` / `rejected`), allowed jumps, and role permissions.
    - `backend/app/services/workflow/machine.py`: Authoritative workflow state engine (`transition_release`, `transition_renewal`). Validates transitions, verifies caller permissions (officer vs admin), enforces mandatory remarks on rejection and approvals, writes immutable chained audit events, and ensures FDR `instrument_status` only becomes `released` when an authorized administrator transitions the request to `completed`.
    - `backend/app/services/jobs/maturity.py`: Pure idempotent maturity calculation engine (`run_maturity_check`). Evaluates 30d (`maturity_30`), 15d (`renewal_due` + `maturity_15`), 7d (`maturity_7`), and 0d (`matured`). Deduplicates notifications via unique key `(user_id, fdr_id, milestone)`. Invariant preserved: maturity alone never alters workflow status or releases an FDR. Includes simulated date provider (`set_simulated_date`, `get_effective_today`).
    - `backend/app/api/release.py`: Endpoints `POST /release/requests`, `GET /release/requests`, `GET /release/requests/{id}`, `POST /release/requests/{id}/transition`.
    - `backend/app/api/renewals.py`: Atomic renewal approvals (`POST /renewals/{id}/approve` & `POST /renewals/{id}/reject`).
    - `backend/app/api/fdrs.py`: Added renewal intake endpoint `POST /fdrs/{id}/renew` linking new FDRs to predecessor instruments.
    - `backend/app/api/notifications.py`: `GET /notifications` (scoped with unread badge counter), `POST /notifications/{id}/read`, `POST /notifications/read-all`.
    - `backend/app/api/admin.py`: `GET /admin/simulate-date`, `POST /admin/simulate-date` with transactional audit logging and automatic maturity evaluation trigger.
    - `backend/app/main.py`: Mounted release, renewal, notifications, and admin simulation routers.
    - `frontend/src/lib/api.ts`: Typed client integration for release workflow, renewals, notifications, and simulation controls.
    - `frontend/src/features/release/ReleaseWorkbench.tsx`: 6-stage interactive release workflow stepper, request queue, stage filtering, and role-gated transition triggers with mandatory remarks.
    - `frontend/src/features/fdr/FDRDetailPage.tsx`: Embedded "Request Release" modal, "Submit Renewal FDR" modal, renewal predecessor/successor history chain banner, and Officer Renewal Approval workbench.
    - `frontend/src/components/notifications/NotificationDrawer.tsx`: Live notification drawer with milestone urgency indicators and instant FDR navigation.
    - `frontend/src/components/simulation/DateSimulatorModal.tsx`: Hackathon judge date simulation modal with +15d, +30d, +65d fast-forwards and live evaluation telemetry.
    - `frontend/src/components/layout/Header.tsx`: Integrated notification bell counter and active date simulation status badge.
    - `backend/tests/test_workflow_state_machine.py`: Comprehensive test suite testing valid 6-stage lifecycle, invalid state skips (409), unauthorized caller rejections (403), mandatory remark validations, atomic renewal updates, and proof that maturity alone never releases an FDR.
    - `backend/tests/test_maturity_monitoring.py`: Boundary verification (31d, 30d, 15d, 7d, 0d), notification idempotency (running twice produces zero duplicates), and admin date simulation API.
  - **Verification:**
    - Backend Pytest: **48/48 passed** in 9.12s.
    - Backend Ruff lint: **All checks passed** (100% clean).
    - Frontend TypeScript (`npm run typecheck`): **0 errors**.
    - Frontend Build (`npm run build`): Completed in 5.47s without errors.
  - **Status:** All Phase 6 requirements verified. Halting execution for user review and approval before advancing to Phase 7.
- **2026-10-22 — Phase 7 Complete:**
  - **Files created/modified:**
    - `backend/app/services/reports.py`: OpenPyXL & Pandas styled Excel export engine with custom header palettes, auto-fit column widths, freeze-panes, Indian currency number formatting, and an authentic "Generation Metadata" audit sheet.
    - `backend/app/api/reports.py`: API router exposing `GET /reports/data` (filtered preview payload) and `GET /reports/export` (streamed `.xlsx` attachment). Role-restricted to Officers and Administrators.
    - `backend/app/api/dashboard.py`: Implemented `GET /dashboard/priority-cases` (categorizes regulatory urgency: discrepancies, pending renewals, open release requests, and deposits expiring in <= 30 days) and `GET /dashboard/charts` (live status distribution, upcoming 12-month maturity pipeline, and issuing bank concentration).
    - `backend/app/main.py`: Mounted `reports.router` at root and `/api/v1`.
    - `frontend/src/lib/api.ts`: Added types (`PriorityCaseItem`, `ChartTelemetryResponse`, `ReportSummaryResponse`) and methods (`getPriorityCases`, `getChartsData`, `getReportData`, `downloadReportExcel`).
    - `frontend/src/features/reports/ReportsPage.tsx`: Built regulatory reports view with filter tabs (`all`, `expiring`, `pending`, `renewed`, `released`), live principal volume indicators, data table preview, and one-click `.xlsx` download.
    - `frontend/src/features/audit/AuditLedgerPage.tsx`: Built sovereign audit ledger workbench featuring the "Verify Audit Integrity" trigger, real-time SHA-256 chain validation banner, telemetry metrics, and search/filter across audit blocks.
    - `frontend/src/features/dashboard/DashboardPage.tsx`: Integrated Priority Cases urgent review workbench and Portfolio Concentration analytics bars.
    - `frontend/src/components/layout/Sidebar.tsx`: Added `Reports & Exports` and `Hash Audit Ledger` navigation items.
    - `frontend/src/app/router.tsx`: Routed `/reports` to `ReportsPage` and `/audit` to `AuditLedgerPage`.
    - `backend/tests/test_reports_and_priority_cases.py`: Verified role-access control (institutions receive 403 `FORBIDDEN_ROLE`), validated Excel `.xlsx` sheet structures ("AICTE FDR Registry" and "Generation Metadata"), and tested priority cases and charts endpoints.
    - `backend/tests/test_audit_integrity_tamper.py`: Verified SHA-256 hash chain verification on pristine records, proved that modifying a record's remarks or status in the database causes immediate tamper detection with exact broken block identification, verified that corrupting `prev_hash` is detected, proved that no mutation/deletion endpoints exist for audit logs, and verified role permissions and tenant isolation.
  - **Verification:**
    - Backend Pytest: **56/56 passed** in 10.15s.
    - Backend Ruff lint: **All checks passed** (100% clean).
    - Frontend TypeScript (`npm run typecheck`): **0 errors**.
    - Frontend Build (`npm run build`): Completed in 5.63s without errors.
  - **Status:** All Phase 7 requirements satisfied and verified. Halting execution for user review and approval before advancing to Phase 8.
