"""Cop MCP server entrypoint. Run: ``python -m cop_thief.mcp_servers.cop_server``."""

from __future__ import annotations

from ..config import Config
from ..game.actions import Role
from .server_app import run_server


def main() -> None:
    """Bind the cop server from config (``COP_SERVER_HOST``/``COP_SERVER_PORT`` override)."""
    host, port = Config.load().mcp_bind("cop")
    run_server(Role.COP, host, port)


if __name__ == "__main__":
    main()
