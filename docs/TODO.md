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

## Phase 7 — Cloud deployment ✅
- ✅ Both MCP servers deployed on **Google Cloud Run** over HTTPS with bearer-token
  auth (`deploy/cloudrun.sh`, `mcp_servers/cloud_entry.py`) — *DoD met: the peer
  team reached `health_check` over HTTPS with a token.*

## Phase 8 — Reporting ✅
- ✅ Internal & bonus report builders; JSON report **written to `results/reports/`**
  (`orchestrator/report_builder.py`, `orchestrator/bonus_report.py`).
- ✅ Gmail send (body = JSON only) wired (`orchestrator/gmail_sender.py`); used via
  `cop-thief run --email` and **automatically at the end of `cop-thief match`**.
  Needs the one-time OAuth Desktop client + `credentials.json`/`token.json` (git-ignored).

## Cross-cutting ✅
- ✅ Config-driven, no hard-coding; `.env.example`; secrets git-ignored.
- ✅ Ruff-clean; ≤150 lines/file; ≥85 % coverage; `uv.lock`.
- ✅ README with Dec-POMDP, architecture, run/test/security docs.

## Phase 9 — Inter-group bonus match ✅ (vs ahk-yosi)
- ✅ Stateful two-referee match server (opponent's 8-tool contract) + lockstep driver
  (`mcp_servers/match_server.py`, `orchestrator/match_driver.py`); contract + handshake
  in `docs/MATCH_PEER.md`.
- ✅ Team identity filled in `config/config.yaml` (group_name, students, repo, cloud
  MCP URLs, seed); per-server tokens in `.env` (git-ignored).
- ✅ Played the live 6-sub-game match vs **ahk-yosi**, agreed the byte-identical §9.2
  `bonus_game` JSON (`mutual_agreement: true`), and both teams emailed it. Final:
  **ahk-yosi 80 / amireman 60** (series winner ahk-yosi; bonus claim 10/7). Evidence:
  `assets/bonus_report.json`.

## Optional / not required
- ⬜ Tabular Q-learning baseline (assignment §8) — explicitly optional, not implemented.
