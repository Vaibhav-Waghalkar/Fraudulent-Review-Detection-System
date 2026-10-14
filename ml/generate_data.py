"""
Phase 1: Generate synthetic review data.
Default: Standard Faker logic with ext_word_list repetitive spam and Poisson(8) burst velocity,
legit paragraph of 3 sentences with rating 1 to 5.
Optional --hard-cases flag for edge cases.
50,000 rows, 5% fraud, seed 42. Stratified 80/10/10 split.
"""
import random
import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker
from sklearn.model_selection import train_test_split

fake = Faker()

SPAM_WORDS = [
    "incredible", "amazing", "best", "deal", "discount", "offer",
    "recommend", "guaranteed", "bonus", "free", "winner", "urgent"
]

def generate_default(n: int = 50_000, fraud_rate: float = 0.05, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)

    n_fraud = int(n * fraud_rate)
    n_legit = n - n_fraud

    rows = []

    # Legit reviews: 3 sentences paragraph, rating 1 to 5, low velocity
    for _ in range(n_legit):
        user_id = fake.uuid4()[:8]
        text = fake.paragraph(nb_sentences=3)
        rating = random.randint(1, 5)
        # Low Poisson velocity (mostly 0-2)
        velocity = int(np.random.poisson(lam=1.0))
        rows.append({
            "user_id": user_id,
            "text": text,
            "rating": rating,
            "velocity": velocity,
            "label": 0
        })

    # Fraud reviews: repeated words from ext_word_list, rating 5, Poisson(8) velocity
    fraud_users = [fake.uuid4()[:8] for _ in range(50)]
    for _ in range(n_fraud):
        user_id = random.choice(fraud_users)
        # Repeated words from ext_word_list
        text = fake.sentence(nb_words=12, ext_word_list=SPAM_WORDS)
        rating = 5
        velocity = int(np.random.poisson(lam=8.0))
        rows.append({
            "user_id": user_id,
            "text": text,
            "rating": rating,
            "velocity": velocity,
            "label": 1
        })

    df = pd.DataFrame(rows)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def generate_hard_cases(n: int = 50_000, fraud_rate: float = 0.05, seed: int = 42) -> pd.DataFrame:
    """Optional hard cases: rating mismatch, short complaints, varied spam templates."""
    # Keeps the template-based generation logic for edge-testing
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)

    n_fraud = int(n * fraud_rate)
    n_legit = n - n_fraud
    rows = []

    for _ in range(n_legit):
        user_id = fake.uuid4()[:8]
        rating = random.choice([3, 4, 5])
        text = fake.paragraph(nb_sentences=3)
        vel = int(np.random.poisson(lam=1.0))
        rows.append({"user_id": user_id, "text": text, "rating": rating, "velocity": vel, "label": 0})

    fraud_users = [fake.uuid4()[:8] for _ in range(50)]
    for _ in range(n_fraud):
        user_id = random.choice(fraud_users)
        rating = random.choice([1, 5])
        text = fake.sentence(nb_words=14, ext_word_list=SPAM_WORDS) + " " + " ".join(random.sample(SPAM_WORDS, 4))
        vel = int(np.random.poisson(lam=8.0))
        rows.append({"user_id": user_id, "text": text, "rating": rating, "velocity": vel, "label": 1})

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
    parser.add_argument("--hard-cases", action="store_true", help="Include optional hard cases")
    args = parser.parse_args()

    print("Generating data...")
    if args.hard_cases:
        df = generate_hard_cases(n=args.n, fraud_rate=args.fraud_rate, seed=args.seed)
    else:
        df = generate_default(n=args.n, fraud_rate=args.fraud_rate, seed=args.seed)
    split_and_save(df, out_dir=args.out_dir)
