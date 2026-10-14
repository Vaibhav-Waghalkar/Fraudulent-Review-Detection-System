"""
Phase 3: Training pipeline.

Steps:
  1. Load preprocessed CSVs.
  2. Train FraudDetector (class-weighted cross-entropy) for N epochs.
  3. Extract DistilBERT embeddings for train/val/test.
  4. Apply SMOTE on train embeddings + velocity.
  5. Train FusionHead on SMOTE-augmented embeddings.
  6. Evaluate both models on val and test (AUC-ROC, F1, CM, PR curve).
  7. Plot class distribution before/after SMOTE and PCA scatter.
  8. Robustness check.
  9. Save reference_scores.npy for drift detection.
 10. Save fusion model checkpoint.
"""
import os
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pickle
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import DistilBertTokenizerFast, DistilBertModel
from sklearn.metrics import (
    roc_auc_score,
    f1_score,
    confusion_matrix,
    precision_recall_curve,
    average_precision_score,
)
from sklearn.decomposition import PCA
from imblearn.over_sampling import SMOTE
from tqdm import tqdm

from ml.model import FraudDetector, FusionHead
from ml.preprocess import load_tokenizer, compute_features, apply_scaler

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.cuda.set_per_process_memory_fraction(0.85, 0)
MAX_LENGTH = 512
BATCH_SIZE = 16
EMBEDDING_BATCH = 64


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class ReviewDataset(Dataset):
    def __init__(self, df: pd.DataFrame, tokenizer, max_length: int = MAX_LENGTH):
        self.encodings = tokenizer(
            df["text"].tolist(),
            truncation=True,
            max_length=max_length,
            padding=True,
            return_tensors="pt",
        )
        self.velocity = torch.tensor(df["velocity"].values, dtype=torch.float32)
        self.labels = torch.tensor(df["label"].values, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            "input_ids": self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "velocity": self.velocity[idx],
            "label": self.labels[idx],
        }


# ---------------------------------------------------------------------------
# Embedding extraction
# ---------------------------------------------------------------------------

def extract_embeddings(
    df: pd.DataFrame,
    bert: DistilBertModel,
    tokenizer,
    batch_size: int = EMBEDDING_BATCH,
) -> np.ndarray:
    bert.eval()
    all_cls = []
    texts = df["text"].tolist()

    for i in tqdm(range(0, len(texts), batch_size), desc="Extracting embeddings"):
        batch_texts = texts[i : i + batch_size]
        enc = tokenizer(
            batch_texts,
            truncation=True,
            max_length=MAX_LENGTH,
            padding=True,
            return_tensors="pt",
        )
        enc = {k: v.to(DEVICE) for k, v in enc.items()}
        with torch.no_grad():
            with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                out = bert(**enc)
        cls = out.last_hidden_state[:, 0, :].float().cpu().numpy()
        all_cls.append(cls)

    return np.vstack(all_cls)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_fraud_detector(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    tokenizer,
    epochs: int = 3,
    lr: float = 2e-5,
) -> FraudDetector:
    print("\n--- Training FraudDetector (class-weighted, fp16) ---")

    train_ds = ReviewDataset(train_df, tokenizer)
    val_ds = ReviewDataset(val_df, tokenizer)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE * 2)

    model = FraudDetector().to(DEVICE)

    # Class weights: inverse frequency
    n_neg = (train_df["label"] == 0).sum()
    n_pos = (train_df["label"] == 1).sum()
    weight = torch.tensor([1.0, n_neg / n_pos], dtype=torch.float32).to(DEVICE)
    criterion = nn.CrossEntropyLoss(weight=weight)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())

    best_auc = 0.0
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for batch in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}"):
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            velocity = batch["velocity"].to(DEVICE)
            labels = batch["label"].to(DEVICE)

            optimizer.zero_grad()
            with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                logits = model(input_ids, attention_mask, velocity)
                loss = criterion(logits, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            total_loss += loss.item()

        # Validation
        model.eval()
        all_probs, all_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                    logits = model(
                        batch["input_ids"].to(DEVICE),
                        batch["attention_mask"].to(DEVICE),
                        batch["velocity"].to(DEVICE),
                    )
                probs = torch.softmax(logits, dim=1)[:, 1].float().cpu().numpy()
                all_probs.extend(probs)
                all_labels.extend(batch["label"].numpy())

        auc = roc_auc_score(all_labels, all_probs)
        print(f"  Epoch {epoch+1}: loss={total_loss/len(train_loader):.4f}  val_auc={auc:.4f}")

        if auc > best_auc:
            best_auc = auc
            torch.save(model.state_dict(), "models/fraud_detector_best.pt")

    model.load_state_dict(torch.load("models/fraud_detector_best.pt", map_location=DEVICE))
    return model


def train_fusion_head(
    train_emb: np.ndarray,
    train_vel: np.ndarray,
    train_labels: np.ndarray,
    val_emb: np.ndarray,
    val_vel: np.ndarray,
    val_labels: np.ndarray,
    epochs: int = 10,
    lr: float = 1e-3,
) -> FusionHead:
    print("\n--- Training FusionHead (SMOTE augmented) ---")

    # Concatenate embeddings + velocity
    X_train = np.hstack([train_emb, train_vel.reshape(-1, 1)])
    X_val = np.hstack([val_emb, val_vel.reshape(-1, 1)])

    # SMOTE
    print(f"  Before SMOTE: {np.bincount(train_labels.astype(int))}")
    smote = SMOTE(random_state=42)
    X_resampled, y_resampled = smote.fit_resample(X_train, train_labels.astype(int))
    print(f"  After SMOTE : {np.bincount(y_resampled)}")

    # Convert to tensors
    X_t = torch.tensor(X_resampled, dtype=torch.float32)
    y_t = torch.tensor(y_resampled, dtype=torch.long)
    X_v = torch.tensor(X_val, dtype=torch.float32)
    y_v = torch.tensor(val_labels.astype(int), dtype=torch.long)

    from torch.utils.data import TensorDataset
    train_ds = TensorDataset(X_t, y_t)
    val_ds = TensorDataset(X_v, y_v)

    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=512)

    model = FusionHead(input_dim=769).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    best_auc = 0.0
    for epoch in range(epochs):
        model.train()
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            loss = criterion(model(Xb), yb)
            loss.backward()
            optimizer.step()

        model.eval()
        probs_all, labs_all = [], []
        with torch.no_grad():
            for Xb, yb in val_loader:
                p = torch.softmax(model(Xb.to(DEVICE)), dim=1)[:, 1].cpu().numpy()
                probs_all.extend(p)
                labs_all.extend(yb.numpy())
        auc = roc_auc_score(labs_all, probs_all)
        if (epoch + 1) % 2 == 0:
            print(f"  Epoch {epoch+1}: val_auc={auc:.4f}")
        if auc > best_auc:
            best_auc = auc
            torch.save(model.state_dict(), "models/fusion_head_best.pt")

    model.load_state_dict(torch.load("models/fusion_head_best.pt", map_location=DEVICE))
    return model, X_resampled, y_resampled


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate(name: str, labels: np.ndarray, probs: np.ndarray, out_dir: str) -> dict:
    auc = roc_auc_score(labels, probs)
    preds = (probs >= 0.5).astype(int)
    f1 = f1_score(labels, preds, pos_label=1)
    cm = confusion_matrix(labels, preds)
    ap = average_precision_score(labels, probs)

    print(f"\n[{name}] AUC-ROC={auc:.4f}  F1(fraud)={f1:.4f}  AP={ap:.4f}")
    print(f"  Confusion matrix:\n{cm}")

    # PR curve
    precision, recall, _ = precision_recall_curve(labels, probs)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(recall, precision, linewidth=1.5, color="#2F5D50")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(f"{name} PR Curve (AP={ap:.3f})")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, f"pr_curve_{name.lower().replace(' ', '_')}.png"), dpi=120)
    plt.close(fig)

    return {"auc": auc, "f1": f1, "ap": ap, "cm": cm.tolist()}


def plot_class_distribution(
    y_before: np.ndarray, y_after: np.ndarray, out_dir: str
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, y, title in zip(
        axes, [y_before, y_after], ["Before SMOTE", "After SMOTE"]
    ):
        counts = np.bincount(y.astype(int))
        ax.bar(["Legit", "Fraud"], counts, color=["#2F5D50", "#B23A2E"])
        ax.set_title(title)
        ax.set_ylabel("Count")
        for i, c in enumerate(counts):
            ax.text(i, c + 20, str(c), ha="center")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "class_distribution.png"), dpi=120)
    plt.close(fig)
    print(f"Class distribution plot saved.")


def plot_pca(
    embeddings: np.ndarray, labels: np.ndarray, out_dir: str, title: str = "PCA"
) -> None:
    pca = PCA(n_components=2, random_state=42)
    reduced = pca.fit_transform(embeddings[:2000])
    labs = labels[:2000]

    fig, ax = plt.subplots(figsize=(7, 6))
    for cls, color, label in [(0, "#2F5D50", "Legit"), (1, "#B23A2E", "Fraud")]:
        mask = labs == cls
        ax.scatter(reduced[mask, 0], reduced[mask, 1], c=color, label=label,
                   alpha=0.4, s=10, linewidths=0)
    ax.legend()
    ax.set_title(title)
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "pca_scatter.png"), dpi=120)
    plt.close(fig)
    print("PCA scatter saved.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args):
    Path("models").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)

    # Load data
    data_dir = args.data_dir
    train_df = pd.read_csv(os.path.join(data_dir, "train_preprocessed.csv"))
    val_df = pd.read_csv(os.path.join(data_dir, "val_preprocessed.csv"))
    test_df = pd.read_csv(os.path.join(data_dir, "test_preprocessed.csv"))

    tokenizer = load_tokenizer()

    # -----------------------------------------------------------------------
    # Step 1: Train FraudDetector (class-weighted, full fine-tune)
    # -----------------------------------------------------------------------
    if args.skip_full_train:
        print("Skipping full fine-tune (--skip_full_train).")
        detector = FraudDetector().to(DEVICE)
        detector.load_state_dict(torch.load("models/fraud_detector_best.pt", map_location=DEVICE))
    else:
        detector = train_fraud_detector(
            train_df, val_df, tokenizer, epochs=args.epochs, lr=args.lr
        )

    # -----------------------------------------------------------------------
    # Step 2: Extract embeddings using the trained DistilBERT backbone
    # -----------------------------------------------------------------------
    print("\nExtracting embeddings...")
    bert = detector.bert.to(DEVICE)

    train_emb = extract_embeddings(train_df, bert, tokenizer)
    val_emb = extract_embeddings(val_df, bert, tokenizer)
    test_emb = extract_embeddings(test_df, bert, tokenizer)

    train_vel = train_df["velocity"].values
    val_vel = val_df["velocity"].values
    test_vel = test_df["velocity"].values
    train_labels = train_df["label"].values
    val_labels = val_df["label"].values
    test_labels = test_df["label"].values

    # Save embeddings for reuse
    np.save("models/train_emb.npy", train_emb)
    np.save("models/val_emb.npy", val_emb)
    np.save("models/test_emb.npy", test_emb)

    # -----------------------------------------------------------------------
    # Step 3: SMOTE + FusionHead
    # -----------------------------------------------------------------------
    if args.skip_fusion_train:
        print("Skipping fusion head training (--skip_fusion_train).")
        fusion = FusionHead(input_dim=769).to(DEVICE)
        fusion.load_state_dict(torch.load("models/fusion_head_best.pt", map_location=DEVICE))
        X_resampled = np.hstack([train_emb, train_vel.reshape(-1, 1)])
        y_resampled = train_labels
    else:
        fusion, X_resampled, y_resampled = train_fusion_head(
            train_emb, train_vel, train_labels,
            val_emb, val_vel, val_labels,
            epochs=args.fusion_epochs,
        )

    # -----------------------------------------------------------------------
    # Step 4: Plots
    # -----------------------------------------------------------------------
    plot_class_distribution(train_labels, y_resampled, out_dir="reports")
    plot_pca(train_emb, train_labels, out_dir="reports", title="PCA of Training Embeddings")

    # -----------------------------------------------------------------------
    # Step 5: Evaluate FraudDetector on val and test
    # -----------------------------------------------------------------------
    print("\nEvaluating FraudDetector...")
    detector.eval()
    results = {}

    for split_name, df, emb, vel, labs in [
        ("detector_val", val_df, val_emb, val_vel, val_labels),
        ("detector_test", test_df, test_emb, test_vel, test_labels),
    ]:
        dataset = ReviewDataset(df, tokenizer)
        loader = DataLoader(dataset, batch_size=64)
        all_probs = []
        with torch.no_grad():
            for batch in loader:
                logits = detector(
                    batch["input_ids"].to(DEVICE),
                    batch["attention_mask"].to(DEVICE),
                    batch["velocity"].to(DEVICE),
                )
                probs = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
                all_probs.extend(probs)
        results[split_name] = evaluate(split_name, labs, np.array(all_probs), "reports")

    # -----------------------------------------------------------------------
    # Step 6: Evaluate FusionHead on val and test
    # -----------------------------------------------------------------------
    print("\nEvaluating FusionHead...")
    fusion.eval()
    for split_name, emb, vel, labs in [
        ("fusion_val", val_emb, val_vel, val_labels),
        ("fusion_test", test_emb, test_vel, test_labels),
    ]:
        X = np.hstack([emb, vel.reshape(-1, 1)])
        xt = torch.tensor(X, dtype=torch.float32).to(DEVICE)
        with torch.no_grad():
            probs = torch.softmax(fusion(xt), dim=1)[:, 1].cpu().numpy()
        results[split_name] = evaluate(split_name, labs, probs, "reports")

    # -----------------------------------------------------------------------
    # Step 7: Save reference_scores.npy (training set fusion scores)
    # -----------------------------------------------------------------------
    X_train_full = np.hstack([train_emb, train_vel.reshape(-1, 1)])
    xt_train = torch.tensor(X_train_full, dtype=torch.float32).to(DEVICE)
    with torch.no_grad():
        ref_probs = torch.softmax(fusion(xt_train), dim=1)[:, 1].cpu().numpy()
    np.save("models/reference_scores.npy", ref_probs)
    print(f"\nSaved reference_scores.npy (n={len(ref_probs):,})")

    # -----------------------------------------------------------------------
    # Step 8: Robustness check
    # -----------------------------------------------------------------------
    print("\n--- Robustness Check ---")
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    import pickle

    with open("models/scaler.pkl", "rb") as f:
        scaler = pickle.load(f)

    analyzer = SentimentIntensityAnalyzer()

    paraphrase_texts = [
        "Incredible item! Definitely worth every penny. Highly recommend to all!",
        "Five star product. Wonderful in every way. Just purchase it.",
        "Top notch quality. Superb value. Tell your friends about it.",
    ]

    paraphrase_df = pd.DataFrame({
        "text": paraphrase_texts,
        "velocity": [0.0, 0.0, 0.0],
        "label": [1, 1, 1],
    })
    paraphrase_df["text_length"] = paraphrase_df["text"].str.len()
    paraphrase_df["vader_compound"] = paraphrase_df["text"].apply(
        lambda t: analyzer.polarity_scores(t)["compound"]
    )
    paraphrase_df[["text_length", "vader_compound", "velocity"]] = scaler.transform(
        paraphrase_df[["text_length", "vader_compound", "velocity"]].values
    )

    par_emb = extract_embeddings(paraphrase_df, bert, tokenizer, batch_size=4)
    par_vel = paraphrase_df["velocity"].values
    X_par = np.hstack([par_emb, par_vel.reshape(-1, 1)])
    xt_par = torch.tensor(X_par, dtype=torch.float32).to(DEVICE)
    with torch.no_grad():
        par_probs = torch.softmax(fusion(xt_par), dim=1)[:, 1].cpu().numpy()
    print("  Paraphrase spam scores:", [f"{p:.3f}" for p in par_probs])

    # Velocity-masked test: set velocity to 0 for fraud samples
    mask_vel = np.zeros_like(test_vel)
    X_masked = np.hstack([test_emb, mask_vel.reshape(-1, 1)])
    xt_masked = torch.tensor(X_masked, dtype=torch.float32).to(DEVICE)
    with torch.no_grad():
        masked_probs = torch.softmax(fusion(xt_masked), dim=1)[:, 1].cpu().numpy()
    masked_auc = roc_auc_score(test_labels, masked_probs)
    masked_f1 = f1_score(test_labels, (masked_probs >= 0.5).astype(int), pos_label=1)
    print(f"  Velocity-masked test AUC={masked_auc:.4f}  F1(fraud)={masked_f1:.4f}")

    results["robustness"] = {
        "paraphrase_scores": par_probs.tolist(),
        "velocity_masked_auc": masked_auc,
        "velocity_masked_f1": masked_f1,
    }

    # -----------------------------------------------------------------------
    # Step 9: Save summary
    # -----------------------------------------------------------------------
    with open("reports/training_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nAll results saved to reports/training_results.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", dest="data_dir", default="data",
                        help="Directory with preprocessed CSVs")
    parser.add_argument("--epochs", type=int, default=3,
                        help="FraudDetector training epochs")
    parser.add_argument("--fusion_epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--skip_full_train", action="store_true",
                        help="Skip FraudDetector training, load checkpoint")
    parser.add_argument("--skip_fusion_train", action="store_true",
                        help="Skip FusionHead training, load checkpoint")
    args = parser.parse_args()

    # Ensure data is preprocessed
    if not os.path.exists(os.path.join(args.data_dir, "train_preprocessed.csv")):
        print("Preprocessed data not found. Running preprocess.py first...")
        from ml.preprocess import preprocess
        preprocess(data_dir=args.data_dir)

    main(args)
