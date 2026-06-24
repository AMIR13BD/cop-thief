"""Barrier-aware grid geometry used by the heuristics."""

from cop_thief.agents.geometry import (
    BIG,
    bfs,
    legal_barrier_targets,
    mobility,
    neighbours,
)


def test_neighbours_exclude_barriers_and_off_grid():
    nbrs = set(neighbours((0, 0), 5, 5, {(1, 1)}, eight=True))
    assert nbrs == {(0, 1), (1, 0)}  # (1,1) walled off; off-grid cells dropped


def test_mobility_counts_open_exits():
    assert mobility((2, 2), 5, 5, set(), eight=True) == 8
    assert mobility((0, 0), 5, 5, set(), eight=True) == 3  # corner


def test_bfs_routes_around_a_wall_so_path_exceeds_straight_line():
    # 4-directional: a wall at (1,0) forces a detour from (0,0) to (2,0).
    dist = bfs((0, 0), 5, 5, {(1, 0)}, eight=False)
    assert dist[(2, 0)] == 4  # detour, vs a straight-line distance of 2


def test_bfs_marks_a_fully_walled_cell_unreachable():
    wall = {(0, 2), (1, 2), (2, 2), (3, 2), (4, 2)}  # full column splits the board
    dist = bfs((2, 0), 5, 5, wall, eight=True)
    assert dist.get((2, 4), BIG) == BIG  # the far side is unreachable


def test_legal_barrier_targets_exclude_thief_and_barriers():
    obs = {
        "self": [2, 2], "grid_size": [5, 5], "visible_barriers": [[1, 2]],
        "opponent": [2, 3], "opponent_visible": True,
    }
    cells = set(legal_barrier_targets(obs))
    assert (2, 3) not in cells  # not the thief's cell
    assert (1, 2) not in cells  # not an existing barrier
    assert (1, 1) in cells      # an ordinary empty neighbour is fine
