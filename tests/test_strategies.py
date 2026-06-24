"""Heuristic-policy behaviour: cop barrier placement (config-driven, not spammed),
thief evasion with last-seen memory, and the partial-observability guarantee that
neither side can read a hidden opponent's true cell."""

import random

from cop_thief.agents.strategies import HeuristicCop, HeuristicThief, _chebyshev
from cop_thief.game.actions import ActionType


def _obs(
    self_cell,
    *,
    opponent=None,
    grid=(5, 5),
    barriers=(),
    barriers_remaining=5,
    vision=2,
    sub_game=1,
):
    """A partial-observation dict shaped exactly like ``build_observation`` output."""
    return {
        "sub_game": sub_game,
        "self": list(self_cell),
        "grid_size": list(grid),
        "visible_barriers": [list(b) for b in barriers],
        "opponent": list(opponent) if opponent is not None else None,
        "opponent_visible": opponent is not None,
        "barriers_remaining": barriers_remaining,
        "vision_radius": vision,
    }


def test_cop_places_barrier_when_policy_fires():
    cop = HeuristicCop(barrier_prob=1.0, barrier_min_gap=2)
    obs = _obs((2, 2), opponent=(2, 4))  # thief visible at distance 2
    action = cop.choose(obs, random.Random(0))
    assert action.type is ActionType.BARRIER
    assert _chebyshev(tuple(action.to.to_list()), (2, 2)) == 1  # an adjacent cell
    assert tuple(action.to.to_list()) not in {(2, 2), (2, 4)}


def test_cop_never_places_when_prob_is_zero():
    cop = HeuristicCop(barrier_prob=0.0, barrier_min_gap=2)
    obs = _obs((2, 2), opponent=(2, 4))
    assert cop.choose(obs, random.Random(0)).type is ActionType.MOVE


def test_cop_does_not_place_when_thief_invisible():
    cop = HeuristicCop(barrier_prob=1.0, barrier_min_gap=2)
    assert cop.choose(_obs((2, 2)), random.Random(0)).type is ActionType.MOVE


def test_cop_captures_rather_than_walling_when_adjacent():
    cop = HeuristicCop(barrier_prob=1.0, barrier_min_gap=2)
    obs = _obs((2, 2), opponent=(2, 3))  # gap 1 < min_gap -> chase, do not wall
    action = cop.choose(obs, random.Random(0))
    assert action.type is ActionType.MOVE
    assert action.to.to_list() == [2, 3]  # steps onto the thief = capture


def test_thief_never_steps_toward_a_visible_cop():
    thief = HeuristicThief()
    obs = _obs((2, 2), opponent=(2, 3))
    chosen = tuple(thief.choose(obs, random.Random(1)).to.to_list())
    assert _chebyshev(chosen, (2, 3)) >= _chebyshev((2, 2), (2, 3))


def test_thief_flees_using_last_seen_cop_after_it_vanishes():
    thief = HeuristicThief()
    thief.choose(_obs((2, 2), opponent=(2, 3)), random.Random(2))  # see the cop, remember it
    obs = _obs((2, 1))  # cop now out of sight
    chosen = tuple(thief.choose(obs, random.Random(2)).to.to_list())
    assert _chebyshev(chosen, (2, 3)) >= _chebyshev((2, 1), (2, 3))  # still flees the memory


def test_thief_forgets_the_cop_at_a_new_subgame():
    thief = HeuristicThief()
    thief.choose(_obs((2, 2), opponent=(2, 3), sub_game=1), random.Random(3))
    assert thief._last_cop is not None
    thief.choose(_obs((2, 2), sub_game=2), random.Random(3))
    assert thief._last_cop is None


def test_neither_heuristic_can_read_a_hidden_opponent():
    # With the opponent out of vision the obs carries no true cell; the policies must
    # still return a legal action without ever seeing the hidden position.
    blind = _obs((0, 0))
    assert blind["opponent"] is None and blind["opponent_visible"] is False
    assert HeuristicCop().choose(blind, random.Random(4)).type is ActionType.MOVE
    assert HeuristicThief().choose(blind, random.Random(4)).type is ActionType.MOVE
