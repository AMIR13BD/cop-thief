"""Partial observability (Dec-POMDP observation function ``O``).

An agent always knows its own cell, but sees the opponent and barriers only
within ``vision_radius`` (Chebyshev distance). Outside that radius the agent
gets no ground truth and must rely on the other side's natural-language
messages (SHARED_MATCH_RULES.md §2.9).
"""

from __future__ import annotations

from .actions import Role
from .board import Position, chebyshev_distance
from .state import GameState


def _visible_barriers(observer: Position, state: GameState, radius: int) -> list[list[int]]:
    """Barriers within ``radius`` king-steps of the observer, as ``[row, col]`` pairs."""
    return [
        b.to_list()
        for b in sorted(state.board.barriers, key=lambda p: (p.row, p.col))
        if chebyshev_distance(observer, b) <= radius
    ]


def build_observation(state: GameState, role: Role, vision_radius: int) -> dict:
    """Return the legal view for ``role`` — the only world info its agent may use.

    Keys:
        ``self`` / ``opponent`` — ``[row, col]`` or ``None`` when out of sight,
        ``opponent_visible`` — bool, ``visible_barriers`` — list of cells,
        plus move/budget bookkeeping the agent needs to plan a legal action.
    """
    own = state.position_of(role)
    other = state.position_of(role.opponent)
    opponent_in_sight = chebyshev_distance(own, other) <= vision_radius
    return {
        "role": role.value,
        "sub_game": state.sub_game,
        "move_number": state.move_number,
        "max_moves": state.max_moves,
        "grid_size": [state.board.rows, state.board.cols],
        "vision_radius": vision_radius,
        "self": own.to_list(),
        "opponent": other.to_list() if opponent_in_sight else None,
        "opponent_visible": opponent_in_sight,
        "visible_barriers": _visible_barriers(own, state, vision_radius),
        "barriers_remaining": state.barriers_remaining if role is Role.COP else 0,
    }
