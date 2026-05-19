"""Shared constants for Lambda handlers.

Centralizes route paths, DynamoDB key prefixes, and entity type markers
so that infrastructure (CDK route registration) and application code
(handler routing) reference the same source of truth.
"""
from __future__ import annotations

# API route paths
ROUTE_HEALTH = "/api/health"
ROUTE_SESSIONS = "/api/sessions"
ROUTE_SESSIONS_ID = "/api/sessions/"  # prefix; ID appended
ROUTE_CHAT = "/api/chat"
ROUTE_CHAT_STREAM = "/api/chat/stream"
ROUTE_SEARCH = "/api/search"

# DynamoDB key prefixes (single-table design)
PK_USER_PREFIX = "USER#"
SK_SESSION_PREFIX = "SESSION#"
SK_MESSAGE_SEPARATOR = "#MSG#"

# Entity type markers stored in DynamoDB items
ENTITY_SESSION = "SESSION"
ENTITY_MESSAGE = "MESSAGE"

# Limits
MAX_TITLE_LENGTH = 200
MAX_SEARCH_LIMIT = 100
DEFAULT_SEARCH_LIMIT = 50
MAX_PREVIEW_LENGTH = 200

# DynamoDB index names
GSI1_INDEX_NAME = "GSI1"
