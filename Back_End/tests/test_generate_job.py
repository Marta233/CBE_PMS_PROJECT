"""Async generation job store and the poll endpoint, without calling the LLM."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import jobs.job_store as job_store
from API.routers.generate import router as generate_router
from jobs.job_store import JobStatus


class MemoryRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value
        self.ttl[key] = ttl


class FailingRedis:
    def get(self, key: str):
        return None

    def setex(self, key: str, ttl: int, value: str) -> None:
        raise ConnectionError("redis down")


@pytest.fixture(autouse=True)
def _isolated_jobs(monkeypatch):
    job_store._MEMORY_JOBS.clear()
    monkeypatch.setattr(job_store, "get_redis", lambda: None)
    yield
    job_store._MEMORY_JOBS.clear()


def _completed_result() -> dict:
    return {
        "employee_profile": {"job_title": "Digital Banking Officer"},
        "objectives": [
            {
                "objective": "Grow active agents",
                "measure": "Active agents",
                "target": "500",
                "weight_percent": 100,
                "category": "Major",
                "tracking_source": "MIS",
                "time_frame": "Quarter",
            }
        ],
        "total_weight": 100,
        "pipeline_meta": {"warnings": []},
    }


def test_memory_job_moves_from_queued_to_completed():
    job_id = job_store.create_job(ttl=60)
    assert job_store.get_job(job_id)["status"] == JobStatus.QUEUED.value

    job_store.mark_running(job_id)
    assert job_store.get_job(job_id)["status"] == JobStatus.RUNNING.value

    job_store.mark_completed(job_id, _completed_result())
    stored = job_store.get_job(job_id)
    assert stored["status"] == JobStatus.COMPLETED.value
    assert stored["result"]["total_weight"] == 100
    assert job_store.get_job("missing") is None


def test_failed_job_keeps_error_and_detail():
    job_id = job_store.create_job(ttl=60)
    job_store.mark_failed(job_id, "LLM unavailable", detail={"error": "llm_unavailable"})
    stored = job_store.get_job(job_id)
    assert stored["status"] == JobStatus.FAILED.value
    assert stored["error"] == "LLM unavailable"
    assert stored["detail"] == {"error": "llm_unavailable"}


def test_redis_round_trip_and_write_failure_fallback(monkeypatch):
    redis = MemoryRedis()
    monkeypatch.setattr(job_store, "get_redis", lambda: redis)

    job_id = job_store.create_job(ttl=90)
    assert redis.ttl[f"pms:job:{job_id}"] == 90
    job_store._MEMORY_JOBS.clear()
    assert job_store.get_job(job_id)["status"] == JobStatus.QUEUED.value

    monkeypatch.setattr(job_store, "get_redis", lambda: FailingRedis())
    failed_id = job_store.create_job(ttl=90)
    assert job_store.get_job(failed_id)["job_id"] == failed_id
    assert job_store.get_job(failed_id)["status"] == JobStatus.QUEUED.value


def test_poll_endpoint_returns_completed_failed_and_missing_jobs():
    app = FastAPI()
    app.include_router(generate_router, prefix="/api")
    client = TestClient(app)

    completed_id = job_store.create_job(ttl=60)
    job_store.mark_completed(completed_id, _completed_result())
    completed = client.get(f"/api/jobs/{completed_id}")
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "completed"
    assert body["result"]["objectives"][0]["objective"] == "Grow active agents"
    assert body["result"]["total_weight"] == 100

    failed_id = job_store.create_job(ttl=60)
    job_store.mark_failed(failed_id, "Pipeline error", detail={"error": "invalid_json"})
    failed = client.get(f"/api/jobs/{failed_id}")
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["error"] == "Pipeline error"
    assert failed.json()["detail"] == {"error": "invalid_json"}

    missing = client.get("/api/jobs/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "job_not_found"
