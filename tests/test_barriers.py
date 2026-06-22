"""Barrier rules: cop-only, on-own-cell, budget cap, impassability, illegal entry."""

from _helpers import barrier, build_engine, move
from cop_thief.game.actions import Role


def test_cop_places_barrier_on_own_cell():
    from cop_thief.game.board import Position

    eng = build_engine(cop=(1, 1), thief=(3, 3), to_move=Role.COP)
    rec = eng.step(barrier(Role.COP, (1, 1)))
    assert rec.legal
    assert eng.state.barriers_used == 1
    assert eng.state.board.is_barrier(Position(1, 1))


def test_thief_cannot_place_barrier():
    eng = build_engine(cop=(1, 1), thief=(3, 3), to_move=Role.THIEF)
    verdict = eng.validate(Role.THIEF, barrier(Role.THIEF, (3, 3)).action)
    assert verdict.reason == "thief_cannot_place_barrier"


def test_barrier_must_be_on_own_cell():
    eng = build_engine(cop=(1, 1), thief=(3, 3), to_move=Role.COP)
    verdict = eng.validate(Role.COP, barrier(Role.COP, (1, 2)).action)
    assert verdict.reason == "barrier_not_on_own_cell"


def test_barrier_budget_is_capped():
    eng = build_engine(cop=(1, 1), thief=(4, 4), to_move=Role.COP, max_barriers=0)
    verdict = eng.validate(Role.COP, barrier(Role.COP, (1, 1)).action)
    assert verdict.reason == "no_barriers_left"


def test_stepping_into_barrier_loses():
    eng = build_engine(cop=(0, 0), thief=(2, 2), barriers=[(2, 3)])
    rec = eng.step(move(Role.THIEF, (2, 3)))  # thief walks into a barrier
    assert not rec.legal
    assert rec.validation == "into_barrier"
    assert eng.state.result.value == "cop_win"


def test_barrier_blocks_then_cop_must_move_off():
    eng = build_engine(cop=(1, 1), thief=(4, 4), to_move=Role.COP)
    eng.step(barrier(Role.COP, (1, 1)))  # drop barrier, cop stays on (1,1)
    eng.state.to_move = Role.COP  # force cop to act again for the test
    # re-dropping on the same (now-barrier) cell is illegal
    assert eng.validate(Role.COP, barrier(Role.COP, (1, 1)).action).reason == "cell_already_barrier"
    # but moving off the barrier cell is fine
    assert eng.validate(Role.COP, move(Role.COP, (2, 2)).action).legal
