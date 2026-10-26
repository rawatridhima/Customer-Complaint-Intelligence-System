from celery import Celery

from app.core.config import settings

# No result backend: tasks write their results to Postgres, and nothing ever
# reads a Celery result. Without one, a Redis outage cannot stall the API on
# result-backend reconnects.
celery_app = Celery("cis", broker=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_ignore_result=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 120},
    # Submitting a complaint must answer fast even if Redis is down (FR-04):
    # try briefly, then give up. The complaint is already saved, and the
    # worker re-queues anything left pending when it starts (NFR-09).
    broker_connection_timeout=2,
    broker_connection_retry_on_startup=True,
    task_publish_retry_policy={
        "max_retries": 1, "interval_start": 0, "interval_step": 0.2, "interval_max": 0.2,
    },
    # Two queues so a slow LLM provider never delays classification. The
    # worker in docker-compose consumes both; they can be scaled separately.
    task_routes={
        "tasks.analyse_complaint": {"queue": "analysis"},
        "tasks.generate_complaint_content": {"queue": "llm"},
    },
)

celery_app.autodiscover_tasks(["app.workers"])

import app.workers.tasks  # noqa: E402,F401
