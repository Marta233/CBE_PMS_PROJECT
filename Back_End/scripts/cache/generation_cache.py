"""Cache Step 1 draft objectives to skip LLM on repeat regeneration."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from cache.lru_store import LRUMemoryStore
from cache.redis_client import get_redis, redis_available
from config import STEP1_CACHE_MAX_SIZE, STEP1_CACHE_TTL

logger = logging.getLogger(__name__)

_MEMORY = LRUMemoryStore(STEP1_CACHE_MAX_SIZE)


def context_fingerprint(
    jd_context: str,
    bsc_context: str,
    los_context: str,
) -> str:
    raw = "|".join((jd_context, bsc_context, los_context))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def step1_cache_key(
    *,
    employee_id: str,
    fiscal_year: int,
    prompt_version: str,
    num_drafts: int,
    context_fingerprint: str,
) -> str:
    raw = "|".join(
        str(s)
        for s in (
            employee_id.strip().lower(),
            fiscal_year,
            prompt_version,
            num_drafts,
            context_fingerprint,
        )
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"pms:step1:{digest}"


def get_cached_step1_drafts(key: str) -> Optional[list[dict[str, Any]]]:
    r = get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            if raw:
                payload = json.loads(raw)
                drafts = payload.get("drafts")
                if isinstance(drafts, list):
                    return drafts
        except Exception as exc:
            logger.warning(f"Step 1 cache get failed: {exc}")
        return None

    payload = _MEMORY.get(key)
    if isinstance(payload, dict):
        drafts = payload.get("drafts")
        if isinstance(drafts, list):
            return drafts
    return None


def set_cached_step1_drafts(key: str, drafts: list[dict[str, Any]], ttl: int | None = None) -> None:
    ttl = STEP1_CACHE_TTL if ttl is None else ttl
    payload = {"drafts": drafts}

    r = get_redis()
    if r is not None:
        try:
            r.setex(key, ttl, json.dumps(payload, ensure_ascii=False))
            return
        except Exception as exc:
            logger.warning(f"Step 1 cache set failed: {exc}")

    _MEMORY.set(key, payload, ttl)


def invalidate_all() -> int:
    """Clear Step 1 cache (e.g. after prompt template changes)."""
    r = get_redis()
    if r is not None:
        try:
            keys = list(r.scan_iter("pms:step1:*"))
            if keys:
                r.delete(*keys)
            return len(keys)
        except Exception:
            pass
    return _MEMORY.clear()


def cache_stats() -> dict[str, int | bool]:
    return {
        "redis_backed": redis_available(),
        "memory_entries": _MEMORY.size(),
        "memory_max_size": STEP1_CACHE_MAX_SIZE,
        "ttl_seconds": STEP1_CACHE_TTL,
    }
