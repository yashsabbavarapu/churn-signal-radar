"""Tests for SQLite storage round-trips and run-over-run trends."""
from datetime import date
from pathlib import Path

from churn_radar.models import AccountScore, Factor, Ticket, UsageDay
from churn_radar.storage import Store


def _usage() -> list[UsageDay]:
    return [UsageDay("acme", "Acme Corp", date(2026, 10, 10), 100, 40, 50, 300, 20)]


def _ticket() -> list[Ticket]:
    return [Ticket("acme", "Acme Corp", "T-1", date(2026, 10, 9), "open", "Hi", "Help")]


def _score(points: int) -> AccountScore:
    return AccountScore("acme", "Acme Corp", points, "Watch",
                        (Factor("login_decline", 10, "Logins fell"),))


def test_round_trip(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.db")
    try:
        store.save_usage(_usage())
        store.save_tickets(_ticket())
        assert store.account_ids() == [("acme", "Acme Corp")]
        assert store.latest_day() == date(2026, 10, 10)
        loaded = store.usage_for("acme")
        assert loaded == _usage()
        assert store.tickets_for("acme") == _ticket()
    finally:
        store.close()


def test_ingest_is_idempotent(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.db")
    try:
        store.save_usage(_usage())
        store.save_usage(_usage())
        assert len(store.usage_for("acme")) == 1
    finally:
        store.close()


def test_score_trend_across_runs(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.db")
    try:
        assert store.latest_scores() == {}
        store.save_scores([_score(40)])
        assert store.latest_scores() == {"acme": 40}
        store.save_scores([_score(70)])
        assert store.latest_scores() == {"acme": 70}
        history = store.load_scores("acme")
        assert [s for _, s, _ in history] == [40, 70]
        factors = store.load_factors("acme")
        assert factors[0].name == "login_decline"
        assert factors[0].points == 10
    finally:
        store.close()


def test_empty_db(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.db")
    try:
        assert store.account_ids() == []
        assert store.latest_day() is None
        assert store.latest_scores() == {}
    finally:
        store.close()
