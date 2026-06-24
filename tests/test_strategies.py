"""Heuristic-policy behaviour: intelligent thief evasion (safety, mobility, memory,
no hidden-state leak) and tactical, value-gated cop barriers."""

import random

from cop_thief.agents.cop_policy import HeuristicCop
from cop_thief.agents.geometry import BIG, bfs, chebyshev, neighbours
from cop_thief.agents.thief_policy import HeuristicThief
from cop_thief.agents.tuning import Tuning
from cop_thief.game.actions import ActionType


def _obs(self_cell, *, opponent=None, grid=(5, 5), barriers=(),
         barriers_remaining=5, vision=2, sub_game=1):
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


# ----- thief ---------------------------------------------------------------
def test_thief_avoids_immediate_capture_when_a_safe_move_exists():
    thief = HeuristicThief()
    chosen = tuple(thief.choose(_obs((2, 2), opponent=(2, 3)), random.Random(0)).to.to_list())
    assert chebyshev(chosen, (2, 3)) >= 2  # never lands where the cop can step onto it


def test_thief_prefers_a_high_mobility_cell_over_a_dead_end():
    # (0,0) is a dead-end (only exit back to (0,1)); the open cells have many exits.
    thief = HeuristicThief()
    obs = _obs((0, 1), barriers=[(1, 0), (1, 1)])
    chosen = tuple(thief.choose(obs, random.Random(0)).to.to_list())
    assert chosen != (0, 0)


def test_thief_does_not_step_toward_a_visible_cop():
    thief = HeuristicThief()
    obs = _obs((2, 2), opponent=(2, 4))  # cop two cells east, within vision
    chosen = tuple(thief.choose(obs, random.Random(1)).to.to_list())
    assert chebyshev(chosen, (2, 4)) >= chebyshev((2, 2), (2, 4))


def test_thief_uses_last_seen_memory_not_the_hidden_cop():
    thief = HeuristicThief()
    thief.choose(_obs((2, 2), opponent=(2, 3)), random.Random(2))  # see + remember cop at (2,3)
    blind = _obs((2, 1))  # cop now out of sight: obs carries no opponent cell
    assert blind["opponent"] is None
    chosen = tuple(thief.choose(blind, random.Random(2)).to.to_list())
    assert chebyshev(chosen, (2, 3)) >= chebyshev((2, 1), (2, 3))  # flees the remembered cell


def test_thief_memory_confidence_decays_over_time():
    thief = HeuristicThief(tuning=Tuning(thief_memory_decay=4))
    thief.choose(_obs((2, 2), opponent=(2, 3)), random.Random(3))  # age 0
    _, fresh = thief._belief()
    for _ in range(3):  # three unseen turns
        thief.choose(_obs((2, 1)), random.Random(3))
    _, stale = thief._belief()
    assert fresh == 1.0 and 0.0 <= stale < fresh


def test_thief_lookahead_keeps_it_safer_after_the_cops_reply():
    # One cell scores best on raw distance/mobility, another stays safest once the cop
    # responds. The lookahead-aware thief must not end up closer than the greedy one.
    scenario = _obs((1, 2), opponent=(3, 2))
    greedy = HeuristicThief(tuning=Tuning(thief_lookahead_weight=0.0))
    careful = HeuristicThief(tuning=Tuning(thief_lookahead_weight=10.0))
    g = tuple(greedy.choose(scenario, random.Random(0)).to.to_list())
    c = tuple(careful.choose(scenario, random.Random(0)).to.to_list())

    reach = [bfs(m, 5, 5, set(), True) for m in neighbours((3, 2), 5, 5, set(), True)]

    def safety(cell):  # how close the cop can get after its single best reply
        return min(d.get(cell, BIG) for d in reach)

    assert safety(c) >= safety(g)


def test_thief_forgets_the_cop_at_a_new_subgame():
    thief = HeuristicThief()
    thief.choose(_obs((2, 2), opponent=(2, 3), sub_game=1), random.Random(4))
    assert thief._last_cop is not None
    thief.choose(_obs((2, 2), sub_game=2), random.Random(4))
    assert thief._last_cop is None


# ----- cop -----------------------------------------------------------------
def test_cop_captures_an_adjacent_thief():
    cop = HeuristicCop()
    action = cop.choose(_obs((2, 2), opponent=(2, 3)), random.Random(0))
    assert action.type is ActionType.MOVE and action.to.to_list() == [2, 3]


def test_cop_moves_toward_a_visible_thief():
    cop = HeuristicCop()
    action = cop.choose(_obs((0, 0), opponent=(0, 4)), random.Random(0))
    assert action.type is ActionType.MOVE
    assert chebyshev(tuple(action.to.to_list()), (0, 4)) < chebyshev((0, 0), (0, 4))


def test_cop_places_a_tactical_barrier_on_the_thiefs_escape_lane():
    cop = HeuristicCop(tuning=Tuning(cop_barrier_min_value=0.1, cop_barrier_max_probability=1.0))
    action = cop.choose(_obs((2, 2), opponent=(2, 4)), random.Random(0))
    assert action.type is ActionType.BARRIER
    assert chebyshev(tuple(action.to.to_list()), (2, 4)) == 1  # blocks a real escape cell


def test_cop_skips_a_barrier_with_no_tactical_value():
    cop = HeuristicCop(tuning=Tuning(cop_barrier_min_value=100.0, cop_barrier_max_probability=1.0))
    action = cop.choose(_obs((2, 2), opponent=(2, 4)), random.Random(0))
    assert action.type is ActionType.MOVE  # no candidate clears the value threshold


def test_cop_never_places_a_barrier_with_none_remaining():
    cop = HeuristicCop(tuning=Tuning(cop_barrier_min_value=0.1, cop_barrier_max_probability=1.0))
    action = cop.choose(_obs((2, 2), opponent=(2, 4), barriers_remaining=0), random.Random(0))
    assert action.type is ActionType.MOVE


def test_cop_does_not_use_a_hidden_thief_position():
    cop = HeuristicCop()
    blind = _obs((2, 2))  # thief out of sight
    assert blind["opponent"] is None
    assert cop.choose(blind, random.Random(0)).type is ActionType.MOVE


def test_neither_policy_reads_a_hidden_opponent():
    blind = _obs((0, 0))
    assert blind["opponent"] is None and blind["opponent_visible"] is False
    assert HeuristicCop().choose(blind, random.Random(0)).type is ActionType.MOVE
    assert HeuristicThief().choose(blind, random.Random(0)).type is ActionType.MOVE
