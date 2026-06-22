"""Prompts, LLM builder, log writer, and report writing."""

import json

from cop_thief.game.actions import Role
from cop_thief.game.state import TurnRecord
from cop_thief.orchestrator.llm_client import _accepts_temperature, build_llm
from cop_thief.orchestrator.prompts import ACTION_SCHEMA, build_system_prompt, build_user_prompt
from cop_thief.orchestrator.report_builder import write_report
from cop_thief.orchestrator.results import SubGameSummary, TurnLogWriter


def test_prompts_mention_role_and_carry_messages():
    assert "COP" in build_system_prompt("cop")
    assert "THIEF" in build_system_prompt("thief")
    user = build_user_prompt({"self": [0, 0]}, ["watch the north exit"])
    assert "watch the north exit" in user
    assert ACTION_SCHEMA["required"] == ["message", "action"]


def test_accepts_temperature_excludes_opus_and_fable():
    assert _accepts_temperature("claude-haiku-4-5") is True
    assert _accepts_temperature("claude-opus-4-8") is False
    assert _accepts_temperature("claude-fable-5") is False


def test_build_llm_returns_none_without_anthropic_provider():
    assert build_llm({"provider": "heuristic", "model": "x"}) is None


def test_build_llm_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert build_llm({"provider": "anthropic", "model": "x"}) is None


def test_turn_log_writer_emits_one_line_per_event(tmp_path):
    writer = TurnLogWriter(tmp_path / "logs")
    record = TurnRecord(
        timestamp="t", sub_game=1, move_number=1, role=Role.COP, message="hi",
        action={"type": "move", "to": [0, 1]}, legal=True, validation="ok",
        cop=[0, 1], thief=[4, 4],
    )
    writer.turn(record)
    writer.subgame_end(
        SubGameSummary(1, "cop_win", "capture", 1, {"cop": 20, "thief": 5},
                       {"cop": [0, 0], "thief": [4, 4]})
    )
    writer.series_end({"cop": 20, "thief": 5})
    writer.close()
    lines = writer.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["role"] == "cop"
    assert json.loads(lines[2])["event"] == "series_end"


def test_write_report_round_trips_json(tmp_path):
    path = write_report({"group_name": "T", "totals": {"cop": 1, "thief": 2}}, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["totals"] == {"cop": 1, "thief": 2}
