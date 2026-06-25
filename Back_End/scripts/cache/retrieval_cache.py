"""Retrieval cache with bounded in-memory LRU fallback (Redis optional)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Optional

from cache.lru_store import LRUMemoryStore
from cache.redis_client import get_redis, redis_available
from config import RETRIEVAL_CACHE_MAX_SIZE, RETRIEVAL_CACHE_TTL

logger = logging.getLogger(__name__)

_MEMORY = LRUMemoryStore(RETRIEVAL_CACHE_MAX_SIZE)


def query_cache_key(query: str, bsc_k: int = 5) -> str:
    """Stable cache key from normalized query text + BSC top-k."""
    normalized = re.sub(r"\s+", " ", query.strip().lower())
    digest = hashlib.sha256(f"{normalized}|{bsc_k}".encode("utf-8")).hexdigest()[:32]
    return f"pms:retrieval:{digest}"


def profile_cache_key(
    *,
    division: str,
    department: str,
    unit: str,
    job_title: str,
    job_grade: str,
    bsc_k: int = 5,
) -> str:
    """Backward-compatible key built from profile fields (same semantics as query hash)."""
    query = (
        f"division: {division.strip().lower()}\n"
        f"department: {department.strip().lower()}\n"
        f"unit: {unit.strip().lower()}\n"
        f"job title: {job_title.strip().lower()}\n"
        f"job grade: {job_grade.strip().lower()}"
    )
    return query_cache_key(query, bsc_k)


def get_cached_context(key: str) -> Optional[dict[str, Any]]:
    r = get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning(f"Retrieval cache get failed: {exc}")
        return None

    return _MEMORY.get(key)


def set_cached_context(key: str, payload: dict[str, Any], ttl: int | None = None) -> None:
    ttl = RETRIEVAL_CACHE_TTL if ttl is None else ttl
    r = get_redis()
    if r is not None:
        try:
            r.setex(key, ttl, json.dumps(payload, ensure_ascii=False))
            return
        except Exception as exc:
            logger.warning(f"Retrieval cache set failed: {exc}")

    _MEMORY.set(key, payload, ttl)


def invalidate_all() -> int:
    """Clear retrieval cache (call after ingest/rebuild). Returns keys removed."""
    r = get_redis()
    if r is not None:
        try:
            keys = list(r.scan_iter("pms:retrieval:*"))
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
        "memory_max_size": RETRIEVAL_CACHE_MAX_SIZE,
        "ttl_seconds": RETRIEVAL_CACHE_TTL,
    }
