import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import (
    get_complaint_service,
    get_generated_content_service,
    get_prediction_service,
)
from app.models.enums import AnalysisStatus, Category, ComplaintStatus, Priority
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintCreated,
    ComplaintDetail,
    ComplaintSummary,
    Paginated,
    PredictionOut,
    StatusUpdate,
)
from app.schemas.generated_content import (
    GeneratedContentApprove,
    GeneratedContentOut,
    GeneratedContentUpdate,
)
from app.services.generated_content_service import GeneratedContentService
from app.services.complaint_service import ComplaintService
from app.services.prediction_service import PredictionService

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


@router.get(
    "/{complaint_id}/prediction",
    response_model=PredictionOut,
)
def get_prediction(
    complaint_id: uuid.UUID,
    service: PredictionService = Depends(get_prediction_service),
):
    return service.get_by_complaint(complaint_id)


@router.post(
    "/{complaint_id}/generated-content",
    response_model=GeneratedContentOut,
)
def generate_content(
    complaint_id: uuid.UUID,
    service: GeneratedContentService = Depends(
        get_generated_content_service
    ),
):
    return service.generate(complaint_id)


@router.get(
    "/{complaint_id}/generated-content",
    response_model=GeneratedContentOut,
)
def get_generated_content(
    complaint_id: uuid.UUID,
    service: GeneratedContentService = Depends(
        get_generated_content_service
    ),
):
    return service.get(complaint_id)

@router.patch(
    "/{complaint_id}/generated-content",
    response_model=GeneratedContentOut,
)
def update_generated_content(
    complaint_id: uuid.UUID,
    payload: GeneratedContentUpdate,
    service: GeneratedContentService = Depends(
        get_generated_content_service
    ),
):
    return service.update_draft(
        complaint_id=complaint_id,
        draft_response=payload.draft_response,
    )


@router.post(
    "/{complaint_id}/generated-content/approve",
    response_model=GeneratedContentOut,
)
def approve_generated_content(
    complaint_id: uuid.UUID,
    payload: GeneratedContentApprove,
    service: GeneratedContentService = Depends(
        get_generated_content_service
    ),
):
    return service.approve(
        complaint_id=complaint_id,
        final_response=payload.final_response,
    )