import json
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.audit_log import AuditLog
from app.models.complaint import Complaint
from app.models.generated_content import GeneratedContent
from app.repositories.audit_log_repo import AuditLogRepository
from app.repositories.complaint_repo import ComplaintRepository
from app.repositories.generated_content_repo import GeneratedContentRepository
from app.services.llm_service import LLMService


class GeneratedContentService:
    """Generate and persist LLM content for a complaint."""

    def __init__(self, db: Session) -> None:
        self._complaint_repo = ComplaintRepository(db)
        self._repo = GeneratedContentRepository(db)
        self._audit = AuditLogRepository(db)
        self._llm = LLMService()

    def generate(self, complaint_id: uuid.UUID) -> GeneratedContent:
        complaint = self._complaint_repo.get(complaint_id)

        if complaint is None:
            raise NotFoundError(
                f"Complaint {complaint_id} not found"
            )

        complaint_text = complaint.redacted_text

        summary = self._llm.generate_summary(
            complaint_text
        )

        resolution = self._llm.generate_resolution(
            complaint_text
        )

        draft_response = self._llm.generate_response(
            complaint_text,
            resolution,
        )

        existing = self._repo.get_by_complaint(
            complaint_id
        )

        if existing is not None:
            existing.summary = summary
            existing.suggested_resolution = resolution
            existing.draft_response = draft_response
            existing.prompt_version = self._llm.prompt_version
            self._repo.update(existing)
            self._repo.commit()
            return existing

        content = GeneratedContent(
            complaint_id=complaint_id,
            summary=summary,
            suggested_resolution=resolution,
            draft_response=draft_response,
            prompt_version=self._llm.prompt_version,
            llm_model=self._llm.model or None,
        )

        self._repo.add(content)
        self._repo.commit()

        return content

    def get(self, complaint_id: uuid.UUID) -> GeneratedContent:
        content = self._repo.get_by_complaint(complaint_id)

        if content is None:
            raise NotFoundError(
                f"Generated content for complaint "
                f"{complaint_id} not found"
            )

        return content

    def update_draft(
        self,
        complaint_id: uuid.UUID,
        draft_response: str,
    ) -> GeneratedContent:
        content = self._repo.get_by_complaint(complaint_id)

        if content is None:
            raise NotFoundError(
                f"Generated content for complaint {complaint_id} not found"
            )

        content.draft_response = draft_response
        content.was_edited = True

        self._repo.update(content)
        self._repo.commit()

        return content

    def approve(
        self,
        complaint_id: uuid.UUID,
        final_response: str,
        approved_by: uuid.UUID,
    ) -> GeneratedContent:
        """FR-22. Records who approved the response and when."""
        content = self._repo.get_by_complaint(complaint_id)

        if content is None:
            raise NotFoundError(
                f"Generated content for complaint {complaint_id} not found"
            )

        content.final_response = final_response
        content.approved_by = approved_by
        content.approved_at = datetime.now(UTC)
        # FR-30: approvals are part of the complaint's audit trail.
        self._audit.add(AuditLog(
            actor_id=approved_by,
            action="response_approved",
            entity_type="complaint",
            entity_id=complaint_id,
            details=json.dumps({"edited": content.was_edited}),
        ))

        self._repo.update(content)
        self._repo.commit()

        return content