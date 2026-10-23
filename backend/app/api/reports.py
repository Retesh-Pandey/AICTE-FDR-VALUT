from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.exceptions import ForbiddenException
from app.db.models import User, UserRole
from app.services.reports import (
    generate_csv_report,
    generate_excel_report,
    get_report_records,
)

router = APIRouter(prefix="/reports", tags=["Reporting & Exports"])


class ReportSummaryResponse(BaseModel):
    report_type: str
    total_records: int
    total_amount: float
    records: List[Dict[str, Any]]


def resolve_and_verify_report_scope(current_user: User, requested_institution_id: Optional[UUID]) -> Optional[UUID]:
    """Enforces multi-tenant institutional and official scoping for reporting and export endpoints.
    - Institutions may only access records belonging to their own assigned institution.
    - Scoped officers access only their assigned institution.
    - Council-wide officers and Admins may access all institutions or filter by a specific institution.
    """
    if current_user.role == UserRole.institution:
        if not current_user.institution_id:
            raise ForbiddenException(
                message="Access denied: Your account is not associated with any registered institution.",
                code="NO_INSTITUTION_AFFILIATION",
            )
        if requested_institution_id and requested_institution_id != current_user.institution_id:
            raise ForbiddenException(
                message="Cross-tenant access forbidden: institutions may only access reports for their own institution.",
                code="CROSS_TENANT_FORBIDDEN",
            )
        return current_user.institution_id

    if current_user.role == UserRole.officer and current_user.institution_id is not None:
        if requested_institution_id and requested_institution_id != current_user.institution_id:
            raise ForbiddenException(
                message="Access denied: Your official assignment is scoped exclusively to your assigned institution.",
                code="OFFICER_SCOPE_EXCEEDED",
            )
        return current_user.institution_id

    return requested_institution_id


@router.get("/data", response_model=ReportSummaryResponse)
def get_report_dataset(
    type: str = Query("all", pattern="^(all|active|expiring|pending|renewed|released)$"),
    institution_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns filtered report rows and summary telemetry for UI preview.
    Strictly scoped: Institution users only receive their own institution's data.
    Assigned officers only receive their assigned institution's data.
    Council-wide officers and Admins receive all data or specific requested institution.
    """
    effective_inst_id = resolve_and_verify_report_scope(current_user, institution_id)
    records = get_report_records(db, type, effective_inst_id)
    total_amount = sum(r["amount"] for r in records)

    return ReportSummaryResponse(
        report_type=type,
        total_records=len(records),
        total_amount=total_amount,
        records=records,
    )


@router.get("/export")
def export_report_excel(
    type: str = Query("all", pattern="^(all|active|expiring|pending|renewed|released)$"),
    institution_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Streams a professionally formatted Excel (.xlsx) workbook for the requested filter type.
    Includes customized header fills, Indian currency formatting, and a Generation Metadata sheet.
    Strictly tenant-scoped based on user role and assigned institution.
    """
    effective_inst_id = resolve_and_verify_report_scope(current_user, institution_id)
    excel_stream = generate_excel_report(db, type, current_user, effective_inst_id)
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"aicte_fdr_report_{type}_{now_str}.xlsx"

    return Response(
        content=excel_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/ledger-export")
def export_ledger_scoped(
    type: str = Query("all", pattern="^(all|active|expiring|pending|renewed|released)$"),
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    institution_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Authenticated export endpoint for ledger balance and registers.
    Strictly tenant-scoped: Institution users only receive their own institution's ledger data.
    Assigned officers only receive their assigned institution's ledger data.
    Council-wide officers and Administrators receive council-wide data (or specific institution if queried).
    """
    effective_inst_id = resolve_and_verify_report_scope(current_user, institution_id)
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if format == "csv":
        csv_data = generate_csv_report(db, type, effective_inst_id)
        filename = f"aicte_fdr_report_{type}_{now_str}.csv"
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    excel_stream = generate_excel_report(db, type, current_user, effective_inst_id)
    filename = f"aicte_fdr_report_{type}_{now_str}.xlsx"

    return Response(
        content=excel_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
