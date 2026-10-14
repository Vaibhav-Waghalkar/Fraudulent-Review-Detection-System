"""
Redis cache service for user velocity tracking.
TTL: 1 day (86400 seconds).
"""
import logging
from redis import Redis
from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Redis = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def get_user_velocity(user_id: str) -> int:
    """Return the cached review count for a user in the last day."""
    try:
        r = get_redis()
        val = r.get(f"velocity:{user_id}")
        return int(val) if val else 0
    except Exception as e:
        logger.warning("Redis get_user_velocity error: %s", e)
        return 0


def increment_user_velocity(user_id: str) -> int:
    """Increment and return the user velocity counter."""
    try:
        r = get_redis()
        key = f"velocity:{user_id}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, settings.velocity_ttl)
        result = pipe.execute()
        return int(result[0])
    except Exception as e:
        logger.warning("Redis increment_user_velocity error: %s", e)
        return 0


def ping() -> bool:
    try:
        return get_redis().ping()
    except Exception:
        return False
