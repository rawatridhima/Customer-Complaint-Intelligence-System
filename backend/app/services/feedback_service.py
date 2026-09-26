import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.feedback import Feedback
from app.repositories.feedback_repo import FeedbackRepository


class FeedbackService:
    """Business logic for agent feedback."""

    def __init__(self, db: Session) -> None:
        self._repo = FeedbackRepository(db)

    def create(
        self,
        complaint_id: uuid.UUID,
        field_corrected: str,
        original_value: str,
        corrected_value: str,
        corrected_by: uuid.UUID,
        model_version: str,
    ) -> Feedback:
        feedback = Feedback(
            complaint_id=complaint_id,
            field_corrected=field_corrected,
            original_value=original_value,
            corrected_value=corrected_value,
            corrected_by=corrected_by,
            model_version=model_version,
        )

        self._repo.add(feedback)
        self._repo.commit()

        return feedback

    def get(self, feedback_id: uuid.UUID) -> Feedback:
        feedback = self._repo.get(feedback_id)

        if feedback is None:
            raise NotFoundError(
                f"Feedback {feedback_id} not found"
            )

        return feedback

    def list_by_complaint(
        self,
        complaint_id: uuid.UUID,
    ) -> list[Feedback]:
        return self._repo.list_by_complaint(complaint_id)