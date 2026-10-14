"""
MongoDB database layer.
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None


async def connect_db() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_db]
    await _ensure_indexes()
    logger.info("MongoDB connected: %s / %s", settings.mongodb_uri, settings.mongodb_db)


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB disconnected.")


def get_db() -> AsyncIOMotorDatabase:
    return _db


async def _ensure_indexes() -> None:
    """Create indexes on reviews and audit_log collections."""
    try:
        reviews = _db["reviews"]
        await reviews.create_indexes([
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("score", DESCENDING)]),
        ])

        audit = _db["audit_log"]
        await audit.create_indexes([
            IndexModel([("review_id", ASCENDING)]),
            IndexModel([("timestamp", DESCENDING)]),
        ])

        drift = _db["drift_events"]
        await drift.create_indexes([
            IndexModel([("checked_at", DESCENDING)]),
        ])

        logger.info("MongoDB indexes ensured.")
    except OperationFailure as e:
        logger.warning("Index creation warning: %s", e)
