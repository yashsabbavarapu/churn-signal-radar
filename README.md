# Churn Signal Radar
[![CI](https://github.com/yashsabbavarapu/churn-signal-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/yashsabbavarapu/churn-signal-radar/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Detect churn risk from product usage and support signals, and explain every point of the score. Growth teams pay for this category (ChurnZero, Vitally). This is the open-source, explainable version.

The thesis: a churn score nobody can explain is a churn score nobody acts on. Every account gets a 0-100 risk score plus the exact factors behind it in plain language, each with a suggested save motion.

## How it works

```
usage.csv ──┐
            ├─► ingest ─► SQLite ─► score (transparent heuristics) ─► digest (Slack-ready Markdown)
tickets.csv ┘
```

1. **Ingest** product usage events (logins, active users, seats, feature use) and support tickets from CSVs.
2. **Score** each account 0-100. Recent 14 days vs prior 14 days on every signal. Bands: Healthy (<30), Watch (30-59), At risk (60-79), Critical (80+).
3. **Digest** renders a ranked Slack-compatible Markdown digest: score, why, and what to do.

### The scoring model (all of it, no black box)

| Factor | Points | Trigger |
|---|---|---|
| Login decline | 10/20/30 | Logins fell 15/30/50%+ vs prior 14 days |
| Dormancy | 20 | Zero logins in the last 7 days (replaces decline, no double count) |
| Utilization drop | 8/15 | Active seats fell 10/25+ percentage points |
| Feature abandonment | 15 | Core feature use dropped to zero after active use |
| Support backlog | 5/10/15 | 1/3/5+ open tickets |
| Stale tickets | 5/10 | Oldest open ticket 7/14+ days old |
| Negative sentiment | 10 | Negative language in a ticket in the last 30 days |

Each factor maps to a save motion via a small rule table (`rules.py`): exec check-in, re-activation push, enablement session, workflow review, support SWAT, escalation, recovery plan.

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install pytest mypy  # dev only; runtime is stdlib
python scripts/gen_fixtures.py            # demo data: 8 accounts, 28 days
PYTHONPATH=src python -m churn_radar ingest --usage fixtures/usage.csv --tickets fixtures/tickets.csv
PYTHONPATH=src python -m churn_radar digest --output digest.md
```

Sample output (from the fixtures):

```
*Churn Signal Radar*: 2026-10-10
_2 at risk, 2 on watch, 4 healthy out of 8 accounts_

*At risk*
• *Globex Inc*: *73/100* · At risk (new)
  _Why:_ Logins fell 52% (81 to 39 per day) over the last 14 days; Seat utilization
  fell 14% (64% to 49% of seats active); 5 open support tickets; Oldest open ticket
  is 15 days old with no resolution; Negative language in 2 tickets in the last 30 days.
  _Save motion:_ Exec check-in: re-engage the champion with a review of ROI delivered;
  Support SWAT: clear the backlog with a named contact.
```

Run `digest` again after new ingests and each account shows its trend (`+12 vs last run`).

## CSV schemas

`usage.csv`: `account_id,account_name,date,logins,active_users,seats,feature_uses,key_feature_uses`
`tickets.csv`: `account_id,account_name,ticket_id,date,status,subject,body` (status: `open` or `resolved`)

Malformed rows are skipped with a stderr warning, never fatal. Re-ingesting is idempotent.

## Checks

```bash
.venv/bin/python -m pytest        # 24 tests
.venv/bin/python -m mypy --strict src   # clean
```

## What v1 does NOT do

- The model is a transparent heuristic, not ML. Weights are reasoned defaults, not learned.
- Sentiment is keyword-based, not a classifier. Sarcasm will fool it.
- Fixtures are synthetic, not real customer data.
- No live integrations (no Salesforce, no Zendesk, no Slack webhook). CSV in, Markdown out.
- Single-user SQLite. "Today" is the latest date in your usage data, so backfills work.

## v2 roadmap

Real source integrations (CRM + helpdesk APIs behind the ingest boundary), learned weights with the heuristic as a prior, a proper sentiment classifier, Slack webhook delivery on a schedule, per-account score history charts.
