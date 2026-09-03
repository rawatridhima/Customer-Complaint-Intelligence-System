import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_complaint_service
from app.models.enums import AnalysisStatus, Category, ComplaintStatus, Priority
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintCreated,
    ComplaintDetail,
    ComplaintSummary,
    Paginated,
    StatusUpdate,
)
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/complaints", tags=["complaints"])


@router.post("", response_model=ComplaintCreated, status_code=status.HTTP_201_CREATED)
def create_complaint(
    payload: ComplaintCreate,
    service: ComplaintService = Depends(get_complaint_service),
):
    return service.create(payload)


@router.get("", response_model=Paginated)
def list_complaints(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    status_filter: ComplaintStatus | None = Query(None, alias="status"),
    category: Category | None = None,
    priority: Priority | None = None,
    analysis_status: AnalysisStatus | None = None,
    service: ComplaintService = Depends(get_complaint_service),
):
    items, total = service.list(
        page=page, size=size, status=status_filter,
        category=category, priority=priority, analysis_status=analysis_status,
    )
    return Paginated(
        items=[ComplaintSummary.model_validate(c) for c in items],
        page=page, size=size, total=total,
        pages=(total + size - 1) // size,
    )


@router.get("/{complaint_id}", response_model=ComplaintDetail)
def get_complaint(
    complaint_id: uuid.UUID,
    service: ComplaintService = Depends(get_complaint_service),
):
    return service.get(complaint_id)


@router.patch("/{complaint_id}", response_model=ComplaintDetail)
def update_status(
    complaint_id: uuid.UUID,
    payload: StatusUpdate,
    service: ComplaintService = Depends(get_complaint_service),
):
    return service.update_status(complaint_id, payload.status)
