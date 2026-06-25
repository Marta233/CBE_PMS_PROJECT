"""Shared Redis client — optional; in-memory fallbacks when unavailable."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_redis_client = None
_redis_checked = False
_status_logged = False


def get_redis():
    """Return a connected Redis client, or None when Redis is unavailable."""
    global _redis_client, _redis_checked, _status_logged

    if _redis_checked:
        return _redis_client

    _redis_checked = True
    try:
        import redis
        from config import REDIS_URL

        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        if not _status_logged:
            logger.info("Redis connected — shared cache and async queue available")
            _status_logged = True
    except ImportError:
        _redis_client = None
        if not _status_logged:
            logger.info(
                "Redis package not installed — using in-memory cache (sync API). "
                "Install with: pip install redis"
            )
            _status_logged = True
    except Exception as exc:
        _redis_client = None
        if not _status_logged:
            logger.info(
                f"Redis server unavailable ({exc}) — using in-memory cache (sync API)"
            )
            _status_logged = True

    return _redis_client


def redis_available() -> bool:
    return get_redis() is not None
