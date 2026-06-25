"""Peer-thief MCP client helpers for :class:`PeerSeriesRunner` (Option 1, §D).

Split out of ``peer_series`` to stay within the 150-line limit. ``_PeerThiefClient``
is a mixin: its methods use attributes set in ``PeerSeriesRunner.__init__``
(``peer_thief_url``, ``peer_token``, ``max_retries``, ``params``).
"""

from __future__ import annotations

from ..agents.strategies import legal_targets
from ..game.actions import Action, ActionType
from ..game.board import Position
from .mcp_series import TechnicalLoss

# An action the engine is guaranteed to reject, so an unparseable peer reply is
# funnelled through the normal illegal-move forfeit path (§2.5) instead of crashing.
_FORFEIT_ACTION = Action(ActionType.MOVE, Position(-1, -1))


class _PeerThiefClient:
    """Pull the opponent thief's moves over MCP, with retries and a forfeit fallback."""

    def _peer_client(self):
        """A streamable-HTTP client to the opponent's thief server."""
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        headers = {"Authorization": f"Bearer {self.peer_token}"} if self.peer_token else None
        return Client(StreamableHttpTransport(self.peer_thief_url, headers=headers))

    async def _call(self, client, tool: str, args: dict) -> dict:
        """Call an MCP tool with a retry budget; exhaustion is a Technical Loss (§3)."""
        last: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                result = await client.call_tool(tool, args)
                return result.data if result.data is not None else {}
            except Exception as exc:  # noqa: BLE001 — transport/tool failure -> retry/void
                last = exc
        raise TechnicalLoss(f"tool {tool!r} failed after {self.max_retries + 1} tries: {last}")

    async def _ask_peer(self, client, observation: dict, opponent_message: str):
        """One ``play_turn`` call; a garbled reply degrades to a forfeit action."""
        data = await self._call(
            client, "play_turn", {"observation": observation, "opponent_message": opponent_message}
        )
        message = str(data.get("message", ""))
        try:
            action = Action.from_dict(data["action"])
        except Exception:  # noqa: BLE001 — malformed action -> let the engine forfeit it
            action = _FORFEIT_ACTION
        return message, action

    async def _peer_move(self, client, observation: dict, opponent_message: str):
        """Pull the opponent thief's move; re-prompt once if the first is illegal (§2.5)."""
        message, action = await self._ask_peer(client, observation, opponent_message)
        if not self._is_legal(action, observation):
            message, action = await self._ask_peer(client, observation, opponent_message)
        return message, action

    def _is_legal(self, action: Action, observation: dict) -> bool:
        """The thief may only move; check the destination against our authoritative view."""
        if action.type is not ActionType.MOVE:
            return False
        targets = set(legal_targets(observation, self.params.eight_directional))
        return tuple(action.to.to_list()) in targets
