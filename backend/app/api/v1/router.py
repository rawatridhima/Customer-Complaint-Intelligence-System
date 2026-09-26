from fastapi import APIRouter

from app.api.v1 import (
    audit_logs,
    complaints,
    feedback,
    knowledge_articles,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(complaints.router)
api_router.include_router(knowledge_articles.router)
api_router.include_router(feedback.router)
api_router.include_router(audit_logs.router)