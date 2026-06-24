"""Offline heuristic policies — a legal baseline that needs no LLM or network.

Because the vision radius (>=1) always covers adjacent cells, an agent can see
every barrier it might step into, so these heuristics never produce an illegal
move. Strategy quality is explicitly *not* graded (assignment §3); this exists so
the full pipeline runs deterministically for tests and demos. The thief evades
with corner-avoidance and a one-step memory of where it last saw the cop; the cop
chases and, config-permitting, occasionally walls off a flight lane.
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


def _mobility(cell: tuple[int, int], obs: dict, eight_directional: bool) -> int:
    """How many legal steps lead out of ``cell`` — a proxy for "not a trap"."""
    rows, cols = obs["grid_size"]
    blocked = {tuple(b) for b in obs["visible_barriers"]}
    count = 0
    for d_row, d_col in direction_offsets(eight_directional):
        nbr = (cell[0] + d_row, cell[1] + d_col)
        if 0 <= nbr[0] < rows and 0 <= nbr[1] < cols and nbr not in blocked:
            count += 1
    return count


def _move(cell: tuple[int, int]) -> Action:
    return Action(ActionType.MOVE, Position(cell[0], cell[1]))


def _argmax(pool: list[tuple[int, int]], key, rng: random.Random) -> tuple[int, int]:
    """Pick the highest-scoring cell, breaking exact ties at random for variety."""
    best = max(key(t) for t in pool)
    return rng.choice([t for t in pool if key(t) == best])


class HeuristicThief:
    """Evade with corner-avoidance and a one-turn memory of the cop's last sighting.

    Weights (tuned for the default 5x5/king-move board) trade three signals:
    distance from the cop, how many escape routes a cell keeps, and how far the cell
    sits from the walls — so the thief flees without sprinting into a corner. State
    resets at the start of each sub-game (detected via the ``sub_game`` field).
    """

    # Weights on (distance-to-cop, escape-routes, wall-clearance). Distance leads so
    # the thief keeps running, but mobility/clearance keep it off the walls.
    _W_DIST = 4
    _W_ROUTES = 2
    _W_CLEAR = 1

    def __init__(self, eight_directional: bool = True) -> None:
        self.eight = eight_directional
        self._sub_game: int | None = None
        self._last_cop: tuple[int, int] | None = None

    def choose(self, obs: dict, rng: random.Random) -> Action:
        self._sync_sub_game(obs)
        here = tuple(obs["self"])
        rows, cols = obs["grid_size"]
        targets = legal_targets(obs, self.eight)
        if not targets:  # fully walled in — stay put (sub-game will run out)
            return _move(here)
        if obs["opponent_visible"]:
            self._last_cop = tuple(obs["opponent"])
        cop = self._last_cop
        if cop is None:
            # Cop never seen: stay mobile and off the walls, but do not rush the
            # centre (where a wide-radius cop would sit) — clearance, then routes.
            return _move(_argmax(
                targets,
                lambda t: (_centrality(t, rows, cols), _mobility(t, obs, self.eight)),
                rng,
            ))
        # Never volunteer a step toward the cop while a non-closing option exists.
        here_gap = _chebyshev(here, cop)
        safe = [t for t in targets if _chebyshev(t, cop) >= here_gap] or targets

        def score(cell: tuple[int, int]) -> int:
            return (
                self._W_DIST * _chebyshev(cell, cop)
                + self._W_ROUTES * _mobility(cell, obs, self.eight)
                + self._W_CLEAR * _centrality(cell, rows, cols)
            )

        return _move(_argmax(safe, score, rng))

    def _sync_sub_game(self, obs: dict) -> None:
        if obs["sub_game"] != self._sub_game:
            self._sub_game = obs["sub_game"]
            self._last_cop = None


class HeuristicCop:
    """Chase a visible thief; config-permitting, wall off a flight lane while closing.

    Barriers are *not* spammed: the cop only considers one when the thief is in sight
    but not yet adjacent (``barrier_min_gap`` ≤ gap ≤ vision), it still has barriers
    left, and a per-turn ``barrier_prob`` roll succeeds. It then drops the barrier on a
    neighbour cell that sits on the thief's flight lane, spending the turn in place
    (PRD deviation: a neighbour cell, never the cop's own).
    """

    def __init__(
        self,
        eight_directional: bool = True,
        barrier_prob: float = 0.5,
        barrier_min_gap: int = 2,
    ) -> None:
        self.eight = eight_directional
        self.barrier_prob = barrier_prob
        self.barrier_min_gap = barrier_min_gap

    def choose(self, obs: dict, rng: random.Random) -> Action:
        targets = legal_targets(obs, self.eight) or [tuple(obs["self"])]
        rows, cols = obs["grid_size"]
        if not obs["opponent_visible"]:
            return _move(_argmax(targets, lambda t: _centrality(t, rows, cols), rng))
        thief = tuple(obs["opponent"])
        here = tuple(obs["self"])
        barrier = self._maybe_barrier(obs, here, thief, rng)
        if barrier is not None:
            return barrier
        best = min(_chebyshev(t, thief) for t in targets)
        pool = [t for t in targets if _chebyshev(t, thief) == best]
        return _move(rng.choice(pool))

    def _maybe_barrier(self, obs, here, thief, rng: random.Random) -> Action | None:
        """Return a barrier action when policy + geometry make one worthwhile."""
        if obs["barriers_remaining"] <= 0 or self.barrier_prob <= 0:
            return None
        gap = _chebyshev(here, thief)
        if not (self.barrier_min_gap <= gap <= obs["vision_radius"]):
            return None
        if rng.random() >= self.barrier_prob:
            return None
        cells = legal_barrier_targets(obs)
        if not cells:
            return None
        rows, cols = obs["grid_size"]
        # Prefer a cell on the thief's own doorstep (a flight lane it would use);
        # otherwise the neighbour closest to the thief. Break ties toward open cells.
        lane = [c for c in cells if _chebyshev(c, thief) == 1] or cells
        wall = min(lane, key=lambda c: (_chebyshev(c, thief), -_centrality(c, rows, cols)))
        return Action(ActionType.BARRIER, Position(wall[0], wall[1]))
