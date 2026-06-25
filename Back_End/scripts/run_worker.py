"""Start Celery worker for async objective generation.

From Back_End/:
  python -m scripts.run_worker

Requires Redis (REDIS_URL) and Ollama/vLLM on the worker host.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from tasks.celery_app import celery_app

if __name__ == "__main__":
    celery_app.worker_main(argv=["worker", "--loglevel=info", "--concurrency=2"])
