"""Build the final JSON reports (assignment §9.1 internal, §9.2 bonus).

The internal report is for a team that ran both agents itself; the bonus report
is the mutually-agreed inter-group form. Both are emitted exactly as the spec
shows so the grading harness can parse them.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ..config import Config
from .results import SeriesResult


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


def compute_bonus_claim(totals_by_group: dict[str, int]) -> dict[str, int]:
    """Apply the fixed bonus rule: higher total -> 10, lower -> 7, tie -> 5 each."""
    (team_a, score_a), (team_b, score_b) = totals_by_group.items()
    if score_a == score_b:
        return {team_a: 5, team_b: 5}
    if score_a > score_b:
        return {team_a: 10, team_b: 7}
    return {team_a: 7, team_b: 10}


def build_bonus_report(
    groups: dict[str, str],
    repos: dict[str, str],
    mcp_urls: dict[str, str],
    students: dict[str, list],
    sub_games: list[dict],
    totals_by_group: dict[str, int],
    timezone_name: str = "Asia/Jerusalem",
) -> dict:
    """Assemble the inter-group bonus report (§9.2); both teams email this verbatim."""
    return {
        "report_type": "bonus_game",
        "groups": groups,
        "github_repo_group_1": repos["group_1"],
        "github_repo_group_2": repos["group_2"],
        "mcp_url_group_1_cop": mcp_urls["group_1_cop"],
        "mcp_url_group_1_thief": mcp_urls["group_1_thief"],
        "mcp_url_group_2_cop": mcp_urls["group_2_cop"],
        "mcp_url_group_2_thief": mcp_urls["group_2_thief"],
        "timezone": timezone_name,
        "students_group_1": students["group_1"],
        "students_group_2": students["group_2"],
        "sub_games": sub_games,
        "totals_by_group": totals_by_group,
        "bonus_claim": compute_bonus_claim(totals_by_group),
        "mutual_agreement": True,
    }


def write_report(report: dict, output_dir: str | Path) -> Path:
    """Write ``report`` to a timestamped JSON file and return its path."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"report_{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
