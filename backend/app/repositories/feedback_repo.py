import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import Feedback


class FeedbackRepository:
    """Database access for agent feedback and prediction corrections."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, feedback: Feedback) -> Feedback:
        self._db.add(feedback)
        self._db.flush()
        return feedback

    def get(
        self,
        feedback_id: uuid.UUID,
    ) -> Feedback | None:
        stmt = select(Feedback).where(
            Feedback.feedback_id == feedback_id
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def list_by_complaint(
        self,
        complaint_id: uuid.UUID,
    ) -> list[Feedback]:
        stmt = (
            select(Feedback)
            .where(Feedback.complaint_id == complaint_id)
            .order_by(Feedback.created_at.desc())
        )

        return list(self._db.execute(stmt).scalars().all())

    def commit(self) -> None:
        self._db.commit()