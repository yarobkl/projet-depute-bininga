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
    """Run a real database round-trip without mutating application data."""
    backend = _backend(server)
    if not backend:
        return False, "database_not_configured"
    connector = getattr(server, "_pg", None)
    if not callable(connector):
        return False, "persistent_connection_unavailable"
    try:
        conn = connector()
        if not conn:
            return False, "database_unreachable"
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
        if not row or int(row[0]) != 1:
            return False, "unexpected_probe_result"
        return True, ""
    except Exception as exc:
        # Force the legacy connection helper to reconnect on the next probe.
        try:
            local = getattr(server, "_pg_local", None)
            if local is not None:
                local.conn = None
        except Exception:
            pass
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
