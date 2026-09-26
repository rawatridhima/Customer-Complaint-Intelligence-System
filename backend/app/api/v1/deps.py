from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.complaint_service import ComplaintService
from app.services.prediction_service import PredictionService
from app.services.generated_content_service import GeneratedContentService

def get_complaint_service(db: Session = Depends(get_db)) -> Iterator[ComplaintService]:
    yield ComplaintService(db)

def get_prediction_service(
    db: Session = Depends(get_db),
) -> Iterator[PredictionService]:
    yield PredictionService(db)

def get_generated_content_service(
    db: Session = Depends(get_db),
) -> Iterator[GeneratedContentService]:
    yield GeneratedContentService(db)