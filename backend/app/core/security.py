import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from jose import JWTError, jwt

from app.core.config import settings
from app.core.logging import logger

ALGORITHM = "HS256"
PBKDF2_ITERATIONS = 100000


def get_password_hash(password: str) -> str:
    """Generate a secure PBKDF2-HMAC-SHA256 password hash with unique random salt."""
    salt = secrets.token_hex(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${hash_bytes.hex()}"


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verify a plain password against the stored PBKDF2 hash using constant-time comparison."""
    if not hashed_password or not plain_password:
        return False

    parts = hashed_password.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False

    try:
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]
        computed_bytes = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(computed_bytes.hex(), expected_hash)
    except Exception as e:
        logger.warning(f"Password verification encountered error: {e}")
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token with enforced expiration."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=settings.JWT_EXPIRY_HOURS)

    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": expire,
    })
    encoded_jwt = jwt.encode(to_encode, settings.effective_jwt_secret, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.effective_jwt_secret,
            algorithms=[ALGORITHM],
            options={"verify_aud": False, "verify_exp": True},
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


def create_download_token(document_id: UUID, user_id: UUID, institution_id: Optional[UUID], expires_in_minutes: int = 5) -> str:
    """Create a short-lived cryptographically signed token for document download links."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=expires_in_minutes)
    claims = {
        "sub": str(user_id),
        "doc_id": str(document_id),
        "inst_id": str(institution_id) if institution_id else None,
        "type": "doc_download",
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    return jwt.encode(claims, settings.effective_jwt_secret, algorithm=ALGORITHM)


def verify_download_token(token: str) -> dict[str, Any] | None:
    """Verify download token signature, expiration, and token type."""
    try:
        payload = jwt.decode(
            token,
            settings.effective_jwt_secret,
            algorithms=[ALGORITHM],
            options={"verify_aud": False, "verify_exp": True},
        )
        if payload.get("type") != "doc_download":
            return None
        return payload
    except JWTError as e:
        logger.warning(f"Download token validation failed: {e}")
        return None
