import os
import sqlite3
import tempfile
import unittest

from app.session_store import SCHEMA_VERSION, SessionStore


class SessionStoreTests(unittest.TestCase):
    def _temp_db_path(self) -> str:
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        return handle.name

    def test_initializes_schema_version_for_new_database(self):
        db_path = self._temp_db_path()
        SessionStore(db_path)

        with sqlite3.connect(db_path) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)

    def test_migrates_existing_versionless_database_without_losing_data(self):
        db_path = self._temp_db_path()
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO sessions (title, created_at, updated_at)
                VALUES ('Legacy session', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
                """
            )
            connection.execute(
                """
                INSERT INTO messages (session_id, role, content, created_at, metadata_json)
                VALUES (1, 'user', 'hello from legacy', '2026-01-01T00:00:00+00:00', NULL)
                """
            )
            connection.commit()

        store = SessionStore(db_path)
        payload = store.get_session_payload(1)

        self.assertEqual(payload["session"]["title"], "Legacy session")
        self.assertEqual(payload["messages"][0]["content"], "hello from legacy")

        with sqlite3.connect(db_path) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)
            indexes = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }
            self.assertIn("idx_sessions_updated_at", indexes)
            self.assertIn("idx_messages_session_id_id", indexes)


if __name__ == "__main__":
    unittest.main()
