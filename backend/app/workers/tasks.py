import logging
import uuid
from app.services.generated_content_service import GeneratedContentService
from app.core.database import session_scope
from app.core.config import settings
from app.core.exceptions import LLMRateLimitedError, LLMUnavailableError, NotFoundError
from app.core.logging import log_event
from app.models.enums import AnalysisStatus
from app.models.prediction import Prediction
from app.repositories.complaint_repo import ComplaintRepository
from app.services.classifier_service import classifier, sentiment
from app.services.priority_service import PriorityService
from app.services.settings_service import SettingsService
from app.workers.celery_app import celery_app
from datetime import UTC, datetime, timedelta

from celery.signals import worker_process_init, worker_ready


@worker_process_init.connect
def _warm_models(**_kwargs) -> None:
    """Load models when a worker process starts, not inside the first task.
    Loading takes 10-30s, which would otherwise blow analyse_complaint's
    45s soft time limit."""
    classifier.warm()
    sentiment.warm()

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=2)


@worker_ready.connect
def _requeue_stale(**_kwargs) -> None:
    """Recover complaints whose analysis task was never run.

    That happens if Redis was down when the complaint was submitted, or lost
    its queue on a restart. Re-queuing is safe: analyse_complaint skips any
    complaint that already has a prediction. Only the local ML stage is
    re-queued, never the LLM, so a restart cannot spend LLM quota.
    """
    try:
        requeue_stale_analyses()
    except Exception:  # noqa: BLE001 - recovery must never stop the worker
        logger.exception("could not re-queue stale complaints")


def requeue_stale_analyses(now: datetime | None = None) -> list[str]:
    cutoff = (now or datetime.now(UTC)) - STALE_AFTER
    with session_scope() as db:
        ids = ComplaintRepository(db).stale_analysis_ids(cutoff)
    for cid in ids:
        analyse_complaint.delay(str(cid))
    if ids:
        log_event(logger, "requeued_stale_analyses", count=len(ids))
    return [str(c) for c in ids]


@celery_app.task(
    name="tasks.analyse_complaint",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
    time_limit=60,
    soft_time_limit=45,
)
def analyse_complaint(self, complaint_id: str) -> None:
    """Run ML analysis and enqueue the independent LLM stage."""

    cid = uuid.UUID(complaint_id)

    analysis_succeeded = False
    failure: Exception | None = None

    with session_scope() as db:
        repo = ComplaintRepository(db)
        complaint = repo.get(cid)

        if complaint is None:
            logger.warning(
                "complaint %s vanished before analysis",
                complaint_id,
            )
            return
        if complaint.prediction is not None:
            logger.info(
                "complaint %s already has a prediction; "
                "skipping duplicate delivery",
                complaint_id,
            )
            complaint.analysis_status = AnalysisStatus.COMPLETED
            return
        complaint.analysis_status = AnalysisStatus.PROCESSING
        db.flush()

        try:
            cls = classifier.predict(complaint.redacted_text)
            snt = sentiment.predict(complaint.redacted_text)

            repeat_count = repo.count_prior_complaints(
                complaint.customer_ref
            )

            # FR-17: weights a manager set in the dashboard, else the .env defaults.
            pri = PriorityService(SettingsService(db).priority_weights()).compute(
                text=complaint.redacted_text,
                category=cls.category,
                sentiment_label=snt.label,
                sentiment_score=snt.score,
                repeat_count=max(repeat_count, 0),
            )

            repo.add_prediction(
                Prediction(
                    complaint_id=cid,
                    category=cls.category,
                    category_confidence=cls.confidence,
                    sentiment_label=snt.label,
                    sentiment_score=round(snt.score, 3),
                    priority_score=pri.score,
                    priority_bucket=pri.bucket,
                    priority_breakdown=pri.breakdown,
                    needs_review=cls.needs_review,
                    model_version=cls.model_version,
                    inference_ms=cls.inference_ms,
                )
            )

            complaint.analysis_status = AnalysisStatus.COMPLETED
            analysis_succeeded = True

            log_event(
                logger,
                "analysis_complete",
                complaint_id=complaint_id,
                stage="ml_inference",
                category=cls.category,
                confidence=cls.confidence,
                priority=pri.bucket,
                duration_ms=cls.inference_ms,
            )

        except Exception as exc:
            failure = exc
            final_attempt = self.request.retries >= self.max_retries
            logger.exception(
                "analysis failed for %s (attempt %d)",
                complaint_id, self.request.retries + 1,
            )
            # Undo anything half-written (e.g. a prediction), then record the
            # status in this same transaction so it is actually saved:
            # "pending" while retries remain, "failed" after the last one.
            # The complaint itself is never lost (NFR-09).
            db.rollback()
            complaint = repo.get(cid)
            complaint.analysis_status = (
                AnalysisStatus.FAILED if final_attempt else AnalysisStatus.PENDING)

    if failure is not None:
        # Outside the transaction, so the status above has been committed.
        raise self.retry(exc=failure) from failure

    # Transaction is committed before LLM task is queued.
    if analysis_succeeded:
        generate_complaint_content.delay(complaint_id)


@celery_app.task(
    name="tasks.generate_complaint_content",
    bind=True,
    max_retries=3,
    acks_late=True,
    rate_limit=settings.LLM_RATE_LIMIT,
    time_limit=120,
    soft_time_limit=100,
)
def generate_complaint_content(
    self,
    complaint_id: str,
) -> None:
    """The LLM stage. Independent of ML analysis: if the LLM is down, the
    complaint is still classified, prioritised and visible (NFR-07).

    A failed LLM call is retried with exponential backoff (NFR-08). Only the
    last attempt falls back to the template response (FR-25), so a brief
    provider outage does not leave a complaint with a template.
    """
    cid = uuid.UUID(complaint_id)
    final_attempt = self.request.retries >= self.max_retries

    try:
        with session_scope() as db:
            service = GeneratedContentService(db)
            if service_has_content(service, cid):
                # Redelivered task, or an agent already generated it.
                return
            # With no LLM configured there is nothing to retry: fall back now.
            content = service.generate(
                cid, allow_fallback=final_attempt or not service.llm_available)
            log_event(
                logger,
                "llm_generation_complete",
                complaint_id=complaint_id,
                stage="llm_generation",
                fallback=content.is_fallback,
                attempt=self.request.retries + 1,
            )
    except LLMRateLimitedError as exc:
        if exc.daily:
            # Retrying cannot help until the quota resets: save the template now
            # instead of spending three more requests on certain failures.
            logger.warning("LLM daily quota used up; template for %s", complaint_id)
            with session_scope() as db:
                GeneratedContentService(db).generate(cid, allow_fallback=True)
            return
        logger.warning("LLM rate limited for %s (attempt %d), waiting %ss",
                       complaint_id, self.request.retries + 1, exc.retry_after)
        countdown = max(exc.retry_after, 2 ** (self.request.retries + 1) * 5)
        raise self.retry(exc=exc, countdown=countdown) from exc
    except LLMUnavailableError as exc:
        logger.warning("LLM unavailable for %s (attempt %d): %s",
                       complaint_id, self.request.retries + 1, exc.message)
        raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1) * 5) from exc


def service_has_content(service: GeneratedContentService, complaint_id: uuid.UUID) -> bool:
    try:
        service.get(complaint_id)
    except NotFoundError:
        return False
    return True
