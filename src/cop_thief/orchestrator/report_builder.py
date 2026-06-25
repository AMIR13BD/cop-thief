"""Build the final JSON reports (assignment §9.1 internal, §9.2 bonus).

The internal report is for a team that ran both agents itself; the bonus report
is the mutually-agreed inter-group form. Both are emitted exactly as the spec
shows so the grading harness can parse them. The §9.2 bonus builders live in
``bonus_report`` and are re-exported here so existing imports keep working.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ..config import Config
from .bonus_report import (
    build_bonus_from_halves,
    build_bonus_match_report,
    build_bonus_report,
    compute_bonus_claim,
    series_winner,
)
from .results import SeriesResult

__all__ = [
    "build_internal_report", "write_report", "build_bonus_report",
    "build_bonus_from_halves", "build_bonus_match_report", "compute_bonus_claim",
    "series_winner",
]


def _sub_games(series: SeriesResult) -> list[dict]:
    return [asdict(summary) for summary in series.sub_games]


def build_internal_report(series: SeriesResult, config: Config) -> dict:
    """Assemble the internal-game report (§9.1)."""
    team = config.team
    return {
        "group_name": team["group_name"],
        "students": list(team.get("students", [])),
        "github_repo": team["github_repo"],
        "cop_mcp_url": team["cop_mcp_url"],
        "thief_mcp_url": team["thief_mcp_url"],
        "timezone": team["timezone"],
        "sub_games": _sub_games(series),
        "totals": series.totals,
    }


def write_report(report: dict, output_dir: str | Path) -> Path:
    """Write ``report`` to a timestamped JSON file and return its path."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"report_{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
