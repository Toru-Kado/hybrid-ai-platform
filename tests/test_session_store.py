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

    def test_ensure_session_uses_first_prompt_as_title_for_empty_new_session(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session()

        ensured = store.ensure_session(session.session_id, prompt="   First prompt for title   ")

        self.assertEqual(ensured.session_id, session.session_id)
        self.assertEqual(ensured.title, "First prompt for title")

    def test_delete_session_cascades_messages(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("Scratchpad")
        message = store.add_message(
            session_id=session.session_id,
            role="user",
            content="hello history",
            metadata={"source": "test"},
        )

        store.delete_session(session.session_id)

        with self.assertRaises(KeyError):
            store.get_session(session.session_id)
        with self.assertRaises(KeyError):
            store.get_message(message.message_id)

    def test_add_message_round_trips_metadata_and_preview(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("Scratchpad")

        message = store.add_message(
            session_id=session.session_id,
            role="assistant",
            content="## Reply",
            metadata={"request_id": "req-123", "output_tokens": 42},
        )
        refreshed = store.get_session(session.session_id)

        self.assertEqual(message.metadata, {"request_id": "req-123", "output_tokens": 42})
        self.assertEqual(refreshed.message_count, 1)
        self.assertEqual(refreshed.preview, "## Reply")


    def test_search_messages_finds_matching_content(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("Search test")
        store.add_message(session_id=session.session_id, role="user", content="hello world")
        store.add_message(session_id=session.session_id, role="assistant", content="goodbye world")
        store.add_message(session_id=session.session_id, role="user", content="nothing here")

        results = store.search_messages("hello")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].message_id, 1)
        self.assertEqual(results[0].role, "user")
        self.assertIn("hello", results[0].snippet.lower())
        self.assertEqual(results[0].session_title, "Search test")

    def test_search_messages_returns_empty_for_no_match(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("No match")
        store.add_message(session_id=session.session_id, role="user", content="hello world")

        results = store.search_messages("xyznonexistent")

        self.assertEqual(results, [])

    def test_search_messages_empty_query_returns_empty(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("Empty query")
        store.add_message(session_id=session.session_id, role="user", content="hello world")

        self.assertEqual(store.search_messages(""), [])
        self.assertEqual(store.search_messages("   "), [])

    def test_search_messages_scoped_to_session(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        s1 = store.create_session("Session one")
        s2 = store.create_session("Session two")
        store.add_message(session_id=s1.session_id, role="user", content="unique keyword alpha")
        store.add_message(session_id=s2.session_id, role="user", content="unique keyword beta")

        results = store.search_messages("keyword", session_id=s1.session_id)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].session_id, s1.session_id)
        self.assertIn("alpha", results[0].content)

    def test_search_messages_cross_session(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        s1 = store.create_session("Session one")
        s2 = store.create_session("Session two")
        store.add_message(session_id=s1.session_id, role="user", content="shared keyword here")
        store.add_message(session_id=s2.session_id, role="user", content="shared keyword there")

        results = store.search_messages("keyword")

        self.assertEqual(len(results), 2)
        session_ids = {r.session_id for r in results}
        self.assertEqual(session_ids, {s1.session_id, s2.session_id})

    def test_search_messages_special_characters_safe(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("Special chars")
        store.add_message(session_id=session.session_id, role="user", content='has "quotes" inside')

        results = store.search_messages('"quotes"')

        self.assertEqual(len(results), 1)

    def test_fts_sync_on_insert(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("FTS sync")

        results_before = store.search_messages("laterword")
        self.assertEqual(results_before, [])

        store.add_message(session_id=session.session_id, role="user", content="laterword appears")

        results_after = store.search_messages("laterword")
        self.assertEqual(len(results_after), 1)

    def test_fts_sync_on_delete(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("FTS delete sync")
        store.add_message(session_id=session.session_id, role="user", content="deletable content")

        results_before = store.search_messages("deletable")
        self.assertEqual(len(results_before), 1)

        store.delete_session(session.session_id)

        results_after = store.search_messages("deletable")
        self.assertEqual(results_after, [])

    def test_migration_v1_to_v2_creates_fts_table(self):
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
                    metadata_json TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "INSERT INTO sessions (title, created_at, updated_at) "
                "VALUES ('Old session', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
            )
            connection.execute(
                "INSERT INTO messages (session_id, role, content, created_at) "
                "VALUES (1, 'user', 'searchable content', '2026-01-01T00:00:00+00:00')"
            )
            connection.execute("PRAGMA user_version = 1")
            connection.commit()

        store = SessionStore(db_path)

        with sqlite3.connect(db_path) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertIn("messages_fts", tables)

        results = store.search_messages("searchable")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "searchable content")

    def test_search_messages_respects_limit_and_offset(self):
        db_path = self._temp_db_path()
        store = SessionStore(db_path)
        session = store.create_session("Pagination")
        for i in range(5):
            store.add_message(
                session_id=session.session_id,
                role="user",
                content=f"paginated message {i}",
            )

        results_limited = store.search_messages("paginated", limit=2)
        self.assertEqual(len(results_limited), 2)

        results_offset = store.search_messages("paginated", limit=2, offset=2)
        self.assertEqual(len(results_offset), 2)

        all_ids = {r.message_id for r in results_limited} | {r.message_id for r in results_offset}
        self.assertEqual(len(all_ids), 4)


if __name__ == "__main__":
    unittest.main()
