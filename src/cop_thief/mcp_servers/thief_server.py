"""Thief MCP server entrypoint. Run: ``python -m cop_thief.mcp_servers.thief_server``."""

from __future__ import annotations

import os

from ..game.actions import Role
from .server_app import run_server


def main() -> None:
    """Bind the thief server from ``THIEF_SERVER_HOST`` / ``THIEF_SERVER_PORT``."""
    host = os.getenv("THIEF_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("THIEF_SERVER_PORT", "8102"))
    run_server(Role.THIEF, host, port)


if __name__ == "__main__":
    main()
