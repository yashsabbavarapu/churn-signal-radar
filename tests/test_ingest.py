"""Tests for CSV ingestion, including malformed rows."""
from pathlib import Path

import pytest

from churn_radar.ingest import parse_tickets, parse_usage

USAGE_OK = """account_id,account_name,date,logins,active_users,seats,feature_uses,key_feature_uses
acme,Acme Corp,2026-10-10,100,40,50,300,20
"""

USAGE_BAD_ROWS = """account_id,account_name,date,logins,active_users,seats,feature_uses,key_feature_uses
acme,Acme Corp,2026-10-10,100,40,50,300,20
acme,Acme Corp,not-a-date,100,40,50,300,20
acme,Acme Corp,2026-10-09,many,40,50,300,20
acme,Acme Corp,2026-10-08,100,40,0,300,20
,Acme Corp,2026-10-07,100,40,50,300,20
"""

TICKETS_OK = """account_id,account_name,ticket_id,date,status,subject,body
acme,Acme Corp,T-1,2026-10-09,open,Broken,It is broken.
"""

TICKETS_BAD_ROWS = """account_id,account_name,ticket_id,date,status,subject,body
acme,Acme Corp,T-1,2026-10-09,open,Broken,It is broken.
acme,Acme Corp,T-2,2026-10-09,pending,Weird,Bad status row.
acme,Acme Corp,,2026-10-09,open,No id,Missing ticket id.
"""


def test_parse_usage_ok(tmp_path: Path) -> None:
    p = tmp_path / "u.csv"
    p.write_text(USAGE_OK, encoding="utf-8")
    rows = parse_usage(p)
    assert len(rows) == 1
    assert rows[0].logins == 100
    assert rows[0].day.isoformat() == "2026-10-10"


def test_parse_usage_skips_bad_rows(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "u.csv"
    p.write_text(USAGE_BAD_ROWS, encoding="utf-8")
    rows = parse_usage(p)
    assert len(rows) == 1  # only the first row survives
    assert "warn" in capsys.readouterr().err


def test_parse_usage_missing_column(tmp_path: Path) -> None:
    p = tmp_path / "u.csv"
    p.write_text("account_id,date\nacme,2026-10-10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        parse_usage(p)


def test_parse_tickets_ok_and_bad_rows(tmp_path: Path) -> None:
    p = tmp_path / "t.csv"
    p.write_text(TICKETS_OK, encoding="utf-8")
    assert len(parse_tickets(p)) == 1
    p.write_text(TICKETS_BAD_ROWS, encoding="utf-8")
    rows = parse_tickets(p)
    assert len(rows) == 1
    assert rows[0].ticket_id == "T-1"
