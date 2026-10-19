"""Unit tests for the ML prediction pipeline (`backend/app/predictor.py`)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import predictor  # noqa: E402
from app.predictor import predict_news, get_model_status  # noqa: E402


class PredictorModelTests(unittest.TestCase):
    def test_model_loaded_successfully(self):
        status = get_model_status()
        self.assertTrue(status["loaded"])
        self.assertIn("tfidf", status["pipeline_steps"])
        self.assertIn("classifier", status["pipeline_steps"])

    def test_valid_prediction_returns_serializable_dict(self):
        sample = (
            "The government announced a new public transport initiative "
            "after reviewing proposals from local authorities."
        )
        result = predict_news(sample)
        self.assertIsInstance(result, dict)
        self.assertIn(result["label"], ("Real", "Fake"))
        self.assertIsInstance(result["confidence"], float)
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 100.0)

    def test_empty_and_whitespace_rejected(self):
        for bad in ("", "   ", "\n\t"):
            with self.assertRaises(ValueError):
                predict_news(bad)

    def test_oversized_input_rejected(self):
        with self.assertRaises(ValueError):
            predict_news("a" * (predictor.MAX_TEXT_LENGTH + 1))

    def test_missing_model_file_handled_gracefully(self):
        original_model = predictor.model
        try:
            loaded = predictor.load_model(BACKEND_DIR / "artifacts" / "nonexistent.joblib")
            self.assertIsNone(loaded)
            status = get_model_status()
            self.assertFalse(status["loaded"])
            with self.assertRaises(RuntimeError):
                predict_news("Valid text while model is unloaded")
        finally:
            predictor.model = original_model
            predictor._model_error = None


if __name__ == "__main__":
    sample = """
The government announced a new public transport initiative
after reviewing proposals from local authorities.
"""
    result = predict_news(sample)
    print("Prediction:", result["label"])
    print("Confidence:", result["confidence"], "%")
    unittest.main()
