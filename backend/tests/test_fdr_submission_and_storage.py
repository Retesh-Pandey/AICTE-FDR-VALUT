from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.auth import create_access_token
from app.db.models import FDRRecord, Institution, User, UserRole, WorkflowAuditLog


@pytest.fixture
def auth_headers(db):
    """Generates bearer authorization headers for each demo role."""
    inst_user = db.query(User).filter(User.role == UserRole.institution).first()
    officer_user = db.query(User).filter(User.role == UserRole.officer).first()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()

    return {
        "institution": {
            "Authorization": f"Bearer {create_access_token({'sub': str(inst_user.id), 'email': inst_user.email, 'role': 'institution'})}",
            "user": inst_user,
        },
        "officer": {
            "Authorization": f"Bearer {create_access_token({'sub': str(officer_user.id), 'email': officer_user.email, 'role': 'officer'})}",
            "user": officer_user,
        },
        "admin": {
            "Authorization": f"Bearer {create_access_token({'sub': str(admin_user.id), 'email': admin_user.email, 'role': 'admin'})}",
            "user": admin_user,
        },
    }


def test_ocr_endpoint_assistive(client: TestClient, auth_headers):
    """Verify POST /api/v1/fdrs/ocr extracts fields without creating database records."""
    pdf_path = Path("sample-data/fdr_clean.pdf")
    pdf_bytes = pdf_path.read_bytes() if pdf_path.exists() else b"%PDF-1.4 Mock PDF"

    response = client.post(
        "/api/v1/fdrs/ocr",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        files={"file": ("fdr_clean.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert "fdr_number" in data
    assert "bank_name" in data
    assert "amount" in data
    assert "disclaimer" in data
    assert "Assistive data entry only" in data["disclaimer"]


def test_fdr_submission_success(client: TestClient, auth_headers, db):
    """Verify complete FDR submission flow, private storage, and atomic audit row."""
    import uuid
    test_fdr_num = f"FDR-AUTO-{uuid.uuid4().hex[:6].upper()}"
    inst_user = auth_headers["institution"]["user"]
    pdf_path = Path("sample-data/fdr_clean.pdf")
    pdf_bytes = pdf_path.read_bytes() if pdf_path.exists() else b"%PDF-1.4 Dummy"

    form_data = {
        "fdr_number": test_fdr_num,
        "bank_name": "State Bank of India",
        "branch": "Parliament Street",
        "amount": "5000000.00",
        "issue_date": "2026-01-15",
        "maturity_date": "2027-01-15",
        "lien_info": "Lien in favor of Member Secretary AICTE",
    }
    files = {"file": ("fdr_test_deposit.pdf", pdf_bytes, "application/pdf")}

    response = client.post(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        data=form_data,
        files=files,
    )

    assert response.status_code == 201
    res_data = response.json()
    assert "fdr" in res_data
    assert "document" in res_data

    fdr = res_data["fdr"]
    assert fdr["fdr_number"] == test_fdr_num
    assert fdr["bank_name"] == "State Bank of India"
    assert fdr["instrument_status"] == "submitted"
    assert fdr["verification_status"] == "pending"
    assert fdr["institution_id"] == str(inst_user.institution_id)

    doc = res_data["document"]
    assert "sha256" in doc
    assert doc["sha256"] is not None
    assert "signed_url" in doc

    # Verify atomic audit write in same transaction
    audit_entry = (
        db.query(WorkflowAuditLog)
        .filter(WorkflowAuditLog.entity_id == UUID(fdr["id"]))
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.action == "fdr.created"
    assert audit_entry.new_status == "submitted"
    assert audit_entry.row_hash is not None


def test_fdr_submission_invalid_file_type(client: TestClient, auth_headers):
    """Verify rejection of unpermitted file types like executable scripts."""
    form_data = {
        "fdr_number": "FDR-INV-FILE-001",
        "bank_name": "State Bank of India",
        "amount": "100000.00",
        "issue_date": "2026-01-15",
        "maturity_date": "2027-01-15",
    }
    files = {"file": ("malicious_payload.exe", b"MZ binary content", "application/octet-stream")}

    response = client.post(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        data=form_data,
        files=files,
    )

    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "INVALID_FILE_TYPE"


def test_fdr_submission_file_too_large(client: TestClient, auth_headers):
    """Verify server-side file size limit enforcement (> 10MB)."""
    form_data = {
        "fdr_number": "FDR-TOO-LARGE-001",
        "bank_name": "State Bank of India",
        "amount": "100000.00",
        "issue_date": "2026-01-15",
        "maturity_date": "2027-01-15",
    }
    # Create 11MB dummy content in memory
    oversized_bytes = b"0" * (11 * 1024 * 1024)
    files = {"file": ("large_scan.pdf", oversized_bytes, "application/pdf")}

    response = client.post(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        data=form_data,
        files=files,
    )

    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "FILE_TOO_LARGE"


def test_fdr_submission_duplicate_conflict(client: TestClient, auth_headers):
    """Verify duplicate (bank_name, fdr_number) produces HTTP 409 FDR_DUPLICATE_NUMBER."""
    form_data = {
        "fdr_number": "39482019482",  # Already present in seed data
        "bank_name": "State Bank of India",
        "amount": "5000000.00",
        "issue_date": "2026-01-15",
        "maturity_date": "2027-01-15",
    }
    files = {"file": ("deposit.pdf", b"%PDF-1.4 dummy", "application/pdf")}

    response = client.post(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        data=form_data,
        files=files,
    )

    assert response.status_code == 409
    err = response.json()["error"]
    assert err["code"] == "FDR_DUPLICATE_NUMBER"


def test_fdr_submission_invalid_dates(client: TestClient, auth_headers):
    """Verify maturity_date <= issue_date is rejected with 400."""
    form_data = {
        "fdr_number": "FDR-DATE-ERR-001",
        "bank_name": "State Bank of India",
        "amount": "5000000.00",
        "issue_date": "2026-06-01",
        "maturity_date": "2026-01-01",  # Before issue date
    }
    files = {"file": ("deposit.pdf", b"%PDF-1.4 dummy", "application/pdf")}

    response = client.post(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        data=form_data,
        files=files,
    )

    assert response.status_code == 400
    err = response.json()["error"]
    assert err["code"] == "INVALID_DATE_SEQUENCE"


def test_fdr_submission_cross_tenant_forbidden(client: TestClient, auth_headers, db):
    """Verify institution user cannot submit on behalf of a different institution."""
    other_inst = (
        db.query(Institution)
        .filter(Institution.id != auth_headers["institution"]["user"].institution_id)
        .first()
    )

    form_data = {
        "fdr_number": "FDR-CROSS-001",
        "bank_name": "State Bank of India",
        "amount": "5000000.00",
        "issue_date": "2026-01-15",
        "maturity_date": "2027-01-15",
        "institution_id": str(other_inst.id),  # Attempting to target another institution
    }
    files = {"file": ("deposit.pdf", b"%PDF-1.4 dummy", "application/pdf")}

    response = client.post(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        data=form_data,
        files=files,
    )

    assert response.status_code == 403
    err = response.json()["error"]
    assert err["code"] == "CROSS_TENANT_FORBIDDEN"


def test_fdr_list_scoping(client: TestClient, auth_headers):
    """Verify GET /api/v1/fdrs automatically restricts institution users to their own records."""
    inst_user = auth_headers["institution"]["user"]

    # Institution request
    inst_resp = client.get(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
    )
    assert inst_resp.status_code == 200
    inst_items = inst_resp.json()["items"]
    assert len(inst_items) > 0
    for item in inst_items:
        assert item["institution_id"] == str(inst_user.institution_id)

    # Officer request sees all institutions
    officer_resp = client.get(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["officer"]["Authorization"]},
    )
    assert officer_resp.status_code == 200
    officer_items = officer_resp.json()["items"]
    assert len(officer_items) >= len(inst_items)


def test_fdr_detail_access_control(client: TestClient, auth_headers, db):
    """Verify institution cannot view FDR detail of another institution."""
    other_fdr = (
        db.query(FDRRecord)
        .filter(FDRRecord.institution_id != auth_headers["institution"]["user"].institution_id)
        .first()
    )

    # Institution user accessing another tenant's FDR
    resp_forbidden = client.get(
        f"/api/v1/fdrs/{other_fdr.id}",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
    )
    assert resp_forbidden.status_code == 403
    assert resp_forbidden.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # Officer accessing same FDR succeeds
    resp_officer = client.get(
        f"/api/v1/fdrs/{other_fdr.id}",
        headers={"Authorization": auth_headers["officer"]["Authorization"]},
    )
    assert resp_officer.status_code == 200
    assert resp_officer.json()["id"] == str(other_fdr.id)


def test_validation_neutral_discrepancy_wording(client: TestClient, auth_headers):
    """Verify validation engine discrepancy flags use strictly neutral terminology."""
    import uuid
    form_data = {
        "fdr_number": f"FDR-DISC-{uuid.uuid4().hex[:6].upper()}",
        "bank_name": "State Bank of India",
        "amount": "2500000.00",  # Entered value differs from OCR
        "issue_date": "2026-01-15",
        "maturity_date": "2027-01-15",
        "extracted_json": '{"amount": {"value": "5000000.00", "confidence": 0.95}}',
    }
    files = {"file": ("deposit.pdf", b"%PDF-1.4 dummy", "application/pdf")}

    response = client.post(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        data=form_data,
        files=files,
    )

    assert response.status_code == 201
    flags = response.json()["validation_flags"]
    amount_flag = next((f for f in flags if f["rule"] == "EXTRACTION_DISCREPANCY_AMOUNT"), None)
    assert amount_flag is not None
    assert amount_flag["severity"] == "warning"
    # Verify neutral tone
    assert "needs review" in amount_flag["message"].lower()
    assert "fraud" not in amount_flag["message"].lower()
    assert "fake" not in amount_flag["message"].lower()


def test_resolve_discrepancy_by_officer(client: TestClient, auth_headers, db):
    """Verify officer can resolve discrepancy with note and audit trail."""
    fdr = db.query(FDRRecord).first()

    # Institution attempt should fail with 403
    resp_inst = client.post(
        f"/api/v1/fdrs/{fdr.id}/resolve-discrepancy",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        json={"outcome": "verified", "resolution_note": "Institution trying to resolve"},
    )
    assert resp_inst.status_code == 403

    # Officer resolution succeeds
    resp_officer = client.post(
        f"/api/v1/fdrs/{fdr.id}/resolve-discrepancy",
        headers={"Authorization": auth_headers["officer"]["Authorization"]},
        json={
            "outcome": "verified",
            "resolution_note": "Verified against physical bank confirmation certificate",
        },
    )
    assert resp_officer.status_code == 200
    assert resp_officer.json()["verification_status"] == "verified"
