"""Connectivity + tool-discovery probe for a peer team's MCP server.

Run before an inter-group match (``docs/MATCH_PROTOCOL.md``) to confirm a peer
URL is reachable over HTTP(S) with our bearer token, and to **discover which
tools the peer actually exposes** — the concrete input to agreeing the wire
contract. Read-only: it pings, lists tools, and calls the unauthenticated
``health`` if present, but never a state-changing tool.
"""

from __future__ import annotations

import asyncio

from ..security.tokens import resolve_peer_token


async def _probe(url: str, token: str | None) -> dict:
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    headers = {"Authorization": f"Bearer {token}"} if token else None
    client = Client(StreamableHttpTransport(url, headers=headers))
    async with client:
        await client.ping()
        tools = await client.list_tools()
        result: dict = {
            "reachable": True,
            "authenticated": token is not None,
            "tools": [
                {"name": t.name, "description": (t.description or "").strip()} for t in tools
            ],
        }
        if any(t["name"] == "health" for t in result["tools"]):
            try:
                result["health"] = (await client.call_tool("health", {})).data
            except Exception as exc:  # noqa: BLE001 — health is best-effort diagnostics
                result["health_error"] = str(exc)
        return result


def peer_check(url: str, token: str | None = None) -> dict:
    """Probe ``url`` synchronously; return reachability, the tool list, and health.

    ``token`` falls back to ``MCP_PEER_TOKEN``. Never raises — a failure is
    reported as ``{"reachable": False, "error": ...}`` so the CLI can print it.
    """
    token = token or resolve_peer_token()
    try:
        return asyncio.run(_probe(url, token))
    except Exception as exc:  # noqa: BLE001 — surface any transport/handshake failure
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}
