from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FDRDocumentBase(BaseModel):
    storage_path: str
    doc_type: str = "fdr_receipt"
    sha256: str
    ocr_raw_text: Optional[str] = None
    extracted_json: Optional[Dict[str, Any]] = None


class FDRDocumentCreate(FDRDocumentBase):
    fdr_id: Optional[UUID] = None


class FDRDocumentResponse(FDRDocumentBase):
    id: UUID
    fdr_id: Optional[UUID] = None
    uploaded_by: Optional[UUID] = None
    uploaded_at: datetime
    signed_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
