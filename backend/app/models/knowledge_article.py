import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.enums import Category


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    body: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    category: Mapped[Category] = mapped_column(
        Enum(Category, name="category_enum"),
        nullable=False,
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(384)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )