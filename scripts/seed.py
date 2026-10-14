"""
Seed script: generates and submits reviews to the running API.
Usage: python scripts/seed.py --n 200 --api http://localhost:8000
"""
import argparse
import random
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))


def seed(n: int = 200, api_url: str = "http://localhost:8000"):
    from ml.generate_data import generate

    df = generate(n=n, seed=99)
    submitted = 0
    errors = 0

    for _, row in df.iterrows():
        try:
            resp = requests.post(
                f"{api_url}/api/reviews/submit",
                json={
                    "text": str(row["text"]),
                    "user_id": str(row["user_id"]),
                    "rating": int(row["rating"]),
                },
                timeout=10,
            )
            resp.raise_for_status()
            submitted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"Error: {e}")

    print(f"Seeded {submitted} reviews ({errors} errors).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    seed(n=args.n, api_url=args.api)
