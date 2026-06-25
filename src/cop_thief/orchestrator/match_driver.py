"""Lockstep driver for the inter-group match (opponent contract, docs/MATCH_PEER.md).

Both teams run their own driver against four role-bound match servers (two ours,
two theirs). Per sub-game the authoritative referee is the **cop-side** team's cop
server and the mirror is the **thief-side** team's thief server; every move is
submitted to **both** so they stay in sync. We act only when *both* relevant
servers report ``turn == our role``. Our brain (LLM/heuristic) decides our moves
in this client (§5.2); the opponent's driver decides theirs.

Role split (we are group_2): sub-games 1–3 we are THIEF (they referee), 4–6 we are
COP (we referee). We call ``reset`` only for the sub-games we referee; otherwise we
wait for the opponent's reset to appear. We record authoritative results for our
cop half (4–6) — those become our half of the §9.2 report.
"""

from __future__ import annotations

import asyncio

from ..agents.cop_agent import build_cop_agent
from ..agents.thief_agent import build_thief_agent
from ..config import Config
from ..game.actions import ActionType, Role
from ..game.scoring import accumulate, score_subgame
from ..game.state import SubGameResult
from ..security.tokens import resolve_expected_token
from .mcp_series import TechnicalLoss
from .results import SeriesResult, SubGameSummary, TurnLogWriter

# The agreed start cells per sub-game (docs/MATCH_PEER.md): sub_game -> (cop, thief).
START_POSITIONS: dict[int, tuple[list[int], list[int]]] = {
    1: ([4, 0], [1, 3]), 2: ([3, 1], [4, 4]), 3: ([1, 1], [4, 0]),
    4: ([0, 4], [3, 1]), 5: ([4, 3], [0, 1]), 6: ([0, 1], [3, 1]),
}


class MatchDriver:
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

    # ----- client construction --------------------------------------------
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

    # ----- run loop --------------------------------------------------------
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

    def _tally(self, index: int, final: dict, team_totals: dict, breakdown: list) -> None:
        """Append one §9.2 sub-game row (opponent's agreed shape) and tally team points."""
        status = final.get("status")
        if status not in (SubGameResult.COP_WIN.value, SubGameResult.THIEF_WIN.value):
            return  # voided / non-terminal — never crash the result report
        result = SubGameResult(status)
        sc = score_subgame(result, self.table)
        we_are_cop = self._layout(index)["we_are_cop"]
        cop_name = self.our_name if we_are_cop else self.opp_name
        thief_name = self.opp_name if we_are_cop else self.our_name
        winner = "cop" if result is SubGameResult.COP_WIN else "thief"
        team_totals[cop_name] = team_totals.get(cop_name, 0) + sc["cop"]
        team_totals[thief_name] = team_totals.get(thief_name, 0) + sc["thief"]
        breakdown.append({  # exact key order matches docs/MATCH_PEER.md / opponent contract
            "index": index,
            "winner": winner,
            "moves_played": int(final.get("thief_moves", 0)),
            "cop_score": sc["cop"],
            "thief_score": sc["thief"],
            "technical_loss": False,
            "cop_group": cop_name,
            "thief_group": thief_name,
            "winner_group": cop_name if winner == "cop" else thief_name,
        })

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
            # They referee (1-3): adopt THEIR start. Their cells come from their own
            # seed (docs/MATCH_PEER.md), so we don't hardcode — we wait for their fresh
            # reset (thief_moves==0) and mirror those exact cells into our thief server.
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

    async def _adopt_start(self, opp_cli) -> tuple[list[int], list[int]]:
        """Wait for the opponent's fresh reset (thief_moves==0) and return its start cells."""
        waited = 0.0
        while True:
            s = await self._call(opp_cli, "get_match_status", {})
            if (s.get("status") == "ongoing" and s.get("thief_moves") == 0
                    and s.get("cop") and s.get("thief")):
                return list(s["cop"]), list(s["thief"])
            await asyncio.sleep(self.poll_interval)
            waited += self.poll_interval
            if waited > self.turn_timeout * 4:
                raise TechnicalLoss("opponent's fresh reset (thief_moves==0) did not appear")

    async def _await_start(self, refs, cop_start, thief_start) -> None:
        """Block until both referees show the agreed start with thief_moves == 0."""
        waited = 0.0
        while True:
            statuses = [await self._call(ref, "get_match_status", {}) for ref in refs]
            ready = all(
                s.get("status") == "ongoing" and s.get("thief_moves") == 0
                and s.get("cop") == cop_start and s.get("thief") == thief_start
                for s in statuses
            )
            if ready:
                return
            await asyncio.sleep(self.poll_interval)
            waited += self.poll_interval
            if waited > self.turn_timeout * 4:
                raise TechnicalLoss("opponent reset/start did not appear in time")

    async def _take_our_turn(self, index, lay, clients, barriers_used) -> int:
        """Decide our move, submit to both referees, deliver our message. Returns barriers added."""
        our_view = clients[lay["our_view"]]
        observation = await self._call(our_view, "get_observation", {})
        inbox = await self._call(our_view, "get_messages", {})
        ours = lay["our_role"].value
        opp_msgs = [m["message"] for m in inbox.get("messages", []) if m.get("from") != ours]
        agent_obs = self._to_agent_obs(observation, lay["our_role"], index, barriers_used)
        agent = self.cop_agent if lay["we_are_cop"] else self.thief_agent
        message, action = agent.decide(agent_obs, opp_msgs[-1:])
        status = await self._call(clients[lay["our_view"]], "get_match_status", {})
        payload = {
            "sub_game": index,
            "move_number": int(status.get("thief_moves", 0))
            + (1 if lay["our_role"] is Role.THIEF else 0),
            "role": lay["our_role"].value,
            "message": message,
            "action": action.to_dict(),
        }
        for ref in (clients[lay["cop_server"]], clients[lay["thief_server"]]):
            await self._call(ref, "submit_turn", {"payload": payload})
        await self._call(
            clients[lay["opp_view"]], "receive_message",
            {"from_role": lay["our_role"].value, "message": message},
        )
        added = 1 if (lay["we_are_cop"] and action.type is ActionType.BARRIER) else 0
        if self.writer:
            self._log_turn(index, payload, status)
        return added

    def _to_agent_obs(self, obs: dict, role: Role, index: int, barriers_used: int) -> dict:
        """Translate the opponent contract's observation into our agent's expected shape."""
        opponent = obs.get("visible_opponent")
        return {
            "role": role.value,
            "sub_game": index,
            "move_number": obs.get("move_number", 0),
            "max_moves": self.params.max_moves,
            "grid_size": obs.get("grid_size", [self.params.grid_rows, self.params.grid_cols]),
            "vision_radius": obs.get("vision_radius", self.vision),
            "self": obs["own_cell"],
            "opponent": opponent,
            "opponent_visible": opponent is not None,
            "visible_barriers": obs.get("visible_barriers", []),
            "barriers_remaining": (
                (self.params.max_barriers - barriers_used) if role is Role.COP else 0
            ),
        }

    def _log_turn(self, index, payload, status) -> None:
        from datetime import UTC, datetime

        from ..game.state import TurnRecord

        self.writer.turn(TurnRecord(
            timestamp=datetime.now(UTC).isoformat(),
            sub_game=index,
            move_number=payload["move_number"],
            role=Role(payload["role"]),
            message=payload["message"],
            action=payload["action"],
            legal=True,
            validation="submitted",
            cop=status.get("cop") or [],
            thief=status.get("thief") or [],
        ))

    def _summarise(self, index, status, cop_start, thief_start, final) -> SubGameSummary:
        result = SubGameResult(status)
        summary = SubGameSummary(
            sub_game=index,
            result=result.value,
            reason="capture" if result is SubGameResult.COP_WIN else "survived",
            moves=int(final.get("thief_moves", 0)),
            score=score_subgame(result, self.table),
            start={"cop": cop_start, "thief": thief_start},
            barriers=[],
        )
        if self.writer:
            self.writer.subgame_end(summary)
        return summary
