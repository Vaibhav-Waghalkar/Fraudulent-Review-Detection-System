"""
Tests for fallback behavior when model is unavailable.
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
import mongomock_motor

from app.main import app
from app.db import get_db


@pytest.fixture
async def fallback_client():
    """Client with model NOT loaded to test fallback."""
    mongo_client = mongomock_motor.AsyncMongoMockClient()
    test_db = mongo_client["reviewguard_fallback_test"]

    async def override_db():
        return test_db

    app.dependency_overrides[get_db] = override_db

    with patch("app.services.inference._model_loaded", False), \
         patch("app.services.inference._session", None), \
         patch("app.services.cache.get_redis") as mock_redis_factory, \
         patch("app.workers.tasks.score_review.delay"):

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.ping.return_value = True
        pipeline_mock = MagicMock()
        pipeline_mock.incr = MagicMock()
        pipeline_mock.expire = MagicMock()
        pipeline_mock.execute = MagicMock(return_value=[1, True])
        mock_redis.pipeline.return_value = pipeline_mock
        mock_redis_factory.return_value = mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, test_db

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_fallback_batch_detect_works(fallback_client):
    """Batch detect should work and return fallback=True when model not loaded."""
    ac, _ = fallback_client
    resp = await ac.post(
        "/api/reviews/detect/batch",
        json=[{"text": "buy now buy now amazing", "user_id": "user-f1", "rating": 5}],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["fallback"] is True
    assert 0.0 <= data[0]["score"] <= 1.0


@pytest.mark.asyncio
async def test_fallback_score_is_rule_based(fallback_client):
    """In fallback mode, score should reflect rule triggers."""
    ac, _ = fallback_client
    # Clear review with no rules triggered
    resp_clean = await ac.post(
        "/api/reviews/detect/batch",
        json=[{"text": "Decent product. Works fine.", "user_id": "user-f2", "rating": 3}],
    )
    clean_score = resp_clean.json()[0]["score"]

    # Spammy review -- rules should trigger higher score
    resp_spam = await ac.post(
        "/api/reviews/detect/batch",
        json=[{
            "text": "buy buy buy buy buy amazing amazing amazing amazing",
            "user_id": "user-f3",
            "rating": 1,
        }],
    )
    spam_score = resp_spam.json()[0]["score"]

    # Spam should score >= clean in fallback mode
    assert spam_score >= clean_score


@pytest.mark.asyncio
async def test_submit_still_works_in_fallback(fallback_client):
    """Submit should still work even without model."""
    ac, _ = fallback_client
    resp = await ac.post(
        "/api/reviews/submit",
        json={"text": "Some review.", "user_id": "user-f4", "rating": 4},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_health_reflects_model_not_loaded(fallback_client):
    """Health check should report model_loaded=False."""
    ac, _ = fallback_client
    with patch("app.api.system.redis_ping", return_value=True):
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_loaded"] is False
    assert data["status"] in ("ok", "degraded")
