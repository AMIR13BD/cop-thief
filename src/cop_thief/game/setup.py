"""Build a fresh sub-game: the Dec-POMDP initial state distribution.

Start cells come from a seeded RNG so a match is reproducible
(SHARED_MATCH_RULES.md §2.4). Cop and thief never share a cell and, when the
grid allows, begin beyond each other's vision radius (§2.9).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .board import Board, Position, chebyshev_distance
from .state import GameState


@dataclass(frozen=True)
class GameParams:
    """Immutable per-match game parameters resolved from config."""

    grid_rows: int
    grid_cols: int
    max_moves: int
    num_games: int
    max_barriers: int
    eight_directional: bool
    vision_radius: int
    start_outside_vision: bool
    strategy: dict = field(default_factory=dict)  # heuristic tuning (config 'strategy' block)


def _draw_start(params: GameParams, rng: random.Random) -> tuple[Position, Position]:
    """Pick distinct cop/thief cells, preferring thief beyond the cop's vision."""
    cells = [
        Position(r, c) for r in range(params.grid_rows) for c in range(params.grid_cols)
    ]
    cop = rng.choice(cells)
    others = [c for c in cells if c != cop]
    if params.start_outside_vision:
        far = [c for c in others if chebyshev_distance(cop, c) > params.vision_radius]
        if far:
            others = far
    return cop, rng.choice(others)


def new_subgame(sub_game: int, params: GameParams, rng: random.Random) -> GameState:
    """Create the :class:`GameState` for sub-game ``sub_game`` (1-indexed)."""
    cop, thief = _draw_start(params, rng)
    board = Board(params.grid_rows, params.grid_cols, params.eight_directional)
    return GameState(
        sub_game=sub_game,
        board=board,
        cop=cop,
        thief=thief,
        max_moves=params.max_moves,
        max_barriers=params.max_barriers,
    )
