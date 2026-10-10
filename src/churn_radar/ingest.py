"""CSV ingestion for usage events and support tickets.

Both parsers are strict about columns and lenient about rows: a malformed
row is skipped with a warning on stderr, never silently dropped, never fatal.
"""
from __future__ import annotations

import csv
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

from churn_radar.models import Ticket, UsageDay

USAGE_COLUMNS = (
    "account_id",
    "account_name",
    "date",
    "logins",
    "active_users",
    "seats",
    "feature_uses",
    "key_feature_uses",
)
TICKET_COLUMNS = (
    "account_id",
    "account_name",
    "ticket_id",
    "date",
    "status",
    "subject",
    "body",
)


def _warn(lineno: int, reason: str) -> None:
    print(f"warn: line {lineno}: {reason}, skipped", file=sys.stderr)


def _parse_int(raw: str, field: str, lineno: int) -> int | None:
    try:
        value = int(raw.strip())
    except ValueError:
        _warn(lineno, f"bad integer in {field}: {raw!r}")
        return None
    if value < 0:
        _warn(lineno, f"negative value in {field}: {raw!r}")
        return None
    return value


def _parse_date(raw: str, lineno: int) -> date | None:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        _warn(lineno, f"bad date: {raw!r} (expected YYYY-MM-DD)")
        return None


def _require_columns(fieldnames: Sequence[str] | None, expected: tuple[str, ...], path: Path) -> None:
    missing = [c for c in expected if not fieldnames or c not in fieldnames]
    if missing:
        raise ValueError(f"{path}: missing columns: {', '.join(missing)}")


def _cell(row: Mapping[str, str | None], key: str) -> str:
    value = row.get(key)
    return value.strip() if value else ""


def parse_usage(path: Path) -> list[UsageDay]:
    """Parse a usage CSV. Columns: account_id,account_name,date,logins,
    active_users,seats,feature_uses,key_feature_uses."""
    rows: list[UsageDay] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        _require_columns(reader.fieldnames, USAGE_COLUMNS, path)
        for lineno, row in enumerate(reader, start=2):
            account_id = _cell(row, "account_id")
            account_name = _cell(row, "account_name")
            if not account_id or not account_name:
                _warn(lineno, "missing account_id or account_name")
                continue
            day = _parse_date(_cell(row, "date"), lineno)
            logins = _parse_int(_cell(row, "logins"), "logins", lineno)
            active = _parse_int(_cell(row, "active_users"), "active_users", lineno)
            seats = _parse_int(_cell(row, "seats"), "seats", lineno)
            feats = _parse_int(_cell(row, "feature_uses"), "feature_uses", lineno)
            key_feats = _parse_int(_cell(row, "key_feature_uses"), "key_feature_uses", lineno)
            if day is None or logins is None or active is None:
                continue
            if seats is None or feats is None or key_feats is None:
                continue
            if seats == 0:
                _warn(lineno, "seats is 0")
                continue
            rows.append(
                UsageDay(
                    account_id=account_id,
                    account_name=account_name,
                    day=day,
                    logins=logins,
                    active_users=min(active, seats),
                    seats=seats,
                    feature_uses=feats,
                    key_feature_uses=key_feats,
                )
            )
    return rows


def parse_tickets(path: Path) -> list[Ticket]:
    """Parse a tickets CSV. Columns: account_id,account_name,ticket_id,date,
    status,subject,body. Status must be 'open' or 'resolved'."""
    rows: list[Ticket] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        _require_columns(reader.fieldnames, TICKET_COLUMNS, path)
        for lineno, row in enumerate(reader, start=2):
            account_id = _cell(row, "account_id")
            account_name = _cell(row, "account_name")
            ticket_id = _cell(row, "ticket_id")
            status = _cell(row, "status").lower()
            if not account_id or not ticket_id:
                _warn(lineno, "missing account_id or ticket_id")
                continue
            if status not in ("open", "resolved"):
                _warn(lineno, f"bad status: {_cell(row, 'status')!r}")
                continue
            day = _parse_date(_cell(row, "date"), lineno)
            if day is None:
                continue
            rows.append(
                Ticket(
                    account_id=account_id,
                    account_name=account_name or account_id,
                    ticket_id=ticket_id,
                    day=day,
                    status=status,
                    subject=_cell(row, "subject"),
                    body=_cell(row, "body"),
                )
            )
    return rows
