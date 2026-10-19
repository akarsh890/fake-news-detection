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

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

# The app has no login yet, but NEWS.user_id is NOT NULL, so anonymous
# submissions are stored under one placeholder account.
GUEST_EMAIL = "guest@fakenews.local"
GUEST_NAME = "Guest"
GUEST_PASSWORD_PLACEHOLDER = "!"  # not a valid hash, so nobody can log in as guest

HEADLINE_MAX = 200  # NEWS.headline is VARCHAR(500)


def is_configured():
    return all(os.getenv(k) for k in ("DB_USER", "DB_NAME"))


def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        connect_timeout=5,
        autocommit=False,
    )


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
    Never raises.
    """
    if not is_configured():
        logger.warning("Database not configured; skipping save.")
        return None
    if label not in ("Real", "Fake"):
        logger.error("Unexpected label %r; skipping save.", label)
        return None
    try:
        confidence = round(float(confidence_percent) / 100, 4)
    except (TypeError, ValueError):
        logger.error("Invalid confidence %r; skipping save.", confidence_percent)
        return None
    if not 0 <= confidence <= 1:
        logger.error("Confidence out of range: %r; skipping save.", confidence_percent)
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
        return {"news_id": news_id, "prediction_id": prediction_id}
    except pymysql.MySQLError:
        logger.exception("Could not save prediction to MySQL")
        if conn:
            try:
                conn.rollback()
            except pymysql.MySQLError:
                pass
        return None
    finally:
        if conn:
            conn.close()
