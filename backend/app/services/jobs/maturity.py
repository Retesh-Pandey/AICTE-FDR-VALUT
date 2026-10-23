"""Maturity Monitoring, Renewal Alert Job, and Hackathon Date Simulator.

Rules:
1. run_maturity_check is a pure function taking `today: date`.
2. Idempotent notifications deduplicated by (user_id, fdr_id, milestone).
3. Maturity alone must NEVER release an FDR or alter verification/workflow status.
4. Effective date returns simulated date when ENABLE_SIMULATED_DATE is enabled.
"""

from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.models import (
    FDRRecord,
    InstrumentStatus,
    Notification,
    User,
    UserRole,
)

# In-memory storage for hackathon simulated date override
_simulated_date_override: Optional[date] = None


def set_simulated_date(target_date: Optional[date]) -> None:
    """Sets or clears the simulated date for hackathon demonstration."""
    global _simulated_date_override
    _simulated_date_override = target_date
    logger.info(f"Simulated date set to: {_simulated_date_override}")


def get_simulated_date() -> Optional[date]:
    """Returns current simulated date override if active."""
    return _simulated_date_override


def get_effective_today() -> date:
    """Returns current effective date.

    Uses simulated override if enabled; otherwise returns real system date.
    """
    if settings.ENABLE_SIMULATED_DATE and _simulated_date_override is not None:
        return _simulated_date_override
    return date.today()


def _ensure_notification(
    db: Session,
    user_id: UUID,
    fdr_id: UUID,
    notif_type: str,
    milestone: str,
    message: str,
) -> bool:
    """Inserts a notification only if the unique milestone does not already exist."""
    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.fdr_id == fdr_id,
            Notification.milestone == milestone,
        )
        .first()
    )
    if existing:
        return False

    notif = Notification(
        user_id=user_id,
        fdr_id=fdr_id,
        type=notif_type,
        milestone=milestone,
        message=message,
    )
    db.add(notif)
    return True


def run_maturity_check(db: Session, today: date) -> Dict[str, Any]:
    """Pure function executing boundary evaluations against all current FDR instruments.

    Evaluation boundaries:
    - 30 days left (30..16): sends 'maturity_30' notice to institution + officers
    - 15 days left (15..8): checks if renewal exists; if not, marks 'renewal_due' and sends 'maturity_15'
    - 7 days left (7..1): escalates 'maturity_7' notice to officers/admins
    - <= 0 days (maturity_date <= today): marks 'matured' and sends 'matured' notice

    CRITICAL INVARIANT:
    This function strictly modifies only instrument_status between active -> renewal_due -> matured.
    It NEVER sets instrument_status to 'released', and NEVER modifies verification_status
    or workflow_status.
    """
    results: Dict[str, Any] = {
        "evaluated_date": str(today),
        "total_active_evaluated": 0,
        "marked_renewal_due": 0,
        "marked_matured": 0,
        "notifications_created": 0,
        "details": [],
    }

    # Fetch all active / current FDRs (ignore superseded or released)
    records = (
        db.query(FDRRecord)
        .filter(
            FDRRecord.is_current.is_(True),
            FDRRecord.instrument_status.notin_([InstrumentStatus.released, InstrumentStatus.renewed]),
        )
        .all()
    )

    results["total_active_evaluated"] = len(records)

    # Pre-fetch council officers and admins for notifications
    council_users = (
        db.query(User)
        .filter(User.role.in_([UserRole.officer, UserRole.admin]))
        .all()
    )

    for fdr in records:
        days_left = (fdr.maturity_date - today).days

        # Pre-fetch institution users
        inst_users = (
            db.query(User)
            .filter(User.institution_id == fdr.institution_id)
            .all()
        )
        recipients = {u.id for u in inst_users + council_users}

        # Check if renewal already exists
        has_renewal = (
            db.query(FDRRecord)
            .filter(FDRRecord.previous_fdr_id == fdr.id)
            .first()
            is not None
        )

        notifs_for_this_fdr = 0

        # Boundary 4: Maturity Reached / Overdue (days_left <= 0)
        if days_left <= 0:
            if fdr.instrument_status != InstrumentStatus.matured:
                fdr.instrument_status = InstrumentStatus.matured
                results["marked_matured"] += 1

            for uid in recipients:
                created = _ensure_notification(
                    db=db,
                    user_id=uid,
                    fdr_id=fdr.id,
                    notif_type="matured",
                    milestone="matured",
                    message=(
                        f"MATURED DEPOSIT: Security Deposit FDR {fdr.fdr_number} "
                        f"({fdr.bank_name}, ₹{fdr.amount:,.2f}) matured on {fdr.maturity_date}. "
                        "AICTE administrative review and action required."
                    ),
                )
                if created:
                    notifs_for_this_fdr += 1

        # Boundary 3: Critical Expiry Escalation (1 <= days_left <= 7)
        elif 1 <= days_left <= 7:
            for uid in recipients:
                created = _ensure_notification(
                    db=db,
                    user_id=uid,
                    fdr_id=fdr.id,
                    notif_type="maturity_7",
                    milestone="maturity_7",
                    message=(
                        f"CRITICAL MATURITY ESCALATION: Security Deposit FDR {fdr.fdr_number} "
                        f"matures in {days_left} day(s) on {fdr.maturity_date}. "
                        "Urgent renewal or encashment review required."
                    ),
                )
                if created:
                    notifs_for_this_fdr += 1

        # Boundary 2: 15-Day Renewal Due Check (8 <= days_left <= 15)
        elif 8 <= days_left <= 15:
            if not has_renewal:
                if fdr.instrument_status == InstrumentStatus.active:
                    fdr.instrument_status = InstrumentStatus.renewal_due
                    results["marked_renewal_due"] += 1

                for uid in recipients:
                    created = _ensure_notification(
                        db=db,
                        user_id=uid,
                        fdr_id=fdr.id,
                        notif_type="maturity_15",
                        milestone="maturity_15",
                        message=(
                            f"RENEWAL WARNING: Security Deposit FDR {fdr.fdr_number} "
                            f"matures in {days_left} days ({fdr.maturity_date}). "
                            "No renewal instrument has been received yet."
                        ),
                    )
                    if created:
                        notifs_for_this_fdr += 1

        # Boundary 1: 30-Day Reminder (16 <= days_left <= 30)
        elif 16 <= days_left <= 30:
            for uid in recipients:
                created = _ensure_notification(
                    db=db,
                    user_id=uid,
                    fdr_id=fdr.id,
                    notif_type="maturity_30",
                    milestone="maturity_30",
                    message=(
                        f"Maturity Notice: Security Deposit FDR {fdr.fdr_number} "
                        f"({fdr.bank_name}) matures in {days_left} days on {fdr.maturity_date}. "
                        "Please review institutional compliance and renewal requirements."
                    ),
                )
                if created:
                    notifs_for_this_fdr += 1

        results["notifications_created"] += notifs_for_this_fdr
        if notifs_for_this_fdr > 0 or days_left <= 30:
            results["details"].append({
                "fdr_number": fdr.fdr_number,
                "days_left": days_left,
                "instrument_status": fdr.instrument_status.value,
                "notifications_sent": notifs_for_this_fdr,
            })

    db.flush()
    return results
