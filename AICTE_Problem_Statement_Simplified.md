# AICTE Problem Statement SIH26265 — Streamline of Security Deposit / FDR Portal

## 1. Background and Context

The All India Council for Technical Education (AICTE), the apex advisory and regulatory body for technical education in India under the Ministry of Education, requires technical institutions seeking approval, affiliation, or capacity expansion to submit and maintain security deposits in the form of **Fixed Deposit Receipts (FDRs)**. These FDRs, typically held jointly with the Member Secretary of AICTE or under sovereign lien, safeguard student and public interest, ensuring compliance with institutional norms, infrastructure standards, and regulatory covenants.

## 2. Core Problem & Pain Points

Currently, FDR management across thousands of technical institutions involves fragmented, manual processes spanning spreadsheets, physical paperwork, emails, and isolated branch correspondence. This manual paradigm creates severe operational risks:
- **Maturity Blindspots:** FDR maturity milestones are frequently missed or overlooked without automated proactive alerts, causing loss of accrued interest, regulatory delinquency, and administrative backlogs.
- **Verification Bottlenecks:** Manual reconciliation between institution-submitted receipts and issuing bank ledgers is time-consuming and vulnerable to clerical error or document tampering.
- **Traceability Gaps:** Tracking renewal chains, superseding FDRs, and lien status across multiple academic years lacks a unified, tamper-evident audit trail.
- **Uncontrolled Release Delays:** Legitimate refund/release requests are delayed due to scattered compliance records, or conversely, lack strict role-enforced multi-stage governance before encashment authorization.

## 3. SIH26265 Objectives & Expected Outcome

Build the **AICTE Smart FDR Lifecycle Management Portal** ("AICTE FDR Vault"):
1. **Central Repository:** A unified, searchable repository indexing institutional FDR records with unique regulatory identifiers, tracking 3 distinct statuses (Instrument, Verification, Workflow).
2. **Intelligent Document Ingestion (OCR):** Automated extraction of critical fields (FDR number, issuing bank/IFSC, principal sum, interest rate, issue/maturity dates, and lien clause) from scanned receipts/PDFs with human-in-the-loop validation and confidence scoring.
3. **Automated Compliance & Verification Engine:** Cross-verification of submitted instrument attributes against bank confirmation adapters (simulated for MVP, bank-API ready) with clear discrepancy flagging.
4. **Maturity Radar & Proactive Notifications:** Automated milestone monitoring (30, 15, and 7-day windows + maturity) with simulated calendar date manipulation for demonstration.
5. **Governed Renewal & Controlled Release Workflows:** State-machine enforced transitions with role-based checks (Institution, Officer, Administrator) preventing automatic unauthorized releases.
6. **Cryptographic Tamper-Evident Audit Ledger:** Append-only, SHA-256 hash-chained immutable audit log of all regulatory actions and state transitions with verifiable chain parity.
