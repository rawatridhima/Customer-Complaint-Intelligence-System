import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    actor_id: uuid.UUID | None = None
    action: str = Field(min_length=1, max_length=64)
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: uuid.UUID | None = None
    details: str | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    details: str | None
    created_at: datetime