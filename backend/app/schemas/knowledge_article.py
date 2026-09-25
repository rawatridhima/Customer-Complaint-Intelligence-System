import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Category


class KnowledgeArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    category: Category
    embedding: list[float] | None = None


class KnowledgeArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    article_id: uuid.UUID
    title: str
    body: str
    category: Category
    embedding: list[float] | None = None
    created_at: datetime


class KnowledgeArticleSearch(BaseModel):
    embedding: list[float]
    limit: int = Field(default=5, ge=1, le=20)