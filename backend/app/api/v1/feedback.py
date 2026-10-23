import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from datetime import date, timedelta

from fastapi import Query
from fastapi.responses import Response

from app.api.v1.deps import STAFF, ManagerUser, StaffUser, require_role
from app.services.analytics_service import AnalyticsService
from app.core.database import get_db
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services.feedback_service import FeedbackService

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"],
    dependencies=[Depends(require_role(*STAFF))],
)


def get_feedback_service(
    db: Session = Depends(get_db),
) -> FeedbackService:
    return FeedbackService(db)


@router.post(
    "",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
def create_feedback(
    payload: FeedbackCreate,
    user: StaffUser,
    service: FeedbackService = Depends(get_feedback_service),
):
    return service.create(
        complaint_id=payload.complaint_id,
        field_corrected=payload.field_corrected,
        original_value=payload.original_value,
        corrected_value=payload.corrected_value,
        corrected_by=user.user_id,  # from the token, never the request body
        model_version=payload.model_version,
    )


# Declared before "/{feedback_id}" so "export.csv" is not read as an id.
@router.get("/export.csv", response_class=Response)
def export_feedback(
    user: ManagerUser,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None, description="inclusive"),
    db: Session = Depends(get_db),
):
    """FR-42. Every agent correction as a CSV training set: the redacted
    complaint text, what the model predicted, and what the agent corrected
    it to. Feed it to ml/src for retraining."""
    end = date_to + timedelta(days=1) if date_to else None
    body = AnalyticsService(db).feedback_csv(date_from, end)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="feedback.csv"'},
    )


@router.get(
    "/{feedback_id}",
    response_model=FeedbackOut,
)
def get_feedback(
    feedback_id: uuid.UUID,
    service: FeedbackService = Depends(get_feedback_service),
):
    return service.get(feedback_id)


@router.get(
    "/complaint/{complaint_id}",
    response_model=list[FeedbackOut],
)
def list_feedback_by_complaint(
    complaint_id: uuid.UUID,
    service: FeedbackService = Depends(get_feedback_service),
):
    return service.list_by_complaint(complaint_id)