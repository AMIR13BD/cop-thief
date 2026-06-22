"""Step-wise driver: plays the series and yields a snapshot per turn for the GUI.

This is the presentation layer's view of the same authoritative referee the
runner uses; it never changes the rules, it only emits per-turn state so the
board can be animated. Defaults to heuristic agents so the window is responsive.
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from ..agents.cop_agent import build_cop_agent
from ..agents.thief_agent import build_thief_agent
from ..config import Config
from ..game.actions import Role, TurnPayload
from ..game.scoring import accumulate, score_subgame
from ..game.setup import GameParams, new_subgame
from ..orchestrator.referee import SubGameReferee


def _snapshot(index, ply, role, message, action, ref, totals, params, *, score=None) -> dict:
    """Flatten the current referee state into a render-ready dict."""
    state = ref.state
    return {
        "sub_game": index,
        "ply": ply,
        "role": role.value if role else None,
        "message": message,
        "action": action.to_dict() if action else None,
        "cop": state.cop.to_list(),
        "thief": state.thief.to_list(),
        "barriers": sorted(b.to_list() for b in state.board.barriers),
        "grid": [params.grid_rows, params.grid_cols],
        "to_move": state.to_move.value,
        "result": state.result.value,
        "reason": state.reason,
        "barriers_remaining": state.barriers_remaining,
        "totals": dict(totals),
        "score": score,
    }


def iter_series(config: Config, llm=None) -> Iterator[dict]:
    """Yield one snapshot for the start of each sub-game and after every turn."""
    params: GameParams = config.game_params()
    table = config.scoring_table()
    cop = build_cop_agent(params, llm, random.Random(config.seed + 1))
    thief = build_thief_agent(params, llm, random.Random(config.seed + 2))
    agents = {Role.COP: cop, Role.THIEF: thief}
    setup_rng = random.Random(config.seed)
    totals = {"cop": 0, "thief": 0}
    for index in range(1, params.num_games + 1):
        ref = SubGameReferee(new_subgame(index, params, setup_rng), config.vision_radius)
        outbox: dict[Role, list[str]] = {Role.COP: [], Role.THIEF: []}
        yield _snapshot(index, 0, None, "Sub-game start", None, ref, totals, params)
        ply = 0
        while not ref.is_over():
            role = ref.whose_turn()
            ply += 1
            message, action = agents[role].decide(ref.observe(role), outbox[role.opponent][-2:])
            ref.submit(TurnPayload(index, ply, role, message, action))
            outbox[role].append(message)
            yield _snapshot(index, ply, role, message, action, ref, totals, params)
        score = score_subgame(ref.state.result, table)
        totals = accumulate(totals, score)
        yield _snapshot(index, ply, None, "Sub-game over", None, ref, totals, params, score=score)
