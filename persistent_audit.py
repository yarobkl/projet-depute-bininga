"""Durable audit log bridge for BININGA.

Vercel uses /tmp for DATA_DIR, so ``audit.log`` alone disappears across cold
starts. This module keeps the legacy JSONL file as a local fallback while
mirroring the latest audit entries into the application's durable KV database.
"""
from __future__ import annotations

from datetime import datetime
import threading
from typing import Any

_DURABLE_KEY = "audit_log"
_MAX_DURABLE_ENTRIES = 1000
_LOCK = threading.Lock()


def _entry(action: str, ip: str = "", detail: str = "") -> dict[str, str]:
    return {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": str(action or ""),
        "ip": str(ip or ""),
        "detail": str(detail or ""),
    }


def _load_durable(server: Any) -> list[dict[str, Any]] | None:
    loader = getattr(server, "_pg_load", None)
    if not callable(loader):
        return None
    try:
        rows = loader(_DURABLE_KEY)
    except Exception:
        return None
    if rows is None:
        return None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _save_durable(server: Any, rows: list[dict[str, Any]]) -> bool:
    saver = getattr(server, "_pg_save", None)
    if not callable(saver):
        return False
    try:
        return bool(saver(_DURABLE_KEY, rows[-_MAX_DURABLE_ENTRIES:]))
    except Exception:
        return False


def install(server: Any) -> None:
    """Replace ``audit_log`` / ``load_audit`` with durable-aware versions."""
    if getattr(server, "_bininga_persistent_audit_installed", False):
        return

    legacy_write = getattr(server, "audit_log", None)
    legacy_load = getattr(server, "load_audit", None)

    def audit_log(action: str, ip: str = "", detail: str = "") -> None:
        row = _entry(action, ip, detail)
        durable_ok = False

        # Serialise writes inside one runtime. When the durable key does not
        # exist yet, seed it with the very first event instead of silently
        # falling back to Vercel's ephemeral /tmp filesystem.
        with _LOCK:
            rows = _load_durable(server)
            if rows is None:
                durable_ok = _save_durable(server, [row])
            else:
                rows.append(row)
                durable_ok = _save_durable(server, rows)

        if callable(legacy_write):
            try:
                legacy_write(action, ip, detail)
            except Exception as exc:
                # Audit must never take the application down. If the DB write
                # worked, an unavailable local filesystem is harmless.
                if not durable_ok:
                    print(f"[AUDIT] Persistance indisponible: {exc}", flush=True)

    def load_audit(limit: int = 100):
        try:
            limit_i = max(1, min(int(limit or 100), _MAX_DURABLE_ENTRIES))
        except Exception:
            limit_i = 100

        rows = _load_durable(server)
        if rows is not None:
            return list(reversed(rows[-limit_i:]))

        if callable(legacy_load):
            try:
                return legacy_load(limit_i)
            except Exception:
                return []
        return []

    server.audit_log = audit_log
    server.load_audit = load_audit
    server._bininga_persistent_audit_installed = True
