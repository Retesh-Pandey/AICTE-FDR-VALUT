from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.models import (
    FDRRecord,
    Institution,
    InstrumentStatus,
    Notification,
    User,
    UserRole,
)
from app.main import app
from app.services.jobs.maturity import run_maturity_check, set_simulated_date

client = TestClient(app)


@pytest.fixture
def maturity_fixtures(db):
    import uuid
    set_simulated_date(None)
    suffix = uuid.uuid4().hex[:6].upper()

    inst = db.query(Institution).first()
    if not inst:
        inst = Institution(
            aicte_id=f"AICTE-MAT-{suffix}",
            name=f"Institute of Applied Sciences {suffix}",
            region="Western",
        )
        db.add(inst)
        db.commit()
        db.refresh(inst)

    inst_user = db.query(User).filter(User.role == UserRole.institution, User.institution_id == inst.id).first()
    if not inst_user:
        inst_user = db.query(User).filter(User.role == UserRole.institution).first()
    officer_user = db.query(User).filter(User.role == UserRole.officer).first()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()

    admin_token = create_access_token(data={"sub": str(admin_user.id), "role": "admin", "email": admin_user.email})
    inst_token = create_access_token(data={"sub": str(inst_user.id), "role": "institution", "email": inst_user.email})

    return {
        "inst": inst,
        "inst_user": inst_user,
        "officer_user": officer_user,
        "admin_user": admin_user,
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "inst_headers": {"Authorization": f"Bearer {inst_token}"},
    }


def test_maturity_boundary_evaluations(maturity_fixtures, db):
    """Verifies all boundary days: 31, 30, 15, 7, 0, and -1."""
    inst = maturity_fixtures["inst"]
    today = date(2028, 6, 1)

    import uuid
    suffix = uuid.uuid4().hex[:6].upper()

    # 1. Day 31: no notification
    fdr_31 = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-31DAYS-{suffix}",
        bank_name="Canara Bank",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=365),
        maturity_date=today + timedelta(days=31),
        instrument_status=InstrumentStatus.active,
        is_current=True,
    )

    # 2. Day 30: maturity_30 notification
    fdr_30 = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-30DAYS-{suffix}",
        bank_name="Canara Bank",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=365),
        maturity_date=today + timedelta(days=30),
        instrument_status=InstrumentStatus.active,
        is_current=True,
    )

    # 3. Day 15: renewal_due and maturity_15 notification
    fdr_15 = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-15DAYS-{suffix}",
        bank_name="Canara Bank",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=365),
        maturity_date=today + timedelta(days=15),
        instrument_status=InstrumentStatus.active,
        is_current=True,
    )

    # 4. Day 7: maturity_7 critical escalation
    fdr_7 = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-7DAYS-{suffix}",
        bank_name="Canara Bank",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=365),
        maturity_date=today + timedelta(days=7),
        instrument_status=InstrumentStatus.active,
        is_current=True,
    )

    # 5. Day 0: matured
    fdr_0 = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-0DAYS-{suffix}",
        bank_name="Canara Bank",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=365),
        maturity_date=today,
        instrument_status=InstrumentStatus.active,
        is_current=True,
    )

    # 6. Day -1: matured overdue
    fdr_neg = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-NEGDAYS-{suffix}",
        bank_name="Canara Bank",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=365),
        maturity_date=today - timedelta(days=5),
        instrument_status=InstrumentStatus.active,
        is_current=True,
    )

    db.add_all([fdr_31, fdr_30, fdr_15, fdr_7, fdr_0, fdr_neg])
    db.commit()

    # Run check
    results = run_maturity_check(db=db, today=today)
    assert results["total_active_evaluated"] >= 6

    db.refresh(fdr_31)
    db.refresh(fdr_30)
    db.refresh(fdr_15)
    db.refresh(fdr_7)
    db.refresh(fdr_0)
    db.refresh(fdr_neg)

    # Check status mutations
    assert fdr_31.instrument_status == InstrumentStatus.active
    assert fdr_30.instrument_status == InstrumentStatus.active
    assert fdr_15.instrument_status == InstrumentStatus.renewal_due
    assert fdr_0.instrument_status == InstrumentStatus.matured
    assert fdr_neg.instrument_status == InstrumentStatus.matured

    # Check notifications
    notifs_31 = db.query(Notification).filter(Notification.fdr_id == fdr_31.id).all()
    assert len(notifs_31) == 0

    notifs_30 = db.query(Notification).filter(Notification.fdr_id == fdr_30.id, Notification.milestone == "maturity_30").all()
    assert len(notifs_30) > 0

    notifs_15 = db.query(Notification).filter(Notification.fdr_id == fdr_15.id, Notification.milestone == "maturity_15").all()
    assert len(notifs_15) > 0

    notifs_7 = db.query(Notification).filter(Notification.fdr_id == fdr_7.id, Notification.milestone == "maturity_7").all()
    assert len(notifs_7) > 0

    notifs_0 = db.query(Notification).filter(Notification.fdr_id == fdr_0.id, Notification.milestone == "matured").all()
    assert len(notifs_0) > 0


def test_idempotent_notifications_no_duplicates(maturity_fixtures, db):
    """Running run_maturity_check twice on the exact same date produces no duplicates."""
    inst = maturity_fixtures["inst"]
    today = date(2028, 6, 1)

    import uuid
    suffix = uuid.uuid4().hex[:6].upper()

    fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number=f"FDR-IDEMP-{suffix}",
        bank_name="Canara Bank",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=365),
        maturity_date=today + timedelta(days=20),
        instrument_status=InstrumentStatus.active,
        is_current=True,
    )
    db.add(fdr)
    db.commit()

    # First run
    run1 = run_maturity_check(db=db, today=today)
    assert run1["notifications_created"] > 0
    count_after_run1 = db.query(Notification).filter(Notification.fdr_id == fdr.id).count()

    # Second run on same date
    run2 = run_maturity_check(db=db, today=today)
    assert run2["notifications_created"] == 0
    count_after_run2 = db.query(Notification).filter(Notification.fdr_id == fdr.id).count()

    assert count_after_run1 == count_after_run2


def test_simulate_date_api_endpoint(maturity_fixtures):
    """Verifies POST /admin/simulate-date sets the date, runs check, and requires admin/officer."""
    admin_headers = maturity_fixtures["admin_headers"]
    inst_headers = maturity_fixtures["inst_headers"]

    # 1. Institution forbidden
    res = client.post(
        "/admin/simulate-date",
        json={"offset_days": 25},
        headers=inst_headers,
    )
    assert res.status_code == 403

    # 2. Admin successfully shifts date
    res = client.post(
        "/admin/simulate-date",
        json={"offset_days": 25},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_simulated"] is True
    assert "results" in data

    # 3. Check status endpoint
    status_res = client.get("/admin/simulate-date", headers=admin_headers)
    assert status_res.status_code == 200
    assert status_res.json()["is_simulated"] is True

    # 4. Reset date
    reset_res = client.post(
        "/admin/simulate-date",
        json={"reset": True},
        headers=admin_headers,
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["is_simulated"] is False
