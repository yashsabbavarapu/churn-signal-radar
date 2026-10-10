"""SQLite storage (stdlib only). Tables: usage, tickets, scores.

Re-ingesting the same CSVs is idempotent: usage rows are replaced by
(account_id, day), tickets by ticket_id. Each digest run appends one row
per account to scores, which is what powers run-over-run trends.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TypedDict

from churn_radar.models import AccountScore, Factor, Ticket, UsageDay


class _FactorJSON(TypedDict):
    name: str
    points: int
    explanation: str

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage(
    account_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    day TEXT NOT NULL,
    logins INTEGER NOT NULL,
    active_users INTEGER NOT NULL,
    seats INTEGER NOT NULL,
    feature_uses INTEGER NOT NULL,
    key_feature_uses INTEGER NOT NULL,
    PRIMARY KEY (account_id, day)
);
CREATE TABLE IF NOT EXISTS tickets(
    ticket_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    day TEXT NOT NULL,
    status TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scores(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    account_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    score INTEGER NOT NULL,
    band TEXT NOT NULL,
    factors_json TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def save_usage(self, rows: list[UsageDay]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO usage VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    r.account_id,
                    r.account_name,
                    r.day.isoformat(),
                    r.logins,
                    r.active_users,
                    r.seats,
                    r.feature_uses,
                    r.key_feature_uses,
                )
                for r in rows
            ],
        )
        self._conn.commit()

    def save_tickets(self, rows: list[Ticket]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO tickets VALUES (?,?,?,?,?,?,?)",
            [
                (
                    r.ticket_id,
                    r.account_id,
                    r.account_name,
                    r.day.isoformat(),
                    r.status,
                    r.subject,
                    r.body,
                )
                for r in rows
            ],
        )
        self._conn.commit()

    def account_ids(self) -> list[tuple[str, str]]:
        cur = self._conn.execute(
            "SELECT account_id, MAX(account_name) FROM usage GROUP BY account_id "
            "UNION SELECT account_id, MAX(account_name) FROM tickets GROUP BY account_id"
        )
        return [(str(a), str(n)) for a, n in cur.fetchall()]

    def usage_for(self, account_id: str) -> list[UsageDay]:
        cur = self._conn.execute(
            "SELECT account_id, account_name, day, logins, active_users, seats,"
            " feature_uses, key_feature_uses FROM usage WHERE account_id = ?"
            " ORDER BY day",
            (account_id,),
        )
        return [
            UsageDay(
                account_id=str(r[0]),
                account_name=str(r[1]),
                day=date.fromisoformat(str(r[2])),
                logins=int(r[3]),
                active_users=int(r[4]),
                seats=int(r[5]),
                feature_uses=int(r[6]),
                key_feature_uses=int(r[7]),
            )
            for r in cur.fetchall()
        ]

    def tickets_for(self, account_id: str) -> list[Ticket]:
        cur = self._conn.execute(
            "SELECT ticket_id, account_id, account_name, day, status, subject, body"
            " FROM tickets WHERE account_id = ? ORDER BY day",
            (account_id,),
        )
        return [
            Ticket(
                ticket_id=str(r[0]),
                account_id=str(r[1]),
                account_name=str(r[2]),
                day=date.fromisoformat(str(r[3])),
                status=str(r[4]),
                subject=str(r[5]),
                body=str(r[6]),
            )
            for r in cur.fetchall()
        ]

    def latest_day(self) -> date | None:
        cur = self._conn.execute("SELECT MAX(day) FROM usage")
        row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return date.fromisoformat(str(row[0]))

    def latest_scores(self) -> dict[str, int]:
        """Scores from the most recent digest run, keyed by account_id."""
        cur = self._conn.execute("SELECT MAX(run_at) FROM scores")
        row = cur.fetchone()
        if row is None or row[0] is None:
            return {}
        cur = self._conn.execute(
            "SELECT account_id, score FROM scores WHERE run_at = ?", (str(row[0]),)
        )
        return {str(a): int(s) for a, s in cur.fetchall()}

    def save_scores(self, scores: list[AccountScore]) -> None:
        run_at = datetime.now(timezone.utc).isoformat()
        self._conn.executemany(
            "INSERT INTO scores (run_at, account_id, account_name, score, band, factors_json)"
            " VALUES (?,?,?,?,?,?)",
            [
                (
                    run_at,
                    s.account_id,
                    s.account_name,
                    s.score,
                    s.band,
                    json.dumps(
                        [
                            {"name": f.name, "points": f.points, "explanation": f.explanation}
                            for f in s.factors
                        ]
                    ),
                )
                for s in scores
            ],
        )
        self._conn.commit()

    def load_scores(self, account_id: str) -> list[tuple[str, int, str]]:
        """History for one account: (run_at, score, band), oldest first."""
        cur = self._conn.execute(
            "SELECT run_at, score, band FROM scores WHERE account_id = ? ORDER BY id",
            (account_id,),
        )
        return [(str(r[0]), int(r[1]), str(r[2])) for r in cur.fetchall()]

    def load_factors(self, account_id: str) -> list[Factor]:
        cur = self._conn.execute(
            "SELECT factors_json FROM scores WHERE account_id = ? ORDER BY id DESC LIMIT 1",
            (account_id,),
        )
        row = cur.fetchone()
        if row is None:
            return []
        items: list[_FactorJSON] = json.loads(str(row[0]))
        return [
            Factor(name=i["name"], points=i["points"], explanation=i["explanation"])
            for i in items
        ]
