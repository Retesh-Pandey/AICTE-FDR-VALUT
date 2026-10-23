from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.db.models import User, UserRole
from app.schemas.fdr import FDRResponse
from app.schemas.renewal import RenewalDecisionRequest
from app.services.workflow.machine import transition_renewal

router = APIRouter(prefix="/renewals", tags=["FDR Renewals"])


@router.post("/{id}/approve", response_model=FDRResponse)
def approve_renewal(
    id: UUID,
    data: RenewalDecisionRequest,
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Approve a pending renewal FDR instrument.

    Atomically activates the new renewal FDR (instrument_status='active', is_current=True)
    and marks the previous FDR as renewed (instrument_status='renewed', is_current=False)
    in the same database transaction.
    """
    new_fdr = transition_renewal(
        db=db,
        new_fdr_id=id,
        outcome="approved",
        actor=current_user,
        remarks=data.remarks,
    )
    db.commit()
    db.refresh(new_fdr)
    return new_fdr


@router.post("/{id}/reject", response_model=FDRResponse)
def reject_renewal(
    id: UUID,
    data: RenewalDecisionRequest,
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Reject a pending renewal FDR submission.

    Sets the renewal submission's workflow_status to 'rejected'.
    The previous FDR instrument remains unchanged.
    """
    new_fdr = transition_renewal(
        db=db,
        new_fdr_id=id,
        outcome="rejected",
        actor=current_user,
        remarks=data.remarks,
    )
    db.commit()
    db.refresh(new_fdr)
    return new_fdr
