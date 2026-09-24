import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prediction import Prediction


class PredictionRepository:
    """Database access for complaint predictions."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, prediction: Prediction) -> Prediction:
        self._db.add(prediction)
        self._db.flush()
        return prediction

    def get_by_complaint(
        self,
        complaint_id: uuid.UUID,
    ) -> Prediction | None:
        stmt = select(Prediction).where(
            Prediction.complaint_id == complaint_id
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def get(
        self,
        prediction_id: uuid.UUID,
    ) -> Prediction | None:
        stmt = select(Prediction).where(
            Prediction.prediction_id == prediction_id
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def commit(self) -> None:
        self._db.commit()