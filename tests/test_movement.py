"""Movement legality: adjacency, bounds, diagonals, the must-move rule."""

from _helpers import build_engine, move
from cop_thief.game.actions import Role


def test_orthogonal_step_is_legal():
    eng = build_engine(cop=(0, 0), thief=(2, 2))
    assert eng.validate(Role.THIEF, move(Role.THIEF, (2, 3)).action).legal


def test_diagonal_step_is_legal_in_eight_directional():
    eng = build_engine(cop=(0, 0), thief=(2, 2))
    assert eng.validate(Role.THIEF, move(Role.THIEF, (3, 3)).action).legal


def test_diagonal_rejected_in_four_directional():
    eng = build_engine(cop=(0, 0), thief=(2, 2), eight=False)
    verdict = eng.validate(Role.THIEF, move(Role.THIEF, (3, 3)).action)
    assert not verdict.legal
    assert verdict.reason == "diagonal_not_allowed"


def test_two_cell_jump_is_not_adjacent():
    eng = build_engine(cop=(0, 0), thief=(2, 2))
    assert eng.validate(Role.THIEF, move(Role.THIEF, (2, 4)).action).reason == "not_adjacent"


def test_staying_put_violates_must_move():
    eng = build_engine(cop=(0, 0), thief=(2, 2))
    assert eng.validate(Role.THIEF, move(Role.THIEF, (2, 2)).action).reason == "must_move"


def test_off_board_is_illegal():
    eng = build_engine(cop=(4, 4), thief=(0, 0))
    assert eng.validate(Role.THIEF, move(Role.THIEF, (-1, 0)).action).reason == "off_board"


def test_out_of_turn_is_rejected():
    eng = build_engine(cop=(0, 0), thief=(2, 2))  # thief to move first
    assert eng.validate(Role.COP, move(Role.COP, (1, 0)).action).reason == "out_of_turn"


def test_illegal_move_loses_subgame():
    eng = build_engine(cop=(0, 0), thief=(2, 2))
    record = eng.step(move(Role.THIEF, (2, 4)))  # not adjacent -> thief loses
    assert not record.legal
    assert eng.state.result.value == "cop_win"
