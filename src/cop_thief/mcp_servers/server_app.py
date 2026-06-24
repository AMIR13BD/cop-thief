"""Shared FastMCP application factory for the cop and thief agent endpoints.

Architecture (assignment §5.2 / §14): the LLM **and** the single authoritative
game state live in the **client** (the orchestrator the students build). Each MCP
server is a *thin per-agent boundary that exposes tools only* — it never runs the
LLM and it is not the referee. Its tools cover exactly what §5.1 calls for:

* receiving/serving an agent's current observation,
* sending + recording its natural-language message and chosen action,
* mutual verification of locations.

The orchestrator (the MCP client in ``orchestrator/mcp_series.py``) owns the one
:class:`~cop_thief.orchestrator.referee.SubGameReferee` and drives the whole
series through these tools over HTTP. Every state-changing tool requires a bearer
token (assignment §6); when no token is configured (local dev) auth is open.

``fastmcp`` is imported lazily so importing this module never requires the SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Config
from ..game.actions import Role
from ..security.auth import require_bearer
from ..security.tokens import resolve_expected_token


def _incoming_authorization() -> str | None:
    """Read the Authorization header from the active MCP HTTP request, if any."""
    try:
        from fastmcp.server.dependencies import get_http_headers

        # get_http_headers() strips ``authorization`` by default; opt back in or the
        # bearer token never reaches the verifier (every state-changing tool 401s).
        headers = {k.lower(): v for k, v in get_http_headers(include={"authorization"}).items()}
        return headers.get("authorization")
    except Exception:  # noqa: BLE001 — non-HTTP transport or unavailable context
        return None


def _authorize() -> None:
    """Raise unless the caller presents the expected bearer token (if configured)."""
    require_bearer(_incoming_authorization(), resolve_expected_token())


@dataclass
class _Endpoint:
    """Per-agent scratch state pushed/pulled by the client. NOT authoritative.

    The authoritative game state lives in the orchestrator; this only mirrors what
    the client shares so the agent can read its observation and the opponent can
    read this agent's last message over MCP.
    """

    role: Role
    observation: dict = field(default_factory=dict)
    position: list[int] | None = None
    last_message: str = ""
    last_action: dict | None = None


# Cross-team wire-contract version advertised by ``health`` so a mismatch is
# caught before kickoff (docs/MATCH_PROTOCOL.md §A/§D).
PROTOCOL_VERSION = "0.1"


def build_mcp_app(role: Role, config: Config | None = None):
    """Create the FastMCP app exposing this agent's tools."""
    import random

    from fastmcp import FastMCP

    from ..agents.cop_agent import build_cop_agent
    from ..agents.thief_agent import build_thief_agent
    from ..orchestrator.llm_client import build_llm

    cfg = config or Config.load()
    state = _Endpoint(role=role)
    # Our brain, server-side — used by ``play_turn`` so an opponent referee can pull
    # this team's move (MATCH_PROTOCOL.md §D, Option 1). Falls back to the heuristic
    # when no LLM is configured; same decision path as the self-play orchestrator.
    params = cfg.game_params()
    llm = build_llm(cfg.llm)
    rng = random.Random()
    builder = build_cop_agent if role is Role.COP else build_thief_agent
    agent = builder(params, llm, rng)
    mcp = FastMCP(f"cop-thief-{role.value}")

    @mcp.tool
    def health() -> dict:
        """Liveness probe (no auth) for deployment/readiness checks."""
        return {"status": "ok", "role": role.value, "protocol": PROTOCOL_VERSION}

    @mcp.tool
    def set_context(observation: dict, position: list[int]) -> dict:
        """Client pushes this agent's current partial observation and true cell."""
        _authorize()
        state.observation = dict(observation)
        state.position = list(position)
        return {"ok": True, "role": role.value}

    @mcp.tool
    def observe() -> dict:
        """Return this agent's current legal partial observation."""
        _authorize()
        return state.observation

    @mcp.tool
    def submit_turn(message: str, action: dict) -> dict:
        """Send + record this agent's NL message and chosen action.

        The outcome is decided by ``action`` (validated by the orchestrator's
        referee), never by ``message`` — which is free text and may bluff.
        """
        _authorize()
        state.last_message = message
        state.last_action = dict(action)
        return {"role": role.value, "message": message, "action": dict(action)}

    @mcp.tool
    def last_message() -> dict:
        """Return this agent's most recent NL message (read by the opponent)."""
        _authorize()
        return {"role": role.value, "message": state.last_message}

    @mcp.tool
    def verify_location(claim: list[int]) -> dict:
        """Mutual location verification (§5.1): does ``claim`` match the true cell?"""
        _authorize()
        actual = state.position
        return {
            "role": role.value,
            "claim": list(claim),
            "actual": actual,
            "match": actual is not None and list(claim) == actual,
        }

    @mcp.tool
    def play_turn(observation: dict, opponent_message: str = "") -> dict:
        """Referee-driven turn (MATCH_PROTOCOL.md §D, Option 1).

        The opponent team's referee passes the partial ``observation`` it computed
        for THIS agent (engine ``build_observation`` shape) plus the opponent's last
        natural-language line; this team's own brain decides and returns the message
        + binding action. The result is still adjudicated by the referee on the
        ``action`` — ``message`` may bluff and is never binding.
        """
        _authorize()
        obs = dict(observation)
        inbox = [opponent_message] if opponent_message else []
        message, action = agent.decide(obs, inbox)
        # Mirror to scratch state so last_message / verify_location stay coherent.
        state.observation = obs
        if obs.get("self") is not None:
            state.position = list(obs["self"])
        state.last_message = message
        state.last_action = action.to_dict()
        return {"role": role.value, "message": message, "action": action.to_dict()}

    return mcp


def run_server(role: Role, host: str, port: int) -> None:
    """Launch the server over HTTP (front with TLS/ngrok for the HTTPS requirement)."""
    build_mcp_app(role).run(transport="http", host=host, port=port)
