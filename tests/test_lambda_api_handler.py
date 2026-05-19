"""Tests for the API Gateway Lambda handler."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app.lambda_handlers.api_handler import handler
from app.lambda_handlers.dynamo_session_store import SessionMessage, SessionSummary


def _api_event(
    method: str = "GET",
    path: str = "/api/health",
    body: dict | None = None,
    query_params: dict | None = None,
    user_id: str = "test-user-123",
) -> dict:
    """Build a minimal API Gateway v2 proxy event for testing."""
    event = {
        "rawPath": path,
        "requestContext": {
            "http": {"method": method},
            "authorizer": {
                "jwt": {"claims": {"sub": user_id}}
            },
        },
        "queryStringParameters": query_params,
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


class HealthEndpointTests(unittest.TestCase):
    """Tests for the /api/health endpoint."""

    @patch.dict(os.environ, {"BEDROCK_MODEL_ID": "test-model"})
    def test_returns_200_with_status_ok(self):
        event = _api_event("GET", "/api/health")
        # Remove authorizer since health doesn't need it
        del event["requestContext"]["authorizer"]
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["provider"], "bedrock")
        self.assertEqual(body["model_id"], "test-model")


class SessionEndpointTests(unittest.TestCase):
    """Tests for the /api/sessions endpoints."""

    @patch("app.lambda_handlers.api_handler._get_store")
    def test_list_sessions_returns_empty_list(self, mock_get_store):
        store = MagicMock()
        store.list_sessions.return_value = []
        mock_get_store.return_value = store

        event = _api_event("GET", "/api/sessions")
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["sessions"], [])
        store.list_sessions.assert_called_once_with("test-user-123")

    @patch("app.lambda_handlers.api_handler._get_store")
    def test_create_session_returns_201(self, mock_get_store):
        store = MagicMock()
        store.create_session.return_value = SessionSummary(
            session_id="sess-1",
            title="Test Session",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            message_count=0,
            preview=None,
        )
        mock_get_store.return_value = store

        event = _api_event("POST", "/api/sessions", body={"title": "Test Session"})
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 201)
        body = json.loads(result["body"])
        self.assertEqual(body["session"]["title"], "Test Session")

    @patch("app.lambda_handlers.api_handler._get_store")
    def test_get_session_returns_session_with_messages(self, mock_get_store):
        store = MagicMock()
        store.get_session.return_value = SessionSummary(
            session_id="sess-1",
            title="My Session",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            message_count=1,
            preview="Hello",
        )
        store.get_messages.return_value = [
            SessionMessage(
                message_id="msg-1",
                session_id="sess-1",
                role="user",
                content="Hello",
                created_at="2024-01-01T00:00:00",
                metadata=None,
            )
        ]
        mock_get_store.return_value = store

        event = _api_event("GET", "/api/sessions/sess-1")
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["session"]["session_id"], "sess-1")
        self.assertEqual(len(body["messages"]), 1)

    @patch("app.lambda_handlers.api_handler._get_store")
    def test_get_session_returns_404_for_missing(self, mock_get_store):
        store = MagicMock()
        store.get_session.side_effect = KeyError("Session not-found was not found.")
        mock_get_store.return_value = store

        event = _api_event("GET", "/api/sessions/not-found")
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 404)

    @patch("app.lambda_handlers.api_handler._get_store")
    def test_delete_session_returns_204(self, mock_get_store):
        store = MagicMock()
        mock_get_store.return_value = store

        event = _api_event("DELETE", "/api/sessions/sess-1")
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 204)
        store.delete_session.assert_called_once_with("test-user-123", "sess-1")

    @patch("app.lambda_handlers.api_handler._get_store")
    def test_update_session_requires_title(self, mock_get_store):
        store = MagicMock()
        mock_get_store.return_value = store

        event = _api_event("PATCH", "/api/sessions/sess-1", body={"title": ""})
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertIn("title", body["error"])


class RoutingTests(unittest.TestCase):
    """Tests for handler routing logic."""

    def test_unknown_route_returns_404(self):
        event = _api_event("GET", "/api/unknown")
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 404)
        body = json.loads(result["body"])
        self.assertEqual(body["error"], "Not found")

    def test_invalid_json_body_returns_400(self):
        event = _api_event("POST", "/api/sessions")
        event["body"] = "not valid json {"
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 400)

    def test_missing_auth_context_returns_404(self):
        event = {
            "rawPath": "/api/sessions",
            "requestContext": {"http": {"method": "GET"}},
        }
        result = handler(event, None)
        # Missing auth raises KeyError -> 404 (via AuthError)
        self.assertIn(result["statusCode"], [401, 404])


class SearchEndpointTests(unittest.TestCase):
    """Tests for the /api/search endpoint."""

    @patch("app.lambda_handlers.api_handler._get_store")
    def test_search_requires_query_parameter(self, mock_get_store):
        store = MagicMock()
        mock_get_store.return_value = store

        event = _api_event("GET", "/api/search", query_params={})
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertIn("q parameter", body["error"])

    @patch("app.lambda_handlers.api_handler._get_store")
    def test_search_returns_results(self, mock_get_store):
        store = MagicMock()
        store.search_messages.return_value = []
        mock_get_store.return_value = store

        event = _api_event("GET", "/api/search", query_params={"q": "hello"})
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["results"], [])
        self.assertEqual(body["query"], "hello")


if __name__ == "__main__":
    unittest.main()
