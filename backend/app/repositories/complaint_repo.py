import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.complaint import Complaint
from app.models.enums import AnalysisStatus, Category, ComplaintStatus, Priority, Sentiment
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
        sentiment: Sentiment | None = None,
        analysis_status: AnalysisStatus | None = None,
        assigned_to: uuid.UUID | None = None,
        unassigned: bool = False,
        submitted_from: datetime | None = None,
        submitted_to: datetime | None = None,
        sort: str = "newest",
    ) -> tuple[list[Complaint], int]:
        """FR-26. Filters combine with AND. sort: newest, oldest or priority."""
        conditions = []
        if status is not None:
            conditions.append(Complaint.status == status)
        if analysis_status is not None:
            conditions.append(Complaint.analysis_status == analysis_status)
        if assigned_to is not None:
            conditions.append(Complaint.assigned_to == assigned_to)
        if unassigned:
            conditions.append(Complaint.assigned_to.is_(None))
        if submitted_from is not None:
            conditions.append(Complaint.submitted_at >= submitted_from)
        if submitted_to is not None:
            conditions.append(Complaint.submitted_at < submitted_to)

        prediction_filters = []
        if category is not None:
            prediction_filters.append(Prediction.category == category)
        if priority is not None:
            prediction_filters.append(Prediction.priority_bucket == priority)
        if sentiment is not None:
            prediction_filters.append(Prediction.sentiment_label == sentiment)

        stmt = select(Complaint).options(selectinload(Complaint.prediction))
        count_stmt = select(func.count()).select_from(Complaint)

        if prediction_filters:
            # Inner join: a complaint still being analysed has no prediction,
            # so it cannot match a prediction filter.
            stmt = stmt.join(Prediction).where(*prediction_filters)
            count_stmt = count_stmt.join(Prediction).where(*prediction_filters)
        elif sort == "priority":
            stmt = stmt.outerjoin(Prediction)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        if sort == "priority":
            order = (Prediction.priority_score.desc().nulls_last(),
                     Complaint.submitted_at.desc())
        elif sort == "oldest":
            order = (Complaint.submitted_at.asc(),)
        else:
            order = (Complaint.submitted_at.desc(),)

        total = self._db.execute(count_stmt).scalar_one()
        stmt = stmt.order_by(*order).offset((page - 1) * size).limit(size)
        items = list(self._db.execute(stmt).scalars().all())
        return items, total

    def get_many(self, complaint_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Complaint]:
        stmt = (
            select(Complaint)
            .options(selectinload(Complaint.prediction))
            .where(Complaint.complaint_id.in_(complaint_ids))
        )
        return {c.complaint_id: c for c in self._db.execute(stmt).scalars().all()}

    def add_prediction(self, prediction: Prediction) -> Prediction:
        self._db.add(prediction)
        self._db.flush()
        return prediction

    def commit(self) -> None:
        self._db.commit()
