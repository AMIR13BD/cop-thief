"""Report schemas: internal (§9.1), bonus (§9.2), and the bonus-claim rule."""

from cop_thief.config import Config
from cop_thief.orchestrator.report_builder import (
    build_bonus_from_halves,
    build_bonus_report,
    build_internal_report,
    compute_bonus_claim,
)
from cop_thief.orchestrator.results import SeriesResult, SubGameSummary

_INTERNAL_KEYS = {
    "group_name", "students", "github_repo", "cop_mcp_url", "thief_mcp_url",
    "timezone", "sub_games", "totals",
}
_BONUS_KEYS = {
    "report_type", "groups", "github_repo_group_1", "github_repo_group_2",
    "mcp_url_group_1_cop", "mcp_url_group_1_thief", "mcp_url_group_2_cop",
    "mcp_url_group_2_thief", "timezone", "students_group_1", "students_group_2",
    "sub_games", "totals_by_group", "bonus_claim", "mutual_agreement",
}


def _series() -> SeriesResult:
    summary = SubGameSummary(
        sub_game=1, result="cop_win", reason="capture", moves=4,
        score={"cop": 20, "thief": 5}, start={"cop": [0, 0], "thief": [4, 4]},
    )
    return SeriesResult(sub_games=[summary], totals={"cop": 20, "thief": 5})


def test_internal_report_has_exactly_the_spec_keys():
    report = build_internal_report(_series(), Config.load())
    assert set(report) == _INTERNAL_KEYS
    assert report["totals"] == {"cop": 20, "thief": 5}
    assert report["sub_games"][0]["result"] == "cop_win"


def test_bonus_claim_rewards_higher_total():
    assert compute_bonus_claim({"Team-A": 80, "Team-B": 60}) == {"Team-A": 10, "Team-B": 7}


def test_bonus_claim_ties_are_five_each():
    assert compute_bonus_claim({"Team-A": 70, "Team-B": 70}) == {"Team-A": 5, "Team-B": 5}


def test_bonus_report_shape_and_mutual_agreement():
    report = build_bonus_report(
        groups={"group_1": "Team-A", "group_2": "Team-B"},
        repos={"group_1": "https://x/a", "group_2": "https://x/b"},
        mcp_urls={
            "group_1_cop": "https://a-cop", "group_1_thief": "https://a-thief",
            "group_2_cop": "https://b-cop", "group_2_thief": "https://b-thief",
        },
        students={"group_1": [], "group_2": []},
        sub_games=[],
        totals_by_group={"Team-A": 60, "Team-B": 80},
    )
    assert set(report) == _BONUS_KEYS
    assert report["report_type"] == "bonus_game"
    assert report["mutual_agreement"] is True
    assert report["bonus_claim"] == {"Team-A": 7, "Team-B": 10}


def _half(group: str, name: str, sub_games: list[dict]) -> dict:
    return {
        "group_name": name, "group": group, "role": "cop", "protocol": "0.1",
        "github_repo": f"https://x/{name}", "students": [f"{name} <1>"],
        "cop_mcp_url": f"https://{name}-cop", "thief_mcp_url": f"https://{name}-thief",
        "timezone": "Asia/Jerusalem", "sub_games": sub_games, "totals": {},
    }


def _sub(idx: int, cop: int, thief: int) -> dict:
    return {"sub_game": idx, "result": "x", "reason": "y", "moves": 5,
            "score": {"cop": cop, "thief": thief}, "start": {}, "barriers": []}


def test_merge_halves_maps_cop_thief_scores_to_groups():
    # Group 1 cop in 1-3 (wins all), Group 2 cop in 4-6 (wins all).
    g1 = _half("1", "Alpha", [_sub(1, 20, 5), _sub(2, 20, 5), _sub(3, 20, 5)])
    g2 = _half("2", "Beta", [_sub(6, 20, 5), _sub(4, 20, 5), _sub(5, 20, 5)])
    report = build_bonus_from_halves(g2, g1)  # order-independent
    assert set(report) == _BONUS_KEYS
    # Each group: own cop wins (60) + opponent's thief points against them (15) = 75 each -> tie.
    assert report["totals_by_group"] == {"Alpha": 75, "Beta": 75}
    assert report["bonus_claim"] == {"Alpha": 5, "Beta": 5}
    assert [s["sub_game"] for s in report["sub_games"]] == [1, 2, 3, 4, 5, 6]
    assert report["groups"] == {"group_1": "Alpha", "group_2": "Beta"}


def test_merge_halves_requires_one_of_each_group():
    g1 = _half("1", "Alpha", [_sub(1, 20, 5)])
    import pytest

    with pytest.raises(ValueError, match="group-1 half and one group-2 half"):
        build_bonus_from_halves(g1, _half("1", "Beta", [_sub(2, 20, 5)]))
