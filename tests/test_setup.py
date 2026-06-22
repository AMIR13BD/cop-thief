"""Start-position generation: distinct cells, vision spacing, reproducibility."""

import random

from cop_thief.game.board import chebyshev_distance
from cop_thief.game.setup import GameParams, new_subgame


def _params(**overrides) -> GameParams:
    base = dict(
        grid_rows=5, grid_cols=5, max_moves=25, num_games=6, max_barriers=5,
        eight_directional=True, vision_radius=2, start_outside_vision=True,
    )
    base.update(overrides)
    return GameParams(**base)


def test_cop_and_thief_never_share_a_cell():
    rng = random.Random(0)
    for index in range(1, 50):
        state = new_subgame(index, _params(), rng)
        assert state.cop != state.thief


def test_start_outside_vision_when_grid_allows():
    rng = random.Random(7)
    # On a larger grid, the constraint is always satisfiable.
    state = new_subgame(1, _params(grid_rows=8, grid_cols=8), rng)
    assert chebyshev_distance(state.cop, state.thief) > 2


def test_same_seed_reproduces_positions():
    a = new_subgame(1, _params(), random.Random(42))
    b = new_subgame(1, _params(), random.Random(42))
    assert (a.cop, a.thief) == (b.cop, b.thief)


def test_thief_moves_first():
    from cop_thief.game.actions import Role

    state = new_subgame(1, _params(), random.Random(1))
    assert state.to_move is Role.THIEF
