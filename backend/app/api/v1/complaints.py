import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import (
    StaffUser,
    get_complaint_service,
    get_generated_content_service,
    get_prediction_service,
)
from app.core.exceptions import ValidationError
from app.models.enums import AnalysisStatus, Category, ComplaintStatus, Priority, Sentiment
from app.schemas.complaint import (
    AssignRequest,
    BulkFailure,
    BulkStatusResult,
    BulkStatusUpdate,
    CategoryOverride,
    ComplaintCreate,
    ComplaintCreated,
    ComplaintDetail,
    ComplaintSummary,
    HistoryEntry,
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

# Submitting a complaint is public: customers file them (FR-01, SRS 2.3).
# Every other route is for signed-in staff (FR-38).


@router.post("", response_model=ComplaintCreated, status_code=status.HTTP_201_CREATED)
def create_complaint(
    payload: ComplaintCreate,
    service: ComplaintService = Depends(get_complaint_service),
):
    return service.create(payload)


def _day_start(d: date | None) -> datetime | None:
    return datetime.combine(d, time.min, tzinfo=timezone.utc) if d else None


@router.get("", response_model=Paginated)
def list_complaints(
    user: StaffUser,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    status_filter: ComplaintStatus | None = Query(None, alias="status"),
    category: Category | None = None,
    priority: Priority | None = None,
    sentiment: Sentiment | None = None,
    analysis_status: AnalysisStatus | None = None,
    assigned: Literal["me", "none"] | None = Query(
        None, description="me = assigned to you, none = unassigned"),
    assigned_to: uuid.UUID | None = Query(None, description="a specific user"),
    date_from: date | None = Query(None, description="submitted on or after (UTC)"),
    date_to: date | None = Query(None, description="submitted on or before (UTC)"),
    sort: Literal["newest", "oldest", "priority"] = "newest",
    service: ComplaintService = Depends(get_complaint_service),
):
    """FR-26. Filterable, sortable complaint list."""
    if date_from and date_to and date_from > date_to:
        raise ValidationError("date_from must be on or before date_to")
    items, total = service.list(
        page=page, size=size, status=status_filter,
        category=category, priority=priority, sentiment=sentiment,
        analysis_status=analysis_status,
        assigned_to=user.user_id if assigned == "me" else assigned_to,
        unassigned=assigned == "none",
        submitted_from=_day_start(date_from),
        submitted_to=_day_start(date_to + timedelta(days=1)) if date_to else None,
        sort=sort,
    )
    return Paginated(
        items=[ComplaintSummary.model_validate(c) for c in items],
        page=page, size=size, total=total,
        pages=(total + size - 1) // size,
    )


# Declared before "/{complaint_id}" routes so "bulk-status" is never read as an id.
@router.patch("/bulk-status", response_model=BulkStatusResult)
def bulk_update_status(
    user: StaffUser,
    payload: BulkStatusUpdate,
    service: ComplaintService = Depends(get_complaint_service),
):
    """FR-29. Complaints that cannot make the move are listed in `failed`;
    the rest are still updated."""
    updated, failed = service.bulk_update_status(payload.complaint_ids, payload.status, user)
    return BulkStatusResult(
        updated=updated,
        failed=[BulkFailure(complaint_id=cid, reason=r) for cid, r in failed],
    )


@router.get("/{complaint_id}", response_model=ComplaintDetail)
def get_complaint(
    user: StaffUser,
    complaint_id: uuid.UUID,
    service: ComplaintService = Depends(get_complaint_service),
):
    return service.get(complaint_id)


@router.patch("/{complaint_id}", response_model=ComplaintDetail)
def update_status(
    user: StaffUser,
    complaint_id: uuid.UUID,
    payload: StatusUpdate,
    service: ComplaintService = Depends(get_complaint_service),
):
    """FR-28. Only moves allowed by the state machine; see allowed_next_statuses."""
    return service.update_status(complaint_id, payload.status, user)


@router.patch("/{complaint_id}/category", response_model=ComplaintDetail)
def override_category(
    user: StaffUser,
    complaint_id: uuid.UUID,
    payload: CategoryOverride,
    service: ComplaintService = Depends(get_complaint_service),
):
    """FR-10. Correct the predicted category. Priority is recalculated and the
    correction is saved as training feedback."""
    return service.override_category(complaint_id, payload.category, user)


@router.patch("/{complaint_id}/assignee", response_model=ComplaintDetail)
def assign_complaint(
    user: StaffUser,
    complaint_id: uuid.UUID,
    payload: AssignRequest,
    service: ComplaintService = Depends(get_complaint_service),
):
    """Assign to a staff member, or send user_id null to unassign."""
    return service.assign(complaint_id, payload.user_id, user)


@router.get("/{complaint_id}/history", response_model=list[HistoryEntry])
def complaint_history(
    user: StaffUser,
    complaint_id: uuid.UUID,
    service: ComplaintService = Depends(get_complaint_service),
):
    """FR-30. Audit trail for one complaint, newest first."""
    return service.history(complaint_id)


@router.get(
    "/{complaint_id}/prediction",
    response_model=PredictionOut,
)
def get_prediction(
    user: StaffUser,
    complaint_id: uuid.UUID,
    service: PredictionService = Depends(get_prediction_service),
):
    return service.get_by_complaint(complaint_id)


@router.post(
    "/{complaint_id}/generated-content",
    response_model=GeneratedContentOut,
)
def generate_content(
    user: StaffUser,
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
    user: StaffUser,
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
    user: StaffUser,
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
    user: StaffUser,
    complaint_id: uuid.UUID,
    payload: GeneratedContentApprove,
    service: GeneratedContentService = Depends(
        get_generated_content_service
    ),
):
    return service.approve(
        complaint_id=complaint_id,
        final_response=payload.final_response,
        approved_by=user.user_id,
    )