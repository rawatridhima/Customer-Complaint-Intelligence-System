import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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

    def update(self, content: GeneratedContent) -> GeneratedContent:
        self._db.add(content)
        self._db.flush()
        return content

    def commit(self) -> None:
        self._db.commit()