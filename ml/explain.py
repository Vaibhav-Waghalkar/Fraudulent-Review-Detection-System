"""
LIME-based explanation for the fusion model.
Provides text-level feature importance.
"""
import os
import pickle
import numpy as np
import torch
from lime.lime_text import LimeTextExplainer
from transformers import DistilBertTokenizerFast


def get_explainer() -> LimeTextExplainer:
    return LimeTextExplainer(class_names=["legit", "fraud"])


def explain_text(
    text: str,
    velocity: float,
    onnx_session,
    tokenizer: DistilBertTokenizerFast,
    scaler,
    num_features: int = 10,
    num_samples: int = 300,
) -> dict:
    """
    Run LIME explanation on a single text.
    Returns dict of {word: importance} for fraud class.
    """
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()

    def predict_fn(texts: list[str]) -> np.ndarray:
        results = []
        for t in texts:
            text_len = len(t)
            vader = analyzer.polarity_scores(t)["compound"]
            features = np.array([[text_len, vader, velocity]])
            scaled = scaler.transform(features)
            scaled_vel = float(scaled[0, 2])

            enc = tokenizer(
                [t],
                truncation=True,
                max_length=512,
                padding=True,
                return_tensors="np",
            )
            out = onnx_session.run(
                None,
                {
                    "input_ids": enc["input_ids"].astype(np.int64),
                    "attention_mask": enc["attention_mask"].astype(np.int64),
                    "velocity": np.array([scaled_vel], dtype=np.float32),
                },
            )[0]
            results.append(out[0])  # [p_legit, p_fraud]
        return np.array(results)

    explainer = get_explainer()
    exp = explainer.explain_instance(
        text,
        predict_fn,
        num_features=num_features,
        num_samples=num_samples,
        labels=[1],  # fraud class
    )

    word_importance = dict(exp.as_list(label=1))
    return {
        "top_features": word_importance,
        "local_explanation": [
            {"word": w, "importance": float(s)}
            for w, s in sorted(word_importance.items(), key=lambda x: abs(x[1]), reverse=True)
        ],
    }
