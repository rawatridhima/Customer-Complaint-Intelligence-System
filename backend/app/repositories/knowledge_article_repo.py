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

    def list_all(self) -> list[KnowledgeArticle]:
        stmt = select(KnowledgeArticle).order_by(KnowledgeArticle.created_at)
        return list(self._db.execute(stmt).scalars().all())

    def get_many(self, article_ids: list[uuid.UUID]) -> list[KnowledgeArticle]:
        if not article_ids:
            return []
        stmt = select(KnowledgeArticle).where(KnowledgeArticle.article_id.in_(article_ids))
        found = {a.article_id: a for a in self._db.execute(stmt).scalars().all()}
        return [found[i] for i in article_ids if i in found]  # keep citation order

    def get_by_title(self, title: str) -> KnowledgeArticle | None:
        stmt = select(KnowledgeArticle).where(KnowledgeArticle.title == title)
        return self._db.execute(stmt).scalar_one_or_none()

    def similarity_search(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[KnowledgeArticle]:
        stmt = (
            select(KnowledgeArticle)
            .where(KnowledgeArticle.embedding.is_not(None))
            .order_by(
                KnowledgeArticle.embedding.cosine_distance(
                    query_embedding
                )
            )
            .limit(limit)
        )

        return list(self._db.execute(stmt).scalars().all())

    def commit(self) -> None:
        self._db.commit()