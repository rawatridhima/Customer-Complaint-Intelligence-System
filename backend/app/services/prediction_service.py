import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.prediction import Prediction
from app.repositories.prediction_repo import PredictionRepository


class PredictionService:
    def __init__(self, db: Session) -> None:
        self._repo = PredictionRepository(db)

    def get_by_complaint(self, complaint_id: uuid.UUID) -> Prediction:
        prediction = self._repo.get_by_complaint(complaint_id)

        if prediction is None:
            raise NotFoundError(
                f"Prediction for complaint {complaint_id} not found"
            )

        return prediction

    def get(self, prediction_id: uuid.UUID) -> Prediction:
        prediction = self._repo.get(prediction_id)

        if prediction is None:
            raise NotFoundError(
                f"Prediction {prediction_id} not found"
            )

        return prediction