# PROMPTS — LLM agent design

When `llm.provider: anthropic`, the orchestrator drives each agent with Claude
via the Anthropic SDK. The LLM lives in the **client** (assignment §5.2); the MCP
servers never call it.

## Model & parameters

- **Model:** `llm.model` in `config.yaml` (default `claude-opus-4-8`; overridable
  via `COP_THIEF_LLM_MODEL`). Haiku is a cheaper option for this short-token
  workload.
- **Structured outputs:** every call uses `output_config.format` with
  `ACTION_SCHEMA`, guaranteeing a parseable `{message, action}` and avoiding
  assistant prefill (removed on Opus 4.7/4.8).
- **Sampling:** `temperature` is sent only to models that accept it (Haiku/Sonnet),
  never to Opus 4.7/4.8/Fable (they reject sampling params).
- **No thinking config** is sent — turns are tiny, so adaptive thinking is left at
  its default to keep latency and cost low.

## System prompt (per role)

Built by `build_system_prompt(role)` in `orchestrator/prompts.py`:

- **Objective** — cop: *win by moving onto the thief; may drop a barrier on an
  adjacent empty cell instead of moving.* thief: *survive every move; you cannot
  place barriers; use your message to mislead.*
- **Common rules** — `[row,col]` origin top-left; 8-directional adjacency; stay on
  board; never enter a barrier; you see opponent/barriers only within your vision
  radius and otherwise reason from (possibly bluffed) messages; *the outcome is
  decided by your action, not your message.*
- **Output contract** — "Reply only with the JSON object."

## User prompt (per turn)

Built by `build_user_prompt(observation, inbox)`:

- the agent's **legal observation** (JSON);
- the opponent's **recent messages** (may be bluffs);
- an instruction to choose one legal action and a short message.

## Output schema (`ACTION_SCHEMA`)

```json
{ "message": "string",
  "action": { "type": "move|barrier", "to": [row, col] } }
```

## Safety / robustness

The agent **sanitises** the returned action (`agents/base_agent.py`): a move must
be in the legal-target set; a barrier must land on an **adjacent empty cell**
(one of the 8 neighbours, not the cop's own cell, not the thief's, not an existing
barrier) with budget remaining. Anything else (or any SDK/network error) falls
back to the deterministic heuristic, so a bad reply never forfeits a sub-game.

## Prompt-engineering notes

- Keep messages well-formed so neither server trips on a bad payload
  (SHARED_MATCH_RULES §3).
- Bluffing belongs in `message`, never in `action`.
- Because the prompt only ever contains the agent's **legal** view, the model
  cannot "cheat" by seeing the hidden opponent — partial observability is enforced
  upstream of the LLM.
