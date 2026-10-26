"""Analytics for managers (FR-31 to FR-36) and the feedback export (FR-42).

The statistics that decide something (emerging issues) are pure functions of
plain numbers, so they are unit-tested without a database.
"""

import csv
import io
import json
import logging
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import Category, Priority, Sentiment
from app.repositories.analytics_repo import AnalyticsRepository
from app.services.classifier_service import CLASSIFIER_DIR_NAME

logger = logging.getLogger(__name__)

CATEGORIES = [c.value for c in Category]

# FR-34: a category is emerging when its last-7-day volume is more than
# EMERGING_SIGMA standard deviations above the mean 7-day volume of the 30 days
# before. EMERGING_MIN_COUNT stops tiny numbers (0 -> 2) being flagged.
EMERGING_SIGMA = 2.0
EMERGING_MIN_COUNT = 5
CURRENT_DAYS = 7
BASELINE_DAYS = 30


def day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=UTC)


@dataclass
class EmergingIssue:
    category: str
    last_7_days: int
    baseline_mean: float
    baseline_sd: float
    threshold: float
    ratio: float | None  # last_7_days / baseline_mean


def detect_emerging(
    daily: dict[str, list[int]],
    sigma: float = EMERGING_SIGMA,
    min_count: int = EMERGING_MIN_COUNT,
) -> list[EmergingIssue]:
    """FR-34.

    daily[category] holds BASELINE_DAYS + CURRENT_DAYS daily counts, oldest
    first; the last CURRENT_DAYS are "this week". The baseline is every 7-day
    window inside the previous 30 days (24 overlapping windows), so this week
    is compared with weeks, not with single days.
    """
    issues = []
    for category, counts in daily.items():
        if len(counts) != BASELINE_DAYS + CURRENT_DAYS:
            raise ValueError(f"expected {BASELINE_DAYS + CURRENT_DAYS} days for {category}")
        baseline = counts[:BASELINE_DAYS]
        current = sum(counts[BASELINE_DAYS:])
        windows = [sum(baseline[i:i + CURRENT_DAYS])
                   for i in range(BASELINE_DAYS - CURRENT_DAYS + 1)]
        mean = statistics.fmean(windows)
        sd = statistics.pstdev(windows)
        threshold = mean + sigma * sd
        if current >= min_count and current > threshold:
            issues.append(EmergingIssue(
                category=category,
                last_7_days=current,
                baseline_mean=round(mean, 1),
                baseline_sd=round(sd, 1),
                threshold=round(threshold, 1),
                ratio=round(current / mean, 1) if mean else None,
            ))
    return sorted(issues, key=lambda i: i.last_7_days - i.threshold, reverse=True)


def fill_series(rows, start: date, end: date) -> list[dict]:
    """[(day, category, n)] -> one dict per day with every category, zeros filled."""
    by_day: dict[date, dict[str, int]] = {}
    for d, category, n in rows:
        by_day.setdefault(d, {})[category] = n
    out = []
    d = start
    while d < end:
        counts = by_day.get(d, {})
        out.append({"date": d.isoformat(), **{c: counts.get(c, 0) for c in CATEGORIES}})
        d += timedelta(days=1)
    return out


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self._repo = AnalyticsRepository(db)

    def overview(self, start: date, end: date) -> dict:
        """end is exclusive: the day after the last day shown."""
        s, e = day_start(start), day_start(end)
        sentiment = self._repo.sentiment_counts(s, e)
        priority = self._repo.priority_counts(s, e)
        return {
            "range": {"from": start.isoformat(), "to": (end - timedelta(days=1)).isoformat()},
            "kpis": self._repo.kpis(s, e),
            "volume": fill_series(self._repo.daily_counts_by_category(s, e), start, end),
            "sentiment": {label.value: sentiment.get(label.value, 0) for label in Sentiment},
            "priority": {p.value: priority.get(p.value, 0) for p in Priority},
            "emerging": [asdict(i) for i in self.emerging()],
        }

    def emerging(self, today: date | None = None) -> list[EmergingIssue]:
        """Always relative to today, whatever date range the dashboard shows."""
        end = (today or datetime.now(UTC).date()) + timedelta(days=1)
        start = end - timedelta(days=BASELINE_DAYS + CURRENT_DAYS)
        rows = self._repo.daily_counts_by_category(day_start(start), day_start(end))
        series = fill_series(rows, start, end)
        return detect_emerging({c: [day[c] for day in series] for c in CATEGORIES})

    # ---- model health (FR-35, FR-36) ---------------------------------------------

    def model_health(self, start: date, end: date) -> dict:
        s, e = day_start(start), day_start(end)
        threshold = settings.CONFIDENCE_THRESHOLD
        live = self._repo.prediction_stats(s, e, threshold)
        total = live["total"]

        histogram = [
            {"from": round(b / 20, 2), "to": round((b + 1) / 20, 2),
             "count": live["histogram"].get(b, (0, 0))[0],
             "corrected": live["histogram"].get(b, (0, 0))[1]}
            for b in range(10, 20)
        ]
        # Everything under 0.50 is folded into the first band shown.
        low = sum(n for b, (n, _) in live["histogram"].items() if b < 10)
        low_corrected = sum(w for b, (_, w) in live["histogram"].items() if b < 10)
        histogram[0]["count"] += low
        histogram[0]["corrected"] += low_corrected
        histogram[0]["from"] = 0.0

        return {
            "threshold": threshold,
            "live": {
                "predictions": total,
                "below_threshold": live["below_threshold"],
                "below_threshold_rate": round(live["below_threshold"] / total, 3) if total else None,
                "overridden": live["overridden"],
                "override_rate": round(live["overridden"] / total, 3) if total else None,
                "avg_confidence": live["avg_confidence"],
                "avg_inference_ms": live["avg_inference_ms"],
                "confidence_histogram": histogram,
                "corrections": [{"predicted": p, "corrected_to": c, "count": n}
                                for p, c, n in sorted(live["corrections"], key=lambda r: -r[2])],
                "per_category": [{"category": c, "predicted": n, "corrected": w,
                                  "corrected_rate": round(w / n, 3) if n else None}
                                 for c, n, w in sorted(live["per_category"])],
                "model_versions": [{"version": v, "count": n} for v, n in live["versions"]],
            },
            "offline": self.offline_evaluation(),
            "llm": self._repo.llm_stats(s, e),
        }

    @staticmethod
    def offline_evaluation() -> dict | None:
        """The held-out test results saved next to the model (metrics.json from
        training, evaluation.json from ml/src/evaluate_model.py). None if the
        model folder is not mounted or has neither file."""
        model_dir = settings.MODEL_DIR / CLASSIFIER_DIR_NAME
        result: dict = {"model": CLASSIFIER_DIR_NAME}
        for name in ("metrics", "evaluation"):
            path = model_dir / f"{name}.json"
            try:
                result[name] = json.loads(path.read_text()) if path.exists() else None
            except (OSError, ValueError):
                logger.warning("could not read %s", path)
                result[name] = None
        if result["metrics"] is None and result["evaluation"] is None:
            return None
        return result

    # ---- FR-42 ------------------------------------------------------------------------

    def feedback_csv(self, start: date | None, end: date | None) -> str:
        """Agent corrections as training data. The text is the redacted
        complaint, so the file holds no customer emails, phones or account
        numbers."""
        rows = self._repo.feedback_rows(
            day_start(start) if start else None, day_start(end) if end else None)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["feedback_id", "complaint_id", "text", "field", "predicted",
                         "corrected", "model_version", "corrected_at"])
        for fb, text in rows:
            writer.writerow([fb.feedback_id, fb.complaint_id, text, fb.field_corrected,
                             fb.original_value, fb.corrected_value, fb.model_version,
                             fb.created_at.isoformat()])
        return buf.getvalue()
