"""Bearer-token issuing and resolution.

Tokens replace passwords (assignment §9): they are high-entropy, revocable, and
exchanged out of band. They never live in the repo — only in the environment.
"""

from __future__ import annotations

import os
import secrets


def generate_token(num_bytes: int = 32) -> str:
    """Return a fresh URL-safe random token suitable for an Authorization header."""
    return secrets.token_urlsafe(num_bytes)


def resolve_expected_token(env_var: str = "MCP_AUTH_TOKEN") -> str | None:
    """The token THIS server requires from callers, read from the environment."""
    value = os.getenv(env_var)
    return value or None


def resolve_peer_token(env_var: str = "MCP_PEER_TOKEN") -> str | None:
    """The token used when calling the OTHER team's servers (bonus match)."""
    value = os.getenv(env_var)
    return value or None
