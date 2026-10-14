"""
Tests for rule-based scoring service.
"""
import pytest
from app.services.rules import (
    check_repetitive_phrasing,
    check_high_velocity,
    check_extreme_rating_generic_text,
    check_unusual_sentiment,
    score_rules,
    REPETITION_THRESHOLD,
    VELOCITY_THRESHOLD,
)


class TestRepetitivePhrasing:
    def test_no_repetition(self):
        text = "This product arrived on time and works well."
        assert check_repetitive_phrasing(text) is None

    def test_high_repetition(self):
        text = "buy buy buy buy buy this now now now now"
        result = check_repetitive_phrasing(text)
        assert result is not None
        assert result["rule"] == "repetitive_phrasing"
        assert result["value"] >= REPETITION_THRESHOLD

    def test_empty_text(self):
        assert check_repetitive_phrasing("") is None

    def test_returns_actual_value(self):
        text = "amazing amazing amazing amazing amazing product product product"
        result = check_repetitive_phrasing(text)
        assert result is not None
        assert "value" in result
        assert isinstance(result["value"], float)


class TestHighVelocity:
    def test_low_velocity(self):
        assert check_high_velocity(1) is None

    def test_at_threshold(self):
        result = check_high_velocity(VELOCITY_THRESHOLD)
        assert result is not None
        assert result["rule"] == "high_velocity"
        assert result["value"] == VELOCITY_THRESHOLD

    def test_above_threshold(self):
        result = check_high_velocity(20)
        assert result is not None
        assert result["value"] == 20


class TestExtremeRatingGenericText:
    def test_normal_rating_short_text(self):
        assert check_extreme_rating_generic_text("Ok", 3) is None

    def test_extreme_rating_short_text(self):
        result = check_extreme_rating_generic_text("Good.", 5)
        assert result is not None
        assert result["rule"] == "extreme_rating_generic_text"
        assert result["value"]["rating"] == 5

    def test_extreme_rating_long_text(self):
        long_text = "This product is excellent. " * 10
        assert check_extreme_rating_generic_text(long_text, 5) is None


class TestUnusualSentiment:
    def test_neutral_text(self):
        text = "The product arrived and I used it."
        assert check_unusual_sentiment(text) is None

    def test_very_positive(self):
        text = "Absolutely incredible! Best thing ever! Amazing! Perfect! Love it!"
        result = check_unusual_sentiment(text)
        assert result is not None
        assert result["rule"] == "unusual_sentiment"
        assert result["value"] > 0

    def test_returns_compound_value(self):
        text = "Absolutely incredible! Best thing ever! Amazing!"
        result = check_unusual_sentiment(text)
        if result:
            assert isinstance(result["value"], float)
            assert -1.0 <= result["value"] <= 1.0


class TestScoreRules:
    def test_clean_review_low_score(self):
        score, rules = score_rules(
            text="Good product. Works as expected.",
            rating=4,
            velocity=0,
        )
        assert score == 0.0
        assert rules == []

    def test_fraud_review_high_score(self):
        text = "buy buy buy buy buy this amazing amazing amazing limited time offer!!!"
        score, rules = score_rules(text=text, rating=5, velocity=10)
        assert score > 0
        assert len(rules) > 0

    def test_score_bounded(self):
        text = "buy now buy now buy now best best best limited limited limited amazing"
        score, _ = score_rules(text=text, rating=1, velocity=100)
        assert 0.0 <= score <= 1.0

    def test_rule_has_required_fields(self):
        _, rules = score_rules(
            text="buy buy buy buy buy",
            rating=5,
            velocity=10,
        )
        for rule in rules:
            assert "rule" in rule
            assert "description" in rule
            assert "value" in rule
            assert "threshold" in rule
