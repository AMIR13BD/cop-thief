"""Mutable per-sub-game state and the terminal-result enum.

The state is the authoritative record the referee mutates; everything else
(observations, reports) is derived from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .actions import Role
from .board import Board, Position


class SubGameResult(StrEnum):
    """How a sub-game ended."""

    COP_WIN = "cop_win"      # cop landed on the thief (capture)
    THIEF_WIN = "thief_win"  # thief survived all its moves
    IN_PROGRESS = "in_progress"

    @classmethod
    def win_for(cls, role: Role) -> SubGameResult:
        """The terminal result meaning ``role`` won."""
        return cls.COP_WIN if role is Role.COP else cls.THIEF_WIN


@dataclass
class GameState:
    """Authoritative state of a single sub-game.

    ``move_number`` counts completed THIEF moves (SHARED_MATCH_RULES.md §2.8):
    the thief wins once it finishes its ``max_moves``-th move uncaught.
    """

    sub_game: int
    board: Board
    cop: Position
    thief: Position
    max_moves: int
    max_barriers: int
    barriers_used: int = 0
    move_number: int = 0
    to_move: Role = Role.THIEF  # thief always moves first
    result: SubGameResult = SubGameResult.IN_PROGRESS
    reason: str = ""

    def position_of(self, role: Role) -> Position:
        """Current cell of ``role``."""
        return self.cop if role is Role.COP else self.thief

    def set_position(self, role: Role, pos: Position) -> None:
        """Move ``role`` to ``pos`` (used by the referee after validation)."""
        if role is Role.COP:
            self.cop = pos
        else:
            self.thief = pos

    @property
    def is_terminal(self) -> bool:
        """True once a winner has been decided."""
        return self.result is not SubGameResult.IN_PROGRESS

    @property
    def barriers_remaining(self) -> int:
        """How many barriers the cop may still place this sub-game."""
        return self.max_barriers - self.barriers_used


@dataclass
class TurnRecord:
    """One referee-validated turn, kept for the timestamped log and the report."""

    timestamp: str
    sub_game: int
    move_number: int
    role: Role
    message: str
    action: dict
    legal: bool
    validation: str
    cop: list[int]
    thief: list[int]
    barriers: list[list[int]] = field(default_factory=list)
    result: str = SubGameResult.IN_PROGRESS.value
