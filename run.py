"""Convenience wrapper so `python run.py` works from the repository root as well as `backend/`."""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from run import app  # noqa: E402

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")
    host = os.getenv("FLASK_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.getenv("FLASK_PORT", "5000"))
    except ValueError:
        port = 5000
    app.run(host=host, port=port, debug=debug_mode)
