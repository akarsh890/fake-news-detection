
from flask import Flask, request, jsonify
from flask_cors import CORS

from app.predictor import predict_news
from app.db import save_prediction

app = Flask(__name__)

CORS(app, origins=["http://localhost:5173"])


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "message": "Fake News Detection API is running"
    })


@app.post("/api/predict")
def predict():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Please provide news text"}), 400

    if len(text) > 20000:
        return jsonify({"error": "Text exceeds 20,000 characters"}), 400

    try:
        result = predict_news(text)
        # Persist to MySQL; failures are logged inside and never affect the response.
        headline = data.get("headline")
        save_prediction(text, result["label"], result["confidence"], headline=headline)
        return jsonify(result)
    except Exception:
        app.logger.exception("Prediction failed")
        return jsonify({"error": "Prediction failed"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
