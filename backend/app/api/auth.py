from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_role
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.models import InstitutionRegistrationRequest, RegistrationRequestStatus, User, UserRole
from app.schemas.user import ChangePasswordRequest, LoginRequest, MeResponse, PasswordLoginRequest, TokenResponse
from app.services.audit import write_audit_log

router = APIRouter(prefix="", tags=["Auth"])


@router.get("/me", response_model=MeResponse)
def read_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return currently authenticated user, role, and institution details."""
    return current_user


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login_with_password(
    request: Request,
    req: PasswordLoginRequest,
    db: Session = Depends(get_db)
):
    """Secure password-based authentication endpoint.
    Validates user credentials against hashed PBKDF2 password in database.
    Does not trust client-supplied roles; roles are loaded exclusively from database.
    Isolates pending registration applicants from accessing any portal data.
    """
    clean_email = req.email.lower().strip()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        # Check if there is an unapproved institution registration request
        pending_req = db.query(InstitutionRegistrationRequest).filter(
            InstitutionRegistrationRequest.official_email == clean_email,
            InstitutionRegistrationRequest.status == RegistrationRequestStatus.pending_verification,
        ).first()
        if pending_req:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "INSTITUTION_REGISTRATION_PENDING",
                        "message": (
                            f"Registration request for '{pending_req.institution_name}' (Tracking Ref: REG-{pending_req.id.hex[:8].upper()}) "
                            "is pending verification by an authorized AICTE Vigilance Officer. Portal access is restricted until approved."
                        )
                    }
                }
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}}
        )

    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "ACCOUNT_DEACTIVATED", "message": "User account has been deactivated."}}
        )

    if not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}}
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
        }
    )

    logger.info(f"User {user.email} authenticated successfully via password")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.post("/auth/demo-login", response_model=TokenResponse)
@limiter.limit("15/minute")
def demo_login(
    request: Request,
    req: LoginRequest,
    db: Session = Depends(get_db)
):
    """Development-only demo login endpoint.
    Strictly disabled in production and cannot be enabled when ENVIRONMENT=production.
    """
    if settings.ENVIRONMENT.lower() == "production" or not settings.ENABLE_DEMO_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "DEMO_LOGIN_DISABLED", "message": "Demo login is disabled in this environment. Please authenticate using /auth/login with valid credentials."}}
        )

    clean_email = req.email.lower().strip()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        pending_req = db.query(InstitutionRegistrationRequest).filter(
            InstitutionRegistrationRequest.official_email == clean_email,
            InstitutionRegistrationRequest.status == RegistrationRequestStatus.pending_verification,
        ).first()
        if pending_req:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "INSTITUTION_REGISTRATION_PENDING",
                        "message": (
                            f"Registration request for '{pending_req.institution_name}' (Tracking Ref: REG-{pending_req.id.hex[:8].upper()}) "
                            "is pending verification by an authorized AICTE Vigilance Officer. Portal access is restricted until approved."
                        )
                    }
                }
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": f"Demo user with email {req.email} not found. Please run seed script."}}
        )

    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "ACCOUNT_DEACTIVATED", "message": "User account has been deactivated."}}
        )

    # Generate token with sub = user.id
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
        }
    )

    logger.info(f"Demo login successful for {user.email} [{user.role}]")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.post("/auth/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Authenticated endpoint to securely change user password with validation."""
    if current_user.hashed_password and not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CURRENT_PASSWORD", "message": "Current password does not match."}}
        )

    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "WEAK_PASSWORD", "message": "New password must be at least 8 characters long."}}
        )

    current_user.hashed_password = get_password_hash(req.new_password)

    write_audit_log(
        db=db,
        action="user.password_changed",
        entity="user",
        entity_id=current_user.id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        old_status=None,
        new_status=None,
        remarks=f"Password updated by user {current_user.email}",
        payload={"email": current_user.email}
    )

    db.commit()
    return {"status": "success", "message": "Password changed successfully."}


@router.get("/auth/officer-only", tags=["Auth"])
def officer_only_action(
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin))
):
    """Protected endpoint requiring Officer or Admin role."""
    return {
        "status": "success",
        "message": f"Welcome Officer {current_user.full_name or current_user.email}",
        "role": current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
    }


@router.get("/auth/admin-only", tags=["Auth"])
def admin_only_action(
    current_user: User = Depends(require_role(UserRole.admin))
):
    """Protected endpoint requiring Admin role."""
    return {
        "status": "success",
        "message": f"Welcome Sovereign Administrator {current_user.full_name or current_user.email}",
        "role": current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
    }
