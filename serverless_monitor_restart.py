"""Serverless-safe restart bridge for the YARO IA news monitor.

On long-lived hosts the legacy ``/api/monitor-restart`` route can restart
``monitor.py`` as a subprocess. Vercel functions cannot keep that background
process alive, so the same action must execute one bounded monitoring cycle
inline instead of spawning a daemon.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

ROUTE = "/api/monitor-restart"


def _is_vercel() -> bool:
    """Return True only inside a Vercel runtime."""
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def _client_ip(handler) -> str:
    try:
        return str(handler.client_address[0])
    except Exception:
        return "unknown"


def guard_request(server, handler) -> bool:
    """Handle monitor restart safely on Vercel; defer elsewhere.

    Returning ``False`` tells the central request pipeline that the response
    has already been produced. On non-Vercel hosts the legacy server route is
    left untouched so process-based monitoring continues to work there.
    """
    path = str(getattr(handler, "path", "")).split("?", 1)[0]
    method = str(getattr(handler, "command", "GET")).upper()
    if method != "POST" or path != ROUTE or not _is_vercel():
        return True

    token = str(handler.headers.get("X-Admin-Token", "") or "")
    session = server.get_session(token) if token else None
    if not session:
        handler._json({"ok": False, "message": "Non autorisé"}, 401)
        return False
    if session.get("role") != "admin":
        handler._json({"ok": False, "message": "Non autorisé"}, 403)
        return False

    csrf_received = str(handler.headers.get("X-CSRF-Token", "") or "")
    csrf_expected = str(session.get("csrf_token", "") or "")
    if not csrf_expected or not secrets.compare_digest(csrf_received, csrf_expected):
        try:
            server.audit_log("CSRF_REJECT", _client_ip(handler), f"Token CSRF invalide sur {ROUTE}")
        except Exception:
            pass
        handler._json({"ok": False, "message": "Requête invalide (CSRF)"}, 403)
        return False

    try:
        data = server.load_news()
        if getattr(server, "BININGA_TEST", False):
            nouveaux = []
        else:
            import veille_serverless
            nouveaux = veille_serverless.run_news_quick(data, "", budget_s=8.0)

        if nouveaux:
            data.setdefault("items", []).extend(nouveaux)
        data["last_run"] = datetime.now(timezone.utc).isoformat()
        stats = data.setdefault("stats", {"total_found": 0, "runs": 0})
        stats["total_found"] = int(stats.get("total_found") or 0) + len(nouveaux)
        stats["runs"] = int(stats.get("runs") or 0) + 1
        server.save_news(data)

        message = f"YARO IA relancé en mode serverless : {len(nouveaux)} nouvel(aux) article(s)"
        server.audit_log("SAVE", _client_ip(handler), message)
        handler._json({"ok": True, "message": message, "found": len(nouveaux), "mode": "serverless"})
    except Exception as exc:
        handler._json({"ok": False, "message": str(exc)}, 500)
    return False
