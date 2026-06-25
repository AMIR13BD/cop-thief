"""Inter-group §9.2 ``bonus_game`` report: scoring, schema, and builders.

Split out of ``report_builder`` to keep each file within the 150-line limit.
Re-exported from ``report_builder`` so existing imports keep working.
"""

from __future__ import annotations

from ..config import Config
from .results import SeriesResult


def compute_bonus_claim(totals_by_group: dict[str, int]) -> dict[str, int]:
    """Apply the fixed bonus rule: higher total -> 10, lower -> 7, tie -> 5 each."""
    (team_a, score_a), (team_b, score_b) = totals_by_group.items()
    if score_a == score_b:
        return {team_a: 5, team_b: 5}
    if score_a > score_b:
        return {team_a: 10, team_b: 7}
    return {team_a: 7, team_b: 10}


def series_winner(totals_by_group: dict[str, int]) -> str:
    """The group with the higher total, or ``"tie"`` if equal (§9.2 ``series_winner``)."""
    (team_a, score_a), (team_b, score_b) = totals_by_group.items()
    if score_a == score_b:
        return "tie"
    return team_a if score_a > score_b else team_b


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
        "series_winner": series_winner(totals_by_group),
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


def _student_objs(raw: list) -> list[dict]:
    """Parse ``"Full Name <id>"`` strings into ``{"name","id"}`` objects (opponent shape)."""
    objs: list[dict] = []
    for entry in raw:
        s = str(entry).strip()
        if "<" in s and s.endswith(">"):
            name, ident = s[:-1].split("<", 1)
            objs.append({"name": name.strip(), "id": ident.strip()})
        else:
            objs.append({"name": s, "id": ""})
    return objs


def build_bonus_match_report(series: SeriesResult, config: Config) -> dict:
    """Build the §9.2 ``bonus_game`` report from one side's complete match data.

    ``series.breakdown`` already holds all 6 sub-game rows in the agreed shape
    (``index, winner, moves_played, cop_score, thief_score, technical_loss,
    cop_group, thief_group, winner_group``). The opponent's identity comes from
    ``config.match`` so the report is produced solo — both teams' synced engines
    yield identical results, so both produce the same report to email verbatim.
    Group 1 is the opponent (cop in sub-games 1–3); group 2 is us.
    """
    team = config.team
    m = config.match
    our = team["group_name"]
    opp = m.get("opponent_name", "ahk-yosi")
    rows = list(series.breakdown or [])
    totals_by_group = {opp: 0, our: 0}  # opponent (group_1) first to match their key order
    for r in rows:
        for role in ("cop", "thief"):
            grp, pts = r[f"{role}_group"], r[f"{role}_score"]
            totals_by_group[grp] = totals_by_group.get(grp, 0) + pts
    return build_bonus_report(
        groups={"group_1": opp, "group_2": our},
        repos={"group_1": m.get("opponent_github_repo", ""), "group_2": team["github_repo"]},
        mcp_urls={
            "group_1_cop": m.get("opponent_cop_mcp_url", ""),
            "group_1_thief": m.get("opponent_thief_mcp_url", ""),
            "group_2_cop": team["cop_mcp_url"],
            "group_2_thief": team["thief_mcp_url"],
        },
        students={
            "group_1": _student_objs(m.get("opponent_students", [])),
            "group_2": _student_objs(list(team.get("students", []))),
        },
        sub_games=rows,
        totals_by_group=totals_by_group,
        timezone_name=team["timezone"],
    )
