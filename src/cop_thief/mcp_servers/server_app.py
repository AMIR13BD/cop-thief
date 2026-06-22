"""Shared FastMCP application factory for the cop and thief servers.

The MCP server is the network boundary: it exposes *tools* over HTTPS and never
hosts the LLM (assignment §5.2). The authoritative state lives in a
:class:`SubGameReferee`; tools fetch the legal observation and submit validated
turns. Every state-changing tool requires a bearer token in the Authorization
header (assignment §6 / SHARED_MATCH_RULES.md §3).

``fastmcp`` is imported lazily so importing this module never requires the SDK.
"""

from __future__ import annotations

import random

from ..config import Config
from ..game.actions import Role, TurnPayload
from ..game.setup import new_subgame
from ..orchestrator.referee import SubGameReferee
from ..orchestrator.results import _record_dict
from ..security.auth import require_bearer
from ..security.tokens import resolve_expected_token


def _incoming_authorization() -> str | None:
    """Read the Authorization header from the active MCP HTTP request, if any."""
    try:
        from fastmcp.server.dependencies import get_http_headers

        headers = {k.lower(): v for k, v in get_http_headers().items()}
        return headers.get("authorization")
    except Exception:  # noqa: BLE001 — non-HTTP transport or unavailable context
        return None


def _authorize() -> None:
    """Raise unless the caller presents the expected bearer token (if configured)."""
    require_bearer(_incoming_authorization(), resolve_expected_token())


class _ServerState:
    """Holds the role's referee and advances through the series of sub-games."""

    def __init__(self, role: Role, config: Config) -> None:
        self.role = role
        self.params = config.game_params()
        self.vision = config.vision_radius
        self._rng = random.Random(config.seed)
        self.sub_game = 0
        self.referee: SubGameReferee = self._next()

    def _next(self) -> SubGameReferee:
        self.sub_game += 1
        return SubGameReferee(new_subgame(self.sub_game, self.params, self._rng), self.vision)

    def reset(self) -> int:
        self.referee = self._next()
        return self.sub_game


def build_mcp_app(role: Role, config: Config | None = None):
    """Create the FastMCP app exposing this role's tools."""
    from fastmcp import FastMCP

    state = _ServerState(role, config or Config.load())
    mcp = FastMCP(f"cop-thief-{role.value}")

    @mcp.tool
    def health() -> dict:
        """Liveness probe (no auth) for deployment checks."""
        return {"status": "ok", "role": role.value, "sub_game": state.sub_game}

    @mcp.tool
    def whose_turn() -> dict:
        """Whether it is this role's turn and whether the sub-game is over."""
        _authorize()
        return {"to_move": state.referee.whose_turn().value, "over": state.referee.is_over()}

    @mcp.tool
    def observe() -> dict:
        """This role's legal partial observation (own cell + what is in vision)."""
        _authorize()
        return state.referee.observe(role)

    @mcp.tool
    def submit_turn(message: str, action: dict, move_number: int = 0) -> dict:
        """Validate and apply a turn; the result is decided by ``action``, not ``message``."""
        _authorize()
        payload = TurnPayload.from_dict(
            {
                "sub_game": state.sub_game,
                "move_number": move_number,
                "role": role.value,
                "message": message,
                "action": action,
            }
        )
        return _record_dict(state.referee.submit(payload))

    @mcp.tool
    def reset() -> dict:
        """Advance to the next sub-game in the series."""
        _authorize()
        return {"sub_game": state.reset()}

    return mcp


def run_server(role: Role, host: str, port: int) -> None:
    """Launch the server over HTTP (front with TLS/ngrok for the HTTPS requirement)."""
    build_mcp_app(role).run(transport="http", host=host, port=port)
