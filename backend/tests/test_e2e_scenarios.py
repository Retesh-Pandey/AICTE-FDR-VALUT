import io
import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import (
    FDRRecord,
    Institution,
    InstrumentStatus,
    User,
    UserRole,
    VerificationStatus,
    WorkflowStatus,
)
from app.main import app
from app.services.jobs.maturity import run_maturity_check


def get_token_header(user: User) -> dict:
    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "institution_id": str(user.institution_id) if user.institution_id else None,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_e2e_scenario_1_fdr_submission_and_validation(db: Session):
    """
    Scenario 1: Institution submits a Fixed Deposit Receipt with an attached PDF document.
    Validates server-side file handling, validation flags, duplicate checks, and initial state.
    """
    client = TestClient(app)

    # 1. Fetch institution user
    inst = db.query(Institution).first()
    inst_user = db.query(User).filter(User.role == UserRole.institution, User.institution_id == inst.id).first()
    if not inst_user:
        inst_user = User(
            email=f"e2e_inst_{uuid.uuid4().hex[:6]}@test.com",
            role=UserRole.institution,
            institution_id=inst.id,
        )
        db.add(inst_user)
        db.commit()

    headers = get_token_header(inst_user)

    # 2. Assistive OCR extraction test
    dummy_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (FDR Fixed Deposit Receipt) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    ocr_res = client.post(
        "/fdrs/ocr",
        files={"file": ("deposit_receipt.pdf", io.BytesIO(dummy_pdf), "application/pdf")},
        headers=headers,
    )
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()
    assert "disclaimer" in ocr_data
    assert "fdr_number" in ocr_data

    # 3. Formal Multipart FDR Submission
    unique_fdr_num = f"FDR-E2E-{uuid.uuid4().hex[:8]}"
    today = date.today()
    form_data = {
        "fdr_number": unique_fdr_num,
        "bank_name": "State Bank of India",
        "branch": "New Delhi Main Branch",
        "amount": "2500000.00",
        "issue_date": (today - timedelta(days=90)).isoformat(),
        "maturity_date": (today + timedelta(days=275)).isoformat(),
        "lien_info": "Lien marked exclusively in favor of Member Secretary, AICTE New Delhi.",
    }

    sub_res = client.post(
        "/fdrs",
        data=form_data,
        files={"file": ("sbi_receipt.pdf", io.BytesIO(dummy_pdf), "application/pdf")},
        headers=headers,
    )
    assert sub_res.status_code == 201
    created_fdr = sub_res.json()
    assert created_fdr["fdr"]["fdr_number"] == unique_fdr_num
    assert created_fdr["fdr"]["instrument_status"] == "submitted"
    assert created_fdr["fdr"]["verification_status"] == "pending"

    # 4. Duplicate FDR Number Rejection Check
    dup_res = client.post(
        "/fdrs",
        data=form_data,
        files={"file": ("duplicate_receipt.pdf", io.BytesIO(dummy_pdf), "application/pdf")},
        headers=headers,
    )
    assert dup_res.status_code in [400, 409]
    assert "DUPLICATE" in dup_res.json()["error"]["code"] or "ALREADY_EXISTS" in dup_res.json()["error"]["code"]


def test_e2e_scenario_2_discrepancy_and_officer_resolution(db: Session):
    """
    Scenario 2: An FDR with a discrepancy flag is reviewed and resolved by an AICTE Officer
    with mandatory statutory remarks and cryptographic audit trail generation.
    """
    client = TestClient(app)

    inst = db.query(Institution).first()
    unique_num = f"FDR-DISC-E2E-{uuid.uuid4().hex[:6]}"
    fdr = FDRRecord(
        fdr_number=unique_num,
        institution_id=inst.id,
        bank_name="Canara Bank",
        branch="Connaught Place",
        amount=Decimal("1000000.00"),
        issue_date=date.today() - timedelta(days=30),
        maturity_date=date.today() + timedelta(days=335),
        instrument_status=InstrumentStatus.active,
        verification_status=VerificationStatus.discrepancy,
        workflow_status=WorkflowStatus.none,
        lien_info="Lien marked in favor of Member Secretary AICTE",
    )
    db.add(fdr)
    db.commit()

    officer = db.query(User).filter(User.role == UserRole.officer).first()
    officer_headers = get_token_header(officer)

    # 1. Attempt resolution without remarks -> fails validation
    fail_res = client.post(
        f"/fdrs/{fdr.id}/resolve-discrepancy",
        json={"outcome": "verified", "resolution_note": ""},
        headers=officer_headers,
    )
    assert fail_res.status_code in [400, 422]

    # 2. Valid officer resolution with mandatory justification
    success_res = client.post(
        f"/fdrs/{fdr.id}/resolve-discrepancy",
        json={
            "outcome": "verified",
            "resolution_note": "Verified against physical bank confirmation letter ref #CAN/AICTE/2026/894. Discrepancy cleared.",
        },
        headers=officer_headers,
    )
    assert success_res.status_code == 200
    assert success_res.json()["verification_status"] == "verified"

    # 3. Verify audit log entry was created
    audit_res = client.get(f"/fdrs/{fdr.id}/audit", headers=officer_headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert any("discrepancy_resolved" in entry["action"].lower() for entry in logs)


def test_e2e_scenario_3_maturity_date_simulation_and_notifications(db: Session):
    """
    Scenario 3: Fast-forward time using the date simulator. Verify boundary calculations,
    idempotent milestone notifications, and ensure maturity alone never releases an FDR.
    """
    client = TestClient(app)
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    admin_headers = get_token_header(admin)

    inst = db.query(Institution).first()
    unique_num = f"FDR-MAT-E2E-{uuid.uuid4().hex[:6]}"
    today = date.today()

    # Create deposit maturing exactly in 30 days
    fdr_30 = FDRRecord(
        fdr_number=unique_num,
        institution_id=inst.id,
        bank_name="HDFC Bank",
        branch="Nehru Place",
        amount=Decimal("3000000.00"),
        issue_date=today - timedelta(days=335),
        maturity_date=today + timedelta(days=30),
        instrument_status=InstrumentStatus.active,
        verification_status=VerificationStatus.verified,
        workflow_status=WorkflowStatus.none,
        lien_info="Lien in favor of Member Secretary AICTE",
    )
    db.add(fdr_30)
    db.commit()

    # 1. Run maturity check at current date -> should dispatch 30-day notice
    res1 = run_maturity_check(db, today)
    db.commit()
    assert res1["notifications_created"] >= 1

    # Idempotency: Re-running immediately on same date produces 0 duplicate notices
    res1_dup = run_maturity_check(db, today)
    db.commit()
    assert res1_dup["notifications_created"] == 0

    # 2. Simulate date fast-forward to maturity day (0 days left)
    sim_date = today + timedelta(days=30)
    sim_res = client.post(
        "/admin/simulate-date",
        json={"target_date": sim_date.isoformat()},
        headers=admin_headers,
    )
    assert sim_res.status_code == 200
    assert sim_res.json()["is_simulated"] is True

    # Check that instrument status is updated to 'matured'
    db.refresh(fdr_30)
    assert fdr_30.instrument_status == InstrumentStatus.matured

    # CRITICAL INVARIANT: Verify that workflow_status is NOT released!
    assert fdr_30.workflow_status != WorkflowStatus.completed
    assert fdr_30.instrument_status != InstrumentStatus.released

    # Reset simulation to live real-time
    reset_res = client.post(
        "/admin/simulate-date",
        json={"reset": True},
        headers=admin_headers,
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["is_simulated"] is False


def test_e2e_scenario_4_renewal_linking_and_atomic_approval(db: Session):
    """
    Scenario 4: Institution submits a renewal replacement deposit linked to a maturing FDR.
    Officer approves renewal: predecessor transitions to 'renewed' (is_current=False),
    successor transitions to 'active' (is_current=True) in a single atomic transaction.
    """
    client = TestClient(app)

    inst = db.query(Institution).first()
    inst_user = db.query(User).filter(User.role == UserRole.institution, User.institution_id == inst.id).first()
    inst_headers = get_token_header(inst_user)

    # 1. Predecessor FDR
    old_num = f"FDR-OLD-{uuid.uuid4().hex[:6]}"
    old_fdr = FDRRecord(
        fdr_number=old_num,
        institution_id=inst.id,
        bank_name="Bank of Baroda",
        amount=Decimal("2000000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=10),
        instrument_status=InstrumentStatus.renewal_due,
        verification_status=VerificationStatus.verified,
        workflow_status=WorkflowStatus.none,
        is_current=True,
    )
    db.add(old_fdr)
    db.commit()

    # 2. Institution submits Renewal FDR
    new_num = f"FDR-NEW-{uuid.uuid4().hex[:6]}"
    dummy_pdf = b"%PDF-1.4\nRenewal Receipt\n%%EOF"
    renew_form = {
        "fdr_number": new_num,
        "bank_name": "Bank of Baroda",
        "branch": "Main Branch",
        "amount": "2000000.00",
        "issue_date": date.today().isoformat(),
        "maturity_date": (date.today() + timedelta(days=365)).isoformat(),
        "lien_info": "Lien in favor of Member Secretary AICTE",
    }
    renew_res = client.post(
        f"/fdrs/{old_fdr.id}/renew",
        data=renew_form,
        files={"file": ("renewal_fdr.pdf", io.BytesIO(dummy_pdf), "application/pdf")},
        headers=inst_headers,
    )
    assert renew_res.status_code == 201
    renewal_data = renew_res.json()
    new_fdr_id = renewal_data["fdr"]["id"]

    # 3. Officer reviews and approves renewal
    officer = db.query(User).filter(User.role == UserRole.officer).first()
    officer_headers = get_token_header(officer)

    # Approve renewal
    approve_res = client.post(
        f"/renewals/{new_fdr_id}/approve",
        json={"remarks": "Renewal approved. Term extended for 1 year with continuous AICTE lien."},
        headers=officer_headers,
    )
    assert approve_res.status_code == 200

    # 4. Verify atomic state update
    db.refresh(old_fdr)
    new_fdr = db.query(FDRRecord).filter(FDRRecord.id == new_fdr_id).first()

    assert old_fdr.instrument_status == InstrumentStatus.renewed
    assert old_fdr.is_current is False

    assert new_fdr.instrument_status == InstrumentStatus.active
    assert new_fdr.is_current is True


def test_e2e_scenario_5_controlled_release_workflow_complete_cycle(db: Session):
    """
    Scenario 5: Complete controlled release workflow through the authoritative 6-stage stepper:
    release_requested -> under_review -> conditions_checked -> approval_pending -> approved -> completed.
    Verifies role boundaries, mandatory remarks, and admin completion marking FDR 'released'.
    """
    client = TestClient(app)

    inst = db.query(Institution).first()
    inst_user = db.query(User).filter(User.role == UserRole.institution, User.institution_id == inst.id).first()
    inst_headers = get_token_header(inst_user)

    officer = db.query(User).filter(User.role == UserRole.officer).first()
    officer_headers = get_token_header(officer)

    admin = db.query(User).filter(User.role == UserRole.admin).first()
    admin_headers = get_token_header(admin)

    # 1. Create mature deposit
    fdr_num = f"FDR-REL-E2E-{uuid.uuid4().hex[:6]}"
    fdr = FDRRecord(
        fdr_number=fdr_num,
        institution_id=inst.id,
        bank_name="State Bank of India",
        amount=Decimal("5000000.00"),
        issue_date=date.today() - timedelta(days=1825),
        maturity_date=date.today() - timedelta(days=5),
        instrument_status=InstrumentStatus.matured,
        verification_status=VerificationStatus.verified,
        workflow_status=WorkflowStatus.none,
    )
    db.add(fdr)
    db.commit()

    # 2. Institution initiates Release Request
    req_res = client.post(
        "/release/requests",
        json={"fdr_id": str(fdr.id), "reason": "Mandatory 5-year deposit tenure fulfilled with AICTE accreditation approval."},
        headers=inst_headers,
    )
    assert req_res.status_code == 201
    request_id = req_res.json()["id"]

    # 3. Officer Review Phase: Transition to 'under_review'
    t1 = client.post(
        f"/release/requests/{request_id}/transition",
        json={"to_stage": "under_review", "remarks": "Officer started regulatory file inspection."},
        headers=officer_headers,
    )
    assert t1.status_code == 200
    assert t1.json()["stage"] == "under_review"

    # 4. Officer Conditions Checked: Transition to 'conditions_checked'
    t2 = client.post(
        f"/release/requests/{request_id}/transition",
        json={"to_stage": "conditions_checked", "remarks": "Zero outstanding student grievances or accreditation violations."},
        headers=officer_headers,
    )
    assert t2.status_code == 200
    assert t2.json()["stage"] == "conditions_checked"

    # 5. Forward to Admin: Transition to 'approval_pending'
    t3 = client.post(
        f"/release/requests/{request_id}/transition",
        json={"to_stage": "approval_pending", "remarks": "Forwarded to Member Secretary for executive approval."},
        headers=officer_headers,
    )
    assert t3.status_code == 200
    assert t3.json()["stage"] == "approval_pending"

    # Officer cannot approve (role security test)
    unauthorized_app = client.post(
        f"/release/requests/{request_id}/transition",
        json={"to_stage": "approved", "remarks": "Officer attempting unauthorized approval."},
        headers=officer_headers,
    )
    assert unauthorized_app.status_code == 403

    # 6. Admin Executive Approval: Transition to 'approved'
    t4 = client.post(
        f"/release/requests/{request_id}/transition",
        json={"to_stage": "approved", "remarks": "Executive approval granted by AICTE Competent Authority."},
        headers=admin_headers,
    )
    assert t4.status_code == 200
    assert t4.json()["stage"] == "approved"

    # 7. Admin Discharge & Completion: Transition to 'completed'
    t5 = client.post(
        f"/release/requests/{request_id}/transition",
        json={"to_stage": "completed", "remarks": "Statutory lien discharged. Bank release authorization dispatched."},
        headers=admin_headers,
    )
    assert t5.status_code == 200
    assert t5.json()["stage"] == "completed"

    # 8. Verify FDR Instrument Status is now RELEASED
    db.refresh(fdr)
    assert fdr.instrument_status == InstrumentStatus.released
    assert fdr.workflow_status == WorkflowStatus.completed
