"""Referee-driven runner for an inter-group match half (MATCH_PROTOCOL.md §D).

This drives the three sub-games in which **we are the cop**, so we are the sole
referee (SHARED_MATCH_RULES.md §2.1): we own the authoritative
:class:`~cop_thief.orchestrator.referee.SubGameReferee`, generate the start
positions, and adjudicate every action. On our cop turn we decide locally; on the
opponent's thief turn we pull their move from their **thief** server's
``play_turn`` tool (Option 1) and re-validate it against our state.

The other three sub-games (we are thief, the opponent referees) are driven by the
opponent's orchestrator calling *our* ``play_turn`` — nothing here runs for them.
Each referee produces its own three authoritative records; the two halves are
exchanged out of band and concatenated in sub-game order for the §9.2 report.
"""

from __future__ import annotations

import asyncio
import random

from ..agents.cop_agent import build_cop_agent
from ..agents.strategies import legal_targets
from ..config import Config
from ..game.actions import Action, ActionType, Role, TurnPayload, round_number
from ..game.board import Position
from ..game.scoring import accumulate, score_subgame
from ..game.setup import new_subgame
from ..security.tokens import resolve_peer_token
from .mcp_series import TechnicalLoss
from .referee import SubGameReferee
from .results import SeriesResult, SubGameSummary, TurnLogWriter

# An action the engine is guaranteed to reject, so an unparseable peer reply is
# funnelled through the normal illegal-move forfeit path (§2.5) instead of crashing.
_FORFEIT_ACTION = Action(ActionType.MOVE, Position(-1, -1))


class PeerSeriesRunner:
    """Referee our cop half by pulling the opponent thief's moves over MCP."""

    def __init__(
        self,
        config: Config,
        peer_thief_url: str,
        peer_token: str | None = None,
        llm=None,
        log: bool = True,
        num_games: int = 3,
        start_index: int = 1,
    ) -> None:
        self.config = config
        self.params = config.game_params()
        self.table = config.scoring_table()
        self.vision = config.vision_radius
        self.seed = config.seed
        self.max_retries = int(config.match.get("max_retries", 3))
        self.num_games = num_games
        self.start_index = start_index
        self.cop = build_cop_agent(self.params, llm, random.Random(self.seed + 1))
        self.peer_thief_url = peer_thief_url
        self.peer_token = peer_token or resolve_peer_token()
        self.writer = TurnLogWriter(config.logging["dir"]) if log else None

    # ----- client construction --------------------------------------------
    def _peer_client(self):
        """A streamable-HTTP client to the opponent's thief server."""
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        headers = {"Authorization": f"Bearer {self.peer_token}"} if self.peer_token else None
        return Client(StreamableHttpTransport(self.peer_thief_url, headers=headers))

    # ----- the run loop ----------------------------------------------------
    def run(self) -> SeriesResult:
        """Synchronous entrypoint: referee the half and return its result."""
        return asyncio.run(self._run())

    async def _run(self) -> SeriesResult:
        setup_rng = random.Random(self.seed)
        totals = {"cop": 0, "thief": 0}
        summaries: list[SubGameSummary] = []
        async with self._peer_client() as thief_cli:
            valid = 0
            while valid < self.num_games:
                index = self.start_index + valid
                rng_state = setup_rng.getstate()  # so a void sub-game re-runs identically
                try:
                    summary = await self._run_subgame(index, setup_rng, thief_cli)
                except TechnicalLoss as exc:
                    setup_rng.setstate(rng_state)
                    if self.writer:
                        self.writer.void(index, str(exc))
                    continue
                valid += 1
                totals = accumulate(totals, summary.score)
                summaries.append(summary)
        if self.writer:
            self.writer.series_end(totals)
            self.writer.close()
        return SeriesResult(sub_games=summaries, totals=totals)

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

    async def _run_subgame(self, index, setup_rng, thief_cli) -> SubGameSummary:
        state = new_subgame(index, self.params, setup_rng)
        ref = SubGameReferee(state, self.vision)
        start = {"cop": state.cop.to_list(), "thief": state.thief.to_list()}
        ply = 0
        cop_msg = ""  # our cop's last NL line (sent to the opponent thief)
        thief_msg = ""  # opponent thief's last NL line (read by our cop)
        while not ref.is_over():
            role = ref.whose_turn()
            ply += 1
            observation = ref.observe(role)
            if role is Role.COP:
                message, action = self.cop.decide(observation, [thief_msg] if thief_msg else [])
                cop_msg = message
            else:  # opponent thief — decided remotely via their server's play_turn
                message, action = await self._peer_move(thief_cli, observation, cop_msg)
                thief_msg = message
            record = ref.submit(TurnPayload(index, round_number(ply), role, message, action))
            if self.writer:
                self.writer.turn(record)
        return self._summarise(index, ref, start)

    def _summarise(self, index, ref, start) -> SubGameSummary:
        state = ref.state
        summary = SubGameSummary(
            sub_game=index,
            result=state.result.value,
            reason=state.reason,
            moves=state.move_number,
            score=score_subgame(state.result, self.table),
            start=start,
            barriers=sorted(b.to_list() for b in state.board.barriers),
        )
        if self.writer:
            self.writer.subgame_end(summary)
        return summary
