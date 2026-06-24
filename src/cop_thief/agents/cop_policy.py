"""Cop pursuit policy — chase on the shortest barrier-aware path and wall a lane
only when it is genuinely worth a turn.

Movement: capture if the thief is one legal step away; otherwise step along the BFS
shortest path toward it (around barriers). When the thief is out of sight, head for
its last-seen cell from a *decaying* memory, or patrol the open middle — never the
hidden true cell.

Barriers: every legal adjacent candidate is *simulated*. Its value is how much it
shrinks the thief's best escape (barrier-aware distance + mobility of the thief's
best next cell) minus any damage it does to the cop's own route to the thief. A
barrier is placed only when the best candidate clears ``cop_barrier_min_value`` —
and even then only up to ``cop_barrier_max_probability`` of the time, so the cop
keeps chasing rather than spamming walls.
"""

from __future__ import annotations

import logging
import random

from .geometry import (
    BIG,
    barrier_action,
    bfs,
    blocked_set,
    centrality,
    chebyshev,
    legal_barrier_targets,
    mobility,
    move_action,
    neighbours,
)
from .tuning import Tuning

_log = logging.getLogger("cop_thief.cop")


class HeuristicCop:
    """Chase via shortest path; place a barrier only when it has tactical value."""

    def __init__(self, eight_directional: bool = True, tuning: Tuning | None = None) -> None:
        self.eight = eight_directional
        self.t = tuning or Tuning()
        self._sub_game: int | None = None
        self._last_thief: tuple[int, int] | None = None
        self._age = 0

    def choose(self, obs: dict, rng: random.Random) -> object:
        self._sync(obs)
        here = tuple(obs["self"])
        rows, cols = obs["grid_size"]
        blocked = blocked_set(obs)
        legal = neighbours(here, rows, cols, blocked, self.eight)
        if not legal:
            return move_action(here)
        if obs["opponent_visible"]:
            self._last_thief, self._age = tuple(obs["opponent"]), 0
            thief = tuple(obs["opponent"])
            if thief in set(legal):  # capture: step onto the thief's exact cell
                return move_action(thief)
            barrier = self._maybe_barrier(here, thief, obs, blocked, rng)
            if barrier is not None:
                return barrier
            return move_action(self._chase(thief, legal, rows, cols, blocked, rng))
        # thief unseen: use decaying memory, else patrol the open middle
        self._age += 1
        target, conf = self._belief()
        if target is None or conf <= 0.0:
            return move_action(self._patrol(legal, rows, cols, blocked, rng))
        return move_action(self._chase(target, legal, rows, cols, blocked, rng))

    # ----- memory ----------------------------------------------------------
    def _sync(self, obs: dict) -> None:
        if obs["sub_game"] != self._sub_game:
            self._sub_game, self._last_thief, self._age = obs["sub_game"], None, 0

    def _belief(self) -> tuple[tuple[int, int] | None, float]:
        if self._last_thief is None:
            return None, 0.0
        decay = max(1, self.t.thief_memory_decay)
        return self._last_thief, max(0.0, 1.0 - self._age / decay)

    # ----- movement --------------------------------------------------------
    def _chase(self, target, legal, rows, cols, blocked, rng: random.Random) -> tuple[int, int]:
        dist = bfs(target, rows, cols, blocked, self.eight)  # path distances from the target

        def key(cell):
            return (dist.get(cell, BIG), chebyshev(cell, target))

        best = min(key(c) for c in legal)
        return rng.choice([c for c in legal if key(c) == best])

    def _patrol(self, legal, rows, cols, blocked, rng: random.Random) -> tuple[int, int]:
        def score(cell):
            mob = mobility(cell, rows, cols, blocked, self.eight)
            return centrality(cell, rows, cols) + 0.25 * mob

        best = max(score(c) for c in legal)
        return rng.choice([c for c in legal if score(c) == best])

    # ----- barriers --------------------------------------------------------
    def _maybe_barrier(self, here, thief, obs, blocked, rng: random.Random):
        """Place a barrier only if a candidate's simulated value clears the threshold."""
        if obs["barriers_remaining"] <= 0:
            return None
        rows, cols = obs["grid_size"]
        if chebyshev(here, thief) < self.t.cop_barrier_min_gap:
            return None  # close enough to chase/capture; don't waste the turn
        # Only walls that sit on one of the thief's own escape cells can shrink its
        # options (the cop can only place next to itself, so this also keeps the
        # barrier on the near edge of the thief's route, not a random nearby cell).
        candidates = [c for c in legal_barrier_targets(obs) if chebyshev(c, thief) == 1]
        if not candidates:
            return None
        base_escape = self._escape_quality(here, thief, rows, cols, blocked)
        base_reach = bfs(here, rows, cols, blocked, self.eight).get(thief, BIG)
        best_cell, best_value = None, -BIG
        for cell in candidates:
            walled = blocked | {cell}
            escape_after = self._escape_quality(here, thief, rows, cols, walled)
            reach_after = bfs(here, rows, cols, walled, self.eight).get(thief, BIG)
            cop_penalty = max(0, reach_after - base_reach)  # don't wall off our own route
            value = (base_escape - escape_after) - cop_penalty
            if value > best_value:
                best_cell, best_value = cell, value
        if best_cell is None or best_value < self.t.cop_barrier_min_value:
            _log.debug("cop@%s no useful barrier (best value=%.2f < %.2f)",
                       here, best_value, self.t.cop_barrier_min_value)
            return None
        if rng.random() >= self.t.cop_barrier_max_probability:
            return None  # useful, but keep chasing this turn so we don't spam walls
        _log.debug("cop@%s wall %s value=%.2f (thief@%s)", here, best_cell, best_value, thief)
        return barrier_action(best_cell)

    def _escape_quality(self, cop, thief, rows, cols, blocked) -> float:
        """Total escape capacity from ``thief``: every legal next cell contributes its
        distance from the cop plus its onward mobility, so walling any one of them
        lowers the score (and walling a better escape lowers it more)."""
        moves = neighbours(thief, rows, cols, blocked, self.eight)
        if not moves:
            return 0.0  # thief boxed in — the best possible outcome for the cop
        dist = bfs(cop, rows, cols, blocked, self.eight)
        return sum(
            min(dist.get(m, BIG), rows * cols) + 0.5 * mobility(m, rows, cols, blocked, self.eight)
            for m in moves
        )
