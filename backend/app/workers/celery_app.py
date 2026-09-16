"""
DevLens AI — Celery Application
Configures the Celery app with Redis broker and result backend.
"""
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "devlens",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,                    # Ack only after task completes (safe retry on crash)
    worker_prefetch_multiplier=1,           # One task at a time per worker slot (fair scheduling)
    task_soft_time_limit=1200,              # 20 min soft limit per task
    task_time_limit=1500,                   # 25 min hard limit
)
