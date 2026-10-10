"""Tests for digest rendering."""
from datetime import date

from churn_radar.digest import render_digest
from churn_radar.models import AccountScore, Factor


def _score(name: str, points: int, band: str, factor_names: tuple[str, ...] = ()) -> AccountScore:
    factors = tuple(Factor(n, 10, f"{n} happened") for n in factor_names)
    return AccountScore(name.lower().replace(" ", ""), name, points, band, factors)


def test_digest_ranks_and_sections() -> None:
    scores = [
        _score("Healthy Co", 5, "Healthy"),
        _score("Risky Co", 70, "At risk", ("login_decline", "support_backlog")),
        _score("Watchful Co", 40, "Watch", ("stale_tickets",)),
    ]
    text = render_digest(scores, {}, date(2026, 10, 10))
    assert text.startswith("*Churn Signal Radar*: 2026-10-10")
    assert "_1 at risk, 1 on watch, 1 healthy out of 3 accounts_" in text
    assert "*At risk*" in text and "*Watch*" in text
    assert text.index("Risky Co") < text.index("Watchful Co")
    assert "_Healthy:_ Healthy Co" in text


def test_digest_includes_factors_and_save_motion() -> None:
    scores = [_score("Risky Co", 70, "At risk", ("login_decline", "support_backlog"))]
    text = render_digest(scores, {}, date(2026, 10, 10))
    assert "_Why:_ login_decline happened; support_backlog happened." in text
    assert "_Save motion:_" in text
    assert "Exec check-in" in text  # rule for login_decline


def test_digest_trend_lines() -> None:
    scores = [_score("Risky Co", 70, "At risk"), _score("New Co", 65, "At risk")]
    text = render_digest(scores, {"riskyco": 55}, date(2026, 10, 10))
    assert "(+15 vs last run)" in text
    assert "(new)" in text


def test_digest_negative_trend() -> None:
    scores = [_score("Risky Co", 50, "Watch")]
    text = render_digest(scores, {"riskyco": 70}, date(2026, 10, 10))
    assert "(-20 vs last run)" in text


def test_empty_digest() -> None:
    text = render_digest([], {}, date(2026, 10, 10))
    assert "0 at risk, 0 on watch, 0 healthy out of 0 accounts" in text
