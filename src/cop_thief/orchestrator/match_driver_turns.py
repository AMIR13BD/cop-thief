"""Per-turn decision, observation translation, and result recording for ``MatchDriver``.

Split out of ``match_driver`` to stay within the 150-line limit. ``_DriverTurns`` is a
mixin: its methods use attributes/methods provided by ``MatchDriver`` (``params``,
``vision``, ``table``, ``writer``, ``cop_agent``, ``thief_agent``, ``our_name``,
``opp_name``, ``_call``, ``_layout``).
"""

from __future__ import annotations

import asyncio

from ..game.actions import ActionType, Role
from ..game.scoring import score_subgame
from ..game.state import SubGameResult
from .mcp_series import TechnicalLoss
from .results import SubGameSummary


class _DriverTurns:
    """Decision/observation/reporting helpers mixed into :class:`MatchDriver`."""

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
