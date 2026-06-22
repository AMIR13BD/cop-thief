"""Natural-language message composition for the talk channel.

The message is the *only* thing an agent reveals beyond its action; it may be
honest or a bluff (SHARED_MATCH_RULES.md §1). The referee never reads it — it is
pure inter-agent communication, which is exactly what the assignment grades.
"""

from __future__ import annotations

import random

from ..game.actions import Action, ActionType, Role

_COMPASS = {
    (-1, 0): "north", (1, 0): "south", (0, -1): "west", (0, 1): "east",
    (-1, -1): "north-west", (-1, 1): "north-east", (1, -1): "south-west", (1, 1): "south-east",
}


def _heading(frm: list[int], to: list[int]) -> str:
    """Compass word for the step ``frm -> to`` (``"still"`` if unchanged)."""
    key = (_sign(to[0] - frm[0]), _sign(to[1] - frm[1]))
    return _COMPASS.get(key, "still")


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


class Messenger:
    """Compose a short message for a chosen action, optionally bluffing."""

    def __init__(self, role: Role, bluff_prob: float = 0.0) -> None:
        self.role = role
        self.bluff_prob = bluff_prob

    def compose(self, obs: dict, action: Action, rng: random.Random) -> str:
        """Return a natural-language line consistent with ``role`` (may bluff)."""
        if action.type is ActionType.BARRIER:
            return "Sealing this corridor — you won't get through here."
        true_heading = _heading(obs["self"], action.to.to_list())
        if rng.random() < self.bluff_prob:
            decoy = rng.choice([d for d in _COMPASS.values() if d != true_heading])
            return self._line(decoy, bluff=True)
        return self._line(true_heading, bluff=False)

    def _line(self, heading: str, *, bluff: bool) -> str:
        if self.role is Role.THIEF:
            if bluff:
                return f"Breaking {heading} — try to keep up."
            return f"Slipping {heading}, staying clear of you."
        return f"Closing in from the {heading}; nowhere left to run."
