# 🔍 OCR Setup, Intake Classification, & Escalation Guide

This document details the configuration, local setup, classification architecture, and safety rules for the AICTE FDR Vault Document Intake and Escalation Subsystem.

---

## 🛡️ Critical Safety Principles

1. **OCR & Classification Can Be Wrong**: Optical Character Recognition and automated document classifiers are probabilistic assistive tools. The system **never permanently freezes, suspends, or punishes an institution automatically** based solely on an OCR or classification result.
2. **System Failures Never Count as Strikes**: OCR engine outages, missing language data, corrupt or unreadable files, timeouts, and low-confidence classifications are **strictly excluded** from confirmed unrelated submission strikes.
3. **No Authenticity or Fraud Claims**: The system never claims that an OCR match proves document authenticity, nor that an unrelated classification proves deliberate fraud. All document-content descriptions are explicitly labeled as **automated estimates**.
4. **100% Local Document Processing**: Uploaded bank documents and security receipts are **never sent to external cloud APIs or third-party OCR services**. Processing runs entirely locally on the server host or Docker container.
5. **Multi-Tenant Isolation & Privacy**: Raw OCR text and document contents are strictly scoped to the uploading institution and authorized AICTE officers. Raw text is never exposed in public logs, error telemetry, or cross-tenant views.
6. **Data Preservation**: Manually entered form values are **never discarded or wiped** when OCR fails, times out, or when a document is flagged as unrelated.

---

## 1. Local OCR Setup Instructions

The portal uses **PyMuPDF** (`pymupdf`) and **pypdf** to read digital PDFs directly from their embedded vector text layer without requiring OCR. For scanned PDFs (raster images) and image files (PNG/JPEG), it uses **Tesseract OCR v5**.

### A. Windows Local Setup
1. **Download the Tesseract OCR Installer**:
   - Download the official 64-bit installer from the UB-Mannheim repository:
     [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
   - Run the installer (default installation path: `C:\Program Files\Tesseract-OCR\tesseract.exe`).
2. **Verify Language Data**:
   - Ensure `eng.traineddata` exists inside `C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata`.
3. **Add to System PATH or Configure `.env`**:
   - Add `C:\Program Files\Tesseract-OCR` to your Windows system `PATH` environment variable.
   - Alternatively, declare it in your `backend/.env` file:
     ```env
     TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
     TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata
     ```
4. **Verify from PowerShell**:
   ```powershell
   tesseract --version
   ```

### B. Linux / Backend Docker Image
The project backend Dockerfile (`backend/Dockerfile`) is configured to install Tesseract and English language packs automatically:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*
```
To run natively on Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

### C. Verifying OCR Subsystem Availability
The backend exposes a structured health endpoint at `GET /health/ocr`:
```json
{
  "status": "ok",
  "engine_available": true,
  "engine_status": "available",
  "engine_diagnostic": {
    "available": true,
    "status": "available",
    "version": "5.3.3",
    "languages": ["eng", "osd"],
    "binary_path": "/usr/bin/tesseract"
  },
  "escalation_policy": {
    "strike_threshold": 7,
    "window_days": 30,
    "hold_duration_days": 14,
    "deduplication": "sha256_hash"
  }
}
```

The diagnostic accurately distinguishes:
- `available`: Tesseract executable operational and English traineddata present.
- `engine_missing`: Executable binary not found on the host or PATH.
- `language_data_missing`: Tesseract binary found, but `eng.traineddata` missing from `tessdata`.

---

## 2. Document Intake & Classification Pipeline

When an institution or officer uploads a document, it passes through the multi-stage intake pipeline:

```
[Upload] ──> [SHA-256 Hash Digest]
                 │
                 ├──> [Digital PDF?] ──> [Extract Embedded Text (PyMuPDF / pypdf)]
                 │                           │ (If >= 5 words found)
                 │                           └──> [Text Classifier]
                 │
                 └──> [Scanned PDF / Image?] ──> [Is Tesseract Available?]
                                                      ├── No ──> [Return ocr_unavailable (Never flag as 'wrong')]
                                                      └── Yes ──> [Preprocess + Local Raster OCR] ──> [Text Classifier]
```

### Structured Classification Statuses

| Classification Status | Meaning | Action / User Experience |
|-----------------------|---------|--------------------------|
| `likely_fdr` | Document contains recognized banking entity and Fixed/Term Deposit terminology with tenure or amount fields. | Fields auto-populated in assistive form for officer attestation. |
| `possibly_fdr_needs_review` | Some banking or deposit terms found, but certain fields are partial or ambiguous. | Highlighted in amber for verification; manual entry enabled. |
| `likely_unrelated` | Document matches a non-FDR profile (utility bill, academic transcript, tax invoice, resume, lease agreement, identity card) without FDR core terms. | Submission blocked for institution users. Plain-language explanation with non-sensitive snippets displayed. "Replace Document" and "Request AICTE Officer Review" buttons provided. |
| `unreadable` | Blank, completely degraded, or unreadable scan (zero detected words). | Plain statement that content cannot be determined. No strikes applied; manual entry permitted. |
| `ocr_unavailable` | Tesseract engine is not installed on the server host. | Explicit notice that OCR is offline on server. Document is safely hashed and stored; form values preserved. **Never labeled as wrong.** |
| `corrupt_or_unsupported` | Corrupt bytes, invalid header, or encrypted password-protected PDF. | Safe rejection with descriptive error; manual submission blocked until valid file uploaded. |

### Privacy & Data Sanitization
- Snippets extracted for the user and officer review queue are **strictly masked**: numbers with 5 or more digits are replaced with `XXXXX`, and email addresses are replaced with `[EMAIL]`.
- Raw OCR text is stored securely in encrypted document storage and is accessible only to the owning institution and authorized AICTE vigilance officers.

---

## 3. Repeated Unrelated-Submission Escalation Policy

To protect portal integrity against automated spam or repeated non-FDR uploads while rigorously preventing false-positive institutional penalties, the portal enforces an escalating human-governed hold workflow:

### Policy Parameters
- **`UNRELATED_STRIKE_THRESHOLD`**: `7` confirmed unrelated submissions.
- **`UNRELATED_WINDOW_DAYS`**: `30` days rolling time window.
- **`REVIEW_HOLD_DAYS`**: `14` days temporary upload hold duration.

### Deduplication Rule
- Submissions are indexed by **SHA-256 cryptographic digest**.
- Retrying or re-uploading the same file hash within the rolling window **never creates duplicate strikes**. Repeated attempts with the identical file produce at most 1 strike.

### Human-in-the-Loop Gate
- Automated classification **never generates strikes directly**.
- Uploads flagged as `likely_unrelated` are staged in the **AICTE Officer Review Queue** (`/fdrs/review-queue`).
- A strike is recorded **only when an authorized AICTE Officer or System Administrator explicitly inspects the evidence and confirms the document is unrelated** (`confirm_unrelated`) with mandatory statutory remarks.
- Officers have full discretion to:
  1. `confirm_unrelated`: Assigns 1 strike (subject to file-hash deduplication).
  2. `override_as_fdr`: Overrules classifier and permits FDR deposit registration.
  3. `dismiss`: Closes review without strike (for ambiguous, test, or degraded files).

### Upload Review Hold Mechanism
When an institution reaches 7 confirmed distinct unrelated submissions within 30 days:
1. **Hold Placed**: The institution is placed on a temporary 14-day upload hold (`upload_hold_active = True`).
2. **Uploads Suspended**: New FDR submissions for that institution are blocked.
3. **Read Access Unaffected**: Existing FDR instruments, status tracking, verified certificates, and renewal history remain **100% accessible in read-only mode**. The institution is never locked out of the portal.
4. **Notifications Dispatched**: Automated notifications are delivered to institution users and AICTE system administrators explaining the hold reason and duration.
5. **Tamper-Evident Audit Record**: An SHA-256 hash-chained block is committed to the sovereign ledger (`institution.upload_hold_placed`).

### Appeals & Administrative Unfreeze
1. **Institution Appeal**: Institution users can submit a formal administrative appeal with a detailed justification statement directly from the portal. This dispatches an alert to AICTE administrators (`upload_hold_appealed_at`).
2. **Administrative Unfreeze**: An AICTE System Administrator can review the appeal and lift the hold at any time (`POST /api/v1/admin/institutions/{id}/unfreeze-hold`) with mandatory justification. This clears the hold, notifies the institution, and logs the action in the audit trail.
3. **Hold Extension**: Administrators can extend the hold by 1 to 90 days with justification if non-compliance persists (`POST /api/v1/admin/institutions/{id}/extend-hold`).
4. **Automatic Expiry**: The hold automatically clears after 14 days without requiring administrator intervention, restoring upload access seamlessly.
