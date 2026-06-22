"""Grid geometry: positions, distance, and the board with its barriers.

Coordinates follow SHARED_MATCH_RULES.md §2.3: origin ``[0, 0]`` is top-left,
addressing is ``[row, col]`` (rows increase downward, cols rightward).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The eight king-move offsets (8-directional movement, diagonals included).
_EIGHT_DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
# Orthogonal-only offsets (used when config selects 4-directional movement).
_FOUR_DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


@dataclass(frozen=True)
class Position:
    """An immutable ``[row, col]`` grid cell."""

    row: int
    col: int

    def to_list(self) -> list[int]:
        """Return ``[row, col]`` — the JSON/payload representation."""
        return [self.row, self.col]

    @classmethod
    def from_list(cls, pair: list[int] | tuple[int, int]) -> Position:
        """Build a position from a ``[row, col]`` pair."""
        return cls(int(pair[0]), int(pair[1]))


def chebyshev_distance(a: Position, b: Position) -> int:
    """King-move distance: the larger of the row and column deltas."""
    return max(abs(a.row - b.row), abs(a.col - b.col))


def direction_offsets(eight_directional: bool) -> list[tuple[int, int]]:
    """The legal ``(drow, dcol)`` steps for the configured movement mode."""
    return list(_EIGHT_DIRS if eight_directional else _FOUR_DIRS)


@dataclass
class Board:
    """The grid plus the set of impassable barrier cells.

    The board knows nothing about players; it only answers spatial questions
    (bounds, passability, neighbours) so the engine stays the single rule owner.
    """

    rows: int
    cols: int
    eight_directional: bool = True
    barriers: set[Position] = field(default_factory=set)

    def in_bounds(self, pos: Position) -> bool:
        """True when ``pos`` lies on the grid."""
        return 0 <= pos.row < self.rows and 0 <= pos.col < self.cols

    def is_barrier(self, pos: Position) -> bool:
        """True when a barrier occupies ``pos``."""
        return pos in self.barriers

    def is_passable(self, pos: Position) -> bool:
        """A cell can be entered when it is on the grid and not a barrier."""
        return self.in_bounds(pos) and not self.is_barrier(pos)

    def add_barrier(self, pos: Position) -> None:
        """Mark ``pos`` impassable for both agents."""
        self.barriers.add(pos)

    def neighbours(self, pos: Position) -> list[Position]:
        """Passable cells one legal step away from ``pos``."""
        offsets = direction_offsets(self.eight_directional)
        candidates = (Position(pos.row + dr, pos.col + dc) for dr, dc in offsets)
        return [c for c in candidates if self.is_passable(c)]
