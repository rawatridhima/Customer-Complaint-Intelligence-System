from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import ManagerUser
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.services.analytics_service import AnalyticsService

# FR-31 to FR-36. Analytics are for managers and administrators (SRS 2.3).
router = APIRouter(prefix="/analytics", tags=["analytics"])

MAX_RANGE_DAYS = 366


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


def date_range(
    date_from: date | None = Query(None, description="first day (UTC); default 30 days ago"),
    date_to: date | None = Query(None, description="last day (UTC), inclusive; default today"),
) -> tuple[date, date]:
    """Returns (start, end) with end exclusive."""
    to = date_to or datetime.now(UTC).date()
    start = date_from or to - timedelta(days=29)
    if start > to:
        raise ValidationError("date_from must be on or before date_to")
    if (to - start).days >= MAX_RANGE_DAYS:
        raise ValidationError(f"The range can be at most {MAX_RANGE_DAYS} days")
    return start, to + timedelta(days=1)


@router.get("/overview")
def overview(
    user: ManagerUser,
    rng: tuple[date, date] = Depends(date_range),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """KPIs (FR-31), daily volume by category (FR-32), sentiment (FR-33),
    priority mix, and emerging issues (FR-34, always relative to today)."""
    return service.overview(*rng)


@router.get("/model-health")
def model_health(
    user: ManagerUser,
    rng: tuple[date, date] = Depends(date_range),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """FR-35, FR-36. Live behaviour of the classifier and LLM in the selected
    range, plus the held-out test results saved with the model."""
    return service.model_health(*rng)
