"""
Shared pytest fixtures.
"""
import asyncio
import pytest
import mongomock_motor
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db import get_db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """In-memory async mongomock database."""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client["reviewguard_test"]
    return db


@pytest.fixture
def mock_async_db(mock_db):
    """
    Async mongomock db.
    We override get_db dependency in tests.
    """
    return mock_db


@pytest.fixture
async def async_client(mock_db):
    """
    FastAPI test client with mocked DB, inference, and Redis.
    """
    # Mock inference
    with patch("app.services.inference._model_loaded", True), \
         patch("app.services.inference._session", MagicMock()), \
         patch("app.services.inference._scaler", MagicMock()), \
         patch("app.services.inference._tokenizer", MagicMock()), \
         patch("app.services.inference.infer", return_value=(0.3, False)), \
         patch("app.services.cache.get_redis", return_value=MagicMock(
             get=MagicMock(return_value=None),
             ping=MagicMock(return_value=True),
             pipeline=MagicMock(return_value=MagicMock(
                 incr=MagicMock(),
                 expire=MagicMock(),
                 execute=MagicMock(return_value=[1, True]),
             )),
         )), \
         patch("app.workers.tasks.score_review.delay", return_value=None):

        # Override DB dependency
        async def override_get_db():
            return mock_db

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

        app.dependency_overrides.clear()
