"""Aggregate queries for the analytics dashboard (FR-31 to FR-36).

Every query counts complaints by submission time in [start, end), in UTC.
All the work is done by Postgres (GROUP BY), so the API never loads
individual complaints to count them (NFR-03).
"""

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.models.enums import ComplaintStatus, Priority
from app.models.feedback import Feedback
from app.models.generated_content import GeneratedContent
from app.models.prediction import Prediction


def _in_range(start: datetime, end: datetime):
    return (Complaint.submitted_at >= start, Complaint.submitted_at < end)


def _day(column):
    return cast(func.date_trunc("day", func.timezone("UTC", column)), Date)


class AnalyticsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ---- FR-31 -------------------------------------------------------------------

    def kpis(self, start: datetime, end: datetime) -> dict:
        resolved = Complaint.status == ComplaintStatus.RESOLVED
        resolution_seconds = func.extract("epoch", Complaint.resolved_at - Complaint.submitted_at)
        stmt = (
            select(
                func.count(Complaint.complaint_id),
                func.count(Complaint.complaint_id).filter(~resolved),
                func.count(Complaint.complaint_id).filter(resolved),
                func.avg(resolution_seconds).filter(resolved, Complaint.resolved_at.is_not(None)),
                func.count(Prediction.prediction_id).filter(Prediction.priority_bucket == Priority.P0),
                func.count(Prediction.prediction_id).filter(
                    Prediction.priority_bucket == Priority.P0, ~resolved),
                func.count(Complaint.complaint_id).filter(Complaint.status == ComplaintStatus.ESCALATED),
            )
            .select_from(Complaint)
            .outerjoin(Prediction)
            .where(*_in_range(start, end))
        )
        total, open_, resolved_n, avg_seconds, p0, p0_open, escalated = self._db.execute(stmt).one()
        return {
            "total": total,
            "open": open_,
            "resolved": resolved_n,
            "escalated": escalated,
            "avg_resolution_hours": round(float(avg_seconds) / 3600, 1) if avg_seconds else None,
            "p0": p0,
            "p0_open": p0_open,
        }

    # ---- FR-32, FR-34 -------------------------------------------------------------

    def daily_counts_by_category(self, start: datetime, end: datetime) -> Sequence[tuple[date, str, int]]:
        day = _day(Complaint.submitted_at)
        stmt = (
            select(day, Prediction.category, func.count())
            .select_from(Complaint)
            .join(Prediction)
            .where(*_in_range(start, end))
            .group_by(day, Prediction.category)
        )
        return [(d, c.value, n) for d, c, n in self._db.execute(stmt).all()]

    # ---- FR-33 ----------------------------------------------------------------------

    def sentiment_counts(self, start: datetime, end: datetime) -> dict[str, int]:
        stmt = (
            select(Prediction.sentiment_label, func.count())
            .select_from(Complaint)
            .join(Prediction)
            .where(*_in_range(start, end))
            .group_by(Prediction.sentiment_label)
        )
        return {label.value: n for label, n in self._db.execute(stmt).all()}

    def priority_counts(self, start: datetime, end: datetime) -> dict[str, int]:
        stmt = (
            select(Prediction.priority_bucket, func.count())
            .select_from(Complaint)
            .join(Prediction)
            .where(*_in_range(start, end))
            .group_by(Prediction.priority_bucket)
        )
        return {bucket.value: n for bucket, n in self._db.execute(stmt).all()}

    # ---- FR-35, FR-36: the model in production --------------------------------------

    def prediction_stats(self, start: datetime, end: datetime, threshold: float) -> dict:
        # The model's own answer: original_category is set only after an override.
        model_category = func.coalesce(Prediction.original_category, Prediction.category)
        stmt = (
            select(
                func.count(),
                func.count().filter(Prediction.category_confidence < threshold),
                func.count().filter(Prediction.original_category.is_not(None)),
                func.avg(Prediction.category_confidence),
                func.avg(Prediction.inference_ms),
            )
            .select_from(Complaint)
            .join(Prediction)
            .where(*_in_range(start, end))
        )
        total, below, overridden, avg_conf, avg_ms = self._db.execute(stmt).one()

        band = func.least(func.floor(Prediction.category_confidence * 20), 19)
        hist_stmt = (
            select(band, func.count(),
                   func.count().filter(Prediction.original_category.is_not(None)))
            .select_from(Complaint).join(Prediction)
            .where(*_in_range(start, end))
            .group_by(band)
        )
        histogram = {int(b): (n, wrong) for b, n, wrong in self._db.execute(hist_stmt).all()}

        corrections_stmt = (
            select(Prediction.original_category, Prediction.category, func.count())
            .select_from(Complaint).join(Prediction)
            .where(*_in_range(start, end), Prediction.original_category.is_not(None))
            .group_by(Prediction.original_category, Prediction.category)
        )
        corrections = [(o.value, c.value, n) for o, c, n in self._db.execute(corrections_stmt).all()]

        versions_stmt = (
            select(Prediction.model_version, func.count())
            .select_from(Complaint).join(Prediction)
            .where(*_in_range(start, end))
            .group_by(Prediction.model_version)
            .order_by(func.count().desc())
        )
        versions = [(v, n) for v, n in self._db.execute(versions_stmt).all()]

        per_category_stmt = (
            select(model_category, func.count(),
                   func.count().filter(Prediction.original_category.is_not(None)))
            .select_from(Complaint).join(Prediction)
            .where(*_in_range(start, end))
            .group_by(model_category)
        )
        per_category = [(c.value, n, wrong) for c, n, wrong in self._db.execute(per_category_stmt).all()]

        return {
            "total": total,
            "below_threshold": below,
            "overridden": overridden,
            "avg_confidence": round(float(avg_conf), 3) if avg_conf is not None else None,
            "avg_inference_ms": round(float(avg_ms)) if avg_ms is not None else None,
            "histogram": histogram,
            "corrections": corrections,
            "versions": versions,
            "per_category": per_category,
        }

    def llm_stats(self, start: datetime, end: datetime) -> dict:
        stmt = (
            select(
                func.count(),
                func.count().filter(GeneratedContent.is_fallback.is_(True)),
                func.count().filter(GeneratedContent.token_count == 0),
                func.avg(GeneratedContent.token_count).filter(GeneratedContent.token_count > 0),
                func.count().filter(GeneratedContent.approved_at.is_not(None)),
                func.count().filter(GeneratedContent.approved_at.is_not(None),
                                    GeneratedContent.was_edited.is_(True)),
            )
            .select_from(GeneratedContent)
            .join(Complaint, Complaint.complaint_id == GeneratedContent.complaint_id)
            .where(*_in_range(start, end))
        )
        total, fallback, cached, avg_tokens, approved, edited = self._db.execute(stmt).one()
        return {
            "generated": total,
            "fallback": fallback,
            "cached": cached,
            "avg_tokens": round(float(avg_tokens)) if avg_tokens is not None else None,
            "approved": approved,
            "approved_after_edit": edited,
        }

    # ---- FR-42 ------------------------------------------------------------------------

    def feedback_rows(self, start: datetime | None, end: datetime | None):
        """Corrections joined to the complaint text, oldest first."""
        stmt = (
            select(Feedback, Complaint.redacted_text)
            .join(Complaint, Complaint.complaint_id == Feedback.complaint_id)
            .order_by(Feedback.created_at)
        )
        if start is not None:
            stmt = stmt.where(Feedback.created_at >= start)
        if end is not None:
            stmt = stmt.where(Feedback.created_at < end)
        return self._db.execute(stmt).all()
