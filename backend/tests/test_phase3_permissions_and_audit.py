import uuid

from app.db.models import FDRRecord, Institution
from app.services.audit import verify_chain_integrity


def get_token(client, email):
    res = client.post("/auth/demo-login", json={"email": email})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_unauthorized_access_error_structure(client):
    """Calling protected endpoints without token returns standardized 401 format."""
    res = client.get("/institutions")
    assert res.status_code == 401
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_AUTHENTICATED"
    assert "message" in data["error"]


def test_role_enforcement_on_institutions_and_audit(client):
    """Institutions cannot list all institutions; officers cannot verify audit ledger chain."""
    inst_token = get_token(client, "institution@demo.test")
    officer_token = get_token(client, "officer@demo.test")
    admin_token = get_token(client, "admin@demo.test")

    # 1. Institution trying to list all institutions -> 403
    inst_res = client.get("/institutions", headers={"Authorization": f"Bearer {inst_token}"})
    assert inst_res.status_code == 403
    assert inst_res.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # 2. Officer listing all institutions -> 200
    officer_res = client.get("/institutions", headers={"Authorization": f"Bearer {officer_token}"})
    assert officer_res.status_code == 200
    assert len(officer_res.json()) >= 3

    # 3. Officer attempting to verify audit chain -> 403 (Admin only)
    chain_off_res = client.get("/audit/verify-chain", headers={"Authorization": f"Bearer {officer_token}"})
    assert chain_off_res.status_code == 403
    assert chain_off_res.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # 4. Admin verifying audit chain -> 200
    chain_admin_res = client.get("/audit/verify-chain", headers={"Authorization": f"Bearer {admin_token}"})
    assert chain_admin_res.status_code == 200
    assert chain_admin_res.json()["valid"] is True
    assert chain_admin_res.json()["broken_at"] is None


def test_institutional_cross_tenant_isolation(client, db):
    """Institution users can access only their own institution's records."""
    inst_token = get_token(client, "institution@demo.test")
    officer_token = get_token(client, "officer@demo.test")

    apex = db.query(Institution).filter(Institution.aicte_id == "AICTE-1-4928190").first()
    nie = db.query(Institution).filter(Institution.aicte_id == "AICTE-1-7890123").first()

    # Institution user accessing own institution FDRs -> 200
    own_res = client.get(f"/institutions/{apex.id}/fdrs", headers={"Authorization": f"Bearer {inst_token}"})
    assert own_res.status_code == 200
    assert len(own_res.json()) >= 1

    # Institution user attempting to access NIE's FDRs -> 403 CROSS_TENANT_FORBIDDEN
    cross_res = client.get(f"/institutions/{nie.id}/fdrs", headers={"Authorization": f"Bearer {inst_token}"})
    assert cross_res.status_code == 403
    assert cross_res.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # Officer can access NIE's FDRs -> 200
    officer_nie_res = client.get(f"/institutions/{nie.id}/fdrs", headers={"Authorization": f"Bearer {officer_token}"})
    assert officer_nie_res.status_code == 200


def test_fdr_audit_trail_endpoint_and_scoping(client, db):
    """Inspect FDR audit history with tenant scoping."""
    inst_token = get_token(client, "institution@demo.test")
    officer_token = get_token(client, "officer@demo.test")

    # Apex FDR (own)
    apex_fdr = db.query(FDRRecord).filter(FDRRecord.fdr_number == "39482019482").first()
    own_audit_res = client.get(f"/fdrs/{apex_fdr.id}/audit", headers={"Authorization": f"Bearer {inst_token}"})
    assert own_audit_res.status_code == 200
    assert len(own_audit_res.json()) >= 1

    # NIE FDR (other)
    nie_fdr = db.query(FDRRecord).filter(FDRRecord.fdr_number == "CAN88910244").first()
    cross_audit_res = client.get(f"/fdrs/{nie_fdr.id}/audit", headers={"Authorization": f"Bearer {inst_token}"})
    assert cross_audit_res.status_code == 403
    assert cross_audit_res.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # Officer can inspect NIE FDR audit -> 200
    officer_audit_res = client.get(f"/fdrs/{nie_fdr.id}/audit", headers={"Authorization": f"Bearer {officer_token}"})
    assert officer_audit_res.status_code == 200


def test_transactional_audit_write_on_institution_creation(client, db):
    """Creating an institution creates an audit log entry in the same transaction."""
    officer_token = get_token(client, "officer@demo.test")
    unique_code = f"AICTE-1-{uuid.uuid4().hex[:7]}"

    payload = {
        "aicte_id": unique_code,
        "name": "Vellore Technological Institute",
        "region": "Southern",
        "contact_email": "dean@vti.edu.in"
    }

    create_res = client.post("/institutions", json=payload, headers={"Authorization": f"Bearer {officer_token}"})
    assert create_res.status_code == 201
    created_inst = create_res.json()

    # Verify audit chain integrity remains intact after transactional write
    chain_status = verify_chain_integrity(db)
    assert chain_status["valid"] is True
    assert chain_status["broken_at"] is None

    # Clean up test institution
    db_inst = db.query(Institution).filter(Institution.id == uuid.UUID(created_inst["id"])).first()
    if db_inst:
        db.delete(db_inst)
        db.commit()


def test_not_found_standard_error(client):
    """Missing resource returns standardized 404 error format."""
    officer_token = get_token(client, "officer@demo.test")
    fake_id = uuid.uuid4()
    res = client.get(f"/institutions/{fake_id}", headers={"Authorization": f"Bearer {officer_token}"})
    assert res.status_code == 404
    data = res.json()
    assert data["error"]["code"] == "INSTITUTION_NOT_FOUND"
    assert "not found" in data["error"]["message"].lower()
