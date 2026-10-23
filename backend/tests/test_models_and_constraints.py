import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    FDRDocument,
    FDRRecord,
    Institution,
    InstrumentStatus,
    Notification,
    User,
    UserRole,
    VerificationStatus,
    WorkflowAuditLog,
    WorkflowStatus,
)
from app.schemas.fdr import FDRCreate
from app.services.audit import verify_chain_integrity, write_audit_log


def test_fdr_relationships(db):
    inst = db.query(Institution).filter(Institution.aicte_id == "AICTE-1-4928190").first()
    assert inst is not None
    assert len(inst.fdrs) >= 3

    # Check SBI FDR
    sbi_fdr = db.query(FDRRecord).filter(FDRRecord.fdr_number == "39482019482").first()
    assert sbi_fdr is not None
    assert sbi_fdr.institution.id == inst.id
    assert sbi_fdr.amount == Decimal("15000000.00")
    assert len(sbi_fdr.documents) >= 1
    assert len(sbi_fdr.verification_logs) >= 1
    assert sbi_fdr.verification_status == VerificationStatus.verified

    # Check renewal linkage
    new_pnb = db.query(FDRRecord).filter(FDRRecord.fdr_number == "PNB77492011").first()
    assert new_pnb is not None
    assert new_pnb.previous_fdr is not None
    assert new_pnb.previous_fdr.fdr_number == "PNB77490001-OLD"
    assert new_pnb.previous_fdr.instrument_status == InstrumentStatus.renewed
    assert not new_pnb.previous_fdr.is_current


def test_decoupled_statuses(db):
    """Ensure instrument_status, verification_status, and workflow_status operate independently."""
    # Submitted FDR with pending verification
    fdr2 = db.query(FDRRecord).filter(FDRRecord.fdr_number == "PNB77492011").first()
    assert fdr2.instrument_status == InstrumentStatus.submitted
    assert fdr2.verification_status == VerificationStatus.pending
    assert fdr2.workflow_status == WorkflowStatus.none

    # Active FDR under release request review
    fdr5 = db.query(FDRRecord).filter(FDRRecord.fdr_number == "HDFC9920194").first()
    assert fdr5.instrument_status == InstrumentStatus.released
    assert fdr5.verification_status == VerificationStatus.verified
    assert fdr5.workflow_status == WorkflowStatus.completed

    # Submitted FDR with discrepancy
    fdr6 = db.query(FDRRecord).filter(FDRRecord.fdr_number == "ICIC5501928").first()
    assert fdr6.instrument_status == InstrumentStatus.submitted
    assert fdr6.verification_status == VerificationStatus.discrepancy


def test_unique_bank_fdr_number_constraint(db):
    """Prevent duplicate (bank_name, fdr_number) from being inserted."""
    inst = db.query(Institution).first()
    dup_fdr = FDRRecord(
        id=uuid.uuid4(),
        institution_id=inst.id,
        fdr_number="39482019482",  # Existing SBI FDR
        bank_name="State Bank of India",
        amount=Decimal("1000000.00"),
        issue_date=date.today(),
        maturity_date=date.today() + timedelta(days=365)
    )
    db.add(dup_fdr)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_unique_notification_milestone_constraint(db):
    """Prevent duplicate notifications for the same user, FDR, and milestone."""
    user = db.query(User).filter(User.role == UserRole.institution).first()
    fdr = db.query(FDRRecord).first()
    unique_milestone = f"milestone_dup_{uuid.uuid4()}"

    n1 = Notification(
        id=uuid.uuid4(),
        user_id=user.id,
        fdr_id=fdr.id,
        type="maturity_30",
        milestone=unique_milestone,
        message="Notice 1"
    )
    db.add(n1)
    db.commit()

    n2 = Notification(
        id=uuid.uuid4(),
        user_id=user.id,
        fdr_id=fdr.id,
        type="maturity_30",
        milestone=unique_milestone,
        message="Notice 2 duplicate"
    )
    db.add(n2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Clean up n1
    db.delete(n1)
    db.commit()


def test_pydantic_schema_validation():
    """Verify Pydantic schemas enforce non-negotiable validation rules."""
    # Amount must be strictly > 0
    with pytest.raises(ValueError, match="strictly greater than 0"):
        FDRCreate(
            institution_id=uuid.uuid4(),
            fdr_number="TEST001",
            bank_name="Test Bank",
            amount=Decimal("-500.00"),
            issue_date=date(2025, 1, 1),
            maturity_date=date(2026, 1, 1)
        )

    # Maturity date must be strictly > issue date
    with pytest.raises(ValueError, match="strictly after"):
        FDRCreate(
            institution_id=uuid.uuid4(),
            fdr_number="TEST002",
            bank_name="Test Bank",
            amount=Decimal("50000.00"),
            issue_date=date(2026, 1, 1),
            maturity_date=date(2025, 1, 1)
        )


def test_audit_hash_chain_and_tamper_detection(db):
    """Verify SHA-256 hash chain validity and ensure tampered blocks are detected."""
    # 1. Existing seeded chain must be 100% valid
    result = verify_chain_integrity(db)
    assert result["valid"] is True
    assert result["broken_at"] is None
    assert result["total_blocks"] >= 8

    # 2. Append a new block and verify it extends the chain seamlessly
    write_audit_log(
        db=db,
        action="fdr.test_action",
        entity="fdr",
        actor_role="admin",
        remarks="Extending audit chain in unit test"
    )
    db.commit()

    res_after = verify_chain_integrity(db)
    assert res_after["valid"] is True
    assert res_after["total_blocks"] == result["total_blocks"] + 1

    # 3. Simulate tamper: modify remarks of an existing row directly without updating hash
    tampered_log = db.query(WorkflowAuditLog).filter(WorkflowAuditLog.id == 2).first()
    original_remarks = tampered_log.remarks
    tampered_log.remarks = "MALICIOUS_TAMPER_MODIFICATION"
    db.commit()

    tamper_check = verify_chain_integrity(db)
    assert tamper_check["valid"] is False
    assert tamper_check["broken_at"] == 2

    # Restore original remarks
    tampered_log.remarks = original_remarks
    db.commit()
    restore_check = verify_chain_integrity(db)
    assert restore_check["valid"] is True


def test_fdr_cascade_delete(db):
    """Deleting an FDR cascades to associated documents, verification logs, notifications, and release requests."""
    inst = db.query(Institution).first()
    user = db.query(User).first()

    temp_fdr = FDRRecord(
        id=uuid.uuid4(),
        institution_id=inst.id,
        fdr_number="CASCADE_TEST_999",
        bank_name="Test Bank",
        amount=Decimal("100000.00"),
        issue_date=date.today(),
        maturity_date=date.today() + timedelta(days=365)
    )
    db.add(temp_fdr)
    db.commit()

    doc = FDRDocument(
        id=uuid.uuid4(),
        fdr_id=temp_fdr.id,
        storage_path="test/path.pdf",
        sha256="testsha256hash999",
        uploaded_by=user.id
    )
    db.add(doc)
    db.commit()

    doc_id = doc.id
    db.delete(temp_fdr)
    db.commit()

    # Document should be gone due to CASCADE
    assert db.query(FDRDocument).filter(FDRDocument.id == doc_id).first() is None
