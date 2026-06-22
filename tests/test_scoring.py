"""Scoring table and series accumulation (assignment §4.4)."""

from cop_thief.game.scoring import ScoringTable, accumulate, score_subgame
from cop_thief.game.state import SubGameResult


def default_table() -> ScoringTable:
    return ScoringTable.from_config(
        {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}
    )


def test_cop_win_scores_20_5():
    assert score_subgame(SubGameResult.COP_WIN, default_table()) == {"cop": 20, "thief": 5}


def test_thief_win_scores_5_10():
    assert score_subgame(SubGameResult.THIEF_WIN, default_table()) == {"cop": 5, "thief": 10}


def test_in_progress_cannot_be_scored():
    import pytest

    with pytest.raises(ValueError):
        score_subgame(SubGameResult.IN_PROGRESS, default_table())


def test_accumulate_sums_running_totals():
    totals = {"cop": 0, "thief": 0}
    totals = accumulate(totals, {"cop": 20, "thief": 5})
    totals = accumulate(totals, {"cop": 5, "thief": 10})
    assert totals == {"cop": 25, "thief": 15}


def test_max_series_total_matches_spec():
    table = default_table()
    # 3 cop wins + 3 thief wins is the spec's 90-point ceiling for one team.
    cop_side = sum(score_subgame(SubGameResult.COP_WIN, table)["cop"] for _ in range(3))
    thief_side = sum(score_subgame(SubGameResult.THIEF_WIN, table)["thief"] for _ in range(3))
    assert cop_side + thief_side == 90
