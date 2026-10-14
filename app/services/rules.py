"""
Rule-based scoring and explanation service.
Rules:
  - repetitive_phrasing: repeated words exceed threshold
  - high_velocity: user submitted many reviews in 24h
  - extreme_rating_generic_text: rating 1 or 5 with generic short text
  - unusual_sentiment: extreme VADER polarity
Each rule returns the actual triggering value.
"""
import re
from collections import Counter
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

# Thresholds
REPETITION_THRESHOLD = 0.35   # fraction of duplicate words
VELOCITY_THRESHOLD = 5        # reviews/day considered high
EXTREME_RATING_LEN_THRESHOLD = 80  # chars -- "generic text" if shorter
VADER_EXTREME_THRESHOLD = 0.85  # |compound| > this is unusual


def check_repetitive_phrasing(text: str) -> dict | None:
    words = re.findall(r"\b[a-z]+\b", text.lower())
    if not words:
        return None
    counts = Counter(words)
    repeated = sum(v - 1 for v in counts.values() if v > 1)
    ratio = repeated / len(words)
    if ratio >= REPETITION_THRESHOLD:
        return {
            "rule": "repetitive_phrasing",
            "description": "Excessive word repetition detected.",
            "value": round(ratio, 3),
            "threshold": REPETITION_THRESHOLD,
        }
    return None


def check_high_velocity(velocity: int) -> dict | None:
    if velocity >= VELOCITY_THRESHOLD:
        return {
            "rule": "high_velocity",
            "description": f"User submitted {velocity} reviews in the last 24 hours.",
            "value": velocity,
            "threshold": VELOCITY_THRESHOLD,
        }
    return None


def check_extreme_rating_generic_text(text: str, rating: int) -> dict | None:
    if rating in (1, 5) and len(text.strip()) < EXTREME_RATING_LEN_THRESHOLD:
        return {
            "rule": "extreme_rating_generic_text",
            "description": "Extreme rating paired with very short or generic text.",
            "value": {"rating": rating, "text_length": len(text.strip())},
            "threshold": {"ratings": [1, 5], "min_length": EXTREME_RATING_LEN_THRESHOLD},
        }
    return None


def check_unusual_sentiment(text: str) -> dict | None:
    scores = _analyzer.polarity_scores(text)
    compound = scores["compound"]
    if abs(compound) >= VADER_EXTREME_THRESHOLD:
        return {
            "rule": "unusual_sentiment",
            "description": "Unusually extreme sentiment polarity.",
            "value": round(compound, 4),
            "threshold": VADER_EXTREME_THRESHOLD,
        }
    return None


def score_rules(text: str, rating: int, velocity: int) -> tuple[float, list[dict]]:
    """
    Returns (rule_score 0-1, list of triggered rule explanations).
    Rule score is 0.25 per triggered rule, capped at 1.0.
    """
    triggered = []

    checks = [
        check_repetitive_phrasing(text),
        check_high_velocity(velocity),
        check_extreme_rating_generic_text(text, rating),
        check_unusual_sentiment(text),
    ]

    for result in checks:
        if result is not None:
            triggered.append(result)

    rule_score = min(len(triggered) * 0.25, 1.0)
    return rule_score, triggered
