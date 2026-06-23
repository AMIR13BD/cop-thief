"""Thief MCP server entrypoint. Run: ``python -m cop_thief.mcp_servers.thief_server``."""

from __future__ import annotations

from ..config import Config
from ..game.actions import Role
from .server_app import run_server


def main() -> None:
    """Bind the thief server from config (``THIEF_SERVER_HOST``/``THIEF_SERVER_PORT`` override)."""
    host, port = Config.load().mcp_bind("thief")
    run_server(Role.THIEF, host, port)


if __name__ == "__main__":
    main()
