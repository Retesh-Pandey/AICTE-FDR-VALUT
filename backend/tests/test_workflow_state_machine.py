from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.models import (
    FDRRecord,
    Institution,
    InstrumentStatus,
    User,
    UserRole,
    WorkflowAuditLog,
    WorkflowStatus,
)
from app.main import app
from app.services.jobs.maturity import run_maturity_check

client = TestClient(app)


@pytest.fixture
def test_setup(db):
    """Sets up institution, institution user, officer, admin, and a unique sample active FDR."""
    import uuid
    suffix = uuid.uuid4().hex[:6].upper()

    inst = db.query(Institution).first()
    if not inst:
        inst = Institution(
            aicte_id=f"AICTE-TST-{suffix}",
            name=f"State Testing Institute {suffix}",
            region="Northern",
        )
        db.add(inst)
        db.commit()
        db.refresh(inst)

    inst_user = db.query(User).filter(User.role == UserRole.institution, User.institution_id == inst.id).first()
    if not inst_user:
        inst_user = db.query(User).filter(User.role == UserRole.institution).first()
    officer_user = db.query(User).filter(User.role == UserRole.officer).first()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()

    fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-WF-{suffix}",
        bank_name=f"Punjab National Bank {suffix}",
        amount=Decimal("5000000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=60),
        instrument_status=InstrumentStatus.active,
        workflow_status=WorkflowStatus.none,
        is_current=True,
    )
    db.add(fdr)
    db.commit()
    db.refresh(fdr)

    inst_token = create_access_token(data={"sub": str(inst_user.id), "role": "institution", "email": inst_user.email})
    officer_token = create_access_token(data={"sub": str(officer_user.id), "role": "officer", "email": officer_user.email})
    admin_token = create_access_token(data={"sub": str(admin_user.id), "role": "admin", "email": admin_user.email})

    return {
        "inst": inst,
        "inst_user": inst_user,
        "officer_user": officer_user,
        "admin_user": admin_user,
        "fdr": fdr,
        "inst_headers": {"Authorization": f"Bearer {inst_token}"},
        "officer_headers": {"Authorization": f"Bearer {officer_token}"},
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
    }


def test_complete_valid_release_workflow(test_setup, db):
    """Verifies the complete documented release path:

    release_requested (inst) -> under_review (officer) -> conditions_checked (officer)
    -> approval_pending (officer) -> approved (admin) -> completed (admin).
    Verifies that on 'completed', the FDR instrument_status is atomically set to 'released'.
    """
    fdr = test_setup["fdr"]
    inst_headers = test_setup["inst_headers"]
    officer_headers = test_setup["officer_headers"]
    admin_headers = test_setup["admin_headers"]

    # 1. Institution creates release request
    req_res = client.post(
        "/release/requests",
        json={"fdr_id": str(fdr.id), "reason": "Mandatory tenure completed with all regulatory milestones verified."},
        headers=inst_headers,
    )
    assert req_res.status_code == 201, req_res.text
    req_data = req_res.json()
    req_id = req_data["id"]
    assert req_data["stage"] == "release_requested"

    db.refresh(fdr)
    assert fdr.workflow_status == WorkflowStatus.release_requested

    # 2. Officer: release_requested -> under_review
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "under_review", "remarks": "Review commenced by AICTE Regional Office."},
        headers=officer_headers,
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "under_review"

    # 3. Officer: under_review -> conditions_checked
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "conditions_checked", "remarks": "No pending complaints or encumbrances found."},
        headers=officer_headers,
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "conditions_checked"

    # 4. Officer: conditions_checked -> approval_pending
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "approval_pending", "remarks": "Forwarded to Member Secretary for executive approval."},
        headers=officer_headers,
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "approval_pending"

    # 5. Admin: approval_pending -> approved
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "approved", "remarks": "Executive order issued for full security deposit release."},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "approved"

    # Check that before 'completed', FDR is NOT yet released!
    db.refresh(fdr)
    assert fdr.instrument_status == InstrumentStatus.active

    # 6. Admin: approved -> completed
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "completed", "remarks": "Lien discharge certificate dispatched to issuing bank."},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "completed"

    # Invariant: ON COMPLETED, FDR MUST BE RELEASED
    db.refresh(fdr)
    assert fdr.workflow_status == WorkflowStatus.completed
    assert fdr.instrument_status == InstrumentStatus.released

    # Verify audit logs created
    audits = db.query(WorkflowAuditLog).filter(WorkflowAuditLog.entity_id == req_id).all()
    assert len(audits) >= 5


def test_invalid_state_transitions_rejected(test_setup):
    """Verifies that skipping stages returns 409 INVALID_WORKFLOW_TRANSITION."""
    fdr = test_setup["fdr"]
    inst_headers = test_setup["inst_headers"]
    admin_headers = test_setup["admin_headers"]

    req_res = client.post(
        "/release/requests",
        json={"fdr_id": str(fdr.id), "reason": "Testing invalid jump from requested directly to approved."},
        headers=inst_headers,
    )
    assert req_res.status_code == 201
    req_id = req_res.json()["id"]

    # Try jumping directly from release_requested to approved (skip review and conditions)
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "approved", "remarks": "Attempting illegal stage jump."},
        headers=admin_headers,
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"


def test_unauthorized_role_transition_rejected(test_setup):
    """Verifies that unauthorized roles cannot execute restricted transitions."""
    fdr = test_setup["fdr"]
    inst_headers = test_setup["inst_headers"]
    officer_headers = test_setup["officer_headers"]

    req_res = client.post(
        "/release/requests",
        json={"fdr_id": str(fdr.id), "reason": "Testing role boundaries on release transitions."},
        headers=inst_headers,
    )
    req_id = req_res.json()["id"]

    # Advance to approval_pending
    client.post(f"/release/requests/{req_id}/transition", json={"to_stage": "under_review"}, headers=officer_headers)
    client.post(f"/release/requests/{req_id}/transition", json={"to_stage": "conditions_checked", "remarks": "Checked"}, headers=officer_headers)
    client.post(f"/release/requests/{req_id}/transition", json={"to_stage": "approval_pending"}, headers=officer_headers)

    # Officer attempts to perform ADMIN-only approval -> 403 FORBIDDEN_ROLE
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "approved", "remarks": "Officer attempting executive approval."},
        headers=officer_headers,
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # Institution user attempts any transition -> 403 FORBIDDEN
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "approved", "remarks": "Institution attempting approval."},
        headers=inst_headers,
    )
    assert res.status_code == 403


def test_rejection_requires_mandatory_remarks(test_setup):
    """Verifies that rejecting a release request strictly requires non-empty remarks."""
    fdr = test_setup["fdr"]
    inst_headers = test_setup["inst_headers"]
    officer_headers = test_setup["officer_headers"]

    req_res = client.post(
        "/release/requests",
        json={"fdr_id": str(fdr.id), "reason": "Testing rejection remarks enforcement."},
        headers=inst_headers,
    )
    req_id = req_res.json()["id"]

    client.post(f"/release/requests/{req_id}/transition", json={"to_stage": "under_review"}, headers=officer_headers)

    # Rejection without remarks -> 400 REMARKS_REQUIRED
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "rejected", "remarks": "   "},
        headers=officer_headers,
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "REMARKS_REQUIRED"

    # Rejection with valid remarks succeeds
    res = client.post(
        f"/release/requests/{req_id}/transition",
        json={"to_stage": "rejected", "remarks": "Encroachment dispute pending in court; release denied."},
        headers=officer_headers,
    )
    assert res.status_code == 200
    assert res.json()["stage"] == "rejected"


def test_atomic_renewal_approval(test_setup, db):
    """Verifies atomic renewal approval:

    New FDR becomes active and is_current=True.
    Old FDR becomes renewed and is_current=False.
    """
    old_fdr = test_setup["fdr"]
    inst = test_setup["inst"]
    officer_headers = test_setup["officer_headers"]

    import uuid
    new_fdr_num = f"FDR-RENEWED-{uuid.uuid4().hex[:6].upper()}"

    # Create new renewal FDR pointing to old_fdr
    new_fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number=new_fdr_num,
        bank_name="Punjab National Bank",
        amount=Decimal("5000000.00"),
        issue_date=date.today(),
        maturity_date=date.today() + timedelta(days=365 * 3),
        previous_fdr_id=old_fdr.id,
        instrument_status=InstrumentStatus.submitted,
        workflow_status=WorkflowStatus.renewal_review,
        is_current=True,
    )
    db.add(new_fdr)
    db.commit()
    db.refresh(new_fdr)

    # Officer approves renewal
    res = client.post(
        f"/renewals/{new_fdr.id}/approve",
        json={"remarks": "Renewal verified with PNB CBS. Term extended for 36 months."},
        headers=officer_headers,
    )
    assert res.status_code == 200

    db.refresh(new_fdr)
    db.refresh(old_fdr)

    # Assert new FDR is active and current
    assert new_fdr.instrument_status == InstrumentStatus.active
    assert new_fdr.workflow_status == WorkflowStatus.approved
    assert new_fdr.is_current is True

    # Assert old FDR is atomically marked renewed and NOT current
    assert old_fdr.instrument_status == InstrumentStatus.renewed
    assert old_fdr.is_current is False


def test_maturity_alone_never_releases_fdr(test_setup, db):
    """CRITICAL TEST: Ensures run_maturity_check NEVER sets instrument_status to 'released'.

    Even when an FDR is overdue by 500 days, it must only become 'matured'.
    """
    fdr = test_setup["fdr"]
    fdr.maturity_date = date.today() - timedelta(days=100)
    db.commit()

    # Run check against today
    results = run_maturity_check(db=db, today=date.today())
    assert results["total_active_evaluated"] > 0

    db.refresh(fdr)
    assert fdr.instrument_status == InstrumentStatus.matured
    assert fdr.instrument_status != InstrumentStatus.released
    assert fdr.workflow_status == WorkflowStatus.none  # Workflow status remains unaltered
