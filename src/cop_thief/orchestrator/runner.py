"""The series runner: plays the full 6 sub-game series autonomously.

For each sub-game it builds a fresh referee, then alternates turns — thief first —
asking each agent for a ``(message, action)``, threading the opponent's recent
messages as the only out-of-vision information, and logging every validated turn.
"""

from __future__ import annotations

import random

from ..agents.cop_agent import build_cop_agent
from ..agents.thief_agent import build_thief_agent
from ..config import Config
from ..game.actions import Role, TurnPayload, round_number
from ..game.scoring import accumulate, score_subgame
from ..game.setup import new_subgame
from .referee import SubGameReferee
from .results import SeriesResult, SubGameSummary, TurnLogWriter


class SeriesRunner:
    """Runs ``num_games`` sub-games and returns the scored :class:`SeriesResult`."""

    def __init__(self, config: Config, llm=None, log: bool = True) -> None:
        self.config = config
        self.params = config.game_params()
        self.table = config.scoring_table()
        self.vision = config.vision_radius
        self.seed = config.seed
        self.cop = build_cop_agent(self.params, llm, random.Random(self.seed + 1))
        self.thief = build_thief_agent(self.params, llm, random.Random(self.seed + 2))
        self.writer = TurnLogWriter(config.logging["dir"]) if log else None

    def run(self) -> SeriesResult:
        """Play the whole series and return totals plus per-sub-game summaries."""
        setup_rng = random.Random(self.seed)
        totals: dict[str, int] = {"cop": 0, "thief": 0}
        summaries: list[SubGameSummary] = []
        for index in range(1, self.params.num_games + 1):
            summary = self._run_subgame(index, setup_rng)
            totals = accumulate(totals, summary.score)
            summaries.append(summary)
        if self.writer:
            self.writer.series_end(totals)
            self.writer.close()
        return SeriesResult(sub_games=summaries, totals=totals)

    def _run_subgame(self, index: int, setup_rng: random.Random) -> SubGameSummary:
        state = new_subgame(index, self.params, setup_rng)
        ref = SubGameReferee(state, self.vision)
        agents = {Role.COP: self.cop, Role.THIEF: self.thief}
        outbox: dict[Role, list[str]] = {Role.COP: [], Role.THIEF: []}
        start = {"cop": state.cop.to_list(), "thief": state.thief.to_list()}
        ply = 0
        while not ref.is_over():
            role = ref.whose_turn()
            ply += 1
            observation = ref.observe(role)
            message, action = agents[role].decide(observation, outbox[role.opponent][-2:])
            record = ref.submit(TurnPayload(index, round_number(ply), role, message, action))
            outbox[role].append(message)
            if self.writer:
                self.writer.turn(record)
        return self._summarise(index, ref, start)

    def _summarise(self, index: int, ref: SubGameReferee, start: dict) -> SubGameSummary:
        state = ref.state
        score = score_subgame(state.result, self.table)
        summary = SubGameSummary(
            sub_game=index,
            result=state.result.value,
            reason=state.reason,
            moves=state.move_number,
            score=score,
            start=start,
            barriers=sorted(b.to_list() for b in state.board.barriers),
        )
        if self.writer:
            self.writer.subgame_end(summary)
        return summary
