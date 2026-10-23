import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_download_token
from app.db.models import (
    FDRDocument,
    FDRRecord,
    Institution,
    InstrumentStatus,
    User,
    UserRole,
    VerificationStatus,
    WorkflowStatus,
)
from app.main import app


def make_auth_header(user: User) -> dict:
    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "institution_id": str(user.institution_id) if user.institution_id else None,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def security_test_env(db: Session):
    """
    Creates isolated test institutions, users, and FDRs for testing tenancy and scoping:
    - Institution A (Inst A User)
    - Institution B (Inst B User)
    - Unaffiliated Institution User (institution_id=None)
    - Scoped Officer (assigned to Institution A)
    - Central Officer (institution_id=None)
    - Council Admin
    """
    unique_suffix = uuid.uuid4().hex[:6]

    # 1. Institutions
    inst_a = Institution(
        aicte_id=f"TEST-A-{unique_suffix}",
        name=f"Apex Institute of Tech {unique_suffix}",
        region="Northern",
        contact_email=f"apex_{unique_suffix}@example.edu",
    )
    inst_b = Institution(
        aicte_id=f"TEST-B-{unique_suffix}",
        name=f"Bharat Engineering College {unique_suffix}",
        region="Western",
        contact_email=f"bharat_{unique_suffix}@example.edu",
    )
    db.add_all([inst_a, inst_b])
    db.commit()
    db.refresh(inst_a)
    db.refresh(inst_b)

    # 2. Users
    user_inst_a = User(
        email=f"user_a_{unique_suffix}@apex.edu",
        full_name="Registrar Inst A",
        role=UserRole.institution,
        institution_id=inst_a.id,
    )
    user_inst_b = User(
        email=f"user_b_{unique_suffix}@bharat.edu",
        full_name="Registrar Inst B",
        role=UserRole.institution,
        institution_id=inst_b.id,
    )
    user_unaffiliated = User(
        email=f"unaffiliated_{unique_suffix}@portal.local",
        full_name="Unassigned User",
        role=UserRole.institution,
        institution_id=None,
    )
    officer_scoped_a = User(
        email=f"officer_a_{unique_suffix}@aicte.gov.in",
        full_name="Regional Officer A",
        role=UserRole.officer,
        institution_id=inst_a.id,
    )
    officer_central = User(
        email=f"officer_central_{unique_suffix}@aicte.gov.in",
        full_name="Vigilance Officer Central",
        role=UserRole.officer,
        institution_id=None,
    )
    admin_user = User(
        email=f"admin_{unique_suffix}@aicte.gov.in",
        full_name="Council Administrator",
        role=UserRole.admin,
        institution_id=None,
    )
    db.add_all([user_inst_a, user_inst_b, user_unaffiliated, officer_scoped_a, officer_central, admin_user])
    db.commit()

    # 3. FDRs & Documents
    today = date.today()
    fdr_a = FDRRecord(
        institution_id=inst_a.id,
        fdr_number=f"FDR-A-{unique_suffix}",
        bank_name="State Bank of India",
        branch="Main Branch",
        amount=Decimal("3500000.00"),
        issue_date=today - timedelta(days=60),
        maturity_date=today + timedelta(days=300),
        instrument_status=InstrumentStatus.active,
        verification_status=VerificationStatus.verified,
        workflow_status=WorkflowStatus.none,
        submitted_by=user_inst_a.id,
    )
    fdr_b = FDRRecord(
        institution_id=inst_b.id,
        fdr_number=f"FDR-B-{unique_suffix}",
        bank_name="Punjab National Bank",
        branch="Central Branch",
        amount=Decimal("7500000.00"),
        issue_date=today - timedelta(days=90),
        maturity_date=today + timedelta(days=270),
        instrument_status=InstrumentStatus.active,
        verification_status=VerificationStatus.verified,
        workflow_status=WorkflowStatus.none,
        submitted_by=user_inst_b.id,
    )
    db.add_all([fdr_a, fdr_b])
    db.commit()
    db.refresh(fdr_a)
    db.refresh(fdr_b)

    doc_a = FDRDocument(
        fdr_id=fdr_a.id,
        storage_path=f"fdr_documents/{inst_a.id}/sample_a.pdf",
        doc_type="fdr_receipt",
        sha256="a" * 64,
        uploaded_by=user_inst_a.id,
    )
    doc_b = FDRDocument(
        fdr_id=fdr_b.id,
        storage_path=f"fdr_documents/{inst_b.id}/sample_b.pdf",
        doc_type="fdr_receipt",
        sha256="b" * 64,
        uploaded_by=user_inst_b.id,
    )
    db.add_all([doc_a, doc_b])
    db.commit()
    db.refresh(doc_a)
    db.refresh(doc_b)

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_inst_a": user_inst_a,
        "user_inst_b": user_inst_b,
        "user_unaffiliated": user_unaffiliated,
        "officer_scoped_a": officer_scoped_a,
        "officer_central": officer_central,
        "admin": admin_user,
        "fdr_a": fdr_a,
        "fdr_b": fdr_b,
        "doc_a": doc_a,
        "doc_b": doc_b,
    }


def test_unauthenticated_access_denied():
    """Verify that unauthenticated callers cannot access reports, FDRs, or dashboard telemetry."""
    client = TestClient(app)

    endpoints = [
        "/reports/data",
        "/reports/export",
        "/reports/ledger-export",
        "/dashboard/summary",
        "/dashboard/charts",
        "/dashboard/priority-cases",
        "/fdrs",
        "/release/requests",
    ]

    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 401, f"Expected 401 for unauthenticated request to {ep}, got {resp.status_code}"


def test_institution_own_reports_and_deposits_allowed(security_test_env):
    """Verify that an institution's users can access FDR reports and deposit amounts for their own institution."""
    client = TestClient(app)
    env = security_test_env
    headers_a = make_auth_header(env["user_inst_a"])

    # 1. Reports Data
    res = client.get("/reports/data", headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert "records" in data
    # All records in the report must belong to Institution A
    for rec in data["records"]:
        assert rec["fdr_number"] == env["fdr_a"].fdr_number
        assert rec["amount"] == 3500000.00

    # 2. Excel & CSV Exports
    res_exp = client.get("/reports/export", headers=headers_a)
    assert res_exp.status_code == 200

    res_csv = client.get("/reports/ledger-export?format=csv", headers=headers_a)
    assert res_csv.status_code == 200
    assert env["fdr_a"].fdr_number in res_csv.text
    assert env["fdr_b"].fdr_number not in res_csv.text

    # 3. Dashboard Telemetry
    res_dash = client.get("/dashboard/summary", headers=headers_a)
    assert res_dash.status_code == 200
    dash_data = res_dash.json()
    # Total active amount should match Institution A's FDR only
    assert float(dash_data["total_active_amount"]) == 3500000.00


def test_cross_tenant_report_access_denied(security_test_env):
    """Verify that an institution cannot query or view another institution's reports or deposit amounts."""
    client = TestClient(app)
    env = security_test_env
    headers_a = make_auth_header(env["user_inst_a"])
    inst_b_id = str(env["inst_b"].id)

    # 1. Attempting cross-tenant report data
    res_data = client.get(f"/reports/data?institution_id={inst_b_id}", headers=headers_a)
    assert res_data.status_code == 403
    assert res_data.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # 2. Attempting cross-tenant export
    res_exp = client.get(f"/reports/export?institution_id={inst_b_id}", headers=headers_a)
    assert res_exp.status_code == 403
    assert res_exp.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # 3. Attempting cross-tenant ledger export
    res_ledger = client.get(f"/reports/ledger-export?institution_id={inst_b_id}", headers=headers_a)
    assert res_ledger.status_code == 403
    assert res_ledger.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # 4. Attempting cross-tenant dashboard summary & charts
    res_dash = client.get(f"/dashboard/summary?institution_id={inst_b_id}", headers=headers_a)
    assert res_dash.status_code == 403
    assert res_dash.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    res_charts = client.get(f"/dashboard/charts?institution_id={inst_b_id}", headers=headers_a)
    assert res_charts.status_code == 403
    assert res_charts.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # 5. Attempting cross-tenant FDR listing
    res_fdrs = client.get(f"/fdrs?institution_id={inst_b_id}", headers=headers_a)
    assert res_fdrs.status_code == 403
    assert res_fdrs.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"


def test_unaffiliated_user_access_denied(security_test_env):
    """Verify that an institution user without an institution association is rejected."""
    client = TestClient(app)
    env = security_test_env
    headers_unaffiliated = make_auth_header(env["user_unaffiliated"])

    # Reports
    res_rep = client.get("/reports/data", headers=headers_unaffiliated)
    assert res_rep.status_code == 403
    assert res_rep.json()["error"]["code"] == "NO_INSTITUTION_AFFILIATION"

    # Dashboard
    res_dash = client.get("/dashboard/summary", headers=headers_unaffiliated)
    assert res_dash.status_code == 403
    assert res_dash.json()["error"]["code"] == "NO_INSTITUTION_AFFILIATION"

    # FDRs
    res_fdrs = client.get("/fdrs", headers=headers_unaffiliated)
    assert res_fdrs.status_code == 403
    assert res_fdrs.json()["error"]["code"] == "NO_INSTITUTION_AFFILIATION"


def test_cross_tenant_fdr_detail_and_document_download_denied(security_test_env):
    """Verify that an institution cannot view details or download documents of another institution."""
    client = TestClient(app)
    env = security_test_env
    headers_a = make_auth_header(env["user_inst_a"])

    # 1. Detail view of FDR B
    res_fdr = client.get(f"/fdrs/{env['fdr_b'].id}", headers=headers_a)
    assert res_fdr.status_code == 403
    assert res_fdr.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # 2. Document download of Doc B using credentials
    res_doc = client.get(f"/fdrs/documents/{env['doc_b'].id}/download", headers=headers_a)
    assert res_doc.status_code == 403

    # 3. Cross-tenant token forgery: user A generates a token for Doc B with inst_id of Inst A
    forged_token = create_download_token(
        document_id=env["doc_b"].id,
        user_id=env["user_inst_a"].id,
        institution_id=env["inst_a"].id,
        expires_in_minutes=15,
    )
    res_forged = client.get(f"/fdrs/documents/{env['doc_b'].id}/download?token={forged_token}")
    assert res_forged.status_code == 403
    assert res_forged.json()["error"]["code"] == "CROSS_TENANT_DOWNLOAD"


def test_admin_global_access(security_test_env):
    """Verify that council administrators can view all institutions' reports, summaries, and records."""
    client = TestClient(app)
    env = security_test_env
    headers_admin = make_auth_header(env["admin"])

    # Admin accesses reports across all institutions
    res_rep = client.get("/reports/data", headers=headers_admin)
    assert res_rep.status_code == 200
    data = res_rep.json()
    fdr_numbers = [r["fdr_number"] for r in data["records"]]
    assert env["fdr_a"].fdr_number in fdr_numbers
    assert env["fdr_b"].fdr_number in fdr_numbers

    # Admin can filter by specific institution
    res_filt = client.get(f"/reports/data?institution_id={env['inst_a'].id}", headers=headers_admin)
    assert res_filt.status_code == 200
    filt_numbers = [r["fdr_number"] for r in res_filt.json()["records"]]
    assert env["fdr_a"].fdr_number in filt_numbers
    assert env["fdr_b"].fdr_number not in filt_numbers

    # Admin can view dashboard priority cases
    res_pc = client.get("/dashboard/priority-cases", headers=headers_admin)
    assert res_pc.status_code == 200


def test_official_scoped_access(security_test_env):
    """
    Verify official scoping:
    - Scoped Officer (assigned to Institution A) is permitted for Institution A, denied for Institution B.
    - Central Officer (institution_id=None) has council-wide access.
    """
    client = TestClient(app)
    env = security_test_env
    headers_scoped = make_auth_header(env["officer_scoped_a"])
    headers_central = make_auth_header(env["officer_central"])

    # 1. Scoped officer accessing assigned institution
    res_own = client.get("/reports/data", headers=headers_scoped)
    assert res_own.status_code == 200
    for rec in res_own.json()["records"]:
        assert rec["fdr_number"] == env["fdr_a"].fdr_number

    # 2. Scoped officer attempting to access foreign institution
    res_foreign = client.get(f"/reports/data?institution_id={env['inst_b'].id}", headers=headers_scoped)
    assert res_foreign.status_code == 403
    assert res_foreign.json()["error"]["code"] == "OFFICER_SCOPE_EXCEEDED"

    # 3. Scoped officer attempting to view foreign FDR detail
    res_fdr_b = client.get(f"/fdrs/{env['fdr_b'].id}", headers=headers_scoped)
    assert res_fdr_b.status_code == 403
    assert res_fdr_b.json()["error"]["code"] == "OFFICER_SCOPE_EXCEEDED"

    # 4. Central officer has council-wide access
    res_central = client.get("/reports/data", headers=headers_central)
    assert res_central.status_code == 200
    central_numbers = [r["fdr_number"] for r in res_central.json()["records"]]
    assert env["fdr_a"].fdr_number in central_numbers
    assert env["fdr_b"].fdr_number in central_numbers


def test_tampered_and_expired_download_token_rejected(security_test_env):
    """Verify that invalid or expired download tokens are strictly rejected."""
    client = TestClient(app)
    env = security_test_env

    # 1. Expired token (delta = -10 minutes)
    expired_token = create_download_token(
        document_id=env["doc_a"].id,
        user_id=env["user_inst_a"].id,
        institution_id=env["inst_a"].id,
        expires_in_minutes=-10,
    )
    res_exp = client.get(f"/fdrs/documents/{env['doc_a'].id}/download?token={expired_token}")
    assert res_exp.status_code == 401
    assert res_exp.json()["error"]["code"] == "EXPIRED_OR_INVALID_DOWNLOAD_TOKEN"

    # 2. Tampered token string
    res_tampered = client.get(f"/fdrs/documents/{env['doc_a'].id}/download?token=fake.tampered.jwttoken")
    assert res_tampered.status_code == 401

    # 3. Token document ID mismatch
    mismatched_token = create_download_token(
        document_id=env["doc_b"].id,
        user_id=env["user_inst_a"].id,
        institution_id=env["inst_a"].id,
        expires_in_minutes=15,
    )
    res_mismatch = client.get(f"/fdrs/documents/{env['doc_a'].id}/download?token={mismatched_token}")
    assert res_mismatch.status_code == 403
    assert res_mismatch.json()["error"]["code"] == "TOKEN_MISMATCH"
