import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Category
from app.models.knowledge_article import KnowledgeArticle


class KnowledgeArticleRepository:
    """Database access for knowledge-base articles."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, article: KnowledgeArticle) -> KnowledgeArticle:
        self._db.add(article)
        self._db.flush()
        return article

    def get(
        self,
        article_id: uuid.UUID,
    ) -> KnowledgeArticle | None:
        stmt = select(KnowledgeArticle).where(
            KnowledgeArticle.article_id == article_id
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def list_by_category(
        self,
        category: Category,
    ) -> list[KnowledgeArticle]:
        stmt = (
            select(KnowledgeArticle)
            .where(KnowledgeArticle.category == category)
            .order_by(KnowledgeArticle.created_at.desc())
        )

        return list(self._db.execute(stmt).scalars().all())

    def commit(self) -> None:
        self._db.commit()