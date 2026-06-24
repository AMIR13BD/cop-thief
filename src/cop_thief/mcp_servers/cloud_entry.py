"""Cloud Run entrypoint — one image serves either agent server.

Cloud Run injects ``$PORT`` and requires a ``0.0.0.0`` bind; ``$MCP_ROLE``
(``cop``|``thief``) picks which agent this instance exposes, so the SAME image
is deployed twice (one service per role). Token auth is enforced inside the tools
via ``$MCP_AUTH_TOKEN`` (see ``server_app``), never baked into the image.

Run locally::

    MCP_ROLE=cop PORT=8080 python -m cop_thief.mcp_servers.cloud_entry
"""

from __future__ import annotations

import os

from ..game.actions import Role
from .server_app import run_server


def main() -> None:
    """Bind the role from ``$MCP_ROLE`` on ``0.0.0.0:$PORT`` (Cloud Run defaults)."""
    role = Role(os.environ.get("MCP_ROLE", "cop").lower())
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    print(f"Starting {role.value} MCP server on {host}:{port}")
    run_server(role, host, port)


if __name__ == "__main__":
    main()
