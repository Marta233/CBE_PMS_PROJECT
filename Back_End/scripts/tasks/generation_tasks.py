"""Celery task: run the 3-step LLM pipeline off the HTTP thread."""

from __future__ import annotations

import json
import logging

from jobs.job_store import mark_completed, mark_failed, mark_running, update_job
from llm.llm_client import LLMUnavailableError, LLMTimeoutError
from llm.pipeline import generate_objectives
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.run_generation", bind=True, max_retries=0)
def run_generation(self, job_id: str, context: dict, num_objectives: int) -> dict:
    mark_running(job_id)
    try:
        def _on_progress(update: dict) -> None:
            update_job(
                job_id,
                status="running",
                progress={
                    "stage": update.get("stage"),
                    "message": update.get("message"),
                },
                partial_result=update.get("partial_result"),
            )

        result = generate_objectives(
            context,
            num_objectives,
            progress_callback=_on_progress,
        )
        mark_completed(job_id, result)
        return result
    except LLMTimeoutError as exc:
        mark_failed(job_id, str(exc), detail={"error": "llm_timeout"})
        raise
    except LLMUnavailableError as exc:
        mark_failed(job_id, str(exc), detail={"error": "llm_unavailable"})
        raise
    except json.JSONDecodeError as exc:
        mark_failed(
            job_id,
            f"LLM returned invalid JSON after retries: {exc}",
            detail={"error": "invalid_json"},
        )
        raise
    except ValueError as exc:
        detail = str(exc)
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                mark_failed(job_id, "Validation failed", detail=parsed)
                raise
        except json.JSONDecodeError:
            pass
        mark_failed(job_id, detail)
        raise
    except Exception as exc:
        logger.exception("Generation task failed for job %s", job_id)
        mark_failed(job_id, f"Pipeline error: {exc}")
        raise
