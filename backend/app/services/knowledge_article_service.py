import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.enums import Category
from app.models.knowledge_article import KnowledgeArticle
from app.repositories.knowledge_article_repo import KnowledgeArticleRepository


class KnowledgeArticleService:
    """Business logic for knowledge-base articles."""

    def __init__(self, db: Session) -> None:
        self._repo = KnowledgeArticleRepository(db)

    def create(
        self,
        title: str,
        body: str,
        category: Category,
        embedding: list[float] | None = None,
    ) -> KnowledgeArticle:
        article = KnowledgeArticle(
            title=title,
            body=body,
            category=category,
            embedding=embedding,
        )

        self._repo.add(article)
        self._repo.commit()

        return article

    def get(self, article_id: uuid.UUID) -> KnowledgeArticle:
        article = self._repo.get(article_id)

        if article is None:
            raise NotFoundError(
                f"Knowledge article {article_id} not found"
            )

        return article

    def list_by_category(
        self,
        category: Category,
    ) -> list[KnowledgeArticle]:
        return self._repo.list_by_category(category)

    def similarity_search(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[KnowledgeArticle]:
        return self._repo.similarity_search(
            query_embedding=query_embedding,
            limit=limit,
        )