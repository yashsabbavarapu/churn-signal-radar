"""Digest rendering in Slack-compatible Markdown (mrkdwn).

*bold*, _italic_, and bullet lines all render in Slack as well as in
Markdown viewers, so one format serves both.
"""
from __future__ import annotations

from datetime import date

from churn_radar.models import AccountScore
from churn_radar.rules import motions_for


def _trend_line(score: AccountScore, previous: dict[str, int]) -> str:
    prev = previous.get(score.account_id)
    if prev is None:
        return " (new)"
    delta = score.score - prev
    if delta > 0:
        return f" (+{delta} vs last run)"
    if delta < 0:
        return f" ({delta} vs last run)"
    return " (unchanged)"


def _account_block(score: AccountScore, previous: dict[str, int]) -> list[str]:
    lines = [
        f"• *{score.account_name}*: *{score.score}/100* · {score.band}{_trend_line(score, previous)}"
    ]
    if score.factors:
        reasons = "; ".join(f.explanation for f in score.factors)
        lines.append(f"  _Why:_ {reasons}.")
    motions = motions_for(score.factors)
    if motions:
        lines.append(f"  _Save motion:_ {'; '.join(motions)}.")
    return lines


def render_digest(
    scores: list[AccountScore],
    previous: dict[str, int],
    run_date: date,
) -> str:
    """Render the full digest, accounts ranked by risk within each band."""
    at_risk = [s for s in scores if s.score >= 60]
    watch = [s for s in scores if 30 <= s.score < 60]
    healthy = [s for s in scores if s.score < 30]

    lines: list[str] = [
        f"*Churn Signal Radar*: {run_date.isoformat()}",
        f"_{len(at_risk)} at risk, {len(watch)} on watch, "
        f"{len(healthy)} healthy out of {len(scores)} accounts_",
        "",
    ]
    for heading, group in (("At risk", at_risk), ("Watch", watch)):
        if not group:
            continue
        lines.append(f"*{heading}*")
        for score in sorted(group, key=lambda s: -s.score):
            lines.extend(_account_block(score, previous))
        lines.append("")
    if healthy:
        names = ", ".join(s.account_name for s in sorted(healthy, key=lambda s: s.account_name))
        lines.append(f"_Healthy:_ {names}")
    return "\n".join(lines).rstrip() + "\n"
