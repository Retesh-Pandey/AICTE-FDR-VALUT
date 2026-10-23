# BUILD_PLAN.md — AICTE Smart FDR Lifecycle Management Portal

## Execution Strategy: Strict Phase-Gated MVP Delivery

This plan outlines the 8 phased deliverables specified in `IMPLEMENTATION.md` and user instructions. Each phase must satisfy all acceptance criteria and pass tests before proceeding to the subsequent phase.

---

### Phase 1: Workspace Inspection, Architecture, Repository Structure, Configuration, and Setup
- **Objective:** Establish the clean monorepo architecture, environment configurations, base dependencies, backend FastAPI service with health check and config, SQLAlchemy models & Alembic scaffolding, Supabase/Demo JWT authentication dependencies with role gating, seed script structure, and Vite + React + TypeScript + Tailwind CSS sovereign frontend scaffolding with role routing and navigation.
- **Dependencies:** None.
- **Acceptance Criteria:**
  1. Monorepo folder layout matches Section 2 of `IMPLEMENTATION.md`.
  2. `.env.example`, `.gitignore`, `docker-compose.yml`, and CI workflow configured.
  3. Backend FastAPI app boots, exposes `GET /health` and `GET /me`.
  4. Role dependency (`require_role`) rejects unauthorized roles with 403 and unauthenticated requests with 401.
  5. SQLAlchemy models matching the complete schema from Section 4 of `IMPLEMENTATION.md`.
  6. Frontend builds cleanly (`npm run build`), loads high-fidelity sovereign AICTE FDR Vault theme, and supports login & role-aware navigation.
  7. Seed script populates demo institutions, users across all 3 roles, sample FDRs, and mock bank entries.

---

### Phase 2: Complete Database Models, Migrations, Validation Schemas, Seed Data, and FDR Repository
- **Objective:** Implement complete database migration, Pydantic schemas, private document storage handler, multipart FDR submission (`POST /fdrs`), scoped query filtering (`GET /fdrs`), and FDR detail view (`GET /fdrs/{id}`).
- **Dependencies:** Phase 1 complete.
- **Acceptance Criteria:**
  1. Alembic migrations run cleanly against the configured database.
  2. Institutions are strictly scoped to their own records; officers/admins query across all institutions.
  3. SHA-256 duplicate document detection and `(bank_name, fdr_number)` unique constraints enforced.
  4. File upload size limit (≤ 10 MB) and extension restrictions (PDF, PNG, JPG) strictly enforced server-side.
  5. Initial audit row written on FDR creation inside the same database transaction.

---

### Phase 3: Intelligent OCR Ingestion, Validation Rules Engine, and Simulated Bank Verification
- **Objective:** Build OCR preprocessing and extraction pipeline, Indian financial currency and date parsers, rule-based validation engine with neutral flagging, and pluggable `BankVerifier` protocol with simulated bank verification.
- **Dependencies:** Phase 2 complete.
- **Acceptance Criteria:**
  1. `POST /fdrs/ocr` extracts text, parses Indian amounts, dates, FDR numbers, and bank entities with confidence metrics.
  2. Validation engine evaluates critical and warning rules without fraud accusations (neutral "needs review" language).
  3. `POST /fdrs/{id}/verify` and `POST /fdrs/{id}/resolve-discrepancy` functional with audit trail.
  4. Dual-column sovereign OCR Intake Studio matching reference design with bounding boxes, precision audit, and declaration attestation.

---

### Phase 4: Maturity Radar, Proactive Notifications, and Simulated Calendar Date Engine
- **Objective:** Implement scheduled maturity monitoring jobs (30, 15, and 7-day milestones + matured status flagging) using APScheduler, idempotent notification storage, and demo date simulation endpoint (`POST /admin/simulate-date`).
- **Dependencies:** Phase 3 complete.
- **Acceptance Criteria:**
  1. `run_maturity_check(today: date)` is a pure, idempotent function.
  2. Notifications de-duplicated by `(user_id, fdr_id, milestone)`.
  3. Simulating date forward triggers correct milestone notifications and priority case ranking.
  4. Matured instruments flagged for review without premature or automated release.

---

### Phase 5: Renewal & Controlled Release State Machines with Role Governance
- **Objective:** Implement renewal linking with full ancestor chain traceability, and the multi-stage release request approval state machine defined in `services/workflow/config.py`.
- **Dependencies:** Phase 4 complete.
- **Acceptance Criteria:**
  1. `POST /fdrs/{id}/renew` links new FDR to previous FDR and sets `workflow_status=renewal_review`.
  2. Officer approval atomically transitions old FDR to `renewed` and new FDR to `active`.
  3. Release request progresses strictly through defined stages (`release_requested` → `under_review` → `conditions_checked` → `approval_pending` → `approved` → `completed`).
  4. Terminal `completed` state setting `instrument_status=released` requires admin role; no shortcut bypass exists.

---

### Phase 6: Reporting, Cryptographic Audit Ledger Integrity Verification, and UI Polish
- **Objective:** Implement Excel reporting export (`GET /reports/export`), audit trail inspection (`GET /fdrs/{id}/audit`), and cryptographic hash-chain parity validation (`GET /audit/verify-chain`).
- **Dependencies:** Phase 5 complete.
- **Acceptance Criteria:**
  1. Excel export generates valid `.xlsx` with formatted sheets and Indian currency notation.
  2. Hash-chain recomputation detects valid chain and pinpoints tampered block if any record modified.
  3. UI includes loading, error, empty states, toasts, and bilingual English/Hindi toggle support.

---

### Phase 7: Security Hardening, Rate Limiting, and Guardrails
- **Objective:** Add rate limiting via SlowAPI, review security headers and CORS, verify private bucket signed URL expiry, and conduct comprehensive code audit.
- **Dependencies:** Phase 6 complete.
- **Acceptance Criteria:**
  1. Rate limiting on sensitive endpoints.
  2. Zero auto-release loopholes.
  3. Comprehensive error responses conforming to standard `{error: {code, message, details}}`.

---

### Phase 8: End-to-End Testing, Demo Data Scripting, Deployment Readiness, and Documentation
- **Objective:** Execute full automated test suite (backend pytest, frontend build, Playwright/E2E scenarios), prepare sample test documents, generate demo script and walkthrough guide.
- **Dependencies:** Phase 7 complete.
- **Acceptance Criteria:**
  1. All automated tests passing.
  2. Sample FDR documents ready in `sample-data/`.
  3. `docs/DEMO_SCRIPT.md` documented with step-by-step click-through for judges.
