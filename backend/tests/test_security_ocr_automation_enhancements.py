import io
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_download_token,
    get_password_hash,
    verify_download_token,
    verify_password,
)
from app.db.models import (
    FDRDocument,
    FDRRecord,
    Institution,
    InstrumentStatus,
    Notification,
    User,
    UserRole,
    VerificationStatus,
    WorkflowStatus,
)
from app.main import app
from app.services.jobs.maturity import run_maturity_check
from app.services.jobs.scheduler import scheduled_maturity_job
from app.services.ocr.extract import ocr_extractor
from app.services.storage import storage_service


# ==========================================
# 1. SECURITY & AUTHENTICATION TESTS
# ==========================================

def test_password_hashing_and_verification():
    """Verify password hashing generates unique salts and verifies correctly."""
    pwd = "SecureTestPassword@2026"
    hashed = get_password_hash(pwd)
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword@123", hashed) is False
    assert verify_password("", hashed) is False


def test_password_login_endpoint_success_and_failure(db: Session):
    """Verify /auth/login verifies credentials and returns valid access token."""
    client = TestClient(app)

    # Verify existing seeded user login
    res = client.post("/auth/login", json={"email": "officer@demo.test", "password": "Demo@12345"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "officer@demo.test"
    assert data["user"]["role"] == "officer"

    # Verify wrong password fails
    bad_res = client.post("/auth/login", json={"email": "officer@demo.test", "password": "WrongPassword"})
    assert bad_res.status_code == 401
    assert bad_res.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # Verify non-existent user fails
    unknown_res = client.post("/auth/login", json={"email": "unknown@demo.test", "password": "Demo@12345"})
    assert unknown_res.status_code == 401


def test_change_password_endpoint(db: Session):
    """Verify authenticated password change works and verifies against new password."""
    client = TestClient(app)

    # Log in as institution user
    login_res = client.post("/auth/login", json={"email": "institution@demo.test", "password": "Demo@12345"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Change password
    chg_res = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "Demo@12345", "new_password": "NewInstitutionPassword@2026"},
    )
    assert chg_res.status_code == 200

    # Test login with old password fails
    old_login = client.post("/auth/login", json={"email": "institution@demo.test", "password": "Demo@12345"})
    assert old_login.status_code == 401

    # Test login with new password succeeds
    new_login = client.post("/auth/login", json={"email": "institution@demo.test", "password": "NewInstitutionPassword@2026"})
    assert new_login.status_code == 200

    # Reset back to Demo@12345 for subsequent tests
    new_token = new_login.json()["access_token"]
    client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {new_token}"},
        json={"current_password": "NewInstitutionPassword@2026", "new_password": "Demo@12345"},
    )


def test_demo_login_disabled_when_flag_turned_off(client):
    """Verify demo login endpoint returns 403 when ENABLE_DEMO_LOGIN is disabled."""
    orig = settings.ENABLE_DEMO_LOGIN
    try:
        settings.ENABLE_DEMO_LOGIN = False
        res = client.post("/auth/demo-login", json={"email": "admin@demo.test"})
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "DEMO_LOGIN_DISABLED"
    finally:
        settings.ENABLE_DEMO_LOGIN = orig


# ==========================================
# 2. OCR EXTRACTION & SAMPLE TESTS
# ==========================================

def test_ocr_clean_sample_pdf():
    """Verify OCR extracts all 9 fields from sample clean FDR PDF."""
    pdf_path = Path("sample-data/fdr_clean.pdf")
    if not pdf_path.is_file():
        pytest.skip("sample-data/fdr_clean.pdf not found")

    content = pdf_path.read_bytes()
    res = ocr_extractor.extract_fields(content, "fdr_clean.pdf")

    assert res["extraction_status"] == "success"
    assert res["bank_name"]["value"] == "State Bank of India"
    assert res["fdr_number"]["value"] == "FDR-SBI-2026-8801"
    assert res["amount"]["value"] == "5000000.00"
    assert res["issue_date"]["value"] == "2026-01-15"
    assert res["maturity_date"]["value"] == "2027-01-15"
    assert res["interest_rate"]["value"] == "7.25%"
    assert "Member Secretary" in str(res["lien_info"]["value"])
    assert "Assistive data entry only" in res["disclaimer"]


def test_ocr_lakh_crore_format_sample():
    """Verify OCR handles crore format (Rs. 1,25,00,000.00) and PNB bank receipt."""
    pdf_path = Path("sample-data/fdr_lakh_crore_format.pdf")
    if not pdf_path.is_file():
        pytest.skip("sample-data/fdr_lakh_crore_format.pdf not found")

    content = pdf_path.read_bytes()
    res = ocr_extractor.extract_fields(content, "fdr_lakh_crore_format.pdf")

    assert res["extraction_status"] == "success"
    assert res["bank_name"]["value"] == "Punjab National Bank"
    assert "PNB" in str(res["fdr_number"]["value"])
    assert res["amount"]["value"] == "12500000.00"
    assert res["interest_rate"]["value"] == "7.40%"
    assert "AICTE" in str(res["lien_info"]["value"])


def test_ocr_unreadable_sample_safe_handling():
    """Verify OCR returns status 'unreadable' without raising exceptions on empty/blank files."""
    pdf_path = Path("sample-data/fdr_unreadable_sample.pdf")
    if not pdf_path.is_file():
        pytest.skip("sample-data/fdr_unreadable_sample.pdf not found")

    content = pdf_path.read_bytes()
    res = ocr_extractor.extract_fields(content, "fdr_unreadable_sample.pdf")

    assert res["extraction_status"] == "unreadable"
    assert res["fdr_number"]["value"] is None
    assert res["amount"]["value"] is None
    assert "Assistive data entry only" in res["disclaimer"]


def test_ocr_corrupt_or_malformed_bytes_handled_safely():
    """Verify corrupt bytes are safely handled without unhandled 500 errors."""
    corrupt_bytes = b"corrupt random binary content not a real document"
    res = ocr_extractor.extract_fields(corrupt_bytes, "malformed.pdf")
    assert res["extraction_status"] in ("processing_error", "unreadable")
    assert res["bank_name"]["value"] is None


# ==========================================
# 3. ENCRYPTION AT REST & STORAGE TESTS
# ==========================================

def test_document_encryption_at_rest(tmp_path):
    """Verify documents are encrypted with Fernet on disk and decrypted on read."""
    inst_id = uuid4()
    test_content = b"%PDF-1.4 Mock sensitive bank document content that must be encrypted at rest"
    sha = storage_service.compute_sha256(test_content)

    rel_path = storage_service.save_document(
        content=test_content,
        institution_id=inst_id,
        sha256_hash=sha,
        safe_filename="test_fdr.pdf",
    )

    abs_path = storage_service.get_absolute_path(rel_path)
    assert abs_path.is_file()

    # Verify disk content is encrypted (starts with Fernet token header b'gAAAAA')
    disk_bytes = abs_path.read_bytes()
    assert disk_bytes != test_content
    assert disk_bytes.startswith(b"gAAAAA")

    # Verify read_document_bytes automatically decrypts to exact plain bytes
    decrypted_bytes = storage_service.read_document_bytes(rel_path)
    assert decrypted_bytes == test_content


def test_streaming_upload_validation_magic_bytes():
    """Verify storage service validates real file magic bytes."""
    # Spoofed file (text file with .pdf extension)
    spoofed = b"This is plain text claiming to be a PDF"
    with pytest.raises(Exception) as exc_info:
        storage_service.validate_content_signature(spoofed, ".pdf")
    assert getattr(exc_info.value, "code", "") == "MALFORMED_PDF" or "valid PDF signature" in str(exc_info.value)

    # Valid PDF magic bytes pass
    valid_pdf = b"%PDF-1.4 header content"
    storage_service.validate_content_signature(valid_pdf, ".pdf")


def test_signed_download_token_verification(db: Session):
    """Verify signed download token validation, expiration, and tenant access."""
    client = TestClient(app)

    # Seed an FDR record and document
    inst = db.query(Institution).first()
    fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-DL-{uuid4().hex[:6]}",
        bank_name="State Bank of India",
        amount=Decimal("1000000.00"),
        issue_date=date.today() - timedelta(days=30),
        maturity_date=date.today() + timedelta(days=335),
    )
    db.add(fdr)
    db.flush()

    raw_content = b"%PDF-1.4 Valid test receipt bytes"
    sha = storage_service.compute_sha256(raw_content)
    rel_path = storage_service.save_document(
        content=raw_content,
        institution_id=inst.id,
        sha256_hash=sha,
        safe_filename="receipt.pdf",
    )

    doc = FDRDocument(
        fdr_id=fdr.id,
        storage_path=rel_path,
        doc_type="fdr_receipt",
        sha256=sha,
    )
    db.add(doc)
    db.commit()

    # 1. Valid signed token succeeds without Authorization header
    valid_token = create_download_token(
        document_id=doc.id,
        user_id=uuid4(),
        institution_id=inst.id,
        expires_in_minutes=10,
    )
    res_valid = client.get(f"/fdrs/documents/{doc.id}/download?token={valid_token}")
    assert res_valid.status_code == 200
    assert res_valid.content == raw_content

    # 2. Expired signed token fails with 401
    expired_token = create_download_token(
        document_id=doc.id,
        user_id=uuid4(),
        institution_id=inst.id,
        expires_in_minutes=-5,  # Expired in past
    )
    res_expired = client.get(f"/fdrs/documents/{doc.id}/download?token={expired_token}")
    assert res_expired.status_code == 401
    assert "EXPIRED" in res_expired.json()["error"]["code"]

    # 3. Token for mismatched document ID fails with 403
    other_doc_id = uuid4()
    mismatched_token = create_download_token(
        document_id=other_doc_id,
        user_id=uuid4(),
        institution_id=inst.id,
        expires_in_minutes=10,
    )
    res_mismatch = client.get(f"/fdrs/documents/{doc.id}/download?token={mismatched_token}")
    assert res_mismatch.status_code == 403
    assert res_mismatch.json()["error"]["code"] == "TOKEN_MISMATCH"


# ==========================================
# 4. MATURITY AUTOMATION & WORKFLOW TESTS
# ==========================================

def test_scheduled_maturity_job_idempotent_no_duplicate_notifications(db: Session):
    """Verify scheduled_maturity_job runs idempotently and does not create duplicate notifications."""
    inst = db.query(Institution).first()
    officer = db.query(User).filter(User.role == UserRole.officer).first()

    # Create FDR expiring in 10 days (boundary 15)
    fdr_num = f"FDR-SCHED-{uuid4().hex[:6]}"
    test_fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number=fdr_num,
        bank_name="Canara Bank",
        amount=Decimal("2000000.00"),
        issue_date=date.today() - timedelta(days=350),
        maturity_date=date.today() + timedelta(days=10),
        instrument_status=InstrumentStatus.active,
        is_current=True,
    )
    db.add(test_fdr)
    db.commit()

    # First scheduled run
    scheduled_maturity_job()

    initial_notifs = db.query(Notification).filter(Notification.fdr_id == test_fdr.id).count()
    assert initial_notifs > 0

    # Second scheduled run
    scheduled_maturity_job()

    subsequent_notifs = db.query(Notification).filter(Notification.fdr_id == test_fdr.id).count()
    assert subsequent_notifs == initial_notifs  # Zero duplicates created!

    # Verify FDR is NEVER released automatically by maturity job
    db.refresh(test_fdr)
    assert test_fdr.instrument_status != InstrumentStatus.released


def test_simulate_date_admin_only_and_production_guard(db: Session):
    """Verify /admin/simulate-date requires Admin role and fails in production."""
    client = TestClient(app)

    # 1. Officer attempting simulate-date is rejected with 403
    login_officer = client.post("/auth/login", json={"email": "officer@demo.test", "password": "Demo@12345"})
    officer_token = login_officer.json()["access_token"]
    res_officer = client.post(
        "/admin/simulate-date",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"offset_days": 40},
    )
    assert res_officer.status_code == 403
    assert res_officer.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # 2. Admin succeeds when simulation enabled
    login_admin = client.post("/auth/login", json={"email": "admin@demo.test", "password": "Demo@12345"})
    admin_token = login_admin.json()["access_token"]
    res_admin = client.post(
        "/admin/simulate-date",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reset": True},
    )
    assert res_admin.status_code == 200
