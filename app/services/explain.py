"""
On-demand LIME explanation service.
"""
import logging
import pickle
import os
from typing import Any

import numpy as np

from app.core.config import settings
from app.services import inference as inference_svc

logger = logging.getLogger(__name__)


def explain_review(
    text: str,
    velocity: float,
    num_features: int = 10,
    num_samples: int = 200,
) -> dict[str, Any]:
    """
    Run LIME explanation for a review text.
    Returns dict with top word importances.
    """
    if not inference_svc.is_model_loaded():
        return {"error": "Model not loaded. LIME explanation unavailable."}

    try:
        from ml.explain import explain_text
        from transformers import DistilBertTokenizerFast
        import onnxruntime as ort

        session = inference_svc._session
        tokenizer = inference_svc._tokenizer
        scaler = inference_svc._scaler

        result = explain_text(
            text=text,
            velocity=velocity,
            onnx_session=session,
            tokenizer=tokenizer,
            scaler=scaler,
            num_features=num_features,
            num_samples=num_samples,
        )
        return result

    except Exception as e:
        logger.error("LIME explanation failed: %s", e)
        return {"error": str(e)}
