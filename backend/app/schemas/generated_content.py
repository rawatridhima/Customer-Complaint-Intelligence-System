import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Tone = Literal["urgent", "empathetic", "professional"]


class CitedArticle(BaseModel):
    article_id: uuid.UUID
    title: str


class GeneratedContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content_id: uuid.UUID
    complaint_id: uuid.UUID

    summary: str | None = None
    suggested_resolution: str | None = None
    draft_response: str | None = None      # as generated; never overwritten by edits
    final_response: str | None = None      # the agent's edited / approved text (FR-23)

    cited_article_ids: list[uuid.UUID] | None = None
    cited_articles: list[CitedArticle] = []

    tone: str | None = None
    is_fallback: bool = False               # FR-25: template, handle manually
    fallback_reason: str | None = None

    prompt_version: str
    llm_model: str | None = None
    token_count: int | None = None

    was_edited: bool
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime


class GenerateRequest(BaseModel):
    """Leave tone empty to pick it from sentiment and priority (FR-21)."""

    tone: Tone | None = None


class GeneratedContentUpdate(BaseModel):
    """FR-23. Save an edit without approving it."""

    final_response: str = Field(min_length=1, max_length=5000)


class GeneratedContentApprove(BaseModel):
    """FR-22. The text being approved, usually the edited draft."""

    final_response: str = Field(min_length=1, max_length=5000)
