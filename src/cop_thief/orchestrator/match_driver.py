"""Lockstep driver for the inter-group match (opponent contract, docs/MATCH_PEER.md).

Both teams run their own driver against four role-bound match servers. Per sub-game
the authoritative referee is the cop-side team's cop server and the mirror is the
thief-side team's thief server; every move is submitted to **both**. We are group_2:
THIEF in sub-games 1–3 (they referee), COP in 4–6 (we referee). Per-turn decision,
observation translation, and result recording live in the ``_DriverTurns`` mixin.
"""

from __future__ import annotations

import asyncio

from ..agents.cop_agent import build_cop_agent
from ..agents.thief_agent import build_thief_agent
from ..config import Config
from ..game.actions import Role
from ..game.scoring import accumulate
from ..security.tokens import resolve_expected_token
from .match_driver_turns import _DriverTurns
from .mcp_series import TechnicalLoss
from .results import SeriesResult, SubGameSummary, TurnLogWriter

# The agreed start cells per sub-game (docs/MATCH_PEER.md): sub_game -> (cop, thief).
START_POSITIONS: dict[int, tuple[list[int], list[int]]] = {
    1: ([4, 0], [1, 3]), 2: ([3, 1], [4, 4]), 3: ([1, 1], [4, 0]),
    4: ([0, 4], [3, 1]), 5: ([4, 3], [0, 1]), 6: ([0, 1], [3, 1]),
}


class MatchDriver(_DriverTurns):
    """Drive our side of the 6-sub-game inter-group match over the four match servers."""

    def __init__(
        self,
        config: Config,
        peer_cop_url: str,
        peer_thief_url: str,
        peer_cop_token: str,
        peer_thief_token: str,
        llm=None,
        log: bool = True,
        poll_interval: float = 1.0,
        turn_timeout: float = 30.0,
    ) -> None:
        self.config = config
        self.params = config.game_params()
        self.table = config.scoring_table()
        self.vision = config.vision_radius
        self.max_retries = int(config.match.get("max_retries", 3))
        self.poll_interval = poll_interval
        self.turn_timeout = turn_timeout
        self.cop_agent = build_cop_agent(self.params, llm)
        self.thief_agent = build_thief_agent(self.params, llm)
        self.our_name = config.team["group_name"]
        self.opp_name = config.match.get("opponent_name", "ahk-yosi")
        our_token = resolve_expected_token()
        team = config.team  # our canonical deployed (cloud) URLs live here, not in mcp_url()
        self._endpoints = {
            "our_cop": (team["cop_mcp_url"], our_token),
            "our_thief": (team["thief_mcp_url"], our_token),
            "their_cop": (peer_cop_url, peer_cop_token),
            "their_thief": (peer_thief_url, peer_thief_token),
        }
        self.writer = TurnLogWriter(config.logging["dir"]) if log else None

    def _client(self, key: str):
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        url, token = self._endpoints[key]
        headers = {"Authorization": f"Bearer {token}"} if token else None
        return Client(StreamableHttpTransport(url, headers=headers))

    async def _call(self, client, tool: str, args: dict) -> dict:
        """Call a tool with a retry budget; exhaustion is a Technical Loss (§3)."""
        last: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                result = await client.call_tool(tool, args)
                return result.data if result.data is not None else {}
            except Exception as exc:  # noqa: BLE001 — transport/tool failure -> retry/void
                last = exc
        raise TechnicalLoss(f"tool {tool!r} failed after {self.max_retries + 1} tries: {last}")

    def run(self) -> SeriesResult:
        """Play all 6 sub-games; return our authoritative cop half (sub-games 4–6)."""
        return asyncio.run(self._run())

    async def _run(self) -> SeriesResult:
        totals = {"cop": 0, "thief": 0}
        summaries: list[SubGameSummary] = []
        team_totals = {self.our_name: 0, self.opp_name: 0}
        breakdown: list[dict] = []
        async with (
            self._client("our_cop") as our_cop,
            self._client("our_thief") as our_thief,
            self._client("their_cop") as their_cop,
            self._client("their_thief") as their_thief,
        ):
            clients = {
                "our_cop": our_cop, "our_thief": our_thief,
                "their_cop": their_cop, "their_thief": their_thief,
            }
            for index in range(1, self.params.num_games + 1):
                summary, final = await self._play_subgame(index, clients)
                self._tally(index, final, team_totals, breakdown)
                if summary is not None:  # our cop half (4–6) — authoritative record
                    totals = accumulate(totals, summary.score)
                    summaries.append(summary)
        if self.writer:
            self.writer.series_end(totals)
            self.writer.close()
        return SeriesResult(sub_games=summaries, totals=totals,
                            per_team=team_totals, breakdown=breakdown)

    def _layout(self, index: int) -> dict:
        """Which servers/role apply this sub-game (we are group_2)."""
        we_are_cop = index >= 4
        return {
            "we_are_cop": we_are_cop,
            "our_role": Role.COP if we_are_cop else Role.THIEF,
            "cop_server": "our_cop" if we_are_cop else "their_cop",
            "thief_server": "their_thief" if we_are_cop else "our_thief",
            "our_view": "our_cop" if we_are_cop else "our_thief",
            "opp_view": "their_thief" if we_are_cop else "their_cop",
        }

    async def _play_subgame(self, index: int, clients: dict) -> tuple[SubGameSummary | None, dict]:
        lay = self._layout(index)
        cop_cli, thief_cli = clients[lay["cop_server"]], clients[lay["thief_server"]]
        refs = [cop_cli, thief_cli]
        own_cli, opp_cli = clients[lay["our_view"]], clients[lay["opp_view"]]
        if lay["we_are_cop"]:
            # We referee (4-6): we choose the start, reset our cop server, and wait for
            # their thief mirror to show the same cells (they read & mirror our reset).
            cop_start, thief_start = START_POSITIONS[index]
            await self._call(own_cli, "reset", {"cop": cop_start, "thief": thief_start})
            await self._await_start([opp_cli], cop_start, thief_start)
        else:
            # They referee (1-3): adopt THEIR start (their seed), mirror it into our server.
            cop_start, thief_start = await self._adopt_start(opp_cli)
            await self._call(own_cli, "reset", {"cop": cop_start, "thief": thief_start})

        our_barriers_used = 0
        while True:
            statuses = [await self._call(ref, "get_match_status", {}) for ref in refs]
            if all(s.get("status") not in ("ongoing", None) for s in statuses):
                break  # terminal on both
            our_turn = all(
                s.get("status") == "ongoing" and s.get("turn") == lay["our_role"].value
                for s in statuses
            )
            if not our_turn:
                await asyncio.sleep(self.poll_interval)  # opponent's turn / settling
                continue
            our_barriers_used += await self._take_our_turn(index, lay, clients, our_barriers_used)

        result_status = statuses[0].get("status", "ongoing")
        if not lay["we_are_cop"]:
            return None, statuses[0]  # their authoritative half — they record it
        return (self._summarise(index, result_status, cop_start, thief_start, statuses[0]),
                statuses[0])
