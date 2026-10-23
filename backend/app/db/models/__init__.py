import enum
import uuid
from datetime import UTC, datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.types import GUID


def utc_now():
    return datetime.now(UTC)


class UserRole(str, enum.Enum):
    institution = "institution"
    officer = "officer"
    admin = "admin"


class InstrumentStatus(str, enum.Enum):
    submitted = "submitted"
    active = "active"
    renewal_due = "renewal_due"
    matured = "matured"
    renewed = "renewed"
    released = "released"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    discrepancy = "discrepancy"
    rejected = "rejected"


class WorkflowStatus(str, enum.Enum):
    none = "none"
    renewal_review = "renewal_review"
    release_requested = "release_requested"
    under_review = "under_review"
    conditions_checked = "conditions_checked"
    approval_pending = "approval_pending"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"


class RegistrationRequestStatus(str, enum.Enum):
    pending_verification = "pending_verification"
    approved = "approved"
    rejected = "rejected"
    duplicate = "duplicate"


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    aicte_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    region = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    contact_email = Column(String(255), nullable=True)
    source = Column(String(100), nullable=False, default="PORTAL_REGISTRY")
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Temporary Review Hold fields for repeated confirmed unrelated submissions
    upload_hold_active = Column(Boolean, nullable=False, default=False)
    upload_hold_until = Column(DateTime(timezone=True), nullable=True)
    upload_hold_reason = Column(Text, nullable=True)
    upload_hold_placed_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    upload_hold_placed_at = Column(DateTime(timezone=True), nullable=True)
    upload_hold_appealed_at = Column(DateTime(timezone=True), nullable=True)
    upload_hold_appeal_reason = Column(Text, nullable=True)

    users = relationship("User", back_populates="institution", foreign_keys="User.institution_id")
    fdrs = relationship("FDRRecord", back_populates="institution")
    document_reviews = relationship("DocumentSubmissionReview", back_populates="institution", cascade="all, delete-orphan")
    hold_reviewer = relationship("User", foreign_keys=[upload_hold_placed_by])




class InstitutionRegistrationRequest(Base):
    __tablename__ = "institution_registration_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    institution_name = Column(String(255), nullable=False)
    aicte_id = Column(String(100), nullable=True, index=True)
    contact_person = Column(String(255), nullable=False)
    official_email = Column(String(255), nullable=False, index=True)
    region = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    status = Column(
        SQLEnum(RegistrationRequestStatus, native_enum=False),
        nullable=False,
        default=RegistrationRequestStatus.pending_verification,
    )
    reviewed_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    review_decision = Column(String(50), nullable=True)
    review_reason = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    institution_id = Column(GUID(), ForeignKey("institutions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    reviewer = relationship("User", foreign_keys=[reviewed_by])
    institution = relationship("Institution", foreign_keys=[institution_id])


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(SQLEnum(UserRole, native_enum=False), nullable=False)
    institution_id = Column(GUID(), ForeignKey("institutions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    institution = relationship("Institution", back_populates="users", foreign_keys=[institution_id])




class FDRRecord(Base):
    __tablename__ = "fdr_records"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    institution_id = Column(GUID(), ForeignKey("institutions.id"), nullable=False, index=True)
    fdr_number = Column(String(100), nullable=False)
    bank_name = Column(String(255), nullable=False)
    branch = Column(String(255), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    issue_date = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False, index=True)
    lien_info = Column(Text, nullable=True)
    previous_fdr_id = Column(GUID(), ForeignKey("fdr_records.id"), nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)

    instrument_status = Column(
        SQLEnum(InstrumentStatus, native_enum=False),
        nullable=False,
        default=InstrumentStatus.submitted
    )
    verification_status = Column(
        SQLEnum(VerificationStatus, native_enum=False),
        nullable=False,
        default=VerificationStatus.pending
    )
    workflow_status = Column(
        SQLEnum(WorkflowStatus, native_enum=False),
        nullable=False,
        default=WorkflowStatus.none
    )

    submitted_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    institution = relationship("Institution", back_populates="fdrs")
    documents = relationship("FDRDocument", back_populates="fdr", cascade="all, delete-orphan")
    verification_logs = relationship("VerificationLog", back_populates="fdr", cascade="all, delete-orphan")
    release_requests = relationship("ReleaseRequest", back_populates="fdr", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="fdr", cascade="all, delete-orphan")
    previous_fdr = relationship("FDRRecord", remote_side=[id], backref="next_fdrs", foreign_keys=[previous_fdr_id])
    submitter = relationship("User", foreign_keys=[submitted_by])

    __table_args__ = (
        UniqueConstraint("bank_name", "fdr_number", name="uq_bank_fdr_number"),
        CheckConstraint("amount > 0", name="chk_amount_positive"),
        CheckConstraint("maturity_date > issue_date", name="chk_maturity_after_issue"),
        Index("idx_fdr_inst", "institution_id"),
        Index("idx_fdr_maturity", "maturity_date"),
    )


class FDRDocument(Base):
    __tablename__ = "fdr_documents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    fdr_id = Column(GUID(), ForeignKey("fdr_records.id", ondelete="CASCADE"), nullable=True)
    storage_path = Column(String(500), nullable=False)
    doc_type = Column(String(50), nullable=False, default="fdr_receipt")
    sha256 = Column(String(64), nullable=False, index=True)
    ocr_raw_text = Column(Text, nullable=True)
    extracted_json = Column(JSON, nullable=True)
    uploaded_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=utc_now)

    fdr = relationship("FDRRecord", back_populates="documents")


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    fdr_id = Column(GUID(), ForeignKey("fdr_records.id"), nullable=False)
    source = Column(String(100), nullable=False)  # 'SIMULATED_BANK' | 'MANUAL'
    submitted_values = Column(JSON, nullable=False)
    confirmed_values = Column(JSON, nullable=True)
    discrepancies = Column(JSON, nullable=True)
    outcome = Column(SQLEnum(VerificationStatus, native_enum=False), nullable=False)
    resolved_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    fdr = relationship("FDRRecord", back_populates="verification_logs")


class ReleaseRequest(Base):
    __tablename__ = "release_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    fdr_id = Column(GUID(), ForeignKey("fdr_records.id"), nullable=False)
    requested_by = Column(GUID(), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    stage = Column(
        SQLEnum(WorkflowStatus, native_enum=False),
        nullable=False,
        default=WorkflowStatus.release_requested
    )
    assigned_officer = Column(GUID(), ForeignKey("users.id"), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    fdr = relationship("FDRRecord", back_populates="release_requests")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    fdr_id = Column(GUID(), ForeignKey("fdr_records.id"), nullable=True)
    type = Column(String(50), nullable=False)  # maturity_30|maturity_15|maturity_7|matured|discrepancy|workflow
    milestone = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    fdr = relationship("FDRRecord", back_populates="notifications")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "fdr_id", "milestone", name="uq_notification_milestone"),
    )


class WorkflowAuditLog(Base):
    __tablename__ = "workflow_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(GUID(), nullable=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(50), nullable=False)  # 'fdr' | 'release_request' | 'document'
    entity_id = Column(GUID(), nullable=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    remarks = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    prev_hash = Column(String(64), nullable=True)
    row_hash = Column(String(64), nullable=False)


class MockBankRecord(Base):
    __tablename__ = "mock_bank_records"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    fdr_number = Column(String(100), nullable=False)
    bank_name = Column(String(255), nullable=False)
    branch = Column(String(255), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    issue_date = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False)
    lien_marked = Column(Boolean, nullable=False, default=True)
    status = Column(String(50), nullable=False, default="CONFIRMED")
    created_at = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint("bank_name", "fdr_number", name="uq_mock_bank_fdr"),
    )


class DocumentSubmissionReview(Base):
    __tablename__ = "document_submission_reviews"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    institution_id = Column(GUID(), ForeignKey("institutions.id"), nullable=False, index=True)
    fdr_id = Column(GUID(), ForeignKey("fdr_records.id", ondelete="SET NULL"), nullable=True)
    document_sha256 = Column(String(64), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=True)
    classification = Column(String(50), nullable=False)  # likely_fdr | possibly_fdr_needs_review | likely_unrelated | unreadable | ocr_unavailable | corrupt_or_unsupported
    confidence = Column(Numeric(4, 3), nullable=False, default=0.0)
    classification_reasons = Column(JSON, nullable=True)
    detected_document_type = Column(String(100), nullable=True)
    content_summary = Column(Text, nullable=True)
    extracted_snippets = Column(JSON, nullable=True)
    review_status = Column(String(50), nullable=False, default="pending")  # pending | confirmed_unrelated | overridden_as_fdr | dismissed
    reviewed_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_reason = Column(Text, nullable=True)
    is_strike = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    institution = relationship("Institution", back_populates="document_reviews")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    fdr = relationship("FDRRecord")

