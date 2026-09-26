import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    complaint_id: uuid.UUID
    field_corrected: str = Field(min_length=1, max_length=32)
    original_value: str = Field(min_length=1, max_length=64)
    corrected_value: str = Field(min_length=1, max_length=64)
    corrected_by: uuid.UUID
    model_version: str = Field(min_length=1, max_length=32)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feedback_id: uuid.UUID
    complaint_id: uuid.UUID
    field_corrected: str
    original_value: str
    corrected_value: str
    corrected_by: uuid.UUID
    model_version: str
    created_at: datetime