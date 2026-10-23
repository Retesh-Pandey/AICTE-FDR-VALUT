from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_role
from app.core.exceptions import ForbiddenException
from app.db.models import (
    FDRRecord,
    Institution,
    InstrumentStatus,
    User,
    UserRole,
    VerificationStatus,
    WorkflowStatus,
)
from app.schemas.fdr import FDRResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard Telemetry"])


class DashboardSummaryResponse(BaseModel):
    total_fdrs: int
    active_fdrs: int
    total_active_amount: Decimal
    expiring_30_days: int
    pending_verification: int
    flagged_discrepancies: int
    matured_fdrs: int
    recent_records: List[FDRResponse] = []


class PriorityCaseItem(BaseModel):
    fdr_id: UUID
    fdr_number: str
    institution_name: str
    bank_name: str
    amount: Decimal
    priority_type: str  # "discrepancy", "release_requested", "renewal_pending", "expiring_soon", "pending_verification"
    urgency: str  # "high", "medium", "low"
    reason: str
    days_until_maturity: Optional[int] = None
    created_at: datetime


class ChartTelemetryResponse(BaseModel):
    status_distribution: List[Dict[str, Any]]
    maturity_by_month: List[Dict[str, Any]]
    amount_by_bank: List[Dict[str, Any]]


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    institution_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns real-time dashboard telemetry and aggregated metrics derived from live application data.
    Automatically scoped to institution for institution accounts.
    """
    query = db.query(FDRRecord)

    # Multi-tenant and official scoping
    if current_user.role == UserRole.institution:
        if not current_user.institution_id:
            raise ForbiddenException(
                message="Access denied: Your user account is not associated with any registered institution.",
                code="NO_INSTITUTION_AFFILIATION",
            )
        if institution_id and institution_id != current_user.institution_id:
            raise ForbiddenException(
                message="Cross-tenant access forbidden: you may only view dashboard telemetry for your own institution.",
                code="CROSS_TENANT_FORBIDDEN",
            )
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    elif current_user.role == UserRole.officer and current_user.institution_id is not None:
        if institution_id and institution_id != current_user.institution_id:
            raise ForbiddenException(
                message="Access denied: Your official role is assigned exclusively to institution scope.",
                code="OFFICER_SCOPE_EXCEEDED",
            )
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    elif institution_id:
        query = query.filter(FDRRecord.institution_id == institution_id)

    today = date.today()
    in_30_days = today + timedelta(days=30)

    # 1. Total FDRs
    total_fdrs = query.count()

    # 2. Active FDRs count
    active_fdrs = query.filter(FDRRecord.instrument_status == InstrumentStatus.active).count()

    # 3. Total Active Amount
    total_active_val = (
        query.filter(FDRRecord.instrument_status == InstrumentStatus.active)
        .with_entities(func.coalesce(func.sum(FDRRecord.amount), Decimal("0")))
        .scalar()
    ) or Decimal("0")

    # 4. Expiring within 30 days
    expiring_30_days = query.filter(
        FDRRecord.maturity_date <= in_30_days,
        FDRRecord.maturity_date >= today,
        FDRRecord.instrument_status.in_([InstrumentStatus.active, InstrumentStatus.renewal_due]),
    ).count()

    # 5. Pending verification
    pending_verification = query.filter(
        FDRRecord.verification_status == VerificationStatus.pending
    ).count()

    # 6. Flagged discrepancies
    flagged_discrepancies = query.filter(
        FDRRecord.verification_status == VerificationStatus.discrepancy
    ).count()

    # 7. Matured FDRs
    matured_fdrs = query.filter(
        FDRRecord.instrument_status == InstrumentStatus.matured
    ).count()

    # 8. Recent 5 records
    recent_records = query.order_by(FDRRecord.created_at.desc()).limit(5).all()

    return DashboardSummaryResponse(
        total_fdrs=total_fdrs,
        active_fdrs=active_fdrs,
        total_active_amount=Decimal(str(total_active_val)),
        expiring_30_days=expiring_30_days,
        pending_verification=pending_verification,
        flagged_discrepancies=flagged_discrepancies,
        matured_fdrs=matured_fdrs,
        recent_records=recent_records,
    )


@router.get("/priority-cases", response_model=List[PriorityCaseItem])
def get_priority_cases(
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Returns prioritized cases requiring immediate regulatory review by AICTE Officers:
    - High Urgency: Flagged discrepancies, Open Release Requests, Pending Renewal Reviews
    - Medium Urgency: Deposits expiring in <= 30 days
    - Low Urgency: Newly submitted deposits pending bank verification
    """
    today = date.today()

    # Query all active or flagged records, scoped to officer assignment if applicable
    query = (
        db.query(FDRRecord, Institution.name.label("inst_name"))
        .join(Institution, FDRRecord.institution_id == Institution.id, isouter=True)
    )
    if current_user.role == UserRole.officer and current_user.institution_id is not None:
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)

    records = query.all()

    priority_cases: List[PriorityCaseItem] = []

    for fdr, inst_name in records:
        days_left = (fdr.maturity_date - today).days if fdr.maturity_date else None
        inst_label = inst_name or "Apex Institute of Technology"

        # 1. Flagged Discrepancy (Highest priority)
        if fdr.verification_status == VerificationStatus.discrepancy:
            priority_cases.append(PriorityCaseItem(
                fdr_id=fdr.id,
                fdr_number=fdr.fdr_number,
                institution_name=inst_label,
                bank_name=fdr.bank_name,
                amount=fdr.amount,
                priority_type="discrepancy",
                urgency="high",
                reason="Verification discrepancy flagged against CBS record. Needs statutory review.",
                days_until_maturity=days_left,
                created_at=fdr.created_at,
            ))
            continue

        # 2. Release Requested
        if fdr.workflow_status == WorkflowStatus.release_requested:
            priority_cases.append(PriorityCaseItem(
                fdr_id=fdr.id,
                fdr_number=fdr.fdr_number,
                institution_name=inst_label,
                bank_name=fdr.bank_name,
                amount=fdr.amount,
                priority_type="release_requested",
                urgency="high",
                reason="Institution filed formal release request. Stepper workflow awaiting action.",
                days_until_maturity=days_left,
                created_at=fdr.created_at,
            ))
            continue

        # 3. Renewal Review Pending
        if fdr.workflow_status == WorkflowStatus.renewal_review:
            priority_cases.append(PriorityCaseItem(
                fdr_id=fdr.id,
                fdr_number=fdr.fdr_number,
                institution_name=inst_label,
                bank_name=fdr.bank_name,
                amount=fdr.amount,
                priority_type="renewal_pending",
                urgency="high",
                reason="Renewal FDR instrument uploaded. Officer determination pending.",
                days_until_maturity=days_left,
                created_at=fdr.created_at,
            ))
            continue

        # 4. Expiring in <= 30 days
        if (
            fdr.instrument_status in [InstrumentStatus.active, InstrumentStatus.renewal_due]
            and days_left is not None
            and 0 <= days_left <= 30
        ):
            urgency = "high" if days_left <= 7 else "medium"
            priority_cases.append(PriorityCaseItem(
                fdr_id=fdr.id,
                fdr_number=fdr.fdr_number,
                institution_name=inst_label,
                bank_name=fdr.bank_name,
                amount=fdr.amount,
                priority_type="expiring_soon",
                urgency=urgency,
                reason=f"Maturity imminent in {days_left} days. Ensure timely renewal or lien discharge.",
                days_until_maturity=days_left,
                created_at=fdr.created_at,
            ))
            continue

        # 5. Pending Verification
        if fdr.verification_status == VerificationStatus.pending:
            priority_cases.append(PriorityCaseItem(
                fdr_id=fdr.id,
                fdr_number=fdr.fdr_number,
                institution_name=inst_label,
                bank_name=fdr.bank_name,
                amount=fdr.amount,
                priority_type="pending_verification",
                urgency="low",
                reason="Newly submitted receipt awaiting CBS verification run.",
                days_until_maturity=days_left,
                created_at=fdr.created_at,
            ))

    # Sort: high urgency first, then newest created_at first within each urgency tier
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    priority_cases.sort(
        key=lambda c: (
            urgency_order.get(c.urgency, 3),
            -(c.created_at.timestamp() if hasattr(c.created_at, "timestamp") else 0)
        )
    )

    return priority_cases[:50]


@router.get("/charts", response_model=ChartTelemetryResponse)
def get_dashboard_charts(
    institution_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns authentic analytics chart telemetry derived from actual database records:
    1. Status Distribution (donut chart metrics)
    2. Maturity by Month (bar chart metrics for upcoming 12 months)
    3. Amount by Issuing Bank (concentration bar chart)
    """
    query = db.query(FDRRecord)
    if current_user.role == UserRole.institution:
        if not current_user.institution_id:
            raise ForbiddenException(
                message="Access denied: Your user account is not associated with any registered institution.",
                code="NO_INSTITUTION_AFFILIATION",
            )
        if institution_id and institution_id != current_user.institution_id:
            raise ForbiddenException(
                message="Cross-tenant access forbidden: you may only view chart telemetry for your own institution.",
                code="CROSS_TENANT_FORBIDDEN",
            )
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    elif current_user.role == UserRole.officer and current_user.institution_id is not None:
        if institution_id and institution_id != current_user.institution_id:
            raise ForbiddenException(
                message="Access denied: Your official role is assigned exclusively to institution scope.",
                code="OFFICER_SCOPE_EXCEEDED",
            )
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    elif institution_id:
        query = query.filter(FDRRecord.institution_id == institution_id)

    all_fdrs = query.all()

    # 1. Status Distribution
    status_counts: Dict[str, Dict[str, Any]] = {
        "active": {"name": "Active Custody", "count": 0, "amount": 0.0, "color": "#10b981"},
        "renewal_due": {"name": "Renewal Due", "count": 0, "amount": 0.0, "color": "#f59e0b"},
        "matured": {"name": "Matured / Expired", "count": 0, "amount": 0.0, "color": "#f43f5e"},
        "renewed": {"name": "Renewed / Archived", "count": 0, "amount": 0.0, "color": "#8b5cf6"},
        "released": {"name": "Released / Discharged", "count": 0, "amount": 0.0, "color": "#06b6d4"},
    }

    for fdr in all_fdrs:
        st_val = fdr.instrument_status.value if fdr.instrument_status else "active"
        if st_val in status_counts:
            status_counts[st_val]["count"] += 1
            status_counts[st_val]["amount"] += float(fdr.amount or 0)

    status_dist = [
        {"status": k, **v} for k, v in status_counts.items()
    ]

    # 2. Maturity by Month (Next 12 months)
    today = date.today()
    month_buckets: Dict[str, Dict[str, Any]] = {}
    for i in range(12):
        target_month = (today.replace(day=1) + timedelta(days=i * 31)).strftime("%Y-%m")
        month_label = (today.replace(day=1) + timedelta(days=i * 31)).strftime("%b %y")
        month_buckets[target_month] = {"month": month_label, "count": 0, "amount": 0.0}

    for fdr in all_fdrs:
        if fdr.maturity_date:
            m_key = fdr.maturity_date.strftime("%Y-%m")
            if m_key in month_buckets:
                month_buckets[m_key]["count"] += 1
                month_buckets[m_key]["amount"] += float(fdr.amount or 0)

    maturity_by_month = list(month_buckets.values())

    # 3. Amount by Issuing Bank
    bank_buckets: Dict[str, Dict[str, Any]] = {}
    for fdr in all_fdrs:
        bank = fdr.bank_name or "Other Scheduled Bank"
        if bank not in bank_buckets:
            bank_buckets[bank] = {"bank_name": bank, "count": 0, "amount": 0.0}
        bank_buckets[bank]["count"] += 1
        bank_buckets[bank]["amount"] += float(fdr.amount or 0)

    # Sort top banks by amount
    amount_by_bank = sorted(bank_buckets.values(), key=lambda b: b["amount"], reverse=True)[:6]

    return ChartTelemetryResponse(
        status_distribution=status_dist,
        maturity_by_month=maturity_by_month,
        amount_by_bank=amount_by_bank,
    )
