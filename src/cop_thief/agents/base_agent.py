"""The agent: turns a partial observation (+ inbox) into a message and action.

When an LLM client is attached the agent delegates reasoning to it, but always
*sanitises* the returned action against the rules it can verify locally — so a
malformed model reply degrades to a safe heuristic move instead of forfeiting
the sub-game. Without an LLM the agent runs its heuristic strategy directly.
"""

from __future__ import annotations

import random

from ..game.actions import Action, ActionType, Role
from .strategies import legal_barrier_targets, legal_targets


class Agent:
    """A role-bound decision maker (cop or thief)."""

    def __init__(self, role, eight_directional, strategy, messenger, llm=None, rng=None) -> None:
        self.role: Role = role
        self.eight = eight_directional
        self.strategy = strategy
        self.messenger = messenger
        self.llm = llm
        self.rng = rng or random.Random()

    def decide(self, observation: dict, inbox: list[str]) -> tuple[str, Action]:
        """Return ``(message, action)`` for the current turn."""
        if self.llm is not None:
            result = self._decide_with_llm(observation, inbox)
            if result is not None:
                return result
        action = self.strategy.choose(observation, self.rng)
        return self.messenger.compose(observation, action, self.rng), action

    def _decide_with_llm(self, observation: dict, inbox: list[str]):
        try:
            message, action = self.llm.decide(self.role, observation, inbox)
        except Exception:  # noqa: BLE001 — any LLM/transport failure -> heuristic fallback
            return None
        return message, self._sanitise(action, observation)

    def _sanitise(self, action: Action, observation: dict) -> Action:
        """Replace an unverifiable/illegal action with a safe heuristic move."""
        if action.type is ActionType.BARRIER:
            on_adjacent_cell = tuple(action.to.to_list()) in set(legal_barrier_targets(observation))
            if self.role is Role.COP and on_adjacent_cell and observation["barriers_remaining"] > 0:
                return action
        elif tuple(action.to.to_list()) in set(legal_targets(observation, self.eight)):
            return action
        return self.strategy.choose(observation, self.rng)
