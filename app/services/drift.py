"""
Drift detection service using KS test.
Compares live scores from MongoDB against reference_scores.npy.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from scipy.stats import ks_2samp

from app.core.config import settings

logger = logging.getLogger(__name__)

_reference_scores: Optional[np.ndarray] = None


def load_reference_scores() -> bool:
    global _reference_scores
    path = settings.reference_scores_path
    if os.path.exists(path):
        _reference_scores = np.load(path)
        logger.info("Loaded reference scores: n=%d", len(_reference_scores))
        return True
    logger.warning("Reference scores not found: %s", path)
    return False


def get_reference_scores() -> Optional[np.ndarray]:
    return _reference_scores


def run_ks_test(live_scores: np.ndarray) -> dict:
    """
    Run KS test between live_scores and reference distribution.
    Returns dict with statistic, p_value, alert flag.
    """
    if _reference_scores is None:
        return {"error": "Reference scores not loaded", "alert": False}

    if len(live_scores) < 30:
        return {"error": "Not enough live scores (need >= 30)", "alert": False}

    stat, p_value = ks_2samp(_reference_scores, live_scores)

    alert = bool(p_value < settings.ks_p_value_threshold)
    return {
        "ks_statistic": float(stat),
        "p_value": float(p_value),
        "alert": alert,
        "n_reference": len(_reference_scores),
        "n_live": len(live_scores),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def send_mock_alerts(p_value: float, ks_stat: float) -> None:
    """Log mock email and Slack alerts when drift detected."""
    msg = (
        f"[DRIFT ALERT] KS p-value={p_value:.6f} < threshold={settings.ks_p_value_threshold}. "
        f"KS statistic={ks_stat:.4f}. Distribution shift detected in fraud scores."
    )
    logger.warning("[EMAIL ALERT] To: ops@reviewguard.internal | Subject: Drift Alert | %s", msg)
    logger.warning("[SLACK ALERT] #ml-ops | %s", msg)
