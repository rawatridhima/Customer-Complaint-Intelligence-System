import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("complaints.complaint_id", ondelete="CASCADE"),
        nullable=False,
    )

    field_corrected: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    original_value: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    corrected_value: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    corrected_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
    )

    model_version: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )