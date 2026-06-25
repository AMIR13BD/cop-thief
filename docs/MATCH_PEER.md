# Inter-group match — opponent team & reconciliation status

Live working notes for the §12 bonus match. Bearer tokens are **not** here — they
live only in `.env` (git-ignored). See also `docs/MATCH_PROTOCOL.md` (our v0.1
proposal) and `docs/SHARED_MATCH_RULES.md`.

## Opponent team — `ahk-yosi` (group_1)
- Members: yosef shanaa (213314859), ahmad kaiss (325811255)
- Repo: https://github.com/yosefshanaa/HW6
- Cop server:   `https://cop-thief-cop-1035205205472.me-west1.run.app/mcp`
- Thief server: `https://cop-thief-thief-1035205205472.me-west1.run.app/mcp`
- Per-server bearer tokens (cop / thief): in `.env` as `PEER_COP_TOKEN` / `PEER_THIEF_TOKEN`.
- Note: use the URL **without** a trailing slash (`/mcp`, not `/mcp/`) — a trailing
  slash 307-redirects and drops the auth header.

## Us — `amireman` (group_2)
- Cop server:   `https://cop-thief-cop-wail7kwomq-zf.a.run.app/mcp`
- Thief server: `https://cop-thief-thief-wail7kwomq-zf.a.run.app/mcp`
- Single bearer token for both servers (`MCP_AUTH_TOKEN` in `.env` / deploy env).

## Role split (assignment §12.1, confirmed by both)
- Sub-games **1–3**: group_1 (ahk-yosi) **Cop** vs group_2 (us) **Thief** → they referee.
- Sub-games **4–6**: group_2 (us) **Cop** vs group_1 (ahk-yosi) **Thief** → we referee.

## Rules — agreement vs ours
Matches our engine: 5×5, vision radius 2 (Chebyshev), 6 sub-games, thief moves
first, 25 thief moves, scoring cop_win 20 / thief_win 10 / loss 5, capture = land
on the other's cell, illegal/off-board/no-action = forfeit.

**To confirm with them:**
- **Barrier placement model.** We use the lecturer-confirmed deviation: the cop
  drops a barrier on one of the 8 **adjacent empty cells** (not an arbitrary cell);
  it is impassable for both; ≤5 per sub-game. Their spec only says "cop ≤5
  barriers" — must confirm identical placement legality or validation will diverge.
- **Start positions.** They derive both sides identically via
  `random.Random(f"{seed}:{index}")` + uniform distinct pair with Chebyshev
  distance > vision radius, **seed = 1234**. Our generator differs — for their
  two-synced-referee model we must adopt their exact algorithm + seed.

## Protocol mismatch — MUST reconcile before play
Their orchestration (their §4) and tool contract differ fundamentally from ours.

| | **Them (group_1)** | **Us (group_2)** |
|---|---|---|
| Model | Two synced referees; both drivers run; every move submitted to both servers; lockstep on turn | Single referee per sub-game (cop team); referee pulls opponent's move via one tool |
| Where state lives | In the role-bound **server** (server = referee) | In the **orchestrator** (server = relay) |
| Start positions | Both derive identically from shared seed | Cop-side referee generates; other side need not reproduce |
| Tools | `health_check, get_observation, validate_action, submit_turn, receive_message, get_match_status, reset(cop,thief), get_messages` | `health, observe, set_context, submit_turn, last_message, verify_location, play_turn` |

This is the **spec-literal Option 2** (our `MATCH_PROTOCOL.md` §H) vs our
**Option 1** (§D). The two do not interoperate without one side conforming.

**Open decision:** which contract do we play on? Leaning toward adopting theirs
(it is fully specified and already implemented), which means: make our servers
stateful referees exposing their 8 tools + `reset`, implement their start-position
algorithm (seed 1234), and write a lockstep driver. Pending: their exact
tool signatures (`get_observation` params, `submit_turn`/`validate_action`
payloads, `reset` signature, `get_match_status` shape) and barrier confirmation.

## Per-sub-game sequencing & reset handoff (REQUIRED — this is what stalled SG1→SG2)

The match is 6 sub-games played **in order** over the same four servers. The
single most important agreement, and the one that broke our first live run, is
**who resets which server between sub-games**. Rules:

1. **Each team resets only the server it OWNS.** Nobody resets the opponent's server.
2. **The cop side is authoritative for the start cells** that sub-game. At the
   start of sub-game *i* the cop side calls `reset(cop, thief)` on **its own cop
   server** to that sub-game's start (so `get_match_status` → `thief_moves: 0`).
3. **The thief side adopts the cop side's start.** It polls the cop server until
   `thief_moves == 0`, reads `cop`/`thief`, and `reset`s **its own thief server**
   to those exact cells. (No shared seed needed — the thief mirrors whatever the
   cop side chose.)
4. **Every turn, each team submits its own role's move to BOTH servers** (its own
   + the opponent's) so authoritative and mirror stay in sync.
5. **A sub-game ends** when both servers report a terminal `status`
   (`cop_win`/`thief_win`). Then **advance to the next index and GOTO step 2** —
   the cop side resets again for the new sub-game.

Role split: group_1 (ahk-yosi) is cop for 1–3, group_2 (us) is cop for 4–6. So
group_1 resets its cop server at the top of sub-games 1, 2, 3; group_2 resets its
cop server at the top of 4, 5, 6. The thief side resets its own thief server each
time after adopting the cop side's start.

Our driver implements exactly this in `orchestrator/match_driver.py`:
`_run` loops `index` 1..6 → `_play_subgame` → for sub-games we referee we
`reset` our cop server + `_await_start` the opponent's thief mirror; for sub-games
they referee we `_adopt_start` (read their cop server's fresh reset) + `reset` our
thief mirror; then a turn loop dual-submits via `_take_our_turn`.

**What we observed live (2026-06-25):** SG1 played end-to-end and ended `cop_win`
(their cop captured our thief) — authoritative (their cop) and mirror (our thief)
agreed. Then it stalled: **their cop server stayed frozen at the SG1 `cop_win`
result and was never reset for SG2**, so our thief driver waited forever for a
clean `thief_moves: 0`. Their networked driver must **loop all 6 sub-games and
re-`reset` its cop server at the top of each one** (step 2/5 above), not play a
single sub-game and stop.

**Repo note (their public repo, checked 2026-06-25):** `cop-thief-match` there is
the **loopback** `LocalMatch` (both teams in-process, local referees — not the
networked driver), and `mcp/server_app.py` exposes only **6 tools with no
`reset`** (self-resets once at boot to a random seeded start). Their *deployed*
servers clearly have more (we saw `reset` to our agreed cells + both roles
moving), so **their real code is newer than what's pushed** — they should push the
networked driver + the reset-capable 8-tool server they actually run.

## Verify
Health-check (expect non-401 with token, 401 without):
```
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -d '{}' <url>
```
