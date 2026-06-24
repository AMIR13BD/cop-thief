# MATCH_PROTOCOL — inter-group online match wire contract (PROPOSAL v0.1)

> Status: **DRAFT to agree with the opponent team.** The assignment fixes the
> *game* rules (`SHARED_MATCH_RULES.md`, §2.2 turn payload) but **not** the
> cross-team MCP tool API (§5 describes the local two-server model only). This
> document proposes that missing API so two teams' engines can play the §12
> bonus series. Both teams must implement the **same** tools/shapes. Cite this
> file by section in code and in the post-match report.

---

## §A — Transport, identity, auth

- **Transport:** MCP over **streamable-HTTP** (FastMCP). Local dev: `http://`.
  Cloud match: **HTTPS only** (assignment §6/§7 — tunnel or reverse proxy).
- **Endpoints:** each team publishes **two** URLs — a **cop** server and a
  **thief** server (assignment §5.1, §6). Mount path `/mcp` (configurable).
- **Auth (§6/§7):** every state-changing tool requires
  `Authorization: Bearer <token>`. Tokens are high-entropy, **revocable**, and
  exchanged **out of band** (never in git). `health` is unauthenticated.
  A bad/missing token → the call fails (treated as 401). Each team sets the token
  its own servers demand (`MCP_AUTH_TOKEN`) and the token it sends to the peer
  (`MCP_PEER_TOKEN`).
- **Versioning:** `health()` returns `protocol` = this file's version so a
  mismatch is caught before kickoff.

## §B — Game rules (by reference)

All of `SHARED_MATCH_RULES.md` applies verbatim: 5×5 grid, `[row,col]` origin
top-left, 8-directional king moves, **barrier = adjacent empty cell** (cop-only,
≤5/sub-game, lecturer-confirmed deviation), `vision_radius` 2 (Chebyshev),
`max_moves` 25, scoring cop_win=20 / thief_win=10 / losses=5. The **action binds,
the message does not**; the referee never reads the message.

## §C — Match structure (§12.1) & referee (§2.1)

- A series is **6 sub-games**. Assign the two teams as **Group 1** and
  **Group 2** (agree which is which out of band):
  - **Sub-games 1–3:** Group 1 **cop** vs Group 2 **thief**.
  - **Sub-games 4–6:** Group 2 **cop** vs Group 1 **thief**.
- **Exactly one referee per sub-game = the cop's team** (§2.1). The referee owns
  the authoritative `GameState`, generates that sub-game's start positions
  (seeded), validates every action, and decides the result. The other team never
  needs to reproduce the referee's RNG (this avoids the cross-engine
  reproducibility trap — different codebases ≠ same RNG stream).

## §D — Tool contract — **Option 1 (RECOMMENDED): referee-driven**

The refereeing (cop) team's orchestrator **drives** its three sub-games. On the
thief's turn it asks the opponent's **thief** server for that team's move; on its
own (cop) turn it decides locally and applies it. Symmetric for the swapped half.

Each team's **agent server** (cop and thief) exposes:

```
health() -> { "status": "ok", "role": "cop|thief", "protocol": "0.1" }     # no auth

play_turn(observation: object, opponent_message: string = "")              # auth
    -> { "message": string,                  # free NL (may bluff)
         "action": { "type": "move|barrier", "to": [row, col] } }

verify_location(claim: [row, col]) -> { "claim":[r,c], "match": bool }      # auth, §5.1
```

- `play_turn` is the heart of the match: given the **observation the referee
  computed for this agent** (shape in §E) plus the opponent's last NL line, the
  server returns **its own team's** chosen message + action. The team's LLM/
  heuristic runs **inside that team's own stack** — the referee never executes
  the opponent's model, so §5.2 ("LLM lives in the client, not in the relay
  the *other* side calls") is honored in spirit. `to` is `[row,col]`; for a
  `barrier` it is the adjacent cell to block.
- The referee re-validates every returned `action` against authoritative state;
  an illegal/garbled action follows the local rules (re-prompt once, then the
  mover concedes the sub-game — §2.5).

### Per-turn flow (referee side, one sub-game where we are cop)
1. Referee builds the thief's partial observation from authoritative state.
2. Referee → opponent **thief** server: `play_turn(obs_thief, our_last_msg)`.
3. Referee validates + applies the thief action; checks capture/terminal.
4. If not over, referee decides its **cop** move locally, applies it.
5. (Optional §5.1) either side may `verify_location` the other's claimed cell.
6. Loop until capture or `max_moves`; record the sub-game.

## §E — Observation shape (what the referee sends to `play_turn`)

Exactly the engine's `build_observation` output:

```json
{ "role": "thief", "sub_game": 1, "move_number": 7, "max_moves": 25,
  "grid_size": [5,5], "vision_radius": 2,
  "self": [r,c], "opponent": [r,c]|null, "opponent_visible": true|false,
  "visible_barriers": [[r,c], ...], "barriers_remaining": 0 }
```

`opponent` is `null` when out of vision (the agent must then reason from the NL
message). `barriers_remaining` is 0 for the thief.

## §F — Errors, timeouts, Technical Loss (§3/§4)

- Per-turn budget **30 s**; on timeout the mover is re-prompted **once**, then
  concedes the sub-game.
- A transient transport error is retried up to **3×**; exhaustion marks the
  sub-game a **Technical Loss → void & re-run** from the same start until 6 clean
  sub-games complete. Rate-limit outbound calls to **30/min** per direction.

## §G — Result exchange & matched report (§9.2)

Each half has a single referee, so:
1. Each team referees its 3 cop sub-games and produces authoritative records:
   `{ sub_game, result, reason, moves, score, start:{cop,thief}, barriers }`.
2. The two halves are exchanged out of band and concatenated **in sub-game
   order (1..6)**.
3. Both teams compute `totals_by_group` and `bonus_claim` (higher→10, lower→7,
   tie→5) and build the **§9.2 `bonus_game` JSON** (both group names, both
   `github_repo_*`, all four `mcp_url_group_*_{cop,thief}`, timezone, both
   student lists, `sub_games`, `totals_by_group`, `bonus_claim`).
4. Both **independently** verify the assembled JSON is byte-identical, set
   `mutual_agreement: true`, and email it (body = JSON only). **Any mismatch
   voids the bonus → 0 for both** (§12.2).

## §H — Alternative — Option 2 (spec-literal lockstep relay)

Faithful to §5.2's thin-mailbox model: **both** orchestrators run; the thin tools
are `set_context / observe / submit_turn / last_message / verify_location`; each
team posts its own agent's move to its own server and reads the opponent's from
theirs, alternating in lockstep. Rejected as the default: it needs a distributed
turn-sequencer and authoritative-state distribution across two independently-run
programs — much higher failure surface for no scoring benefit. Kept here as the
fallback if the opponent team's server already exposes only these tools.

---

### Open items to confirm with the opponent team
- [ ] Which team is **Group 1** vs **Group 2** (sets the cop/thief halves).
- [ ] **Option 1** (recommended) vs **Option 2** for the tool contract.
- [ ] Two HTTPS URLs each + bearer tokens (out of band).
- [ ] Protocol version string + a `health()` handshake before kickoff.
- [ ] Out-of-band channel + format for exchanging the 3-sub-game result halves.
