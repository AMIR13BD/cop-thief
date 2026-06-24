"""Factory for the cop agent (chaser, barrier-placer)."""

from __future__ import annotations

import random

from ..game.actions import Role
from ..game.setup import GameParams
from .base_agent import Agent
from .cop_policy import HeuristicCop
from .messages import Messenger
from .tuning import Tuning


def build_cop_agent(params: GameParams, llm=None, rng: random.Random | None = None) -> Agent:
    """Wire a cop agent: shortest-path chase + tactical barriers + taunting messages."""
    return Agent(
        role=Role.COP,
        eight_directional=params.eight_directional,
        strategy=HeuristicCop(params.eight_directional, Tuning.from_mapping(params.strategy)),
        messenger=Messenger(Role.COP, bluff_prob=0.1),
        llm=llm,
        rng=rng,
    )
