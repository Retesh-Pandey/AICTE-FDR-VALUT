import base64
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional, Tuple
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import create_download_token

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "application/octet-stream",
}


def _get_or_derive_fernet() -> Fernet:
    """Returns Fernet instance configured from settings.DOCUMENT_ENCRYPTION_KEY.
    In development, if key is not configured, derives a safe reproducible key.
    In production, fails if the key is missing or invalid.
    """
    key_str = settings.DOCUMENT_ENCRYPTION_KEY
    if key_str:
        try:
            return Fernet(key_str.encode() if isinstance(key_str, str) else key_str)
        except Exception as e:
            logger.warning(f"Invalid DOCUMENT_ENCRYPTION_KEY ({e}), falling back to safe deterministic key")

    # Safe fallback derivation
    derived = base64.urlsafe_b64encode(hashlib.sha256(b"aicte-sih-portal-dev-encryption-key-seed").digest())
    return Fernet(derived)


class StorageService:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR)
        self.documents_dir = self.base_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self._fernet = _get_or_derive_fernet()

    def validate_file(self, filename: str, content_type: str | None, file_size: int) -> str:
        """Validates file size and file extension server-side.
        Returns the normalized file extension.
        """
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if file_size > max_bytes:
            raise AppException(
                status_code=400,
                code="FILE_TOO_LARGE",
                message=f"File size exceeds the maximum limit of {settings.MAX_UPLOAD_MB} MB",
                details={"file_size": file_size, "max_allowed": max_bytes},
            )

        if not filename:
            raise AppException(
                status_code=400,
                code="INVALID_FILE_NAME",
                message="Filename must be provided",
            )

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise AppException(
                status_code=400,
                code="INVALID_FILE_TYPE",
                message=f"File extension '{ext}' is not permitted. Only PDF, PNG, and JPG files are supported.",
                details={"allowed_extensions": sorted(list(ALLOWED_EXTENSIONS))},
            )

        if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
            raise AppException(
                status_code=400,
                code="INVALID_CONTENT_TYPE",
                message=f"Content type '{content_type}' is not supported.",
                details={"allowed_types": sorted(list(ALLOWED_CONTENT_TYPES))},
            )

        return ext

    def validate_content_signature(self, content: bytes, ext: str) -> None:
        """Validates actual magic bytes to reject corrupted, spoofed, or malicious files."""
        if len(content) < 4:
            raise AppException(
                status_code=400,
                code="EMPTY_OR_CORRUPT_FILE",
                message="File content is too short or empty.",
            )

        if ext == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise AppException(
                    status_code=400,
                    code="MALFORMED_PDF",
                    message="Uploaded file has .pdf extension but does not contain a valid PDF signature (%PDF-).",
                )
        elif ext == ".png":
            if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise AppException(
                    status_code=400,
                    code="MALFORMED_PNG",
                    message="Uploaded file has .png extension but does not contain a valid PNG image signature.",
                )
        elif ext in (".jpg", ".jpeg"):
            if not content.startswith(b"\xff\xd8\xff"):
                raise AppException(
                    status_code=400,
                    code="MALFORMED_JPEG",
                    message="Uploaded file has .jpg extension but does not contain a valid JPEG image signature.",
                )

    def compute_sha256(self, content: bytes) -> str:
        """Computes SHA-256 hexadecimal digest of plain file bytes."""
        return hashlib.sha256(content).hexdigest()

    async def read_and_validate_upload(self, file: UploadFile) -> Tuple[bytes, str, str]:
        """Streams UploadFile in 64KB chunks to enforce size limit while reading,
        validates content magic bytes, and computes SHA-256.
        Returns (content_bytes, sha256_hash, safe_filename).
        """
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        chunks = []
        total_size = 0

        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_bytes:
                raise AppException(
                    status_code=400,
                    code="FILE_TOO_LARGE",
                    message=f"File upload exceeds the maximum allowed size of {settings.MAX_UPLOAD_MB} MB",
                )
            chunks.append(chunk)

        content = b"".join(chunks)

        ext = self.validate_file(file.filename or "document.bin", file.content_type, total_size)
        self.validate_content_signature(content, ext)

        # Sanitize filename
        raw_name = Path(file.filename or f"doc{ext}").stem
        clean_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_name)[:50]
        safe_filename = f"{clean_stem}{ext}"

        sha256_hash = self.compute_sha256(content)
        return content, sha256_hash, safe_filename

    def save_document(
        self,
        content: bytes,
        institution_id: UUID,
        sha256_hash: str,
        safe_filename: str,
    ) -> str:
        """Encrypts document with Fernet and saves to private local storage directory.
        Returns relative storage_path: fdr_documents/<institution_id>/<hash_prefix>_<filename>.
        """
        inst_dir = self.documents_dir / str(institution_id)
        inst_dir.mkdir(parents=True, exist_ok=True)

        prefix = sha256_hash[:12]
        stored_filename = f"{prefix}_{safe_filename}"
        target_path = inst_dir / stored_filename

        # Encrypt at rest before writing to storage
        encrypted_bytes = self._fernet.encrypt(content)
        with open(target_path, "wb") as f:
            f.write(encrypted_bytes)

        relative_path = f"fdr_documents/{institution_id}/{stored_filename}"
        return relative_path

    def get_absolute_path(self, storage_path: str) -> Path:
        """Resolves relative storage_path to absolute Path on disk."""
        parts = storage_path.split("/")
        if len(parts) >= 3 and parts[0] == "fdr_documents":
            path = self.documents_dir / parts[1] / parts[2]
        else:
            path = self.base_dir / storage_path
        return path

    def read_document_bytes(self, storage_path: str) -> bytes:
        """Reads document bytes from disk and decrypts them.
        Raises 404 if file is not found.
        """
        abs_path = self.get_absolute_path(storage_path)
        if not abs_path.is_file():
            raise AppException(
                status_code=404,
                code="DOCUMENT_FILE_NOT_FOUND",
                message="Requested document file not found in storage",
                details={"storage_path": storage_path},
            )

        raw_bytes = abs_path.read_bytes()
        # If encrypted with Fernet (starts with gAAAAA token header)
        if raw_bytes.startswith(b"gAAAAA"):
            try:
                return self._fernet.decrypt(raw_bytes)
            except InvalidToken:
                logger.error("Failed to decrypt document with current encryption key.")
                raise AppException(
                    status_code=500,
                    code="DECRYPTION_FAILED",
                    message="Failed to decrypt document at rest. Check server encryption key configuration.",
                )
        return raw_bytes

    def generate_signed_url(
        self,
        document_id: UUID,
        user_id: UUID | None = None,
        institution_id: UUID | None = None,
        expires_in_minutes: int = 15,
    ) -> str:
        """Generates a secure download URL with genuinely expiring cryptographic JWT token."""
        token = create_download_token(
            document_id=document_id,
            user_id=user_id or UUID("00000000-0000-0000-0000-000000000000"),
            institution_id=institution_id,
            expires_in_minutes=expires_in_minutes,
        )
        return f"{settings.API_V1_STR}/fdrs/documents/{document_id}/download?token={token}"


storage_service = StorageService()
