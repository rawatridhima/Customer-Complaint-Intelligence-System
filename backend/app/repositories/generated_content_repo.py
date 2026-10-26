import uuid

from sqlalchemy import select

from app.models.enums import ComplaintStatus
from app.models.prediction import Prediction
from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.models.generated_content import GeneratedContent


class GeneratedContentRepository:
    """Database access for LLM-generated complaint content."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, content: GeneratedContent) -> GeneratedContent:
        self._db.add(content)
        self._db.flush()
        return content

    def get_by_complaint(
        self,
        complaint_id: uuid.UUID,
    ) -> GeneratedContent | None:
        stmt = select(GeneratedContent).where(
            GeneratedContent.complaint_id == complaint_id
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def find_cached(
        self,
        text_hash: str,
        prompt_version: str,
        tone: str,
        exclude_complaint_id: uuid.UUID,
    ) -> GeneratedContent | None:
        """FR-24. Content already generated for identical complaint text with
        the same prompt version and tone. Fallback templates are never reused."""
        stmt = (
            select(GeneratedContent)
            .join(Complaint, Complaint.complaint_id == GeneratedContent.complaint_id)
            .where(
                Complaint.text_hash == text_hash,
                Complaint.complaint_id != exclude_complaint_id,
                GeneratedContent.prompt_version == prompt_version,
                GeneratedContent.tone == tone,
                GeneratedContent.is_fallback.is_(False),
            )
            .order_by(GeneratedContent.created_at.desc())
            .limit(1)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def complaints_needing_content(self, limit: int, include_demo: bool = False) -> list:
        """Analysed, unresolved complaints with no AI reply yet, or only the
        fallback template, most urgent first."""
        stmt = (
            select(Complaint.complaint_id)
            .join(Prediction, Prediction.complaint_id == Complaint.complaint_id)
            .outerjoin(GeneratedContent, GeneratedContent.complaint_id == Complaint.complaint_id)
            .where(
                Complaint.status != ComplaintStatus.RESOLVED,
                (GeneratedContent.content_id.is_(None))
                | (GeneratedContent.is_fallback.is_(True) & GeneratedContent.approved_at.is_(None)),
            )
            .order_by(Prediction.priority_score.desc(), Complaint.submitted_at.desc())
            .limit(limit)
        )
        if not include_demo:
            stmt = stmt.where(Complaint.channel != "demo")
        return list(self._db.execute(stmt).scalars().all())

    def update(self, content: GeneratedContent) -> GeneratedContent:
        self._db.add(content)
        self._db.flush()
        return content

    def commit(self) -> None:
        self._db.commit()