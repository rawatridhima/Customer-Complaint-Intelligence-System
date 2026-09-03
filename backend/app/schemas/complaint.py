import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AnalysisStatus,
    Category,
    ComplaintStatus,
    Priority,
    Sentiment,
)


class ComplaintCreate(BaseModel):
    text: str = Field(min_length=20, max_length=5000)
    customer_ref: str | None = Field(default=None, max_length=128)
    channel: str = Field(default="web", max_length=32)


class ComplaintCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    complaint_id: uuid.UUID
    status: ComplaintStatus
    analysis_status: AnalysisStatus
    submitted_at: datetime
    duplicate_of: uuid.UUID | None = None


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: Category
    category_confidence: float
    sentiment_label: Sentiment
    sentiment_score: float
    priority_score: float
    priority_bucket: Priority
    priority_breakdown: dict
    needs_review: bool
    model_version: str
    inference_ms: int | None = None


class ComplaintSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    complaint_id: uuid.UUID
    raw_text: str
    status: ComplaintStatus
    analysis_status: AnalysisStatus
    submitted_at: datetime
    prediction: PredictionOut | None = None


class ComplaintDetail(ComplaintSummary):
    customer_ref: str | None = None
    channel: str
    assigned_to: uuid.UUID | None = None
    duplicate_of: uuid.UUID | None = None
    resolved_at: datetime | None = None


class StatusUpdate(BaseModel):
    status: ComplaintStatus


class Paginated(BaseModel):
    items: list[ComplaintSummary]
    page: int
    size: int
    total: int
    pages: int
