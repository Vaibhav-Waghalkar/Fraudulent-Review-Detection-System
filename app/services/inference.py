"""
ONNX inference service with fallback to rules-only scoring.
Loads quantized model by default, falls back to FP32 if unavailable.
"""
import logging
import os
import pickle
from typing import Optional

import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.core.config import settings

logger = logging.getLogger(__name__)

_session = None
_scaler = None
_tokenizer = None
_analyzer = SentimentIntensityAnalyzer()
_model_loaded = False


def load_model() -> bool:
    global _session, _scaler, _tokenizer, _model_loaded

    # Try quantized first, then FP32
    model_paths = [settings.quantized_model_path, settings.model_path]

    for path in model_paths:
        if os.path.exists(path):
            try:
                import onnxruntime as ort
                opts = ort.SessionOptions()
                opts.log_severity_level = 3
                opts.intra_op_num_threads = min(8, os.cpu_count() or 4)
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                _session = ort.InferenceSession(
                    path,
                    sess_options=opts,
                    providers=["CPUExecutionProvider"],
                )
                logger.info("Loaded ONNX model: %s", path)
                break
            except Exception as e:
                logger.warning("Failed to load %s: %s", path, e)

    if _session is None:
        logger.warning("No ONNX model loaded. Will use rules-only fallback.")
        _model_loaded = False
        return False

    # Load scaler
    if os.path.exists(settings.scaler_path):
        try:
            with open(settings.scaler_path, "rb") as f:
                _scaler = pickle.load(f)
            logger.info("Scaler loaded: %s", settings.scaler_path)
        except Exception as e:
            logger.warning("Scaler load failed: %s", e)

    # Load tokenizer
    try:
        from transformers import DistilBertTokenizerFast
        _tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")
        logger.info("Tokenizer loaded.")
    except Exception as e:
        logger.warning("Tokenizer load failed: %s", e)
        _model_loaded = False
        return False

    _model_loaded = True
    return True


def is_model_loaded() -> bool:
    return _model_loaded


def infer(text: str, velocity: float) -> tuple[float, bool]:
    """
    Returns (fraud_probability, fallback_used).
    fallback_used=True means we returned rules-only score.
    """
    if not _model_loaded or _session is None or _scaler is None or _tokenizer is None:
        return _rules_fallback_score(text, velocity), True

    try:
        # Scale features
        text_len = len(text)
        vader = _analyzer.polarity_scores(text)["compound"]
        features = np.array([[text_len, vader, velocity]], dtype=np.float64)
        scaled = _scaler.transform(features)
        scaled_vel = float(scaled[0, 2])

        # Tokenize with dynamic max_length
        enc = _tokenizer(
            [text],
            truncation=True,
            max_length=128,
            padding=True,
            return_tensors="np",
        )

        out = _session.run(
            None,
            {
                "input_ids": enc["input_ids"].astype(np.int64),
                "attention_mask": enc["attention_mask"].astype(np.int64),
                "velocity": np.array([scaled_vel], dtype=np.float32),
            },
        )[0]

        fraud_prob = float(out[0, 1])
        return fraud_prob, False

    except Exception as e:
        logger.error("ONNX inference failed: %s. Using rules fallback.", e)
        return _rules_fallback_score(text, velocity), True


def infer_batch(texts: list[str], velocities: list[float]) -> list[tuple[float, bool]]:
    """
    Batch inference for multiple reviews in a single ONNX forward pass.
    """
    if not _model_loaded or _session is None or _scaler is None or _tokenizer is None:
        return [(_rules_fallback_score(t, v), True) for t, v in zip(texts, velocities)]

    try:
        features = []
        for text, vel in zip(texts, velocities):
            text_len = len(text)
            vader = _analyzer.polarity_scores(text)["compound"]
            features.append([text_len, vader, vel])

        scaled = _scaler.transform(np.array(features, dtype=np.float64))
        scaled_vels = scaled[:, 2].astype(np.float32)

        # Dynamic batch padding to longest text in batch (max 128)
        enc = _tokenizer(
            texts,
            truncation=True,
            max_length=128,
            padding=True,
            return_tensors="np",
        )

        out = _session.run(
            None,
            {
                "input_ids": enc["input_ids"].astype(np.int64),
                "attention_mask": enc["attention_mask"].astype(np.int64),
                "velocity": scaled_vels,
            },
        )[0]

        return [(float(prob[1]), False) for prob in out]

    except Exception as e:
        logger.error("ONNX batch inference failed: %s. Using rules fallback.", e)
        return [(_rules_fallback_score(t, v), True) for t, v in zip(texts, velocities)]


def _rules_fallback_score(text: str, velocity: float) -> float:
    """Simple heuristic fallback when ONNX model is unavailable."""
    from app.services.rules import score_rules
    rule_score, _ = score_rules(text, rating=3, velocity=int(velocity))
    return rule_score
