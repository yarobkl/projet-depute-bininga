"""Production DB resilience primitives for BININGA.

Provides a cheap cached health probe and a short circuit-breaker for durable
mutations. It intentionally fails closed: if persistence cannot be verified,
critical writes are rejected rather than acknowledged optimistically.
"""
from __future__ import annotations

import threading
import time


_LOCK = threading.Lock()
_STATE = {
    "checked_at": 0.0,
    "healthy": False,
    "backend": "",
    "failures": 0,
    "circuit_until": 0.0,
    "last_error": "",
}
PROBE_TTL_SECONDS = 10
CIRCUIT_SECONDS = 20


def _backend(server) -> str:
    try:
        backend, _ = server._db_config()
        return str(backend or "")
    except Exception:
        return ""


def _probe_once(server) -> tuple[bool, str]:
    backend = _backend(server)
    if not backend:
        return False, "database_not_configured"
    loader = getattr(server, "_pg_load", None)
    if not callable(loader):
        return False, "persistent_loader_unavailable"
    try:
        # Existing key keeps this read harmless and avoids any schema mutation.
        loader("users")
        return True, ""
    except Exception as exc:
        return False, exc.__class__.__name__


def health(server, *, force: bool = False) -> dict:
    now = time.monotonic()
    with _LOCK:
        if not force and _STATE["checked_at"] and now - _STATE["checked_at"] < PROBE_TTL_SECONDS:
            return dict(_STATE)
        if not force and _STATE["circuit_until"] > now:
            return dict(_STATE)

    ok, error = _probe_once(server)
    backend = _backend(server)
    with _LOCK:
        _STATE["checked_at"] = now
        _STATE["backend"] = backend
        _STATE["healthy"] = bool(ok)
        if ok:
            _STATE["failures"] = 0
            _STATE["circuit_until"] = 0.0
            _STATE["last_error"] = ""
        else:
            _STATE["failures"] = int(_STATE["failures"] or 0) + 1
            _STATE["last_error"] = str(error or "database_unreachable")[:120]
            _STATE["circuit_until"] = now + CIRCUIT_SECONDS
        return dict(_STATE)


def can_persist(server) -> bool:
    return bool(health(server).get("healthy"))


def public_status(server) -> dict:
    state = health(server)
    return {
        "ok": bool(state.get("healthy")),
        "database": "up" if state.get("healthy") else "down",
        "backend": state.get("backend") or "unconfigured",
        "circuit_open": bool(float(state.get("circuit_until") or 0) > time.monotonic()),
    }
