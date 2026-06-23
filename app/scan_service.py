"""Core once-per-day scan decision.

Statuses are kept in English internally ("ALLOWED" / "DENIED") so other code
and tests can key on them reliably. Only the human-facing reason text is
Georgian.

Race safety: we DO NOT SELECT-then-INSERT. We attempt the INSERT of a scan row
guarded by UNIQUE(person_id, local_date). If it raises IntegrityError the
person already ate today — exactly one concurrent tap can win.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .config import get_settings
from .models import Person, Scan
from .timeutil import local_date_for, local_time_str, utc_now

# Machine-readable statuses (never localized).
STATUS_ALLOWED = "ALLOWED"
STATUS_DENIED = "DENIED"

# Georgian reason codes shown to the user.
REASON_UNKNOWN_CARD = "უცნობი ბარათი"
REASON_INACTIVE = "ბარათი გათიშულია"
REASON_ALREADY_ATE = "დღეს უკვე ნაჭამია"


@dataclass
class ScanResult:
    status: str
    reason: str | None = None
    scanned_at: str | None = None  # local HH:MM:SS for display


def normalize_card_id(raw: str) -> str:
    """Trim surrounding whitespace but preserve everything else (leading zeros)."""
    return (raw or "").strip()


def decide_scan(session: Session, raw_card_id: str) -> ScanResult:
    settings = get_settings()
    tz = settings.tz

    card_id = normalize_card_id(raw_card_id)
    if not card_id:
        return ScanResult(status=STATUS_DENIED, reason=REASON_UNKNOWN_CARD)

    person = session.exec(select(Person).where(Person.card_id == card_id)).first()
    if person is None:
        return ScanResult(status=STATUS_DENIED, reason=REASON_UNKNOWN_CARD)
    if not person.active:
        return ScanResult(status=STATUS_DENIED, reason=REASON_INACTIVE)

    now = utc_now()
    today_local = local_date_for(now, tz)

    scan = Scan(
        person_id=person.id,
        card_id=card_id,
        scanned_at=now,
        local_date=today_local,
    )
    session.add(scan)
    try:
        session.commit()
    except IntegrityError:
        # UNIQUE(person_id, local_date) violated → already ate today.
        session.rollback()
        return ScanResult(status=STATUS_DENIED, reason=REASON_ALREADY_ATE)

    session.refresh(scan)
    return ScanResult(
        status=STATUS_ALLOWED,
        scanned_at=local_time_str(scan.scanned_at, tz),
    )
