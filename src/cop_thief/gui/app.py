"""Tkinter front-end: animated replay of the 6-sub-game series.

Run with ``cop-thief-gui`` (or ``python -m cop_thief.gui``). It plays the series
with the offline heuristic agents and animates cop/thief/barrier movement, the
score, and the per-turn natural-language messages (bluffs included).
"""

from __future__ import annotations

import tkinter as tk

from ..config import Config
from .board_view import BoardView
from .driver import iter_series

_BG = "#1e1f29"
_FG = "#e6e6ee"
_ROLE_COLOUR = {"cop": "#4f8cff", "thief": "#ff5d5d", None: "#9aa0b4"}


def _describe_cop_action(action: dict | None) -> str:
    """Human-readable summary of a cop's action for the GUI status line."""
    if not action:
        return "—"
    row, col = action["to"]
    verb = "placed barrier at" if action["type"] == "barrier" else "moved to"
    return f"{verb} [{row}, {col}]"


def _annotate_cop_actions(snaps: list[dict]) -> list[dict]:
    """Tag each snapshot with the most recent cop action, reset per sub-game."""
    last = "—"
    for snap in snaps:
        if snap["message"] == "Sub-game start":
            last = "—"
        elif snap["role"] == "cop" and snap["action"]:
            last = _describe_cop_action(snap["action"])
        snap["last_cop"] = last
    return snaps


class GuiApp:
    """Window that steps through precomputed snapshots of the series."""

    def __init__(self, config: Config) -> None:
        params = config.game_params()
        self.snaps = _annotate_cop_actions(list(iter_series(config)))
        self.num_games = params.num_games
        self.max_barriers = params.max_barriers
        self.index = 0
        self.playing = False
        self.delay_ms = 650
        self.root = tk.Tk()
        self.root.title("Cop vs Thief — series replay")
        self.root.configure(bg=_BG)
        self.view = BoardView(self.root)
        self.view.canvas.pack(padx=16, pady=(16, 8))
        self.status = self._label(18, "bold")
        self.barriers = self._label(14, "bold")
        self.last_cop = self._label(12, "normal")
        self.message = self._label(13, "normal")
        self.totals = self._label(14, "bold")
        self._build_controls()
        self._show()

    def _label(self, size: int, weight: str) -> tk.Label:
        var = tk.Label(self.root, bg=_BG, fg=_FG, font=("Helvetica", size, weight))
        var.pack(padx=16, anchor="w")
        return var

    def _build_controls(self) -> None:
        bar = tk.Frame(self.root, bg=_BG)
        bar.pack(pady=12)
        self.play_btn = tk.Button(bar, text="▶ Play", width=8, command=self._toggle)
        self.play_btn.pack(side="left", padx=4)
        tk.Button(bar, text="⏮", width=4, command=lambda: self._step(-1)).pack(side="left", padx=4)
        tk.Button(bar, text="⏭", width=4, command=lambda: self._step(1)).pack(side="left", padx=4)
        tk.Button(bar, text="↺ Restart", width=9, command=self._restart).pack(side="left", padx=4)

    def _show(self) -> None:
        snap = self.snaps[self.index]
        self.view.render(snap)
        if snap["result"] != "in_progress":
            tail = f" · {snap['result']} ({snap['reason']})"
        else:
            tail = f" · to move: {snap['to_move']}"
        head = f"Sub-game {snap['sub_game']}/{self.num_games} · move {snap['ply']}"
        self.status.config(text=head + tail)
        self.barriers.config(
            text=f"Cop barriers left: {snap['barriers_remaining']}/{self.max_barriers}"
        )
        self.last_cop.config(text=f"Last cop action: {snap['last_cop']}")
        self.message.config(
            text=f"{(snap['role'] or 'referee')}: {snap['message']}",
            fg=_ROLE_COLOUR.get(snap["role"], _FG),
        )
        totals = snap["totals"]
        self.totals.config(text=f"Totals   cop {totals['cop']}  –  thief {totals['thief']}")

    def _step(self, delta: int) -> None:
        self.index = max(0, min(len(self.snaps) - 1, self.index + delta))
        self._show()

    def _toggle(self) -> None:
        self.playing = not self.playing
        self.play_btn.config(text="⏸ Pause" if self.playing else "▶ Play")
        if self.playing:
            self._tick()

    def _tick(self) -> None:
        if not self.playing:
            return
        if self.index < len(self.snaps) - 1:
            self._step(1)
            self.root.after(self.delay_ms, self._tick)
        else:
            self.playing = False
            self.play_btn.config(text="▶ Play")

    def _restart(self) -> None:
        self.index = 0
        self._show()

    def run(self) -> None:
        """Enter the Tk event loop."""
        self.root.mainloop()


def main() -> int:
    """Launch the GUI (offline heuristic series)."""
    GuiApp(Config.load()).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
