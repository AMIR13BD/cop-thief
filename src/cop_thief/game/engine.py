"""The referee: validates one turn, applies it, and adjudicates the sub-game.

This module is the single owner of the rules (assignment §4). Everything binding
happens here on the ``action``; the ``message`` is never consulted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .actions import Action, ActionType, Role, TurnPayload
from .board import chebyshev_distance
from .state import GameState, SubGameResult, TurnRecord


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of checking an action against the rules."""

    legal: bool
    reason: str


def _utc_now() -> str:
    """ISO-8601 UTC timestamp for the log record."""
    return datetime.now(UTC).isoformat()


class GameEngine:
    """Stateful referee bound to one :class:`GameState`."""

    def __init__(self, state: GameState, vision_radius: int = 2) -> None:
        self.state = state
        self.vision_radius = vision_radius

    # ----- validation ------------------------------------------------------
    def validate(self, role: Role, action: Action) -> ValidationResult:
        """Check ``action`` for ``role`` without mutating state."""
        if role is not self.state.to_move:
            return ValidationResult(False, "out_of_turn")
        if action.type is ActionType.BARRIER:
            return self._validate_barrier(role, action)
        return self._validate_move(role, action)

    def _validate_barrier(self, role: Role, action: Action) -> ValidationResult:
        # DELIBERATE DEVIATION from assignment §4.3 (which places the barrier on the
        # cop's OWN cell): this project places it on an ADJACENT empty cell. Documented
        # as a team design choice in the README. Target must be one of the 8 neighbours,
        # on-grid, not the thief's cell, and not already a barrier (own cell is excluded
        # automatically since it is at Chebyshev distance 0).
        board, pos, target = self.state.board, self.state.position_of(role), action.to
        if role is not Role.COP:
            return ValidationResult(False, "thief_cannot_place_barrier")
        if self.state.barriers_remaining <= 0:
            return ValidationResult(False, "no_barriers_left")
        if not board.in_bounds(target):
            return ValidationResult(False, "barrier_off_board")
        if chebyshev_distance(pos, target) != 1:
            return ValidationResult(False, "barrier_not_adjacent")
        if target == self.state.position_of(role.opponent):
            return ValidationResult(False, "barrier_on_thief")
        if board.is_barrier(target):
            return ValidationResult(False, "cell_already_barrier")
        return ValidationResult(True, "ok")

    def _validate_move(self, role: Role, action: Action) -> ValidationResult:
        board, pos, dest = self.state.board, self.state.position_of(role), action.to
        if not board.in_bounds(dest):
            return ValidationResult(False, "off_board")
        dist = chebyshev_distance(pos, dest)
        if dist == 0:
            return ValidationResult(False, "must_move")
        if dist > 1:
            return ValidationResult(False, "not_adjacent")
        manhattan = abs(pos.row - dest.row) + abs(pos.col - dest.col)
        if not board.eight_directional and manhattan != 1:
            return ValidationResult(False, "diagonal_not_allowed")
        if board.is_barrier(dest):
            return ValidationResult(False, "into_barrier")
        return ValidationResult(True, "ok")

    # ----- application -----------------------------------------------------
    def step(self, payload: TurnPayload) -> TurnRecord:
        """Validate and apply one turn, advancing or terminating the sub-game."""
        role, action = payload.role, payload.action
        verdict = self.validate(role, action)
        if not verdict.legal:
            self.state.result = SubGameResult.win_for(role.opponent)
            self.state.reason = f"illegal:{verdict.reason}"
        else:
            self._apply(role, action)
        return self._record(payload, verdict)

    def _apply(self, role: Role, action: Action) -> None:
        if action.type is ActionType.BARRIER:
            self.state.board.add_barrier(action.to)
            self.state.barriers_used += 1
        else:
            self.state.set_position(role, action.to)
        self._adjudicate(role)

    def _adjudicate(self, role: Role) -> None:
        if self.state.cop == self.state.thief:
            self.state.result = SubGameResult.COP_WIN
            self.state.reason = "capture"
        elif role is Role.THIEF:
            self.state.move_number += 1
            self.state.to_move = Role.COP  # cop gets its reply (last chance)
        elif self.state.move_number >= self.state.max_moves:
            self.state.result = SubGameResult.THIEF_WIN
            self.state.reason = "survived"
        else:
            self.state.to_move = Role.THIEF

    def _record(self, payload: TurnPayload, verdict: ValidationResult) -> TurnRecord:
        return TurnRecord(
            timestamp=_utc_now(),
            sub_game=payload.sub_game,
            move_number=payload.move_number,
            role=payload.role,
            message=payload.message,
            action=payload.action.to_dict(),
            legal=verdict.legal,
            validation=verdict.reason,
            cop=self.state.cop.to_list(),
            thief=self.state.thief.to_list(),
            barriers=sorted(b.to_list() for b in self.state.board.barriers),
            result=self.state.result.value,
        )
