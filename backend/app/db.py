"""MySQL persistence for the Fake News Detection System.

Saves each submitted article (NEWS) and its model output (PREDICTION)
in one transaction. Database problems are logged and never propagate,
so the prediction API keeps working even if MySQL is down or unset.
"""
import logging
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

# Load .env from backend/ first, then repository root as fallback (without overriding existing env vars)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _BACKEND_DIR.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

# The app has no login yet, but NEWS.user_id is NOT NULL, so anonymous
# submissions are stored under one placeholder account.
GUEST_EMAIL = "guest@fakenews.local"
GUEST_NAME = "Guest"
GUEST_PASSWORD_PLACEHOLDER = "!"  # not a valid hash, so nobody can log in as guest

HEADLINE_MAX = 200  # NEWS.headline is VARCHAR(500)
PLACEHOLDER_VALUES = {"your_mysql_user", "your_mysql_password", "changeme"}

_last_save_status = {
    "saved": False,
    "status": "not_configured",
    "message": "Database not configured.",
}


def get_last_save_status():
    """Return a copy of the status from the most recent save_prediction call."""
    return dict(_last_save_status)


def is_configured():
    """Check whether DB_USER and DB_NAME are configured with non-placeholder values."""
    user = (os.getenv("DB_USER") or "").strip()
    dbname = (os.getenv("DB_NAME") or "").strip()
    if not user or not dbname:
        return False
    if user.lower() in PLACEHOLDER_VALUES or dbname.lower() in PLACEHOLDER_VALUES:
        return False
    return True


def _parse_port():
    raw_port = (os.getenv("DB_PORT") or "3306").strip()
    try:
        port = int(raw_port)
        if not (1 <= port <= 65535):
            raise ValueError("Port out of valid TCP range")
        return port
    except ValueError as exc:
        raise ValueError(f"Invalid DB_PORT value {raw_port!r}; expected an integer 1-65535.") from exc


def get_connection():
    """Create a new PyMySQL connection using environment variables."""
    if not is_configured():
        raise pymysql.OperationalError(
            "Database environment variables (DB_USER, DB_NAME) are missing or contain placeholder values."
        )
    port = _parse_port()
    return pymysql.connect(
        host=(os.getenv("DB_HOST") or "127.0.0.1").strip(),
        port=port,
        user=(os.getenv("DB_USER") or "").strip(),
        password=os.getenv("DB_PASSWORD") or "",
        database=(os.getenv("DB_NAME") or "").strip(),
        charset="utf8mb4",
        connect_timeout=3,
        read_timeout=5,
        write_timeout=5,
        autocommit=False,
    )


def check_health():
    """Perform a live connectivity check against MySQL without exposing credentials."""
    if not is_configured():
        return {
            "configured": False,
            "connected": False,
            "status": "not_configured",
            "message": "MySQL is not configured (set DB_USER and DB_NAME in .env to enable persistence).",
        }
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
        if row and row[0] == 1:
            return {
                "configured": True,
                "connected": True,
                "status": "connected",
                "message": "Connected to MySQL database.",
            }
        return {
            "configured": True,
            "connected": False,
            "status": "unreachable",
            "message": "MySQL health query returned unexpected output.",
        }
    except ValueError as exc:
        logger.error("Database configuration error: %s", exc)
        return {
            "configured": False,
            "connected": False,
            "status": "config_error",
            "message": str(exc),
        }
    except pymysql.MySQLError as exc:
        code = exc.args[0] if exc.args else "unknown"
        logger.warning("MySQL connectivity check failed (code=%s)", code)
        return {
            "configured": True,
            "connected": False,
            "status": "unreachable",
            "message": f"MySQL server is unreachable or rejected connection (error code: {code}).",
        }
    except Exception as exc:
        logger.warning("Unexpected error checking MySQL health: %s", type(exc).__name__)
        return {
            "configured": True,
            "connected": False,
            "status": "unreachable",
            "message": "Could not verify MySQL connection.",
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _make_headline(text, headline=None):
    if isinstance(headline, str) and headline.strip():
        return headline.strip()[:HEADLINE_MAX]
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:HEADLINE_MAX]
    return text.strip()[:HEADLINE_MAX]


def _guest_user_id(cur):
    # Get-or-create; LAST_INSERT_ID(user_id) makes lastrowid valid for both cases.
    cur.execute(
        "INSERT INTO `user` (name, email, password, role) "
        "VALUES (%s, %s, %s, 'user') "
        "ON DUPLICATE KEY UPDATE user_id = LAST_INSERT_ID(user_id)",
        (GUEST_NAME, GUEST_EMAIL, GUEST_PASSWORD_PLACEHOLDER),
    )
    return cur.lastrowid


def save_prediction(text, label, confidence_percent, headline=None, user_id=None):
    """Store one article + prediction atomically.

    confidence_percent is the predictor's 0-100 value; the schema stores 0-1.
    Returns {"news_id", "prediction_id"} or None if nothing was saved.
    Updates _last_save_status so callers can inspect why a save was skipped or failed.
    Never raises.
    """
    global _last_save_status

    if not is_configured():
        logger.warning("Database not configured; skipping save.")
        _last_save_status = {
            "saved": False,
            "status": "not_configured",
            "message": "MySQL is not configured; prediction returned in stateless mode.",
        }
        return None
    if not isinstance(text, str) or not text.strip():
        logger.error("Empty article text; skipping save.")
        _last_save_status = {
            "saved": False,
            "status": "validation_error",
            "message": "Article text must be non-empty.",
        }
        return None
    if label not in ("Real", "Fake"):
        logger.error("Unexpected label %r; skipping save.", label)
        _last_save_status = {
            "saved": False,
            "status": "validation_error",
            "message": f"Unexpected prediction label: {label!r}.",
        }
        return None
    try:
        if confidence_percent is None or isinstance(confidence_percent, bool):
            raise TypeError("Confidence must be a number")
        confidence = round(float(confidence_percent) / 100, 4)
    except (TypeError, ValueError):
        logger.error("Invalid confidence %r; skipping save.", confidence_percent)
        _last_save_status = {
            "saved": False,
            "status": "validation_error",
            "message": "Invalid confidence value.",
        }
        return None
    if not 0 <= confidence <= 1:
        logger.error("Confidence out of range: %r; skipping save.", confidence_percent)
        _last_save_status = {
            "saved": False,
            "status": "validation_error",
            "message": "Confidence score is out of range [0, 100].",
        }
        return None

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            if user_id is None:
                user_id = _guest_user_id(cur)
            cur.execute(
                "INSERT INTO `news` (user_id, headline, article_text) VALUES (%s, %s, %s)",
                (user_id, _make_headline(text, headline), text),
            )
            news_id = cur.lastrowid
            cur.execute(
                "INSERT INTO `prediction` (news_id, result, confidence_score) "
                "VALUES (%s, %s, %s)",
                (news_id, label, confidence),
            )
            prediction_id = cur.lastrowid
        conn.commit()
        result_ids = {"news_id": news_id, "prediction_id": prediction_id}
        _last_save_status = {
            "saved": True,
            "status": "saved",
            "message": "Prediction saved to MySQL database.",
            "news_id": news_id,
            "prediction_id": prediction_id,
        }
        return result_ids
    except (pymysql.MySQLError, ValueError, OSError) as exc:
        logger.exception("Could not save prediction to MySQL")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        _last_save_status = {
            "saved": False,
            "status": "failed",
            "message": f"Database save failed ({type(exc).__name__}); prediction returned without persistence.",
        }
        return None
    except Exception as exc:
        logger.exception("Unexpected error saving prediction to MySQL")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        _last_save_status = {
            "saved": False,
            "status": "failed",
            "message": f"Unexpected database error ({type(exc).__name__}); prediction returned without persistence.",
        }
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_recent_predictions(limit=10):
    """Fetch recent saved predictions from MySQL if configured and reachable.

    Returns a dictionary with {"available": bool, "items": list, "status": str, "message": str}.
    Never raises.
    """
    if not is_configured():
        return {
            "available": False,
            "status": "not_configured",
            "message": "MySQL is not configured.",
            "items": [],
        }
    try:
        safe_limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        safe_limit = 10

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.prediction_id, n.news_id, n.headline, p.result, "
                "p.confidence_score, p.predicted_at "
                "FROM `prediction` p "
                "JOIN `news` n ON n.news_id = p.news_id "
                "ORDER BY p.predicted_at DESC, p.prediction_id DESC "
                "LIMIT %s",
                (safe_limit,),
            )
            rows = cur.fetchall()
        items = [
            {
                "prediction_id": row[0],
                "news_id": row[1],
                "headline": row[2],
                "label": row[3],
                "confidence": round(float(row[4]) * 100, 2),
                "predicted_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
            }
            for row in rows
        ]
        return {
            "available": True,
            "status": "connected",
            "message": "Loaded recent predictions from MySQL.",
            "items": items,
        }
    except Exception as exc:
        logger.warning("Could not fetch recent predictions from MySQL: %s", type(exc).__name__)
        return {
            "available": False,
            "status": "unreachable",
            "message": "Could not query MySQL database.",
            "items": [],
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
