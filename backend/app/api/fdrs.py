import json
import mimetypes
from datetime import date
from decimal import Decimal
from math import ceil
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import (
    get_current_user,
    get_db,
    require_role,
    security,
    verify_institution_access,
)
from app.core.exceptions import AppException, ConflictException, NotFoundException
from app.core.limiter import limiter
from app.core.security import verify_download_token
from app.db.models import (
    DocumentSubmissionReview,
    FDRDocument,
    FDRRecord,
    Institution,
    InstrumentStatus,
    User,
    UserRole,
    VerificationLog,
    VerificationStatus,
    WorkflowStatus,
)
from app.schemas.document import FDRDocumentResponse
from app.schemas.fdr import (
    DiscrepancyResolutionRequest,
    DocumentSubmissionAdjudicationRequest,
    DocumentSubmissionReviewResponse,
    FDRDetailResponse,
    FDRListResponse,
    FDRResponse,
    FDRSubmissionResponse,
    OCRResponse,
)
from app.schemas.verification import SimulatedVerificationResponse
from app.services.audit import write_audit_log
from app.services.escalation import (
    adjudicate_document_submission,
    check_and_update_institution_hold,
    record_submission_for_review,
)
from app.services.verifier import get_bank_verifier
from app.services.ocr import ocr_extractor
from app.services.storage import storage_service
from app.services.validation import validation_engine

router = APIRouter(prefix="/fdrs", tags=["FDR Records & Submissions"])


@router.post("/ocr", response_model=OCRResponse)
@limiter.limit("20/minute")
async def extract_fdr_ocr(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Assistive OCR extraction endpoint.
    Extracts available fields with confidence metrics without creating a database record.
    Enforces server-side file type and size restrictions.
    """
    content, _, safe_filename = await storage_service.read_and_validate_upload(file)
    extracted = ocr_extractor.extract_fields(content, safe_filename)
    return OCRResponse(**extracted)


@router.post("", response_model=FDRSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_fdr(
    fdr_number: str = Form(...),
    bank_name: str = Form(...),
    amount: Decimal = Form(...),
    issue_date: date = Form(...),
    maturity_date: date = Form(...),
    branch: Optional[str] = Form(None),
    lien_info: Optional[str] = Form(None),
    institution_id: Optional[UUID] = Form(None),
    previous_fdr_id: Optional[UUID] = Form(None),
    extracted_json: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a new institutional Fixed Deposit Receipt with private document upload.
    Enforces multi-tenant institutional scoping, file validation, duplicate detection,
    validation rules engine evaluation, and atomic transaction audit logging.
    """
    # 1. Resolve and verify target institution
    if current_user.role == UserRole.institution:
        if not current_user.institution_id:
            raise AppException(
                status_code=400,
                code="NO_INSTITUTION_AFFILIATION",
                message="Your user account is not associated with any registered institution.",
            )
        target_inst_id = current_user.institution_id
        if institution_id and institution_id != current_user.institution_id:
            raise AppException(
                status_code=403,
                code="CROSS_TENANT_FORBIDDEN",
                message="Institution accounts may only submit FDR records for their own institution.",
            )
    else:
        # Officer or Admin must provide or target an institution
        if not institution_id:
            raise AppException(
                status_code=400,
                code="INSTITUTION_ID_REQUIRED",
                message="Institution ID is required when submitting as an Officer or Admin.",
            )
        target_inst_id = institution_id

    # Verify institution existence
    inst = db.query(Institution).filter(Institution.id == target_inst_id).first()
    if not inst:
        raise NotFoundException(
            message=f"Target institution '{target_inst_id}' not found.",
            code="INSTITUTION_NOT_FOUND",
        )

    # 1b. Check temporary upload review hold
    if check_and_update_institution_hold(db, inst):
        until_str = inst.upload_hold_until.strftime("%d-%b-%Y %H:%M UTC") if inst.upload_hold_until else "administrative review"
        hold_msg = (
            f"FDR document uploads for {inst.name} are currently on temporary administrative review hold until {until_str}. "
            f"Reason: {inst.upload_hold_reason or 'Repeated confirmed unrelated submissions'}. "
            "Existing FDR records remain accessible in read-only mode. You may submit an appeal via the portal."
        )
        raise AppException(
            status_code=403,
            code="INSTITUTION_UPLOAD_HOLD",
            message=hold_msg,
            details={
                "upload_hold_active": True,
                "upload_hold_until": inst.upload_hold_until.isoformat() if inst.upload_hold_until else None,
                "upload_hold_reason": inst.upload_hold_reason,
                "upload_hold_appealed_at": inst.upload_hold_appealed_at.isoformat() if inst.upload_hold_appealed_at else None,
            },
        )

    # 2. Field sanity checks
    if amount <= Decimal("0"):
        raise AppException(
            status_code=400,
            code="INVALID_AMOUNT",
            message="FDR principal amount must be strictly greater than zero.",
        )

    if maturity_date <= issue_date:
        raise AppException(
            status_code=400,
            code="INVALID_DATE_SEQUENCE",
            message="Maturity date must be strictly after the issue date.",
        )

    # 3. Check duplicate (bank_name, fdr_number) in database
    existing_fdr = (
        db.query(FDRRecord)
        .filter(
            FDRRecord.bank_name.ilike(bank_name.strip()),
            FDRRecord.fdr_number == fdr_number.strip(),
        )
        .first()
    )
    if existing_fdr:
        raise ConflictException(
            message=f"An instrument with FDR number '{fdr_number}' from '{bank_name}' is already registered in the vault.",
            code="FDR_DUPLICATE_NUMBER",
            details={"existing_id": str(existing_fdr.id), "institution_id": str(existing_fdr.institution_id)},
        )

    # 4. Read, validate, and hash document upload
    content, sha256_hash, safe_filename = await storage_service.read_and_validate_upload(file)

    # 5. Parse assistive OCR payload if passed, or extract on the fly
    parsed_extracted = None
    if extracted_json:
        try:
            parsed_extracted = json.loads(extracted_json)
        except Exception:
            parsed_extracted = None

    if not parsed_extracted or not isinstance(parsed_extracted, dict):
        extracted = ocr_extractor.extract_fields(content, safe_filename)
        parsed_extracted = extracted
    elif "classification" not in parsed_extracted:
        extracted = ocr_extractor.extract_fields(content, safe_filename)
        parsed_extracted["classification"] = extracted.get("classification", {})


    # Enforce Unrelated Document submission blockage
    classification_data = parsed_extracted.get("classification") or {}
    doc_class = classification_data.get("status")

    if doc_class == "likely_unrelated":
        # Check if an authorized Officer/Admin has reviewed and overridden this document
        override = (
            db.query(DocumentSubmissionReview)
            .filter(
                DocumentSubmissionReview.institution_id == target_inst_id,
                DocumentSubmissionReview.document_sha256 == sha256_hash,
                DocumentSubmissionReview.review_status == "overridden_as_fdr",
            )
            .first()
        )

        if not override and current_user.role == UserRole.institution:
            # Stage in review queue so officers can see and adjudicate it
            record_submission_for_review(
                db=db,
                institution_id=target_inst_id,
                filename=safe_filename,
                sha256_hash=sha256_hash,
                classification_dict=classification_data,
                storage_path=None,
                fdr_id=None,
            )
            db.commit()

            summary = classification_data.get("content_summary") or "The document does not match Fixed Deposit Receipt terminology or structure."
            raise AppException(
                status_code=400,
                code="DOCUMENT_CLASSIFIED_UNRELATED",
                message=(
                    f"This does not appear to be an FDR receipt. {summary} "
                    "Submission of this file is blocked until you upload a valid Fixed Deposit Receipt "
                    "or an authorized AICTE Officer reviews and overrides the classification."
                ),
                details={
                    "classification": classification_data,
                    "sha256": sha256_hash,
                    "detected_type": classification_data.get("detected_document_type"),
                    "reasons": classification_data.get("classification_reasons"),
                },
            )


    # 6. Evaluate validation rules engine
    validation_flags = validation_engine.validate_fdr(
        db=db,
        institution_id=target_inst_id,
        fdr_number=fdr_number.strip(),
        bank_name=bank_name.strip(),
        amount=amount,
        issue_date=issue_date,
        maturity_date=maturity_date,
        document_sha256=sha256_hash,
        extracted_json=parsed_extracted,
    )

    # Check for blocking critical flags
    critical_flags = [f for f in validation_flags if f.get("severity") == "critical"]
    if critical_flags:
        raise AppException(
            status_code=400,
            code="VALIDATION_CRITICAL_ERROR",
            message=critical_flags[0]["message"],
            details={"critical_flags": critical_flags},
        )

    # 7. Save document to private storage
    storage_path = storage_service.save_document(
        content=content,
        institution_id=target_inst_id,
        sha256_hash=sha256_hash,
        safe_filename=safe_filename,
    )

    # 8. Create database records inside transaction
    new_fdr = FDRRecord(
        institution_id=target_inst_id,
        fdr_number=fdr_number.strip(),
        bank_name=bank_name.strip(),
        branch=branch.strip() if branch else None,
        amount=amount,
        issue_date=issue_date,
        maturity_date=maturity_date,
        lien_info=lien_info.strip() if lien_info else None,
        previous_fdr_id=previous_fdr_id,
        is_current=True,
        instrument_status=InstrumentStatus.submitted,
        verification_status=VerificationStatus.pending,
        workflow_status=WorkflowStatus.none,
        submitted_by=current_user.id,
    )
    db.add(new_fdr)
    db.flush()

    new_doc = FDRDocument(
        fdr_id=new_fdr.id,
        storage_path=storage_path,
        doc_type="fdr_receipt",
        sha256=sha256_hash,
        ocr_raw_text=parsed_extracted.get("raw_text") if isinstance(parsed_extracted, dict) else None,
        extracted_json=parsed_extracted,
        uploaded_by=current_user.id,
    )
    db.add(new_doc)
    db.flush()

    # 9. Append transactional SHA-256 hash-chained audit record
    write_audit_log(
        db=db,
        action="fdr.created",
        entity="fdr",
        entity_id=new_fdr.id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role),
        old_status=None,
        new_status="submitted",
        remarks=f"Initial FDR deposit registration for {inst.name} ({fdr_number} at {bank_name})",
        payload={
            "fdr_number": new_fdr.fdr_number,
            "bank_name": new_fdr.bank_name,
            "amount": str(new_fdr.amount),
            "document_sha256": sha256_hash,
            "validation_warnings_count": len([f for f in validation_flags if f.get("severity") == "warning"]),
        },
    )

    db.commit()
    db.refresh(new_fdr)
    db.refresh(new_doc)

    # Generate secure signed download URL
    doc_response = new_doc
    setattr(doc_response, "signed_url", storage_service.generate_signed_url(new_doc.id, user_id=current_user.id, institution_id=target_inst_id))

    return FDRSubmissionResponse(
        fdr=new_fdr,
        document=doc_response,
        validation_flags=validation_flags,
        message="FDR registered successfully with pending verification.",
    )


@router.get("", response_model=FDRListResponse)
def list_fdrs(
    status: Optional[InstrumentStatus] = None,
    verification_status: Optional[VerificationStatus] = None,
    institution_id: Optional[UUID] = None,
    bank: Optional[str] = None,
    q: Optional[str] = None,
    maturity_before: Optional[date] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List FDR records with pagination and multi-parameter filtering.
    Institutions are automatically scoped to their own records.
    """
    query = (
        db.query(FDRRecord)
        .join(Institution, FDRRecord.institution_id == Institution.id)
        .options(joinedload(FDRRecord.institution))
    )

    # Scoping enforcement
    if current_user.role == UserRole.institution:
        if not current_user.institution_id:
            raise AppException(
                status_code=403,
                code="NO_INSTITUTION_AFFILIATION",
                message="Your account is not associated with any registered institution.",
            )
        if institution_id and institution_id != current_user.institution_id:
            raise AppException(
                status_code=403,
                code="CROSS_TENANT_FORBIDDEN",
                message="Institution accounts may only access their own records.",
            )
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    elif current_user.role == UserRole.officer and current_user.institution_id is not None:
        if institution_id and institution_id != current_user.institution_id:
            raise AppException(
                status_code=403,
                code="OFFICER_SCOPE_EXCEEDED",
                message="Official role is scoped to assigned institution.",
            )
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    elif institution_id:
        query = query.filter(FDRRecord.institution_id == institution_id)

    # Filters
    if status:
        query = query.filter(FDRRecord.instrument_status == status)
    if verification_status:
        query = query.filter(FDRRecord.verification_status == verification_status)
    if bank:
        query = query.filter(FDRRecord.bank_name.ilike(f"%{bank.strip()}%"))
    if maturity_before:
        query = query.filter(FDRRecord.maturity_date <= maturity_before)
    if q:
        search_pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                FDRRecord.fdr_number.ilike(search_pattern),
                Institution.name.ilike(search_pattern),
                FDRRecord.bank_name.ilike(search_pattern),
            )
        )

    total = query.count()
    pages = ceil(total / limit) if total > 0 else 1
    offset = (page - 1) * limit

    items = query.order_by(FDRRecord.created_at.desc()).offset(offset).limit(limit).all()

    return FDRListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/{id}", response_model=FDRDetailResponse)
def get_fdr_detail(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetch comprehensive FDR details including documents with signed download URLs,
    verification logs, and release history.
    """
    fdr = (
        db.query(FDRRecord)
        .options(
            joinedload(FDRRecord.institution),
            joinedload(FDRRecord.documents),
            joinedload(FDRRecord.verification_logs),
            joinedload(FDRRecord.release_requests),
        )
        .filter(FDRRecord.id == id)
        .first()
    )
    if not fdr:
        raise NotFoundException(message=f"FDR record with id '{id}' not found.", code="FDR_NOT_FOUND")

    # Institutional multi-tenant verification
    verify_institution_access(fdr.institution_id, current_user)

    # Attach signed URLs to each document
    for doc in fdr.documents:
        setattr(doc, "signed_url", storage_service.generate_signed_url(doc.id, user_id=current_user.id, institution_id=fdr.institution_id))

    return fdr


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: UUID,
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Authorized document download endpoint. Verifies either a valid expiring
    signed token OR authenticated user credentials with tenant permissions
    before streaming decrypted private storage bytes.
    """
    doc = db.query(FDRDocument).join(FDRRecord).filter(FDRDocument.id == document_id).first()
    if not doc:
        raise NotFoundException(message="Document record not found.", code="DOCUMENT_NOT_FOUND")

    if token:
        payload = verify_download_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "EXPIRED_OR_INVALID_DOWNLOAD_TOKEN", "message": "Download link is expired or invalid."}}
            )
        if payload.get("doc_id") != str(document_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "TOKEN_MISMATCH", "message": "Download token is not valid for this document."}}
            )
        token_inst_id = payload.get("inst_id")
        if doc.fdr and token_inst_id != str(doc.fdr.institution_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "CROSS_TENANT_DOWNLOAD", "message": "Download token does not match institution tenant."}}
            )
    else:
        current_user = get_current_user(credentials=credentials, db=db)
        if doc.fdr:
            verify_institution_access(doc.fdr.institution_id, current_user)

    file_bytes = storage_service.read_document_bytes(doc.storage_path)
    filename = Path(doc.storage_path).name
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )

@router.post("/{id}/verify", response_model=SimulatedVerificationResponse)
def verify_fdr_with_bank(
    id: UUID,
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Execute simulated bank verification against synthetic core-banking mock records.
    Restricted to Vigilance Officers and Admins.
    Guaranteed synthetic data only: returns explicit 'SIMULATED — NOT BANK CONFIRMATION'
    disclaimer, records verification log and SHA-256 hash-chained audit record.
    """
    fdr = db.query(FDRRecord).filter(FDRRecord.id == id).first()
    if not fdr:
        raise NotFoundException(message=f"FDR record with id '{id}' not found.", code="FDR_NOT_FOUND")

    verifier = get_bank_verifier()
    result = verifier.verify_fdr(fdr=fdr, db=db, actor=current_user)
    return result


@router.post("/{id}/resolve-discrepancy", response_model=FDRResponse)
def resolve_discrepancy(
    id: UUID,
    data: DiscrepancyResolutionRequest,
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Authoritative resolution of flagged FDR discrepancies.
    Requires Officer or Admin role with mandatory resolution note and audit trail.
    """
    fdr = db.query(FDRRecord).filter(FDRRecord.id == id).first()
    if not fdr:
        raise NotFoundException(message=f"FDR record with id '{id}' not found.", code="FDR_NOT_FOUND")

    old_status = fdr.verification_status.value
    new_status = data.outcome

    if not data.resolution_note or len(data.resolution_note.strip()) < 5:
        raise AppException(
            status_code=400,
            code="RESOLUTION_NOTE_REQUIRED",
            message="A detailed resolution note explaining the decision is required.",
        )

    fdr.verification_status = new_status

    # Record verification log
    vlog = VerificationLog(
        fdr_id=fdr.id,
        source="MANUAL_RESOLUTION",
        submitted_values={"fdr_number": fdr.fdr_number, "amount": str(fdr.amount), "bank": fdr.bank_name},
        confirmed_values={"fdr_number": fdr.fdr_number, "amount": str(fdr.amount), "bank": fdr.bank_name},
        discrepancies=[],
        outcome=new_status,
        resolved_by=current_user.id,
        resolution_note=data.resolution_note.strip(),
    )
    db.add(vlog)

    # Audit log
    write_audit_log(
        db=db,
        action="fdr.discrepancy_resolved",
        entity="fdr",
        entity_id=fdr.id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role),
        old_status=old_status,
        new_status=new_status.value,
        remarks=f"Discrepancy resolved: {data.resolution_note.strip()}",
        payload={"outcome": new_status.value, "note": data.resolution_note.strip()},
    )

    db.commit()
    db.refresh(fdr)
    return fdr


@router.post("/{id}/renew", response_model=FDRSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def renew_fdr(
    id: UUID,
    fdr_number: str = Form(...),
    bank_name: str = Form(...),
    amount: Decimal = Form(...),
    issue_date: date = Form(...),
    maturity_date: date = Form(...),
    branch: Optional[str] = Form(None),
    lien_info: Optional[str] = Form(None),
    extracted_json: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a renewal instrument linked to an existing FDR record.

    Validates previous FDR status, ensures no conflicting release workflow,
    creates the renewal FDR with workflow_status='renewal_review',
    and logs an audit trail in the same transaction.
    """
    old_fdr = db.query(FDRRecord).filter(FDRRecord.id == id).first()
    if not old_fdr:
        raise NotFoundException(message=f"Previous FDR record with id '{id}' not found.", code="FDR_NOT_FOUND")

    # Multi-tenant scoping check
    verify_institution_access(old_fdr.institution_id, current_user)

    if not old_fdr.is_current:
        raise AppException(
            status_code=400,
            code="NOT_CURRENT_FDR",
            message="Cannot renew an FDR that is already superseded or non-current.",
        )

    if old_fdr.workflow_status in (
        WorkflowStatus.release_requested,
        WorkflowStatus.under_review,
        WorkflowStatus.conditions_checked,
        WorkflowStatus.approval_pending,
    ):
        raise AppException(
            status_code=409,
            code="RELEASE_WORKFLOW_ACTIVE",
            message="Cannot submit a renewal while an FDR release request is actively in progress.",
        )

    # Check for already pending renewal
    pending_renewal = (
        db.query(FDRRecord)
        .filter(
            FDRRecord.previous_fdr_id == old_fdr.id,
            FDRRecord.workflow_status == WorkflowStatus.renewal_review,
        )
        .first()
    )
    if pending_renewal:
        raise AppException(
            status_code=409,
            code="PENDING_RENEWAL_EXISTS",
            message=f"A renewal instrument ({pending_renewal.fdr_number}) is already pending review for this FDR.",
        )

    if amount <= Decimal("0"):
        raise AppException(status_code=400, code="INVALID_AMOUNT", message="Principal amount must be positive.")

    if maturity_date <= issue_date:
        raise AppException(status_code=400, code="INVALID_DATE_SEQUENCE", message="Maturity date must follow issue date.")

    # Duplicate check across system
    existing_duplicate = (
        db.query(FDRRecord)
        .filter(
            FDRRecord.bank_name.ilike(bank_name.strip()),
            FDRRecord.fdr_number == fdr_number.strip(),
        )
        .first()
    )
    if existing_duplicate:
        raise ConflictException(
            message=f"FDR number '{fdr_number}' from '{bank_name}' is already registered in the vault.",
            code="FDR_DUPLICATE_NUMBER",
        )

    # Validate upload & storage
    content, sha256_hash, safe_filename = await storage_service.read_and_validate_upload(file)

    parsed_extracted = None
    if extracted_json:
        try:
            parsed_extracted = json.loads(extracted_json)
        except Exception:
            parsed_extracted = None

    storage_path = storage_service.save_document(
        content=content,
        institution_id=old_fdr.institution_id,
        sha256_hash=sha256_hash,
        safe_filename=safe_filename,
    )

    # Validation rules engine
    validation_flags = validation_engine.validate_fdr(
        db=db,
        institution_id=old_fdr.institution_id,
        fdr_number=fdr_number.strip(),
        bank_name=bank_name.strip(),
        amount=amount,
        issue_date=issue_date,
        maturity_date=maturity_date,
        document_sha256=sha256_hash,
        extracted_json=parsed_extracted,
    )

    # Create new renewal FDR
    new_fdr = FDRRecord(
        institution_id=old_fdr.institution_id,
        fdr_number=fdr_number.strip(),
        bank_name=bank_name.strip(),
        branch=branch.strip() if branch else None,
        amount=amount,
        issue_date=issue_date,
        maturity_date=maturity_date,
        lien_info=lien_info.strip() if lien_info else None,
        previous_fdr_id=old_fdr.id,
        is_current=True,
        instrument_status=InstrumentStatus.submitted,
        verification_status=VerificationStatus.pending,
        workflow_status=WorkflowStatus.renewal_review,
        submitted_by=current_user.id,
    )
    db.add(new_fdr)
    db.flush()

    new_doc = FDRDocument(
        fdr_id=new_fdr.id,
        storage_path=storage_path,
        doc_type="renewal",
        sha256=sha256_hash,
        ocr_raw_text=parsed_extracted.get("raw_text") if isinstance(parsed_extracted, dict) else None,
        extracted_json=parsed_extracted,
        uploaded_by=current_user.id,
    )
    db.add(new_doc)
    db.flush()

    # Audit renewal submission
    write_audit_log(
        db=db,
        action="fdr.renewal_submitted",
        entity="fdr",
        entity_id=new_fdr.id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role),
        old_status=None,
        new_status="submitted",
        remarks=f"Renewal instrument submitted for previous FDR {old_fdr.fdr_number}",
        payload={
            "previous_fdr_id": str(old_fdr.id),
            "previous_fdr_number": old_fdr.fdr_number,
            "new_fdr_number": new_fdr.fdr_number,
            "amount": str(new_fdr.amount),
        },
    )

    db.commit()
    db.refresh(new_fdr)
    db.refresh(new_doc)

    return FDRSubmissionResponse(
        fdr=FDRResponse.model_validate(new_fdr),
        document=FDRDocumentResponse.model_validate(new_doc),
        validation_flags=validation_flags,
        message="Renewal FDR registered and queued for officer review.",
    )


# -------------------------------------------------------------------------
# Document Review Queue & Escalation Endpoints
# -------------------------------------------------------------------------

@router.get("/review-queue", response_model=List[DocumentSubmissionReviewResponse])
def get_document_review_queue(
    status_filter: Optional[str] = Query("pending", alias="status"),
    institution_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List submissions in the Document Review Queue.
    Officers/Admins can see all items or filter by institution.
    Institutions are strictly scoped to their own items.
    """
    query = db.query(DocumentSubmissionReview).join(Institution, DocumentSubmissionReview.institution_id == Institution.id)

    if current_user.role == UserRole.institution:
        if not current_user.institution_id:
            raise AppException(status_code=403, code="NO_INSTITUTION_AFFILIATION", message="No registered institution affiliation.")
        if institution_id and institution_id != current_user.institution_id:
            raise AppException(status_code=403, code="CROSS_TENANT_FORBIDDEN", message="Access forbidden.")
        query = query.filter(DocumentSubmissionReview.institution_id == current_user.institution_id)
    elif current_user.role == UserRole.officer and current_user.institution_id is not None:
        if institution_id and institution_id != current_user.institution_id:
            raise AppException(status_code=403, code="OFFICER_SCOPE_EXCEEDED", message="Access forbidden outside assigned institution.")
        query = query.filter(DocumentSubmissionReview.institution_id == current_user.institution_id)
    elif institution_id:
        query = query.filter(DocumentSubmissionReview.institution_id == institution_id)

    if status_filter and status_filter.lower() != "all":
        query = query.filter(DocumentSubmissionReview.review_status == status_filter.lower())

    items = query.order_by(DocumentSubmissionReview.created_at.desc()).limit(100).all()

    responses = []
    for item in items:
        resp = DocumentSubmissionReviewResponse.model_validate(item)
        if item.institution:
            resp.institution_name = item.institution.name
            resp.institution_aicte_id = item.institution.aicte_id
        responses.append(resp)

    return responses


@router.get("/review-queue/{review_id}", response_model=DocumentSubmissionReviewResponse)
def get_document_review_item(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """View details of a document in the review queue."""
    item = db.query(DocumentSubmissionReview).filter(DocumentSubmissionReview.id == review_id).first()
    if not item:
        raise NotFoundException(message="Review item not found", code="REVIEW_ITEM_NOT_FOUND")

    if current_user.role == UserRole.institution and item.institution_id != current_user.institution_id:
        raise AppException(status_code=403, code="CROSS_TENANT_FORBIDDEN", message="Access forbidden.")

    resp = DocumentSubmissionReviewResponse.model_validate(item)
    if item.institution:
        resp.institution_name = item.institution.name
        resp.institution_aicte_id = item.institution.aicte_id
    return resp


@router.post("/review-queue/{review_id}/adjudicate", response_model=DocumentSubmissionReviewResponse)
def adjudicate_review_item(
    review_id: UUID,
    body: DocumentSubmissionAdjudicationRequest,
    current_user: User = Depends(require_role(UserRole.officer, UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Officer / Admin adjudication of a flagged document.
    Actions:
      - 'confirm_unrelated': Confirms file is an unrelated upload (requires reason).
         Deduplicated by hash. Checks 7-strike threshold for temporary upload hold.
      - 'override_as_fdr': Overrides classification to permit institution to submit as FDR.
      - 'dismiss': Dismisses review item without penalty.
    """
    # Check officer scoping
    item = db.query(DocumentSubmissionReview).filter(DocumentSubmissionReview.id == review_id).first()
    if not item:
        raise NotFoundException(message="Review item not found", code="REVIEW_ITEM_NOT_FOUND")
    if current_user.role == UserRole.officer and current_user.institution_id is not None and item.institution_id != current_user.institution_id:
        raise AppException(status_code=403, code="OFFICER_SCOPE_EXCEEDED", message="Access forbidden outside assigned institution.")

    updated_item = adjudicate_document_submission(
        db=db,
        review_id=review_id,
        decision=body.decision,
        reason=body.reason,
        reviewer=current_user,
    )
    resp = DocumentSubmissionReviewResponse.model_validate(updated_item)
    if updated_item.institution:
        resp.institution_name = updated_item.institution.name
        resp.institution_aicte_id = updated_item.institution.aicte_id
    return resp


@router.post("/request-review", response_model=DocumentSubmissionReviewResponse)
async def request_manual_review(
    institution_id: Optional[UUID] = Form(None),
    note: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Allows an institution user (or officer) to upload a document and explicitly request
    manual Officer review (e.g. if automatic classification marked it as possibly unrelated).
    Does NOT count as a strike.
    """
    if current_user.role == UserRole.institution:
        target_inst_id = current_user.institution_id
    else:
        target_inst_id = institution_id or current_user.institution_id

    if not target_inst_id:
        raise AppException(status_code=400, code="INSTITUTION_ID_REQUIRED", message="Institution ID required.")

    inst = db.query(Institution).filter(Institution.id == target_inst_id).first()
    if not inst:
        raise NotFoundException(message="Institution not found", code="INSTITUTION_NOT_FOUND")

    content, sha256_hash, safe_filename = await storage_service.read_and_validate_upload(file)
    extracted = ocr_extractor.extract_fields(content, safe_filename)

    review_item = record_submission_for_review(
        db=db,
        institution_id=target_inst_id,
        filename=safe_filename,
        sha256_hash=sha256_hash,
        classification_dict=extracted.get("classification") or {},
        storage_path=None,
        fdr_id=None,
    )

    write_audit_log(
        db=db,
        action="document_review.requested_by_user",
        entity="document_review",
        entity_id=review_item.id,
        actor_id=current_user.id,
        actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        old_status=None,
        new_status="pending",
        remarks=f"Manual document review requested for {inst.name}: {note or 'Institution requested officer evaluation.'}",
        payload={"filename": safe_filename, "sha256": sha256_hash},
    )

    db.commit()
    db.refresh(review_item)

    resp = DocumentSubmissionReviewResponse.model_validate(review_item)
    resp.institution_name = inst.name
    resp.institution_aicte_id = inst.aicte_id
    return resp


