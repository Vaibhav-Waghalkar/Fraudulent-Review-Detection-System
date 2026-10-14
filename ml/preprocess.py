"""
Phase 2: Preprocessing.
- DistilBERT tokenizer (truncate 512, dynamic padding)
- Features: text_length, VADER compound polarity, velocity (standardized)
- Saves StandardScaler to models/scaler.pkl
"""
import os
import pickle
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from transformers import DistilBertTokenizerFast
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.preprocessing import StandardScaler


TOKENIZER_NAME = "distilbert-base-uncased"
MAX_LENGTH = 512


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute auxiliary scalar features (text_length, vader_compound, velocity)."""
    analyzer = SentimentIntensityAnalyzer()

    df = df.copy()
    df["text_length"] = df["text"].str.len()
    df["vader_compound"] = df["text"].apply(
        lambda t: analyzer.polarity_scores(str(t))["compound"]
    )
    # velocity already numeric; standardize in fit_scaler
    df["velocity"] = df["velocity"].astype(float)
    return df


def fit_scaler(train_df: pd.DataFrame, model_dir: str = "models") -> StandardScaler:
    """Fit StandardScaler on training set and save."""
    Path(model_dir).mkdir(parents=True, exist_ok=True)

    feature_cols = ["text_length", "vader_compound", "velocity"]
    scaler = StandardScaler()
    scaler.fit(train_df[feature_cols].values)

    scaler_path = os.path.join(model_dir, "scaler.pkl")
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Scaler saved to {scaler_path}")
    return scaler


def apply_scaler(df: pd.DataFrame, scaler: StandardScaler) -> pd.DataFrame:
    """Apply a fitted scaler to scale feature columns."""
    feature_cols = ["text_length", "vader_compound", "velocity"]
    df = df.copy()
    df[feature_cols] = scaler.transform(df[feature_cols].values)
    return df


def tokenize_batch(texts: list[str], tokenizer) -> dict:
    """Tokenize a list of texts. Returns dict of tensors."""
    return tokenizer(
        texts,
        truncation=True,
        max_length=MAX_LENGTH,
        padding=True,
        return_tensors="pt",
    )


def load_tokenizer(name: str = TOKENIZER_NAME):
    return DistilBertTokenizerFast.from_pretrained(name)


def preprocess(
    data_dir: str = "data",
    model_dir: str = "models",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, StandardScaler]:
    train_df = pd.read_csv(os.path.join(data_dir, "train.csv"))
    val_df = pd.read_csv(os.path.join(data_dir, "val.csv"))
    test_df = pd.read_csv(os.path.join(data_dir, "test.csv"))

    print("Computing features...")
    train_df = compute_features(train_df)
    val_df = compute_features(val_df)
    test_df = compute_features(test_df)

    print("Fitting and applying scaler...")
    scaler = fit_scaler(train_df, model_dir=model_dir)
    train_df = apply_scaler(train_df, scaler)
    val_df = apply_scaler(val_df, scaler)
    test_df = apply_scaler(test_df, scaler)

    # Save preprocessed csvs
    train_df.to_csv(os.path.join(data_dir, "train_preprocessed.csv"), index=False)
    val_df.to_csv(os.path.join(data_dir, "val_preprocessed.csv"), index=False)
    test_df.to_csv(os.path.join(data_dir, "test_preprocessed.csv"), index=False)

    print(f"Train shape: {train_df.shape}")
    print(f"Val shape  : {val_df.shape}")
    print(f"Test shape : {test_df.shape}")

    return train_df, val_df, test_df, scaler


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default="data")
    parser.add_argument("--model_dir", default="models")
    args = parser.parse_args()
    preprocess(data_dir=args.data_dir, model_dir=args.model_dir)
