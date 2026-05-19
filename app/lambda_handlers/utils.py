"""Shared utilities for Lambda handlers.

Provides request parsing, response building, and initialization helpers
used by both the API handler and stream handler to eliminate duplication.
"""
from __future__ import annotations

import base64
import json
from typing import Any


def parse_request_body(event: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON body from an API Gateway v2 or Function URL event.

    Handles both raw and base64-encoded bodies. Returns an empty dict
    if no body is present.

    Raises:
        ValueError: If body is not valid JSON or not a JSON object.
    """
    body = event.get("body")
    if not body:
        return {}
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Request body must be a JSON object.")
    return parsed


def json_response(status_code: int, body: dict[str, Any] | None) -> dict[str, Any]:
    """Build an API Gateway v2 / Function URL JSON response.

    Args:
        status_code: HTTP status code.
        body: Response payload (None for no-body responses like 204).

    Returns:
        API Gateway v2 compatible response dict.
    """
    response: dict[str, Any] = {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
    }
    if body is not None:
        response["body"] = json.dumps(body)
    return response


def error_response(status_code: int, message: str) -> dict[str, Any]:
    """Build a standardized error response."""
    return json_response(status_code, {"error": message})


def cors_preflight_response() -> dict[str, Any]:
    """Build a CORS preflight (OPTIONS) response."""
    return {
        "statusCode": 204,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        },
    }


def extract_path_param(path: str, prefix: str) -> str:
    """Extract a path parameter after a known prefix.

    Example:
        extract_path_param("/api/sessions/abc123", "/api/sessions/") -> "abc123"

    Raises:
        ValueError: If no parameter is found after the prefix.
    """
    param = path[len(prefix):].strip("/")
    if not param:
        raise ValueError("Resource ID is required in path.")
    return param


def require_string(payload: dict[str, Any], key: str) -> str:
    """Extract a required non-empty string from a JSON payload.

    Raises:
        ValueError: If key is missing or value is empty.
    """
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required.")
    return value.strip()
