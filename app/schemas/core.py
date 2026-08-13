from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.core import EnvironmentStatus


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str


class EnvironmentCreate(BaseModel):
    template_id: str
    name: str | None = Field(default=None, max_length=80)
    ttl_hours: int | None = Field(default=None, ge=1, le=72)


class ComponentStatus(BaseModel):
    name: str
    healthy: bool
    message: str | None = None


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    template_id: str
    status: EnvironmentStatus
    url: str | None
    error_message: str | None
    created_at: datetime
    expires_at: datetime | None


class EnvironmentDetail(EnvironmentOut):
    components: list[ComponentStatus] = []


class CredentialsOut(BaseModel):
    values: dict[str, str]


class LogsOut(BaseModel):
    logs: dict[str, str]
