# ARCHITECTURE

Deeper companion to the README's architecture section.

## Module map & responsibilities

| Module | Responsibility | I/O? |
|---|---|---|
| `game/board.py` | `Position`, Chebyshev distance, `Board` (bounds, barriers, neighbours) | none |
| `game/actions.py` | `Role`, `ActionType`, `Action`, `TurnPayload` (shared shape) | none |
| `game/state.py` | `GameState`, `SubGameResult`, `TurnRecord` | none |
| `game/observation.py` | `O`: build the per-agent partial view | none |
| `game/scoring.py` | `R`: `ScoringTable`, `score_subgame`, `accumulate` | none |
| `game/engine.py` | `P`: validate, apply, capture, adjudicate (the referee's rules) | none |
| `game/setup.py` | seeded initial state distribution | none |
| `agents/strategies.py` | offline heuristic policies + legal-target helper | none |
| `agents/messages.py` | natural-language message composition (with bluffing) | none |
| `agents/base_agent.py` | `Agent`: observation → `(message, action)`, LLM + sanitise | none |
| `agents/cop_agent.py` / `thief_agent.py` | role-specific agent factories | none |
| `orchestrator/referee.py` | `SubGameReferee`: the single source of truth | none |
| `orchestrator/runner.py` | series loop, message threading, logging | writes log |
| `orchestrator/llm_client.py` | Anthropic client + `build_llm` | network |
| `orchestrator/prompts.py` | system/user prompts + structured-output schema | none |
| `orchestrator/results.py` | result dataclasses + JSONL writer | writes log |
| `orchestrator/report_builder.py` | internal/bonus reports, write to disk | writes file |
| `orchestrator/gmail_sender.py` | OAuth + Gmail send (JSON-only body) | network |
| `mcp_servers/server_app.py` | FastMCP app factory + tool definitions + auth | network |
| `security/auth.py` / `tokens.py` | bearer verify / token issue | env |
| `config.py` | typed config loader (YAML + env overrides) | file/env |
| `main.py` | CLI: run → report → optional email | stdout |

## Control flow (one turn)

```
runner: role = referee.whose_turn()
runner: obs  = referee.observe(role)
agent : (message, action) = decide(obs, opponent_recent_messages)
          ├─ llm_client.decide(...)  → sanitise against legal_targets
          └─ or heuristic.choose(...) + messenger.compose(...)
runner: record = referee.submit(TurnPayload(..., message, action))
runner: log(record) ; opponent_inbox.append(message)
```

## Why the layering holds

- `game/` imports nothing from `agents/`, `orchestrator/`, or `mcp_servers/`.
- `config.py` depends on `game/` (for `GameParams`/`ScoringTable`), not the
  reverse — game logic never imports upward.
- Heavy/optional deps (`anthropic`, `fastmcp`, `google-*`) are imported **lazily**
  inside the functions that need them, so the core package and the test suite
  import and run without them.

## Failure handling

- Illegal action → engine ends the sub-game in the opponent's favour, recorded
  with a reason (`illegal:<why>`).
- LLM error / malformed action → agent falls back to a safe heuristic move.
- Network/server glitch in a real match → Technical Loss: void and rerun until
  6 clean sub-games (SHARED_MATCH_RULES §4).

## Extensibility points

- New strategy: add a class with `choose(obs, rng) -> Action` and wire it in a
  factory.
- New movement rule: change `direction_offsets` / config, no engine edits.
- Different grid/scoring/vision: edit `config.yaml` only.
- Real inter-team play: run the MCP servers, set tokens, swap roles per the
  bonus rules, and reuse `build_bonus_report`.
