from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FDRDocument, FDRRecord


class ValidationFlag:
    def __init__(self, rule: str, severity: str, message: str, field: Optional[str] = None):
        self.rule = rule
        self.severity = severity  # 'info' | 'warning' | 'critical'
        self.field = field
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
        }


class ValidationEngine:
    def validate_fdr(
        self,
        db: Session,
        institution_id: UUID,
        fdr_number: str,
        bank_name: str,
        amount: Decimal,
        issue_date: date,
        maturity_date: date,
        document_sha256: Optional[str] = None,
        extracted_json: Optional[Dict[str, Any]] = None,
        current_fdr_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates FDR submission against compliance and sanity checks.
        Returns a list of validation flags with neutral, factual wording.
        """
        flags: List[ValidationFlag] = []

        # 1. Critical: Mandatory fields check
        if not fdr_number or not fdr_number.strip():
            flags.append(
                ValidationFlag(
                    rule="REQUIRED_FIELD_MISSING",
                    severity="critical",
                    field="fdr_number",
                    message="FDR number is required and cannot be blank.",
                )
            )

        if not bank_name or not bank_name.strip():
            flags.append(
                ValidationFlag(
                    rule="REQUIRED_FIELD_MISSING",
                    severity="critical",
                    field="bank_name",
                    message="Bank name is required and cannot be blank.",
                )
            )

        # 2. Critical: Amount validation
        if amount is None or amount <= Decimal("0"):
            flags.append(
                ValidationFlag(
                    rule="INVALID_AMOUNT",
                    severity="critical",
                    field="amount",
                    message="Principal amount must be strictly greater than zero.",
                )
            )

        # 3. Critical: Maturity vs Issue date logic
        if issue_date and maturity_date:
            if maturity_date <= issue_date:
                flags.append(
                    ValidationFlag(
                        rule="INVALID_DATE_SEQUENCE",
                        severity="critical",
                        field="maturity_date",
                        message="Maturity date must be strictly after the issue date.",
                    )
                )

        # 4. Warning: Future issue date
        today = date.today()
        if issue_date and issue_date > today:
            flags.append(
                ValidationFlag(
                    rule="FUTURE_ISSUE_DATE",
                    severity="warning",
                    field="issue_date",
                    message="Issue date is recorded in the future — needs review.",
                )
            )

        # 5. Critical check: Duplicate (bank_name, fdr_number)
        if bank_name and fdr_number:
            query = select(FDRRecord).where(
                FDRRecord.bank_name.ilike(bank_name.strip()),
                FDRRecord.fdr_number == fdr_number.strip(),
            )
            if current_fdr_id:
                query = query.where(FDRRecord.id != current_fdr_id)

            existing = db.execute(query).scalar_one_or_none()
            if existing:
                flags.append(
                    ValidationFlag(
                        rule="DUPLICATE_FDR_NUMBER",
                        severity="critical",
                        field="fdr_number",
                        message=f"An instrument with FDR number '{fdr_number}' and bank '{bank_name}' is already registered.",
                    )
                )

        # 6. Warning: Document SHA-256 duplication
        if document_sha256:
            query_doc = select(FDRDocument).where(FDRDocument.sha256 == document_sha256)
            if current_fdr_id:
                query_doc = query_doc.where(FDRDocument.fdr_id != current_fdr_id)

            dup_doc = db.execute(query_doc).first()
            if dup_doc:
                flags.append(
                    ValidationFlag(
                        rule="DUPLICATE_DOCUMENT_HASH",
                        severity="warning",
                        field="document",
                        message="Document cryptographic hash matches a previously submitted file — verify if re-submission or duplicate.",
                    )
                )

        # 7. Discrepancy checks against assistive OCR extractions (if present)
        if extracted_json:
            # Amount discrepancy
            ocr_amt_data = extracted_json.get("amount", {})
            if isinstance(ocr_amt_data, dict) and ocr_amt_data.get("value"):
                try:
                    ocr_amt = Decimal(str(ocr_amt_data["value"]))
                    if ocr_amt != amount:
                        flags.append(
                            ValidationFlag(
                                rule="EXTRACTION_DISCREPANCY_AMOUNT",
                                severity="warning",
                                field="amount",
                                message="Amount differs between document extraction and entered value — needs review.",
                            )
                        )
                except Exception:
                    pass

            # FDR number discrepancy
            ocr_fdr_data = extracted_json.get("fdr_number", {})
            if isinstance(ocr_fdr_data, dict) and ocr_fdr_data.get("value"):
                ocr_num = str(ocr_fdr_data["value"]).strip().upper()
                entered_num = fdr_number.strip().upper() if fdr_number else ""
                if ocr_num and entered_num and ocr_num != entered_num:
                    flags.append(
                        ValidationFlag(
                            rule="EXTRACTION_DISCREPANCY_NUMBER",
                            severity="warning",
                            field="fdr_number",
                            message="FDR number differs between document extraction and entered value — needs review.",
                        )
                    )

            # Bank name discrepancy
            ocr_bank_data = extracted_json.get("bank_name", {})
            if isinstance(ocr_bank_data, dict) and ocr_bank_data.get("value"):
                ocr_bank = str(ocr_bank_data["value"]).strip().lower()
                entered_bank = bank_name.strip().lower() if bank_name else ""
                if ocr_bank and entered_bank and ocr_bank not in entered_bank and entered_bank not in ocr_bank:
                    flags.append(
                        ValidationFlag(
                            rule="EXTRACTION_DISCREPANCY_BANK",
                            severity="warning",
                            field="bank_name",
                            message="Bank name differs between document extraction and entered value — needs review.",
                        )
                    )

            # Low confidence warnings (Info severity)
            for field_name in ["fdr_number", "bank_name", "amount", "issue_date", "maturity_date"]:
                field_info = extracted_json.get(field_name, {})
                if isinstance(field_info, dict):
                    conf = field_info.get("confidence", 0.0)
                    val = field_info.get("value")
                    if val is not None and conf < 0.60:
                        flags.append(
                            ValidationFlag(
                                rule="LOW_EXTRACTION_CONFIDENCE",
                                severity="info",
                                field=field_name,
                                message=f"Low extraction confidence ({int(conf * 100)}%) for {field_name.replace('_', ' ')} — manual verification recommended.",
                            )
                        )

        return [f.to_dict() for f in flags]


validation_engine = ValidationEngine()
