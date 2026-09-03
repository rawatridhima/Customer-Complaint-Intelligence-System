import logging
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidTransitionError, NotFoundError
from app.core.logging import log_event
from app.models.complaint import Complaint
from app.models.enums import ALLOWED_TRANSITIONS, ComplaintStatus
from app.repositories.complaint_repo import ComplaintRepository
from app.schemas.complaint import ComplaintCreate
from app.services.redaction_service import RedactionService

logger = logging.getLogger(__name__)


class ComplaintService:
    def __init__(self, db: Session) -> None:
        self._repo = ComplaintRepository(db)
        self._redactor = RedactionService()

    def create(self, payload: ComplaintCreate) -> Complaint:
        """FR-01 to FR-06. Returns immediately. Analysis is enqueued."""
        redacted = self._redactor.redact(payload.text)
        text_hash = self._redactor.hash_text(payload.text)

        original = self._repo.find_duplicate(text_hash, payload.customer_ref)

        complaint = Complaint(
            raw_text=payload.text,
            redacted_text=redacted,
            text_hash=text_hash,
            customer_ref=payload.customer_ref,
            channel=payload.channel,
            duplicate_of=original.complaint_id if original else None,
        )
        self._repo.add(complaint)
        self._repo.commit()

        log_event(
            logger, "complaint_created",
            complaint_id=str(complaint.complaint_id),
            is_duplicate=original is not None,
        )

        self._enqueue_analysis(complaint.complaint_id)
        return complaint

    def get(self, complaint_id: uuid.UUID) -> Complaint:
        complaint = self._repo.get(complaint_id)
        if complaint is None:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        return complaint

    def list(self, **filters):
        return self._repo.list(**filters)

    def update_status(
        self, complaint_id: uuid.UUID, new_status: ComplaintStatus
    ) -> Complaint:
        """FR-28. Transition validated against the state machine."""
        complaint = self.get(complaint_id)
        allowed = ALLOWED_TRANSITIONS[complaint.status]
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot move from {complaint.status} to {new_status}"
            )
        complaint.status = new_status
        self._repo.commit()
        log_event(
            logger, "status_changed",
            complaint_id=str(complaint_id), new_status=new_status,
        )
        return complaint

    @staticmethod
    def _enqueue_analysis(complaint_id: uuid.UUID) -> None:
        """Import inside the function so the API does not hard-depend on Celery."""
        try:
            from app.workers.tasks import analyse_complaint

            analyse_complaint.delay(str(complaint_id))
        except Exception:
            logger.warning("could not enqueue analysis; is the worker running?")
