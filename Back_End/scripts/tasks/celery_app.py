"""Celery application for async objective generation."""

from __future__ import annotations

from celery import Celery

from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "pms_generation",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["tasks.generation_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
)
