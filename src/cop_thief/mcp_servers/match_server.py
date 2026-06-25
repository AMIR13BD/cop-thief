"""Inter-group match server — the opponent team's 8-tool, two-referee contract.

Unlike ``server_app.py`` (a thin relay whose state lives in the orchestrator),
this server is a **stateful referee**: it owns a :class:`GameEngine` and both
teams submit every move to it, so the authoritative (cop-side) and mirror
(thief-side) servers stay in sync. It is **role-bound** — ``get_observation``
only ever returns this server's role's partial view, so the opponent's fog is
never leaked. Contract + handshake are documented in ``docs/MATCH_PEER.md``.

Tools (all auth'd except ``health_check``): ``health_check``, ``reset``,
``get_observation``, ``validate_action``, ``submit_turn``, ``get_match_status``,
``receive_message``, ``get_messages``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Config
from ..game.actions import Action, Role, TurnPayload
from ..game.board import Board, Position, chebyshev_distance
from ..game.engine import GameEngine
from ..game.state import GameState, SubGameResult
from ..security.auth import extract_bearer, verify_token
from ..security.tokens import resolve_expected_token
from .server_app import _authorize

# Version string returned by health_check (matches the opponent's "1.00").
MATCH_PROTOCOL_VERSION = "1.00"


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


@dataclass
class _Match:
    """The server's authoritative game state for the current sub-game."""

    role: Role
    vision: int
    rows: int
    cols: int
    eight: bool
    max_moves: int
    max_barriers: int
    engine: GameEngine | None = None
    messages: list[dict] = field(default_factory=list)
    sub_game: int = 0


def _status(state: GameState) -> str:
    return "ongoing" if not state.is_terminal else state.result.value


def _observation(state: GameState, role: Role, radius: int) -> dict:
    """The role-bound partial view, in the opponent contract's field names."""
    own = state.position_of(role)
    other = state.position_of(role.opponent)
    visible = chebyshev_distance(own, other) <= radius
    barriers = sorted(state.board.barriers, key=lambda p: (p.row, p.col))
    return {
        "role": role.value,
        "own_cell": own.to_list(),
        "move_number": state.move_number,
        "vision_radius": radius,
        "grid_size": [state.board.rows, state.board.cols],
        "visible_opponent": other.to_list() if visible else None,
        "visible_barriers": [b.to_list() for b in barriers if chebyshev_distance(own, b) <= radius],
    }


def build_match_app(role: Role, config: Config | None = None):
    """Create the FastMCP app exposing the inter-group match contract for ``role``."""
    from fastmcp import FastMCP

    cfg = config or Config.load()
    params = cfg.game_params()
    ctx = _Match(
        role=role,
        vision=cfg.vision_radius,
        rows=params.grid_rows,
        cols=params.grid_cols,
        eight=params.eight_directional,
        max_moves=params.max_moves,
        max_barriers=params.max_barriers,
    )
    mcp = FastMCP(f"cop-thief-match-{role.value}")

    @mcp.tool
    def health_check() -> dict:
        """Liveness probe (no auth)."""
        return {"ok": True, "version": MATCH_PROTOCOL_VERSION}

    @mcp.tool
    def reset(cop: list[int], thief: list[int]) -> dict:
        """Start a fresh sub-game with the given ``[row, col]`` start cells; clears messages."""
        _authorize()
        cop_pos, thief_pos = Position.from_list(cop), Position.from_list(thief)
        board = Board(ctx.rows, ctx.cols, ctx.eight, set())
        if not (board.in_bounds(cop_pos) and board.in_bounds(thief_pos)):
            return {"ok": False, "reason": "start_off_board", "status": "error"}
        if cop_pos == thief_pos:
            return {"ok": False, "reason": "start_cells_equal", "status": "error"}
        ctx.sub_game += 1
        state = GameState(
            sub_game=ctx.sub_game,
            board=board,
            cop=cop_pos,
            thief=thief_pos,
            max_moves=ctx.max_moves,
            max_barriers=ctx.max_barriers,
        )
        ctx.engine = GameEngine(state, ctx.vision)
        ctx.messages = []
        return {"ok": True, "status": "ongoing"}

    @mcp.tool
    def get_observation() -> dict:
        """This server's role-bound partial observation (opponent/barriers within radius 2)."""
        _authorize()
        if ctx.engine is None:
            return {"error": "no_active_game"}
        return _observation(ctx.engine.state, ctx.role, ctx.vision)

    @mcp.tool
    def validate_action(action: dict) -> dict:
        """Check ``action`` for this server's role without mutating state."""
        _authorize()
        if ctx.engine is None:
            return {"valid": False, "reason": "no_active_game"}
        verdict = ctx.engine.validate(ctx.role, Action.from_dict(action))
        return {"valid": verdict.legal, "reason": verdict.reason}

    @mcp.tool
    def submit_turn(payload: dict) -> dict:
        """Apply one validated turn (binding on ``action``); an illegal action loses the sub-game.

        Accepts a submit for EITHER role — both teams submit every move to both
        referees to keep them in sync (``docs/MATCH_PEER.md``).
        """
        _authorize()
        if ctx.engine is None:
            return {"accepted": False, "reason": "no_active_game",
                    "capture": False, "terminal": False, "status": "error"}
        state = ctx.engine.state
        turn = TurnPayload(
            sub_game=int(payload.get("sub_game", state.sub_game)),
            move_number=int(payload.get("move_number", state.move_number)),
            role=Role(payload["role"]),
            message=str(payload.get("message", "")),
            action=Action.from_dict(payload["action"]),
        )
        record = ctx.engine.step(turn)
        state = ctx.engine.state
        captured = state.result is SubGameResult.COP_WIN and state.reason == "capture"
        return {
            "accepted": record.legal,
            "reason": record.validation,
            "capture": captured,
            "terminal": state.is_terminal,
            "status": _status(state),
        }

    @mcp.tool
    def get_match_status() -> dict:
        """Current sub-game status, thief-move count, whose turn, and true positions."""
        _authorize()
        if ctx.engine is None:
            return {"status": "error", "thief_moves": 0, "turn": None, "cop": None, "thief": None}
        state = ctx.engine.state
        return {
            "status": _status(state),
            "thief_moves": state.move_number,
            "turn": state.to_move.value,
            "cop": state.cop.to_list(),
            "thief": state.thief.to_list(),
        }

    @mcp.tool
    def receive_message(from_role: str, message: str) -> dict:
        """Deliver the opponent's natural-language line into this server's inbox."""
        _authorize()
        ctx.messages.append({"from": from_role, "message": message})
        return {"ack": True, "count": len(ctx.messages)}

    @mcp.tool
    def get_messages() -> dict:
        """Read the inbox (cleared on ``reset``)."""
        _authorize()
        return {"messages": list(ctx.messages)}

    return mcp


def run_match_server(role: Role, host: str, port: int) -> None:
    """Launch the match server over HTTP behind the 401 bearer gate (TLS fronts HTTPS)."""
    import uvicorn
    from starlette.middleware import Middleware

    app = build_match_app(role).http_app(middleware=[Middleware(BearerAuthMiddleware)])
    uvicorn.run(app, host=host, port=port)
