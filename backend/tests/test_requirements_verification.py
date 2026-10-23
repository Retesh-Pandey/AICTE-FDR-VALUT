import io
import json
import uuid
from decimal import Decimal
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import (
    FDRRecord,
    Institution,
    InstrumentStatus,
    MockBankRecord,
    User,
    UserRole,
    VerificationStatus,
    WorkflowStatus,
)
from app.db.session import SessionLocal

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_setup(db_session):
    """Seed test fixtures for multi-tenant and role testing."""
    # Create test institutions
    inst1 = db_session.query(Institution).filter(Institution.aicte_id == "TEST-INST-001").first()
    if not inst1:
        inst1 = Institution(
            id=uuid.uuid4(),
            aicte_id="TEST-INST-001",
            name="Alpha Engineering College",
            region="North",
            contact_email="principal@alpha.test",
        )
        db_session.add(inst1)

    inst2 = db_session.query(Institution).filter(Institution.aicte_id == "TEST-INST-002").first()
    if not inst2:
        inst2 = Institution(
            id=uuid.uuid4(),
            aicte_id="TEST-INST-002",
            name="Beta Institute of Technology",
            region="South",
            contact_email="director@beta.test",
        )
        db_session.add(inst2)
    db_session.commit()

    # Create test users with distinct server-side roles
    inst_user = db_session.query(User).filter(User.email == "test_inst_user@alpha.test").first()
    if not inst_user:
        inst_user = User(
            id=uuid.uuid4(),
            email="test_inst_user@alpha.test",
            role=UserRole.institution,
            institution_id=inst1.id,
            is_active=True,
        )
        db_session.add(inst_user)

    officer_user = db_session.query(User).filter(User.email == "test_officer@aicte.gov.in").first()
    if not officer_user:
        officer_user = User(
            id=uuid.uuid4(),
            email="test_officer@aicte.gov.in",
            role=UserRole.officer,
            is_active=True,
        )
        db_session.add(officer_user)

    admin_user = db_session.query(User).filter(User.email == "test_admin@aicte.gov.in").first()
    if not admin_user:
        admin_user = User(
            id=uuid.uuid4(),
            email="test_admin@aicte.gov.in",
            role=UserRole.admin,
            is_active=True,
        )
        db_session.add(admin_user)

    # Inactive user
    inactive_user = db_session.query(User).filter(User.email == "inactive@alpha.test").first()
    if not inactive_user:
        inactive_user = User(
            id=uuid.uuid4(),
            email="inactive@alpha.test",
            role=UserRole.institution,
            institution_id=inst1.id,
            is_active=False,
        )
        db_session.add(inactive_user)

    # Seed mock bank records for simulated verification
    mock_fdr = db_session.query(MockBankRecord).filter(MockBankRecord.fdr_number == "MOCK-999-MATCH").first()
    if not mock_fdr:
        mock_fdr = MockBankRecord(
            fdr_number="MOCK-999-MATCH",
            bank_name="State Bank of India",
            branch="Parliament Street",
            amount=Decimal("1500000.00"),
            issue_date=date(2025, 1, 1),
            maturity_date=date(2028, 1, 1),
            lien_marked=True,
            status="CONFIRMED",
        )
        db_session.add(mock_fdr)

    mock_mismatch = db_session.query(MockBankRecord).filter(MockBankRecord.fdr_number == "MOCK-999-MISMATCH").first()
    if not mock_mismatch:
        mock_mismatch = MockBankRecord(
            fdr_number="MOCK-999-MISMATCH",
            bank_name="Punjab National Bank",
            branch="Connaught Place",
            amount=Decimal("500000.00"),  # Bank has 5,00,000
            issue_date=date(2025, 1, 1),
            maturity_date=date(2028, 1, 1),
            lien_marked=True,
            status="CONFIRMED",
        )
        db_session.add(mock_mismatch)

    db_session.commit()

    # Create FDR records for inst1 and inst2
    fdr_inst1 = db_session.query(FDRRecord).filter(FDRRecord.fdr_number == "MOCK-999-MATCH").first()
    if not fdr_inst1:
        fdr_inst1 = FDRRecord(
            institution_id=inst1.id,
            fdr_number="MOCK-999-MATCH",
            bank_name="State Bank of India",
            amount=Decimal("1500000.00"),
            issue_date=date(2025, 1, 1),
            maturity_date=date(2028, 1, 1),
            instrument_status=InstrumentStatus.submitted,
            verification_status=VerificationStatus.pending,
            workflow_status=WorkflowStatus.none,
            submitted_by=inst_user.id,
        )
        db_session.add(fdr_inst1)

    fdr_mismatch = db_session.query(FDRRecord).filter(FDRRecord.fdr_number == "MOCK-999-MISMATCH").first()
    if not fdr_mismatch:
        fdr_mismatch = FDRRecord(
            institution_id=inst1.id,
            fdr_number="MOCK-999-MISMATCH",
            bank_name="Punjab National Bank",
            amount=Decimal("900000.00"),  # Submitted claims 9,00,000 (differs from 5,00,000)
            issue_date=date(2025, 1, 1),
            maturity_date=date(2028, 1, 1),
            instrument_status=InstrumentStatus.submitted,
            verification_status=VerificationStatus.pending,
            workflow_status=WorkflowStatus.none,
            submitted_by=inst_user.id,
        )
        db_session.add(fdr_mismatch)

    fdr_notfound = db_session.query(FDRRecord).filter(FDRRecord.fdr_number == "FDR-NON-EXISTENT-BANK").first()
    if not fdr_notfound:
        fdr_notfound = FDRRecord(
            institution_id=inst1.id,
            fdr_number="FDR-NON-EXISTENT-BANK",
            bank_name="Bank of Baroda",
            amount=Decimal("1000000.00"),
            issue_date=date(2025, 1, 1),
            maturity_date=date(2028, 1, 1),
            instrument_status=InstrumentStatus.submitted,
            verification_status=VerificationStatus.pending,
            workflow_status=WorkflowStatus.none,
            submitted_by=inst_user.id,
        )
        db_session.add(fdr_notfound)

    fdr_inst2 = db_session.query(FDRRecord).filter(FDRRecord.fdr_number == "FDR-BETA-001").first()
    if not fdr_inst2:
        fdr_inst2 = FDRRecord(
            institution_id=inst2.id,
            fdr_number="FDR-BETA-001",
            bank_name="HDFC Bank",
            amount=Decimal("2000000.00"),
            issue_date=date(2025, 2, 1),
            maturity_date=date(2028, 2, 1),
            instrument_status=InstrumentStatus.active,
            verification_status=VerificationStatus.verified,
            workflow_status=WorkflowStatus.none,
        )
        db_session.add(fdr_inst2)

    db_session.commit()

    return {
        "inst1": inst1,
        "inst2": inst2,
        "inst_user": inst_user,
        "officer_user": officer_user,
        "admin_user": admin_user,
        "inactive_user": inactive_user,
        "fdr_inst1": fdr_inst1,
        "fdr_mismatch": fdr_mismatch,
        "fdr_notfound": fdr_notfound,
        "fdr_inst2": fdr_inst2,
    }


def auth_header(user: User) -> dict:
    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. Role-Based Sign-In & Authentication Enforcement
# =========================================================================

def test_deactivated_account_cannot_authenticate(test_setup):
    """Deactivated accounts are rejected at server-side token validation."""
    headers = auth_header(test_setup["inactive_user"])
    res = client.get("/api/v1/me", headers=headers)
    assert res.status_code == 401
    data = res.json()
    assert data["error"]["code"] == "ACCOUNT_INACTIVE"


def test_role_enforcement_institution_cannot_verify_fdr(test_setup):
    """An institution user cannot call Officer/Admin endpoints like /verify."""
    headers = auth_header(test_setup["inst_user"])
    fdr_id = str(test_setup["fdr_inst1"].id)
    res = client.post(f"/api/v1/fdrs/{fdr_id}/verify", headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN_ROLE"


def test_officer_can_access_verification_endpoint(test_setup):
    """An officer user is authorized to execute simulated bank verification."""
    headers = auth_header(test_setup["officer_user"])
    fdr_id = str(test_setup["fdr_inst1"].id)
    res = client.post(f"/api/v1/fdrs/{fdr_id}/verify", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["outcome"] == "match"
    assert "SIMULATED — NOT BANK CONFIRMATION" in data["disclaimer"]


# =========================================================================
# 2. Institution Search & Autocomplete
# =========================================================================

def test_public_institution_search_returns_synthetic_brief(test_setup):
    """Public search allows typeahead without exposing private fields."""
    res = client.get("/api/v1/institutions/public-search?q=Alpha")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    alpha_item = next(i for i in items if i["aicte_id"] == "TEST-INST-001")
    assert alpha_item["name"] == "Alpha Engineering College"
    assert alpha_item["is_synthetic"] is True
    # Ensure no private contact_email is exposed
    assert "contact_email" not in alpha_item


def test_institution_user_cannot_reassign_tenant_on_submission(test_setup):
    """Selecting a different institution ID in client request is rejected server-side."""
    headers = auth_header(test_setup["inst_user"])
    # Attempt to submit an FDR targeting inst2 while authenticated as inst1
    fake_pdf = b"%PDF-1.4 Mock Document"
    files = {"file": ("receipt.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    data = {
        "fdr_number": "ROGUE-FDR-001",
        "bank_name": "State Bank of India",
        "amount": "1000000.00",
        "issue_date": "2025-01-01",
        "maturity_date": "2028-01-01",
        "institution_id": str(test_setup["inst2"].id),  # Cross-tenant injection attempt!
    }
    res = client.post("/api/v1/fdrs", data=data, files=files, headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"


# =========================================================================
# 3. Multi-Tenant Scoping (Institution Data Isolation)
# =========================================================================

def test_institution_cannot_inspect_other_institution_fdr(test_setup):
    """Institution 1 cannot view FDRs belonging to Institution 2."""
    headers = auth_header(test_setup["inst_user"])
    inst2_fdr_id = str(test_setup["fdr_inst2"].id)
    res = client.get(f"/api/v1/fdrs/{inst2_fdr_id}", headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"


def test_officer_can_inspect_any_institution_fdr(test_setup):
    """Officers have regulatory authority to view all institutional records."""
    headers = auth_header(test_setup["officer_user"])
    inst2_fdr_id = str(test_setup["fdr_inst2"].id)
    res = client.get(f"/api/v1/fdrs/{inst2_fdr_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["fdr_number"] == "FDR-BETA-001"


# =========================================================================
# 4. Simulated Bank Verification Outcomes
# =========================================================================

def test_simulated_bank_verification_exact_match(test_setup):
    """Matching record produces 'match' outcome and explicit disclaimer."""
    headers = auth_header(test_setup["officer_user"])
    fdr_id = str(test_setup["fdr_inst1"].id)
    res = client.post(f"/api/v1/fdrs/{fdr_id}/verify", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["outcome"] == "match"
    assert data["source"] == "SIMULATED_BANK"
    assert "SIMULATED — NOT BANK CONFIRMATION" in data["disclaimer"]
    assert len(data["different_fields"]) == 0
    assert "fdr_number" in data["matched_fields"]
    assert "amount" in data["matched_fields"]


def test_simulated_bank_verification_mismatch_identifies_fields(test_setup):
    """Mismatched record produces 'mismatch' outcome and specifies differing fields."""
    headers = auth_header(test_setup["officer_user"])
    fdr_id = str(test_setup["fdr_mismatch"].id)
    res = client.post(f"/api/v1/fdrs/{fdr_id}/verify", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["outcome"] == "mismatch"
    assert "SIMULATED — NOT BANK CONFIRMATION" in data["disclaimer"]
    diff_fields = [d["field"] for d in data["different_fields"]]
    assert "amount" in diff_fields


def test_simulated_bank_verification_not_found(test_setup):
    """Unknown record produces 'not_found' outcome and does NOT approve silently."""
    headers = auth_header(test_setup["officer_user"])
    fdr_id = str(test_setup["fdr_notfound"].id)
    res = client.post(f"/api/v1/fdrs/{fdr_id}/verify", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["outcome"] == "not_found"
    assert "SIMULATED — NOT BANK CONFIRMATION" in data["disclaimer"]


# =========================================================================
# 5. OCR Processing, Health & Safety Checks
# =========================================================================

def test_ocr_health_endpoint():
    """OCR health endpoint provides clear diagnostics on Tesseract engine status."""
    res = client.get("/api/v1/health/ocr")
    assert res.status_code == 200
    data = res.json()
    assert "ocr_engine_available" in data
    assert "python_libraries" in data
    assert "pymupdf" in data["python_libraries"]
    assert "max_pages" in data
    assert "disclaimer" in data


def test_ocr_disclaimer_mandatory_on_extraction(test_setup):
    """OCR extraction returns mandatory human review disclaimer."""
    headers = auth_header(test_setup["inst_user"])
    fake_pdf = b"%PDF-1.4 Mock Sample Receipt"
    files = {"file": ("receipt.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    res = client.post("/api/v1/fdrs/ocr", files=files, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "disclaimer" in data
    assert "human review" in data["disclaimer"].lower() or "assistive" in data["disclaimer"].lower()


def test_ocr_corrupt_or_unsupported_file_rejected_safely(test_setup):
    """Executable or corrupted uploads are rejected with 400 without crashing."""
    headers = auth_header(test_setup["inst_user"])
    malicious_bytes = b"MZ\x90\x00\x03\x00\x00\x00"  # Windows PE binary header
    files = {"file": ("malware.exe", io.BytesIO(malicious_bytes), "application/x-msdownload")}
    res = client.post("/api/v1/fdrs/ocr", files=files, headers=headers)
    assert res.status_code in (400, 415)
    assert res.json()["error"]["code"] in ("UNSUPPORTED_FILE_TYPE", "INVALID_FILE", "INVALID_FILE_TYPE")

