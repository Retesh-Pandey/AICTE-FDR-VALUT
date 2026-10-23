# AICTE Smart FDR Lifecycle Management Portal — Hackathon Demo Script

## 1. System Setup & Run Commands

### Prerequisites
- Python 3.11+ (Python 3.14.6 verified)
- Node.js 18+ (Node.js 20+ verified)
- SQLite (default local) or PostgreSQL / Supabase

### Backend Setup & Launch
```bash
# Navigate to backend
cd backend

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Run database migrations to head
alembic upgrade head

# Seed initial safe demonstration dataset (institutions, users, sample FDRs, audit genesis)
python -m app.db.seed

# Start FastAPI application server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Interactive API Docs (Swagger): `http://127.0.0.1:8000/docs`
- Health Endpoint: `http://127.0.0.1:8000/health`

### Frontend Setup & Launch
```bash
# Navigate to frontend
cd frontend

# Install dependencies (if not already installed)
npm install

# Start Vite development server
npm run dev
```
- Portal Web App: `http://localhost:5173`

---

## 2. Seeded Demo Accounts (Role-Based Access)

All accounts are pre-seeded with safe local development credentials.

| Role | Email | Password | Display Name / Organization | Scope & Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **Institution** | `institution@demo.test` | Any / 1-Click | Dr. R.K. Sharma (Apex Institute of Technology) | Manage own FDRs, submit deposits, upload receipts, request renewals, submit release requests. Cross-tenant isolated. |
| **AICTE Officer** | `officer@demo.test` | Any / 1-Click | P.K. Mathur, IRS (Regional Vigilance Officer) | View all institutional FDRs, review OCR discrepancies, verify documents, advance release requests up to `approval_pending`, approve renewals. |
| **AICTE Admin** | `admin@demo.test` | Any / 1-Click | Member Secretary Bureau (AICTE Executive Admin) | Full council authority: final release executive approval (`approved`), statutory lien discharge (`completed`), date simulation controls, audit tamper verification. |

---

## 3. Five-Step Demonstration Sequence

### Workflow 1: Assistive FDR Submission & Validation (Institution Role)
1. **Login**: Authenticate as `institution@demo.test` using Quick Switch Demo Login button ("Institution Custodian").
2. **Navigate**: Click **"New FDR Submission"** on the institutional dashboard.
3. **Upload**: Select `sample-data/fdr_samples/sample_fdr_sbi.pdf` (or any PDF receipt).
4. **Assistive OCR**: Observe that the portal extracts Bank Name (`State Bank of India`), Amount (`₹25,00,000`), FDR Number, and Maturity Date into the form with an explicit **"Assistive OCR Extraction — Please Verify"** badge.
5. **Human Review**: Institutional principal reviews the extracted fields, enters the required AICTE Lien Clause (`Lien in favor of Member Secretary, AICTE New Delhi`), and clicks **"Submit Deposit"**.
6. **Result**: The FDR is created with `instrument_status = submitted`, `verification_status = pending`, and file hash SHA-256 is recorded.

### Workflow 2: Discrepancy Review & Authoritative Officer Resolution (Officer Role)
1. **Login**: Switch to `officer@demo.test` (Click "AICTE Vigilance Officer" demo button).
2. **Filter**: On the Council FDR Ledger, click the **"Discrepancy"** filter chip.
3. **Inspect**: Open FDR record `FDR-CAN-2024-991` (Canara Bank). Notice the discrepancy card explaining: *"Extracted bank differs from submitted bank"*.
4. **Authoritative Resolution**: Click **"Resolve Discrepancy"**.
   - Attempt to resolve without comments -> system enforces mandatory minimum 5-character statutory justification.
   - Enter remark: `Physical bank confirmation letter verified under reference CAN/AICTE/2026/894. Discrepancy cleared.`
   - Select Outcome: **"Verified"**. Click **"Confirm Resolution"**.
5. **Result**: Status transitions immediately to `verification_status = verified`. The cryptographic audit ledger logs an immutable entry with actor ID and justification.

### Workflow 3: Fast-Forward Maturity Simulation & Multi-Tier Notifications (Admin Role)
1. **Login**: Switch to `admin@demo.test` (Click "Member Secretary AICTE" demo button).
2. **Access Control**: Open the **"Maturity Time Machine"** banner at the top of the screen (visible only to Officer/Admin roles).
3. **Boundary Simulation**:
   - Fast-forward date by **+30 days**: The maturity engine runs idempotently. FDR `FDR-HDFC-2023-004` enters 30-day window; automated notification is dispatched.
   - Fast-forward date to **Maturity Date (+365 days)**: FDR transitions from `active` -> `matured`.
4. **Critical Invariant Verification**: Verify that even though the FDR is `matured`, its `workflow_status` is **NOT** released and lien remains intact. **Maturity alone NEVER releases an FDR.**
5. **Reset**: Click **"Reset Time Machine"** to return to real-world live date.

### Workflow 4: Renewal Replacement Linking & Atomic Activation (Institution + Officer)
1. **Login**: Switch to `institution@demo.test` ("Institution Custodian").
2. **Select Maturing FDR**: Find an active deposit maturing soon and click **"Submit Renewal"**.
3. **Form Pre-fill**: Notice predecessor FDR ID is locked and linked. Upload the renewal certificate PDF with extended maturity date.
4. **Submit**: Submits renewal with `workflow_status = renewal_pending`.
5. **Officer Approval**: Switch to `officer@demo.test`. Locate the renewal submission under **"Renewal Queue"**.
6. **Atomic Approval**: Click **"Approve Renewal"** with remark `Extension approved with continuous lien`.
7. **Result**: Predecessor FDR atomically transitions to `instrument_status = renewed` (`is_current = false`), and successor FDR transitions to `instrument_status = active` (`is_current = true`) in a single database transaction.

### Workflow 5: Controlled 6-Stage Release Workflow & Lien Discharge (Institution + Officer + Admin)
1. **Step 1 (Institution Request)**: Login as institution (`institution@demo.test`). Click **"Request Release"** on a matured deposit. Input justification: `5-year mandatory deposit tenure fulfilled. Council approval grant AICTE-2021-098.` Status becomes `release_requested`.
2. **Step 2 (Officer Review)**: Login as Officer (`officer@demo.test`). Transition stage to `under_review` with remarks: `Started inspection of regulatory compliance history.`
3. **Step 3 (Conditions Check)**: Officer checks compliance checklist (no student grievances, no pending penalties) and advances to `conditions_checked`.
4. **Step 4 (Forward to Admin)**: Officer advances stage to `approval_pending` with remarks: `All conditions satisfied. Recommended for Member Secretary release.`
5. **Role Boundary Check**: Officer attempts to approve -> system blocks with `403 Forbidden` (`Only AICTE Executive Admin may grant final release approval`).
6. **Step 5 (Admin Approval)**: Login as Admin (`admin@demo.test`). Click **"Executive Approve"** with statutory approval notes. Stage becomes `approved`.
7. **Step 6 (Discharge Completion)**: Admin clicks **"Discharge & Complete"**.
8. **Final State**: FDR `instrument_status` becomes `released`, `workflow_status` becomes `completed`, release authorization certificate is generated, and final audit hash is written to the chain.

---

## 4. Environment Variables Reference

| Variable | Description | Default (Local Demo) | Production Recommendation |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./fdr_vault.db` | Supabase Postgres: `postgresql+psycopg://...` |
| `SUPABASE_URL` | Supabase project URL | `https://demo.supabase.co` | Actual Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase public anonymous key | `demo-anon-key` | Actual Supabase client anon key |
| `SUPABASE_SERVICE_KEY` | Server-side elevated key | `demo-service-key` | Server environment secret only (never in frontend) |
| `STORAGE_BUCKET` | Supabase storage bucket name | `fdr-documents` | Private Supabase bucket |
| `ENABLE_SIMULATED_DATE`| Enable date time machine | `true` | `false` in production deployment |
| `VERIFIER_MODE` | Bank verification backend | `mock` | `real` with scheduled SFTP/API banking integration |
| `LLM_FALLBACK_ENABLED` | AI extraction fallback | `false` | `true` if Gemini / OpenAI API key configured |
| `MAX_UPLOAD_MB` | File size limit | `10` | `10` to `25` MB |
| `VITE_API_URL` | Frontend API backend origin | `http://localhost:8000` | Backend production domain |

---

## 5. Known Limitations & Hackathon Trade-offs

1. **OCR Dependencies**: Built with robust heuristic fallback (`pypdf` extraction + regex tokenizers). If Tesseract / Poppler binary is absent on the host OS, the portal gracefully falls back to PDF text extraction without crash or error.
2. **Bank Verification API**: In this hackathon MVP, live bank core banking APIs (CBS) are simulated using an authoritative mock verifier engine with realistic verification latencies and error simulation.
3. **Storage Engine**: Files are hashed (SHA-256) and stored securely in local encrypted private directories (`storage/uploads`) if Supabase Storage credentials are not active.
4. **Simulated Date Controls**: The time-machine date simulator is in-memory and gated by `ENABLE_SIMULATED_DATE=true`. Re-launching the server restores the system to real-time.
