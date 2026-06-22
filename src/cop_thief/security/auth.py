"""Constant-time verification of the ``Authorization: Bearer <token>`` header."""

from __future__ import annotations

import hmac

_BEARER_PREFIX = "Bearer "


class AuthError(Exception):
    """Raised when a request carries a missing or invalid token."""


def extract_bearer(header: str | None) -> str | None:
    """Pull the raw token out of an ``Authorization`` header value."""
    if not header or not header.startswith(_BEARER_PREFIX):
        return None
    return header[len(_BEARER_PREFIX):].strip() or None


def verify_token(provided: str | None, expected: str | None) -> bool:
    """Constant-time token comparison. Unset ``expected`` means auth is disabled."""
    if expected is None:
        return True  # no token configured (local dev) -> open
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def require_bearer(header: str | None, expected: str | None) -> None:
    """Validate ``header`` or raise :class:`AuthError` (for MCP tool guards)."""
    if not verify_token(extract_bearer(header), expected):
        raise AuthError("missing or invalid bearer token")
