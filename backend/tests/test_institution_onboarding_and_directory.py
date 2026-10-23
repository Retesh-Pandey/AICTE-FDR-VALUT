import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.db.models import (
    Institution,
    InstitutionRegistrationRequest,
    RegistrationRequestStatus,
    User,
    UserRole,
    FDRRecord,
)
from app.db.session import SessionLocal

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def auth_tokens(db):
    officer_user = db.query(User).filter(User.role == UserRole.officer).first()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()
    inst_user = db.query(User).filter(User.role == UserRole.institution).first()

    return {
        "officer": create_access_token({"sub": str(officer_user.id), "email": officer_user.email}),
        "admin": create_access_token({"sub": str(admin_user.id), "email": admin_user.email}),
        "institution": create_access_token({"sub": str(inst_user.id), "email": inst_user.email}),
        "inst_user": inst_user,
    }


def test_public_institution_search(db):
    """Test type-ahead autocomplete search by name and AICTE ID."""
    # 1. Search by name 'Apex'
    res = client.get("/api/v1/institutions/public-search?q=Apex")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert any("Apex" in item["name"] for item in data)
    assert "aicte_id" in data[0]
    assert "source" in data[0]

    # 2. Search by AICTE permanent ID
    res_id = client.get("/api/v1/institutions/public-search?q=AICTE-1-4928190")
    assert res_id.status_code == 200
    data_id = res_id.json()
    assert len(data_id) >= 1
    assert data_id[0]["aicte_id"] == "AICTE-1-4928190"

    # 3. Search non-existent institution
    res_none = client.get("/api/v1/institutions/public-search?q=NonExistentPolytechnic999")
    assert res_none.status_code == 200
    assert len(res_none.json()) == 0


def test_institution_directory_pagination_and_disclosure(db):
    """Test paginated directory browsing with coverage disclosure and synchronization metadata."""
    res = client.get("/api/v1/institutions/directory?page=1&limit=2")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pages" in data
    assert "source_label" in data
    assert "coverage_disclaimer" in data
    assert len(data["items"]) <= 2
    assert "registered institutions in this portal" in data["source_label"].lower()
    assert "registered" in data["coverage_disclaimer"].lower()


def test_institution_registration_request_and_duplicate_prevention(db):
    """Test filing a new registration request and detecting duplicates."""
    unique_suffix = uuid.uuid4().hex[:6]
    college_name = f"Zenith Engineering College {unique_suffix}"
    official_email = f"registrar_{unique_suffix}@zenith.edu.in"
    aicte_id = f"AICTE-1-{unique_suffix.upper()}"

    payload = {
        "institution_name": college_name,
        "aicte_id": aicte_id,
        "contact_person": "Dr. S. Nair, Director",
        "official_email": official_email,
        "region": "Southern",
        "address": "Campus Road, Kochi, Kerala - 682022",
    }

    # 1. Submit valid onboarding request
    res = client.post("/api/v1/institutions/register-request", json=payload)
    assert res.status_code == 201
    created_req = res.json()
    assert created_req["institution_name"] == college_name
    assert created_req["status"] == "pending_verification"
    assert created_req["tracking_reference"].startswith("REG-")
    assert "pending_verification" in created_req["notice"]

    # 2. Attempt duplicate submission with same email
    res_dup = client.post("/api/v1/institutions/register-request", json=payload)
    assert res_dup.status_code == 409
    dup_err = res_dup.json()
    assert "already pending review" in dup_err["error"]["message"].lower()

    # 3. Attempt duplicate submission against existing active college
    active_inst = db.query(Institution).first()
    res_active_dup = client.post(
        "/api/v1/institutions/register-request",
        json={
            "institution_name": active_inst.name,
            "aicte_id": active_inst.aicte_id,
            "contact_person": "Prof. Test",
            "official_email": "new_email@test.edu.in",
        },
    )
    assert res_active_dup.status_code == 409
    assert "already registered" in res_active_dup.json()["error"]["message"].lower()


def test_pending_registration_isolation_from_signin(db):
    """Test that applicants with pending registrations CANNOT sign in or access tenant data."""
    unique_suffix = uuid.uuid4().hex[:6]
    pending_email = f"applicant_{unique_suffix}@unapproved.edu.in"

    # Create pending registration request
    req = InstitutionRegistrationRequest(
        institution_name=f"Unapproved Institute {unique_suffix}",
        aicte_id=f"AICTE-UNAPP-{unique_suffix}",
        contact_person="Unapproved Custodian",
        official_email=pending_email,
        region="Northern",
        status=RegistrationRequestStatus.pending_verification,
    )
    db.add(req)
    db.commit()

    # Attempt to sign in with this pending applicant's email
    res_login = client.post(
        "/api/v1/auth/login",
        json={"email": pending_email, "password": "AnyPassword123!"},
    )
    assert res_login.status_code == 403
    assert res_login.json()["error"]["code"] == "INSTITUTION_REGISTRATION_PENDING"
    assert "pending verification" in res_login.json()["error"]["message"].lower()


def test_officer_review_and_approval_flow(db, auth_tokens):
    """Test that an authorized Officer/Admin can review and approve a registration request, activating the institution."""
    unique_suffix = uuid.uuid4().hex[:6]
    college_name = f"Aryabhatta Institute of Science {unique_suffix}"
    official_email = f"director_{unique_suffix}@aryabhatta.edu.in"

    req = InstitutionRegistrationRequest(
        institution_name=college_name,
        contact_person="Dr. A. Verma",
        official_email=official_email,
        region="Western",
        status=RegistrationRequestStatus.pending_verification,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # 1. Institution users cannot review registration requests (403 Forbidden)
    res_unauth = client.post(
        f"/api/v1/institutions/registration-requests/{req.id}/review",
        json={"decision": "approved", "review_reason": "Attempt by non-officer"},
        headers={"Authorization": f"Bearer {auth_tokens['institution']}"},
    )
    assert res_unauth.status_code == 403

    # 2. Officer reviews and approves the request
    res_approve = client.post(
        f"/api/v1/institutions/registration-requests/{req.id}/review",
        json={
            "decision": "approved",
            "review_reason": "Verified against Maharashtra State Technical Directorate gazette notification 2024.",
        },
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
    )
    assert res_approve.status_code == 200
    approved_data = res_approve.json()
    assert approved_data["status"] == "approved"
    assert approved_data["review_decision"] == "approved"

    # Verify active institution was created in database
    activated_inst = db.query(Institution).filter(Institution.contact_email == official_email).first()
    assert activated_inst is not None
    assert activated_inst.name == college_name
    assert activated_inst.source == "APPROVED_REQUEST"


def test_tenant_isolation_enforcement(db, auth_tokens):
    """Test that institution users can only access their own institution records and cannot access others."""
    # Active institutions in DB
    inst1 = db.query(Institution).filter(Institution.name.like("%Apex%")).first()
    other_inst = db.query(Institution).filter(Institution.id != inst1.id).first()

    # Institution user accessing their own institution details
    res_own = client.get(
        f"/api/v1/institutions/{inst1.id}",
        headers={"Authorization": f"Bearer {auth_tokens['institution']}"},
    )
    assert res_own.status_code == 200

    # Institution user attempting cross-tenant access to another institution
    res_other = client.get(
        f"/api/v1/institutions/{other_inst.id}",
        headers={"Authorization": f"Bearer {auth_tokens['institution']}"},
    )
    assert res_other.status_code == 403
    assert res_other.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # Officer can access all institutions
    res_officer = client.get(
        f"/api/v1/institutions/{other_inst.id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
    )
    assert res_officer.status_code == 200
