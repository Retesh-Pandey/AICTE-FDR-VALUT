from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import app.db.models  # Ensure all models are registered
from app.api import (
    admin,
    audit,
    auth,
    dashboard,
    fdrs,
    institutions,
    notifications,
    release,
    renewals,
    reports,
)
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.limiter import limiter
from app.core.logging import logger, setup_logging
from app.db.migrate import run_safe_migrations
from app.db.session import Base, engine
from app.services.jobs.scheduler import shutdown_scheduler, start_scheduler

setup_logging()

# Auto-create tables & safe schema migration on startup (preserves existing data safely)
try:
    run_safe_migrations(engine)
    logger.info("Database schema verified/created successfully.")
except Exception as e:
    logger.error(f"Error initializing database schema: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background scheduler for maturity monitoring
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"Could not start background scheduler: {e}")

    # Startup Diagnostic: Log OCR engine availability and Bank Verifier mode
    try:
        from app.services.ocr import ocr_extractor
        ocr_ok, ocr_msg = ocr_extractor.check_ocr_engine_available()
        logger.info(f"OCR Subsystem Diagnostic: engine_available={ocr_ok} ({ocr_msg})")
        logger.info(f"Bank Verifier Subsystem: VERIFIER_MODE='{settings.VERIFIER_MODE}' (SIMULATED BANK RECORDS)")
    except Exception as e:
        logger.warning(f"Subsystem startup diagnostic error: {e}")

    yield
    # Shutdown: Stop scheduler gracefully
    try:
        shutdown_scheduler()
    except Exception as e:
        logger.warning(f"Could not cleanly shutdown background scheduler: {e}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sovereign AICTE FDR Lifecycle Management Portal — SIH26265 Protocol",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate Limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Standardized Error Handling
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "details": None,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request parameter validation failed",
                "details": exc.errors(),
            }
        },
    )


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for container probes and uptime monitors."""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "connected",
        "verifier_mode": settings.VERIFIER_MODE,
        "protocol": "AICTE-SIH26265-SOVEREIGN"
    }


@app.get("/health/ocr", tags=["Health"])
def ocr_health_diagnostic():
    """
    Diagnostic endpoint reporting status of OCR libraries, Tesseract binary,
    language data, and unrelated submission escalation policy.
    Does not expose sensitive system paths or file contents.
    """
    from app.services.ocr import ocr_extractor
    diag = ocr_extractor.get_engine_diagnostic()

    libraries = {}
    for mod_name, label in [("pymupdf", "pymupdf"), ("pypdf", "pypdf"), ("pytesseract", "pytesseract"), ("PIL", "pillow")]:
        try:
            __import__(mod_name)
            libraries[label] = True
        except ImportError:
            libraries[label] = False

    return {
        "status": "operational" if diag["available"] else "degraded",
        "ocr_engine_available": diag["available"],
        "engine_status": diag["status"],  # 'available' | 'engine_missing' | 'language_data_missing'
        "status_detail": diag["reason"],
        "tesseract_version": diag["version"],
        "languages_available": diag["languages"],
        "python_libraries": libraries,
        "max_pages": settings.MAX_OCR_PAGES,
        "verifier_mode": settings.VERIFIER_MODE,
        "policy": {
            "unrelated_strike_threshold": settings.UNRELATED_STRIKE_THRESHOLD,
            "unrelated_window_days": settings.UNRELATED_WINDOW_DAYS,
            "review_hold_days": settings.REVIEW_HOLD_DAYS,
        },
        "disclaimer": "Assistive OCR data-entry only. Scanned documents undergo human review."
    }


# Include Routers (Direct root mount & /api/v1 versioned mount)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(institutions.router)
app.include_router(fdrs.router)
app.include_router(release.router)
app.include_router(renewals.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(audit.router)

api_v1 = APIRouter(prefix=settings.API_V1_STR)
api_v1.add_api_route("/health", health_check, methods=["GET"], tags=["Health"])
api_v1.add_api_route("/health/ocr", ocr_health_diagnostic, methods=["GET"], tags=["Health"])
api_v1.include_router(auth.router)
api_v1.include_router(dashboard.router)
api_v1.include_router(institutions.router)
api_v1.include_router(fdrs.router)
api_v1.include_router(release.router)
api_v1.include_router(renewals.router)
api_v1.include_router(notifications.router)
api_v1.include_router(reports.router)
api_v1.include_router(admin.router)
api_v1.include_router(audit.router)
app.include_router(api_v1)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "AICTE Smart FDR Lifecycle Management API is operating.",
        "docs": "/docs",
        "health": "/health"
    }
