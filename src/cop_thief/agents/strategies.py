"""Offline heuristic policies — a legal baseline that needs no LLM or network.

Because the vision radius (>=1) always covers adjacent cells, an agent can see
every barrier it might step into, so these heuristics never produce an illegal
move. Strategy quality is explicitly *not* graded (assignment §3); this exists so
the full pipeline runs deterministically for tests and demos.
"""

from __future__ import annotations

import random

from ..game.actions import Action, ActionType
from ..game.board import Position, direction_offsets


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def legal_targets(obs: dict, eight_directional: bool) -> list[tuple[int, int]]:
    """Adjacent in-bounds cells that are not known barriers (always safe)."""
    row, col = obs["self"]
    rows, cols = obs["grid_size"]
    blocked = {tuple(b) for b in obs["visible_barriers"]}
    targets = []
    for d_row, d_col in direction_offsets(eight_directional):
        cell = (row + d_row, col + d_col)
        if 0 <= cell[0] < rows and 0 <= cell[1] < cols and cell not in blocked:
            targets.append(cell)
    return targets


def legal_barrier_targets(obs: dict) -> list[tuple[int, int]]:
    """Adjacent empty cells where the cop may drop a barrier (PRD deviation from §4.3).

    Any of the 8 neighbours that is on-grid, not the (visible) thief's cell, and not
    already a barrier. Always uses the 8-neighbourhood per PRD §2.4, regardless of the
    movement mode. Returns ``[]`` when no valid cell exists (barrier then unavailable).
    """
    row, col = obs["self"]
    rows, cols = obs["grid_size"]
    blocked = {tuple(b) for b in obs["visible_barriers"]}
    thief = tuple(obs["opponent"]) if obs.get("opponent_visible") else None
    targets = []
    for d_row, d_col in direction_offsets(eight_directional=True):
        cell = (row + d_row, col + d_col)
        if not (0 <= cell[0] < rows and 0 <= cell[1] < cols):
            continue
        if cell in blocked or cell == thief:
            continue
        targets.append(cell)
    return targets


def _centrality(cell: tuple[int, int], rows: int, cols: int) -> int:
    """Distance to the nearest wall — higher means more escape routes."""
    return min(cell[0], rows - 1 - cell[0], cell[1], cols - 1 - cell[1])


def _move(cell: tuple[int, int]) -> Action:
    return Action(ActionType.MOVE, Position(cell[0], cell[1]))


class HeuristicThief:
    """Flee a visible cop; otherwise drift toward open space to keep options."""

    def __init__(self, eight_directional: bool = True) -> None:
        self.eight = eight_directional

    def choose(self, obs: dict, rng: random.Random) -> Action:
        targets = legal_targets(obs, self.eight) or [tuple(obs["self"])]
        rows, cols = obs["grid_size"]
        if obs["opponent_visible"]:
            cop = tuple(obs["opponent"])
            best = max(_chebyshev(t, cop) for t in targets)
            pool = [t for t in targets if _chebyshev(t, cop) == best]
        else:
            best = max(_centrality(t, rows, cols) for t in targets)
            pool = [t for t in targets if _centrality(t, rows, cols) == best]
        return _move(rng.choice(pool))


class HeuristicCop:
    """Chase a visible thief; wall off a corridor when chasing stalls."""

    def __init__(self, eight_directional: bool = True) -> None:
        self.eight = eight_directional

    def choose(self, obs: dict, rng: random.Random) -> Action:
        targets = legal_targets(obs, self.eight) or [tuple(obs["self"])]
        rows, cols = obs["grid_size"]
        if not obs["opponent_visible"]:
            best = max(_centrality(t, rows, cols) for t in targets)
            pool = [t for t in targets if _centrality(t, rows, cols) == best]
            return _move(rng.choice(pool))
        thief = tuple(obs["opponent"])
        here = tuple(obs["self"])
        best = min(_chebyshev(t, thief) for t in targets)
        # When the chase stalls and the thief is aligned, wall off an adjacent cell on
        # the thief's side (PRD deviation: barrier on a neighbour, not the cop's own cell).
        stalled = best >= _chebyshev(here, thief)
        aligned = here[0] == thief[0] or here[1] == thief[1]
        if stalled and aligned and obs["barriers_remaining"] > 0:
            barrier_cells = legal_barrier_targets(obs)
            if barrier_cells:
                wall = min(barrier_cells, key=lambda t: _chebyshev(t, thief))
                return Action(ActionType.BARRIER, Position(wall[0], wall[1]))
        pool = [t for t in targets if _chebyshev(t, thief) == best]
        return _move(rng.choice(pool))
