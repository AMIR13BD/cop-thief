"""Bearer-token auth and token issuing for the MCP boundary."""

import pytest

from cop_thief.security.auth import AuthError, extract_bearer, require_bearer, verify_token
from cop_thief.security.tokens import generate_token


def test_extract_bearer_pulls_the_token():
    assert extract_bearer("Bearer abc123") == "abc123"


def test_extract_bearer_rejects_other_schemes():
    assert extract_bearer("Basic abc123") is None
    assert extract_bearer(None) is None


def test_verify_token_is_constant_time_match():
    assert verify_token("secret", "secret") is True
    assert verify_token("secret", "other") is False


def test_unset_expected_token_means_auth_disabled():
    assert verify_token(None, None) is True  # local dev: no token configured -> open


def test_require_bearer_raises_on_bad_token():
    with pytest.raises(AuthError):
        require_bearer("Bearer wrong", "right")


def test_generated_tokens_are_unique_and_long():
    a, b = generate_token(), generate_token()
    assert a != b
    assert len(a) > 20
