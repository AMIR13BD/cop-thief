"""Configuration loader — the single entry point for all tunable values.

Reads ``config/config.yaml`` (assignment §10: no hard-coded parameters). Secrets
are never stored here; they are read from environment variables at point of use.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from .game.scoring import ScoringTable
from .game.setup import GameParams

DEFAULT_CONFIG_PATH = "config/config.yaml"


class Config:
    """Thin typed wrapper over the parsed YAML configuration tree."""

    def __init__(self, raw: dict) -> None:
        self.raw = raw

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        """Load configuration from ``path`` (or ``$COP_THIEF_CONFIG``/default)."""
        resolved = Path(path or os.getenv("COP_THIEF_CONFIG", DEFAULT_CONFIG_PATH))
        with open(resolved, encoding="utf-8") as handle:
            return cls(yaml.safe_load(handle))

    def game_params(self) -> GameParams:
        """Resolve the immutable :class:`GameParams` used to build sub-games."""
        game, obs = self.raw["game"], self.raw["observation"]
        rows, cols = game["grid_size"]
        return GameParams(
            grid_rows=int(rows),
            grid_cols=int(cols),
            max_moves=int(game["max_moves"]),
            num_games=int(game["num_games"]),
            max_barriers=int(game["max_barriers"]),
            eight_directional=int(game["movement_directions"]) == 8,
            vision_radius=int(obs["vision_radius"]),
            start_outside_vision=bool(obs["start_outside_vision"]),
        )

    def scoring_table(self) -> ScoringTable:
        """Build the :class:`ScoringTable` from the ``scoring`` block."""
        return ScoringTable.from_config(self.raw["scoring"])

    @property
    def seed(self) -> int:
        """Shared RNG seed for reproducible start positions."""
        return int(self.raw["match"]["seed"])

    @property
    def vision_radius(self) -> int:
        """King-move observation radius."""
        return int(self.raw["observation"]["vision_radius"])

    @property
    def llm(self) -> dict:
        """LLM settings; ``$COP_THIEF_LLM_MODEL`` overrides the model id."""
        block = dict(self.raw["llm"])
        block["model"] = os.getenv("COP_THIEF_LLM_MODEL", block["model"])
        return block

    @property
    def team(self) -> dict:
        """Team identity and MCP endpoints."""
        return self.raw["team"]

    @property
    def report(self) -> dict:
        """Report recipient and output directory."""
        return self.raw["report"]

    @property
    def logging(self) -> dict:
        """Logging level and directory."""
        return self.raw["logging"]

    @property
    def turn(self) -> dict:
        """Per-turn timeout / re-prompt policy."""
        return self.raw["turn"]

    @property
    def match(self) -> dict:
        """Match-level policy (seed, rate limit, retry budget)."""
        return self.raw["match"]

    def mcp_bind(self, role: str) -> tuple[str, int]:
        """``(host, port)`` to bind ``role``'s MCP server; env overrides config."""
        block = self.raw["mcp"][role]
        host = os.getenv(f"{role.upper()}_SERVER_HOST", block["host"])
        port = int(os.getenv(f"{role.upper()}_SERVER_PORT", block["port"]))
        return host, port

    def mcp_url(self, role: str) -> str:
        """URL the orchestrator (MCP client) connects to for ``role``'s server.

        ``{COP,THIEF}_MCP_URL`` fully overrides it (e.g. a cloud HTTPS tunnel);
        otherwise it is built from the local bind host/port and the mount path.
        """
        override = os.getenv(f"{role.upper()}_MCP_URL")
        if override:
            return override
        host, port = self.mcp_bind(role)
        path = self.raw["mcp"].get("path", "/mcp")
        return f"http://{host}:{port}{path}"
