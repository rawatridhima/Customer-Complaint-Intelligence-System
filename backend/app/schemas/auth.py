import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models.enums import UserRole


def _check_password(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes")
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8)
    role: UserRole = UserRole.AGENT

    _password_bytes = field_validator("password")(_check_password)

    @field_validator("username", "email")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(BaseModel):
    """Admin edits. Every field is optional; only the ones sent are changed."""

    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)

    _password_bytes = field_validator("password")(
        lambda v: v if v is None else _check_password(v)
    )
