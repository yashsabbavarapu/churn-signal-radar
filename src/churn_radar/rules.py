"""Save-motion rule table: each risk factor maps to a concrete action.

Small, explicit, and editable. A factor with no rule gets no motion rather
than a guessed one.
"""
from __future__ import annotations

from churn_radar.models import Factor

SAVE_MOTIONS: dict[str, str] = {
    "login_decline": "Exec check-in: re-engage the champion with a review of ROI delivered",
    "dormancy": "Re-activation push: targeted outreach to the users who went dark",
    "utilization_drop": "Enablement session: train the seats that stopped logging in",
    "feature_abandonment": "Workflow review: find out what replaced the core feature",
    "support_backlog": "Support SWAT: clear the backlog with a named contact",
    "stale_tickets": "Escalation: resolve or formally close aging tickets this week",
    "negative_sentiment": "Recovery plan: acknowledge the frustration, commit a fix date",
}


def motions_for(factors: tuple[Factor, ...], limit: int = 2) -> tuple[str, ...]:
    """Top save motions for the highest-contributing factors, deduplicated."""
    seen: list[str] = []
    for factor in sorted(factors, key=lambda f: -f.points):
        motion = SAVE_MOTIONS.get(factor.name)
        if motion and motion not in seen:
            seen.append(motion)
        if len(seen) >= limit:
            break
    return tuple(seen)
