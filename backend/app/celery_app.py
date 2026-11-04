from celery import Celery
from app.config import settings

celery_app = Celery(
    "bidpivot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,
    task_soft_time_limit=1740,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=24 * 60 * 60,
)

celery_app.autodiscover_tasks(["app.tasks"])
