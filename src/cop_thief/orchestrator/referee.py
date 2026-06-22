"""The referee: the single authoritative owner of one sub-game's state.

Both the in-process runner and the MCP servers talk to a referee rather than to
the engine directly, so there is exactly one source of truth (SHARED_MATCH_RULES.md
§2.1). It exposes only the two operations an agent needs: a legal observation and
a validated turn submission.
"""

from __future__ import annotations

from ..game.actions import Role, TurnPayload
from ..game.engine import GameEngine
from ..game.observation import build_observation
from ..game.state import GameState, SubGameResult, TurnRecord


class SubGameReferee:
    """Owns one :class:`GameState` and adjudicates every turn against it."""

    def __init__(self, state: GameState, vision_radius: int) -> None:
        self.engine = GameEngine(state, vision_radius)
        self.vision_radius = vision_radius

    @property
    def state(self) -> GameState:
        """The authoritative sub-game state."""
        return self.engine.state

    def whose_turn(self) -> Role:
        """Role expected to act next."""
        return self.state.to_move

    def is_over(self) -> bool:
        """True once the sub-game has a winner."""
        return self.state.is_terminal

    def result(self) -> SubGameResult:
        """Terminal result (or ``IN_PROGRESS``)."""
        return self.state.result

    def observe(self, role: Role) -> dict:
        """The legal partial-observation view for ``role``."""
        return build_observation(self.state, role, self.vision_radius)

    def submit(self, payload: TurnPayload) -> TurnRecord:
        """Validate and apply ``payload`` (binding on its ``action``)."""
        return self.engine.step(payload)
