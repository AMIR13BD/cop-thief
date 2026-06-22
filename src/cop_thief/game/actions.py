"""Roles, action types, and the per-turn payload shape shared by both teams.

The turn payload matches SHARED_MATCH_RULES.md §2.2 verbatim::

    {"sub_game": 1, "move_number": 7, "role": "thief",
     "message": "free natural-language text",
     "action": {"type": "move|barrier", "to": [row, col]}}

The result is always decided by ``action`` — never by ``message`` (which may bluff).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .board import Position


class Role(StrEnum):
    """Which agent is acting. ``StrEnum`` keeps it JSON-friendly."""

    COP = "cop"
    THIEF = "thief"

    @property
    def opponent(self) -> Role:
        """The other role."""
        return Role.THIEF if self is Role.COP else Role.COP


class ActionType(StrEnum):
    """The two kinds of action. Only the cop may use ``BARRIER``."""

    MOVE = "move"
    BARRIER = "barrier"


@dataclass(frozen=True)
class Action:
    """A structured action: a move to ``to`` or a barrier dropped on ``to``."""

    type: ActionType
    to: Position

    def to_dict(self) -> dict:
        """Serialise to the ``action`` sub-object of the turn payload."""
        return {"type": self.type.value, "to": self.to.to_list()}

    @classmethod
    def from_dict(cls, data: dict) -> Action:
        """Parse an ``action`` sub-object back into an :class:`Action`."""
        return cls(ActionType(data["type"]), Position.from_list(data["to"]))


@dataclass
class TurnPayload:
    """One full turn: the bluffable message plus the binding structured action."""

    sub_game: int
    move_number: int
    role: Role
    message: str
    action: Action

    def to_dict(self) -> dict:
        """Serialise to the shared turn shape (for logs and MCP transport)."""
        return {
            "sub_game": self.sub_game,
            "move_number": self.move_number,
            "role": self.role.value,
            "message": self.message,
            "action": self.action.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TurnPayload:
        """Parse a turn payload received over MCP or read from a log."""
        return cls(
            sub_game=int(data["sub_game"]),
            move_number=int(data["move_number"]),
            role=Role(data["role"]),
            message=str(data.get("message", "")),
            action=Action.from_dict(data["action"]),
        )
