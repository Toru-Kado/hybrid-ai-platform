"""DynamoDB-backed session store for Lambda handlers.

Implements the same logical interface as the SQLite SessionStore but
uses DynamoDB single-table design for multi-tenant cloud deployment.

Key schema:
    PK: USER#{userId}
    SK: SESSION#{sessionId} (session record)
        SESSION#{sessionId}#MSG#{messageId} (message record)

GSI1 (SessionsByRecency):
    GSI1PK: USER#{userId}
    GSI1SK: {updatedAt}#{sessionId}
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.lambda_handlers.constants import (
    ENTITY_MESSAGE,
    ENTITY_SESSION,
    GSI1_INDEX_NAME,
    MAX_PREVIEW_LENGTH,
    MAX_TITLE_LENGTH,
    PK_USER_PREFIX,
    SK_MESSAGE_SEPARATOR,
    SK_SESSION_PREFIX,
)


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _generate_id() -> str:
    """Generate a time-sortable unique ID (ULID-like using UUID v7 hex)."""
    return uuid.uuid4().hex


def _default_title(prompt: str) -> str:
    """Derive a session title from the first user prompt, truncated to 72 chars."""
    compact = " ".join(prompt.strip().split())
    if not compact:
        return "New session"
    return compact[:72].rstrip()


def _user_pk(user_id: str) -> str:
    """Build the partition key for a user."""
    return f"{PK_USER_PREFIX}{user_id}"


def _session_sk(session_id: str) -> str:
    """Build the sort key for a session record."""
    return f"{SK_SESSION_PREFIX}{session_id}"


def _message_sk(session_id: str, message_id: str) -> str:
    """Build the sort key for a message record."""
    return f"{SK_SESSION_PREFIX}{session_id}{SK_MESSAGE_SEPARATOR}{message_id}"


def _message_sk_prefix(session_id: str) -> str:
    """Build the sort key prefix for querying all messages in a session."""
    return f"{SK_SESSION_PREFIX}{session_id}{SK_MESSAGE_SEPARATOR}"


def _session_sk_prefix(session_id: str) -> str:
    """Build the sort key prefix for querying a session and all its messages."""
    return f"{SK_SESSION_PREFIX}{session_id}"


@dataclass(slots=True)
class SessionSummary:
    """Lightweight session record for list views."""

    session_id: str
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
    """A single message within a session."""

    message_id: str
    session_id: str
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


@dataclass(slots=True)
class SearchResult:
    """A search hit with contextual snippet."""

    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str
    session_title: str
    snippet: str

    def to_dict(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "session_title": self.session_title,
            "snippet": self.snippet,
        }


class DynamoSessionStore:
    """DynamoDB-backed session and message store (multi-tenant).

    All operations are scoped by user_id for tenant isolation.
    """

    def __init__(self, table_name: str | None = None) -> None:
        self._table_name = table_name or os.environ["SESSIONS_TABLE_NAME"]
        self._dynamodb = boto3.resource("dynamodb")
        self._table = self._dynamodb.Table(self._table_name)

    def list_sessions(self, user_id: str) -> list[SessionSummary]:
        """List all sessions for a user, ordered by most recently updated."""
        response = self._table.query(
            IndexName=GSI1_INDEX_NAME,
            KeyConditionExpression=Key("GSI1PK").eq(_user_pk(user_id)),
            ScanIndexForward=False,
        )

        sessions = []
        for item in response.get("Items", []):
            sessions.append(
                SessionSummary(
                    session_id=item["session_id"],
                    title=item.get("title", "New session"),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                    message_count=int(item.get("message_count", 0)),
                    preview=item.get("preview"),
                )
            )
        return sessions

    def create_session(self, user_id: str, title: str | None = None) -> SessionSummary:
        """Create a new empty session."""
        session_id = _generate_id()
        created_at = _utc_now()
        clean_title = (title or "").strip() or "New session"
        clean_title = clean_title[:MAX_TITLE_LENGTH]

        item = {
            "PK": _user_pk(user_id),
            "SK": _session_sk(session_id),
            "GSI1PK": _user_pk(user_id),
            "GSI1SK": f"{created_at}#{session_id}",
            "session_id": session_id,
            "title": clean_title,
            "created_at": created_at,
            "updated_at": created_at,
            "message_count": 0,
            "entity_type": ENTITY_SESSION,
        }

        ttl_days = int(os.environ.get("DYNAMODB_TTL_DAYS", "0"))
        if ttl_days > 0:
            item["ttl"] = int(time.time()) + (ttl_days * 86400)

        self._table.put_item(Item=item)

        return SessionSummary(
            session_id=session_id,
            title=clean_title,
            created_at=created_at,
            updated_at=created_at,
            message_count=0,
            preview=None,
        )

    def get_session(self, user_id: str, session_id: str) -> SessionSummary:
        """Get a single session by ID."""
        response = self._table.get_item(
            Key={
                "PK": _user_pk(user_id),
                "SK": _session_sk(session_id),
            }
        )
        item = response.get("Item")
        if not item:
            raise KeyError(f"Session {session_id} was not found.")

        return SessionSummary(
            session_id=item["session_id"],
            title=item.get("title", "New session"),
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            message_count=int(item.get("message_count", 0)),
            preview=item.get("preview"),
        )

    def get_messages(self, user_id: str, session_id: str) -> list[SessionMessage]:
        """Get all messages for a session, ordered by creation time."""
        response = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(_user_pk(user_id))
                & Key("SK").begins_with(_message_sk_prefix(session_id))
            ),
        )

        messages = []
        for item in response.get("Items", []):
            messages.append(
                SessionMessage(
                    message_id=item["message_id"],
                    session_id=session_id,
                    role=item["role"],
                    content=item["content"],
                    created_at=item.get("created_at", ""),
                    metadata=item.get("metadata"),
                )
            )
        return messages

    def add_message(
        self,
        *,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionMessage:
        """Add a message to a session and update session metadata."""
        message_id = _generate_id()
        created_at = _utc_now()

        message_item = {
            "PK": _user_pk(user_id),
            "SK": _message_sk(session_id, message_id),
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": created_at,
            "entity_type": ENTITY_MESSAGE,
        }
        if metadata:
            message_item["metadata"] = metadata

        ttl_days = int(os.environ.get("DYNAMODB_TTL_DAYS", "0"))
        if ttl_days > 0:
            message_item["ttl"] = int(time.time()) + (ttl_days * 86400)

        self._table.put_item(Item=message_item)

        # Atomically update session metadata when a new message is added.
        # - message_count uses if_not_exists for safe initialization
        # - GSI1SK is updated so the session appears first in recency queries
        # - preview shows the latest message content in session list views
        preview = content[:MAX_PREVIEW_LENGTH] if content else None
        self._table.update_item(
            Key={
                "PK": _user_pk(user_id),
                "SK": _session_sk(session_id),
            },
            UpdateExpression=(
                "SET updated_at = :updated_at, "
                "message_count = if_not_exists(message_count, :zero) + :one, "
                "preview = :preview, "
                "GSI1SK = :gsi1sk"
            ),
            ExpressionAttributeValues={
                ":updated_at": created_at,
                ":zero": 0,
                ":one": 1,
                ":preview": preview,
                ":gsi1sk": f"{created_at}#{session_id}",
            },
        )

        return SessionMessage(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            created_at=created_at,
            metadata=metadata,
        )

    def ensure_session(
        self, user_id: str, session_id: str | None, *, prompt: str
    ) -> SessionSummary:
        """Get or create a session, auto-titling if needed."""
        if session_id is None:
            return self.create_session(user_id, _default_title(prompt))

        session = self.get_session(user_id, session_id)
        if session.message_count == 0 and session.title == "New session":
            self.update_session_title(user_id, session_id, _default_title(prompt))
            return self.get_session(user_id, session_id)
        return session

    def update_session_title(
        self, user_id: str, session_id: str, title: str
    ) -> None:
        """Update session title."""
        clean_title = (title.strip() or "New session")[:MAX_TITLE_LENGTH]
        updated_at = _utc_now()

        self._table.update_item(
            Key={
                "PK": _user_pk(user_id),
                "SK": _session_sk(session_id),
            },
            UpdateExpression="SET title = :title, updated_at = :updated_at, GSI1SK = :gsi1sk",
            ExpressionAttributeValues={
                ":title": clean_title,
                ":updated_at": updated_at,
                ":gsi1sk": f"{updated_at}#{session_id}",
            },
            ConditionExpression=Attr("PK").exists(),
        )

    def delete_session(self, user_id: str, session_id: str) -> None:
        """Delete a session and all its messages.

        Uses the sort key prefix pattern to find both the session record
        (SK=SESSION#{id}) and all message records (SK=SESSION#{id}#MSG#{msgId})
        in a single query, then batch-deletes them all.
        """
        response = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(_user_pk(user_id))
                & Key("SK").begins_with(_session_sk_prefix(session_id))
            ),
        )

        with self._table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(
                    Key={"PK": item["PK"], "SK": item["SK"]}
                )

    def search_messages(
        self,
        user_id: str,
        query: str,
        *,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[SearchResult]:
        """Search messages using DynamoDB scan with contains filter.

        This is the fallback for when OpenSearch is not enabled.
        For production full-text search, use the OpenSearch client.
        """
        query_lower = query.lower().strip()
        if not query_lower:
            return []

        # Build the filter expression
        filter_expr = Attr("entity_type").eq(ENTITY_MESSAGE) & Attr("content").contains(query_lower)
        if session_id:
            filter_expr = filter_expr & Attr("session_id").eq(session_id)

        response = self._table.query(
            KeyConditionExpression=Key("PK").eq(_user_pk(user_id)),
            FilterExpression=filter_expr,
        )

        results = []
        for item in response.get("Items", [])[:limit]:
            content = item.get("content", "")
            # Generate a simple snippet
            idx = content.lower().find(query_lower)
            start = max(0, idx - 50)
            end = min(len(content), idx + len(query_lower) + 50)
            snippet = ("..." if start > 0 else "") + content[start:end] + ("..." if end < len(content) else "")

            results.append(
                SearchResult(
                    message_id=item["message_id"],
                    session_id=item["session_id"],
                    role=item["role"],
                    content=content,
                    created_at=item.get("created_at", ""),
                    session_title="",  # Would need a join/lookup
                    snippet=snippet,
                )
            )

        return results
