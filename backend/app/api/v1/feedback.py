import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services.feedback_service import FeedbackService

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"],
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
    service: FeedbackService = Depends(get_feedback_service),
):
    return service.create(
        complaint_id=payload.complaint_id,
        field_corrected=payload.field_corrected,
        original_value=payload.original_value,
        corrected_value=payload.corrected_value,
        corrected_by=payload.corrected_by,
        model_version=payload.model_version,
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