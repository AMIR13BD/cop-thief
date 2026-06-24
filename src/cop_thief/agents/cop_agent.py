"""Factory for the cop agent (chaser, barrier-placer)."""

from __future__ import annotations

import random

from ..game.actions import Role
from ..game.setup import GameParams
from .base_agent import Agent
from .messages import Messenger
from .strategies import HeuristicCop


def build_cop_agent(params: GameParams, llm=None, rng: random.Random | None = None) -> Agent:
    """Wire a cop agent: chase heuristic + (mostly honest) taunting messages."""
    return Agent(
        role=Role.COP,
        eight_directional=params.eight_directional,
        strategy=HeuristicCop(
            params.eight_directional,
            barrier_prob=params.cop_barrier_prob,
            barrier_min_gap=params.cop_barrier_min_gap,
        ),
        messenger=Messenger(Role.COP, bluff_prob=0.1),
        llm=llm,
        rng=rng,
    )
