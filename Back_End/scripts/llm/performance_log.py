"""Append-only LLM request timing log."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

_logger: logging.Logger | None = None
_HEADER = (
    "# timestamp | backend | model | label | status | duration | "
    "system_chars | user_chars | response_chars | timeout_limit | error"
)


def get_perf_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    from config import LLM_PERF_LOG_PATH

    path = Path(LLM_PERF_LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0

    logger = logging.getLogger("pms.llm.performance")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    if write_header:
        logger.info(_HEADER)

    _logger = logger
    return _logger


def log_llm_request(
    *,
    backend: str,
    model: str,
    label: str,
    status: str,
    duration_seconds: float,
    timeout_seconds: float,
    system_chars: int = 0,
    user_chars: int = 0,
    response_chars: int = 0,
    error: str | None = None,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = " | ".join([
        ts,
        backend,
        model,
        label or "-",
        status,
        f"{duration_seconds:.2f}s",
        str(system_chars),
        str(user_chars),
        str(response_chars),
        f"{timeout_seconds:.0f}s",
        (error or "-").replace("\n", " ")[:200],
    ])
    get_perf_logger().info(row)
