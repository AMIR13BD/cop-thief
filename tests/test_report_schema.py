"""Report schemas: internal (§9.1), bonus (§9.2), and the bonus-claim rule."""

from cop_thief.config import Config
from cop_thief.orchestrator.report_builder import (
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
