from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogBase(BaseModel):
    actor_id: Optional[UUID] = None
    actor_role: Optional[str] = None
    action: str
    entity: str
    entity_id: Optional[UUID] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    remarks: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class AuditLogResponse(AuditLogBase):
    id: int
    created_at: datetime
    prev_hash: Optional[str] = None
    row_hash: str
    model_config = ConfigDict(from_attributes=True)


class ChainVerificationResponse(BaseModel):
    valid: bool
    broken_at: Optional[int] = None
    total_blocks: int
    head_hash: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_time_ms: Optional[float] = None
    message: Optional[str] = None
