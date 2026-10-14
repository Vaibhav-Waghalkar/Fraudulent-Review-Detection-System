"""
Tests for the API endpoints using httpx AsyncClient with mongomock.
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
import mongomock_motor

from app.main import app
from app.db import get_db


@pytest.fixture
async def client():
    """Test client with mocked dependencies."""
    mongo_client = mongomock_motor.AsyncMongoMockClient()
    test_db = mongo_client["reviewguard_test"]

    async def override_db():
        return test_db

    app.dependency_overrides[get_db] = override_db

    with patch("app.services.inference._model_loaded", True), \
         patch("app.services.inference.infer", return_value=(0.25, False)), \
         patch("app.services.cache.get_redis") as mock_redis_factory, \
         patch("app.workers.tasks.score_review.delay"):

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.ping.return_value = True
        pipeline_mock = MagicMock()
        pipeline_mock.__enter__ = MagicMock(return_value=pipeline_mock)
        pipeline_mock.__exit__ = MagicMock(return_value=False)
        pipeline_mock.incr = MagicMock()
        pipeline_mock.expire = MagicMock()
        pipeline_mock.execute = MagicMock(return_value=[2, True])
        mock_redis.pipeline.return_value = pipeline_mock
        mock_redis_factory.return_value = mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, test_db

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_root(client):
    ac, _ = client
    resp = await ac.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "service" in data
    assert data["service"] == "ReviewGuard"


@pytest.mark.asyncio
async def test_submit_review(client):
    ac, db = client
    resp = await ac.post(
        "/api/reviews/submit",
        json={"text": "Great product!", "user_id": "user-1", "rating": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_submit_review_invalid_rating(client):
    ac, _ = client
    resp = await ac.post(
        "/api/reviews/submit",
        json={"text": "Good", "user_id": "user-1", "rating": 6},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_review_missing_text(client):
    ac, _ = client
    resp = await ac.post(
        "/api/reviews/submit",
        json={"user_id": "user-1", "rating": 3},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_detect(client):
    ac, _ = client
    resp = await ac.post(
        "/api/reviews/detect/batch",
        json=[
            {"text": "Amazing product!", "user_id": "user-2", "rating": 5},
            {"text": "Terrible, waste of money.", "user_id": "user-3", "rating": 1},
        ],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for item in data:
        assert "id" in item
        assert "score" in item
        assert "status" in item
        assert 0.0 <= item["score"] <= 1.0


@pytest.mark.asyncio
async def test_batch_detect_fallback_marked(client):
    """When model is not loaded, batch detect should mark fallback=True."""
    ac, _ = client
    with patch("app.services.inference.infer", return_value=(0.5, True)):
        resp = await ac.post(
            "/api/reviews/detect/batch",
            json=[{"text": "Test review", "user_id": "user-4", "rating": 3}],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["fallback"] is True


@pytest.mark.asyncio
async def test_get_review(client):
    ac, db = client
    # First submit a review
    submit_resp = await ac.post(
        "/api/reviews/submit",
        json={"text": "Good product.", "user_id": "user-5", "rating": 4},
    )
    review_id = submit_resp.json()["id"]

    # Get the review
    resp = await ac.get(f"/api/reviews/{review_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == review_id
    assert data["text"] == "Good product."


@pytest.mark.asyncio
async def test_get_review_not_found(client):
    ac, _ = client
    resp = await ac.get("/api/reviews/507f1f77bcf86cd799439011")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_review_invalid_id(client):
    ac, _ = client
    resp = await ac.get("/api/reviews/not-a-valid-id")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_reviews(client):
    ac, _ = client
    # Submit a few
    for i in range(3):
        await ac.post(
            "/api/reviews/submit",
            json={"text": f"Review {i}", "user_id": "list-user", "rating": 3},
        )

    resp = await ac.get("/api/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_reviews_filters(client):
    ac, _ = client
    resp = await ac.get("/api/reviews?user_id=list-user&page=1&page_size=5")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_override_review(client):
    ac, db = client
    # Submit and get review
    submit_resp = await ac.post(
        "/api/reviews/submit",
        json={"text": "Suspicious review!", "user_id": "user-6", "rating": 5},
    )
    review_id = submit_resp.json()["id"]

    resp = await ac.post(
        f"/api/reviews/{review_id}/override",
        json={"moderator_id": "mod-001", "action": "approve", "note": "Looks fine."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "approve"
    assert data["moderator_id"] == "mod-001"


@pytest.mark.asyncio
async def test_override_invalid_action(client):
    ac, db = client
    submit_resp = await ac.post(
        "/api/reviews/submit",
        json={"text": "Test", "user_id": "user-7", "rating": 3},
    )
    review_id = submit_resp.json()["id"]

    resp = await ac.post(
        f"/api/reviews/{review_id}/override",
        json={"moderator_id": "mod-001", "action": "delete"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_health_check(client):
    ac, _ = client
    with patch("app.api.system.redis_ping", return_value=True):
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "model_loaded" in data


@pytest.mark.asyncio
async def test_drift_status_no_events(client):
    ac, _ = client
    resp = await ac.get("/api/drift/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "alert" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_webhook_missing_signature(client):
    ac, _ = client
    resp = await ac.post(
        "/api/reviews/webhook",
        content=b'{"text":"test","user_id":"u1","rating":3}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_signature(client):
    ac, _ = client
    resp = await ac.post(
        "/api/reviews/webhook",
        content=b'{"text":"test","user_id":"u1","rating":3}',
        headers={
            "Content-Type": "application/json",
            "X-Signature": "sha256=invalidsignature",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_valid_signature(client):
    import hashlib
    import hmac

    ac, _ = client
    secret = "changeme-webhook-secret"
    body = b'{"text":"webhook review","user_id":"wh-user","rating":4}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    resp = await ac.post(
        "/api/reviews/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_get_stats(client):
    ac, test_db = client
    # Insert test review
    from datetime import datetime, timezone
    await test_db["reviews"].insert_one({
        "text": "Great product",
        "user_id": "test-user-stats",
        "rating": 5,
        "score": 0.15,
        "status": "reviewed",
        "created_at": datetime.now(timezone.utc),
    })

    resp = await ac.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_reviews" in data
    assert "status_counts" in data
    assert "fraud_rate" in data
    assert "daily_timeline" in data
    assert "score_distribution" in data
    assert len(data["daily_timeline"]) == 30
    assert len(data["score_distribution"]) == 20


@pytest.mark.asyncio
async def test_get_model_info(client):
    ac, _ = client
    resp = await ac.get("/api/model/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_name" in data
    assert "training_metrics" in data
    assert "benchmarks" in data
    assert "int8_size_mb" in data
    assert "synthetic_data_note" in data


@pytest.mark.asyncio
async def test_run_drift_check(client):
    ac, test_db = client
    # Seed reviews with scores
    from datetime import datetime, timezone
    docs = [
        {"score": 0.05 * (i % 10), "updated_at": datetime.now(timezone.utc)}
        for i in range(40)
    ]
    await test_db["reviews"].insert_many(docs)

    resp = await ac.post("/api/drift/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "ks_statistic" in data or "error" in data
