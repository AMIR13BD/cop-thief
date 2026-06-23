"""Barrier rules (PRD deviation from §4.3): cop-only, on an ADJACENT empty cell,
budget cap, impassability for both, illegal entry, and the no-valid-cell case."""

from _helpers import barrier, build_engine, move
from cop_thief.agents.strategies import legal_barrier_targets
from cop_thief.game.actions import Role
from cop_thief.game.board import Position
from cop_thief.game.observation import build_observation


def test_cop_places_barrier_on_adjacent_cell():
    eng = build_engine(cop=(1, 1), thief=(3, 3), to_move=Role.COP)
    rec = eng.step(barrier(Role.COP, (1, 2)))  # adjacent empty cell
    assert rec.legal
    assert eng.state.barriers_used == 1
    assert eng.state.board.is_barrier(Position(1, 2))
    assert eng.state.cop == Position(1, 1)  # cop does not move on placement


def test_thief_cannot_place_barrier():
    eng = build_engine(cop=(1, 1), thief=(3, 3), to_move=Role.THIEF)
    verdict = eng.validate(Role.THIEF, barrier(Role.THIEF, (3, 2)).action)
    assert verdict.reason == "thief_cannot_place_barrier"


def test_barrier_on_own_cell_is_not_adjacent():
    eng = build_engine(cop=(1, 1), thief=(3, 3), to_move=Role.COP)
    verdict = eng.validate(Role.COP, barrier(Role.COP, (1, 1)).action)
    assert verdict.reason == "barrier_not_adjacent"


def test_barrier_two_cells_away_is_not_adjacent():
    eng = build_engine(cop=(1, 1), thief=(3, 3), to_move=Role.COP)
    verdict = eng.validate(Role.COP, barrier(Role.COP, (1, 3)).action)
    assert verdict.reason == "barrier_not_adjacent"


def test_barrier_cannot_land_on_thief():
    eng = build_engine(cop=(1, 1), thief=(1, 2), to_move=Role.COP)
    verdict = eng.validate(Role.COP, barrier(Role.COP, (1, 2)).action)
    assert verdict.reason == "barrier_on_thief"


def test_barrier_off_board_is_rejected():
    eng = build_engine(cop=(0, 0), thief=(3, 3), to_move=Role.COP)
    verdict = eng.validate(Role.COP, barrier(Role.COP, (-1, 0)).action)
    assert verdict.reason == "barrier_off_board"


def test_barrier_budget_is_capped():
    eng = build_engine(cop=(1, 1), thief=(4, 4), to_move=Role.COP, max_barriers=0)
    verdict = eng.validate(Role.COP, barrier(Role.COP, (1, 2)).action)
    assert verdict.reason == "no_barriers_left"


def test_cannot_place_on_existing_barrier():
    eng = build_engine(cop=(1, 1), thief=(4, 4), to_move=Role.COP, barriers=[(1, 2)])
    verdict = eng.validate(Role.COP, barrier(Role.COP, (1, 2)).action)
    assert verdict.reason == "cell_already_barrier"


def test_stepping_into_barrier_loses():
    eng = build_engine(cop=(0, 0), thief=(2, 2), barriers=[(2, 3)])
    rec = eng.step(move(Role.THIEF, (2, 3)))  # thief walks into a barrier
    assert not rec.legal
    assert rec.validation == "into_barrier"
    assert eng.state.result.value == "cop_win"


def test_barrier_blocks_both_agents():
    eng = build_engine(cop=(1, 1), thief=(4, 4), to_move=Role.COP)
    eng.step(barrier(Role.COP, (1, 2)))  # drop barrier on neighbour, cop stays on (1,1)
    eng.state.to_move = Role.COP  # force cop to act again for the test
    # the cop cannot step into its own barrier either
    assert eng.validate(Role.COP, move(Role.COP, (1, 2)).action).reason == "into_barrier"
    # but moving to another free neighbour is fine
    assert eng.validate(Role.COP, move(Role.COP, (2, 2)).action).legal


def test_no_valid_adjacent_cell_makes_barrier_unavailable():
    # Cop boxed into the corner: every in-bounds neighbour is a barrier or the thief.
    eng = build_engine(cop=(0, 0), thief=(1, 0), to_move=Role.COP, barriers=[(0, 1), (1, 1)])
    obs = build_observation(eng.state, Role.COP, vision_radius=2)
    assert legal_barrier_targets(obs) == []  # nowhere legal to place
    for cell in [(0, 1), (1, 0), (1, 1)]:
        assert not eng.validate(Role.COP, barrier(Role.COP, cell).action).legal
