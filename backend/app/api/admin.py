from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_role
from app.core.exceptions import AppException
from app.db.models import Institution, User, UserRole
from app.schemas.fdr import AdminExtendHoldRequest, AdminUnfreezeRequest, InstitutionHoldStatus
from app.services.audit import write_audit_log
from app.services.escalation import (
    admin_extend_institution_hold,
    admin_unfreeze_institution_hold,
    check_and_update_institution_hold,
    count_confirmed_unrelated_strikes,
)
from app.services.jobs.maturity import (
    get_effective_today,
    get_simulated_date,
    run_maturity_check,
    set_simulated_date,
)

router = APIRouter(prefix="/admin", tags=["Admin & Hackathon Demo Controls"])


class SimulateDateRequest(BaseModel):
    target_date: Optional[date] = None
    offset_days: Optional[int] = None
    reset: bool = False


@router.get("/simulate-date")
def get_simulation_status(
    current_user: User = Depends(get_current_user),
):
    """Inspect current simulated date status and effective date."""
    sim_date = get_simulated_date()
    return {
        "effective_date": str(get_effective_today()),
        "simulated_date": str(sim_date) if sim_date else None,
        "is_simulated": sim_date is not None,
        "simulation_enabled": settings.ENABLE_SIMULATED_DATE,
    }


@router.post("/simulate-date")
def simulate_date(
    data: SimulateDateRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Set or reset simulated date to demonstrate maturity monitoring and reminders.

    Guarded by settings.ENABLE_SIMULATED_DATE and strictly forbidden in production. Admin only.
    Immediately executes run_maturity_check against the effective date and audits invocation.
    """
    if settings.ENVIRONMENT.lower() == "production" or not settings.ENABLE_SIMULATED_DATE:
        raise AppException(
            status_code=403,
            code="SIMULATED_DATE_DISABLED",
            message="Simulated date controls are disabled in production and non-demo environments.",
        )

    old_effective = get_effective_today()

    if data.reset:
        set_simulated_date(None)
    elif data.offset_days is not None:
        target = date.today() + timedelta(days=data.offset_days)
        set_simulated_date(target)
    elif data.target_date is not None:
        set_simulated_date(data.target_date)

    new_effective = get_effective_today()

    # Trigger pure maturity check using effective date
    results = run_maturity_check(db=db, today=new_effective)

    # Cryptographically chained audit entry
    write_audit_log(
        db=db,
        action="admin.simulate_date",
        entity="system",
        entity_id=None,
        actor_id=current_user.id,
        actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        old_status=str(old_effective),
        new_status=str(new_effective),
        remarks=f"Simulated date adjusted from {old_effective} to {new_effective} by {current_user.full_name}",
        payload={"offset_days": data.offset_days, "reset": data.reset, "results": results},
    )

    db.commit()

    return {
        "status": "success",
        "effective_date": str(new_effective),
        "is_simulated": get_simulated_date() is not None,
        "results": results,
    }


# -------------------------------------------------------------------------
# Escalation & Temporary Upload Review Hold Management (Admin Only)
# -------------------------------------------------------------------------

@router.get("/institutions/held", response_model=list[InstitutionHoldStatus])
def list_held_institutions(
    current_user: User = Depends(require_role(UserRole.admin, UserRole.officer)),
    db: Session = Depends(get_db),
):
    """
    Lists institutions currently under temporary upload review hold or with active strikes.
    Accessible to Administrators and Officers.
    """
    institutions = db.query(Institution).all()
    results = []
    for inst in institutions:
        check_and_update_institution_hold(db, inst)
        strikes = count_confirmed_unrelated_strikes(db, inst.id)
        if inst.upload_hold_active or strikes > 0:
            results.append(
                InstitutionHoldStatus(
                    institution_id=inst.id,
                    institution_name=inst.name,
                    upload_hold_active=bool(inst.upload_hold_active),
                    upload_hold_until=inst.upload_hold_until,
                    upload_hold_reason=inst.upload_hold_reason,
                    upload_hold_placed_at=inst.upload_hold_placed_at,
                    upload_hold_appealed_at=inst.upload_hold_appealed_at,
                    upload_hold_appeal_reason=inst.upload_hold_appeal_reason,
                    confirmed_strikes_in_window=strikes,
                    strike_threshold=settings.UNRELATED_STRIKE_THRESHOLD,
                    window_days=settings.UNRELATED_WINDOW_DAYS,
                    hold_duration_days=settings.REVIEW_HOLD_DAYS,
                )
            )
    return results


@router.post("/institutions/{id}/unfreeze-hold", response_model=InstitutionHoldStatus)
def unfreeze_institution_hold(
    id: UUID,
    body: AdminUnfreezeRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Administrative unfreeze: Removes upload review hold on an institution.
    Strictly restricted to Admin role with cryptographic audit trail.
    """
    inst = admin_unfreeze_institution_hold(
        db=db,
        institution_id=id,
        reason=body.reason,
        admin_user=current_user,
    )
    strikes = count_confirmed_unrelated_strikes(db, id)
    return InstitutionHoldStatus(
        institution_id=inst.id,
        institution_name=inst.name,
        upload_hold_active=bool(inst.upload_hold_active),
        upload_hold_until=inst.upload_hold_until,
        upload_hold_reason=inst.upload_hold_reason,
        upload_hold_placed_at=inst.upload_hold_placed_at,
        upload_hold_appealed_at=inst.upload_hold_appealed_at,
        upload_hold_appeal_reason=inst.upload_hold_appeal_reason,
        confirmed_strikes_in_window=strikes,
        strike_threshold=settings.UNRELATED_STRIKE_THRESHOLD,
        window_days=settings.UNRELATED_WINDOW_DAYS,
        hold_duration_days=settings.REVIEW_HOLD_DAYS,
    )


@router.post("/institutions/{id}/extend-hold", response_model=InstitutionHoldStatus)
def extend_institution_hold(
    id: UUID,
    body: AdminExtendHoldRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Administrative hold extension: Extends upload review hold duration.
    Strictly restricted to Admin role with cryptographic audit trail.
    """
    inst = admin_extend_institution_hold(
        db=db,
        institution_id=id,
        days=body.days,
        reason=body.reason,
        admin_user=current_user,
    )
    strikes = count_confirmed_unrelated_strikes(db, id)
    return InstitutionHoldStatus(
        institution_id=inst.id,
        institution_name=inst.name,
        upload_hold_active=bool(inst.upload_hold_active),
        upload_hold_until=inst.upload_hold_until,
        upload_hold_reason=inst.upload_hold_reason,
        upload_hold_placed_at=inst.upload_hold_placed_at,
        upload_hold_appealed_at=inst.upload_hold_appealed_at,
        upload_hold_appeal_reason=inst.upload_hold_appeal_reason,
        confirmed_strikes_in_window=strikes,
        strike_threshold=settings.UNRELATED_STRIKE_THRESHOLD,
        window_days=settings.UNRELATED_WINDOW_DAYS,
        hold_duration_days=settings.REVIEW_HOLD_DAYS,
    )

