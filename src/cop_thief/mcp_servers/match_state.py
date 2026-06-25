"""Per-server match state + role-bound observation for the match server.

Split out of ``match_server`` to stay within the 150-line limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..game.actions import Role
from ..game.board import chebyshev_distance
from ..game.engine import GameEngine
from ..game.state import GameState


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
