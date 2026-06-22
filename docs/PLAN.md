# PLAN — Architecture & Design

## C4 (Context → Container → Component)

**Context.** A student/operator triggers a series; the system plays it
autonomously and emails a JSON report to the course address. A peer team may
call the MCP servers during the bonus match.

**Containers.**
- *Orchestrator (CLI process)* — the MCP client: LLM, runner, referee, report,
  email.
- *Cop MCP server* and *Thief MCP server* — FastMCP HTTP services exposing tools.
- *Anthropic API* — external LLM (optional).
- *Gmail API* — external mail delivery.

**Components** (within the orchestrator): `runner`, `referee`, `llm_client`,
`report_builder`, `gmail_sender`, plus the `game` core and `agents`.

## Layered design (per software guidelines §4)

```
Entrypoints (CLI main.py, MCP server mains)
        │   thin; no business logic
Orchestration (orchestrator/)  ── owns the referee, LLM, logging, reporting
        │
Domain core (game/)            ── rules, state, observation, scoring  (pure)
        │
Infrastructure (security/, gmail_sender, llm_client)  ── auth, mail, API
```

The domain core has no I/O and is 100 % unit-tested. Higher layers depend
downward only.

## Key design decisions (ADRs)

1. **Single referee owns state** (SHARED_MATCH_RULES §2.1). *Why:* two engines
   must never disagree. *Alternative:* per-agent state mirrors — rejected as
   error-prone.
2. **LLM in the client, not the server** (assignment §5.2). *Why:* the spec's
   core architectural point; keeps servers key-free and the boundary thin.
3. **Heuristic fallback + action sanitisation.** *Why:* the pipeline must run
   offline and never forfeit a game on a malformed LLM reply. *Trade-off:* a
   sanitised action diverges from the model's literal output (logged as such).
4. **Structured outputs for the LLM** (`output_config.format`). *Why:* guarantees
   a parseable `{message, action}`; avoids prefill (removed on Opus 4.7/4.8).
5. **In-process series for the internal game; MCP tools for inter-team.** *Why:*
   determinism and speed locally; the same operations are exposed for the cloud.
6. **`StrEnum` roles/results, frozen `Position`.** *Why:* JSON-friendly,
   hashable, immutable state.

## Transition function (P) — turn flow

```
thief.move ─▶ capture? ─yes▶ COP_WIN
            └─no▶ move_number++ ; cop replies
cop.move/barrier ─▶ capture? ─yes▶ COP_WIN
            └─no▶ move_number ≥ max? ─yes▶ THIEF_WIN  └─no▶ thief's turn
illegal action by X ─▶ win_for(opponent of X)
```

## Data contracts

- **Turn payload** — shared shape (`{sub_game, move_number, role, message,
  action:{type,to}}`).
- **Observation** — `{role, self, opponent|null, opponent_visible,
  visible_barriers, barriers_remaining, grid_size, move_number, …}`.
- **Reports** — see `docs/REPORT_SCHEMA.md`.

## Risks & mitigations

- *LLM latency/failure* → heuristic fallback + retries/timeout config.
- *Inter-team disagreement* → shared rules + identical JSON before emailing.
- *Server/network glitch* → Technical Loss: void & rerun until 6 clean sub-games.
