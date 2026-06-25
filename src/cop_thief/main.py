"""Command-line entrypoint: run the full series, write the report, optionally email.

Examples::

    cop-thief run                      # play 6 sub-games, write JSON report
    cop-thief run --provider anthropic # drive agents with Claude (needs ANTHROPIC_API_KEY)
    cop-thief run --email              # also send the report via the Gmail API
"""

from __future__ import annotations

import argparse
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


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cop-thief", description="Cop-vs-Thief MCP game runner")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="play the series and build the report")
    run.add_argument("--config", default=None, help="path to config.yaml")
    run.add_argument("--provider", choices=["heuristic", "anthropic"], help="override llm.provider")
    run.add_argument("--no-log", action="store_true", help="do not write the JSONL turn log")
    run.add_argument(
        "--mcp",
        action="store_true",
        help="drive the series THROUGH the two running MCP servers (start them first)",
    )
    run.add_argument("--email", action="store_true", help="email the report via the Gmail API")
    pc = sub.add_parser("peer-check", help="probe a peer team's MCP server (reachability + tools)")
    pc.add_argument("url", help="peer MCP server URL (e.g. https://thief-mcp-beta.example.run/mcp)")
    pc.add_argument("--token", default=None, help="bearer token (default: $MCP_PEER_TOKEN)")
    pm = sub.add_parser(
        "peer-match", help="referee our cop half of an inter-group match (MATCH_PROTOCOL §D)"
    )
    pm.add_argument("peer_thief_url", help="opponent thief server URL we pull moves from")
    pm.add_argument("--token", default=None, help="bearer token to send (default: $MCP_PEER_TOKEN)")
    pm.add_argument("--config", default=None, help="path to config.yaml")
    pm.add_argument("--provider", choices=["heuristic", "anthropic"], help="override llm.provider")
    pm.add_argument(
        "--group",
        choices=["1", "2"],
        default="1",
        help="which group we are: 1 -> sub-games 1-3, 2 -> sub-games 4-6 (default 1)",
    )
    pm.add_argument("--num-games", type=int, default=3, help="sub-games in our half (default 3)")
    pm.add_argument("--no-log", action="store_true", help="do not write the JSONL turn log")
    pr = sub.add_parser(
        "peer-report", help="merge two match halves into the §9.2 bonus_game report"
    )
    pr.add_argument("half_a", help="path to one peer_half_*.json (group 1 or 2)")
    pr.add_argument("half_b", help="path to the other peer_half_*.json")
    pr.add_argument("--config", default=None, help="path to config.yaml (for output_dir)")
    mt = sub.add_parser(
        "match", help="drive our side of the inter-group lockstep match (docs/MATCH_PEER.md)"
    )
    mt.add_argument("--config", default=None, help="path to config.yaml")
    mt.add_argument(
        "--provider", choices=["heuristic", "anthropic", "openai"], help="override llm.provider"
    )
    mt.add_argument("--no-log", action="store_true", help="do not write the JSONL turn log")
    mt.add_argument(
        "--no-email", action="store_true",
        help="do not auto-email the result summary (Gmail API) when the match ends",
    )
    mt.add_argument(
        "--poll-interval", type=float, default=1.0, help="status poll seconds (default 1.0)"
    )
    return parser.parse_args(argv)


def _print_summary(series, totals) -> None:
    for summary in series.sub_games:
        print(
            f"  sub-game {summary.sub_game}: {summary.result:<9} "
            f"({summary.reason}) in {summary.moves} moves -> {summary.score}"
        )
    print(f"Totals: cop={totals['cop']} thief={totals['thief']}")


def _run_peer_match(args) -> int:
    """Referee our 3 cop sub-games against the opponent's thief server (MATCH_PROTOCOL §D)."""
    from .orchestrator.peer_series import PeerSeriesRunner

    config = Config.load(args.config)
    if args.provider:
        config.raw["llm"]["provider"] = args.provider
    llm = build_llm(config.llm)
    start_index = 1 if args.group == "1" else 4
    print(
        f"Refereeing our cop half as Group {args.group} "
        f"(sub-games {start_index}-{start_index + args.num_games - 1}) "
        f"vs opponent thief {args.peer_thief_url}"
    )
    series = PeerSeriesRunner(
        config,
        peer_thief_url=args.peer_thief_url,
        peer_token=args.token,
        llm=llm,
        log=not args.no_log,
        num_games=args.num_games,
        start_index=start_index,
    ).run()
    _print_summary(series, series.totals)
    path = _write_half(config, args.group, series)
    print(f"Half record written to {path}")
    return 0


def _write_half(config, group: str, series) -> Path:
    """Persist our authoritative half (self-describing) for the §9.2 merge step."""
    import json
    from datetime import UTC, datetime

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


def _run_match(args) -> int:
    """Drive our side of the inter-group lockstep match; record our cop half (4–6)."""
    import os

    from .orchestrator.match_driver import MatchDriver

    config = Config.load(args.config)
    if args.provider:
        config.raw["llm"]["provider"] = args.provider
    llm = build_llm(config.llm)

    def need(var: str) -> str:
        val = os.getenv(var)
        if not val:
            raise SystemExit(f"missing env var {var} (opponent endpoint — see .env)")
        return val

    print("Driving inter-group match as group_2 (thief in 1-3, cop in 4-6)...")
    series = MatchDriver(
        config,
        peer_cop_url=need("PEER_COP_MCP_URL"),
        peer_thief_url=need("PEER_THIEF_MCP_URL"),
        peer_cop_token=need("PEER_COP_TOKEN"),
        peer_thief_token=need("PEER_THIEF_TOKEN"),
        llm=llm,
        log=not args.no_log,
        poll_interval=args.poll_interval,
    ).run()
    _print_summary(series, series.totals)
    path = _write_half(config, "2", series)
    print(f"Our cop half (sub-games 4-6) written to {path}")
    _email_match_result(config, series, no_email=args.no_email)
    return 0


def _email_match_result(config, series, *, no_email: bool) -> None:
    """Auto-send a per-team result summary via the Gmail pipeline (§9 delivery)."""
    our = config.team["group_name"]
    opp = config.match.get("opponent_name", "ahk-yosi")
    per_team = series.per_team or {}
    ranked = sorted(per_team.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked) >= 2 and ranked[0][1] == ranked[1][1]:
        winner = "tie"
    else:
        winner = ranked[0][0] if ranked else "n/a"
    for name, pts in ranked:
        print(f"  {name}: {pts} points")
    print(f"  winner: {winner}")
    if no_email:
        print("Email skipped (--no-email).")
        return

    from datetime import UTC, datetime
    report = {
        "match": f"{our} (group_2) vs {opp} (group_1)",
        "generated_utc": datetime.now(UTC).isoformat(),
        "totals_by_team": per_team,
        "winner": winner,
        "sub_games": series.breakdown or [],
    }
    try:
        from .orchestrator.gmail_sender import send_report_from_env
        msg_id = send_report_from_env(
            report, config.report["recipient"],
            subject=f"HW6 Cop-Thief Match — {our} vs {opp} (winner: {winner})",
        )
        print(f"Result emailed (message id {msg_id})")
    except Exception as exc:  # noqa: BLE001 — email is best-effort; never fail the match on it
        print(f"WARNING: result email failed ({exc}). Run finished; results saved to disk.")


def _run_peer_report(args) -> int:
    """Merge our half + the opponent's half into the §9.2 matched bonus_game report."""
    import json

    from .orchestrator.report_builder import build_bonus_from_halves, write_report

    config = Config.load(args.config)
    half_a = json.loads(Path(args.half_a).read_text(encoding="utf-8"))
    half_b = json.loads(Path(args.half_b).read_text(encoding="utf-8"))
    report = build_bonus_from_halves(half_a, half_b)
    path = write_report(report, config.report["output_dir"])
    totals = report["totals_by_group"]
    print("Bonus game (§9.2) merged:")
    for name, total in totals.items():
        print(f"  {name}: total={total}  bonus={report['bonus_claim'][name]}")
    print(f"Report written to {path}")
    print("Both teams must email byte-identical JSON or the bonus voids (§12.2).")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; returns a process exit code."""
    import sys

    raw = list(sys.argv[1:] if argv is None else argv)
    _commands = {"run", "peer-check", "peer-match", "peer-report", "match"}
    if not raw or raw[0] not in _commands:  # default to the `run` subcommand
        raw = ["run", *raw]
    args = _parse_args(raw)
    _load_dotenv()
    if args.command == "peer-check":
        import json

        from .orchestrator.peer_check import peer_check

        result = peer_check(args.url, args.token)
        print(json.dumps(result, indent=2))
        return 0 if result.get("reachable") else 1
    if args.command == "peer-match":
        return _run_peer_match(args)
    if args.command == "peer-report":
        return _run_peer_report(args)
    if args.command == "match":
        return _run_match(args)
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


if __name__ == "__main__":
    raise SystemExit(main())
