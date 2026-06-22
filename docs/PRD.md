# PRD — Cop vs Thief (HW6)

## 1. Context & goal

Build an autonomous, end-to-end pipeline in which two AI agents (Cop, Thief)
play a partially observable chase, talk in free natural language over two MCP
servers, and produce an emailed JSON report — with no human in the loop. The
deliverable is graded on **orchestration and communication**, not strategy
(assignment §3, §14).

## 2. Users & use cases

- **Student/operator** runs `cop-thief run` and obtains a scored series + report.
- **Grading harness** receives a JSON-only email and parses it.
- **Peer team** (bonus) calls our MCP servers over HTTPS with a bearer token.

## 3. Objectives, KPIs & acceptance criteria

| Objective | KPI / acceptance criterion |
|---|---|
| Correct rules | All engine unit tests pass (movement, barriers, capture, scoring). |
| Partial observability | Opponent/barriers hidden beyond `vision_radius`; tested. |
| Autonomous series | One command runs 6 clean sub-games and writes a report. |
| Two MCP servers | Cop & thief servers start independently, expose tools, require a token. |
| NL + action per turn | Every turn logged with a `message` and a binding `action`. |
| Report schemas | Internal (§9.1) & bonus (§9.2) JSON match the spec keys exactly; tested. |
| Email | Body is JSON-only, sent via Gmail API to the fixed address. |
| Quality | ≤150 lines/file, Ruff-clean, ≥85 % coverage, `uv`-managed. |

## 4. Functional requirements

- Read all parameters from `config.yaml`; never hard-code.
- Generate seeded start positions (distinct, outside vision when possible).
- Validate each action; an illegal action loses the sub-game.
- Score each sub-game and accumulate series totals.
- Build observation views per agent; thread opponent messages between turns.
- Drive agents via an LLM when configured, else a deterministic heuristic.
- Expose `observe` / `submit_turn` / `whose_turn` / `reset` / `health` MCP tools.
- Write a timestamped JSONL log of every turn, sub-game end, and series total.
- Build and (optionally) email the JSON report.

## 5. Non-functional requirements

- Runs offline with no API key (heuristic provider) for tests and demos.
- Reproducible given a fixed seed.
- Secrets out of git; token auth on the MCP boundary; HTTPS for the cloud stage.
- Modular, layered, OOP, DRY; clear logging.

## 6. Out of scope / assumptions

- Strong play / RL training (heuristic + optional LLM only; Q-learning is a
  documented option, not required — assignment §8).
- A polished GUI (the spec lists it as a later stage; CLI + logs are the core).
- The actual inter-team match scheduling (coordinated out of band).

## 7. Constraints & open items

- `PICK TOGETHER` values default to the shared-rules suggestions; team-specific
  values (team names, URLs, tokens, GitHub repo, seed) must be filled per match.

## 8. Timeline / milestones

Follows the assignment's engineering order (§13): rules → MCP infra → local run
→ decision logic → NL integration → (GUI) → cloud deploy → Gmail.
