"""Tests for shared Lambda handler utilities."""
from __future__ import annotations

import base64
import json
import unittest

from app.lambda_handlers.utils import (
    cors_preflight_response,
    error_response,
    extract_path_param,
    json_response,
    parse_request_body,
    require_string,
)


class ParseRequestBodyTests(unittest.TestCase):
    """Tests for parse_request_body utility."""

    def test_parses_json_body(self):
        event = {"body": '{"prompt": "hello"}'}
        result = parse_request_body(event)
        self.assertEqual(result, {"prompt": "hello"})

    def test_returns_empty_dict_for_no_body(self):
        event = {}
        result = parse_request_body(event)
        self.assertEqual(result, {})

    def test_returns_empty_dict_for_empty_body(self):
        event = {"body": ""}
        result = parse_request_body(event)
        self.assertEqual(result, {})

    def test_decodes_base64_encoded_body(self):
        payload = {"key": "value"}
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        event = {"body": encoded, "isBase64Encoded": True}
        result = parse_request_body(event)
        self.assertEqual(result, payload)

    def test_raises_on_invalid_json(self):
        event = {"body": "not json {{{"}
        with self.assertRaises(ValueError) as ctx:
            parse_request_body(event)
        self.assertIn("valid JSON", str(ctx.exception))

    def test_raises_on_non_object_json(self):
        event = {"body": '["array", "not", "object"]'}
        with self.assertRaises(ValueError) as ctx:
            parse_request_body(event)
        self.assertIn("JSON object", str(ctx.exception))

    def test_raises_on_json_string(self):
        event = {"body": '"just a string"'}
        with self.assertRaises(ValueError) as ctx:
            parse_request_body(event)
        self.assertIn("JSON object", str(ctx.exception))


class JsonResponseTests(unittest.TestCase):
    """Tests for json_response utility."""

    def test_builds_response_with_body(self):
        result = json_response(200, {"status": "ok"})
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(json.loads(result["body"]), {"status": "ok"})
        self.assertEqual(result["headers"]["Content-Type"], "application/json")

    def test_builds_response_without_body(self):
        result = json_response(204, None)
        self.assertEqual(result["statusCode"], 204)
        self.assertNotIn("body", result)

    def test_includes_cors_headers(self):
        result = json_response(200, {})
        self.assertEqual(result["headers"]["Access-Control-Allow-Origin"], "*")


class ErrorResponseTests(unittest.TestCase):
    """Tests for error_response utility."""

    def test_wraps_message_in_error_key(self):
        result = error_response(400, "Bad input")
        body = json.loads(result["body"])
        self.assertEqual(body, {"error": "Bad input"})
        self.assertEqual(result["statusCode"], 400)


class CorsPreflightResponseTests(unittest.TestCase):
    """Tests for cors_preflight_response utility."""

    def test_returns_204_with_cors_headers(self):
        result = cors_preflight_response()
        self.assertEqual(result["statusCode"], 204)
        self.assertIn("Access-Control-Allow-Methods", result["headers"])
        self.assertIn("Access-Control-Max-Age", result["headers"])


class ExtractPathParamTests(unittest.TestCase):
    """Tests for extract_path_param utility."""

    def test_extracts_param_from_path(self):
        result = extract_path_param("/api/sessions/abc123", "/api/sessions/")
        self.assertEqual(result, "abc123")

    def test_strips_trailing_slash(self):
        result = extract_path_param("/api/sessions/abc123/", "/api/sessions/")
        self.assertEqual(result, "abc123")

    def test_raises_on_empty_param(self):
        with self.assertRaises(ValueError):
            extract_path_param("/api/sessions/", "/api/sessions/")


class RequireStringTests(unittest.TestCase):
    """Tests for require_string utility."""

    def test_extracts_non_empty_string(self):
        result = require_string({"name": "  hello  "}, "name")
        self.assertEqual(result, "hello")

    def test_raises_on_missing_key(self):
        with self.assertRaises(ValueError):
            require_string({}, "name")

    def test_raises_on_empty_string(self):
        with self.assertRaises(ValueError):
            require_string({"name": "   "}, "name")

    def test_raises_on_non_string_value(self):
        with self.assertRaises(ValueError):
            require_string({"name": 123}, "name")


if __name__ == "__main__":
    unittest.main()
