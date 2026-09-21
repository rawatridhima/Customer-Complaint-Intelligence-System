import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GeneratedContent(Base):
    __tablename__ = "generated_content"

    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("complaints.complaint_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    summary: Mapped[str | None] = mapped_column(Text)
    suggested_resolution: Mapped[str | None] = mapped_column(Text)
    draft_response: Mapped[str | None] = mapped_column(Text)
    final_response: Mapped[str | None] = mapped_column(Text)

    cited_article_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True))
    )

    prompt_version: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    llm_model: Mapped[str | None] = mapped_column(String(64))
    token_count: Mapped[int | None] = mapped_column(Integer)

    was_edited: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    complaint = relationship("Complaint", backref="generated_content")

    approver = relationship("User")