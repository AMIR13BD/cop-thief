"""The GUI driver yields well-formed per-turn snapshots over the whole series."""

from cop_thief.config import Config
from cop_thief.gui.driver import iter_series

_REQUIRED = {"sub_game", "ply", "cop", "thief", "barriers", "grid", "result", "totals", "message"}


def _short(num_games: int = 2) -> Config:
    config = Config.load()
    config.raw["game"]["num_games"] = num_games
    return config


def test_first_snapshot_is_a_subgame_start():
    snaps = list(iter_series(_short(2)))
    assert _REQUIRED.issubset(snaps[0])
    assert snaps[0]["ply"] == 0
    assert snaps[0]["result"] == "in_progress"


def test_each_subgame_emits_one_scored_end_snapshot():
    ends = [s for s in iter_series(_short(2)) if s["score"] is not None]
    assert len(ends) == 2
    assert all(s["result"] in {"cop_win", "thief_win"} for s in ends)


def test_totals_are_non_decreasing_and_final_is_positive():
    snaps = list(iter_series(_short(3)))
    cop_totals = [s["totals"]["cop"] for s in snaps]
    assert cop_totals == sorted(cop_totals)
    last = snaps[-1]["totals"]
    assert last["cop"] + last["thief"] > 0
