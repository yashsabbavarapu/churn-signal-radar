"""Tests for the explainable scoring engine."""
from datetime import date, timedelta

from churn_radar.models import Ticket, UsageDay
from churn_radar.scoring import band_for, score_account, sentiment_of

TODAY = date(2026, 10, 10)


def _usage(
    logins: list[int],
    seats: int = 40,
    active_frac: float = 0.8,
    key_uses: int = 10,
    account_id: str = "acme",
    name: str = "Acme Corp",
) -> list[UsageDay]:
    rows = []
    for i, n in enumerate(logins):
        day = TODAY - timedelta(days=len(logins) - 1 - i)
        active = min(seats, int(seats * active_frac))
        rows.append(UsageDay(account_id, name, day, n, active, seats, n * 3, key_uses))
    return rows


def _ticket(
    tid: str,
    days_ago: int,
    status: str = "open",
    subject: str = "Question",
    body: str = "Hello",
    account_id: str = "acme",
    name: str = "Acme Corp",
) -> Ticket:
    return Ticket(account_id, name, tid, TODAY - timedelta(days=days_ago), status, subject, body)


def _flat(n: int = 28, logins: int = 100) -> list[UsageDay]:
    return _usage([logins] * n)


def test_healthy_account_scores_zero() -> None:
    score = score_account("acme", "Acme Corp", _flat(), [], TODAY)
    assert score.score == 0
    assert score.band == "Healthy"
    assert score.factors == ()


def test_login_decline_is_explained_with_numbers() -> None:
    usage = _usage([100] * 14 + [40] * 14)
    score = score_account("acme", "Acme Corp", usage, [], TODAY)
    factor = next(f for f in score.factors if f.name == "login_decline")
    assert factor.points == 30
    assert "60%" in factor.explanation  # (100-40)/100
    assert "100" in factor.explanation and "40" in factor.explanation


def test_dormancy_beats_decline_no_double_count() -> None:
    usage = _usage([100] * 21 + [0] * 7)
    score = score_account("acme", "Acme Corp", usage, [], TODAY)
    names = [f.name for f in score.factors]
    assert "dormancy" in names
    assert "login_decline" not in names


def test_support_backlog_and_stale_tickets() -> None:
    tickets = [_ticket(f"T-{i}", days_ago=20 - i, status="open") for i in range(5)]
    score = score_account("acme", "Acme Corp", _flat(), tickets, TODAY)
    by_name = {f.name: f for f in score.factors}
    assert by_name["support_backlog"].points == 15
    assert by_name["stale_tickets"].points == 10
    assert "20 days old" in by_name["stale_tickets"].explanation


def test_negative_sentiment_detected() -> None:
    bad = _ticket("T-1", 3, subject="Thinking about canceling",
                  body="Terrible experience, we are frustrated and may leave.")
    good = _ticket("T-2", 3, subject="Thanks", body="Great session, very helpful!")
    assert sentiment_of(bad) > 0
    assert sentiment_of(good) < 0
    score = score_account("acme", "Acme Corp", _flat(), [bad, good], TODAY)
    assert any(f.name == "negative_sentiment" for f in score.factors)


def test_feature_abandonment() -> None:
    prior = [UsageDay("acme", "Acme", TODAY - timedelta(days=28 - i), 50, 30, 40, 150, 20)
             for i in range(14)]
    recent = [UsageDay("acme", "Acme", TODAY - timedelta(days=14 - i), 50, 30, 40, 150, 0)
              for i in range(14)]
    score = score_account("acme", "Acme Corp", prior + recent, [], TODAY)
    assert any(f.name == "feature_abandonment" and f.points == 15 for f in score.factors)


def test_utilization_drop() -> None:
    usage = _usage([100] * 28, active_frac=0.8)[:14] + _usage([100] * 28, active_frac=0.4)[14:]
    score = score_account("acme", "Acme Corp", usage, [], TODAY)
    factor = next(f for f in score.factors if f.name == "utilization_drop")
    assert factor.points == 15


def test_score_is_capped_and_matches_factor_sum() -> None:
    # Worst plausible case: dormant, feature abandoned, 8 open tickets,
    # ancient backlog, furious customers.
    usage = [
        UsageDay("acme", "Acme Corp", TODAY - timedelta(days=28 - i), 100, 30, 40, 300,
                 20 if i < 14 else 0)
        for i in range(21)
    ] + [
        UsageDay("acme", "Acme Corp", TODAY - timedelta(days=7 - i), 0, 0, 40, 0, 0)
        for i in range(7)
    ]
    tickets = [_ticket(f"T-{i}", days_ago=25 - i, status="open",
                       subject="Cancel now", body="Terrible, broken, urgent, leaving.")
               for i in range(8)]
    score = score_account("acme", "Acme Corp", usage, tickets, TODAY)
    assert score.score == min(100, sum(f.points for f in score.factors))
    assert score.score <= 100
    assert score.band == band_for(score.score)
    assert score.score >= 60  # this scenario must ring every alarm


def test_band_boundaries() -> None:
    assert band_for(0) == "Healthy"
    assert band_for(29) == "Healthy"
    assert band_for(30) == "Watch"
    assert band_for(59) == "Watch"
    assert band_for(60) == "At risk"
    assert band_for(79) == "At risk"
    assert band_for(80) == "Critical"
    assert band_for(100) == "Critical"


def test_every_point_has_an_explanation() -> None:
    usage = _usage([100] * 14 + [20] * 14)
    tickets = [_ticket("T-1", 10, subject="Broken", body="This is broken and urgent.")]
    score = score_account("acme", "Acme Corp", usage, tickets, TODAY)
    assert score.score == sum(f.points for f in score.factors)
    assert all(f.explanation.strip() for f in score.factors)
