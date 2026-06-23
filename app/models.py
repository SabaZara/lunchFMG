"""Database models.

people  — one row per ID card (identified by card_id; name optional, hidden in UI)
scans   — one row per claimed meal; UNIQUE(person_id, local_date) is the hard
          once-per-day guarantee enforced at the DB level.
admins  — operator login accounts.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .timeutil import utc_now

# Placeholder used when a card is imported/added without a real name.
NAME_PLACEHOLDER = "----"


class Person(SQLModel, table=True):
    __tablename__ = "people"

    id: int | None = Field(default=None, primary_key=True)
    # card_id is TEXT, unique, indexed, required. Never parsed as a number;
    # leading zeros are preserved end-to-end.
    card_id: str = Field(index=True, unique=True, nullable=False)
    # Kept in the schema so names can be added later with NO migration.
    # Hidden in the UI for now; defaults to the placeholder.
    full_name: str = Field(default=NAME_PLACEHOLDER)
    department: str | None = Field(default=None)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)


class Scan(SQLModel, table=True):
    __tablename__ = "scans"
    __table_args__ = (
        # The race-condition safety net: at most one meal per person per local day.
        UniqueConstraint("person_id", "local_date", name="uq_person_local_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="people.id", index=True, nullable=False)
    # Snapshot of the card string actually tapped (so history survives reassigns).
    card_id: str = Field(nullable=False)
    scanned_at: datetime = Field(default_factory=utc_now, nullable=False)
    # Local calendar date (in the configured timezone) the meal counted for.
    local_date: date = Field(index=True, nullable=False)


class Admin(SQLModel, table=True):
    __tablename__ = "admins"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False)
    password_hash: str = Field(nullable=False)
