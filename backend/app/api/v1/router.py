from fastapi import APIRouter

from app.api.v1 import complaints

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(complaints.router)
