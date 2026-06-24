"""End-to-end engine behaviour: capture, turn order, survival, move counting."""

from _helpers import barrier, build_engine, move
from cop_thief.game.actions import Role, round_number
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


def test_subgame_ends_exactly_at_max_moves_with_thief_win():
    # No capture ever happens; the sub-game must stop the moment the thief completes
    # its max_moves-th move, and move_number must never run past max_moves.
    eng = build_engine(cop=(0, 0), thief=(4, 4), max_moves=3)
    thief_to = {(4, 4): (4, 3), (4, 3): (4, 4)}
    cop_to = {(0, 0): (0, 1), (0, 1): (0, 0)}
    while eng.state.result is SubGameResult.IN_PROGRESS:
        if eng.state.to_move is Role.THIEF:
            eng.step(move(Role.THIEF, thief_to[tuple(eng.state.thief.to_list())]))
        else:
            eng.step(move(Role.COP, cop_to[tuple(eng.state.cop.to_list())]))
        assert eng.state.move_number <= eng.state.max_moves  # never exceeds the cap
    assert eng.state.result is SubGameResult.THIEF_WIN
    assert eng.state.reason == "survived"
    assert eng.state.move_number == 3


def test_round_number_maps_actions_to_assignment_moves():
    # Plies 1..6 are thief/cop/thief/cop... -> assignment moves 1,1,2,2,3,3.
    assert [round_number(p) for p in range(1, 7)] == [1, 1, 2, 2, 3, 3]
    # The very last action of a full 25-move sub-game is still move 25, not 50.
    assert round_number(2 * 25) == 25


def test_record_snapshots_positions_and_barriers():
    eng = build_engine(cop=(1, 1), thief=(4, 4), to_move=Role.COP)
    rec = eng.step(barrier(Role.COP, (1, 2)))  # adjacent empty cell (PRD deviation)
    assert rec.cop == [1, 1]  # cop does not move when placing a barrier
    assert rec.thief == [4, 4]
    assert [1, 2] in rec.barriers
