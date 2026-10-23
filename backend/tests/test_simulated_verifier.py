from datetime import timedelta
from decimal import Decimal
import pytest
from app.core.security import create_access_token
from app.db.models import FDRRecord, InstrumentStatus, User, UserRole, VerificationLog, VerificationStatus, WorkflowAuditLog
from app.services.verifier import MockBankVerifierAdapter, get_bank_verifier


@pytest.fixture
def officer_token(db):
    user = db.query(User).filter(User.email == "officer@demo.test").first()
    return create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value},
        expires_delta=timedelta(hours=2)
    )


@pytest.fixture
def institution_token(db):
    user = db.query(User).filter(User.email == "institution@demo.test").first()
    return create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value, "institution_id": str(user.institution_id)},
        expires_delta=timedelta(hours=2)
    )


def test_simulated_verifier_exact_match(client, db, officer_token):
    # FDR 39482019482 (SBI, 1.5 Crore) has a matching mock record
    fdr = db.query(FDRRecord).filter(FDRRecord.fdr_number == "39482019482").first()
    assert fdr is not None

    res = client.post(
        f"/api/v1/fdrs/{fdr.id}/verify",
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res.status_code == 200
    data = res.json()

    assert data["source"] == "SIMULATED_BANK"
    assert data["outcome"] == "match"
    assert data["mode"] == "mock"
    assert "SIMULATED — NOT BANK CONFIRMATION" in data["disclaimer"]
    assert "fdr_number" in data["matched_fields"]
    assert "amount" in data["matched_fields"]
    assert len(data["different_fields"]) == 0
    assert data["new_verification_status"] == "verified"

    # Verify VerificationLog recorded with safe values
    vlog = (
        db.query(VerificationLog)
        .filter(VerificationLog.fdr_id == fdr.id, VerificationLog.source == "SIMULATED_BANK")
        .order_by(VerificationLog.created_at.desc())
        .first()
    )
    assert vlog is not None
    assert vlog.outcome == VerificationStatus.verified
    assert vlog.submitted_values["fdr_number"] == "39482019482"
    assert vlog.confirmed_values["amount"] == "15000000.00"
    assert "SIMULATED — NOT BANK CONFIRMATION" in vlog.resolution_note

    # Verify tamper-evident audit record logged
    audit = (
        db.query(WorkflowAuditLog)
        .filter(WorkflowAuditLog.entity_id == fdr.id, WorkflowAuditLog.action == "fdr.simulated_verification")
        .order_by(WorkflowAuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert audit.payload["outcome"] == "match"
    assert audit.payload["source"] == "SIMULATED_BANK"
    assert audit.row_hash is not None


def test_simulated_verifier_amount_mismatch(client, db, officer_token):
    # FDR ICIC5501928 has submitted amount 45,00,000, while mock record has 40,00,000
    fdr = db.query(FDRRecord).filter(FDRRecord.fdr_number == "ICIC5501928").first()
    assert fdr is not None

    res = client.post(
        f"/api/v1/fdrs/{fdr.id}/verify",
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res.status_code == 200
    data = res.json()

    assert data["source"] == "SIMULATED_BANK"
    assert data["outcome"] == "mismatch"
    assert data["new_verification_status"] == "discrepancy"
    assert "SIMULATED — NOT BANK CONFIRMATION" in data["disclaimer"]

    diff_fields = [d["field"] for d in data["different_fields"]]
    assert "amount" in diff_fields

    # FDR record in DB should have status discrepancy
    db.refresh(fdr)
    assert fdr.verification_status == VerificationStatus.discrepancy


def test_simulated_verifier_unknown_fdr_never_silently_approved(client, db, officer_token):
    # Create synthetic FDR not present in MockBankRecord table
    inst_fdr = db.query(FDRRecord).first()
    unknown_fdr = FDRRecord(
        institution_id=inst_fdr.institution_id,
        fdr_number="UNKNOWN-998877",
        bank_name="Unknown Rural Co-op Bank",
        amount=Decimal("2500000.00"),
        issue_date=inst_fdr.issue_date,
        maturity_date=inst_fdr.maturity_date,
        instrument_status=InstrumentStatus.submitted,
        verification_status=VerificationStatus.pending,
        submitted_by=inst_fdr.submitted_by,
    )
    db.add(unknown_fdr)
    db.commit()
    db.refresh(unknown_fdr)

    res = client.post(
        f"/api/v1/fdrs/{unknown_fdr.id}/verify",
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res.status_code == 200
    data = res.json()

    assert data["source"] == "SIMULATED_BANK"
    assert data["outcome"] == "not_found"
    # CRITICAL: Unknown FDRs must NEVER be silently approved; status stays pending!
    assert data["new_verification_status"] == "pending"
    assert "SIMULATED — NOT BANK CONFIRMATION" in data["disclaimer"]

    db.refresh(unknown_fdr)
    assert unknown_fdr.verification_status == VerificationStatus.pending


def test_simulated_verifier_role_restrictions(client, db, institution_token):
    fdr = db.query(FDRRecord).first()

    # Institution role is forbidden from triggering verification
    res = client.post(
        f"/api/v1/fdrs/{fdr.id}/verify",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res.status_code == 403

    # Unauthenticated is rejected
    unauth_res = client.post(f"/api/v1/fdrs/{fdr.id}/verify")
    assert unauth_res.status_code == 401


def test_verifier_factory_modes():
    # Test default mode
    adapter = get_bank_verifier()
    assert isinstance(adapter, MockBankVerifierAdapter)
    assert adapter.mode_name == "mock"

    # Test that 'real' mode raises NotImplementedError rather than falsely claiming connectivity
    from unittest.mock import patch
    with patch("app.core.config.settings.VERIFIER_MODE", "real"):
        with pytest.raises(NotImplementedError) as exc_info:
            get_bank_verifier()
        assert "Live bank gateway integration is not configured" in str(exc_info.value)
