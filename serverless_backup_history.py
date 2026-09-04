"""Serverless-safe backup history endpoint for BININGA.

On Vercel, local backup folders live under /tmp and are not durable.  The admin
therefore lists successful downloaded archives from durable database metadata
instead of temporary filesystem folders.
"""
from __future__ import annotations

import os

_ROUTE = "/api/backups"
_HISTORY_KEY = "backup_history"


def _is_serverless() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def guard_request(server, handler) -> bool:
    path = str(getattr(handler, "path", "")).split("?", 1)[0]
    method = str(getattr(handler, "command", "GET")).upper()
    if method != "GET" or path != _ROUTE or not _is_serverless():
        return True

    token = str(handler.headers.get("X-Admin-Token", "") or "")
    session = server.get_session(token) if token else None
    if not session:
        handler._json({"ok": False, "message": "Non autorisé"}, 401)
        return False
    if session.get("role") not in ("admin", "ministre"):
        handler._json({"ok": False, "message": "Non autorisé"}, 403)
        return False

    loader = getattr(server, "_pg_load", None)
    try:
        rows = loader(_HISTORY_KEY) if callable(loader) else []
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []
    clean = [row for row in rows if isinstance(row, dict)]
    backups = list(reversed(clean[-50:]))
    latest = backups[0] if backups else None

    db_label = "base configurée"
    label_fn = getattr(server, "_db_label", None)
    if callable(label_fn):
        try:
            db_label = label_fn()
        except Exception:
            pass

    handler._json({
        "ok": True,
        "backups": backups,
        "latest": latest,
        "count": len(backups),
        "database": db_label,
        "storage": {
            "durable": False,
            "history_durable": True,
            "mode": "download",
            "label": "archives téléchargées — historique persistant",
        },
    })
    return False
