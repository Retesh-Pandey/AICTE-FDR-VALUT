"""Authoritative State Machine Engine for FDR Releases and Renewals.

Guarantees transactional consistency, strict role enforcement, mandatory audit logging,
and prevents invalid state jumps.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, NotFoundException
from app.db.models import (
    FDRRecord,
    InstrumentStatus,
    ReleaseRequest,
    User,
    UserRole,
    WorkflowStatus,
)
from app.services.audit import write_audit_log
from app.services.workflow.config import RELEASE_WORKFLOW, RENEWAL_WORKFLOW


def transition_release(
    db: Session,
    release_request_id: UUID,
    to_stage: WorkflowStatus,
    actor: User,
    remarks: Optional[str] = None,
) -> ReleaseRequest:
    """Execute a role-enforced transition on a release request and its linked FDR record.

    Ensures:
    1. The transition path exists in RELEASE_WORKFLOW.
    2. The actor holds the exact required role for that path.
    3. Mandatory remarks for approval/rejection.
    4. FDR instrument_status is ONLY set to 'released' when an admin transitions to 'completed'.
    5. State changes and audit entries are persisted within the same database transaction.
    """
    req = db.query(ReleaseRequest).filter(ReleaseRequest.id == release_request_id).first()
    if not req:
        raise NotFoundException(
            message=f"Release request '{release_request_id}' not found.",
            code="RELEASE_REQUEST_NOT_FOUND"
        )

    current_stage_str = req.stage.value if hasattr(req.stage, "value") else str(req.stage)
    target_stage_str = to_stage.value if hasattr(to_stage, "value") else str(to_stage)

    # 1. Validate transition existence
    allowed_transitions = RELEASE_WORKFLOW.get(current_stage_str, {})
    if target_stage_str not in allowed_transitions:
        raise AppException(
            status_code=409,
            code="INVALID_WORKFLOW_TRANSITION",
            message=(
                f"Transition from '{current_stage_str}' to '{target_stage_str}' is forbidden. "
                f"Allowed destinations: {list(allowed_transitions.keys())}"
            ),
        )

    # 2. Validate actor role
    required_roles = allowed_transitions[target_stage_str]["roles"]
    actor_role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
    if actor_role_str not in required_roles:
        raise AppException(
            status_code=403,
            code="FORBIDDEN_ROLE",
            message=(
                f"Role '{actor_role_str}' is not authorized to transition release request from "
                f"'{current_stage_str}' to '{target_stage_str}'. Required role(s): {required_roles}."
            ),
        )

    # 3. Mandatory remarks check
    if target_stage_str in ("approved", "rejected", "conditions_checked"):
        if not remarks or len(remarks.strip()) < 3:
            raise AppException(
                status_code=400,
                code="REMARKS_REQUIRED",
                message=f"Non-empty remarks are mandatory when transitioning stage to '{target_stage_str}'.",
            )

    # 4. Apply release request stage update
    req.stage = to_stage
    if remarks:
        req.remarks = remarks.strip()
    if actor.role in (UserRole.officer, UserRole.admin) and not req.assigned_officer:
        req.assigned_officer = actor.id

    # 5. Mirror to linked FDR record
    fdr = db.query(FDRRecord).filter(FDRRecord.id == req.fdr_id).first()
    if not fdr:
        raise NotFoundException(
            message=f"Linked FDR record '{req.fdr_id}' not found.",
            code="FDR_NOT_FOUND"
        )

    old_fdr_workflow = fdr.workflow_status.value if hasattr(fdr.workflow_status, "value") else str(fdr.workflow_status)
    old_fdr_instrument = fdr.instrument_status.value if hasattr(fdr.instrument_status, "value") else str(fdr.instrument_status)
    fdr.workflow_status = to_stage

    # ONLY human admin driving 'completed' can set instrument_status to 'released'
    if target_stage_str == "completed":
        fdr.instrument_status = InstrumentStatus.released

    # 6. Cryptographically chained audit entry (same transaction)
    write_audit_log(
        db=db,
        action=f"release_request.{target_stage_str}",
        entity="release_request",
        entity_id=req.id,
        actor_id=actor.id,
        actor_role=actor_role_str,
        old_status=current_stage_str,
        new_status=target_stage_str,
        remarks=remarks or f"Transitioned from {current_stage_str} to {target_stage_str}",
        payload={
            "fdr_id": str(req.fdr_id),
            "fdr_number": fdr.fdr_number,
            "old_fdr_instrument_status": old_fdr_instrument,
            "new_fdr_instrument_status": fdr.instrument_status.value,
            "old_workflow_status": old_fdr_workflow,
            "new_workflow_status": fdr.workflow_status.value,
        },
    )

    return req


def transition_renewal(
    db: Session,
    new_fdr_id: UUID,
    outcome: str,  # "approved" | "rejected"
    actor: User,
    remarks: Optional[str] = None,
) -> FDRRecord:
    """Execute approval or rejection on a pending renewal FDR record.

    Ensures:
    1. Actor is an authorized officer or admin.
    2. Remarks are mandatory.
    3. On 'approved': new record becomes 'active' + 'is_current=True',
       old record atomically becomes 'renewed' + 'is_current=False'.
    4. On 'rejected': new record becomes workflow_status 'rejected',
       old record remains unchanged.
    5. Both records audited in the same database transaction.
    """
    new_fdr = db.query(FDRRecord).filter(FDRRecord.id == new_fdr_id).first()
    if not new_fdr:
        raise NotFoundException(message=f"Renewal FDR '{new_fdr_id}' not found.", code="FDR_NOT_FOUND")

    actor_role_str = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
    allowed_roles = RENEWAL_WORKFLOW.get("renewal_review", {}).get(outcome, {}).get("roles", ["officer", "admin"])

    if actor_role_str not in allowed_roles:
        raise AppException(
            status_code=403,
            code="FORBIDDEN_ROLE",
            message=f"Role '{actor_role_str}' is not authorized to {outcome} renewals. Required: {allowed_roles}",
        )

    if not remarks or len(remarks.strip()) < 3:
        raise AppException(
            status_code=400,
            code="REMARKS_REQUIRED",
            message=f"Mandatory remarks required when renewal is {outcome}.",
        )

    if not new_fdr.previous_fdr_id:
        raise AppException(
            status_code=400,
            code="NOT_A_RENEWAL",
            message="Target FDR is not flagged as a renewal (missing previous_fdr_id).",
        )

    old_fdr = db.query(FDRRecord).filter(FDRRecord.id == new_fdr.previous_fdr_id).first()
    if not old_fdr:
        raise NotFoundException(
            message=f"Previous FDR '{new_fdr.previous_fdr_id}' not found.",
            code="PREVIOUS_FDR_NOT_FOUND"
        )

    if outcome == "approved":
        # Activate new FDR
        new_fdr.instrument_status = InstrumentStatus.active
        new_fdr.workflow_status = WorkflowStatus.approved
        new_fdr.is_current = True

        # Supersede old FDR
        old_instrument_status = old_fdr.instrument_status.value
        old_fdr.instrument_status = InstrumentStatus.renewed
        old_fdr.is_current = False

        # Audit old FDR supersession
        write_audit_log(
            db=db,
            action="fdr.superseded_by_renewal",
            entity="fdr",
            entity_id=old_fdr.id,
            actor_id=actor.id,
            actor_role=actor_role_str,
            old_status=old_instrument_status,
            new_status=InstrumentStatus.renewed.value,
            remarks=f"Superseded by renewal FDR {new_fdr.fdr_number}. Remarks: {remarks.strip()}",
            payload={"new_fdr_id": str(new_fdr.id), "new_fdr_number": new_fdr.fdr_number},
        )

        # Audit new FDR activation
        write_audit_log(
            db=db,
            action="fdr.renewal_approved",
            entity="fdr",
            entity_id=new_fdr.id,
            actor_id=actor.id,
            actor_role=actor_role_str,
            old_status=InstrumentStatus.submitted.value,
            new_status=InstrumentStatus.active.value,
            remarks=remarks.strip(),
            payload={"previous_fdr_id": str(old_fdr.id), "fdr_number": new_fdr.fdr_number},
        )

    elif outcome == "rejected":
        new_fdr.workflow_status = WorkflowStatus.rejected
        write_audit_log(
            db=db,
            action="fdr.renewal_rejected",
            entity="fdr",
            entity_id=new_fdr.id,
            actor_id=actor.id,
            actor_role=actor_role_str,
            old_status=new_fdr.instrument_status.value,
            new_status=new_fdr.instrument_status.value,
            remarks=remarks.strip(),
            payload={"previous_fdr_id": str(old_fdr.id), "outcome": "rejected"},
        )
    else:
        raise AppException(
            status_code=400,
            code="INVALID_OUTCOME",
            message=f"Renewal outcome must be 'approved' or 'rejected', got '{outcome}'.",
        )

    return new_fdr
