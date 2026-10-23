# Architectural Decisions & Technical Records (ADR)

## ADR-001: Technology Stack & Execution Environment
- **Context:** The system runs on Windows with Python 3.14.6 and Node.js v24.19.0.
- **Decision:** Use FastAPI (Pydantic v2, SQLAlchemy 2.0, Alembic) for the backend and Vite + React 18 + TypeScript + Tailwind CSS for the frontend. On Windows, npm commands will be executed via `cmd /c npm` or `npm.cmd` to adhere to execution policy safety.
- **Status:** Accepted.

## ADR-002: Dual Database Strategy (Supabase PostgreSQL with Local SQLite Test Harness)
- **Context:** `IMPLEMENTATION.md` specifies PostgreSQL / Supabase for production and notes SQLite may be used for isolated local automated tests.
- **Decision:** The backend database engine supports standard PostgreSQL connection strings (e.g. Supabase pooler or direct URI via `DATABASE_URL`). For local automated test suites where an external network database may be unreachable or absent during offline CI runs, the connection logic automatically supports a local SQLite fallback for testing while preserving full UUID and JSON/JSONB compatibility via SQLAlchemy TypeDecorators. We never pretend SQLite is PostgreSQL; the active dialect is logged and displayed in system diagnostics.
- **Status:** Accepted.

## ADR-003: High-Fidelity Sovereign Sovereign UI/UX Design System
- **Context:** The user provided an authoritative reference screenshot of the "AICTE FDR VAULT / SIH-2026 SOVEREIGN" interface.
- **Decision:** Build a bespoke dark sovereign theme (`#07090d` background, `#0f131a` card surfaces, `#181f2b` borders, amber `#f59e0b` primary accents, glowing emerald `#10b981` verification indicators, cyber telemetry badges, dual-column intake studio with interactive bounding-box document radar, rule-based compliance engine, field precision audit editor, statutory vigilance officer declaration, and cryptographic minting CTA).
- **Status:** Accepted.

## ADR-004: Dual Auth Provider (Supabase JWT with Offline Demo Fallback)
- **Context:** In a 48-hour hackathon and grading evaluation, external Supabase network connectivity might be unconfigured or rate-limited.
- **Decision:** Implement Supabase Auth JWT verification against `SUPABASE_JWT_SECRET` when configured. Provide a clearly labelled offline demo authentication provider for pre-seeded demo accounts (`institution@demo.test`, `officer@demo.test`, `admin@demo.test`) that issues standard signed HS256 JWTs with identical role and claims structure.
- **Status:** Accepted.

## ADR-005: Three-State Decoupled Lifecycle Architecture
- **Context:** In accordance with non-negotiable safety rules, an FDR must never combine instrument validity, verification state, and workflow state into a single ambiguous enum.
- **Decision:** Maintain three separate enums in `fdr_records`:
  1. `instrument_status`: `submitted`, `active`, `renewal_due`, `matured`, `renewed`, `released`
  2. `verification_status`: `pending`, `verified`, `discrepancy`, `rejected`
  3. `workflow_status`: `none`, `renewal_review`, `release_requested`, `under_review`, `conditions_checked`, `approval_pending`, `approved`, `rejected`, `completed`
- **Status:** Accepted.

## ADR-006: Append-Only Cryptographic SHA-256 Hash Chained Audit Ledger
- **Context:** All critical regulatory state transitions and officer actions must have immutable, verifiable integrity.
- **Decision:** `workflow_audit_logs` implements SHA-256 hash chaining where each block includes `prev_hash`, actor metadata, action, entity IDs, status transition delta, canonical JSON payload, and ISO timestamp. Verification endpoint `GET /audit/verify-chain` verifies chain parity in O(N).
- **Status:** Accepted.
