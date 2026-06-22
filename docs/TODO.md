# TODO — Task tracking

Status: ✅ done · 🔜 next · ⬜ not started. Order follows assignment §13.

## Phase 1 — Game logic & rules ✅
- ✅ Board geometry, positions, distance (`game/board.py`) — *DoD: bounds/barriers tested.*
- ✅ Actions, roles, turn payload (`game/actions.py`).
- ✅ State + terminal results (`game/state.py`).
- ✅ Engine: validation, capture, turn order, scoring hooks (`game/engine.py`).
- ✅ Partial observation (`game/observation.py`), scoring (`game/scoring.py`).
- ✅ Seeded start positions (`game/setup.py`).
- ✅ Tests: movement, barriers, capture, scoring, observation, illegal actions.

## Phase 2 — MCP communication infrastructure ✅
- ✅ FastMCP app factory + cop/thief server entrypoints (`mcp_servers/`).
- ✅ Token issuing & bearer verification (`security/`).
- ✅ `observe` / `submit_turn` / `whose_turn` / `reset` / `health` tools.

## Phase 3 — Full local run ✅
- ✅ Referee (single source of truth) (`orchestrator/referee.py`).
- ✅ Series runner, message threading, JSONL logging (`orchestrator/runner.py`).
- ✅ CLI entrypoint (`main.py`).

## Phase 4 — Decision mechanism ✅
- ✅ Heuristic cop/thief strategies (`agents/strategies.py`).
- ✅ Agent with LLM delegation + action sanitisation (`agents/base_agent.py`).
- ⬜ Optional: tabular Q-learning baseline (assignment §8) — *not required.*

## Phase 5 — Natural-language integration ✅
- ✅ Bluffing message composer (`agents/messages.py`).
- ✅ LLM client + prompts + structured output (`orchestrator/llm_client.py`, `prompts.py`).

## Phase 6 — GUI ✅
- ✅ Tkinter board replay (`gui/`): animates agent/barrier movement, score, and the
  per-turn natural-language messages. Run `cop-thief-gui`. *DoD: renders the series
  with play/step/restart controls — met.*

## Phase 7 — Cloud deployment 🔜
- ⬜ Front each server with TLS (ngrok / Localtonet / Nginx); exchange HTTPS URLs
  and tokens out of band — *DoD: peer reaches `health()` over HTTPS with a token.*

## Phase 8 — Gmail reporting ✅
- ✅ Internal & bonus report builders (`orchestrator/report_builder.py`).
- ✅ Gmail API sender, body = JSON only (`orchestrator/gmail_sender.py`).
- 🔜 One-time: create OAuth Desktop client, add test user, drop `credentials.json`.

## Cross-cutting ✅
- ✅ Config-driven, no hard-coding; `.env.example`; secrets git-ignored.
- ✅ Ruff-clean; ≤150 lines/file; ≥85 % coverage; `uv.lock`.
- ✅ README with Dec-POMDP, architecture, run/test/security docs.

## Per-match (fill before the graded run)
- ⬜ Team names, students, GitHub repo, MCP URLs, shared seed, tokens.
- ⬜ Agree the final JSON with the peer team; both email with `mutual_agreement:true`.
