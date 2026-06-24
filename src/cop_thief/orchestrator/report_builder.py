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


def build_bonus_from_halves(half_a: dict, half_b: dict) -> dict:
    """Merge two self-describing match halves into the §9.2 ``bonus_game`` report.

    Each half is what ``cop-thief peer-match`` writes: the refereeing team's full
    identity plus its 3 cop sub-games (``score`` is ``{"cop", "thief"}`` per
    sub-game, where ``cop`` is that refereeing group and ``thief`` is the opponent).
    Requires exactly one ``group == "1"`` half and one ``group == "2"`` half. Both
    teams run this on the same two halves and must get byte-identical JSON (§9.2),
    so every field here is deterministic.
    """
    by_group = {str(h.get("group")): h for h in (half_a, half_b)}
    if set(by_group) != {"1", "2"}:
        raise ValueError("need exactly one group-1 half and one group-2 half")
    g1, g2 = by_group["1"], by_group["2"]
    name1, name2 = g1["group_name"], g2["group_name"]

    totals_by_group = {name1: 0, name2: 0}
    for sub in g1["sub_games"]:  # g1 refereed as cop
        totals_by_group[name1] += sub["score"]["cop"]
        totals_by_group[name2] += sub["score"]["thief"]
    for sub in g2["sub_games"]:  # g2 refereed as cop
        totals_by_group[name2] += sub["score"]["cop"]
        totals_by_group[name1] += sub["score"]["thief"]

    sub_games = sorted(
        [*g1["sub_games"], *g2["sub_games"]], key=lambda s: int(s["sub_game"])
    )
    return build_bonus_report(
        groups={"group_1": name1, "group_2": name2},
        repos={"group_1": g1["github_repo"], "group_2": g2["github_repo"]},
        mcp_urls={
            "group_1_cop": g1["cop_mcp_url"],
            "group_1_thief": g1["thief_mcp_url"],
            "group_2_cop": g2["cop_mcp_url"],
            "group_2_thief": g2["thief_mcp_url"],
        },
        students={"group_1": list(g1["students"]), "group_2": list(g2["students"])},
        sub_games=sub_games,
        totals_by_group=totals_by_group,
        timezone_name=g1.get("timezone", "Asia/Jerusalem"),
    )


def write_report(report: dict, output_dir: str | Path) -> Path:
    """Write ``report`` to a timestamped JSON file and return its path."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"report_{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
