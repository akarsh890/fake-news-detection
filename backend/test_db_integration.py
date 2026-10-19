r"""Comprehensive backend and database integration tests.

Run from backend/:
    python -m unittest test_db_integration -v
or from repository root:
    .\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v

Real DB tests only touch rows they create (headline starts with [TEST]) and
delete just those rows afterwards. Existing data is never modified.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import db, predictor  # noqa: E402
from run import app  # noqa: E402

MARK = "[TEST] "


@unittest.skipUnless(db.is_configured(), "DB_USER / DB_NAME not set")
class DatabaseTests(unittest.TestCase):
    """Live MySQL integration tests (executed only when a real database is configured)."""

    def setUp(self):
        self.news_ids = []

    def tearDown(self):
        if self.news_ids:
            conn = db.get_connection()
            with conn.cursor() as cur:  # prediction rows go via ON DELETE CASCADE
                cur.executemany(
                    "DELETE FROM `news` WHERE news_id = %s",
                    [(i,) for i in self.news_ids],
                )
            conn.commit()
            conn.close()

    def _save(self, **kw):
        ids = db.save_prediction(
            MARK + "article body", "Fake", 87.5, headline=MARK + "h", **kw
        )
        self.assertIsNotNone(ids)
        self.news_ids.append(ids["news_id"])
        return ids

    def test_connection(self):
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

    def test_news_and_prediction_saved_and_linked(self):
        ids = self._save()
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT n.headline, n.article_text, u.email, p.result, p.confidence_score "
                "FROM news n JOIN `user` u ON u.user_id = n.user_id "
                "JOIN prediction p ON p.news_id = n.news_id WHERE p.prediction_id = %s",
                (ids["prediction_id"],),
            )
            headline, body, email, result, conf = cur.fetchone()
        conn.close()
        self.assertEqual(headline, MARK + "h")
        self.assertEqual(body, MARK + "article body")
        self.assertEqual(email, db.GUEST_EMAIL)
        self.assertEqual(result, "Fake")
        self.assertAlmostEqual(float(conf), 0.875, places=4)

    def test_guest_user_reused(self):
        a, b = self._save(), self._save()
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM `user` WHERE email = %s", (db.GUEST_EMAIL,)
            )
            self.assertEqual(cur.fetchone()[0], 1)
        conn.close()
        self.assertNotEqual(a["news_id"], b["news_id"])

    def test_foreign_key_rejects_bad_news_id(self):
        conn = db.get_connection()
        with conn.cursor() as cur:
            with self.assertRaises(Exception):
                cur.execute(
                    "INSERT INTO prediction (news_id, result, confidence_score) "
                    "VALUES (999999999, 'Real', 0.5)"
                )
        conn.rollback()
        conn.close()

    def test_invalid_values_not_saved(self):
        self.assertIsNone(db.save_prediction("x", "Maybe", 50))
        self.assertIsNone(db.save_prediction("x", "Real", 150))
        self.assertIsNone(db.save_prediction("x", "Real", None))

    def test_nothing_saved_when_insert_fails(self):
        before = self._count_news()
        # Non-existent user_id violates the NEWS foreign key -> whole transaction rolls back.
        self.assertIsNone(
            db.save_prediction(MARK + "x", "Real", 60, user_id=999999999)
        )
        self.assertEqual(self._count_news(), before)

    def _count_news(self):
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM news")
            n = cur.fetchone()[0]
        conn.close()
        return n


class MockedDatabaseUnitTests(unittest.TestCase):
    """Unit tests verifying DB config, transaction commit/rollback, and error handling."""

    def test_is_configured_rejects_missing_or_placeholders(self):
        with mock.patch.dict(os.environ, {"DB_USER": "", "DB_NAME": "test_db"}, clear=False):
            self.assertFalse(db.is_configured())
        with mock.patch.dict(
            os.environ,
            {"DB_USER": "your_mysql_user", "DB_NAME": "fake_news_detection_db"},
            clear=False,
        ):
            self.assertFalse(db.is_configured())
        with mock.patch.dict(
            os.environ,
            {"DB_USER": "root", "DB_NAME": "fake_news_detection_db"},
            clear=False,
        ):
            self.assertTrue(db.is_configured())

    def test_invalid_db_port_handled_safely(self):
        with mock.patch.dict(
            os.environ,
            {"DB_USER": "root", "DB_NAME": "fake_news_detection_db", "DB_PORT": "not_a_port"},
            clear=False,
        ):
            health = db.check_health()
            self.assertEqual(health["status"], "config_error")
            self.assertFalse(health["connected"])
            res = db.save_prediction("Valid article text", "Real", 88.2)
            self.assertIsNone(res)
            self.assertEqual(db.get_last_save_status()["status"], "failed")

    def test_invalid_values_rejected_before_connecting(self):
        with mock.patch.dict(
            os.environ,
            {"DB_USER": "root", "DB_NAME": "fake_news_detection_db"},
            clear=False,
        ), mock.patch.object(db, "get_connection") as mock_conn:
            self.assertIsNone(db.save_prediction("", "Real", 75.0))
            self.assertIsNone(db.save_prediction("text", "UnknownLabel", 75.0))
            self.assertIsNone(db.save_prediction("text", "Real", -5.0))
            self.assertIsNone(db.save_prediction("text", "Real", 105.0))
            self.assertIsNone(db.save_prediction("text", "Real", None))
            self.assertIsNone(db.save_prediction("text", "Real", True))
            mock_conn.assert_not_called()

    def test_transaction_commit_on_success(self):
        fake_cursor = mock.MagicMock()
        fake_cursor.lastrowid = 42
        fake_conn = mock.MagicMock()
        fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

        with mock.patch.dict(
            os.environ,
            {"DB_USER": "root", "DB_NAME": "fake_news_detection_db"},
            clear=False,
        ), mock.patch.object(db, "get_connection", return_value=fake_conn):
            ids = db.save_prediction("Sample news body", "Real", 91.25, headline="Sample Headline")

        self.assertEqual(ids, {"news_id": 42, "prediction_id": 42})
        fake_conn.commit.assert_called_once()
        fake_conn.rollback.assert_not_called()
        fake_conn.close.assert_called_once()
        self.assertTrue(db.get_last_save_status()["saved"])

    def test_transaction_rollback_when_second_insert_fails(self):
        fake_cursor = mock.MagicMock()
        fake_cursor.lastrowid = 10
        # First execute (_guest_user_id) ok, second execute (INSERT news) ok, third (INSERT prediction) fails
        fake_cursor.execute.side_effect = [
            None,
            None,
            db.pymysql.IntegrityError("Simulated constraint failure on prediction insert"),
        ]
        fake_conn = mock.MagicMock()
        fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

        with mock.patch.dict(
            os.environ,
            {"DB_USER": "root", "DB_NAME": "fake_news_detection_db"},
            clear=False,
        ), mock.patch.object(db, "get_connection", return_value=fake_conn):
            ids = db.save_prediction("Sample news body", "Fake", 80.0)

        self.assertIsNone(ids)
        fake_conn.commit.assert_not_called()
        fake_conn.rollback.assert_called_once()
        fake_conn.close.assert_called_once()
        status = db.get_last_save_status()
        self.assertFalse(status["saved"])
        self.assertEqual(status["status"], "failed")


class EndpointTests(unittest.TestCase):
    """Flask API endpoint tests covering predictions, validation, error handling, and health."""

    def setUp(self):
        self.client = app.test_client()

    def test_response_structure_unchanged(self):
        with mock.patch("run.save_prediction") as saver:
            r = self.client.post("/api/predict", json={"text": "Some news text"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.get_json()), {"label", "confidence"})
        saver.assert_called_once()

    def test_predict_with_meta_flag_includes_persistence_status(self):
        with mock.patch(
            "run.save_prediction", return_value={"news_id": 7, "prediction_id": 11}
        ), mock.patch(
            "run.get_last_save_status",
            return_value={"saved": True, "status": "saved", "message": "Saved"},
        ):
            r = self.client.post(
                "/api/predict?meta=1",
                json={"text": "Public transport funding approved by council."},
            )
        self.assertEqual(r.status_code, 200)
        payload = r.get_json()
        self.assertIn("label", payload)
        self.assertIn("confidence", payload)
        self.assertIn("persistence", payload)
        self.assertTrue(payload["persistence"]["saved"])
        self.assertEqual(payload["persistence"]["news_id"], 7)

    def test_empty_and_whitespace_input_rejected(self):
        for invalid_text in ("", "   ", "\n\t  "):
            r = self.client.post("/api/predict", json={"text": invalid_text})
            self.assertEqual(r.status_code, 400)
            self.assertIn("error", r.get_json())

    def test_missing_fields_and_wrong_types_rejected(self):
        # Missing text field
        r1 = self.client.post("/api/predict", json={})
        self.assertEqual(r1.status_code, 400)

        # Non-string text field
        r2 = self.client.post("/api/predict", json={"text": 12345})
        self.assertEqual(r2.status_code, 400)

        # Non-string headline field
        r3 = self.client.post("/api/predict", json={"text": "Valid news", "headline": ["bad"]})
        self.assertEqual(r3.status_code, 400)

        # JSON array instead of object
        r4 = self.client.post("/api/predict", json=["not", "an", "object"])
        self.assertEqual(r4.status_code, 400)

    def test_malformed_json_rejected(self):
        r = self.client.post(
            "/api/predict",
            data="{invalid json",
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.get_json())

    def test_oversized_text_rejected(self):
        huge_text = "a" * (predictor.MAX_TEXT_LENGTH + 1)
        r = self.client.post("/api/predict", json={"text": huge_text})
        self.assertEqual(r.status_code, 400)
        self.assertIn("20,000", r.get_json()["error"])

    def test_model_error_returns_500_without_stack_trace(self):
        with mock.patch("run.predict_news", side_effect=RuntimeError("Internal model failure")):
            r = self.client.post("/api/predict", json={"text": "Some news text"})
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.get_json(), {"error": "Prediction failed"})

    def test_database_down_does_not_break_prediction(self):
        with mock.patch.object(
            db, "get_connection", side_effect=db.pymysql.OperationalError("down")
        ):
            r = self.client.post("/api/predict", json={"text": "Some news text"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.get_json()), {"label", "confidence"})

    def test_health_endpoint_includes_model_and_db_diagnostics(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("model", data)
        self.assertTrue(data["model"]["loaded"])
        self.assertIn("database", data)
        self.assertIn("status", data["database"])

    def test_history_endpoint(self):
        r = self.client.get("/api/history?limit=5")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("available", data)
        self.assertIn("items", data)


if __name__ == "__main__":
    unittest.main()
