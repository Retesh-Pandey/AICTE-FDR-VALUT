from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import (
    get_current_user,
    get_db,
    require_role,
    verify_institution_access,
)
from app.core.exceptions import AppException, NotFoundException
from app.db.models import (
    FDRRecord,
    InstrumentStatus,
    ReleaseRequest,
    User,
    UserRole,
    WorkflowStatus,
)
from app.schemas.release import (
    ReleaseRequestCreate,
    ReleaseRequestResponse,
    ReleaseTransitionRequest,
)
from app.services.audit import write_audit_log
from app.services.workflow.machine import transition_release

router = APIRouter(prefix="/release", tags=["Release Workflow"])


def _hydrate_release_response(req: ReleaseRequest) -> ReleaseRequestResponse:
    resp = ReleaseRequestResponse.model_validate(req)
    if req.fdr:
        resp.fdr_number = req.fdr.fdr_number
        resp.bank_name = req.fdr.bank_name
        resp.amount = req.fdr.amount
        resp.fdr_instrument_status = req.fdr.instrument_status
        if req.fdr.institution:
            resp.institution_name = req.fdr.institution.name
    return resp


@router.post("/requests", response_model=ReleaseRequestResponse, status_code=status.HTTP_201_CREATED)
def create_release_request(
    data: ReleaseRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initiate a formal Release Request for a security deposit FDR.

    Institutions may only request release for their own active/matured FDRs.
    Blocks release request if an open renewal review or release workflow is already active.
    """
    fdr = db.query(FDRRecord).options(joinedload(FDRRecord.institution)).filter(FDRRecord.id == data.fdr_id).first()
    if not fdr:
        raise NotFoundException(message=f"FDR '{data.fdr_id}' not found.", code="FDR_NOT_FOUND")

    # Multi-tenant scoping
    verify_institution_access(fdr.institution_id, current_user)

    # Invariant checks
    if fdr.instrument_status == InstrumentStatus.released:
        raise AppException(
            status_code=400,
            code="ALREADY_RELEASED",
            message="This FDR is already released and has completed its lifecycle.",
        )

    if fdr.workflow_status in (
        WorkflowStatus.release_requested,
        WorkflowStatus.under_review,
        WorkflowStatus.conditions_checked,
        WorkflowStatus.approval_pending,
    ):
        raise AppException(
            status_code=409,
            code="RELEASE_ALREADY_ACTIVE",
            message="A release workflow is already actively in progress for this FDR.",
        )

    if fdr.workflow_status == WorkflowStatus.renewal_review:
        raise AppException(
            status_code=409,
            code="RENEWAL_IN_PROGRESS",
            message="Cannot request release while a renewal review is in progress.",
        )

    if not data.reason or len(data.reason.strip()) < 5:
        raise AppException(
            status_code=400,
            code="REASON_REQUIRED",
            message="A detailed reason and justification is required for requesting FDR release.",
        )

    # Create release request
    req = ReleaseRequest(
        fdr_id=fdr.id,
        requested_by=current_user.id,
        reason=data.reason.strip(),
        stage=WorkflowStatus.release_requested,
    )
    db.add(req)

    # Set FDR workflow status
    fdr.workflow_status = WorkflowStatus.release_requested

    # Cryptographically chained audit entry
    write_audit_log(
        db=db,
        action="fdr.release_requested",
        entity="release_request",
        entity_id=req.id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        old_status=fdr.workflow_status.value,
        new_status=WorkflowStatus.release_requested.value,
        remarks=f"Release requested by {current_user.full_name}: {data.reason.strip()}",
        payload={"fdr_id": str(fdr.id), "fdr_number": fdr.fdr_number, "reason": data.reason.strip()},
    )

    db.commit()
    db.refresh(req)
    return _hydrate_release_response(req)


@router.get("/requests", response_model=List[ReleaseRequestResponse])
def list_release_requests(
    stage: Optional[WorkflowStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List release requests.

    Institution users see only requests for their own institution. Officers and admins see all.
    """
    query = (
        db.query(ReleaseRequest)
        .join(FDRRecord)
        .options(joinedload(ReleaseRequest.fdr).joinedload(FDRRecord.institution))
    )

    if current_user.role == UserRole.institution:
        if not current_user.institution_id:
            raise AppException(
                status_code=403,
                code="NO_INSTITUTION_AFFILIATION",
                message="Your account is not associated with any registered institution.",
            )
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    elif current_user.role == UserRole.officer and current_user.institution_id is not None:
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)

    if stage:
        query = query.filter(ReleaseRequest.stage == stage)

    requests = query.order_by(ReleaseRequest.created_at.desc()).all()
    return [_hydrate_release_response(r) for r in requests]


@router.get("/requests/{id}", response_model=ReleaseRequestResponse)
def get_release_request(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get single release request details with multi-tenant protection."""
    req = (
        db.query(ReleaseRequest)
        .options(joinedload(ReleaseRequest.fdr).joinedload(FDRRecord.institution))
        .filter(ReleaseRequest.id == id)
        .first()
    )
    if not req:
        raise NotFoundException(message=f"Release request '{id}' not found.", code="RELEASE_REQUEST_NOT_FOUND")

    if req.fdr:
        verify_institution_access(req.fdr.institution_id, current_user)

    return _hydrate_release_response(req)


@router.post("/requests/{id}/transition", response_model=ReleaseRequestResponse)
def transition_release_request(
    id: UUID,
    data: ReleaseTransitionRequest,
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Execute authoritative state machine transition for a release request.

    Enforces:
    - release_requested -> under_review (officer)
    - under_review -> conditions_checked | rejected (officer)
    - conditions_checked -> approval_pending | rejected (officer)
    - approval_pending -> approved | rejected (admin)
    - approved -> completed (admin, triggers instrument_status=released)
    """
    req_check = (
        db.query(ReleaseRequest)
        .options(joinedload(ReleaseRequest.fdr))
        .filter(ReleaseRequest.id == id)
        .first()
    )
    if not req_check:
        raise NotFoundException(message=f"Release request '{id}' not found.", code="RELEASE_REQUEST_NOT_FOUND")
    if req_check.fdr:
        verify_institution_access(req_check.fdr.institution_id, current_user)

    req = transition_release(
        db=db,
        release_request_id=id,
        to_stage=data.to_stage,
        actor=current_user,
        remarks=data.remarks,
    )
    db.commit()
    db.refresh(req)
    return _hydrate_release_response(req)

