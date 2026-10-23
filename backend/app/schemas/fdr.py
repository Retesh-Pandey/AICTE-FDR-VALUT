from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.db.models import InstrumentStatus, VerificationStatus, WorkflowStatus
from app.schemas.document import FDRDocumentResponse
from app.schemas.release import ReleaseRequestResponse
from app.schemas.user import InstitutionBrief
from app.schemas.verification import VerificationLogResponse


class FDRBase(BaseModel):
    institution_id: UUID
    fdr_number: str
    bank_name: str
    branch: Optional[str] = None
    amount: Decimal
    issue_date: date
    maturity_date: date
    lien_info: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("FDR principal amount must be strictly greater than 0")
        return v

    @field_validator("maturity_date")
    @classmethod
    def validate_dates(cls, v: date, info) -> date:
        issue = info.data.get("issue_date")
        if issue and v <= issue:
            raise ValueError("Maturity date must be strictly after the issue date")
        return v


class FDRCreate(FDRBase):
    previous_fdr_id: Optional[UUID] = None


class FDRUpdate(BaseModel):
    branch: Optional[str] = None
    lien_info: Optional[str] = None
    instrument_status: Optional[InstrumentStatus] = None
    verification_status: Optional[VerificationStatus] = None
    workflow_status: Optional[WorkflowStatus] = None


class FDRResponse(FDRBase):
    id: UUID
    previous_fdr_id: Optional[UUID] = None
    is_current: bool
    instrument_status: InstrumentStatus
    verification_status: VerificationStatus
    workflow_status: WorkflowStatus
    submitted_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    institution: Optional[InstitutionBrief] = None

    model_config = ConfigDict(from_attributes=True)


class FDRDetailResponse(FDRResponse):
    documents: List[FDRDocumentResponse] = []
    verification_logs: List[VerificationLogResponse] = []
    release_requests: List[ReleaseRequestResponse] = []

    model_config = ConfigDict(from_attributes=True)


class FDRListResponse(BaseModel):
    items: List[FDRResponse]
    total: int
    page: int
    limit: int
    pages: int


class OCRField(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0


class DocumentClassification(BaseModel):
    status: str = "likely_fdr"  # likely_fdr | possibly_fdr_needs_review | likely_unrelated | unreadable | ocr_unavailable | corrupt_or_unsupported
    confidence: float = 0.0
    classification_reasons: List[str] = []
    detected_document_type: Optional[str] = None
    content_summary: Optional[str] = None
    extracted_snippets: List[str] = []
    is_fdr_candidate: bool = True
    submission_blocked: bool = False


class OCRResponse(BaseModel):
    fdr_number: OCRField = OCRField()
    bank_name: OCRField = OCRField()
    ifsc: OCRField = OCRField()
    branch: OCRField = OCRField()
    amount: OCRField = OCRField()
    interest_rate: OCRField = OCRField()
    compounding: OCRField = OCRField()
    tenure: OCRField = OCRField()
    issue_date: OCRField = OCRField()
    maturity_date: OCRField = OCRField()
    institution_name: OCRField = OCRField()
    institution_id: OCRField = OCRField()
    lien_info: OCRField = OCRField()
    raw_text: str = ""
    extraction_status: str = "success"  # success | partial | needs_review | likely_unrelated | unreadable | ocr_unavailable | corrupt_or_unsupported
    status_detail: Optional[str] = None
    engine_available: bool = True
    engine_status: str = "available"  # available | engine_missing | language_data_missing
    classification: DocumentClassification = DocumentClassification()
    disclaimer: str = "Assistive data entry only. Extraction does not prove document authenticity or verify bank records."


class FDRSubmissionResponse(BaseModel):
    fdr: FDRResponse
    document: FDRDocumentResponse
    validation_flags: List[dict] = []
    message: str = "FDR registered successfully with pending verification"


class DiscrepancyResolutionRequest(BaseModel):
    outcome: VerificationStatus
    resolution_note: str


class DocumentSubmissionReviewResponse(BaseModel):
    id: UUID
    institution_id: UUID
    fdr_id: Optional[UUID] = None
    document_sha256: str
    filename: str
    classification: str
    confidence: float
    classification_reasons: Optional[List[str]] = None
    detected_document_type: Optional[str] = None
    content_summary: Optional[str] = None
    extracted_snippets: Optional[List[str]] = None
    review_status: str
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_reason: Optional[str] = None
    is_strike: bool
    created_at: datetime
    institution_name: Optional[str] = None
    institution_aicte_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentSubmissionAdjudicationRequest(BaseModel):
    decision: str  # confirm_unrelated | override_as_fdr | dismiss
    reason: str


class HoldAppealRequest(BaseModel):
    appeal_reason: str


class AdminUnfreezeRequest(BaseModel):
    reason: str


class AdminExtendHoldRequest(BaseModel):
    days: int = 14
    reason: str


class InstitutionHoldStatus(BaseModel):
    institution_id: UUID
    institution_name: str
    upload_hold_active: bool
    upload_hold_until: Optional[datetime] = None
    upload_hold_reason: Optional[str] = None
    upload_hold_placed_at: Optional[datetime] = None
    upload_hold_appealed_at: Optional[datetime] = None
    upload_hold_appeal_reason: Optional[str] = None
    confirmed_strikes_in_window: int = 0
    strike_threshold: int = 7
    window_days: int = 30
    hold_duration_days: int = 14

