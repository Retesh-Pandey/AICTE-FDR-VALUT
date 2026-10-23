from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    PROJECT_NAME: str = "AICTE Smart FDR Lifecycle Management Portal"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # 'development' | 'testing' | 'production'

    DATABASE_URL: str = "sqlite:///./fdr_vault.db"

    # Authentication & Secrets
    JWT_SECRET: Optional[str] = None
    SUPABASE_URL: str = "https://demo.supabase.co"
    SUPABASE_ANON_KEY: str = "demo-anon-key"
    SUPABASE_SERVICE_KEY: str = "demo-service-key"
    SUPABASE_JWT_SECRET: str = "demo-super-secret-jwt-key-sih2026-vault"
    JWT_EXPIRY_HOURS: int = 12

    # Storage & Encryption at Rest
    STORAGE_BUCKET: str = "fdr-documents"
    UPLOAD_DIR: str = "uploads"
    DOCUMENT_ENCRYPTION_KEY: Optional[str] = None  # Base64-encoded 32-byte key for Fernet

    # Security Policies
    ENABLE_DEMO_LOGIN: bool = True  # Disabled automatically in production
    ENABLE_SIMULATED_DATE: bool = True  # Disabled automatically in production
    ALLOWED_ORIGINS: str | list[str] = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    MAX_UPLOAD_MB: int = 10

    # Verification, OCR & Automation
    VERIFIER_MODE: str = "mock"  # 'mock' | 'simulated' | 'real'
    REMINDER_DAYS: str = "30,15,7"
    MATURITY_CHECK_INTERVAL_HOURS: int = 24
    MAX_OCR_PAGES: int = 10
    TESSERACT_CMD: Optional[str] = None

    # Unrelated Submission Escalation Policy
    UNRELATED_STRIKE_THRESHOLD: int = 7  # 7 confirmed unrelated submissions trigger review hold
    UNRELATED_WINDOW_DAYS: int = 30      # Rolling 30-day window
    REVIEW_HOLD_DAYS: int = 14           # Temporary upload review hold duration (days)

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    @field_validator("TESSERACT_CMD", mode="before")
    @classmethod
    def resolve_tesseract_cmd(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v
        import os, shutil
        which_path = shutil.which("tesseract")
        if which_path:
            return which_path
        if os.name == "nt":
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
                r"C:\Users\retes\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for c in candidates:
                if os.path.isfile(c):
                    return c
        return None

    @property
    def effective_jwt_secret(self) -> str:
        return self.JWT_SECRET or self.SUPABASE_JWT_SECRET

    @property
    def reminder_days_list(self) -> list[int]:
        try:
            return [int(d.strip()) for d in self.REMINDER_DAYS.split(",") if d.strip()]
        except Exception:
            return [30, 15, 7]

    def validate_production_readiness(self) -> None:
        """Fail fast at startup if production environment has insecure configurations."""
        if self.ENVIRONMENT.lower() == "production":
            errors = []
            if self.ENABLE_DEMO_LOGIN:
                errors.append("ENABLE_DEMO_LOGIN must be False in production.")
            if self.ENABLE_SIMULATED_DATE:
                errors.append("ENABLE_SIMULATED_DATE must be False in production.")
            if self.effective_jwt_secret in ("demo-super-secret-jwt-key-sih2026-vault", "demo-jwt-secret", "") or len(self.effective_jwt_secret) < 32:
                errors.append("A strong, non-default JWT_SECRET of at least 32 characters is required in production.")
            if not self.DOCUMENT_ENCRYPTION_KEY:
                errors.append("DOCUMENT_ENCRYPTION_KEY must be configured for document encryption at rest in production.")
            if isinstance(self.ALLOWED_ORIGINS, list) and "*" in self.ALLOWED_ORIGINS:
                errors.append("Wildcard '*' in ALLOWED_ORIGINS is prohibited in production.")
            if errors:
                raise ValueError("Production security configuration check failed:\n- " + "\n- ".join(errors))


settings = Settings()
settings.validate_production_readiness()
