"""Prompt construction and the structured-output schema for LLM-driven agents.

The LLM lives in the client/orchestrator, never inside the MCP server
(assignment §5.2). These builders turn a partial observation plus the opponent's
recent natural-language messages into a prompt, and constrain the reply to the
shared turn shape so the referee can validate it.
"""

from __future__ import annotations

import json

# JSON-schema for structured outputs — guarantees a parseable {message, action}.
ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string", "description": "Free natural-language line; may bluff."},
        "action": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["move", "barrier"]},
                "to": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "[row, col] target cell.",
                },
            },
            "required": ["type", "to"],
            "additionalProperties": False,
        },
    },
    "required": ["message", "action"],
    "additionalProperties": False,
}

_COMMON_RULES = (
    "The board is a grid addressed as [row, col] with origin [0,0] at the top-left. "
    "A move goes to one of the 8 adjacent cells (diagonals allowed), must stay on the "
    "board, and must not enter a barrier cell (entering one loses the sub-game). "
    "You only see the opponent and barriers within your vision radius; outside it you "
    "must reason from the opponent's messages, which may be bluffs. The outcome is "
    "decided by your structured action, not by your message."
)

_ROLE_GOAL = {
    "cop": (
        "You are the COP. You win by moving onto the thief's cell. As an alternative to "
        "moving you may drop a barrier on your OWN current cell (action type 'barrier', "
        "'to' equal to your own position) up to your remaining budget; it becomes "
        "impassable for both of you."
    ),
    "thief": (
        "You are the THIEF. You win by surviving every move without the cop landing on "
        "your cell. You cannot place barriers — always use action type 'move'. Use your "
        "message to mislead the cop about where you are heading."
    ),
}


def build_system_prompt(role: str) -> str:
    """System prompt fixing the rules and the acting agent's objective."""
    return f"{_ROLE_GOAL[role]} {_COMMON_RULES} Reply only with the JSON object."


def build_user_prompt(observation: dict, inbox: list[str]) -> str:
    """User prompt carrying the legal observation and the opponent's recent messages."""
    talk = "\n".join(f"- {m}" for m in inbox) or "- (no messages yet)"
    return (
        f"Your observation:\n{json.dumps(observation, indent=2)}\n\n"
        f"Recent messages from your opponent (may be bluffs):\n{talk}\n\n"
        "Choose one legal action and a short message."
    )
