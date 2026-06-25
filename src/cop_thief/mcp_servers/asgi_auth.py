"""Transport-level bearer-token gate for the match servers (assignment §7).

Split out of ``match_server`` to stay within the 150-line limit.
"""

from __future__ import annotations

from ..security.auth import extract_bearer, verify_token
from ..security.tokens import resolve_expected_token


class BearerAuthMiddleware:
    """ASGI gate: reject tokenless/invalid HTTP requests with 401 before any tool runs.

    Defense-in-depth on top of each tool's ``_authorize`` — the assignment (§7) and
    the opponent's check expect a true transport-level 401, not a per-tool error.
    When no token is configured (local dev) the gate is open.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        expected = resolve_expected_token()
        if expected is not None:
            headers = dict(scope.get("headers") or [])
            provided = extract_bearer(headers.get(b"authorization", b"").decode())
            if not verify_token(provided, expected):
                body = b'{"error": "missing or invalid bearer token"}'
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode()),
                                (b"www-authenticate", b"Bearer")],
                })
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
