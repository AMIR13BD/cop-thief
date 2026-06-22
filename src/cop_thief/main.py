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
    run.add_argument("--email", action="store_true", help="email the report via the Gmail API")
    return parser.parse_args(argv)


def _print_summary(series, totals) -> None:
    for summary in series.sub_games:
        print(
            f"  sub-game {summary.sub_game}: {summary.result:<9} "
            f"({summary.reason}) in {summary.moves} moves -> {summary.score}"
        )
    print(f"Totals: cop={totals['cop']} thief={totals['thief']}")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; returns a process exit code."""
    import sys

    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw or raw[0] != "run":  # default to the `run` subcommand
        raw = ["run", *raw]
    args = _parse_args(raw)
    _load_dotenv()
    config = Config.load(args.config)
    if args.provider:
        config.raw["llm"]["provider"] = args.provider
    runner = SeriesRunner(config, llm=build_llm(config.llm), log=not args.no_log)
    series = runner.run()
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
