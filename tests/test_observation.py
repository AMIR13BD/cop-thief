"""Partial observability: vision radius, hidden opponent, barrier visibility."""

from _helpers import build_engine
from cop_thief.game.actions import Role
from cop_thief.game.observation import build_observation


def test_agent_always_sees_itself():
    eng = build_engine(cop=(0, 0), thief=(4, 4), vision=2)
    obs = build_observation(eng.state, Role.THIEF, vision_radius=2)
    assert obs["self"] == [4, 4]


def test_opponent_hidden_outside_vision():
    eng = build_engine(cop=(0, 0), thief=(4, 4), vision=2)  # distance 4 > 2
    obs = build_observation(eng.state, Role.THIEF, vision_radius=2)
    assert obs["opponent"] is None
    assert obs["opponent_visible"] is False


def test_opponent_visible_inside_vision():
    eng = build_engine(cop=(2, 2), thief=(3, 3), vision=2)  # distance 1 <= 2
    obs = build_observation(eng.state, Role.COP, vision_radius=2)
    assert obs["opponent"] == [3, 3]
    assert obs["opponent_visible"] is True


def test_only_nearby_barriers_are_reported():
    eng = build_engine(cop=(0, 0), thief=(0, 1), vision=2, barriers=[(0, 2), (4, 4)])
    obs = build_observation(eng.state, Role.COP, vision_radius=2)
    assert [0, 2] in obs["visible_barriers"]
    assert [4, 4] not in obs["visible_barriers"]


def test_cop_sees_barrier_budget_thief_does_not():
    eng = build_engine(cop=(0, 0), thief=(0, 1), vision=2, max_barriers=5)
    cop_obs = build_observation(eng.state, Role.COP, vision_radius=2)
    thief_obs = build_observation(eng.state, Role.THIEF, vision_radius=2)
    assert cop_obs["barriers_remaining"] == 5
    assert thief_obs["barriers_remaining"] == 0
