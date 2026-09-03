import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import Category, Priority, Sentiment


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("complaints.complaint_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    category: Mapped[Category] = mapped_column(
        Enum(Category, name="category_enum"), nullable=False
    )
    category_confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    sentiment_label: Mapped[Sentiment] = mapped_column(
        Enum(Sentiment, name="sentiment_enum"), nullable=False
    )
    sentiment_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)

    priority_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    priority_bucket: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum"), nullable=False
    )
    priority_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)

    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    inference_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    complaint = relationship("Complaint", back_populates="prediction")
