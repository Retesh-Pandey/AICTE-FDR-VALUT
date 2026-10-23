from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import UserRole


class UserBase(BaseModel):
    email: str
    full_name: str | None = None
    role: UserRole
    institution_id: UUID | None = None


class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InstitutionBrief(BaseModel):
    id: UUID
    aicte_id: str
    name: str
    region: str | None = None
    model_config = ConfigDict(from_attributes=True)


class MeResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    role: UserRole
    institution_id: UUID | None = None
    institution: InstitutionBrief | None = None
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str | None = None


class PasswordLoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeResponse

