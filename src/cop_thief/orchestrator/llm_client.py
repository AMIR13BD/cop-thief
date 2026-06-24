"""Cloud-API reasoning for the agents (LLM approach #1).

The orchestrator owns the LLM; it sends the partial observation + opponent
messages to the model and gets back a structured ``{message, action}`` via
structured outputs. Two providers are supported — Anthropic (Claude) and OpenAI —
behind one ``decide`` interface. Any failure raises, and the calling agent falls
back to its deterministic heuristic, so a missing key or network blip never
forfeits a game (§5.2: the LLM lives here, never inside the MCP server).
"""

from __future__ import annotations

import json
import os

from ..game.actions import Action, Role
from .prompts import ACTION_SCHEMA, build_system_prompt, build_user_prompt

# Models that reject sampling params (Opus 4.7/4.8, Fable, OpenAI o-series); temp sent off-list.
_NO_SAMPLING = ("opus-4-8", "opus-4-7", "opus-4-6", "fable", "mythos", "o1", "o3", "o4")


def _accepts_temperature(model: str) -> bool:
    return not any(tag in model for tag in _NO_SAMPLING)


def _openai_api_key() -> str | None:
    """OpenAI key — accept the standard name and the ``OPEN_API_KEY`` this repo uses."""
    return os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY")


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


class OpenAIClient:
    """Thin wrapper over ``openai.OpenAI`` chat completions with a strict JSON schema."""

    def __init__(self, model: str, max_tokens: int = 400, temperature: float | None = None) -> None:
        import openai  # lazy import: core package runs without the SDK installed

        self._client = openai.OpenAI(api_key=_openai_api_key())
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def decide(self, role: Role, observation: dict, inbox: list[str]) -> tuple[str, Action]:
        """Return ``(message, action)`` chosen by the model for this turn."""
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": build_system_prompt(role.value)},
                {"role": "user", "content": build_user_prompt(observation, inbox)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "turn", "schema": ACTION_SCHEMA, "strict": True},
            },
        }
        if self.temperature is not None and _accepts_temperature(self.model):
            kwargs["temperature"] = self.temperature
        response = self._client.chat.completions.create(**kwargs)
        payload = json.loads(response.choices[0].message.content)
        return payload["message"], Action.from_dict(payload["action"])


def build_llm(llm_config: dict):
    """Build the configured LLM client, or ``None`` (heuristic mode) when unavailable.

    ``provider`` selects the backend: ``anthropic`` (needs ``ANTHROPIC_API_KEY``) or
    ``openai`` (needs ``OPENAI_API_KEY`` / ``OPEN_API_KEY``). Any other value, or a
    missing key, returns ``None`` so the whole pipeline still runs offline.
    """
    provider = llm_config.get("provider")
    model = llm_config["model"]
    max_tokens = int(llm_config.get("max_tokens", 400))
    temperature = llm_config.get("temperature")
    if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        return LLMClient(model=model, max_tokens=max_tokens, temperature=temperature)
    if provider == "openai" and _openai_api_key():
        return OpenAIClient(model=model, max_tokens=max_tokens, temperature=temperature)
    return None
