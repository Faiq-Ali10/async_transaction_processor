from celery import Celery

from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "transaction_processor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
)
