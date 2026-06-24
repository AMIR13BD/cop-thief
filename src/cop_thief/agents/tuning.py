"""Config-driven weights for the heuristic policies.

Strategy quality is not graded (assignment §3), but the local demo should *look*
like two real agents. All knobs live in ``config.yaml``'s ``strategy`` block — none
are hard-coded in the policy logic — so behaviour is tunable without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tuning:
    """Resolved strategy weights (with believable defaults for the 5x5 board)."""

    # Thief — how it scores each candidate escape cell.
    thief_escape_weight: float = 3.0          # reward barrier-aware distance from the cop
    thief_future_mobility_weight: float = 1.0  # reward cells with more exits (avoid dead-ends)
    thief_corner_penalty: float = 1.5         # punish hugging walls/corners when the cop is near
    thief_lookahead_weight: float = 2.0       # reward safety after the cop's best reply
    thief_memory_decay: int = 6               # turns before a last-seen cop is forgotten
    thief_random_tie_break: float = 0.12      # only break near-ties randomly (0 = deterministic)

    # Cop — when a barrier is worth a turn instead of chasing.
    cop_barrier_min_value: float = 1.0        # minimum tactical value to bother placing one
    cop_barrier_max_probability: float = 0.7  # cap on how often a *useful* barrier is taken
    cop_barrier_min_gap: int = 2              # only consider barriers when the thief is >= this far

    @classmethod
    def from_mapping(cls, raw: dict | None) -> Tuning:
        """Build from the ``strategy`` mapping, falling back to defaults per key."""
        raw = raw or {}
        d = cls()  # defaults

        def num(key: str, default: float) -> float:
            return float(raw.get(key, default))

        def whole(key: str, default: int) -> int:
            return int(raw.get(key, default))

        return cls(
            thief_escape_weight=num("thief_escape_weight", d.thief_escape_weight),
            thief_future_mobility_weight=num(
                "thief_future_mobility_weight", d.thief_future_mobility_weight
            ),
            thief_corner_penalty=num("thief_corner_penalty", d.thief_corner_penalty),
            thief_lookahead_weight=num("thief_lookahead_weight", d.thief_lookahead_weight),
            thief_memory_decay=whole("thief_memory_decay", d.thief_memory_decay),
            thief_random_tie_break=num("thief_random_tie_break", d.thief_random_tie_break),
            cop_barrier_min_value=num("cop_barrier_min_value", d.cop_barrier_min_value),
            cop_barrier_max_probability=num(
                "cop_barrier_max_probability", d.cop_barrier_max_probability
            ),
            cop_barrier_min_gap=whole("cop_barrier_min_gap", d.cop_barrier_min_gap),
        )
