"""
Tests for drift detection service.
"""
import numpy as np
import pytest
from unittest.mock import patch


class TestDriftService:
    def test_ks_test_no_drift(self):
        """Similar distributions should not trigger alert."""
        from app.services.drift import run_ks_test
        ref = np.random.default_rng(42).random(1000) * 0.3
        live = np.random.default_rng(43).random(200) * 0.3

        with patch("app.services.drift._reference_scores", ref):
            result = run_ks_test(live)

        assert "p_value" in result
        assert result["p_value"] > 0.05
        assert result["alert"] is False

    def test_ks_test_detects_drift(self):
        """Strongly shifted distribution should trigger alert."""
        from app.services.drift import run_ks_test
        ref = np.random.default_rng(42).random(1000) * 0.3  # low scores
        live = 0.7 + np.random.default_rng(43).random(300) * 0.3  # high scores

        with patch("app.services.drift._reference_scores", ref):
            result = run_ks_test(live)

        assert result["p_value"] < 0.05
        assert result["alert"] is True

    def test_ks_test_not_enough_samples(self):
        """Too few live samples returns error."""
        from app.services.drift import run_ks_test
        ref = np.random.default_rng(42).random(1000)

        with patch("app.services.drift._reference_scores", ref):
            result = run_ks_test(np.array([0.5, 0.3]))  # only 2 samples

        assert "error" in result
        assert result["alert"] is False

    def test_ks_test_no_reference(self):
        """No reference scores loaded returns error."""
        from app.services.drift import run_ks_test

        with patch("app.services.drift._reference_scores", None):
            result = run_ks_test(np.random.random(100))

        assert "error" in result
        assert result["alert"] is False

    def test_load_reference_scores_missing_file(self):
        """Loading non-existent reference file returns False."""
        from app.services.drift import load_reference_scores

        with patch("app.services.drift.settings") as mock_settings:
            mock_settings.reference_scores_path = "/nonexistent/path.npy"
            result = load_reference_scores()

        assert result is False

    def test_load_reference_scores_success(self, tmp_path):
        """Successfully loading a valid .npy file."""
        from app.services.drift import load_reference_scores

        scores = np.random.random(500).astype(np.float32)
        path = tmp_path / "reference_scores.npy"
        np.save(str(path), scores)

        with patch("app.services.drift.settings") as mock_settings:
            mock_settings.reference_scores_path = str(path)
            result = load_reference_scores()

        assert result is True

    def test_send_mock_alerts_logs(self, caplog):
        """send_mock_alerts should log warnings."""
        import logging
        from app.services.drift import send_mock_alerts

        with caplog.at_level(logging.WARNING, logger="app.services.drift"):
            send_mock_alerts(p_value=0.001, ks_stat=0.45)

        assert any("DRIFT ALERT" in r.message or "EMAIL" in r.message or "SLACK" in r.message
                   for r in caplog.records)

    def test_result_has_required_keys(self):
        """KS test result always has expected keys."""
        from app.services.drift import run_ks_test
        ref = np.random.random(500)
        live = np.random.random(200)

        with patch("app.services.drift._reference_scores", ref):
            result = run_ks_test(live)

        for key in ("ks_statistic", "p_value", "alert", "n_reference", "n_live"):
            assert key in result
