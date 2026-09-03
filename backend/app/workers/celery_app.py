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
    task_routes={"tasks.analyse_complaint": {"queue": "analysis"}},
)

celery_app.autodiscover_tasks(["app.workers"])

import app.workers.tasks  # noqa: E402,F401
