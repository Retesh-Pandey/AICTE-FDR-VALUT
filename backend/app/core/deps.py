import uuid
from collections.abc import Generator
from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.logging import logger
from app.core.security import decode_token
from app.db.models import User, UserRole
from app.db.session import SessionLocal

security = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise UnauthorizedException(
            message="Missing authentication bearer token in Authorization header",
            code="NOT_AUTHENTICATED"
        )

    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise UnauthorizedException(
            message="Authentication token is invalid or expired",
            code="INVALID_TOKEN"
        )

    # Supabase JWT sets user id in 'sub'
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException(
            message="Authentication token missing subject claim",
            code="INVALID_TOKEN_CLAIMS"
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        user = db.query(User).filter(User.email == user_id_str).first()
        if user:
            return user
        raise UnauthorizedException(
            message=f"User with identifier {user_id_str} not found in database",
            code="USER_NOT_FOUND"
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        email = payload.get("email")
        if email:
            user = db.query(User).filter(User.email == email).first()

    if not user:
        raise UnauthorizedException(
            message="User record matching authenticated token not found",
            code="USER_NOT_FOUND"
        )

    if not getattr(user, "is_active", True):
        raise UnauthorizedException(
            message="User account is deactivated. Contact AICTE administrator.",
            code="ACCOUNT_INACTIVE"
        )

    return user


def require_role(*allowed_roles: UserRole):
    """Enforce role permissions strictly on the backend."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        role_values = [r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles]
        user_role_val = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)

        if user_role_val not in role_values:
            logger.warning(
                f"Unauthorized role access attempt: user={current_user.email}, role={user_role_val}, required={role_values}"
            )
            raise ForbiddenException(
                message=f"Access denied: current role '{user_role_val}' is unauthorized. Required: {role_values}",
                code="FORBIDDEN_ROLE"
            )
        return current_user
    return role_checker


def verify_institution_access(institution_id: Optional[uuid.UUID], current_user: User):
    """Enforce institutional multi-tenant scoping.
    Administrators have global council-wide access to all institutions.
    Authorized officials with assigned institution_id access only their assigned institution;
    officials without assigned institution_id have council-wide vigilance access.
    Institution users may access only records belonging to their own assigned institution.
    """
    user_role_val = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
    if user_role_val == "admin":
        return

    if user_role_val == "officer":
        if current_user.institution_id is not None:
            if not institution_id or current_user.institution_id != institution_id:
                logger.warning(
                    f"Officer scope violation: officer {current_user.email} (assigned {current_user.institution_id}) attempted access to institution {institution_id}"
                )
                raise ForbiddenException(
                    message="Access denied: Your official assignment does not permit viewing records outside your assigned institution.",
                    code="OFFICER_SCOPE_EXCEEDED"
                )
        return

    # Institution role
    if not current_user.institution_id:
        logger.warning(f"Unassigned institution user blocked: {current_user.email}")
        raise ForbiddenException(
            message="Access denied: Your user account is not associated with any registered institution.",
            code="NO_INSTITUTION_AFFILIATION"
        )

    if not institution_id or current_user.institution_id != institution_id:
        logger.warning(
            f"Cross-tenant access blocked: user {current_user.email} (inst: {current_user.institution_id}) attempted access to {institution_id}"
        )
        raise ForbiddenException(
            message="Cross-tenant access denied: institutions may inspect and submit only their own records.",
            code="CROSS_TENANT_FORBIDDEN"
        )

