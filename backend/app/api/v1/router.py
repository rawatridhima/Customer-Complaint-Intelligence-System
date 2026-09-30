from fastapi import APIRouter

from app.api.v1 import (
    audit_logs,
    auth,
    complaints,
    feedback,
    knowledge_articles,
    users,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(complaints.router)
api_router.include_router(knowledge_articles.router)
api_router.include_router(feedback.router)
api_router.include_router(audit_logs.router)