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

## Verify
Health-check (expect non-401 with token, 401 without):
```
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -d '{}' <url>
```
