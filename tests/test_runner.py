"""Integration: the runner plays a full (short) series with consistent scoring."""

from cop_thief.config import Config
from cop_thief.game.scoring import score_subgame
from cop_thief.game.state import SubGameResult
from cop_thief.orchestrator.runner import SeriesRunner


def _short_config(num_games: int = 3) -> Config:
    config = Config.load()
    config.raw["game"]["num_games"] = num_games
    return config


def test_runner_plays_requested_number_of_subgames():
    series = SeriesRunner(_short_config(3), llm=None, log=False).run()
    assert len(series.sub_games) == 3


def test_every_subgame_reaches_a_terminal_result():
    series = SeriesRunner(_short_config(3), llm=None, log=False).run()
    for summary in series.sub_games:
        assert summary.result in {SubGameResult.COP_WIN.value, SubGameResult.THIEF_WIN.value}


def test_totals_equal_sum_of_subgame_scores():
    config = _short_config(4)
    series = SeriesRunner(config, llm=None, log=False).run()
    table = config.scoring_table()
    expected = {"cop": 0, "thief": 0}
    for summary in series.sub_games:
        delta = score_subgame(SubGameResult(summary.result), table)
        expected = {k: expected[k] + delta[k] for k in expected}
    assert series.totals == expected


def test_run_is_reproducible_with_fixed_seed():
    a = SeriesRunner(_short_config(3), llm=None, log=False).run()
    b = SeriesRunner(_short_config(3), llm=None, log=False).run()
    assert a.totals == b.totals
    assert [s.result for s in a.sub_games] == [s.result for s in b.sub_games]
