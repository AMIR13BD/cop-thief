# SHARED_MATCH_RULES

The single, canonical statement of the match rules both engines must agree on.
Code and `config/config.yaml` cite this document by section so the implementation
and the contract never drift. It is written to match **this repository's
implementation exactly** (see `game/` and `orchestrator/`).

> Scope note. The **local section** (the completed work) runs both agents inside
> one repository against these rules. The **bonus inter-team match** reuses the
> same rules as the contract between two teams' engines; that stage is **deferred
> / not yet completed** (see `docs/TODO.md`). Nothing here depends on the cloud or
> on Gmail being wired up.

---

## §1 — Outcome, scoring, and the message channel

- A **sub-game** ends in exactly one of two ways: the cop captures the thief
  (`cop_win`), or the thief completes `max_moves` moves uncaught (`thief_win`).
- **Per-sub-game score** (`game/scoring.py`):

  | Result | Cop | Thief |
  |---|---|---|
  | Cop wins (capture) | `cop_win` = 20 | `thief_loss` = 5 |
  | Thief wins (escape) | `cop_loss` = 5 | `thief_win` = 10 |

- Every turn an agent emits a **natural-language message** alongside its action.
  The message is free text and **may be honest or a bluff**; it is the only thing
  an agent reveals beyond its move. The referee **never reads the message** — the
  outcome is decided solely by the structured `action` (`agents/messages.py`).

## §2 — Game rules

### §2.1 — Referee & authoritative state
There is exactly **one referee** that owns the authoritative `GameState`; both
sides read state only through it, so two engines can never disagree
(`orchestrator/referee.py`). For an internal game this repository's engine is
always the referee. In the bonus match the **cop's team engine is the referee**
for the three sub-games in which it plays cop (`config.yaml → referee.owner`).

### §2.2 — Turn payload
Each turn is the shared shape (`game/actions.py`):

```json
{ "sub_game": 1, "move_number": 7, "role": "thief",
  "message": "free natural-language text (may bluff)",
  "action": { "type": "move|barrier", "to": [row, col] } }
```

The `action` binds; the `message` does not.

### §2.3 — Coordinate system
The grid is `R×C` (default `5×5`, from config). Origin `[0, 0]` is the
**top-left**; addressing is `[row, col]` with rows increasing downward and
columns rightward (`game/board.py`).

### §2.4 — Start positions & barriers
- **Start positions** are drawn from a seeded RNG so a match is reproducible
  (`match.seed`). The cop and thief never share a cell and, when the grid allows,
  start **beyond each other's vision radius** (`game/setup.py`).
- **Movement** is one cell per turn, 8-directional (king moves; `4`-directional is
  a config switch). Stepping into a barrier or off the board is illegal and loses
  the sub-game.
- **Barriers (cop-only).** As an alternative to moving, the cop may place a
  barrier on an **adjacent empty cell** — one of the 8 neighbours that is on the
  grid, **not** the cop's own cell, **not** the thief's cell, and not already a
  barrier. The cop **does not move** that turn (placement consumes the turn). The
  cell becomes **impassable for both** agents and persists for the rest of the
  sub-game (barriers reset between sub-games). The cop may place at most
  `max_barriers` (default 5) per sub-game; the thief can never place a barrier. If
  no valid adjacent cell exists, the place-barrier action is unavailable that turn.

  > **Deviation from assignment §4.3, lecturer-confirmed.** The assignment text
  > places the barrier on the cop's **own current cell**. This project instead
  > uses the **adjacent empty cell** rule above, which the lecturer confirmed, so
  > the barrier is a usable tool for cutting the thief's escape lanes. Validation:
  > `game/engine.py::_validate_barrier`.

### §2.5 — Timing
Each turn has a budget of `turn.timeout_seconds` (default 30). On timeout the
mover is re-prompted once and then concedes the sub-game
(`turn.reprompt_on_timeout`).

### §2.8 — Move counting
`move_number` counts **completed thief moves**. The thief moves first each round;
after the thief moves, the cop gets one reply (its last chance to capture). The
thief wins the moment it finishes its `max_moves`-th move uncaught
(`game/state.py`, `game/engine.py`).

### §2.9 — Partial observability
Each agent always knows its own cell but sees the opponent and a barrier **only
within `vision_radius`** (Chebyshev distance). Outside that radius it gets no
ground truth and must reason from the opponent's (possibly bluffed) messages
(`game/observation.py`). This is the Dec-POMDP observation function `O`.

## §3 — Logging, rate-limit, and retries
- Every validated turn — message, action, validation result, positions, barriers,
  and result — is appended to a timestamped JSONL log for joint debugging and as
  evidence (`orchestrator/results.py`).
- Outbound calls per direction are capped at `match.rate_limit_per_min` (default
  30) to stay friendly to a peer team's gateway.
- A transient transport error is retried up to `match.max_retries` (default 3)
  before the turn is declared a **Technical Loss** (see §4).

## §4 — Series structure & Technical Loss
A full series is `num_games` sub-games (default 6). If a sub-game cannot complete
cleanly because of a transport/network failure, it is marked a **Technical Loss**,
**voided, and re-run** until the series reaches the required number of *clean*
sub-games. Series totals are the cumulative cop-side and thief-side scores over
those clean sub-games.
