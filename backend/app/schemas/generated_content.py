import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GeneratedContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content_id: uuid.UUID
    complaint_id: uuid.UUID

    summary: str | None = None
    suggested_resolution: str | None = None
    draft_response: str | None = None
    final_response: str | None = None

    cited_article_ids: list[uuid.UUID] | None = None

    prompt_version: str
    llm_model: str | None = None
    token_count: int | None = None

    was_edited: bool
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime

class GeneratedContentUpdate(BaseModel):
    draft_response: str


class GeneratedContentApprove(BaseModel):
    final_response: str