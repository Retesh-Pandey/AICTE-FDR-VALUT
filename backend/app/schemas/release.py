from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import InstrumentStatus, WorkflowStatus


class ReleaseRequestCreate(BaseModel):
    fdr_id: UUID
    reason: str


class ReleaseTransitionRequest(BaseModel):
    to_stage: WorkflowStatus
    remarks: Optional[str] = None


class ReleaseRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fdr_id: UUID
    requested_by: UUID
    reason: str
    stage: WorkflowStatus
    assigned_officer: Optional[UUID] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Nested FDR preview metadata
    fdr_number: Optional[str] = None
    bank_name: Optional[str] = None
    amount: Optional[Decimal] = None
    institution_name: Optional[str] = None
    fdr_instrument_status: Optional[InstrumentStatus] = None
