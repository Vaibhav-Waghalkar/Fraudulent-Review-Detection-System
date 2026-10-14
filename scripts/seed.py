"""
Seed script: generates and submits reviews to the running API or directly seeds MongoDB with historical spread.
Usage: python scripts/seed.py --n 500 --days 14 --api http://localhost:8000
"""
import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))


def seed(n: int = 300, days: int = 14, api_url: str = "http://localhost:8000"):
    root = Path(__file__).parent.parent
    test_csv_path = root / "data" / "test.csv"

    # Try to load varied realistic user ids and review texts from data/test.csv
    reviews_pool = []
    if test_csv_path.exists():
        df_test = pd.read_csv(test_csv_path)
        for _, row in df_test.iterrows():
            reviews_pool.append({
                "text": str(row["text"]),
                "user_id": str(row["user_id"]),
                "rating": int(row["rating"]),
                "velocity": int(row.get("velocity", 1)),
                "label": int(row.get("label", 0)),
            })

    if not reviews_pool:
        from ml.generate_data import generate
        df_gen = generate(n=max(n, 200), seed=42)
        for _, row in df_gen.iterrows():
            reviews_pool.append({
                "text": str(row["text"]),
                "user_id": str(row["user_id"]),
                "rating": int(row["rating"]),
                "velocity": int(row.get("velocity", 1)),
                "label": int(row.get("label", 0)),
            })

    random.seed(42)
    selected = [random.choice(reviews_pool) for _ in range(n)]

    # We also connect directly to MongoDB if available to backdate timestamps over N days
    # while maintaining API scoring
    try:
        from pymongo import MongoClient
        from app.core.config import settings
        from app.services import inference as inference_svc
        from app.services.rules import score_rules

        client = MongoClient(settings.mongodb_uri)
        db = client[settings.mongodb_db]
        reviews_col = db["reviews"]

        if not inference_svc.is_model_loaded():
            inference_svc.load_model()

        now = datetime.now(timezone.utc)
        docs_to_insert = []

        print(f"Seeding {n} reviews spread across the past {days} days...")
        for i, item in enumerate(selected):
            # Spread timestamps over past N days
            random_days_ago = random.uniform(0.05, float(days))
            created_dt = now - timedelta(days=random_days_ago)

            text = item["text"]
            user_id = item["user_id"]
            rating = item["rating"]
            velocity = item.get("velocity", 1)

            nlp_score, fallback = inference_svc.infer(text, float(velocity))
            rule_score, triggered_rules = score_rules(text, rating, velocity)

            vel_norm = min(velocity / 10.0, 1.0)
            final_score = settings.nlp_weight * nlp_score + settings.velocity_weight * vel_norm
            final_score = float(min(final_score, 1.0))
            status = "quarantined" if final_score > settings.quarantine_threshold else "reviewed"

            doc = {
                "text": text,
                "user_id": user_id,
                "rating": rating,
                "velocity": velocity,
                "score": final_score,
                "nlp_score": nlp_score,
                "rule_score": rule_score,
                "status": status,
                "reasons": [r["rule"] for r in triggered_rules],
                "explanation": {"rules": triggered_rules},
                "fallback": fallback,
                "created_at": created_dt,
                "updated_at": created_dt,
            }
            docs_to_insert.append(doc)

        if docs_to_insert:
            reviews_col.insert_many(docs_to_insert)
            print(f"Successfully seeded {len(docs_to_insert)} reviews directly into MongoDB with timestamps spread over {days} days.")
        client.close()
        return

    except Exception as db_err:
        print(f"Direct DB seed fallback to API due to: {db_err}")

    # Fallback to HTTP API if DB cannot be connected directly
    submitted = 0
    errors = 0
    for item in selected:
        try:
            resp = requests.post(
                f"{api_url}/api/reviews/submit",
                json={
                    "text": item["text"],
                    "user_id": item["user_id"],
                    "rating": item["rating"],
                },
                timeout=10,
            )
            resp.raise_for_status()
            submitted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"Error submitting review: {e}")

    print(f"Seeded {submitted} reviews via API ({errors} errors).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    seed(n=args.n, days=args.days, api_url=args.api)
