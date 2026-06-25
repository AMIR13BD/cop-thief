"""Inter-group match CLI handlers (split from ``main`` for the 150-line limit)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .cli_commands import _print_summary, _write_half
from .config import Config
from .orchestrator.llm_client import build_llm


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


def _run_match(args) -> int:
    """Drive our side of the inter-group lockstep match; record our cop half (4–6)."""
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
    """Build the §9.2 ``bonus_game`` report (opponent's agreed shape), save it, and email it."""
    from .orchestrator.report_builder import build_bonus_match_report, write_report

    our = config.team["group_name"]
    opp = config.match.get("opponent_name", "ahk-yosi")
    report = build_bonus_match_report(series, config)
    totals, claim = report["totals_by_group"], report["bonus_claim"]
    path = write_report(report, config.report["output_dir"])
    print(f"§9.2 bonus_game report written to {path}")
    for name, pts in totals.items():
        print(f"  {name}: total={pts}  bonus={claim[name]}")
    if no_email:
        print("Email skipped (--no-email). Share this file; both teams email it verbatim.")
        return
    try:
        from .orchestrator.gmail_sender import send_report_from_env
        # indent=None -> compact single-line body, matching the opponent's wire format.
        msg_id = send_report_from_env(
            report, config.report["recipient"],
            subject=f"HW6 Cop-Thief Bonus — {opp} vs {our}", indent=None,
        )
        print(f"Bonus report emailed (message id {msg_id})")
    except Exception as exc:  # noqa: BLE001 — email is best-effort; never fail the match on it
        print(f"WARNING: result email failed ({exc}). Report saved to disk; send it manually.")


def _run_peer_report(args) -> int:
    """Merge our half + the opponent's half into the §9.2 matched bonus_game report."""
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
