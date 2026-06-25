"""Local-series CLI handlers + shared helpers (split from ``main`` for the 150-line limit)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .config import Config
from .orchestrator.llm_client import build_llm
from .orchestrator.report_builder import build_internal_report, write_report
from .orchestrator.runner import SeriesRunner


def _load_dotenv(path: str = ".env") -> None:
    """Populate os.environ from a local .env file without overriding existing vars."""
    import os

    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _print_summary(series, totals) -> None:
    for summary in series.sub_games:
        print(
            f"  sub-game {summary.sub_game}: {summary.result:<9} "
            f"({summary.reason}) in {summary.moves} moves -> {summary.score}"
        )
    print(f"Totals: cop={totals['cop']} thief={totals['thief']}")


def _write_half(config, group: str, series) -> Path:
    """Persist our authoritative half (self-describing) for the §9.2 merge step."""
    out_dir = Path(config.report["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"peer_half_group{group}_{stamp}.json"
    team = config.team
    half = {
        "group_name": team["group_name"],
        "role": "cop",
        "group": group,
        "github_repo": team["github_repo"],
        "students": list(team.get("students", [])),
        "cop_mcp_url": team["cop_mcp_url"],
        "thief_mcp_url": team["thief_mcp_url"],
        "timezone": team["timezone"],
        "sub_games": [
            {
                "sub_game": s.sub_game, "result": s.result, "reason": s.reason,
                "moves": s.moves, "score": s.score, "start": s.start, "barriers": s.barriers,
            }
            for s in series.sub_games
        ],
        "totals": series.totals,
    }
    path.write_text(json.dumps(half, indent=2), encoding="utf-8")
    return path


def _run_peer_check(args) -> int:
    """Probe a peer team's MCP server (reachability + tool list)."""
    from .orchestrator.peer_check import peer_check

    result = peer_check(args.url, args.token)
    print(json.dumps(result, indent=2))
    return 0 if result.get("reachable") else 1


def _run_series(args) -> int:
    """Play the local 6-sub-game series (in-process or through the MCP servers)."""
    config = Config.load(args.config)
    if args.provider:
        config.raw["llm"]["provider"] = args.provider
    llm = build_llm(config.llm)
    if args.mcp:
        from .orchestrator.mcp_series import MCPSeriesRunner

        print(
            f"Driving the series via MCP servers: cop={config.mcp_url('cop')} "
            f"thief={config.mcp_url('thief')}"
        )
        series = MCPSeriesRunner(config, llm=llm, log=not args.no_log).run()
    else:
        series = SeriesRunner(config, llm=llm, log=not args.no_log).run()
    report = build_internal_report(series, config)
    path = write_report(report, config.report["output_dir"])
    _print_summary(series, series.totals)
    print(f"Report written to {path}")
    if args.email:
        from .orchestrator.gmail_sender import send_report_from_env

        message_id = send_report_from_env(report, config.report["recipient"])
        print(f"Report emailed (message id {message_id})")
    return 0
