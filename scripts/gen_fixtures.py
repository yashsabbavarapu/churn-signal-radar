"""Generate deterministic demo fixtures: 28 days of usage + tickets for 8 accounts.

Run: python scripts/gen_fixtures.py  (writes fixtures/usage.csv, fixtures/tickets.csv)
Seeded RNG, so output is stable across runs. Crafted so the demo shows the
full risk spread: 1 critical, 2 at risk, 1 watch, 4 healthy.
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

END = date(2026, 10, 10)
DAYS = 28
ROOT = Path(__file__).resolve().parent.parent

# account_id, name, base daily logins, trend over the window, seats, base utilization
ACCOUNTS = [
    ("acme", "Acme Corp", 120, 0.15, 50, 0.80),
    ("globex", "Globex Inc", 100, -0.80, 40, 0.75),
    ("initech", "Initech LLC", 80, -0.45, 30, 0.70),
    ("umbrellacorp", "Umbrella Corp", 60, -1.00, 25, 0.70),
    ("hooli", "Hooli Systems", 90, -0.12, 45, 0.75),
    ("stark", "Stark Industries", 110, 0.05, 55, 0.80),
    ("waynecorp", "Wayne Corp", 70, -0.30, 35, 0.70),
    ("wonka", "Wonka Labs", 50, 0.30, 20, 0.70),
]

TICKETS: list[tuple[str, str, str, str, str, str, str]] = [
    # ticket_id, account_id, date, status, subject, body
    ("T-101", "globex", "2026-10-08", "open", "Dashboard broken after update",
     "The dashboard has been broken since Tuesday, this is urgent, our team is frustrated."),
    ("T-102", "globex", "2026-09-25", "open", "Export failing for large reports",
     "Exports fail every time. Considering our options."),
    ("T-103", "globex", "2026-10-05", "open", "Thinking about canceling",
     "We are thinking about canceling if this is not fixed. Terrible experience this month."),
    ("T-104", "globex", "2026-10-09", "open", "SSO login loop",
     "Users stuck in a login loop. Please help."),
    ("T-105", "globex", "2026-09-20", "resolved", "Billing question",
     "Thanks, all sorted."),
    ("T-106", "globex", "2026-10-09", "open", "Renewal question",
     "When does our contract renew? We are evaluating alternatives."),
    ("T-201", "initech", "2026-10-06", "open", "Slow reports",
     "Reports are very slow lately, team is frustrated."),
    ("T-202", "initech", "2026-10-02", "open", "API rate limits",
     "Hitting rate limits, need guidance."),
    ("T-203", "initech", "2026-09-28", "open", "Data discrepancy",
     "Numbers do not match our warehouse."),
    ("T-301", "umbrellacorp", "2026-09-15", "open", "Nobody is using the tool",
     "We are disappointed with adoption. Thinking of leaving at renewal."),
    ("T-302", "umbrellacorp", "2026-10-01", "open", "Champion left the company",
     "Our admin left, not sure who owns this now."),
    ("T-401", "hooli", "2026-10-07", "open", "Feature request: SSO",
     "Would love SSO support."),
    ("T-501", "waynecorp", "2026-10-04", "open", "Core workflow stopped working",
     "The workflow builder is broken for us, this is urgent."),
    ("T-502", "waynecorp", "2026-09-10", "resolved", "Onboarding help",
     "Great session, thanks!"),
    ("T-601", "acme", "2026-10-03", "resolved", "Question about exports",
     "Thanks, helpful as always."),
    ("T-701", "wonka", "2026-10-05", "resolved", "Love the new dashboard",
     "The team loves the new dashboard. Excellent work."),
]

NAMES = {a[0]: a[1] for a in ACCOUNTS}


def main() -> None:
    rng = random.Random(42)
    fixtures = ROOT / "fixtures"
    fixtures.mkdir(exist_ok=True)

    usage_path = fixtures / "usage.csv"
    with usage_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("account_id", "account_name", "date", "logins", "active_users",
                    "seats", "feature_uses", "key_feature_uses"))
        for account_id, name, base, trend, seats, util in ACCOUNTS:
            for i in range(DAYS):
                day = END - timedelta(days=DAYS - 1 - i)
                frac = i / (DAYS - 1)
                if account_id == "umbrellacorp" and i >= DAYS - 10:
                    logins = 0  # went dark
                else:
                    logins = max(0, int(base * (1 + trend * frac) * rng.uniform(0.9, 1.1)))
                active = max(0, min(seats, int(seats * util * (1 + trend * 0.5 * frac)
                                              * rng.uniform(0.9, 1.05))))
                if logins == 0:
                    active = 0
                feature_uses = logins * 3
                if account_id == "waynecorp" and i >= DAYS - 14:
                    key_uses = 0  # abandoned the core feature
                else:
                    key_uses = max(0, int(20 * (1 + trend * frac) * rng.uniform(0.8, 1.2)))
                    if logins == 0:
                        key_uses = 0
                w.writerow((account_id, name, day.isoformat(), logins, active,
                            seats, feature_uses, key_uses))

    tickets_path = fixtures / "tickets.csv"
    with tickets_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("account_id", "account_name", "ticket_id", "date",
                    "status", "subject", "body"))
        for tid, aid, day, status, subject, body in TICKETS:
            w.writerow((aid, NAMES[aid], tid, day, status, subject, body))

    print(f"wrote {usage_path} and {tickets_path}")


if __name__ == "__main__":
    main()
