from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _default_title(prompt: str) -> str:
    compact = " ".join(prompt.strip().split())
    if not compact:
        return "New session"
    return compact[:72].rstrip()


@dataclass(slots=True)
class SessionSummary:
    session_id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int
    preview: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "preview": self.preview,
        }


@dataclass(slots=True)
class SessionMessage:
    message_id: int
    session_id: int
    role: str
    content: str
    created_at: str
    metadata: dict[str, Any] | None

    def to_dict(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class SessionStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def list_sessions(self) -> list[SessionSummary]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    sessions.id,
                    sessions.title,
                    sessions.created_at,
                    sessions.updated_at,
                    COUNT(messages.id) AS message_count,
                    (
                        SELECT content
                        FROM messages
                        WHERE messages.session_id = sessions.id
                        ORDER BY messages.id DESC
                        LIMIT 1
                    ) AS preview
                FROM sessions
                LEFT JOIN messages ON messages.session_id = sessions.id
                GROUP BY sessions.id
                ORDER BY sessions.updated_at DESC, sessions.id DESC
                """
            ).fetchall()

        return [self._summary_from_row(row) for row in rows]

    def create_session(self, title: str | None = None) -> SessionSummary:
        created_at = _utc_now()
        clean_title = (title or "").strip() or "New session"
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO sessions (title, created_at, updated_at)
                VALUES (?, ?, ?)
                """,
                (clean_title, created_at, created_at),
            )
            session_id = int(cursor.lastrowid)
            connection.commit()

        return self.get_session(session_id)

    def get_session(self, session_id: int) -> SessionSummary:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    sessions.id,
                    sessions.title,
                    sessions.created_at,
                    sessions.updated_at,
                    COUNT(messages.id) AS message_count,
                    (
                        SELECT content
                        FROM messages
                        WHERE messages.session_id = sessions.id
                        ORDER BY messages.id DESC
                        LIMIT 1
                    ) AS preview
                FROM sessions
                LEFT JOIN messages ON messages.session_id = sessions.id
                WHERE sessions.id = ?
                GROUP BY sessions.id
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Session {session_id} was not found.")

        return self._summary_from_row(row)

    def get_messages(self, session_id: int) -> list[SessionMessage]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, session_id, role, content, created_at, metadata_json
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()

        return [self._message_from_row(row) for row in rows]

    def ensure_session(self, session_id: int | None, *, prompt: str) -> SessionSummary:
        if session_id is None:
            return self.create_session(_default_title(prompt))

        session = self.get_session(session_id)
        if session.message_count == 0 and session.title == "New session":
            self.update_session_title(session_id, _default_title(prompt))
            return self.get_session(session_id)
        return session

    def update_session_title(self, session_id: int, title: str) -> None:
        clean_title = title.strip() or "New session"
        updated_at = _utc_now()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE sessions
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (clean_title, updated_at, session_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Session {session_id} was not found.")
            connection.commit()

    def delete_session(self, session_id: int) -> None:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                DELETE FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Session {session_id} was not found.")
            connection.commit()

    def add_message(
        self,
        *,
        session_id: int,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionMessage:
        created_at = _utc_now()
        metadata_json = json.dumps(metadata) if metadata is not None else None
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (session_id, role, content, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, created_at, metadata_json),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (created_at, session_id),
            )
            connection.commit()
            message_id = int(cursor.lastrowid)

        return self.get_message(message_id)

    def get_message(self, message_id: int) -> SessionMessage:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT id, session_id, role, content, created_at, metadata_json
                FROM messages
                WHERE id = ?
                """,
                (message_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Message {message_id} was not found.")
        return self._message_from_row(row)

    def get_session_payload(self, session_id: int) -> dict[str, object]:
        session = self.get_session(session_id)
        messages = self.get_messages(session_id)
        return {
            "session": session.to_dict(),
            "messages": [message.to_dict() for message in messages],
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            current_version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if current_version < 1:
                self._migrate_to_v1(connection)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()

    def _migrate_to_v1(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
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
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
            ON sessions (updated_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_session_id_id
            ON messages (session_id, id)
            """
        )

    def _summary_from_row(self, row: sqlite3.Row) -> SessionSummary:
        return SessionSummary(
            session_id=int(row["id"]),
            title=str(row["title"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            message_count=int(row["message_count"]),
            preview=str(row["preview"]) if row["preview"] is not None else None,
        )

    def _message_from_row(self, row: sqlite3.Row) -> SessionMessage:
        return SessionMessage(
            message_id=int(row["id"]),
            session_id=int(row["session_id"]),
            role=str(row["role"]),
            content=str(row["content"]),
            created_at=str(row["created_at"]),
            metadata=json.loads(row["metadata_json"])
            if row["metadata_json"] is not None
            else None,
        )
