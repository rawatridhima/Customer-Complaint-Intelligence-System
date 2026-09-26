import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db
from app.models.enums import Category
from app.schemas.knowledge_article import (
    KnowledgeArticleCreate,
    KnowledgeArticleOut,
    KnowledgeArticleSearch,
)
from app.services.knowledge_article_service import KnowledgeArticleService

router = APIRouter(
    prefix="/knowledge-articles",
    tags=["knowledge-articles"],
)


def get_knowledge_article_service(
    db: Session = Depends(get_db),
) -> KnowledgeArticleService:
    return KnowledgeArticleService(db)


@router.post(
    "",
    response_model=KnowledgeArticleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_article(
    payload: KnowledgeArticleCreate,
    service: KnowledgeArticleService = Depends(
        get_knowledge_article_service
    ),
):
    return service.create(
        title=payload.title,
        body=payload.body,
        category=payload.category,
        embedding=payload.embedding,
    )


@router.get(
    "/{article_id}",
    response_model=KnowledgeArticleOut,
)
def get_article(
    article_id: uuid.UUID,
    service: KnowledgeArticleService = Depends(
        get_knowledge_article_service
    ),
):
    return service.get(article_id)


@router.get(
    "",
    response_model=list[KnowledgeArticleOut],
)
def list_articles(
    category: Category = Query(...),
    service: KnowledgeArticleService = Depends(
        get_knowledge_article_service
    ),
):
    return service.list_by_category(category)


@router.post(
    "/search",
    response_model=list[KnowledgeArticleOut],
)
def search_articles(
    payload: KnowledgeArticleSearch,
    service: KnowledgeArticleService = Depends(
        get_knowledge_article_service
    ),
):
    return service.similarity_search(
        query_embedding=payload.embedding,
        limit=payload.limit,
    )