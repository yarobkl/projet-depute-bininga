"""UTC retention policy for incident media; media bytes live outside the business DB.

Policy: expiry is the earlier of receipt + 7 days and first opening + 48 hours.
Persist first_opened_at atomically in the business database; this module is pure.
"""
from datetime import datetime, timedelta, timezone

MAX_AGE = timedelta(days=7)
AFTER_OPEN = timedelta(hours=48)


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An explicit timezone-aware datetime is required")
    return value.astimezone(timezone.utc)


def expires_at(received_at, first_opened_at=None):
    received_at = utc(received_at)
    maximum = received_at + MAX_AGE
    if first_opened_at is None:
        return maximum
    opened = utc(first_opened_at)
    if not received_at <= opened < maximum:
        raise ValueError("First opening must be within the retention window")
    return min(maximum, opened + AFTER_OPEN)


def register_first_open(received_at, first_opened_at, now):
    now = utc(now)
    received_at = utc(received_at)
    if now < received_at:
        raise ValueError("Opening cannot precede reception")
    deadline = expires_at(received_at, first_opened_at)
    if now >= deadline:
        raise PermissionError("Media expired")
    return utc(first_opened_at) if first_opened_at is not None else now


def can_read(received_at, first_opened_at, now, deleted_at=None):
    if deleted_at is not None:
        utc(deleted_at)
        return False
    return utc(now) >= utc(received_at) and utc(now) < expires_at(received_at, first_opened_at)
