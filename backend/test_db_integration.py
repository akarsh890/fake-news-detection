"""Focused integration tests. Run from backend/:  python -m unittest test_db_integration -v

DB tests only touch rows they create (headline starts with [TEST]) and
delete just those rows afterwards. Existing data is never modified.
"""
import unittest
from unittest import mock

from app import db
from run import app

MARK = "[TEST] "


@unittest.skipUnless(db.is_configured(), "DB_USER / DB_NAME not set")
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.news_ids = []

    def tearDown(self):
        if self.news_ids:
            conn = db.get_connection()
            with conn.cursor() as cur:  # prediction rows go via ON DELETE CASCADE
                cur.executemany("DELETE FROM `news` WHERE news_id = %s",
                                [(i,) for i in self.news_ids])
            conn.commit()
            conn.close()

    def _save(self, **kw):
        ids = db.save_prediction(MARK + "article body", "Fake", 87.5, headline=MARK + "h", **kw)
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
                (ids["prediction_id"],))
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
            cur.execute("SELECT COUNT(*) FROM `user` WHERE email = %s", (db.GUEST_EMAIL,))
            self.assertEqual(cur.fetchone()[0], 1)
        conn.close()
        self.assertNotEqual(a["news_id"], b["news_id"])

    def test_foreign_key_rejects_bad_news_id(self):
        conn = db.get_connection()
        with conn.cursor() as cur:
            with self.assertRaises(Exception):
                cur.execute("INSERT INTO prediction (news_id, result, confidence_score) "
                            "VALUES (999999999, 'Real', 0.5)")
        conn.rollback()
        conn.close()

    def test_invalid_values_not_saved(self):
        self.assertIsNone(db.save_prediction("x", "Maybe", 50))
        self.assertIsNone(db.save_prediction("x", "Real", 150))
        self.assertIsNone(db.save_prediction("x", "Real", None))

    def test_nothing_saved_when_insert_fails(self):
        before = self._count_news()
        # Non-existent user_id violates the NEWS foreign key -> whole transaction rolls back.
        self.assertIsNone(db.save_prediction(MARK + "x", "Real", 60, user_id=999999999))
        self.assertEqual(self._count_news(), before)

    def _count_news(self):
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM news")
            n = cur.fetchone()[0]
        conn.close()
        return n


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_response_structure_unchanged(self):
        with mock.patch("run.save_prediction") as saver:
            r = self.client.post("/api/predict", json={"text": "Some news text"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.get_json()), {"label", "confidence"})
        saver.assert_called_once()

    def test_empty_input_still_rejected(self):
        r = self.client.post("/api/predict", json={"text": "  "})
        self.assertEqual(r.status_code, 400)

    def test_database_down_does_not_break_prediction(self):
        with mock.patch.object(db, "get_connection", side_effect=db.pymysql.OperationalError("down")):
            r = self.client.post("/api/predict", json={"text": "Some news text"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.get_json()), {"label", "confidence"})

    def test_health(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
