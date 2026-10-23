from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.models import FDRRecord, Notification, User, UserRole
from app.schemas.notification import NotificationListResponse, NotificationResponse

router = APIRouter(prefix="/notifications", tags=["System Notifications & Alerts"])


@router.get("", response_model=NotificationListResponse)
def get_user_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve notifications relevant to the authenticated user.

    Returns unread count and chronologically ordered alert entries.
    """
    query = db.query(Notification)

    if current_user.role == UserRole.institution:
        # User's direct notifications or notifications linked to user's institution
        if current_user.institution_id:
            query = query.outerjoin(FDRRecord, Notification.fdr_id == FDRRecord.id).filter(
                (Notification.user_id == current_user.id)
                | (FDRRecord.institution_id == current_user.institution_id)
            )
        else:
            query = query.filter(Notification.user_id == current_user.id)
    elif current_user.role == UserRole.officer and current_user.institution_id is not None:
        # Scoped officer: direct notifications or notifications linked to assigned institution
        query = query.outerjoin(FDRRecord, Notification.fdr_id == FDRRecord.id).filter(
            (Notification.user_id == current_user.id)
            | (FDRRecord.institution_id == current_user.institution_id)
        )
    else:
        # Council-wide Officers and Admins receive council-wide notifications and direct assignments
        query = query.filter(
            (Notification.user_id == current_user.id)
            | (Notification.user_id.is_(None))
        )

    all_notifs = query.order_by(Notification.created_at.desc()).limit(100).all()
    unread_count = sum(1 for n in all_notifs if n.read_at is None)

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in all_notifs],
        total=len(all_notifs),
        unread_count=unread_count,
    )


@router.post("/{id}/read", response_model=NotificationResponse)
def mark_notification_read(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as read with tenant authorization check."""
    notif = db.query(Notification).filter(Notification.id == id).first()
    if not notif:
        raise NotFoundException(message=f"Notification '{id}' not found.", code="NOTIFICATION_NOT_FOUND")

    # Verify authorization to modify this notification
    if current_user.role == UserRole.institution:
        is_owner = notif.user_id == current_user.id
        is_inst = bool(notif.fdr and current_user.institution_id and notif.fdr.institution_id == current_user.institution_id)
        if not (is_owner or is_inst):
            raise ForbiddenException(message="Access denied: Cannot modify notification for another tenant.", code="FORBIDDEN_NOTIFICATION")
    elif current_user.role == UserRole.officer and current_user.institution_id is not None:
        is_assigned = notif.user_id == current_user.id
        is_inst = bool(notif.fdr and notif.fdr.institution_id == current_user.institution_id)
        if not (is_assigned or is_inst):
            raise ForbiddenException(message="Access denied outside assigned institution scope.", code="OFFICER_SCOPE_EXCEEDED")

    if not notif.read_at:
        notif.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notif)

    return NotificationResponse.model_validate(notif)



@router.post("/read-all", response_model=dict)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all unread notifications for the user as read."""
    now = datetime.now(UTC)
    query = db.query(Notification).filter(Notification.read_at.is_(None))

    if current_user.role == UserRole.institution:
        if current_user.institution_id:
            notif_ids = [
                n.id
                for n in query.outerjoin(FDRRecord, Notification.fdr_id == FDRRecord.id)
                .filter(
                    (Notification.user_id == current_user.id)
                    | (FDRRecord.institution_id == current_user.institution_id)
                )
                .all()
            ]
            if notif_ids:
                count = (
                    db.query(Notification)
                    .filter(Notification.id.in_(notif_ids))
                    .update({"read_at": now}, synchronize_session=False)
                )
            else:
                count = 0
        else:
            count = query.filter(Notification.user_id == current_user.id).update(
                {"read_at": now}, synchronize_session=False
            )
    else:
        # Officer/Admin receives system/council-wide alerts as well as direct assignments
        notif_ids = [
            n.id
            for n in query.filter(
                (Notification.user_id == current_user.id)
                | (Notification.user_id.is_(None))
            ).all()
        ]
        if notif_ids:
            count = (
                db.query(Notification)
                .filter(Notification.id.in_(notif_ids))
                .update({"read_at": now}, synchronize_session=False)
            )
        else:
            count = 0

    db.commit()
    return {"status": "success", "marked_read": count}

