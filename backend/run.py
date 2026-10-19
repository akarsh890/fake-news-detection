import os
import sys
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

# Ensure backend/ directory is on sys.path regardless of where run.py is invoked from
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.predictor import predict_news, get_model_status, MAX_TEXT_LENGTH
from app.db import (
    save_prediction,
    get_last_save_status,
    check_health as check_db_health,
    get_recent_predictions,
)

app = Flask(__name__)

# Reject overly large HTTP bodies early (1 MB limit)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
] + [
    r"http://localhost:\d+",
    r"http://127\.0\.0\.1:\d+",
]
CORS(app, origins=_cors_origins)


@app.get("/api/health")
def health():
    model_info = get_model_status()
    db_info = check_db_health()
    overall_status = "ok" if model_info.get("loaded") else "degraded"
    return jsonify({
        "status": overall_status,
        "message": "Fake News Detection API is running" if overall_status == "ok" else "Model failed to load",
        "model": model_info,
        "database": db_info,
    }), (200 if overall_status == "ok" else 503)


@app.get("/api/history")
def history():
    limit = request.args.get("limit", 10)
    history_data = get_recent_predictions(limit=limit)
    return jsonify(history_data), 200


@app.post("/api/predict")
def predict():
    if not request.is_json:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Request body must be valid JSON"}), 400
    else:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Malformed JSON in request body"}), 400

    if not isinstance(data, dict):
        return jsonify({"error": "JSON payload must be an object"}), 400

    text = data.get("text", "")

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Please provide news text"}), 400

    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"error": f"Text exceeds {MAX_TEXT_LENGTH:,} characters"}), 400

    headline = data.get("headline")
    if headline is not None and not isinstance(headline, str):
        return jsonify({"error": "Headline must be a string when provided"}), 400

    try:
        result = predict_news(text)
        # Persist to MySQL; failures are logged inside and never crash the prediction response.
        saved_ids = save_prediction(
            text,
            result["label"],
            result["confidence"],
            headline=headline,
        )
        # Keep response keys {"label", "confidence"} unchanged unless caller requests extended metadata
        include_meta = (
            request.args.get("meta") == "1"
            or str(data.get("include_meta", "")).lower() in ("1", "true")
        )
        if include_meta:
            persistence_info = get_last_save_status()
            if isinstance(saved_ids, dict):
                persistence_info.update(saved_ids)
                persistence_info["saved"] = True
                persistence_info["status"] = "saved"
            result = {
                **result,
                "persistence": persistence_info,
            }
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Prediction failed")
        return jsonify({"error": "Prediction failed"}), 500


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"error": "Request payload is too large"}), 413


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "Method not allowed"}), 405


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")
    host = os.getenv("FLASK_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.getenv("FLASK_PORT", "5000"))
    except ValueError:
        port = 5000
    app.run(host=host, port=port, debug=debug_mode)
