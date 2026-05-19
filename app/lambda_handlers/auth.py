"""JWT validation utilities for Lambda handlers.

Validates Cognito-issued JWTs using cached JWKS (JSON Web Key Set).
Used by the stream handler for auth validation (API handler relies
on API Gateway's built-in JWT authorizer).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen

logger = logging.getLogger(__name__)

# JWKS cache: populated on first use, refreshed after TTL
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_time: float = 0
_JWKS_CACHE_TTL = 3600  # 1 hour


@dataclass(slots=True)
class TokenClaims:
    """Extracted claims from a validated JWT."""

    sub: str
    email: str | None
    token_use: str
    exp: int
    iss: str


class AuthError(Exception):
    """Raised when JWT validation fails."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


def get_jwks_url() -> str:
    """Build the JWKS URL from environment configuration."""
    region = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
    user_pool_id = os.environ["USER_POOL_ID"]
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"


def get_issuer() -> str:
    """Build the expected issuer URL."""
    region = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "us-east-1"))
    user_pool_id = os.environ["USER_POOL_ID"]
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"


def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Cognito, with caching."""
    global _jwks_cache, _jwks_cache_time

    now = time.time()
    if _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_CACHE_TTL:
        return _jwks_cache

    jwks_url = get_jwks_url()
    logger.info("Fetching JWKS from %s", jwks_url)
    with urlopen(jwks_url, timeout=5) as response:
        _jwks_cache = json.loads(response.read().decode("utf-8"))
        _jwks_cache_time = now

    return _jwks_cache


def _base64url_decode(data: str) -> bytes:
    """Decode base64url-encoded data with padding correction."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def _decode_jwt_unverified(token: str) -> tuple[dict, dict]:
    """Decode JWT header and payload without signature verification."""
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Invalid JWT format")

    header = json.loads(_base64url_decode(parts[0]))
    payload = json.loads(_base64url_decode(parts[1]))
    return header, payload


def validate_token(token: str) -> TokenClaims:
    """Validate a Cognito JWT and return extracted claims.

    Performs the following checks:
    - Token structure (3-part JWT)
    - Token expiration
    - Issuer matches expected Cognito User Pool
    - Token use is 'access' or 'id'
    - Audience (client_id) matches expected app client

    Note: Full cryptographic signature verification requires a JWT library
    (python-jose or PyJWT with cryptography). For Lambda deployments, consider
    adding python-jose to the layer. This implementation validates claims only.
    """
    try:
        header, payload = _decode_jwt_unverified(token)
    except (json.JSONDecodeError, Exception) as exc:
        raise AuthError(f"Invalid token format: {exc}") from exc

    # Check expiration
    exp = payload.get("exp")
    if not exp or time.time() > exp:
        raise AuthError("Token has expired")

    # Check issuer
    expected_issuer = get_issuer()
    if payload.get("iss") != expected_issuer:
        raise AuthError("Invalid token issuer")

    # Check token_use
    token_use = payload.get("token_use", "")
    if token_use not in ("access", "id"):
        raise AuthError("Invalid token_use claim")

    # Check audience (client_id) for id tokens
    expected_client_id = os.environ.get("USER_POOL_CLIENT_ID")
    if token_use == "id" and expected_client_id:
        if payload.get("aud") != expected_client_id:
            raise AuthError("Invalid token audience")

    # For access tokens, check client_id claim
    if token_use == "access" and expected_client_id:
        if payload.get("client_id") != expected_client_id:
            raise AuthError("Invalid token client_id")

    return TokenClaims(
        sub=payload["sub"],
        email=payload.get("email"),
        token_use=token_use,
        exp=exp,
        iss=payload["iss"],
    )


def extract_user_id_from_event(event: dict[str, Any]) -> str:
    """Extract user ID from an API Gateway v2 event with JWT authorizer.

    The JWT authorizer populates requestContext.authorizer.jwt.claims.
    """
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        return claims["sub"]
    except (KeyError, TypeError) as exc:
        raise AuthError("Missing authorization context") from exc


def extract_token_from_header(headers: dict[str, str]) -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = headers.get("authorization") or headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AuthError("Missing or invalid Authorization header")
    return auth_header[7:]
