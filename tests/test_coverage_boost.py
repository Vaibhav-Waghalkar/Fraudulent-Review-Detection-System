"""
Coverage boost tests to reach >80% coverage across all app modules.
"""
import pytest
from unittest.mock import patch, MagicMock
from bson import ObjectId
from datetime import datetime, timezone
import ml.explain

from app.services.cache import get_user_velocity, increment_user_velocity, ping
from app.services.explain import explain_review
from app.db import connect_db, close_db, get_db, _ensure_indexes
import app.db as db_mod
from app.workers.tasks import score_review, check_drift
import app.services.inference as inference_mod


@pytest.mark.asyncio
async def test_db_lifecycle():
    # Test real db connect and close
    await connect_db()
    current_db = get_db()
    assert current_db is not None
    await close_db()


@pytest.mark.asyncio
async def test_db_indexes_operation_failure():
    # Test error handling in _ensure_indexes
    with patch.object(db_mod, "_db", MagicMock()) as mock_db:
        from pymongo.errors import OperationFailure
        mock_col = MagicMock()
        mock_col.create_indexes.side_effect = OperationFailure("mock index error")
        mock_db.__getitem__.return_value = mock_col
        # should not raise
        await _ensure_indexes()


def test_cache_service():
    p = ping()
    assert isinstance(p, bool)

    vel = increment_user_velocity("test-user-cov")
    assert vel >= 1

    cached_vel = get_user_velocity("test-user-cov")
    assert cached_vel == vel

    assert get_user_velocity("non-existent-user-1234567") == 0

    with patch("app.services.cache.get_redis", side_effect=Exception("Redis down")):
        assert get_user_velocity("user") == 0
        assert increment_user_velocity("user") == 0
        assert ping() is False


def test_explain_service_unloaded():
    with patch.object(inference_mod, "_model_loaded", False):
        res = explain_review("Nice product", 0.0)
        assert "error" in res


def test_explain_service_loaded_and_error():
    with patch.object(inference_mod, "_model_loaded", True), \
         patch.object(inference_mod, "_session", MagicMock()), \
         patch.object(inference_mod, "_tokenizer", MagicMock()), \
         patch.object(inference_mod, "_scaler", MagicMock()):
        
        with patch.object(ml.explain, "explain_text", return_value={"word_importances": [("good", 0.8)]}):
            res = explain_review("Nice product", 0.0)
            assert "word_importances" in res

        with patch.object(ml.explain, "explain_text", side_effect=RuntimeError("LIME error")):
            res_err = explain_review("Nice product", 0.0)
            assert "error" in res_err


def test_celery_score_review_task():
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_reviews = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_reviews

    oid = ObjectId()
    mock_reviews.find_one.return_value = {
        "_id": oid,
        "text": "Amazing deal! Use promo code BEST10.",
        "user_id": "u-42",
        "rating": 5,
    }

    mock_session = MagicMock()
    mock_client.start_session.return_value.__enter__.return_value = mock_session

    with patch("pymongo.MongoClient", return_value=mock_client), \
         patch("app.services.cache.get_user_velocity", return_value=5), \
         patch("app.services.inference.is_model_loaded", return_value=True), \
         patch("app.services.inference.infer", return_value=(0.95, False)):
        
        score_review(str(oid))
        assert mock_reviews.update_one.called


def test_celery_score_review_not_found():
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_reviews = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_reviews
    mock_reviews.find_one.return_value = None

    with patch("pymongo.MongoClient", return_value=mock_client):
        score_review(str(ObjectId()))
        assert not mock_reviews.update_one.called


def test_celery_check_drift_task():
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_reviews = MagicMock()
    mock_drift = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.side_effect = lambda name: mock_reviews if name == "reviews" else mock_drift

    mock_reviews.find.return_value = [{"score": 0.1}, {"score": 0.9}]

    with patch("pymongo.MongoClient", return_value=mock_client), \
         patch("app.services.drift.load_reference_scores"), \
         patch("app.services.drift.run_ks_test", return_value={"p_value": 0.01, "ks_statistic": 0.35, "alert": True}), \
         patch("app.services.drift.send_mock_alerts") as mock_alerts:

        check_drift()
        assert mock_drift.insert_one.called
        assert mock_alerts.called


@pytest.mark.asyncio
async def test_explain_endpoint(async_client, mock_db):
    oid = ObjectId()
    await mock_db["reviews"].insert_one({
        "_id": oid,
        "text": "Great item!",
        "user_id": "u1",
        "rating": 5,
        "velocity": 1.0,
        "created_at": datetime.now(timezone.utc),
    })

    with patch("app.services.explain.explain_review", return_value={"features": [("great", 0.5)]}):
        # Valid ID
        res = await async_client.get(f"/api/reviews/{str(oid)}/explain")
        assert res.status_code == 200
        assert "lime_explanation" in res.json()

        # Non-existent ID
        missing_oid = str(ObjectId())
        res_missing = await async_client.get(f"/api/reviews/{missing_oid}/explain")
        assert res_missing.status_code == 404

        # Invalid ID format
        res_invalid = await async_client.get("/api/reviews/invalid-id/explain")
        assert res_invalid.status_code == 400


@pytest.mark.asyncio
async def test_list_reviews_filters_full(async_client, mock_db):
    await mock_db["reviews"].insert_many([
        {
            "text": "Review A",
            "user_id": "user-filter",
            "rating": 5,
            "score": 0.2,
            "status": "reviewed",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "text": "Review B",
            "user_id": "user-filter",
            "rating": 1,
            "score": 0.85,
            "status": "quarantined",
            "created_at": datetime.now(timezone.utc),
        },
    ])

    res = await async_client.get("/api/reviews?score_min=0.1&score_max=0.5&user_id=user-filter&status=reviewed")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
