"""Result containers and the timestamped JSONL turn log.

The log captures every message, action, validation result, and score
(SHARED_MATCH_RULES.md §3) for joint debugging and as evidence in the README.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..game.state import TurnRecord


@dataclass
class SubGameSummary:
    """The outcome of one sub-game, scored and ready for the report."""

    sub_game: int
    result: str
    reason: str
    moves: int
    score: dict[str, int]
    start: dict[str, list[int]]
    barriers: list[list[int]] = field(default_factory=list)


@dataclass
class SeriesResult:
    """All sub-game outcomes plus the running totals for the series."""

    sub_games: list[SubGameSummary]
    totals: dict[str, int]
    # Inter-group match extras (None for the local series): per-team point totals
    # across all 6 sub-games and a per-sub-game breakdown, used for the result email.
    per_team: dict[str, int] | None = None
    breakdown: list[dict] | None = None


def _record_dict(record: TurnRecord) -> dict:
    """Serialise a :class:`TurnRecord` (the ``role`` enum becomes its value)."""
    data = asdict(record)
    data["role"] = record.role.value
    return data


class TurnLogWriter:
    """Append-only JSONL writer; one file per series run under the log directory."""

    def __init__(self, log_dir: str | Path) -> None:
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.path = directory / f"series_{stamp}.jsonl"
        self._handle = self.path.open("w", encoding="utf-8")

    def _emit(self, payload: dict) -> None:
        self._handle.write(json.dumps(payload) + "\n")
        self._handle.flush()

    def turn(self, record: TurnRecord) -> None:
        """Log one validated turn."""
        self._emit({"event": "turn", **_record_dict(record)})

    def subgame_end(self, summary: SubGameSummary) -> None:
        """Log a sub-game's final outcome."""
        self._emit({"event": "subgame_end", **asdict(summary)})

    def void(self, sub_game: int, reason: str) -> None:
        """Log a sub-game voided as a Technical Loss (§9) before it is re-run."""
        self._emit({"event": "technical_loss", "sub_game": sub_game, "reason": reason})

    def series_end(self, totals: dict[str, int]) -> None:
        """Log the series totals."""
        self._emit({"event": "series_end", "totals": totals})

    def close(self) -> None:
        """Flush and close the log file."""
        self._handle.close()
