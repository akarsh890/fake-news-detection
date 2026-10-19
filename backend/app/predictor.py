"""Machine learning inference pipeline for the Fake News Detection System.

Loads the serialized scikit-learn Pipeline (TfidfVectorizer + LogisticRegression)
from a reliable path relative to this module and provides safe text validation
and prediction utilities.
"""
import logging
from pathlib import Path
import joblib

logger = logging.getLogger(__name__)

# Locate the saved model independent of the terminal's working directory
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "artifacts" / "fake_news_pipeline.joblib"

MAX_TEXT_LENGTH = 20000

model = None
_model_error = None


def load_model(path=None):
    """Load or reload the trained scikit-learn pipeline from disk."""
    global model, _model_error
    target_path = Path(path) if path else MODEL_PATH
    try:
        model = joblib.load(target_path)
        _model_error = None
        return model
    except Exception as exc:
        model = None
        _model_error = f"Could not load model from {target_path.name}: {type(exc).__name__}"
        logger.exception("Failed to load ML pipeline from %s", target_path)
        return None


# Load the trained pipeline once at startup
load_model()


def get_model_status():
    """Return diagnostic metadata about the loaded ML pipeline."""
    if model is None:
        return {
            "loaded": False,
            "error": _model_error or "Model is not loaded",
            "model_file": MODEL_PATH.name,
        }
    steps = [name for name, _ in getattr(model, "steps", [])]
    return {
        "loaded": True,
        "pipeline_steps": steps,
        "model_file": MODEL_PATH.name,
    }


def predict_news(text):
    """Run the TF-IDF + Logistic Regression pipeline on a validated news string.

    Returns JSON-serializable prediction output:
      - label: "Real" or "Fake"
      - confidence: float in [0, 100] (rounded to 2 decimal places)
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Please provide non-empty news text.")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Text exceeds {MAX_TEXT_LENGTH:,} characters.")

    if model is None:
        raise RuntimeError(_model_error or "Model is not available.")

    cleaned_text = text.strip()
    prediction = int(model.predict([cleaned_text])[0])

    probabilities = model.predict_proba([cleaned_text])[0]
    confidence = float(max(probabilities)) * 100.0

    label = "Real" if prediction == 1 else "Fake"

    return {
        "label": label,
        "confidence": round(confidence, 2),
    }
