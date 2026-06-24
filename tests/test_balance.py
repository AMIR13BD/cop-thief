"""Sanity guard on game balance: with the offline heuristics neither side should
sweep, and the cop should actually place barriers over a seeded sample. This is a
deterministic regression guard against the old 100%-cop / zero-barrier behaviour —
not a precise target (strategy quality is not graded, §3)."""

import copy

from cop_thief.config import Config
from cop_thief.orchestrator.runner import SeriesRunner

_SEEDS = range(500, 510)  # 10 series x 6 sub-games = 60 deterministic sub-games


def _play_all() -> list:
    base = Config.load()
    summaries = []
    for seed in _SEEDS:
        raw = copy.deepcopy(base.raw)
        raw["match"]["seed"] = seed
        summaries.extend(SeriesRunner(Config(raw), llm=None, log=False).run().sub_games)
    return summaries


def test_outcomes_are_mixed_not_a_sweep():
    results = [s.result for s in _play_all()]
    cop_wins = results.count("cop_win")
    assert 0 < cop_wins < len(results)  # both sides win at least one
    # within the rough sanity band the user asked for (~35-65% cop)
    assert 0.30 <= cop_wins / len(results) <= 0.70


def test_cop_actually_places_barriers():
    total_barriers = sum(len(s.barriers) for s in _play_all())
    assert total_barriers > 0
