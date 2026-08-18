"""Job status storage for async objective generation."""

from __future__ import annotations

import json
import logging
import time
import uuid
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

from cache.redis_client import get_redis

_MEMORY_JOBS: dict[str, dict] = {}


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def _job_key(job_id: str) -> str:
    return f"pms:job:{job_id}"


def create_job(*, ttl: int) -> str:
    job_id = uuid.uuid4().hex
    payload = {
        "job_id": job_id,
        "status": JobStatus.QUEUED.value,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _save(job_id, payload, ttl)
    return job_id


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    r = get_redis()
    if r is not None:
        try:
            raw = r.get(_job_key(job_id))
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning(f"Job get failed: {exc}")
        return None
    return _MEMORY_JOBS.get(job_id)


def update_job(job_id: str, **fields) -> None:
    from config import JOB_RESULT_TTL

    job = get_job(job_id) or {"job_id": job_id}
    job.update(fields)
    job["updated_at"] = time.time()
    _save(job_id, job, JOB_RESULT_TTL)


def mark_running(job_id: str) -> None:
    update_job(job_id, status=JobStatus.RUNNING.value)


def mark_completed(job_id: str, result: dict) -> None:
    update_job(job_id, status=JobStatus.COMPLETED.value, result=result)


def mark_failed(job_id: str, error: str, *, detail: Any = None) -> None:
    payload: dict[str, Any] = {"status": JobStatus.FAILED.value, "error": error}
    if detail is not None:
        payload["detail"] = detail
    update_job(job_id, **payload)


def _save(job_id: str, payload: dict, ttl: int) -> None:
    r = get_redis()
    if r is not None:
        try:
            r.setex(_job_key(job_id), ttl, json.dumps(payload, ensure_ascii=False))
            return
        except Exception as exc:
            logger.warning(f"Job save failed: {exc}")
    _MEMORY_JOBS[job_id] = payload
