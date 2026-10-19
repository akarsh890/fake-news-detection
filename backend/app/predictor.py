
from pathlib import Path
import joblib

# Locate the saved model
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "artifacts" / "fake_news_pipeline.joblib"

# Load the trained pipeline once
model = joblib.load(MODEL_PATH)


def predict_news(text):
    prediction = int(model.predict([text])[0])

    probabilities = model.predict_proba([text])[0]
    confidence = float(max(probabilities)) * 100

    label = "Real" if prediction == 1 else "Fake"

    return {
        "label": label,
        "confidence": round(confidence, 2)
    }
