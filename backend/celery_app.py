import sys
import os
sys.path.insert(0, '/app')

from celery import Celery
from config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "mawrid",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Import tasks so Celery discovers them
import tasks  # noqa: F401, E402
