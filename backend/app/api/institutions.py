from datetime import UTC, datetime
from math import ceil
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_user,
    get_db,
    require_role,
    verify_institution_access,
)
from app.core.exceptions import ConflictException, NotFoundException
from app.core.limiter import limiter
from app.db.models import (
    FDRRecord,
    Institution,
    InstitutionRegistrationRequest,
    Notification,
    RegistrationRequestStatus,
    User,
    UserRole,
)
from app.core.config import settings
from app.schemas.fdr import FDRResponse, HoldAppealRequest, InstitutionHoldStatus
from app.schemas.institution import (
    InstitutionCreate,
    InstitutionDirectoryPage,
    InstitutionDirectorySyncRequest,
    InstitutionDirectorySyncResponse,
    InstitutionPublicBrief,
    InstitutionRegistrationCreate,
    InstitutionRegistrationResponse,
    InstitutionRegistrationReview,
    InstitutionResponse,
)
from app.services.audit import write_audit_log
from app.services.escalation import (
    check_and_update_institution_hold,
    count_confirmed_unrelated_strikes,
    submit_institution_hold_appeal,
)

router = APIRouter(prefix="/institutions", tags=["Institutions"])



@router.get("/public-search", response_model=List[InstitutionPublicBrief])
@limiter.limit("30/minute")
def public_search_institutions(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100),
    db: Session = Depends(get_db)
):
    """
    Public rate-limited endpoint for institution sign-in type-ahead autocomplete.
    Searches registered technical institutions by name, AICTE permanent ID, or region.
    Exposes only non-sensitive directory data. All demo records are identified as synthetic.
    """
    term = f"%{q.strip().lower()}%"
    results = (
        db.query(Institution)
        .filter(
            or_(
                func.lower(Institution.name).like(term),
                func.lower(Institution.aicte_id).like(term),
                func.lower(Institution.region).like(term),
            )
        )
        .order_by(Institution.name.asc())
        .limit(8)
        .all()
    )
    return [
        InstitutionPublicBrief(
            id=inst.id,
            aicte_id=inst.aicte_id,
            name=inst.name,
            region=inst.region,
            source=getattr(inst, "source", "PORTAL_REGISTRY") or "PORTAL_REGISTRY",
            is_synthetic=True,
            last_synced_at=getattr(inst, "last_synced_at", None),
        )
        for inst in results
    ]


@router.get("/directory", response_model=InstitutionDirectoryPage)
@limiter.limit("30/minute")
def browse_institution_directory(
    request: Request,
    q: Optional[str] = Query(None, max_length=100),
    region: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Public paginated directory for browsing registered technical institutions.
    Provides browse-all functionality with coverage disclosure:
    Accurately indicates that the directory covers registered portal institutions
    while official national master directory synchronization is pending.
    """
    query = db.query(Institution)

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Institution.name).like(term),
                func.lower(Institution.aicte_id).like(term),
            )
        )

    if region and region.strip():
        query = query.filter(func.lower(Institution.region) == region.strip().lower())

    total = query.count()
    pages = max(1, ceil(total / limit))
    offset = (page - 1) * limit

    items = query.order_by(Institution.name.asc()).offset(offset).limit(limit).all()

    # Most recent synchronization timestamp
    latest_sync = db.query(func.max(Institution.last_synced_at)).scalar()

    return InstitutionDirectoryPage(
        items=[
            InstitutionPublicBrief(
                id=inst.id,
                aicte_id=inst.aicte_id,
                name=inst.name,
                region=inst.region,
                source=getattr(inst, "source", "PORTAL_REGISTRY") or "PORTAL_REGISTRY",
                is_synthetic=True,
                last_synced_at=getattr(inst, "last_synced_at", None),
            )
            for inst in items
        ],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        source_label="Registered Institutions in this Portal",
        coverage_disclaimer=(
            "Showing technical institutions currently registered in this AICTE FDR Portal. "
            "To register a newly approved or uncataloged college, use the 'Request Registration' flow below."
        ),
        last_synced_at=latest_sync,
    )


@router.post("/register-request", response_model=InstitutionRegistrationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def submit_institution_registration_request(
    request: Request,
    data: InstitutionRegistrationCreate,
    db: Session = Depends(get_db)
):
    """
    Public endpoint for institutions not found in the directory.
    Validates formatting, checks for duplicates, and creates a pending_verification request.
    DOES NOT grant portal access or create an active institution until verified by an Officer.
    """
    clean_name = data.institution_name.strip()
    clean_email = data.official_email.lower().strip()
    clean_aicte_id = data.aicte_id.strip() if data.aicte_id else None

    # 1. Duplicate check against active institutions
    existing_inst = None
    if clean_aicte_id:
        existing_inst = db.query(Institution).filter(func.lower(Institution.aicte_id) == clean_aicte_id.lower()).first()
    if not existing_inst:
        existing_inst = db.query(Institution).filter(func.lower(Institution.name) == clean_name.lower()).first()

    if existing_inst:
        raise ConflictException(
            message=(
                f"An institution with this AICTE ID or name is already registered: '{existing_inst.name}' "
                f"({existing_inst.aicte_id}). Please select it from the institution search bar."
            ),
            code="INSTITUTION_ALREADY_EXISTS",
        )

    # 2. Check for existing pending request with same email or AICTE ID
    query_existing_req = db.query(InstitutionRegistrationRequest).filter(
        InstitutionRegistrationRequest.status == RegistrationRequestStatus.pending_verification,
        or_(
            func.lower(InstitutionRegistrationRequest.official_email) == clean_email,
            func.lower(InstitutionRegistrationRequest.institution_name) == clean_name.lower(),
        )
    )
    if clean_aicte_id:
        query_existing_req = query_existing_req.filter(
            or_(
                func.lower(InstitutionRegistrationRequest.official_email) == clean_email,
                func.lower(InstitutionRegistrationRequest.aicte_id) == clean_aicte_id.lower(),
                func.lower(InstitutionRegistrationRequest.institution_name) == clean_name.lower(),
            )
        )
    pending_req = query_existing_req.first()

    if pending_req:
        raise ConflictException(
            message=(
                f"A verification request for '{pending_req.institution_name}' is already pending review "
                f"(Tracking Reference: REG-{pending_req.id.hex[:8].upper()}). "
                "An AICTE Vigilance Officer will review the official documents before activation."
            ),
            code="DUPLICATE_REGISTRATION_REQUEST",
        )

    # 3. Create pending verification request
    reg_req = InstitutionRegistrationRequest(
        institution_name=clean_name,
        aicte_id=clean_aicte_id,
        contact_person=data.contact_person.strip(),
        official_email=clean_email,
        region=data.region.strip() if data.region else None,
        address=data.address.strip() if data.address else None,
        status=RegistrationRequestStatus.pending_verification,
    )
    db.add(reg_req)
    db.flush()

    # 4. Notify Officers & Admins via notification telemetry
    officers = db.query(User).filter(User.role.in_([UserRole.officer, UserRole.admin])).all()
    for off in officers:
        notif = Notification(
            user_id=off.id,
            fdr_id=None,
            type="institution_registration_pending",
            milestone=f"reg_req_{reg_req.id}",
            message=(
                f"New institution onboarding request submitted: '{clean_name}' "
                f"(Contact: {data.contact_person}, {clean_email}). Requires statutory verification."
            ),
        )
        db.add(notif)

    # 5. Write audit trail
    write_audit_log(
        db=db,
        action="institution_registration.submitted",
        entity="institution_registration_request",
        entity_id=reg_req.id,
        actor_id=None,
        actor_role="applicant",
        new_status="pending_verification",
        remarks=f"Institution registration request filed for {clean_name}",
        payload={
            "institution_name": clean_name,
            "aicte_id": clean_aicte_id,
            "official_email": clean_email,
            "contact_person": data.contact_person.strip(),
        },
    )

    db.commit()
    db.refresh(reg_req)

    ref = f"REG-{reg_req.id.hex[:8].upper()}"
    return InstitutionRegistrationResponse(
        id=reg_req.id,
        institution_name=reg_req.institution_name,
        aicte_id=reg_req.aicte_id,
        contact_person=reg_req.contact_person,
        official_email=reg_req.official_email,
        region=reg_req.region,
        address=reg_req.address,
        status=reg_req.status.value if hasattr(reg_req.status, "value") else str(reg_req.status),
        review_decision=reg_req.review_decision,
        review_reason=reg_req.review_reason,
        reviewed_at=reg_req.reviewed_at,
        created_at=reg_req.created_at,
        tracking_reference=ref,
        notice=(
            f"Registration request {ref} received successfully with status 'pending_verification'. "
            "Portal access will only be granted after an authorized AICTE Vigilance Officer verifies the institution records."
        ),
    )


@router.get("/registration-requests", response_model=List[InstitutionRegistrationResponse])
def list_registration_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db)
):
    """List institution onboarding requests (Officers and Admins only)."""
    query = db.query(InstitutionRegistrationRequest)
    if status_filter:
        query = query.filter(InstitutionRegistrationRequest.status == status_filter)

    requests = query.order_by(InstitutionRegistrationRequest.created_at.desc()).all()
    return [
        InstitutionRegistrationResponse(
            id=r.id,
            institution_name=r.institution_name,
            aicte_id=r.aicte_id,
            contact_person=r.contact_person,
            official_email=r.official_email,
            region=r.region,
            address=r.address,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            review_decision=r.review_decision,
            review_reason=r.review_reason,
            reviewed_at=r.reviewed_at,
            created_at=r.created_at,
            tracking_reference=f"REG-{r.id.hex[:8].upper()}",
            notice=f"Request status: {r.status}",
        )
        for r in requests
    ]


@router.post("/registration-requests/{id}/review", response_model=InstitutionRegistrationResponse)
def review_institution_registration_request(
    id: UUID,
    review_data: InstitutionRegistrationReview,
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db)
):
    """
    Adjudicate an institution registration request (Approve, Reject, or mark Duplicate).
    Requires authorized Officer or Admin role with audit trail logging.
    If approved, automatically registers the active Institution.
    """
    req = db.query(InstitutionRegistrationRequest).filter(InstitutionRegistrationRequest.id == id).first()
    if not req:
        raise NotFoundException(message=f"Registration request '{id}' not found", code="REQUEST_NOT_FOUND")

    if req.status != RegistrationRequestStatus.pending_verification:
        raise ConflictException(
            message=f"This registration request has already been adjudicated as '{req.status}'",
            code="REQUEST_ALREADY_ADJUDICATED",
        )

    now = datetime.now(UTC)
    old_status = req.status.value if hasattr(req.status, "value") else str(req.status)
    req.reviewed_by = current_user.id
    req.review_decision = review_data.decision
    req.review_reason = review_data.review_reason.strip()
    req.reviewed_at = now

    created_inst_id = None
    if review_data.decision == "approved":
        req.status = RegistrationRequestStatus.approved

        # Ensure unique AICTE ID
        final_aicte_id = req.aicte_id or f"AICTE-1-{req.id.hex[:7].upper()}"
        existing = db.query(Institution).filter(Institution.aicte_id == final_aicte_id).first()
        if existing:
            final_aicte_id = f"AICTE-REQ-{req.id.hex[:7].upper()}"

        new_inst = Institution(
            aicte_id=final_aicte_id,
            name=req.institution_name,
            region=req.region,
            address=req.address,
            contact_email=req.official_email,
            source="APPROVED_REQUEST",
            last_synced_at=now,
        )
        db.add(new_inst)
        db.flush()
        req.institution_id = new_inst.id
        created_inst_id = new_inst.id

    elif review_data.decision == "duplicate":
        req.status = RegistrationRequestStatus.duplicate
    else:
        req.status = RegistrationRequestStatus.rejected

    # Write audit log
    write_audit_log(
        db=db,
        action=f"institution_registration.{review_data.decision}",
        entity="institution_registration_request",
        entity_id=req.id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role),
        old_status=old_status,
        new_status=req.status.value if hasattr(req.status, "value") else str(req.status),
        remarks=f"Registration {review_data.decision.upper()}: {review_data.review_reason.strip()}",
        payload={
            "institution_name": req.institution_name,
            "official_email": req.official_email,
            "created_institution_id": str(created_inst_id) if created_inst_id else None,
            "decision": review_data.decision,
            "reason": review_data.review_reason.strip(),
        },
    )

    db.commit()
    db.refresh(req)

    ref = f"REG-{req.id.hex[:8].upper()}"
    return InstitutionRegistrationResponse(
        id=req.id,
        institution_name=req.institution_name,
        aicte_id=req.aicte_id,
        contact_person=req.contact_person,
        official_email=req.official_email,
        region=req.region,
        address=req.address,
        status=req.status.value if hasattr(req.status, "value") else str(req.status),
        review_decision=req.review_decision,
        review_reason=req.review_reason,
        reviewed_at=req.reviewed_at,
        created_at=req.created_at,
        tracking_reference=ref,
        notice=f"Request {ref} was adjudicated as '{req.status}' by {current_user.email}.",
    )


@router.post("/sync-directory", response_model=InstitutionDirectorySyncResponse)
def sync_institution_directory(
    payload: InstitutionDirectorySyncRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """
    Sovereign Administrator batch import/sync of institutions from an authorized directory source.
    Includes duplicate detection and comprehensive error tracking for rejected rows.
    """
    now = datetime.now(UTC)
    total = len(payload.institutions)
    created = 0
    updated = 0
    skipped = 0
    rejected: List[dict] = []

    for idx, item in enumerate(payload.institutions):
        aicte_id = item.aicte_id.strip() if item.aicte_id else ""
        name = item.name.strip() if item.name else ""

        if not aicte_id or not name:
            rejected.append({"index": idx, "aicte_id": aicte_id, "name": name, "reason": "Missing required aicte_id or name"})
            continue

        existing = db.query(Institution).filter(func.lower(Institution.aicte_id) == aicte_id.lower()).first()
        if existing:
            # Update fields if changed
            existing.name = name
            if item.region:
                existing.region = item.region
            if item.address:
                existing.address = item.address
            if item.contact_email:
                existing.contact_email = item.contact_email
            existing.source = payload.source
            existing.last_synced_at = now
            updated += 1
        else:
            new_inst = Institution(
                aicte_id=aicte_id,
                name=name,
                region=item.region,
                address=item.address,
                contact_email=item.contact_email,
                source=payload.source,
                last_synced_at=now,
            )
            db.add(new_inst)
            created += 1

    write_audit_log(
        db=db,
        action="institution_directory.sync",
        entity="institution",
        entity_id=None,
        actor_id=current_user.id,
        actor_role=current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role),
        remarks=f"Directory sync from '{payload.source}': {created} created, {updated} updated, {len(rejected)} rejected.",
        payload={
            "source": payload.source,
            "total_processed": total,
            "created": created,
            "updated": updated,
            "rejected_count": len(rejected),
        },
    )

    db.commit()

    return InstitutionDirectorySyncResponse(
        total_processed=total,
        created_count=created,
        updated_count=updated,
        skipped_count=skipped,
        rejected_rows=rejected,
        source=payload.source,
        timestamp=now,
    )


@router.get("", response_model=List[InstitutionResponse])
def list_institutions(
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db)
):
    """List registered technical institutions (Officers & Admins only, scoped to assigned jurisdiction)."""
    query = db.query(Institution)
    if current_user.role == UserRole.officer and current_user.institution_id is not None:
        query = query.filter(Institution.id == current_user.institution_id)
    institutions = query.order_by(Institution.name.asc()).all()
    return institutions



@router.post("", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
def create_institution(
    data: InstitutionCreate,
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Register a new technical institution under AICTE jurisdiction."""
    existing = db.query(Institution).filter(Institution.aicte_id == data.aicte_id.strip()).first()
    if existing:
        raise ConflictException(
            message=f"Institution with AICTE ID '{data.aicte_id}' already registered",
            code="INSTITUTION_EXISTS"
        )

    inst = Institution(
        aicte_id=data.aicte_id.strip(),
        name=data.name.strip(),
        region=data.region,
        address=data.address,
        contact_email=data.contact_email,
        source=data.source or "PORTAL_REGISTRY",
        last_synced_at=datetime.now(UTC),
    )
    db.add(inst)
    db.flush()

    write_audit_log(
        db=db,
        action="institution.created",
        entity="institution",
        entity_id=inst.id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role),
        remarks=f"Registered institution {inst.name} ({inst.aicte_id})",
        payload={"aicte_id": inst.aicte_id, "name": inst.name, "region": inst.region}
    )
    db.commit()
    db.refresh(inst)
    return inst


@router.get("/{id}", response_model=InstitutionResponse)
def get_institution(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get institution details by UUID with tenant authorization."""
    verify_institution_access(id, current_user)
    inst = db.query(Institution).filter(Institution.id == id).first()
    if not inst:
        raise NotFoundException(message=f"Institution with id '{id}' not found", code="INSTITUTION_NOT_FOUND")
    return inst


@router.get("/{id}/fdrs", response_model=List[FDRResponse])
def get_institution_fdrs(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all FDR security deposit records for an institution."""
    verify_institution_access(id, current_user)
    inst = db.query(Institution).filter(Institution.id == id).first()
    if not inst:
        raise NotFoundException(message=f"Institution with id '{id}' not found", code="INSTITUTION_NOT_FOUND")

    fdrs = (
        db.query(FDRRecord)
        .filter(FDRRecord.institution_id == id)
        .order_by(FDRRecord.created_at.desc())
        .all()
    )
    return fdrs


@router.get("/{id}/hold-status", response_model=InstitutionHoldStatus)
def get_institution_hold_status(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns current upload review hold status and confirmed strikes metrics for an institution.
    Tenant isolation: Institution users can only view their own institution's status.
    """
    verify_institution_access(id, current_user)
    inst = db.query(Institution).filter(Institution.id == id).first()
    if not inst:
        raise NotFoundException(message=f"Institution with id '{id}' not found", code="INSTITUTION_NOT_FOUND")

    check_and_update_institution_hold(db, inst)
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


@router.post("/{id}/appeal-hold", response_model=InstitutionHoldStatus)
def appeal_institution_upload_hold(
    id: UUID,
    body: HoldAppealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit an appeal / review request regarding an active upload hold.
    Tenant isolation: Institution accounts may ONLY appeal their own institution's hold.
    """
    verify_institution_access(id, current_user)
    inst = submit_institution_hold_appeal(
        db=db,
        institution_id=id,
        appeal_reason=body.appeal_reason,
        user=current_user,
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

