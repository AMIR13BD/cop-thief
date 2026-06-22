"""Cop-vs-Thief — dual AI agent chase orchestrated over two MCP servers.

Package layout:
    game/          authoritative rules: board, actions, state, observation, scoring, engine
    agents/        cop/thief decision agents and their natural-language messages
    mcp_servers/   FastMCP servers exposing per-agent tools (cop, thief)
    orchestrator/  runner, referee glue, LLM client, report builder, Gmail sender
    security/      token issuing and Authorization-header verification
"""

__version__ = "0.1.0"
