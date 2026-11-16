"""Retention rules for incident media. No media bytes are stored here."""
from datetime import datetime, timedelta, timezone

def utc(value):
    if value.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    return value.astimezone(timezone.utc)

def expires_at(received_at, first_opened_at=None):
    received_at = utc(received_at)
    maximum = received_at + timedelta(days=7)
    if first_opened_at is None:
        return maximum
    opened = utc(first_opened_at)
    if opened < received_at:
        raise ValueError("Opening cannot precede reception")
    return min(maximum, opened + timedelta(hours=48))

def register_first_open(received_at, first_opened_at, now):
    now = utc(now)
    deadline = expires_at(received_at, first_opened_at)
    if now >= deadline:
        raise PermissionError("Media expired")
    return first_opened_at if first_opened_at is not None else now

def can_read(received_at, first_opened_at, now, deleted_at=None):
    return deleted_at is None and utc(now) < expires_at(received_at, first_opened_at)
