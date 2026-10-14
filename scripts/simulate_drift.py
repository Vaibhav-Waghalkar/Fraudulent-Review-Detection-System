"""
Simulate drift by injecting shifted scores into MongoDB.
Proves that the drift detection alert fires.

Usage:
    python scripts/simulate_drift.py --shift 0.4 --n 500
"""
import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def simulate_drift(shift: float = 0.4, n: int = 500, mongo_uri: str = None):
    from pymongo import MongoClient
    from app.core.config import settings
    from app.services.drift import load_reference_scores, run_ks_test, send_mock_alerts

    uri = mongo_uri or settings.mongodb_uri
    client = MongoClient(uri)
    db = client[settings.mongodb_db]
    reviews = db["reviews"]
    drift_events = db["drift_events"]

    # Load reference scores
    ok = load_reference_scores()
    if not ok:
        logger.error("Could not load reference scores. Run training first.")
        return

    # Generate shifted scores and insert as fake reviews
    np.random.seed(99)
    shifted_scores = np.clip(
        np.random.beta(2, 2, n) + shift,
        0.0,
        1.0,
    ).tolist()

    docs = [
        {
            "text": f"Simulated drift review {i}",
            "user_id": f"drift-user-{i % 20}",
            "rating": 5,
            "velocity": 1,
            "score": s,
            "nlp_score": s,
            "rule_score": 0.0,
            "status": "quarantined" if s > 0.7 else "reviewed",
            "reasons": [],
            "explanation": {"simulated": True},
            "fallback": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "simulated_drift": True,
        }
        for i, s in enumerate(shifted_scores)
    ]
    reviews.insert_many(docs)
    logger.info("Inserted %d drift-simulated reviews with shift=%.2f", n, shift)

    # Run KS test against the now-shifted live distribution
    cursor = reviews.find({"score": {"$exists": True}}, {"score": 1}, limit=2000)
    live_scores = np.array([d["score"] for d in cursor])

    result = run_ks_test(live_scores)
    result["checked_at"] = datetime.now(timezone.utc)
    result["simulated"] = True
    drift_events.insert_one(result.copy())

    p = result.get("p_value", float("nan"))
    alert = result.get("alert", False)

    print("\n=== Drift Simulation Results ===")
    print(f"  Shift applied      : +{shift}")
    print(f"  Injected samples   : {n}")
    print(f"  Live scores (total): {result.get('n_live', 0)}")
    print(f"  KS statistic       : {result.get('ks_statistic', 0):.4f}")
    print(f"  p-value            : {p:.6f}")
    print(f"  Alert fired        : {alert}")

    if alert:
        send_mock_alerts(p, result.get("ks_statistic", 0))
        print("  [ALERT] Mock email and Slack alert sent.")
    else:
        print("  [INFO] No alert. Increase --shift to trigger.")

    client.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shift", type=float, default=0.4,
                        help="Score shift to apply (0-1)")
    parser.add_argument("--n", type=int, default=500,
                        help="Number of simulated reviews to inject")
    parser.add_argument("--mongo_uri", type=str, default=None)
    args = parser.parse_args()
    simulate_drift(shift=args.shift, n=args.n, mongo_uri=args.mongo_uri)
