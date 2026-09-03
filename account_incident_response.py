"""Incident-response controls for authenticated BININGA accounts.

Adds server-side session inventory/revocation and enforces 2FA before high-impact
Owner operations. Session data returned to the browser never includes bearer tokens.
"""
from __future__ import annotations

import hashlib
import secrets
import time

import admin_owners

SESSIONS_PATH = "/api/auth/sessions"
REVOKE_ALL_PATH = "/api/auth/revoke-sessions"
_OWNER_2FA_EXEMPT = {
    "/api/2fa/status", "/api/2fa/setup", "/api/2fa/activate", "/api/2fa/disable",
    "/api/auth/session", "/api/auth/sessions", "/api/auth/revoke-sessions", "/api/logout",
}
_HIGH_IMPACT_PREFIXES = (
    "/api/users", "/api/security", "/api/backups", "/api/crm/export",
    "/api/monitoring/", "/api/ia/key",
)


def _path(handler) -> str:
    return str(getattr(handler, "path", "")).split("?", 1)[0]


def _session(server, handler):
    token = str(handler.headers.get("X-Admin-Token", "") or "")
    return (server.get_session(token) if token else None), token


def _csrf_ok(session: dict, handler) -> bool:
    expected = str(session.get("csrf_token", "") or "")
    received = str(handler.headers.get("X-CSRF-Token", "") or "")
    return bool(expected and received and secrets.compare_digest(expected, received))


def _fingerprint(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()[:12]


def _session_rows(server, username: str, current_token: str) -> list[dict]:
    rows = []; sessions = getattr(server, "ACTIVE_SESSIONS", {})
    if not isinstance(sessions, dict): return rows
    now = time.time()
    for token, item in sessions.items():
        if not isinstance(item, dict) or item.get("username") != username: continue
        rows.append({
            "id": _fingerprint(token), "current": bool(token == current_token),
            "created_at": item.get("created_at", ""), "expires_at": item.get("expires_at", ""),
            "ip": item.get("ip", item.get("client_ip", "")), "user_agent": str(item.get("user_agent", ""))[:180],
            "expired": bool(isinstance(item.get("expires_at"), (int, float)) and item.get("expires_at") < now),
        })
    return rows


def _revoke_other_sessions(server, username: str, keep_token: str = "") -> int:
    sessions = getattr(server, "ACTIVE_SESSIONS", {})
    if not isinstance(sessions, dict): return 0
    removed = 0
    for token, item in list(sessions.items()):
        if token == keep_token: continue
        if isinstance(item, dict) and item.get("username") == username:
            sessions.pop(token, None); removed += 1
    saver = getattr(server, "save_sessions", None)
    if callable(saver):
        try: saver()
        except Exception: pass
    return removed


def _owner_has_2fa(server, session: dict) -> bool:
    user = admin_owners.find_user_by_username(server, session.get("username"))
    return bool(isinstance(user, dict) and user.get("totp_secret"))


def _requires_owner_2fa(path: str) -> bool:
    if path in _OWNER_2FA_EXEMPT: return False
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in _HIGH_IMPACT_PREFIXES)


def _enforce_owner_2fa(server, handler, session: object) -> bool:
    if not isinstance(session, dict) or not admin_owners.is_owner_session(server, session): return True
    path = _path(handler)
    if not _requires_owner_2fa(path) or _owner_has_2fa(server, session): return True
    try: server.audit_log("OWNER_2FA_REQUIRED", handler.client_address[0], f"Action bloquée sans 2FA : {path}")
    except Exception: pass
    handler._json({
        "ok": False, "code": "OWNER_2FA_REQUIRED", "two_factor_required": True,
        "message": "Activez l’authentification à deux facteurs avant cette opération sensible.",
    }, 428)
    return False


def guard_request(server, handler):
    path = _path(handler); method = str(getattr(handler, "command", "GET")).upper()
    session, token = _session(server, handler)

    if session and not _enforce_owner_2fa(server, handler, session):
        return False

    if path not in {SESSIONS_PATH, REVOKE_ALL_PATH}: return True
    if not session:
        handler._json({"ok": False, "message": "Session expirée"}, 401); return False
    username = str(session.get("username") or "")
    if method == "GET" and path == SESSIONS_PATH:
        handler._json({"ok": True, "sessions": _session_rows(server, username, token), "two_factor_enabled": _owner_has_2fa(server, session) if admin_owners.is_owner_session(server, session) else None}); return False
    if method == "POST" and path == REVOKE_ALL_PATH:
        if not _csrf_ok(session, handler):
            handler._json({"ok": False, "message": "Requête invalide (CSRF)"}, 403); return False
        removed = _revoke_other_sessions(server, username, keep_token=token)
        try: server.audit_log("SESSIONS_REVOKED", handler.client_address[0], f"{removed} session(s) révoquée(s) pour {username}")
        except Exception: pass
        handler._json({"ok": True, "revoked": removed, "message": "Les autres sessions ont été déconnectées."}); return False
    return True


def owner_security_status(server, session: object) -> dict:
    is_owner = admin_owners.is_owner_session(server, session)
    return {"is_owner": is_owner, "two_factor_expected": bool(is_owner), "has_2fa": bool(is_owner and isinstance(session, dict) and _owner_has_2fa(server, session))}
