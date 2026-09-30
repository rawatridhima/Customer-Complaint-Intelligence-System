from __future__ import annotations  # the class defines list(), which would shadow the builtin in annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidTransitionError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import log_event
from app.models.audit_log import AuditLog
from app.models.complaint import Complaint
from app.models.enums import ALLOWED_TRANSITIONS, Category, ComplaintStatus
from app.models.feedback import Feedback
from app.models.user import User
from app.repositories.audit_log_repo import AuditLogRepository
from app.repositories.complaint_repo import ComplaintRepository
from app.repositories.feedback_repo import FeedbackRepository
from app.repositories.user_repo import UserRepository
from app.schemas.complaint import ComplaintCreate
from app.services.priority_service import PriorityService
from app.services.redaction_service import RedactionService

logger = logging.getLogger(__name__)


class ComplaintService:
    def __init__(self, db: Session) -> None:
        self._repo = ComplaintRepository(db)
        self._audit = AuditLogRepository(db)
        self._feedback = FeedbackRepository(db)
        self._users = UserRepository(db)
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

    # ---- status (FR-28, FR-29, FR-30) ------------------------------------------

    def update_status(
        self, complaint_id: uuid.UUID, new_status: ComplaintStatus, actor: User
    ) -> Complaint:
        """FR-28. Transition validated against the state machine, and audited."""
        complaint = self.get(complaint_id)
        self._apply_status(complaint, new_status, actor)
        self._repo.commit()
        return complaint

    def bulk_update_status(
        self, complaint_ids: list[uuid.UUID], new_status: ComplaintStatus, actor: User
    ) -> tuple[list[uuid.UUID], list[tuple[uuid.UUID, str]]]:
        """FR-29. Each complaint is checked on its own: a resolved complaint in
        the selection is reported as failed instead of blocking the rest.

        Returns (updated_ids, [(failed_id, reason), ...]).
        """
        found = self._repo.get_many(complaint_ids)
        updated, failed = [], []
        for cid in complaint_ids:
            complaint = found.get(cid)
            if complaint is None:
                failed.append((cid, "Complaint not found"))
                continue
            try:
                self._apply_status(complaint, new_status, actor, bulk=True)
            except InvalidTransitionError as exc:
                failed.append((cid, exc.message))
            else:
                updated.append(cid)
        self._repo.commit()
        log_event(logger, "bulk_status_changed", new_status=new_status,
                  updated=len(updated), failed=len(failed))
        return updated, failed

    def _apply_status(
        self, complaint: Complaint, new_status: ComplaintStatus, actor: User,
        bulk: bool = False,
    ) -> None:
        old_status = complaint.status
        if new_status not in ALLOWED_TRANSITIONS[old_status]:
            raise InvalidTransitionError(
                f"Cannot move from {old_status.value} to {new_status.value}"
            )
        complaint.status = new_status
        if new_status is ComplaintStatus.RESOLVED:
            complaint.resolved_at = datetime.now(UTC)
        details = {"from": old_status.value, "to": new_status.value}
        if bulk:
            details["bulk"] = True
        self._record(actor, "status_changed", complaint.complaint_id, details)
        log_event(logger, "status_changed", complaint_id=str(complaint.complaint_id),
                  new_status=new_status)

    # ---- category override (FR-10, FR-41) ----------------------------------------

    def override_category(
        self, complaint_id: uuid.UUID, new_category: Category, actor: User
    ) -> Complaint:
        """An agent corrects the model's category.

        In one transaction this:
          - changes the category and marks the prediction as reviewed
          - keeps the model's original answer (FR-10)
          - recomputes priority, because category severity is one of its factors
          - stores the correction as a training example (FR-41)
          - writes an audit entry (FR-30)
        """
        complaint = self.get(complaint_id)
        prediction = complaint.prediction
        if prediction is None:
            raise InvalidTransitionError(
                "This complaint has not been analysed yet, so there is no category to override"
            )
        old_category = prediction.category
        if new_category == old_category:
            raise ValidationError(f"The category is already {new_category.value}")

        if prediction.original_category is None:
            prediction.original_category = old_category
        prediction.category = new_category
        prediction.overridden_by = actor.user_id
        prediction.overridden_at = datetime.now(UTC)
        prediction.needs_review = False  # a person has now checked it

        old_bucket = prediction.priority_bucket
        priority = PriorityService().compute(
            text=complaint.redacted_text,
            category=new_category,
            sentiment_label=prediction.sentiment_label,
            sentiment_score=float(prediction.sentiment_score),
            repeat_count=max(self._repo.count_prior_complaints(complaint.customer_ref), 0),
        )
        prediction.priority_score = priority.score
        prediction.priority_bucket = priority.bucket
        prediction.priority_breakdown = priority.breakdown

        self._feedback.add(Feedback(
            complaint_id=complaint.complaint_id,
            field_corrected="category",
            original_value=old_category.value,
            corrected_value=new_category.value,
            corrected_by=actor.user_id,
            model_version=prediction.model_version,
        ))
        self._record(actor, "category_overridden", complaint.complaint_id, {
            "from": old_category.value,
            "to": new_category.value,
            "priority_from": old_bucket.value,
            "priority_to": priority.bucket.value,
        })
        self._repo.commit()
        log_event(logger, "category_overridden", complaint_id=str(complaint_id),
                  new_category=new_category)
        return complaint

    # ---- assignment (FR-26 "assigned agent") ----------------------------------

    def assign(
        self, complaint_id: uuid.UUID, assignee_id: uuid.UUID | None, actor: User
    ) -> Complaint:
        complaint = self.get(complaint_id)
        if assignee_id is not None:
            assignee = self._users.get(assignee_id)
            if assignee is None or not assignee.is_active:
                raise ValidationError("That user does not exist or is disabled")
        if complaint.assigned_to == assignee_id:
            return complaint
        old = complaint.assigned_to
        complaint.assigned_to = assignee_id
        self._record(actor, "assigned", complaint.complaint_id, {
            "from": self._username(old),
            "to": self._username(assignee_id),
        })
        self._repo.commit()
        return complaint

    # ---- audit trail (FR-30) --------------------------------------------------

    def history(self, complaint_id: uuid.UUID) -> list[dict]:
        """Newest first, with the actor's username resolved for display."""
        self.get(complaint_id)  # 404 if the complaint does not exist
        entries = self._audit.list_by_entity("complaint", complaint_id)
        names: dict[uuid.UUID | None, str | None] = {}
        rows = []
        for e in entries:
            if e.actor_id not in names:
                names[e.actor_id] = self._username(e.actor_id)
            rows.append({
                "action": e.action,
                "details": json.loads(e.details) if e.details else None,
                "actor_username": names[e.actor_id],
                "created_at": e.created_at,
            })
        return rows

    def _record(self, actor: User, action: str, complaint_id: uuid.UUID, details: dict) -> None:
        self._audit.add(AuditLog(
            actor_id=actor.user_id,
            action=action,
            entity_type="complaint",
            entity_id=complaint_id,
            details=json.dumps(details),
        ))

    def _username(self, user_id: uuid.UUID | None) -> str | None:
        if user_id is None:
            return None
        user = self._users.get(user_id)
        return user.username if user else None

    @staticmethod
    def _enqueue_analysis(complaint_id: uuid.UUID) -> None:
        """Import inside the function so the API does not hard-depend on Celery."""
        try:
            from app.workers.tasks import analyse_complaint

            analyse_complaint.delay(str(complaint_id))
        except Exception:
            logger.warning("could not enqueue analysis; is the worker running?")
