from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InstitutionBase(BaseModel):
    aicte_id: str
    name: str
    region: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None


class InstitutionCreate(InstitutionBase):
    source: Optional[str] = "PORTAL_REGISTRY"


class InstitutionUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None


class InstitutionResponse(InstitutionBase):
    id: UUID
    source: str = "PORTAL_REGISTRY"
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InstitutionPublicBrief(BaseModel):
    id: UUID
    aicte_id: str
    name: str
    region: Optional[str] = None
    source: str = "PORTAL_REGISTRY"
    is_synthetic: bool = True
    last_synced_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class InstitutionDirectoryPage(BaseModel):
    items: List[InstitutionPublicBrief]
    total: int
    page: int
    limit: int
    pages: int
    source_label: str
    coverage_disclaimer: str
    last_synced_at: Optional[datetime] = None


class InstitutionRegistrationCreate(BaseModel):
    institution_name: str = Field(..., min_length=3, max_length=255)
    aicte_id: Optional[str] = Field(None, max_length=100)
    contact_person: str = Field(..., min_length=2, max_length=255)
    official_email: EmailStr
    region: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None


class InstitutionRegistrationResponse(BaseModel):
    id: UUID
    institution_name: str
    aicte_id: Optional[str] = None
    contact_person: str
    official_email: str
    region: Optional[str] = None
    address: Optional[str] = None
    status: str
    review_decision: Optional[str] = None
    review_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    tracking_reference: str
    notice: str
    model_config = ConfigDict(from_attributes=True)


class InstitutionRegistrationReview(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected|duplicate)$")
    review_reason: str = Field(..., min_length=5, max_length=1000)


class InstitutionDirectorySyncItem(BaseModel):
    aicte_id: str
    name: str
    region: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None


class InstitutionDirectorySyncRequest(BaseModel):
    source: str = Field(..., min_length=3, max_length=100)
    institutions: List[InstitutionDirectorySyncItem]


class InstitutionDirectorySyncResponse(BaseModel):
    total_processed: int
    created_count: int
    updated_count: int
    skipped_count: int
    rejected_rows: List[dict]
    source: str
    timestamp: datetime
