"""Factory for the thief agent (evader, frequent bluffer)."""

from __future__ import annotations

import random

from ..game.actions import Role
from ..game.setup import GameParams
from .base_agent import Agent
from .messages import Messenger
from .thief_policy import HeuristicThief
from .tuning import Tuning


def build_thief_agent(params: GameParams, llm=None, rng: random.Random | None = None) -> Agent:
    """Wire a thief agent: intelligent evasion heuristic + often-deceptive messages."""
    return Agent(
        role=Role.THIEF,
        eight_directional=params.eight_directional,
        strategy=HeuristicThief(params.eight_directional, Tuning.from_mapping(params.strategy)),
        messenger=Messenger(Role.THIEF, bluff_prob=0.35),
        llm=llm,
        rng=rng,
    )
