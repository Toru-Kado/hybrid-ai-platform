"""Tests for JWT auth validation utilities."""
from __future__ import annotations

import base64
import json
import os
import time
import unittest
from unittest.mock import patch

from app.lambda_handlers.auth import (
    AuthError,
    TokenClaims,
    _base64url_decode,
    _decode_jwt_unverified,
    extract_token_from_header,
    extract_user_id_from_event,
    validate_token,
)


def _make_jwt(payload: dict, header: dict | None = None) -> str:
    """Build a fake JWT (no signature verification in tests)."""
    header = header or {"alg": "RS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    signature_b64 = base64.urlsafe_b64encode(b"fake-signature").rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.{signature_b64}"


class Base64UrlDecodeTests(unittest.TestCase):
    """Tests for _base64url_decode."""

    def test_decodes_without_padding(self):
        # "hello" in base64url without padding
        encoded = base64.urlsafe_b64encode(b"hello").rstrip(b"=").decode()
        result = _base64url_decode(encoded)
        self.assertEqual(result, b"hello")

    def test_decodes_with_padding(self):
        encoded = base64.urlsafe_b64encode(b"test data").decode()
        result = _base64url_decode(encoded)
        self.assertEqual(result, b"test data")


class DecodeJwtUnverifiedTests(unittest.TestCase):
    """Tests for _decode_jwt_unverified."""

    def test_decodes_valid_jwt(self):
        payload = {"sub": "user123", "exp": 9999999999}
        token = _make_jwt(payload)
        header, decoded_payload = _decode_jwt_unverified(token)
        self.assertEqual(decoded_payload["sub"], "user123")
        self.assertEqual(header["alg"], "RS256")

    def test_raises_on_invalid_format(self):
        with self.assertRaises(AuthError):
            _decode_jwt_unverified("not.a.valid.jwt.with.too.many.parts")

    def test_raises_on_two_parts(self):
        with self.assertRaises(AuthError):
            _decode_jwt_unverified("only.two")


class ExtractTokenFromHeaderTests(unittest.TestCase):
    """Tests for extract_token_from_header."""

    def test_extracts_bearer_token(self):
        headers = {"authorization": "Bearer my-token-123"}
        result = extract_token_from_header(headers)
        self.assertEqual(result, "my-token-123")

    def test_handles_capitalized_header(self):
        headers = {"Authorization": "Bearer my-token"}
        result = extract_token_from_header(headers)
        self.assertEqual(result, "my-token")

    def test_raises_on_missing_header(self):
        with self.assertRaises(AuthError):
            extract_token_from_header({})

    def test_raises_on_non_bearer_scheme(self):
        headers = {"authorization": "Basic dXNlcjpwYXNz"}
        with self.assertRaises(AuthError):
            extract_token_from_header(headers)

    def test_raises_on_empty_header(self):
        headers = {"authorization": ""}
        with self.assertRaises(AuthError):
            extract_token_from_header(headers)


class ValidateTokenTests(unittest.TestCase):
    """Tests for validate_token."""

    def setUp(self):
        self.env_patch = patch.dict(os.environ, {
            "USER_POOL_ID": "us-east-1_TestPool",
            "USER_POOL_CLIENT_ID": "test-client-id",
            "AWS_REGION_NAME": "us-east-1",
        })
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def test_validates_valid_access_token(self):
        payload = {
            "sub": "user-abc-123",
            "token_use": "access",
            "exp": int(time.time()) + 3600,
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "client_id": "test-client-id",
        }
        token = _make_jwt(payload)
        claims = validate_token(token)
        self.assertEqual(claims.sub, "user-abc-123")
        self.assertEqual(claims.token_use, "access")

    def test_validates_valid_id_token(self):
        payload = {
            "sub": "user-xyz",
            "email": "user@example.com",
            "token_use": "id",
            "exp": int(time.time()) + 3600,
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "aud": "test-client-id",
        }
        token = _make_jwt(payload)
        claims = validate_token(token)
        self.assertEqual(claims.sub, "user-xyz")
        self.assertEqual(claims.email, "user@example.com")

    def test_raises_on_expired_token(self):
        payload = {
            "sub": "user-123",
            "token_use": "access",
            "exp": int(time.time()) - 3600,  # expired 1 hour ago
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "client_id": "test-client-id",
        }
        token = _make_jwt(payload)
        with self.assertRaises(AuthError) as ctx:
            validate_token(token)
        self.assertIn("expired", str(ctx.exception))

    def test_raises_on_wrong_issuer(self):
        payload = {
            "sub": "user-123",
            "token_use": "access",
            "exp": int(time.time()) + 3600,
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_WrongPool",
            "client_id": "test-client-id",
        }
        token = _make_jwt(payload)
        with self.assertRaises(AuthError) as ctx:
            validate_token(token)
        self.assertIn("issuer", str(ctx.exception))

    def test_raises_on_invalid_token_use(self):
        payload = {
            "sub": "user-123",
            "token_use": "refresh",  # not allowed
            "exp": int(time.time()) + 3600,
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
        }
        token = _make_jwt(payload)
        with self.assertRaises(AuthError) as ctx:
            validate_token(token)
        self.assertIn("token_use", str(ctx.exception))

    def test_raises_on_wrong_audience_for_id_token(self):
        payload = {
            "sub": "user-123",
            "token_use": "id",
            "exp": int(time.time()) + 3600,
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "aud": "wrong-client-id",
        }
        token = _make_jwt(payload)
        with self.assertRaises(AuthError) as ctx:
            validate_token(token)
        self.assertIn("audience", str(ctx.exception))

    def test_raises_on_wrong_client_id_for_access_token(self):
        payload = {
            "sub": "user-123",
            "token_use": "access",
            "exp": int(time.time()) + 3600,
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "client_id": "wrong-client-id",
        }
        token = _make_jwt(payload)
        with self.assertRaises(AuthError) as ctx:
            validate_token(token)
        self.assertIn("client_id", str(ctx.exception))

    def test_raises_on_missing_exp(self):
        payload = {
            "sub": "user-123",
            "token_use": "access",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "client_id": "test-client-id",
        }
        token = _make_jwt(payload)
        with self.assertRaises(AuthError):
            validate_token(token)


class ExtractUserIdFromEventTests(unittest.TestCase):
    """Tests for extract_user_id_from_event."""

    def test_extracts_sub_from_jwt_context(self):
        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {"sub": "user-from-jwt"}
                    }
                }
            }
        }
        result = extract_user_id_from_event(event)
        self.assertEqual(result, "user-from-jwt")

    def test_raises_on_missing_authorizer(self):
        event = {"requestContext": {}}
        with self.assertRaises(AuthError):
            extract_user_id_from_event(event)

    def test_raises_on_missing_claims(self):
        event = {"requestContext": {"authorizer": {"jwt": {}}}}
        with self.assertRaises(AuthError):
            extract_user_id_from_event(event)


if __name__ == "__main__":
    unittest.main()
