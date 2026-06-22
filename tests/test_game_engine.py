"""End-to-end engine behaviour: capture, turn order, survival, move counting."""

from _helpers import barrier, build_engine, move
from cop_thief.game.actions import Role
from cop_thief.game.state import SubGameResult


def test_cop_captures_by_moving_onto_thief():
    eng = build_engine(cop=(2, 1), thief=(2, 2), to_move=Role.COP)
    rec = eng.step(move(Role.COP, (2, 2)))
    assert rec.legal
    assert eng.state.result is SubGameResult.COP_WIN
    assert eng.state.reason == "capture"


def test_thief_moving_onto_cop_is_captured():
    eng = build_engine(cop=(2, 2), thief=(2, 1), to_move=Role.THIEF)
    eng.step(move(Role.THIEF, (2, 2)))  # thief walks onto the cop
    assert eng.state.result is SubGameResult.COP_WIN


def test_turn_alternates_thief_then_cop():
    eng = build_engine(cop=(0, 0), thief=(4, 4))
    assert eng.state.to_move is Role.THIEF
    eng.step(move(Role.THIEF, (4, 3)))
    assert eng.state.to_move is Role.COP
    eng.step(move(Role.COP, (1, 1)))
    assert eng.state.to_move is Role.THIEF


def test_thief_move_increments_counter_cop_move_does_not():
    eng = build_engine(cop=(0, 0), thief=(4, 4))
    eng.step(move(Role.THIEF, (4, 3)))
    assert eng.state.move_number == 1
    eng.step(move(Role.COP, (0, 1)))
    assert eng.state.move_number == 1


def test_thief_survives_to_win():
    # One-move sub-game: thief moves, cop replies without capturing -> thief wins.
    eng = build_engine(cop=(0, 0), thief=(4, 4), max_moves=1)
    eng.step(move(Role.THIEF, (4, 3)))
    assert eng.state.result is SubGameResult.IN_PROGRESS  # cop still gets its reply
    eng.step(move(Role.COP, (1, 1)))
    assert eng.state.result is SubGameResult.THIEF_WIN
    assert eng.state.reason == "survived"


def test_cop_last_reply_can_still_capture():
    eng = build_engine(cop=(4, 2), thief=(3, 3), max_moves=1)
    eng.step(move(Role.THIEF, (4, 3)))  # thief's final move, lands next to cop
    eng.step(move(Role.COP, (4, 3)))    # cop's last chance: capture
    assert eng.state.result is SubGameResult.COP_WIN


def test_record_snapshots_positions_and_barriers():
    eng = build_engine(cop=(1, 1), thief=(4, 4), to_move=Role.COP)
    rec = eng.step(barrier(Role.COP, (1, 1)))
    assert rec.cop == [1, 1]
    assert rec.thief == [4, 4]
    assert [1, 1] in rec.barriers
