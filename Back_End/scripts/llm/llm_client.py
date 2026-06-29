"""Unified LLM client — Ollama (default) or vLLM OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent import futures
from typing import Any, Callable, TypeVar

from .performance_log import log_llm_request

logger = logging.getLogger(__name__)

T = TypeVar("T")

_ollama_semaphore: threading.BoundedSemaphore | None = None


class LLMUnavailableError(Exception):
    """Raised when the configured LLM backend is unreachable."""


class LLMTimeoutError(LLMUnavailableError):
    """Raised when an LLM request exceeds the configured timeout."""


def _backend_config() -> tuple[str, str]:
    from config import LLM_BACKEND, OLLAMA_MODEL, VLLM_BASE_URL, VLLM_MODEL

    backend = LLM_BACKEND
    if backend == "vllm":
        return backend, VLLM_MODEL
    return "ollama", OLLAMA_MODEL


def _ollama_concurrency_limit() -> threading.BoundedSemaphore:
    global _ollama_semaphore
    if _ollama_semaphore is None:
        from config import OLLAMA_MAX_CONCURRENT

        _ollama_semaphore = threading.BoundedSemaphore(OLLAMA_MAX_CONCURRENT)
    return _ollama_semaphore


def _run_with_timeout(fn: Callable[[], T], timeout_seconds: float) -> T:
    """Run a blocking LLM call with a hard wait timeout (does not cancel the thread)."""
    if timeout_seconds <= 0:
        return fn()

    with futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except futures.TimeoutError as exc:
            raise LLMTimeoutError(
                f"LLM request timed out after {timeout_seconds:.0f}s."
            ) from exc


def _extract_ollama_model_names(listed: dict) -> set[str]:
    model_names: set[str] = set()
    for m in listed.get("models", []):
        raw_name = ""
        if isinstance(m, dict):
            for key in ("model", "name"):
                if m.get(key):
                    raw_name = str(m[key])
                    break
        else:
            raw_name = str(getattr(m, "model", "") or getattr(m, "name", ""))
        if raw_name:
            model_names.add(raw_name.split(":")[0])
    return model_names


def check_llm_available(model: str | None = None) -> None:
    from config import OLLAMA_HEALTH_TIMEOUT_SECONDS

    backend, default_model = _backend_config()
    model = model or default_model
    health_timeout = OLLAMA_HEALTH_TIMEOUT_SECONDS if backend == "ollama" else 5.0

    if backend == "vllm":
        _run_with_timeout(lambda: _check_vllm(model), health_timeout)
    else:
        _run_with_timeout(lambda: _check_ollama(model), health_timeout)


def probe_llm_health(model: str | None = None) -> dict[str, Any]:
    """Lightweight health probe for /api/health — uses short timeouts."""
    from config import (
        OLLAMA_HEALTH_TIMEOUT_SECONDS,
        OLLAMA_MAX_CONCURRENT,
        OLLAMA_TIMEOUT_SECONDS,
        VLLM_TIMEOUT_SECONDS,
    )

    backend, default_model = _backend_config()
    model = model or default_model
    health_timeout = OLLAMA_HEALTH_TIMEOUT_SECONDS if backend == "ollama" else 5.0

    out: dict[str, Any] = {
        "backend": backend,
        "model": model,
        "reachable": False,
        "model_loaded": False,
        "available": False,
        "message": "unknown",
        "request_timeout_seconds": OLLAMA_TIMEOUT_SECONDS if backend == "ollama" else VLLM_TIMEOUT_SECONDS,
        "health_timeout_seconds": health_timeout,
        "max_concurrent_requests": OLLAMA_MAX_CONCURRENT if backend == "ollama" else None,
    }

    try:
        if backend == "vllm":
            _run_with_timeout(lambda: _check_vllm(model), health_timeout)
        else:
            _run_with_timeout(lambda: _check_ollama(model), health_timeout)
        out.update(reachable=True, model_loaded=True, available=True, message="ok")
    except LLMTimeoutError as exc:
        out["message"] = str(exc)
    except LLMUnavailableError as exc:
        msg = str(exc)
        out["message"] = msg
        if backend == "ollama" and "not loaded" in msg.lower():
            out["reachable"] = True
    except Exception as exc:
        out["message"] = f"Health probe failed: {exc}"

    return out


def _check_ollama(model: str) -> None:
    import ollama

    try:
        listed = ollama.list()
    except Exception as exc:
        raise LLMUnavailableError(
            "LLM unavailable. Please ensure Ollama is running and reachable."
        ) from exc

    model_names = _extract_ollama_model_names(listed)
    base = model.split(":")[0]
    if base not in model_names:
        raise LLMUnavailableError(
            f"LLM unavailable. Model '{model}' is not loaded in Ollama."
        )


def _check_vllm(model: str) -> None:
    import httpx
    from config import VLLM_BASE_URL

    url = VLLM_BASE_URL.rstrip("/") + "/models"
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    ids = {m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)}
    if ids and model not in ids and not any(model in i for i in ids):
        logger.warning(f"vLLM model '{model}' not listed; proceeding anyway")


def chat_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.3,
    num_predict: int = 2048,
    seed: int | None = None,
    label: str | None = None,
) -> str:
    from config import OLLAMA_TIMEOUT_SECONDS, VLLM_TIMEOUT_SECONDS

    backend, default_model = _backend_config()
    model = model or default_model
    timeout_seconds = VLLM_TIMEOUT_SECONDS if backend == "vllm" else OLLAMA_TIMEOUT_SECONDS
    request_label = label or "chat"
    started = time.perf_counter()

    try:
        if backend == "vllm":
            result = _vllm_chat(
                system, user, model=model, temperature=temperature, num_predict=num_predict, seed=seed,
            )
        else:
            result = _ollama_chat(
                system, user, model=model, temperature=temperature, num_predict=num_predict, seed=seed,
            )
    except LLMTimeoutError as exc:
        log_llm_request(
            backend=backend,
            model=model,
            label=request_label,
            status="TIMEOUT",
            duration_seconds=time.perf_counter() - started,
            timeout_seconds=timeout_seconds,
            system_chars=len(system),
            user_chars=len(user),
            error=str(exc),
        )
        raise
    except LLMUnavailableError as exc:
        log_llm_request(
            backend=backend,
            model=model,
            label=request_label,
            status="ERROR",
            duration_seconds=time.perf_counter() - started,
            timeout_seconds=timeout_seconds,
            system_chars=len(system),
            user_chars=len(user),
            error=str(exc),
        )
        raise
    except Exception as exc:
        log_llm_request(
            backend=backend,
            model=model,
            label=request_label,
            status="ERROR",
            duration_seconds=time.perf_counter() - started,
            timeout_seconds=timeout_seconds,
            system_chars=len(system),
            user_chars=len(user),
            error=str(exc),
        )
        raise

    log_llm_request(
        backend=backend,
        model=model,
        label=request_label,
        status="OK",
        duration_seconds=time.perf_counter() - started,
        timeout_seconds=timeout_seconds,
        system_chars=len(system),
        user_chars=len(user),
        response_chars=len(result),
    )
    return result


def _ollama_chat(
    system: str,
    user: str,
    *,
    model: str,
    temperature: float,
    num_predict: int,
    seed: int | None = None,
) -> str:
    from config import OLLAMA_TIMEOUT_SECONDS

    with _ollama_concurrency_limit():
        return _run_with_timeout(
            lambda: _ollama_chat_inner(
                system, user,
                model=model, temperature=temperature, num_predict=num_predict, seed=seed,
            ),
            OLLAMA_TIMEOUT_SECONDS,
        )


def _ollama_chat_inner(
    system: str,
    user: str,
    *,
    model: str,
    temperature: float,
    num_predict: int,
    seed: int | None = None,
) -> str:
    import ollama

    options: dict[str, Any] = {
        "temperature": temperature,
        "top_p": 0.9,
        "num_predict": num_predict,
    }
    if seed is not None:
        options["seed"] = seed
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            format="json",
            options=options,
        )
    except Exception as exc:
        raise LLMUnavailableError(
            "LLM unavailable. Please ensure Ollama is running and reachable."
        ) from exc
    return response["message"]["content"]


def _vllm_chat(
    system: str,
    user: str,
    *,
    model: str,
    temperature: float,
    num_predict: int,
    seed: int | None = None,
) -> str:
    import httpx
    from config import VLLM_BASE_URL, VLLM_TIMEOUT_SECONDS

    url = VLLM_BASE_URL.rstrip("/") + "/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system + "\nRespond with valid JSON only."},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": num_predict,
        "response_format": {"type": "json_object"},
    }
    if seed is not None:
        body["seed"] = seed
    try:
        with httpx.Client(timeout=VLLM_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException as exc:
        raise LLMTimeoutError(
            f"LLM request timed out after {VLLM_TIMEOUT_SECONDS:.0f}s."
        ) from exc
    except Exception as exc:
        raise LLMUnavailableError(
            f"LLM unavailable. vLLM request failed at {VLLM_BASE_URL}."
        ) from exc

    content = data["choices"][0]["message"]["content"]
    if isinstance(content, str):
        return content
    return json.dumps(content)
