import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.complaint import Complaint
from app.models.enums import AnalysisStatus, Category, ComplaintStatus, Priority
from app.models.prediction import Prediction


class ComplaintRepository:
    """All complaint database access lives here. No business logic."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, complaint: Complaint) -> Complaint:
        self._db.add(complaint)
        self._db.flush()
        return complaint

    def get(self, complaint_id: uuid.UUID) -> Complaint | None:
        stmt = (
            select(Complaint)
            .options(selectinload(Complaint.prediction))
            .where(Complaint.complaint_id == complaint_id)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def find_duplicate(self, text_hash: str, customer_ref: str | None) -> Complaint | None:
        """FR-05. Exact hash match, same customer, within 24 hours."""
        if customer_ref is None:
            return None
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        stmt = (
            select(Complaint)
            .where(
                Complaint.text_hash == text_hash,
                Complaint.customer_ref == customer_ref,
                Complaint.submitted_at > cutoff,
            )
            .order_by(Complaint.submitted_at.asc())
            .limit(1)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def count_prior_complaints(self, customer_ref: str | None) -> int:
        if customer_ref is None:
            return 0
        stmt = select(func.count()).select_from(Complaint).where(
            Complaint.customer_ref == customer_ref
        )
        return self._db.execute(stmt).scalar_one() - 1

    def list(
        self,
        *,
        page: int = 1,
        size: int = 25,
        status: ComplaintStatus | None = None,
        category: Category | None = None,
        priority: Priority | None = None,
        analysis_status: AnalysisStatus | None = None,
    ) -> tuple[list[Complaint], int]:
        stmt = select(Complaint).options(selectinload(Complaint.prediction))
        count_stmt = select(func.count()).select_from(Complaint)

        if status is not None:
            stmt = stmt.where(Complaint.status == status)
            count_stmt = count_stmt.where(Complaint.status == status)
        if analysis_status is not None:
            stmt = stmt.where(Complaint.analysis_status == analysis_status)
            count_stmt = count_stmt.where(Complaint.analysis_status == analysis_status)
        if category is not None or priority is not None:
            stmt = stmt.join(Prediction)
            count_stmt = count_stmt.join(Prediction)
            if category is not None:
                stmt = stmt.where(Prediction.category == category)
                count_stmt = count_stmt.where(Prediction.category == category)
            if priority is not None:
                stmt = stmt.where(Prediction.priority_bucket == priority)
                count_stmt = count_stmt.where(Prediction.priority_bucket == priority)

        total = self._db.execute(count_stmt).scalar_one()
        stmt = (
            stmt.order_by(Complaint.submitted_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = list(self._db.execute(stmt).scalars().all())
        return items, total

    def add_prediction(self, prediction: Prediction) -> Prediction:
        self._db.add(prediction)
        self._db.flush()
        return prediction

    def commit(self) -> None:
        self._db.commit()
