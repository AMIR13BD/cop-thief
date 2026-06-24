"""Thief evasion policy — scores every legal move so the escape looks deliberate.

Signals combined per candidate cell (all from the legal observation only):
  * immediate safety — never walk into a cell the cop could capture next turn if a
    safer option exists, and never step toward a known cop;
  * distance — barrier-aware shortest-path distance from the cop (BFS, not raw x/y);
  * mobility — prefer cells with more exits, avoid dead-ends;
  * trap/corner — avoid walls and corners while the cop is close;
  * line of sight — bonus for breaking out of the cop's vision radius;
  * lookahead — how safe the cell still is after the cop's best single reply.

When the cop is out of sight the policy uses a *decaying* memory of where it was
last seen (never the hidden true cell); once that memory is stale it just keeps to
open, high-mobility space. Ties are broken with a small config-driven random margin.
"""

from __future__ import annotations

import logging
import random

from .geometry import (
    BIG,
    bfs,
    blocked_set,
    centrality,
    chebyshev,
    max_centrality,
    mobility,
    move_action,
    neighbours,
)
from .tuning import Tuning

_log = logging.getLogger("cop_thief.thief")


class HeuristicThief:
    """Evade intelligently using barrier-aware scoring and a decaying cop memory."""

    def __init__(self, eight_directional: bool = True, tuning: Tuning | None = None) -> None:
        self.eight = eight_directional
        self.t = tuning or Tuning()
        self._sub_game: int | None = None
        self._last_cop: tuple[int, int] | None = None
        self._age = 0  # turns since the cop was last seen

    def choose(self, obs: dict, rng: random.Random) -> object:
        self._sync(obs)
        here = tuple(obs["self"])
        rows, cols = obs["grid_size"]
        blocked = blocked_set(obs)
        legal = neighbours(here, rows, cols, blocked, self.eight)
        if not legal:
            return move_action(here)  # walled in — sit tight
        if obs["opponent_visible"]:
            self._last_cop, self._age = tuple(obs["opponent"]), 0
        else:
            self._age += 1
        cop, conf = self._belief()
        if cop is None or conf <= 0.0:
            return move_action(self._wander(legal, obs, blocked, rng))
        return move_action(self._evade(here, legal, cop, conf, obs, blocked, rng))

    # ----- belief / sub-game bookkeeping -----------------------------------
    def _sync(self, obs: dict) -> None:
        if obs["sub_game"] != self._sub_game:
            self._sub_game, self._last_cop, self._age = obs["sub_game"], None, 0

    def _belief(self) -> tuple[tuple[int, int] | None, float]:
        if self._last_cop is None:
            return None, 0.0
        decay = max(1, self.t.thief_memory_decay)
        return self._last_cop, max(0.0, 1.0 - self._age / decay)

    # ----- the two regimes -------------------------------------------------
    def _wander(self, legal, obs, blocked, rng: random.Random) -> tuple[int, int]:
        """No usable cop info: keep to open, high-mobility space (not the dead centre)."""
        rows, cols = obs["grid_size"]

        def score(cell):
            return mobility(cell, rows, cols, blocked, self.eight) + 0.5 * centrality(
                cell, rows, cols
            )

        return self._pick(legal, score, rng)

    def _evade(self, here, legal, cop, conf, obs, blocked, rng: random.Random) -> tuple[int, int]:
        rows, cols = obs["grid_size"]
        vision = obs["vision_radius"]
        cop_dist = bfs(cop, rows, cols, blocked, self.eight)
        here_gap = cop_dist.get(here, BIG)
        # Immediate safety: drop cells the cop could step onto next turn, then cells
        # that move us closer to it — but only while at least one alternative remains.
        safe = [c for c in legal if chebyshev(c, cop) >= 2] or legal
        pool = [c for c in safe if cop_dist.get(c, BIG) >= here_gap] or safe
        # One-step lookahead: BFS from each cell the cop could move to, so we know how
        # close the cop gets after its best reply to each candidate.
        cop_moves = neighbours(cop, rows, cols, blocked, self.eight)
        reach = [bfs(m, rows, cols, blocked, self.eight) for m in cop_moves]
        close = 1.0 if here_gap <= vision + 1 else 0.4  # corner-fear only when cop is near
        ceil = rows * cols

        def lookahead(cell):
            return min((d.get(cell, BIG) for d in reach), default=BIG)

        def score(cell):
            dist = min(cop_dist.get(cell, BIG), ceil)
            look = min(lookahead(cell), ceil)
            mob = mobility(cell, rows, cols, blocked, self.eight)
            corner = max_centrality(rows, cols) - centrality(cell, rows, cols)
            los = vision + 2 if chebyshev(cell, cop) > vision else 0
            return (
                self.t.thief_escape_weight * conf * dist
                + self.t.thief_future_mobility_weight * mob
                - self.t.thief_corner_penalty * conf * close * corner
                + self.t.thief_lookahead_weight * conf * look
                + conf * los
            )

        choice = self._pick(pool, score, rng)
        _log.debug(
            "thief@%s -> %s (cop@%s conf=%.2f gap=%d->%d mob=%d look=%d)",
            here, choice, cop, conf, here_gap, cop_dist.get(choice, BIG),
            mobility(choice, rows, cols, blocked, self.eight), lookahead(choice),
        )
        return choice

    def _pick(self, pool, score, rng: random.Random) -> tuple[int, int]:
        """Argmax with a small random tie-break among near-best cells (config-driven)."""
        scored = [(score(c), c) for c in pool]
        best = max(s for s, _ in scored)
        margin = self.t.thief_random_tie_break * (abs(best) + 1.0)
        near = [c for s, c in scored if best - s <= margin]
        return rng.choice(near)
