"""Command-line entrypoint: parse args and dispatch to the command handlers.

Examples::

    cop-thief run                      # play 6 sub-games, write JSON report
    cop-thief run --provider anthropic # drive agents with Claude (needs ANTHROPIC_API_KEY)
    cop-thief run --email              # also send the report via the Gmail API
    cop-thief match                    # drive our side of the inter-group bonus match

Handlers live in ``cli_commands`` (local series) and ``cli_match`` (inter-group).
"""

from __future__ import annotations

import argparse

from .cli_commands import _load_dotenv, _run_peer_check, _run_series
from .cli_match import _run_match, _run_peer_match, _run_peer_report


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
        return _run_peer_check(args)
    if args.command == "peer-match":
        return _run_peer_match(args)
    if args.command == "peer-report":
        return _run_peer_report(args)
    if args.command == "match":
        return _run_match(args)
    return _run_series(args)


if __name__ == "__main__":
    raise SystemExit(main())
