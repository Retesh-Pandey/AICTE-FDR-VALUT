from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException, NotFoundException
from app.db.models import (
    DocumentSubmissionReview,
    Institution,
    Notification,
    User,
    UserRole,
)
from app.services.audit import write_audit_log


def check_and_update_institution_hold(db: Session, institution: Institution) -> bool:
    """
    Checks if an institution's upload review hold is active.
    If the hold duration has expired, automatically clears the hold,
    logs the event in the audit ledger, and returns False (hold no longer active).
    """
    if not institution.upload_hold_active:
        return False

    now = datetime.now(UTC)
    hold_until = institution.upload_hold_until
    if hold_until is not None:
        if hold_until.tzinfo is None:
            hold_until = hold_until.replace(tzinfo=UTC)
        if now >= hold_until:
            # Automatic expiry
            old_until = str(institution.upload_hold_until)
            institution.upload_hold_active = False
            institution.upload_hold_until = None
            institution.upload_hold_reason = f"Hold automatically expired on {now.isoformat()} (was set until {old_until})"

        write_audit_log(
            db=db,
            action="institution.upload_hold_expired",
            entity="institution",
            entity_id=institution.id,
            actor_id=None,
            actor_role="system",
            old_status="upload_hold",
            new_status="active",
            remarks=f"Upload review hold for {institution.name} expired automatically after its configured duration.",
            payload={"expired_at": now.isoformat(), "previous_hold_until": old_until},
        )
        db.commit()
        return False

    return True


def count_confirmed_unrelated_strikes(
    db: Session, institution_id: UUID, window_days: Optional[int] = None
) -> int:
    """
    Counts confirmed unrelated submissions for an institution within a rolling time window.
    SAFETY RULES:
      - Counts ONLY submissions that were successfully processed and later confirmed
        unrelated by an authorized Officer/Admin (is_strike=True).
      - Deduplicates repeated attempts with the same file hash so retries do not create multiple strikes.
      - NEVER counts OCR outages, unreadable scans, corrupt files, low-confidence, or system errors.
    """
    days = window_days or settings.UNRELATED_WINDOW_DAYS
    cutoff = datetime.now(UTC) - timedelta(days=days)

    distinct_hashes_count = (
        db.query(func.count(distinct(DocumentSubmissionReview.document_sha256)))
        .filter(
            DocumentSubmissionReview.institution_id == institution_id,
            DocumentSubmissionReview.review_status == "confirmed_unrelated",
            DocumentSubmissionReview.is_strike == True,
            DocumentSubmissionReview.reviewed_at >= cutoff,
        )
        .scalar()
        or 0
    )
    return int(distinct_hashes_count)


def record_submission_for_review(
    db: Session,
    institution_id: UUID,
    filename: str,
    sha256_hash: str,
    classification_dict: Dict[str, Any],
    storage_path: Optional[str] = None,
    fdr_id: Optional[UUID] = None,
) -> DocumentSubmissionReview:
    """
    Staging entry in the Document Review Queue for low-confidence, unreadable,
    or likely-unrelated uploads.
    Does NOT increment strike count. Strikes are ONLY assigned if an authorized
    Officer/Admin explicitly confirms the document as unrelated.
    """
    existing_item = (
        db.query(DocumentSubmissionReview)
        .filter(
            DocumentSubmissionReview.institution_id == institution_id,
            DocumentSubmissionReview.document_sha256 == sha256_hash,
            DocumentSubmissionReview.review_status == "pending",
        )
        .first()
    )

    if existing_item:
        existing_item.filename = filename
        existing_item.classification = classification_dict.get("status", "needs_review")
        existing_item.confidence = classification_dict.get("confidence", 0.0)
        existing_item.classification_reasons = classification_dict.get("classification_reasons")
        existing_item.detected_document_type = classification_dict.get("detected_document_type")
        existing_item.content_summary = classification_dict.get("content_summary")
        existing_item.extracted_snippets = classification_dict.get("extracted_snippets")
        if storage_path:
            existing_item.storage_path = storage_path
        if fdr_id:
            existing_item.fdr_id = fdr_id
        db.flush()
        return existing_item

    review_item = DocumentSubmissionReview(
        institution_id=institution_id,
        fdr_id=fdr_id,
        document_sha256=sha256_hash,
        filename=filename,
        storage_path=storage_path,
        classification=classification_dict.get("status", "possibly_fdr_needs_review"),
        confidence=classification_dict.get("confidence", 0.0),
        classification_reasons=classification_dict.get("classification_reasons"),
        detected_document_type=classification_dict.get("detected_document_type"),
        content_summary=classification_dict.get("content_summary"),
        extracted_snippets=classification_dict.get("extracted_snippets"),
        review_status="pending",
        is_strike=False,
    )
    db.add(review_item)
    db.flush()
    return review_item


def adjudicate_document_submission(
    db: Session,
    review_id: UUID,
    decision: str,
    reason: str,
    reviewer: User,
) -> DocumentSubmissionReview:
    """
    Adjudicates a document in the Officer/Admin review queue.
    Decisions:
      - 'confirm_unrelated': Confirms file is an unrelated document.
         Checks deduplication by file hash. If threshold reached, triggers temporary upload hold.
      - 'override_as_fdr': Overrides classification; permits institution submission as FDR.
      - 'dismiss': Dismisses review without strike.
    """
    if decision not in ("confirm_unrelated", "override_as_fdr", "dismiss"):
        raise AppException(
            status_code=400,
            code="INVALID_ADJUDICATION_DECISION",
            message=f"Invalid decision '{decision}'. Must be 'confirm_unrelated', 'override_as_fdr', or 'dismiss'.",
        )

    if not reason or not reason.strip():
        raise AppException(
            status_code=400,
            code="REVIEW_REASON_REQUIRED",
            message="A substantive adjudication reason is mandatory for audit compliance.",
        )

    item = db.query(DocumentSubmissionReview).filter(DocumentSubmissionReview.id == review_id).first()
    if not item:
        raise NotFoundException(
            message=f"Document review item '{review_id}' not found.",
            code="REVIEW_ITEM_NOT_FOUND",
        )

    inst = db.query(Institution).filter(Institution.id == item.institution_id).first()
    if not inst:
        raise NotFoundException(message="Institution associated with document not found.", code="INSTITUTION_NOT_FOUND")

    now = datetime.now(UTC)
    clean_reason = reason.strip()
    item.reviewed_by = reviewer.id
    item.reviewed_at = now
    item.review_reason = clean_reason

    if decision == "confirm_unrelated":
        item.review_status = "confirmed_unrelated"

        # Check deduplication: did this institution already have a strike for this exact sha256 within the window?
        cutoff = now - timedelta(days=settings.UNRELATED_WINDOW_DAYS)
        existing_strike = (
            db.query(DocumentSubmissionReview)
            .filter(
                DocumentSubmissionReview.institution_id == item.institution_id,
                DocumentSubmissionReview.document_sha256 == item.document_sha256,
                DocumentSubmissionReview.is_strike == True,
                DocumentSubmissionReview.reviewed_at >= cutoff,
                DocumentSubmissionReview.id != item.id,
            )
            .first()
        )

        if existing_strike:
            # Deduplicated: retrying same file hash does not generate multiple strikes
            item.is_strike = False
            strike_note = "Duplicate file hash within rolling window — deduplicated (strike not incremented)."
        else:
            item.is_strike = True
            strike_note = "Distinct confirmed unrelated submission — strike recorded."

        db.flush()

        # Recount current confirmed strikes
        current_strikes = count_confirmed_unrelated_strikes(db, item.institution_id)

        # Audit log for adjudication
        write_audit_log(
            db=db,
            action="document_review.confirmed_unrelated",
            entity="document_review",
            entity_id=item.id,
            actor_id=reviewer.id,
            actor_role=reviewer.role.value if hasattr(reviewer.role, "value") else str(reviewer.role),
            old_status="pending",
            new_status="confirmed_unrelated",
            remarks=f"Document confirmed unrelated for {inst.name}: {clean_reason} ({strike_note})",
            payload={
                "document_sha256": item.document_sha256,
                "is_strike": item.is_strike,
                "current_strikes_in_window": current_strikes,
                "strike_threshold": settings.UNRELATED_STRIKE_THRESHOLD,
            },
        )

        # Check threshold for temporary upload review hold
        if current_strikes >= settings.UNRELATED_STRIKE_THRESHOLD and not inst.upload_hold_active:
            hold_until = now + timedelta(days=settings.REVIEW_HOLD_DAYS)
            inst.upload_hold_active = True
            inst.upload_hold_until = hold_until
            inst.upload_hold_placed_by = reviewer.id
            inst.upload_hold_placed_at = now
            inst.upload_hold_reason = (
                f"Temporary review hold applied: {current_strikes} confirmed unrelated submissions recorded "
                f"within {settings.UNRELATED_WINDOW_DAYS} days (threshold: {settings.UNRELATED_STRIKE_THRESHOLD})."
            )

            # 1. Notify institution users
            inst_users = db.query(User).filter(User.institution_id == inst.id).all()
            for u in inst_users:
                db.add(
                    Notification(
                        user_id=u.id,
                        fdr_id=None,
                        type="upload_hold",
                        milestone=f"HOLD-{now.strftime('%Y%m%d')}",
                        message=(
                            f"FDR uploads for {inst.name} have been placed on a temporary review hold until "
                            f"{hold_until.strftime('%d-%b-%Y %H:%M UTC')}. Existing FDR records remain available for read-only access. "
                            "You may submit an administrative appeal through the portal."
                        ),
                    )
                )

            # 2. Notify Admins
            admin_users = db.query(User).filter(User.role == UserRole.admin).all()
            for a in admin_users:
                db.add(
                    Notification(
                        user_id=a.id,
                        fdr_id=None,
                        type="admin_escalation",
                        milestone=f"HOLD-ADMIN-{inst.id.hex[:6]}",
                        message=(
                            f"Administrative Escalation: {inst.name} has reached {current_strikes} confirmed unrelated "
                            f"submissions. Upload review hold applied until {hold_until.strftime('%d-%b-%Y')}."
                        ),
                    )
                )

            # Audit log for hold placement
            write_audit_log(
                db=db,
                action="institution.upload_hold_placed",
                entity="institution",
                entity_id=inst.id,
                actor_id=reviewer.id,
                actor_role=reviewer.role.value if hasattr(reviewer.role, "value") else str(reviewer.role),
                old_status="active",
                new_status="upload_hold",
                remarks=inst.upload_hold_reason,
                payload={
                    "hold_until": hold_until.isoformat(),
                    "confirmed_strikes": current_strikes,
                    "window_days": settings.UNRELATED_WINDOW_DAYS,
                    "hold_days": settings.REVIEW_HOLD_DAYS,
                },
            )

    elif decision == "override_as_fdr":
        item.review_status = "overridden_as_fdr"
        item.is_strike = False

        write_audit_log(
            db=db,
            action="document_review.overridden_as_fdr",
            entity="document_review",
            entity_id=item.id,
            actor_id=reviewer.id,
            actor_role=reviewer.role.value if hasattr(reviewer.role, "value") else str(reviewer.role),
            old_status="pending",
            new_status="overridden_as_fdr",
            remarks=f"Document overridden as FDR receipt by {reviewer.full_name}: {clean_reason}",
            payload={"document_sha256": item.document_sha256},
        )

    elif decision == "dismiss":
        item.review_status = "dismissed"
        item.is_strike = False

        write_audit_log(
            db=db,
            action="document_review.dismissed",
            entity="document_review",
            entity_id=item.id,
            actor_id=reviewer.id,
            actor_role=reviewer.role.value if hasattr(reviewer.role, "value") else str(reviewer.role),
            old_status="pending",
            new_status="dismissed",
            remarks=f"Document review dismissed by {reviewer.full_name}: {clean_reason}",
            payload={"document_sha256": item.document_sha256},
        )

    db.commit()
    db.refresh(item)
    return item


def admin_unfreeze_institution_hold(
    db: Session,
    institution_id: UUID,
    reason: str,
    admin_user: User,
) -> Institution:
    """
    Administrative action to lift / remove an institution's temporary upload hold.
    Strictly restricted to Admin role with cryptographic audit trail.
    """
    if admin_user.role != UserRole.admin:
        raise AppException(
            status_code=403,
            code="ADMIN_ROLE_REQUIRED",
            message="Only authorized AICTE System Administrators can remove an institution upload review hold.",
        )

    if not reason or not reason.strip():
        raise AppException(
            status_code=400,
            code="UNFREEZE_REASON_REQUIRED",
            message="A justification reason is required to remove an institution upload review hold.",
        )

    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise NotFoundException(message="Institution not found.", code="INSTITUTION_NOT_FOUND")

    if not inst.upload_hold_active:
        return inst

    clean_reason = reason.strip()
    old_until = str(inst.upload_hold_until)
    inst.upload_hold_active = False
    inst.upload_hold_until = None
    inst.upload_hold_reason = f"Hold removed by Administrator ({admin_user.full_name}): {clean_reason}"

    write_audit_log(
        db=db,
        action="institution.upload_hold_removed",
        entity="institution",
        entity_id=inst.id,
        actor_id=admin_user.id,
        actor_role=admin_user.role.value if hasattr(admin_user.role, "value") else str(admin_user.role),
        old_status="upload_hold",
        new_status="active",
        remarks=f"Upload hold removed by Administrator {admin_user.full_name}: {clean_reason}",
        payload={"reason": clean_reason, "previous_hold_until": old_until},
    )

    # Notify institution
    inst_users = db.query(User).filter(User.institution_id == inst.id).all()
    for u in inst_users:
        db.add(
            Notification(
                user_id=u.id,
                fdr_id=None,
                type="hold_cleared",
                milestone=f"HOLD-CLEARED-{datetime.now(UTC).strftime('%Y%m%d%H%M')}",
                message=(
                    f"The upload review hold for {inst.name} has been cleared by AICTE Administration. "
                    "FDR document submissions are now restored."
                ),
            )
        )

    db.commit()
    db.refresh(inst)
    return inst


def admin_extend_institution_hold(
    db: Session,
    institution_id: UUID,
    days: int,
    reason: str,
    admin_user: User,
) -> Institution:
    """
    Administrative action to extend an institution's upload review hold.
    Strictly restricted to Admin role with cryptographic audit trail.
    """
    if admin_user.role != UserRole.admin:
        raise AppException(
            status_code=403,
            code="ADMIN_ROLE_REQUIRED",
            message="Only authorized AICTE System Administrators can extend an upload review hold.",
        )

    if days <= 0 or days > 90:
        raise AppException(
            status_code=400,
            code="INVALID_HOLD_DURATION",
            message="Extension duration must be between 1 and 90 days.",
        )

    if not reason or not reason.strip():
        raise AppException(
            status_code=400,
            code="EXTENSION_REASON_REQUIRED",
            message="A substantive reason is required to extend an institution upload review hold.",
        )

    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise NotFoundException(message="Institution not found.", code="INSTITUTION_NOT_FOUND")

    now = datetime.now(UTC)
    base_date = inst.upload_hold_until if (inst.upload_hold_until and inst.upload_hold_until > now) else now
    new_until = base_date + timedelta(days=days)
    old_until = str(inst.upload_hold_until)

    inst.upload_hold_active = True
    inst.upload_hold_until = new_until
    inst.upload_hold_reason = f"Hold extended by {days} days by Admin {admin_user.full_name}: {reason.strip()}"

    write_audit_log(
        db=db,
        action="institution.upload_hold_extended",
        entity="institution",
        entity_id=inst.id,
        actor_id=admin_user.id,
        actor_role=admin_user.role.value if hasattr(admin_user.role, "value") else str(admin_user.role),
        old_status=old_until,
        new_status=new_until.isoformat(),
        remarks=f"Upload hold extended for {inst.name} by {days} days: {reason.strip()}",
        payload={"extended_by_days": days, "new_hold_until": new_until.isoformat(), "reason": reason.strip()},
    )

    db.commit()
    db.refresh(inst)
    return inst


def submit_institution_hold_appeal(
    db: Session,
    institution_id: UUID,
    appeal_reason: str,
    user: User,
) -> Institution:
    """
    Institution-initiated appeal / review request regarding an active upload hold.
    Tenant isolation: Institution accounts may ONLY appeal their own institution's hold.
    """
    if user.role == UserRole.institution and user.institution_id != institution_id:
        raise AppException(
            status_code=403,
            code="CROSS_TENANT_FORBIDDEN",
            message="Institution users may only submit appeals for their own registered institution.",
        )

    if not appeal_reason or len(appeal_reason.strip()) < 10:
        raise AppException(
            status_code=400,
            code="APPEAL_REASON_TOO_SHORT",
            message="Please provide a detailed appeal statement (minimum 10 characters).",
        )

    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise NotFoundException(message="Institution not found.", code="INSTITUTION_NOT_FOUND")

    now = datetime.now(UTC)
    clean_appeal = appeal_reason.strip()
    inst.upload_hold_appealed_at = now
    inst.upload_hold_appeal_reason = clean_appeal

    write_audit_log(
        db=db,
        action="institution.upload_hold_appeal_submitted",
        entity="institution",
        entity_id=inst.id,
        actor_id=user.id,
        actor_role=user.role.value if hasattr(user.role, "value") else str(user.role),
        old_status="held_unappealed",
        new_status="held_appealed",
        remarks=f"Upload review hold appeal submitted for {inst.name} by {user.full_name or user.email}: {clean_appeal}",
        payload={"appeal_reason": clean_appeal, "appealed_at": now.isoformat()},
    )

    # Notify Admins of the appeal
    admin_users = db.query(User).filter(User.role == UserRole.admin).all()
    for a in admin_users:
        db.add(
            Notification(
                user_id=a.id,
                fdr_id=None,
                type="hold_appeal",
                milestone=f"APPEAL-{inst.id.hex[:6]}",
                message=f"Appeal Submitted: {inst.name} has requested review of their FDR upload review hold.",
            )
        )

    db.commit()
    db.refresh(inst)
    return inst
