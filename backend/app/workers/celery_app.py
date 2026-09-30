from celery import Celery

from app.core.config import settings

celery_app = Celery("cis", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 120},
    # Two queues so a slow LLM provider never delays classification. The
    # worker in docker-compose consumes both; they can be scaled separately.
    task_routes={
        "tasks.analyse_complaint": {"queue": "analysis"},
        "tasks.generate_complaint_content": {"queue": "llm"},
    },
)

celery_app.autodiscover_tasks(["app.workers"])

import app.workers.tasks  # noqa: E402,F401
