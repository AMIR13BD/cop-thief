# REPORT_SCHEMA

Two report shapes, emitted exactly as the assignment shows so the grading
harness can parse them. The email **body is the JSON only** (assignment §9).

## Sub-game summary (shared element)

Each entry of `sub_games` is produced from a `SubGameSummary`:

```json
{
  "sub_game": 1,
  "result": "cop_win",            // or "thief_win"
  "reason": "capture",            // "capture" | "survived" | "illegal:<why>"
  "moves": 4,                      // completed thief moves
  "score": { "cop": 20, "thief": 5 },
  "start": { "cop": [4, 0], "thief": [0, 3] },
  "barriers": [[2, 2]]            // barrier cells placed during the sub-game
}
```

## Internal game report (§9.1)

For a team that ran both agents itself. Built by `build_internal_report`.

```json
{
  "group_name": "Team-Alpha",
  "students": [],
  "github_repo": "https://github.com/.../cop-thief",
  "cop_mcp_url": "https://cop-...",
  "thief_mcp_url": "https://thief-...",
  "timezone": "Asia/Jerusalem",
  "sub_games": [ /* summaries */ ],
  "totals": { "cop": 120, "thief": 30 }
}
```

`totals` are the cumulative cop-side and thief-side scores over the series
(max 90, min 30 for one team).

## Inter-group bonus report (§9.2)

Sent by **both** teams, identical in the agreed fields. Built by
`build_bonus_report`; `bonus_claim` is computed by `compute_bonus_claim`.

```json
{
  "report_type": "bonus_game",
  "groups": { "group_1": "Team-A", "group_2": "Team-B" },
  "github_repo_group_1": "https://github.com/.../a",
  "github_repo_group_2": "https://github.com/.../b",
  "mcp_url_group_1_cop": "https://a-cop...",
  "mcp_url_group_1_thief": "https://a-thief...",
  "mcp_url_group_2_cop": "https://b-cop...",
  "mcp_url_group_2_thief": "https://b-thief...",
  "timezone": "Asia/Jerusalem",
  "students_group_1": [],
  "students_group_2": [],
  "sub_games": [ /* the 6 agreed summaries */ ],
  "totals_by_group": { "Team-A": 60, "Team-B": 80 },
  "bonus_claim": { "Team-A": 7, "Team-B": 10 },
  "mutual_agreement": true
}
```

### Bonus-claim rule

Higher series total → **10**, lower → **7**, exact tie → **5 each**. The final
bonus is the average over all valid series. A mismatch between the two teams'
reports, or a missing `mutual_agreement: true`, voids the bonus (0 for both).

## Role split (bonus match)

- Sub-games **1–3:** Team A cop vs Team B thief.
- Sub-games **4–6:** Team B cop vs Team A thief.

The cop's team engine is the referee for its three sub-games
(SHARED_MATCH_RULES §2.1).
