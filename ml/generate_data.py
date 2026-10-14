"""
Phase 1: Generate synthetic review data.
50,000 rows, 5% fraud, seed 42. Stratified 80/10/10 split.
"""
import random
import csv
import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker
from sklearn.model_selection import train_test_split

fake = Faker()
random.seed(42)
np.random.seed(42)
Faker.seed(42)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LEGIT_TEMPLATES = [
    "Really enjoyed using this product. {detail} Would recommend.",
    "Good quality overall. {detail} Satisfied with the purchase.",
    "Arrived on time and exactly as described. {detail}",
    "The product works as expected. {detail} Happy with it.",
    "Decent quality for the price. {detail}",
    "Used it for {duration} and it still works perfectly. {detail}",
    "My family loves it. {detail} Great value.",
    "Not perfect but does the job. {detail}",
    "Packaging was damaged but the product was fine. {detail}",
    "{detail} Would buy again.",
]

FRAUD_TEMPLATES = [
    "This is the best product ever! Buy it now! Amazing! {spam}",
    "WOW absolutely incredible! {spam} Best purchase of my life!",
    "Do not miss this deal! {spam} Everyone needs this!",
    "Five stars! Perfect! {spam} Highly highly highly recommend!",
    "BEST EVER! {spam} Cannot believe how good this is!",
    "{spam} Best product in the world! Order immediately!",
    "Exceptional! Unbelievable! {spam} Just buy it!",
    "This changed my life! {spam} Tell all your friends!",
]

DETAILS = [
    "Battery life is good.",
    "Fits perfectly.",
    "Color matches the photos.",
    "Easy to set up.",
    "Customer service was helpful.",
    "Slightly smaller than expected but still fine.",
    "The material feels durable.",
    "Instructions were clear.",
    "Took a few days to arrive.",
    "Works well with other devices I own.",
]

SPAM_PHRASES = [
    "Click here for discount!",
    "Use promo code BEST10.",
    "Limited time offer!",
    "Visit our website now.",
    "Follow us on social media.",
    "Buy two get one free!",
    "Share this review for a coupon.",
    "Subscribe to our newsletter.",
]

DURATIONS = ["a week", "two weeks", "a month", "three months", "six months", "a year"]


def _legit_text() -> str:
    tmpl = random.choice(LEGIT_TEMPLATES)
    return tmpl.format(
        detail=random.choice(DETAILS),
        duration=random.choice(DURATIONS),
    )


def _fraud_text() -> str:
    tmpl = random.choice(FRAUD_TEMPLATES)
    # fix the typo "best eve r" -> "best ever"
    text = tmpl.format(spam=random.choice(SPAM_PHRASES))
    return text.replace("best eve r", "best ever")


def _velocity(is_fraud: bool, user_id: str, user_counts: dict) -> int:
    """Number of reviews the user has submitted today (simulated)."""
    base = user_counts.get(user_id, 0)
    if is_fraud:
        increment = random.randint(3, 15)
    else:
        increment = random.randint(0, 2)
    user_counts[user_id] = base + increment
    return base + increment


def generate(n: int = 50_000, fraud_rate: float = 0.05, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)

    n_fraud = int(n * fraud_rate)
    n_legit = n - n_fraud

    rows = []
    user_counts: dict = {}

    # Legit
    for _ in range(n_legit):
        user_id = fake.uuid4()[:8]
        is_fraud = False
        rating = random.choice([3, 4, 5])
        text = _legit_text()
        vel = _velocity(is_fraud, user_id, user_counts)
        rows.append(
            {
                "user_id": user_id,
                "text": text,
                "rating": rating,
                "velocity": vel,
                "label": 0,
            }
        )

    # Fraud
    # Fraudsters often share a small pool of user_ids (burst behaviour)
    fraud_users = [fake.uuid4()[:8] for _ in range(50)]
    for _ in range(n_fraud):
        user_id = random.choice(fraud_users)
        is_fraud = True
        rating = random.choice([1, 5])  # extreme ratings
        text = _fraud_text()
        vel = _velocity(is_fraud, user_id, user_counts)
        rows.append(
            {
                "user_id": user_id,
                "text": text,
                "rating": rating,
                "velocity": vel,
                "label": 1,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def split_and_save(df: pd.DataFrame, out_dir: str = "data") -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    train_df, temp_df = train_test_split(
        df, test_size=0.20, stratify=df["label"], random_state=42
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, stratify=temp_df["label"], random_state=42
    )

    df.to_csv(os.path.join(out_dir, "reviews_dataset.csv"), index=False)
    train_df.to_csv(os.path.join(out_dir, "train.csv"), index=False)
    val_df.to_csv(os.path.join(out_dir, "val.csv"), index=False)
    test_df.to_csv(os.path.join(out_dir, "test.csv"), index=False)

    print(f"Total rows : {len(df):,}")
    print(f"Train rows : {len(train_df):,}  fraud={train_df['label'].sum():,}")
    print(f"Val rows   : {len(val_df):,}  fraud={val_df['label'].sum():,}")
    print(f"Test rows  : {len(test_df):,}  fraud={test_df['label'].sum():,}")
    print(f"Saved to   : {out_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50_000)
    parser.add_argument("--fraud_rate", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out_dir", type=str, default="data")
    args = parser.parse_args()

    print("Generating data...")
    df = generate(n=args.n, fraud_rate=args.fraud_rate, seed=args.seed)
    split_and_save(df, out_dir=args.out_dir)
