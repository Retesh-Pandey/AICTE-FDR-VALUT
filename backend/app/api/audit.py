from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_user,
    get_db,
    require_role,
    verify_institution_access,
)
from app.core.exceptions import NotFoundException
from app.db.models import FDRRecord, User, UserRole, WorkflowAuditLog
from app.schemas.audit import AuditLogResponse, ChainVerificationResponse
from app.services.audit import verify_chain_integrity

router = APIRouter(prefix="", tags=["Audit Ledger"])


@router.get("/audit/verify-chain", response_model=ChainVerificationResponse)
def verify_audit_ledger_chain(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Admin-only endpoint to mathematically verify the SHA-256 tamper-evident hash chain."""
    result = verify_chain_integrity(db)
    return result


@router.get("/audit/logs", response_model=List[AuditLogResponse])
def get_audit_ledger_logs(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve audit ledger blocks. Admins and Officers view all blocks; institutions view their scoped entries."""
    query = db.query(WorkflowAuditLog)
    user_role_val = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
    if user_role_val == "institution":
        inst_fdr_ids = db.query(FDRRecord.id).filter(FDRRecord.institution_id == current_user.institution_id)
        query = query.filter(
            (WorkflowAuditLog.actor_id == current_user.id) |
            (WorkflowAuditLog.entity_id.in_(inst_fdr_ids))
        )
    return query.order_by(WorkflowAuditLog.id.desc()).limit(limit).all()


@router.get("/fdrs/{id}/audit", response_model=List[AuditLogResponse])
def get_fdr_audit_trail(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve immutable audit trail for a specific FDR record with institution scoping."""
    fdr = db.query(FDRRecord).filter(FDRRecord.id == id).first()
    if not fdr:
        raise NotFoundException(message=f"FDR record with id '{id}' not found", code="FDR_NOT_FOUND")

    # Enforce institutional scoping
    verify_institution_access(fdr.institution_id, current_user)

    audit_logs = (
        db.query(WorkflowAuditLog)
        .filter(
            WorkflowAuditLog.entity == "fdr",
            WorkflowAuditLog.entity_id == id
        )
        .order_by(WorkflowAuditLog.id.asc())
        .all()
    )
    return audit_logs
