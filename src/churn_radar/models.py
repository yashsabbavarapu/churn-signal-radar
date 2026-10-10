"""Domain models for churn signal radar."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class UsageDay:
    account_id: str
    account_name: str
    day: date
    logins: int
    active_users: int
    seats: int
    feature_uses: int
    key_feature_uses: int


@dataclass(frozen=True)
class Ticket:
    account_id: str
    account_name: str
    ticket_id: str
    day: date
    status: str  # "open" or "resolved"
    subject: str
    body: str


@dataclass(frozen=True)
class Factor:
    """One explainable contribution to a risk score."""

    name: str
    points: int
    explanation: str


@dataclass(frozen=True)
class AccountScore:
    account_id: str
    account_name: str
    score: int
    band: str
    factors: tuple[Factor, ...]
