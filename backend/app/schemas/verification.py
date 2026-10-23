from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import VerificationStatus


class VerificationLogBase(BaseModel):
    source: str
    submitted_values: Dict[str, Any]
    confirmed_values: Optional[Dict[str, Any]] = None
    discrepancies: Optional[List[Dict[str, Any]]] = None
    outcome: VerificationStatus
    resolution_note: Optional[str] = None


class VerificationLogResponse(VerificationLogBase):
    id: UUID
    fdr_id: UUID
    resolved_by: Optional[UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DiscrepancyResolutionRequest(BaseModel):
    resolution_note: str
    outcome: VerificationStatus


class SimulatedVerificationResponse(BaseModel):
    source: str = "SIMULATED_BANK"
    outcome: str  # "match" | "mismatch" | "not_found"
    mode: str = "mock"
    fdr_id: UUID
    fdr_number: str
    bank_name: str
    matched_fields: List[str] = []
    different_fields: List[Dict[str, Any]] = []
    all_comparisons: List[Dict[str, Any]] = []
    disclaimer: str
    timestamp: datetime
    actor: Optional[str] = None
    new_verification_status: VerificationStatus
    verification_log_id: Optional[UUID] = None
