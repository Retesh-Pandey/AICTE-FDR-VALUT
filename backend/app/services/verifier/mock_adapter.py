import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import FDRRecord, MockBankRecord, User, VerificationLog, VerificationStatus, utc_now
from app.services.audit import write_audit_log
from app.services.verifier.interface import BankVerifierAdapter

logger = logging.getLogger(__name__)

SIMULATED_DISCLAIMER = (
    "SIMULATED — NOT BANK CONFIRMATION: This result was generated using synthetic mock bank records "
    "for testing and demonstration purposes only. It is not an official bank statement and does not prove "
    "the authenticity of the FDR document."
)


def _normalize_bank_name(name: str) -> str:
    """Normalize bank names to handle abbreviations and common variations."""
    if not name:
        return ""
    n = name.strip().lower()
    if "state bank" in n or "sbi" in n:
        return "state bank of india"
    if "punjab national" in n or "pnb" in n:
        return "punjab national bank"
    if "canara" in n:
        return "canara bank"
    if "icici" in n:
        return "icici bank"
    if "bank of baroda" in n or "bob" in n:
        return "bank of baroda"
    if "hdfc" in n:
        return "hdfc bank"
    return n


class MockBankVerifierAdapter(BankVerifierAdapter):
    """
    Simulated Bank Verification Adapter.
    Queries synthetic mock bank database records (MockBankRecord) to simulate
    automated core-banking ledger checks for hackathon/demonstration workflows.
    Never hard-codes or uses live credentials, and prominently flags all results
    as synthetic non-proof.
    """

    def __init__(self, mode_name: str = "mock"):
        self.mode_name = mode_name

    def verify_fdr(
        self,
        fdr: FDRRecord,
        db: Session,
        actor: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Looks up submitted FDR in synthetic MockBankRecord table.
        Compares: fdr_number, bank_name, amount, maturity_date, issue_date.
        Records VerificationLog and WorkflowAuditLog.
        Never stores document binaries, OCR text, or secret keys in log records.
        """
        submitted_fdr_num = fdr.fdr_number.strip().upper()
        submitted_bank_norm = _normalize_bank_name(fdr.bank_name)

        # 1. Look up synthetic record
        mock_records = db.query(MockBankRecord).all()
        matched_mock: Optional[MockBankRecord] = None

        for rec in mock_records:
            if rec.fdr_number.strip().upper() == submitted_fdr_num:
                mock_bank_norm = _normalize_bank_name(rec.bank_name)
                if submitted_bank_norm == mock_bank_norm or not submitted_bank_norm or not mock_bank_norm:
                    matched_mock = rec
                    break

        old_verification_status = fdr.verification_status

        matched_fields: List[str] = []
        different_fields: List[Dict[str, Any]] = []
        all_comparisons: List[Dict[str, Any]] = []

        now = utc_now()
        actor_id = actor.id if actor else None
        actor_role = actor.role.value if actor and hasattr(actor.role, "value") else (str(actor.role) if actor else "system")

        if not matched_mock:
            # OUTCOME: not_found
            # Rule: Never silently approve unknown FDRs! Remains pending review.
            outcome = "not_found"
            new_status = VerificationStatus.pending
            fdr.verification_status = new_status

            all_comparisons = [
                {
                    "field": "fdr_number",
                    "submitted": fdr.fdr_number,
                    "confirmed": None,
                    "match": False,
                    "status": "not_found",
                    "difference": "FDR number not present in synthetic bank ledger"
                },
                {
                    "field": "bank_name",
                    "submitted": fdr.bank_name,
                    "confirmed": None,
                    "match": False,
                    "status": "not_found",
                    "difference": "No bank records matched"
                },
                {
                    "field": "amount",
                    "submitted": f"{Decimal(fdr.amount):.2f}",
                    "confirmed": None,
                    "match": False,
                    "status": "not_found",
                    "difference": "No bank records matched"
                },
                {
                    "field": "maturity_date",
                    "submitted": str(fdr.maturity_date),
                    "confirmed": None,
                    "match": False,
                    "status": "not_found",
                    "difference": "No bank records matched"
                }
            ]
            different_fields = [
                {
                    "field": "fdr_number",
                    "submitted": fdr.fdr_number,
                    "confirmed": None,
                    "reason": "Instrument not registered in simulated bank ledger"
                }
            ]

            note = (
                "[SIMULATED BANK CHECK] Instrument not found in synthetic bank ledger. "
                "Retained in pending status for manual officer examination. "
                "SIMULATED — NOT BANK CONFIRMATION."
            )

            confirmed_values_payload = None

        else:
            # Record found in synthetic bank records; compare fields
            # 1. FDR Number
            num_match = fdr.fdr_number.strip().upper() == matched_mock.fdr_number.strip().upper()
            all_comparisons.append({
                "field": "fdr_number",
                "submitted": fdr.fdr_number,
                "confirmed": matched_mock.fdr_number,
                "match": num_match,
                "status": "match" if num_match else "mismatch"
            })
            if num_match:
                matched_fields.append("fdr_number")
            else:
                different_fields.append({
                    "field": "fdr_number",
                    "submitted": fdr.fdr_number,
                    "confirmed": matched_mock.fdr_number,
                    "reason": "FDR number mismatch"
                })

            # 2. Bank Name
            bank_match = (
                _normalize_bank_name(fdr.bank_name) == _normalize_bank_name(matched_mock.bank_name)
            )
            all_comparisons.append({
                "field": "bank_name",
                "submitted": fdr.bank_name,
                "confirmed": matched_mock.bank_name,
                "match": bank_match,
                "status": "match" if bank_match else "mismatch"
            })
            if bank_match:
                matched_fields.append("bank_name")
            else:
                different_fields.append({
                    "field": "bank_name",
                    "submitted": fdr.bank_name,
                    "confirmed": matched_mock.bank_name,
                    "reason": "Bank name discrepancy"
                })

            # 3. Amount Comparison
            sub_amt = Decimal(str(fdr.amount)).quantize(Decimal("0.01"))
            mock_amt = Decimal(str(matched_mock.amount)).quantize(Decimal("0.01"))
            amt_match = (sub_amt == mock_amt)
            all_comparisons.append({
                "field": "amount",
                "submitted": f"{sub_amt:.2f}",
                "confirmed": f"{mock_amt:.2f}",
                "match": amt_match,
                "status": "match" if amt_match else "mismatch",
                "difference": None if amt_match else f"Submitted ₹{sub_amt:,.2f} vs Confirmed ₹{mock_amt:,.2f}"
            })
            if amt_match:
                matched_fields.append("amount")
            else:
                different_fields.append({
                    "field": "amount",
                    "submitted": f"{sub_amt:.2f}",
                    "confirmed": f"{mock_amt:.2f}",
                    "reason": f"Principal amount difference of ₹{abs(sub_amt - mock_amt):,.2f}"
                })

            # 4. Maturity Date
            mat_match = (fdr.maturity_date == matched_mock.maturity_date)
            all_comparisons.append({
                "field": "maturity_date",
                "submitted": str(fdr.maturity_date),
                "confirmed": str(matched_mock.maturity_date),
                "match": mat_match,
                "status": "match" if mat_match else "mismatch"
            })
            if mat_match:
                matched_fields.append("maturity_date")
            else:
                different_fields.append({
                    "field": "maturity_date",
                    "submitted": str(fdr.maturity_date),
                    "confirmed": str(matched_mock.maturity_date),
                    "reason": "Maturity date discrepancy"
                })

            # 5. Issue Date
            issue_match = (fdr.issue_date == matched_mock.issue_date)
            all_comparisons.append({
                "field": "issue_date",
                "submitted": str(fdr.issue_date),
                "confirmed": str(matched_mock.issue_date),
                "match": issue_match,
                "status": "match" if issue_match else "mismatch"
            })
            if issue_match:
                matched_fields.append("issue_date")
            else:
                different_fields.append({
                    "field": "issue_date",
                    "submitted": str(fdr.issue_date),
                    "confirmed": str(matched_mock.issue_date),
                    "reason": "Issue date discrepancy"
                })

            # 6. Check synthetic bank status
            if matched_mock.status != "CONFIRMED":
                different_fields.append({
                    "field": "bank_ledger_status",
                    "submitted": "CONFIRMED",
                    "confirmed": matched_mock.status,
                    "reason": f"Synthetic bank ledger flagged status '{matched_mock.status}'"
                })

            if len(different_fields) == 0:
                outcome = "match"
                new_status = VerificationStatus.verified
                note = (
                    f"[SIMULATED BANK CHECK] All synthetic bank parameters matched ({len(matched_fields)} fields). "
                    "SIMULATED — NOT BANK CONFIRMATION."
                )
            else:
                outcome = "mismatch"
                new_status = VerificationStatus.discrepancy
                diff_summary = ", ".join([d["field"] for d in different_fields])
                note = (
                    f"[SIMULATED BANK CHECK] Discrepancies detected across: {diff_summary}. "
                    "Instrument flagged for statutory officer review. "
                    "SIMULATED — NOT BANK CONFIRMATION."
                )

            fdr.verification_status = new_status
            confirmed_values_payload = {
                "fdr_number": matched_mock.fdr_number,
                "bank_name": matched_mock.bank_name,
                "branch": matched_mock.branch,
                "amount": f"{matched_mock.amount:.2f}",
                "issue_date": str(matched_mock.issue_date),
                "maturity_date": str(matched_mock.maturity_date),
                "lien_marked": matched_mock.lien_marked,
                "status": matched_mock.status
            }

        # Safe submitted values (no document binaries, OCR dumps, or sensitive auth credentials)
        safe_submitted_values = {
            "fdr_number": fdr.fdr_number,
            "bank_name": fdr.bank_name,
            "branch": fdr.branch,
            "amount": f"{Decimal(fdr.amount):.2f}",
            "issue_date": str(fdr.issue_date),
            "maturity_date": str(fdr.maturity_date)
        }

        # 2. Record VerificationLog
        vlog = VerificationLog(
            fdr_id=fdr.id,
            source="SIMULATED_BANK",
            submitted_values=safe_submitted_values,
            confirmed_values=confirmed_values_payload,
            discrepancies=different_fields,
            outcome=new_status,
            resolved_by=actor_id,
            resolution_note=note,
            created_at=now
        )
        db.add(vlog)
        db.flush()

        # 3. Append to Tamper-Evident SHA-256 Hash-Chained WorkflowAuditLog
        write_audit_log(
            db=db,
            action="fdr.simulated_verification",
            entity="fdr",
            entity_id=fdr.id,
            actor_id=actor_id,
            actor_role=actor_role,
            old_status=old_verification_status.value if hasattr(old_verification_status, "value") else str(old_verification_status),
            new_status=new_status.value,
            remarks=f"Simulated bank verification executed via {self.mode_name} adapter. Outcome: {outcome}. SIMULATED — NOT BANK CONFIRMATION.",
            payload={
                "source": "SIMULATED_BANK",
                "adapter_mode": self.mode_name,
                "outcome": outcome,
                "matched_fields_count": len(matched_fields),
                "discrepancies_count": len(different_fields),
                "discrepant_fields": [d["field"] for d in different_fields]
            }
        )

        db.commit()
        db.refresh(fdr)

        return {
            "source": "SIMULATED_BANK",
            "outcome": outcome,
            "mode": self.mode_name,
            "fdr_id": fdr.id,
            "fdr_number": fdr.fdr_number,
            "bank_name": fdr.bank_name,
            "matched_fields": matched_fields,
            "different_fields": different_fields,
            "all_comparisons": all_comparisons,
            "disclaimer": SIMULATED_DISCLAIMER,
            "timestamp": now,
            "actor": actor.email if actor else "system",
            "new_verification_status": new_status,
            "verification_log_id": vlog.id
        }
