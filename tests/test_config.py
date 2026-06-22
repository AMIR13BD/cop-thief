"""Config loading, typed accessors, and token resolution from the environment."""

from cop_thief.config import Config
from cop_thief.security.tokens import resolve_expected_token, resolve_peer_token


def test_game_params_match_shared_defaults():
    params = Config.load().game_params()
    assert (params.grid_rows, params.grid_cols) == (5, 5)
    assert params.max_moves == 25
    assert params.num_games == 6
    assert params.max_barriers == 5
    assert params.eight_directional is True
    assert params.vision_radius == 2


def test_scoring_table_matches_spec():
    table = Config.load().scoring_table()
    assert (table.cop_win, table.thief_win, table.cop_loss, table.thief_loss) == (20, 10, 5, 5)


def test_typed_accessors_are_present():
    config = Config.load()
    assert config.vision_radius == 2
    assert config.llm["provider"] in {"heuristic", "anthropic"}
    assert "dir" in config.logging
    assert "timeout_seconds" in config.turn
    assert "recipient" in config.report
    assert config.team["group_name"]


def test_env_model_override(monkeypatch):
    monkeypatch.setenv("COP_THIEF_LLM_MODEL", "claude-haiku-4-5")
    assert Config.load().llm["model"] == "claude-haiku-4-5"


def test_token_resolution_from_env(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("MCP_PEER_TOKEN", raising=False)
    assert resolve_expected_token() is None
    assert resolve_peer_token() is None
    monkeypatch.setenv("MCP_AUTH_TOKEN", "abc")
    monkeypatch.setenv("MCP_PEER_TOKEN", "def")
    assert resolve_expected_token() == "abc"
    assert resolve_peer_token() == "def"
