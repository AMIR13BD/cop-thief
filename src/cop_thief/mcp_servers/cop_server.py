"""Cop MCP server entrypoint. Run: ``python -m cop_thief.mcp_servers.cop_server``."""

from __future__ import annotations

import os

from ..game.actions import Role
from .server_app import run_server


def main() -> None:
    """Bind the cop server from ``COP_SERVER_HOST`` / ``COP_SERVER_PORT``."""
    host = os.getenv("COP_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("COP_SERVER_PORT", "8101"))
    run_server(Role.COP, host, port)


if __name__ == "__main__":
    main()
