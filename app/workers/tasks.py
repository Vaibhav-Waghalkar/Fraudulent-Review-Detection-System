"""
Celery tasks:
- score_review: Asynchronously scores a submitted review and updates MongoDB.
- check_drift: Hourly drift detection task.
"""
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.score_review", bind=True, max_retries=3)
def score_review(self, review_id: str):
    """Score a review and update its record in MongoDB."""
    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError

        from app.services import inference as inference_svc
        from app.services.rules import score_rules
        from app.services.cache import get_user_velocity

        client = MongoClient(settings.mongodb_uri)
        db = client[settings.mongodb_db]
        reviews = db["reviews"]

        # Load model if not loaded
        if not inference_svc.is_model_loaded():
            inference_svc.load_model()

        doc = reviews.find_one({"_id": __import__("bson").ObjectId(review_id)})
        if not doc:
            logger.warning("Review not found: %s", review_id)
            return

        text = doc["text"]
        user_id = doc["user_id"]
        rating = doc["rating"]
        velocity = get_user_velocity(user_id)

        # NLP score
        nlp_score, fallback = inference_svc.infer(text, float(velocity))

        # Rule score and explanations
        rule_score, triggered_rules = score_rules(text, rating, velocity)

        # Final combined score
        vel_norm = min(velocity / 10.0, 1.0)
        final_score = (
            settings.nlp_weight * nlp_score
            + settings.velocity_weight * vel_norm
        )
        final_score = float(min(final_score, 1.0))

        status = "quarantined" if final_score > settings.quarantine_threshold else "reviewed"

        # Update with transaction (replica set required)
        with client.start_session() as session:
            with session.start_transaction():
                reviews.update_one(
                    {"_id": __import__("bson").ObjectId(review_id)},
                    {
                        "$set": {
                            "score": final_score,
                            "nlp_score": nlp_score,
                            "rule_score": rule_score,
                            "status": status,
                            "reasons": [r["rule"] for r in triggered_rules],
                            "explanation": {"rules": triggered_rules},
                            "fallback": fallback,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                    session=session,
                )

        logger.info(
            "Scored review %s: score=%.3f status=%s fallback=%s",
            review_id, final_score, status, fallback
        )
        client.close()

    except Exception as exc:
        logger.error("score_review task failed for %s: %s", review_id, exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.check_drift")
def check_drift():
    """Hourly drift detection task."""
    try:
        from pymongo import MongoClient
        import numpy as np
        from app.services.drift import run_ks_test, load_reference_scores, send_mock_alerts

        load_reference_scores()

        client = MongoClient(settings.mongodb_uri)
        db = client[settings.mongodb_db]
        reviews = db["reviews"]
        drift_events = db["drift_events"]

        # Pull recent scores (last 1000)
        cursor = reviews.find(
            {"score": {"$exists": True}},
            {"score": 1},
            sort=[("updated_at", -1)],
            limit=1000,
        )
        live_scores = np.array([doc["score"] for doc in cursor])

        result = run_ks_test(live_scores)
        result["checked_at"] = datetime.now(timezone.utc)

        # Store event
        drift_events.insert_one(result.copy())

        if result.get("alert"):
            send_mock_alerts(result["p_value"], result["ks_statistic"])

        logger.info("Drift check: p=%.4f alert=%s", result.get("p_value", -1), result.get("alert"))
        client.close()

    except Exception as e:
        logger.error("check_drift task failed: %s", e)
