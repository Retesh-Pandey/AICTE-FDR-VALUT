import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import FDRRecord, Institution, User, UserRole, WorkflowAuditLog
from app.main import app
from app.services.audit import (
    compute_row_hash,
    format_timestamp,
    verify_chain_integrity,
    write_audit_log,
)


def get_auth_header(user: User) -> dict:
    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "institution_id": str(user.institution_id) if user.institution_id else None,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_clean_chain_verification(db: Session):
    """Test that a sequence of chained audit events passes integrity verification."""
    # Write a few sequential audit logs
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    actor_id = admin.id if admin else uuid.uuid4()

    write_audit_log(
        db=db,
        action="TEST_ACTION_1",
        entity="fdr",
        actor_id=actor_id,
        actor_role="admin",
        old_status=None,
        new_status="submitted",
        remarks="Block 1 created",
    )
    write_audit_log(
        db=db,
        action="TEST_ACTION_2",
        entity="fdr",
        actor_id=actor_id,
        actor_role="admin",
        old_status="submitted",
        new_status="under_review",
        remarks="Block 2 created",
    )
    db.commit()

    result = verify_chain_integrity(db)
    assert result["valid"] is True
    assert result["broken_at"] is None
    assert result["total_blocks"] >= 2
    assert result["head_hash"] is not None


def test_tamper_detection_on_row_content(db: Session):
    """
    Test that modifying any column in an existing audit row
    (e.g. remarks or status) is immediately detected by verify_chain_integrity.
    """
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    actor_id = admin.id if admin else uuid.uuid4()

    # Append a known audit entry
    log_entry = write_audit_log(
        db=db,
        action="SECURITY_CHECK_EVENT",
        entity="fdr",
        actor_id=actor_id,
        actor_role="admin",
        old_status="approved",
        new_status="completed",
        remarks="Authentic audit record prior to malicious tampering.",
    )
    db.commit()
    target_id = log_entry.id

    # Verify clean state before tampering
    res_before = verify_chain_integrity(db)
    assert res_before["valid"] is True

    # Tamper with the row in the database directly
    tampered_log = db.query(WorkflowAuditLog).filter(WorkflowAuditLog.id == target_id).first()
    tampered_log.remarks = "Malicious modification attempted by unauthorized actor."
    db.commit()

    # Verify that the integrity verification algorithm flags the exact corrupted block id
    res_after = verify_chain_integrity(db)
    assert res_after["valid"] is False
    assert res_after["broken_at"] == target_id

    # Restore remarks and recompute correct hash to heal test database state
    tampered_log.remarks = "Authentic audit record prior to malicious tampering."
    correct_hash = compute_row_hash(
        prev_hash=tampered_log.prev_hash,
        actor_id=tampered_log.actor_id,
        action=tampered_log.action,
        entity=tampered_log.entity,
        entity_id=tampered_log.entity_id,
        old_status=tampered_log.old_status,
        new_status=tampered_log.new_status,
        remarks=tampered_log.remarks,
        payload=tampered_log.payload,
        created_at_iso=format_timestamp(tampered_log.created_at),
    )
    tampered_log.row_hash = correct_hash
    db.commit()

    assert verify_chain_integrity(db)["valid"] is True


def test_tamper_detection_on_prev_hash_linkage(db: Session):
    """
    Test that tampering with the predecessor hash link breaks chain verification.
    """
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    actor_id = admin.id if admin else uuid.uuid4()

    log_entry = write_audit_log(
        db=db,
        action="LINKAGE_TEST_EVENT",
        entity="fdr",
        actor_id=actor_id,
        actor_role="admin",
        old_status="pending",
        new_status="active",
        remarks="Testing linkage tamper detection.",
    )
    db.commit()
    target_id = log_entry.id
    original_prev_hash = log_entry.prev_hash

    # Corrupt prev_hash
    target_log = db.query(WorkflowAuditLog).filter(WorkflowAuditLog.id == target_id).first()
    target_log.prev_hash = "deadbeef" * 8
    db.commit()

    res = verify_chain_integrity(db)
    assert res["valid"] is False
    assert res["broken_at"] == target_id

    # Restore
    target_log.prev_hash = original_prev_hash
    target_log.row_hash = compute_row_hash(
        prev_hash=target_log.prev_hash,
        actor_id=target_log.actor_id,
        action=target_log.action,
        entity=target_log.entity,
        entity_id=target_log.entity_id,
        old_status=target_log.old_status,
        new_status=target_log.new_status,
        remarks=target_log.remarks,
        payload=target_log.payload,
        created_at_iso=format_timestamp(target_log.created_at),
    )
    db.commit()


def test_audit_immutable_no_modification_endpoints(db: Session):
    """
    Verify that audit entries CANNOT be modified or deleted through normal application endpoints.
    No PUT, PATCH, or DELETE endpoints exist for audit logs.
    """
    client = TestClient(app)
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    headers = get_auth_header(admin)

    fdr = db.query(FDRRecord).first()
    fdr_id = str(fdr.id) if fdr else str(uuid.uuid4())

    # Attempting to mutate audit via API returns 404 or 405 (Method Not Allowed)
    res_put = client.put(f"/fdrs/{fdr_id}/audit", json={"remarks": "tampered"}, headers=headers)
    assert res_put.status_code in [404, 405]

    res_patch = client.patch(f"/fdrs/{fdr_id}/audit", json={"remarks": "tampered"}, headers=headers)
    assert res_patch.status_code in [404, 405]

    res_del = client.delete(f"/fdrs/{fdr_id}/audit", headers=headers)
    assert res_del.status_code in [404, 405]

    res_del_all = client.delete("/audit/verify-chain", headers=headers)
    assert res_del_all.status_code in [404, 405]


def test_audit_api_role_and_tenant_enforcement(db: Session):
    """
    Test role enforcement on /audit/verify-chain (Admin only)
    and institutional tenant isolation on /fdrs/{id}/audit.
    """
    client = TestClient(app)

    # 1. Non-admin accessing verify-chain gets 403
    officer = db.query(User).filter(User.role == UserRole.officer).first()
    officer_headers = get_auth_header(officer)
    res_officer_verify = client.get("/audit/verify-chain", headers=officer_headers)
    assert res_officer_verify.status_code == 403

    inst_user = db.query(User).filter(User.role == UserRole.institution).first()
    inst_headers = get_auth_header(inst_user)
    res_inst_verify = client.get("/audit/verify-chain", headers=inst_headers)
    assert res_inst_verify.status_code == 403

    # Admin accessing verify-chain succeeds
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    admin_headers = get_auth_header(admin)
    res_admin_verify = client.get("/audit/verify-chain", headers=admin_headers)
    assert res_admin_verify.status_code == 200
    assert "valid" in res_admin_verify.json()

    # 2. Cross-tenant isolation on /fdrs/{id}/audit
    # Create two institutions
    uid = uuid.uuid4().hex[:6]
    inst_a = Institution(name="Inst A", aicte_id=f"INST-A-{uid}", region="Delhi")
    inst_b = Institution(name="Inst B", aicte_id=f"INST-B-{uid}", region="Maharashtra")
    db.add_all([inst_a, inst_b])
    db.commit()

    user_a = User(email=f"tenant_a_{uid}@test.com", role=UserRole.institution, institution_id=inst_a.id)
    user_b = User(email=f"tenant_b_{uid}@test.com", role=UserRole.institution, institution_id=inst_b.id)
    db.add_all([user_a, user_b])

    today = datetime.now(timezone.utc).date()
    fdr_b = FDRRecord(
        fdr_number=f"FDR-TENANT-B-{uid}",
        institution_id=inst_b.id,
        bank_name="Canara Bank",
        amount=Decimal("500000.00"),
        issue_date=today,
        maturity_date=today.replace(year=today.year + 1),
    )
    db.add(fdr_b)
    db.commit()

    # User A tries to view audit of FDR B -> 403 FORBIDDEN
    headers_a = get_auth_header(user_a)
    res_cross = client.get(f"/fdrs/{fdr_b.id}/audit", headers=headers_a)
    assert res_cross.status_code == 403
    assert res_cross.json()["error"]["code"] == "CROSS_TENANT_FORBIDDEN"

    # User B views own FDR audit -> 200 OK
    headers_b = get_auth_header(user_b)
    res_own = client.get(f"/fdrs/{fdr_b.id}/audit", headers=headers_b)
    assert res_own.status_code == 200
    assert isinstance(res_own.json(), list)


def test_unauthenticated_audit_verify_rejected():
    """Unauthenticated access to verify-chain must return 401 Unauthorized."""
    client = TestClient(app)
    res_root = client.get("/audit/verify-chain")
    assert res_root.status_code == 401
    assert res_root.json()["error"]["code"] == "NOT_AUTHENTICATED"

    res_v1 = client.get("/api/v1/audit/verify-chain")
    assert res_v1.status_code == 401
    assert res_v1.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_audit_verify_chain_response_telemetry_schema(db: Session):
    """Admin verify-chain must return complete telemetry schema including timing and head hash."""
    client = TestClient(app)
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    headers = get_auth_header(admin)

    res = client.get("/audit/verify-chain", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "valid" in data
    assert "broken_at" in data
    assert "total_blocks" in data
    assert "head_hash" in data
    assert "verified_at" in data
    assert "verification_time_ms" in data
    assert "message" in data

    assert data["valid"] is True
    assert data["broken_at"] is None
    assert data["total_blocks"] >= 1
    assert isinstance(data["verification_time_ms"], (int, float))
    assert data["verification_time_ms"] >= 0
    assert data["verified_at"] is not None


def test_empty_ledger_verification():
    """Empty audit ledger returns valid: True, 0 blocks, and genesis baseline intact."""
    from unittest.mock import MagicMock
    mock_db = MagicMock(spec=Session)
    mock_db.query.return_value.order_by.return_value.all.return_value = []

    res = verify_chain_integrity(mock_db)
    assert res["valid"] is True
    assert res["broken_at"] is None
    assert res["total_blocks"] == 0
    assert res["head_hash"] is None
    assert "Empty audit ledger" in res["message"]
    assert res["verification_time_ms"] >= 0


def test_api_surfaces_tampered_block_to_admin(db: Session):
    """When a row is modified in the DB, GET /audit/verify-chain returns valid: False and broken_at."""
    client = TestClient(app)
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    headers = get_auth_header(admin)

    # Append test row
    test_entry = write_audit_log(
        db=db,
        action="TEST_API_TAMPER",
        entity="fdr",
        actor_id=admin.id,
        actor_role="admin",
        old_status=None,
        new_status="active",
        remarks="Pre-tamper remarks for API check",
    )
    db.commit()
    target_id = test_entry.id

    # Tamper with row remarks
    target_row = db.query(WorkflowAuditLog).filter(WorkflowAuditLog.id == target_id).first()
    target_row.remarks = "Direct unauthorized DB modification"
    db.commit()

    try:
        res = client.get("/audit/verify-chain", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert data["broken_at"] == target_id
        assert "Tampered row detected" in data["message"]
    finally:
        # Heal row for database consistency
        target_row.remarks = "Pre-tamper remarks for API check"
        target_row.row_hash = compute_row_hash(
            prev_hash=target_row.prev_hash,
            actor_id=target_row.actor_id,
            action=target_row.action,
            entity=target_row.entity,
            entity_id=target_row.entity_id,
            old_status=target_row.old_status,
            new_status=target_row.new_status,
            remarks=target_row.remarks,
            payload=target_row.payload,
            created_at_iso=format_timestamp(target_row.created_at),
        )
        db.commit()


def test_audit_logs_listing_endpoint(db: Session):
    """GET /audit/logs returns list of audit blocks with authentication requirement."""
    client = TestClient(app)

    # Unauthenticated gets 401
    res_unauth = client.get("/audit/logs")
    assert res_unauth.status_code == 401

    # Admin gets full log list
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    headers = get_auth_header(admin)
    res_admin = client.get("/audit/logs", headers=headers)
    assert res_admin.status_code == 200
    logs = res_admin.json()
    assert isinstance(logs, list)
    if logs:
        assert "row_hash" in logs[0]
        assert "prev_hash" in logs[0]
        assert "action" in logs[0]
