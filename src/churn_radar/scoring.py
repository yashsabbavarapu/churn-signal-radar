"""Transparent heuristic churn scoring.

The product thesis: every point of risk must be explainable. Each factor
records its name, its point contribution, and a plain-language explanation
with the actual numbers. No black boxes.
"""
from __future__ import annotations

from datetime import date, timedelta

from churn_radar.models import AccountScore, Factor, Ticket, UsageDay

RECENT_DAYS = 14
PRIOR_DAYS = 14
DORMANT_DAYS = 7
SENTIMENT_DAYS = 30

NEGATIVE_KEYWORDS = (
    "cancel",
    "broken",
    "frustrat",
    "terrible",
    "awful",
    "urgent",
    "angry",
    "disappoint",
    "refund",
    "leaving",
    "worst",
    "not working",
    "useless",
)
POSITIVE_KEYWORDS = ("love", "great", "awesome", "thanks", "helpful", "excellent")


def band_for(score: int) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "At risk"
    if score >= 30:
        return "Watch"
    return "Healthy"


def sentiment_of(ticket: Ticket) -> int:
    """Net negative keyword hits. Positive return means negative sentiment."""
    text = f"{ticket.subject} {ticket.body}".lower()
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    return neg - pos


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def score_account(
    account_id: str,
    account_name: str,
    usage: list[UsageDay],
    tickets: list[Ticket],
    today: date,
) -> AccountScore:
    factors: list[Factor] = []
    ordered = sorted(usage, key=lambda u: u.day)
    recent = [u for u in ordered if u.day > today - timedelta(days=RECENT_DAYS)]
    prior = [
        u
        for u in ordered
        if today - timedelta(days=RECENT_DAYS + PRIOR_DAYS) < u.day
        <= today - timedelta(days=RECENT_DAYS)
    ]

    recent_logins = _mean([float(u.logins) for u in recent])
    prior_logins = _mean([float(u.logins) for u in prior])

    # Dormancy beats decline: a dead account is not "declining", it is gone.
    last_week_logins = sum(u.logins for u in ordered if u.day > today - timedelta(days=DORMANT_DAYS))
    if last_week_logins == 0 and ordered:
        factors.append(
            Factor(
                name="dormancy",
                points=20,
                explanation=f"No logins at all in the last {DORMANT_DAYS} days",
            )
        )
    elif prior_logins > 0:
        decline = max(0.0, (prior_logins - recent_logins) / prior_logins)
        if decline >= 0.50:
            factors.append(
                Factor(
                    name="login_decline",
                    points=30,
                    explanation=(
                        f"Logins fell {decline:.0%} "
                        f"({prior_logins:.0f} to {recent_logins:.0f} per day) "
                        f"over the last {RECENT_DAYS} days"
                    ),
                )
            )
        elif decline >= 0.30:
            factors.append(
                Factor(
                    name="login_decline",
                    points=20,
                    explanation=(
                        f"Logins fell {decline:.0%} "
                        f"({prior_logins:.0f} to {recent_logins:.0f} per day) "
                        f"over the last {RECENT_DAYS} days"
                    ),
                )
            )
        elif decline >= 0.15:
            factors.append(
                Factor(
                    name="login_decline",
                    points=10,
                    explanation=(
                        f"Logins fell {decline:.0%} "
                        f"({prior_logins:.0f} to {recent_logins:.0f} per day) "
                        f"over the last {RECENT_DAYS} days"
                    ),
                )
            )

    # Seat utilization: are the bought seats actually used?
    def utilization(rows: list[UsageDay]) -> float:
        ratios = [u.active_users / u.seats for u in rows if u.seats > 0]
        return _mean(ratios)

    util_drop = utilization(prior) - utilization(recent)
    if util_drop >= 0.25:
        factors.append(
            Factor(
                name="utilization_drop",
                points=15,
                explanation=(
                    f"Seat utilization fell {util_drop:.0%} "
                    f"({utilization(prior):.0%} to {utilization(recent):.0%} of seats active)"
                ),
            )
        )
    elif util_drop >= 0.10:
        factors.append(
            Factor(
                name="utilization_drop",
                points=8,
                explanation=(
                    f"Seat utilization fell {util_drop:.0%} "
                    f"({utilization(prior):.0%} to {utilization(recent):.0%} of seats active)"
                ),
            )
        )

    # Key feature abandonment: they stopped using the thing they bought it for.
    if sum(u.key_feature_uses for u in recent) == 0 and sum(u.key_feature_uses for u in prior) > 0:
        factors.append(
            Factor(
                name="feature_abandonment",
                points=15,
                explanation="Core feature usage dropped to zero in the last "
                f"{RECENT_DAYS} days after active use before",
            )
        )

    # Support load.
    open_tickets = [t for t in tickets if t.status == "open"]
    if len(open_tickets) >= 5:
        factors.append(
            Factor(
                name="support_backlog",
                points=15,
                explanation=f"{len(open_tickets)} open support tickets",
            )
        )
    elif len(open_tickets) >= 3:
        factors.append(
            Factor(
                name="support_backlog",
                points=10,
                explanation=f"{len(open_tickets)} open support tickets",
            )
        )
    elif len(open_tickets) >= 1:
        factors.append(
            Factor(
                name="support_backlog",
                points=5,
                explanation=f"{len(open_tickets)} open support ticket(s)",
            )
        )
    if open_tickets:
        oldest = min(t.day for t in open_tickets)
        age = (today - oldest).days
        if age > 14:
            factors.append(
                Factor(
                    name="stale_tickets",
                    points=10,
                    explanation=f"Oldest open ticket is {age} days old with no resolution",
                )
            )
        elif age > 7:
            factors.append(
                Factor(
                    name="stale_tickets",
                    points=5,
                    explanation=f"Oldest open ticket is {age} days old with no resolution",
                )
            )

    # Sentiment: keyword heuristic over recent tickets.
    cutoff = today - timedelta(days=SENTIMENT_DAYS)
    negative = [t for t in tickets if t.day >= cutoff and sentiment_of(t) > 0]
    if negative:
        noun = "ticket" if len(negative) == 1 else "tickets"
        factors.append(
            Factor(
                name="negative_sentiment",
                points=10,
                explanation=f"Negative language in {len(negative)} {noun} in the last {SENTIMENT_DAYS} days",
            )
        )

    score = min(100, sum(f.points for f in factors))
    return AccountScore(
        account_id=account_id,
        account_name=account_name,
        score=score,
        band=band_for(score),
        factors=tuple(factors),
    )
