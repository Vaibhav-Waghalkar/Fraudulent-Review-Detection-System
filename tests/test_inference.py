"""
Tests for the inference service (mocked ONNX session).
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


class TestInferenceService:
    def test_infer_returns_probability_and_fallback_flag(self):
        """When model is loaded, infer returns (float, False)."""
        mock_session = MagicMock()
        mock_session.run.return_value = [np.array([[0.3, 0.7]])]

        mock_scaler = MagicMock()
        mock_scaler.transform.return_value = np.array([[0.1, 0.2, 0.3]])

        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {
            "input_ids": np.zeros((1, 8), dtype=np.int64),
            "attention_mask": np.ones((1, 8), dtype=np.int64),
        }

        with patch("app.services.inference._model_loaded", True), \
             patch("app.services.inference._session", mock_session), \
             patch("app.services.inference._scaler", mock_scaler), \
             patch("app.services.inference._tokenizer", mock_tokenizer):

            from app.services.inference import infer
            score, fallback = infer("Great product!", 2.0)

            assert isinstance(score, float)
            assert not fallback

    def test_fallback_when_model_not_loaded(self):
        """When model is not loaded, infer returns rules score with fallback=True."""
        with patch("app.services.inference._model_loaded", False), \
             patch("app.services.inference._session", None):

            from app.services.inference import infer
            score, fallback = infer("buy buy buy buy buy buy", 10.0)

            assert isinstance(score, float)
            assert fallback is True

    def test_fallback_on_exception(self):
        """If ONNX session throws, returns rules fallback."""
        mock_session = MagicMock()
        mock_session.run.side_effect = RuntimeError("ONNX error")

        mock_scaler = MagicMock()
        mock_scaler.transform.return_value = np.array([[0.1, 0.2, 0.3]])

        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {
            "input_ids": np.zeros((1, 8), dtype=np.int64),
            "attention_mask": np.ones((1, 8), dtype=np.int64),
        }

        with patch("app.services.inference._model_loaded", True), \
             patch("app.services.inference._session", mock_session), \
             patch("app.services.inference._scaler", mock_scaler), \
             patch("app.services.inference._tokenizer", mock_tokenizer):

            from app.services.inference import infer
            score, fallback = infer("Some review text", 1.0)

            assert isinstance(score, float)
            assert fallback is True

    def test_is_model_loaded_false_initially(self):
        with patch("app.services.inference._model_loaded", False):
            from app.services.inference import is_model_loaded
            assert not is_model_loaded()

    def test_score_range(self):
        """Score must always be between 0 and 1."""
        mock_session = MagicMock()
        # Model returns extreme probability
        mock_session.run.return_value = [np.array([[0.0, 1.0]])]

        mock_scaler = MagicMock()
        mock_scaler.transform.return_value = np.array([[0.1, 0.2, 0.3]])

        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {
            "input_ids": np.zeros((1, 8), dtype=np.int64),
            "attention_mask": np.ones((1, 8), dtype=np.int64),
        }

        with patch("app.services.inference._model_loaded", True), \
             patch("app.services.inference._session", mock_session), \
             patch("app.services.inference._scaler", mock_scaler), \
             patch("app.services.inference._tokenizer", mock_tokenizer):

            from app.services.inference import infer
            score, _ = infer("Test", 0.0)
            assert 0.0 <= score <= 1.0
