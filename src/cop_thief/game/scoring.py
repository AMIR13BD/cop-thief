"""Scoring (Dec-POMDP reward ``R``) and series totals.

Per sub-game (assignment §4.4 / SHARED_MATCH_RULES.md §1):

    cop wins   -> cop = cop_win (20),  thief = thief_loss (5)
    thief wins -> cop = cop_loss (5),  thief = thief_win (10)
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import SubGameResult


@dataclass(frozen=True)
class ScoringTable:
    """The four configurable score values."""

    cop_win: int = 20
    thief_win: int = 10
    cop_loss: int = 5
    thief_loss: int = 5

    @classmethod
    def from_config(cls, cfg: dict) -> ScoringTable:
        """Build from the ``scoring`` block of config.yaml."""
        return cls(
            cop_win=int(cfg["cop_win"]),
            thief_win=int(cfg["thief_win"]),
            cop_loss=int(cfg["cop_loss"]),
            thief_loss=int(cfg["thief_loss"]),
        )


def score_subgame(result: SubGameResult, table: ScoringTable) -> dict[str, int]:
    """Map a terminal result to ``{"cop": int, "thief": int}``."""
    if result is SubGameResult.COP_WIN:
        return {"cop": table.cop_win, "thief": table.thief_loss}
    if result is SubGameResult.THIEF_WIN:
        return {"cop": table.cop_loss, "thief": table.thief_win}
    raise ValueError(f"Cannot score a non-terminal result: {result}")


def accumulate(totals: dict[str, int], delta: dict[str, int]) -> dict[str, int]:
    """Add per-sub-game scores into a running ``{"cop", "thief"}`` tally."""
    return {
        "cop": totals.get("cop", 0) + delta["cop"],
        "thief": totals.get("thief", 0) + delta["thief"],
    }
