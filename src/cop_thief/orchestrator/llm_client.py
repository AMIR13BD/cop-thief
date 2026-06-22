"""Anthropic-backed reasoning for the agents (LLM approach #1: cloud API).

The orchestrator owns the LLM; it sends the partial observation + opponent
messages to Claude and gets back a structured ``{message, action}`` via
structured outputs. Any failure raises, and the calling agent falls back to its
deterministic heuristic — so a missing key or network blip never forfeits a game.
"""

from __future__ import annotations

import json
import os

from ..game.actions import Action, Role
from .prompts import ACTION_SCHEMA, build_system_prompt, build_user_prompt

# Models that reject sampling params (Opus 4.7/4.8, Fable). Temperature is sent only off-list.
_NO_SAMPLING = ("opus-4-8", "opus-4-7", "opus-4-6", "fable", "mythos")


def _accepts_temperature(model: str) -> bool:
    return not any(tag in model for tag in _NO_SAMPLING)


class LLMClient:
    """Thin wrapper over ``anthropic.Anthropic`` for one-shot turn decisions."""

    def __init__(self, model: str, max_tokens: int = 400, temperature: float | None = None) -> None:
        import anthropic  # lazy import: core package runs without the SDK installed

        self._client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def decide(self, role: Role, observation: dict, inbox: list[str]) -> tuple[str, Action]:
        """Return ``(message, action)`` chosen by the model for this turn."""
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": build_system_prompt(role.value),
            "messages": [{"role": "user", "content": build_user_prompt(observation, inbox)}],
            "output_config": {"format": {"type": "json_schema", "schema": ACTION_SCHEMA}},
        }
        if self.temperature is not None and _accepts_temperature(self.model):
            kwargs["temperature"] = self.temperature
        response = self._client.messages.create(**kwargs)
        payload = json.loads(next(b.text for b in response.content if b.type == "text"))
        return payload["message"], Action.from_dict(payload["action"])


def build_llm(llm_config: dict) -> LLMClient | None:
    """Build an :class:`LLMClient` when configured for Anthropic and a key is present.

    Returns ``None`` (heuristic mode) when ``provider`` is not ``anthropic`` or no
    ``ANTHROPIC_API_KEY`` is set — keeping the whole pipeline runnable offline.
    """
    if llm_config.get("provider") != "anthropic" or not os.getenv("ANTHROPIC_API_KEY"):
        return None
    return LLMClient(
        model=llm_config["model"],
        max_tokens=int(llm_config.get("max_tokens", 400)),
        temperature=llm_config.get("temperature"),
    )
