import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.enums import (
    ALLOWED_TRANSITIONS,
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
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

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
    # FR-10: set once an agent has overridden the category.
    original_category: Category | None = None
    overridden_by: uuid.UUID | None = None
    overridden_at: datetime | None = None


class ComplaintSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    complaint_id: uuid.UUID
    raw_text: str
    status: ComplaintStatus
    analysis_status: AnalysisStatus
    submitted_at: datetime
    assigned_to: uuid.UUID | None = None
    prediction: PredictionOut | None = None


class ComplaintDetail(ComplaintSummary):
    customer_ref: str | None = None
    channel: str
    duplicate_of: uuid.UUID | None = None
    resolved_at: datetime | None = None

    @computed_field
    @property
    def allowed_next_statuses(self) -> list[ComplaintStatus]:
        """The state machine, so the UI never offers an invalid move (FR-28)."""
        return sorted(ALLOWED_TRANSITIONS[self.status])


class StatusUpdate(BaseModel):
    status: ComplaintStatus


class Paginated(BaseModel):
    items: list[ComplaintSummary]
    page: int
    size: int
    total: int
    pages: int



class CategoryOverride(BaseModel):
    """FR-10."""

    category: Category


class BulkStatusUpdate(BaseModel):
    """FR-29. At most 100 complaints per request, one page of the inbox."""

    complaint_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    status: ComplaintStatus

    @field_validator("complaint_ids")
    @classmethod
    def _unique(cls, ids: list[uuid.UUID]) -> list[uuid.UUID]:
        return list(dict.fromkeys(ids))  # drop repeats, keep order


class BulkFailure(BaseModel):
    complaint_id: uuid.UUID
    reason: str


class BulkStatusResult(BaseModel):
    updated: list[uuid.UUID]
    failed: list[BulkFailure]


class AssignRequest(BaseModel):
    """Assign to a staff member, or null to unassign."""

    user_id: uuid.UUID | None


class HistoryEntry(BaseModel):
    """One line of a complaint's audit trail (FR-30)."""

    action: str
    details: dict | None = None
    actor_username: str | None = None
    created_at: datetime
