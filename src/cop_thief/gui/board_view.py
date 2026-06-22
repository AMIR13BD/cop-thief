"""Canvas renderer: draws one snapshot of the board (cells, barriers, agents)."""

from __future__ import annotations

import tkinter as tk

_BG = "#1e1f29"
_CELL = "#2b2d3a"
_GRID = "#3a3d4d"
_BARRIER = "#0d0d12"
_COP = "#4f8cff"
_THIEF = "#ff5d5d"
_CAPTURE = "#ffd23f"


class BoardView:
    """A Tk ``Canvas`` that renders a single GUI snapshot."""

    def __init__(self, parent: tk.Misc, cell: int = 84, pad: int = 26) -> None:
        self.cell = cell
        self.pad = pad
        self.canvas = tk.Canvas(parent, bg=_BG, highlightthickness=0)

    def _center(self, row: int, col: int) -> tuple[float, float]:
        cx = self.pad + col * self.cell + self.cell / 2
        cy = self.pad + row * self.cell + self.cell / 2
        return cx, cy

    def _disc(self, row: int, col: int, colour: str, label: str) -> None:
        cx, cy = self._center(row, col)
        radius = self.cell * 0.34
        self.canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius, fill=colour, outline=""
        )
        self.canvas.create_text(cx, cy, text=label, fill="white", font=("Helvetica", 18, "bold"))

    def render(self, snap: dict) -> None:
        """Clear and redraw the board for ``snap``."""
        rows, cols = snap["grid"]
        self.canvas.configure(width=cols * self.cell + 2 * self.pad,
                              height=rows * self.cell + 2 * self.pad)
        self.canvas.delete("all")
        for row in range(rows):
            for col in range(cols):
                x0, y0 = self.pad + col * self.cell, self.pad + row * self.cell
                self.canvas.create_rectangle(
                    x0, y0, x0 + self.cell, y0 + self.cell, fill=_CELL, outline=_GRID
                )
        for brow, bcol in snap["barriers"]:
            x0, y0 = self.pad + bcol * self.cell, self.pad + brow * self.cell
            self.canvas.create_rectangle(
                x0 + 4, y0 + 4, x0 + self.cell - 4, y0 + self.cell - 4, fill=_BARRIER, outline=""
            )
        self._draw_agents(snap)

    def _draw_agents(self, snap: dict) -> None:
        cop, thief = snap["cop"], snap["thief"]
        if cop == thief:  # capture: highlight the shared cell
            cx, cy = self._center(*cop)
            ring = self.cell * 0.42
            self.canvas.create_oval(
                cx - ring, cy - ring, cx + ring, cy + ring, outline=_CAPTURE, width=4
            )
            self._disc(cop[0], cop[1], _COP, "C/T")
            return
        self._disc(thief[0], thief[1], _THIEF, "T")
        self._disc(cop[0], cop[1], _COP, "C")
