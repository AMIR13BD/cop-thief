"""Grid geometry shared by the heuristic policies.

Everything here reads only what an agent legally observes — its own cell, the grid
size, and the barriers within its vision (``obs["visible_barriers"]``). Distances
are barrier-aware shortest paths (BFS over king/orthogonal steps), so the policies
plan *around* walls instead of through them. Nothing here can see a hidden
opponent, so partial observability is preserved by construction.
"""

from __future__ import annotations

from collections import deque

from ..game.actions import Action, ActionType
from ..game.board import Position, direction_offsets

BIG = 10_000  # stand-in for "unreachable" / infinite distance


def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    """King-move distance between two cells."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def centrality(cell: tuple[int, int], rows: int, cols: int) -> int:
    """Distance to the nearest wall — 0 on an edge/corner, higher in the open."""
    return min(cell[0], rows - 1 - cell[0], cell[1], cols - 1 - cell[1])


def max_centrality(rows: int, cols: int) -> int:
    """The most central cell's wall-distance (used to turn centrality into a penalty)."""
    return (min(rows, cols) - 1) // 2


def in_bounds(cell: tuple[int, int], rows: int, cols: int) -> bool:
    """True when ``cell`` lies on the grid."""
    return 0 <= cell[0] < rows and 0 <= cell[1] < cols


def blocked_set(obs: dict) -> set[tuple[int, int]]:
    """The barriers the observer can see, as a set of cells."""
    return {tuple(b) for b in obs["visible_barriers"]}


def neighbours(
    cell: tuple[int, int], rows: int, cols: int, blocked: set, eight: bool
) -> list[tuple[int, int]]:
    """Legal one-step destinations from ``cell`` (on-grid, not a known barrier)."""
    out = []
    for d_row, d_col in direction_offsets(eight):
        nxt = (cell[0] + d_row, cell[1] + d_col)
        if in_bounds(nxt, rows, cols) and nxt not in blocked:
            out.append(nxt)
    return out


def mobility(cell: tuple[int, int], rows: int, cols: int, blocked: set, eight: bool) -> int:
    """How many legal moves lead out of ``cell`` — a proxy for "not a trap"."""
    return len(neighbours(cell, rows, cols, blocked, eight))


def bfs(source: tuple[int, int], rows: int, cols: int, blocked: set, eight: bool) -> dict:
    """Shortest-path step counts from ``source`` to every reachable cell."""
    dist = {source: 0}
    queue = deque([source])
    offsets = direction_offsets(eight)
    while queue:
        cur = queue.popleft()
        for d_row, d_col in offsets:
            nxt = (cur[0] + d_row, cur[1] + d_col)
            if nxt in dist or not in_bounds(nxt, rows, cols) or nxt in blocked:
                continue
            dist[nxt] = dist[cur] + 1
            queue.append(nxt)
    return dist


def legal_targets(obs: dict, eight_directional: bool) -> list[tuple[int, int]]:
    """Adjacent in-bounds cells that are not known barriers (always safe to enter)."""
    rows, cols = obs["grid_size"]
    return neighbours(tuple(obs["self"]), rows, cols, blocked_set(obs), eight_directional)


def legal_barrier_targets(obs: dict) -> list[tuple[int, int]]:
    """Adjacent empty cells where the cop may drop a barrier (lecturer-confirmed rule).

    Any of the 8 neighbours that is on-grid, not the (visible) thief's cell, and not
    already a barrier. Always the 8-neighbourhood regardless of movement mode.
    """
    row, col = obs["self"]
    rows, cols = obs["grid_size"]
    blocked = blocked_set(obs)
    thief = tuple(obs["opponent"]) if obs.get("opponent_visible") else None
    out = []
    for d_row, d_col in direction_offsets(eight_directional=True):
        cell = (row + d_row, col + d_col)
        if not in_bounds(cell, rows, cols) or cell in blocked or cell == thief:
            continue
        out.append(cell)
    return out


def move_action(cell: tuple[int, int]) -> Action:
    """A MOVE action to ``cell``."""
    return Action(ActionType.MOVE, Position(cell[0], cell[1]))


def barrier_action(cell: tuple[int, int]) -> Action:
    """A BARRIER action on ``cell``."""
    return Action(ActionType.BARRIER, Position(cell[0], cell[1]))
