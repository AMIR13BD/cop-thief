"""Factory for the thief agent (evader, frequent bluffer)."""

from __future__ import annotations

import random

from ..game.actions import Role
from ..game.setup import GameParams
from .base_agent import Agent
from .messages import Messenger
from .strategies import HeuristicThief


def build_thief_agent(params: GameParams, llm=None, rng: random.Random | None = None) -> Agent:
    """Wire a thief agent: evade heuristic + often-deceptive messages."""
    return Agent(
        role=Role.THIEF,
        eight_directional=params.eight_directional,
        strategy=HeuristicThief(params.eight_directional),
        messenger=Messenger(Role.THIEF, bluff_prob=0.35),
        llm=llm,
        rng=rng,
    )
