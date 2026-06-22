"""Shared constructors for the test suite (kept tiny and dependency-free)."""

from __future__ import annotations

from cop_thief.game.actions import Action, ActionType, Role, TurnPayload
from cop_thief.game.board import Board, Position
from cop_thief.game.engine import GameEngine
from cop_thief.game.state import GameState


def build_engine(
    cop: tuple[int, int],
    thief: tuple[int, int],
    *,
    rows: int = 5,
    cols: int = 5,
    max_moves: int = 25,
    max_barriers: int = 5,
    eight: bool = True,
    to_move: Role = Role.THIEF,
    vision: int = 2,
    barriers: list[tuple[int, int]] | None = None,
) -> GameEngine:
    """Construct a :class:`GameEngine` over a freshly built state."""
    board = Board(rows, cols, eight, {Position(*b) for b in (barriers or [])})
    state = GameState(
        sub_game=1,
        board=board,
        cop=Position(*cop),
        thief=Position(*thief),
        max_moves=max_moves,
        max_barriers=max_barriers,
        to_move=to_move,
    )
    return GameEngine(state, vision_radius=vision)


def move(role: Role, to: tuple[int, int], *, move_number: int = 1) -> TurnPayload:
    """A MOVE turn payload for ``role`` to cell ``to``."""
    return TurnPayload(1, move_number, role, "", Action(ActionType.MOVE, Position(*to)))


def barrier(role: Role, to: tuple[int, int], *, move_number: int = 1) -> TurnPayload:
    """A BARRIER turn payload for ``role`` on cell ``to``."""
    return TurnPayload(1, move_number, role, "", Action(ActionType.BARRIER, Position(*to)))
