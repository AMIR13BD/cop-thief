"""The MCP **client**: drives the full series THROUGH the two MCP servers.

This is the orchestrator the assignment calls the *MCP client* (§5.2). It owns the
single authoritative :class:`~cop_thief.orchestrator.referee.SubGameReferee` and
the LLM, and every turn flows over MCP tools:

* the acting agent pushes its observation to its own server (``set_context``) and
  reads it back (``observe``),
* it reads the opponent's most recent natural-language line from the opponent's
  server (``last_message``),
* it **decides client-side** (LLM or heuristic — the LLM is never in the server)
  and announces its message + action via its own server (``submit_turn``),
* it asks the opponent's server to verify a claimed location (``verify_location``).

The outcome is always decided by the orchestrator's referee on the binding
``action`` — never by the (bluffable) ``message``.

Technical-Loss handling (§9): a sub-game whose tool calls keep failing for
technical/transport reasons is marked void and re-run from the same start, until
``num_games`` valid sub-games complete.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable

from ..agents.cop_agent import build_cop_agent
from ..agents.thief_agent import build_thief_agent
from ..config import Config
from ..game.actions import Role, TurnPayload, round_number
from ..game.scoring import accumulate, score_subgame
from ..game.setup import new_subgame
from ..security.tokens import resolve_expected_token
from .referee import SubGameReferee
from .results import SeriesResult, SubGameSummary, TurnLogWriter

# A factory that, given a role, returns an *unopened* MCP client context manager.
ClientFactory = Callable[[Role], object]


class TechnicalLoss(Exception):
    """A sub-game failed for technical/transport reasons and must be re-run (§9)."""


class MCPSeriesRunner:
    """Plays ``num_games`` valid sub-games by driving both MCP servers over HTTP."""

    def __init__(
        self,
        config: Config,
        llm=None,
        log: bool = True,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.config = config
        self.params = config.game_params()
        self.table = config.scoring_table()
        self.vision = config.vision_radius
        self.seed = config.seed
        self.max_retries = int(config.match.get("max_retries", 3))
        self.cop = build_cop_agent(self.params, llm, random.Random(self.seed + 1))
        self.thief = build_thief_agent(self.params, llm, random.Random(self.seed + 2))
        self.urls = {Role.COP: config.mcp_url("cop"), Role.THIEF: config.mcp_url("thief")}
        self.client_factory = client_factory or self._http_client
        self.writer = TurnLogWriter(config.logging["dir"]) if log else None

    # ----- client construction --------------------------------------------
    def _http_client(self, role: Role):
        """Default factory: a streamable-HTTP client to ``role``'s server URL."""
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        token = resolve_expected_token()
        headers = {"Authorization": f"Bearer {token}"} if token else None
        return Client(StreamableHttpTransport(self.urls[role], headers=headers))

    # ----- the run loop ----------------------------------------------------
    def run(self) -> SeriesResult:
        """Synchronous entrypoint: play the whole series and return the result."""
        return asyncio.run(self._run())

    async def _run(self) -> SeriesResult:
        agents = {Role.COP: self.cop, Role.THIEF: self.thief}
        setup_rng = random.Random(self.seed)
        totals = {"cop": 0, "thief": 0}
        summaries: list[SubGameSummary] = []
        async with (
            self.client_factory(Role.COP) as cop_cli,
            self.client_factory(Role.THIEF) as thief_cli,
        ):
            clients = {Role.COP: cop_cli, Role.THIEF: thief_cli}
            valid = 0
            while valid < self.params.num_games:
                index = valid + 1
                rng_state = setup_rng.getstate()  # so a void sub-game re-runs identically
                try:
                    summary = await self._run_subgame(index, setup_rng, clients, agents)
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
        """Call an MCP tool with a small retry budget; exhaustion is a Technical Loss."""
        last: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                result = await client.call_tool(tool, args)
                return result.data if result.data is not None else {}
            except Exception as exc:  # noqa: BLE001 — transport/tool failure -> retry/void
                last = exc
        raise TechnicalLoss(f"tool {tool!r} failed after {self.max_retries + 1} tries: {last}")

    async def _run_subgame(self, index, setup_rng, clients, agents) -> SubGameSummary:
        state = new_subgame(index, self.params, setup_rng)
        ref = SubGameReferee(state, self.vision)
        start = {"cop": state.cop.to_list(), "thief": state.thief.to_list()}
        ply = 0
        while not ref.is_over():
            role = ref.whose_turn()
            ply += 1
            observation = ref.observe(role)
            true_pos = state.position_of(role).to_list()
            # The acting agent reads its observation from its own MCP server.
            await self._call(
                clients[role], "set_context", {"observation": observation, "position": true_pos}
            )
            server_obs = await self._call(clients[role], "observe", {})
            # ...and the opponent's latest natural-language line from the opponent's server.
            opponent = await self._call(clients[role.opponent], "last_message", {})
            inbox = [opponent["message"]] if opponent.get("message") else []
            # Decide CLIENT-SIDE (LLM or heuristic); the LLM is never inside the server.
            message, action = agents[role].decide(server_obs or observation, inbox)
            # Announce the NL message + action via the acting agent's server.
            await self._call(
                clients[role], "submit_turn", {"message": message, "action": action.to_dict()}
            )
            # Mutual location verification through the opponent's server (§5.1).
            await self._call(
                clients[role.opponent],
                "verify_location",
                {"claim": state.position_of(role.opponent).to_list()},
            )
            # The orchestrator's referee is the single authority on the result.
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


def run_mcp_series(config: Config, llm=None, log: bool = True) -> SeriesResult:
    """Convenience wrapper: build the runner and play the series over HTTP."""
    return MCPSeriesRunner(config, llm=llm, log=log).run()
