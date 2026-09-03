import logging
import uuid

from app.core.database import session_scope
from app.core.logging import log_event
from app.models.enums import AnalysisStatus
from app.models.prediction import Prediction
from app.repositories.complaint_repo import ComplaintRepository
from app.services.classifier_service import classifier, sentiment
from app.services.priority_service import PriorityService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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
    """ML stage only in this skeleton. The LLM stage is added in week 7.

    Stage isolation matters: if the LLM stage is added and fails, the
    complaint must still be fully triageable from this stage alone (NFR-07).
    """
    cid = uuid.UUID(complaint_id)

    with session_scope() as db:
        repo = ComplaintRepository(db)
        complaint = repo.get(cid)
        if complaint is None:
            logger.warning("complaint %s vanished before analysis", complaint_id)
            return

        complaint.analysis_status = AnalysisStatus.PROCESSING
        db.flush()

        try:
            cls = classifier.predict(complaint.redacted_text)
            snt = sentiment.predict(complaint.redacted_text)
            repeat_count = repo.count_prior_complaints(complaint.customer_ref)

            pri = PriorityService().compute(
                text=complaint.redacted_text,
                category=cls.category,
                sentiment_label=snt.label,
                sentiment_score=snt.score,
                repeat_count=max(repeat_count, 0),
            )

            repo.add_prediction(Prediction(
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
            ))

            complaint.analysis_status = AnalysisStatus.COMPLETED

            log_event(
                logger, "analysis_complete",
                complaint_id=complaint_id,
                stage="ml_inference",
                category=cls.category,
                confidence=cls.confidence,
                priority=pri.bucket,
                duration_ms=cls.inference_ms,
            )

        except Exception as exc:
            complaint.analysis_status = AnalysisStatus.FAILED
            logger.exception("analysis failed for %s", complaint_id)
            raise self.retry(exc=exc) from exc
