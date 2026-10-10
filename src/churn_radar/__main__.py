"""CLI: ingest signals, then render the digest."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from churn_radar.digest import render_digest
from churn_radar.ingest import parse_tickets, parse_usage
from churn_radar.models import AccountScore
from churn_radar.scoring import score_account
from churn_radar.storage import Store


def cmd_ingest(args: argparse.Namespace) -> int:
    store = Store(Path(args.db))
    try:
        usage = parse_usage(Path(args.usage))
        tickets = parse_tickets(Path(args.tickets))
        store.save_usage(usage)
        store.save_tickets(tickets)
    finally:
        store.close()
    print(f"ingested {len(usage)} usage rows, {len(tickets)} tickets into {args.db}")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    store = Store(Path(args.db))
    try:
        today = store.latest_day() or date.today()
        previous = store.latest_scores()
        scores: list[AccountScore] = []
        for account_id, account_name in sorted(store.account_ids()):
            scores.append(
                score_account(
                    account_id,
                    account_name,
                    store.usage_for(account_id),
                    store.tickets_for(account_id),
                    today,
                )
            )
        store.save_scores(scores)
        text = render_digest(scores, previous, today)
    finally:
        store.close()
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote digest to {args.output}")
    else:
        sys.stdout.write(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="churn-radar", description="Explainable churn-risk radar")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Load usage and ticket CSVs")
    p_ingest.add_argument("--usage", required=True, help="Path to usage CSV")
    p_ingest.add_argument("--tickets", required=True, help="Path to tickets CSV")
    p_ingest.add_argument("--db", default="churn_radar.db", help="SQLite path")
    p_ingest.set_defaults(func=cmd_ingest)

    p_digest = sub.add_parser("digest", help="Score accounts and render the digest")
    p_digest.add_argument("--db", default="churn_radar.db", help="SQLite path")
    p_digest.add_argument("--output", default=None, help="Write digest to file instead of stdout")
    p_digest.set_defaults(func=cmd_digest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
