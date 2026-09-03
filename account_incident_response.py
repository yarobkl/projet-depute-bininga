"""Incident-response controls for authenticated BININGA accounts.

Adds server-side session inventory/revocation and enforces stronger controls on
Owners. This is deliberately small and auditable: session data returned to the
browser never includes bearer tokens.
"""
from __future__ import annotations

import hashlib
import json
import time

import admin_owners


SESSIONS_PATH = "/api/auth/sessions"
REVOKE_ALL_PATH = "/api/auth/revoke-sessions"


def _path(handler) -> str:
    return str(getattr(handler, "path", "")).split("?", 1)[0]


def _session(server, handler):
    token = str(handler.headers.get("X-Admin-Token", "") or "")
    return (server.get_session(token) if token else None), token


def _csrf_ok(session: dict, handler) -> bool:
    expected = str(session.get("csrf_token", "") or "")
    received = str(handler.headers.get("X-CSRF-Token", "") or "")
    if not expected or not received:
        return False
    import secrets
    return secrets.compare_digest(expected, received)


def _fingerprint(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()[:12]


def _session_rows(server, username: str, current_token: str) -> list[dict]:
    rows = []
    sessions = getattr(server, "ACTIVE_SESSIONS", {})
    if not isinstance(sessions, dict):
        return rows
    now = time.time()
    for token, item in sessions.items():
        if not isinstance(item, dict) or item.get("username") != username:
            continue
        rows.append({
            "id": _fingerprint(token),
            "current": bool(token == current_token),
            "created_at": item.get("created_at", ""),
            "expires_at": item.get("expires_at", ""),
            "ip": item.get("ip", item.get("client_ip", "")),
            "user_agent": str(item.get("user_agent", ""))[:180],
            "expired": bool(isinstance(item.get("expires_at"), (int, float)) and item.get("expires_at") < now),
        })
    return rows


def _revoke_other_sessions(server, username: str, keep_token: str = "") -> int:
    sessions = getattr(server, "ACTIVE_SESSIONS", {})
    if not isinstance(sessions, dict):
        return 0
    removed = 0
    for token, item in list(sessions.items()):
        if token == keep_token:
            continue
        if isinstance(item, dict) and item.get("username") == username:
            sessions.pop(token, None)
            removed += 1
    saver = getattr(server, "save_sessions", None)
    if callable(saver):
        try:
            saver()
        except Exception:
            pass
    return removed


def guard_request(server, handler):
    path = _path(handler)
    method = str(getattr(handler, "command", "GET")).upper()
    if path not in {SESSIONS_PATH, REVOKE_ALL_PATH}:
        return True

    session, token = _session(server, handler)
    if not session:
        handler._json({"ok": False, "message": "Session expirée"}, 401)
        return False

    username = str(session.get("username") or "")
    if method == "GET" and path == SESSIONS_PATH:
        handler._json({"ok": True, "sessions": _session_rows(server, username, token)})
        return False

    if method == "POST" and path == REVOKE_ALL_PATH:
        if not _csrf_ok(session, handler):
            handler._json({"ok": False, "message": "Requête invalide (CSRF)"}, 403)
            return False
        removed = _revoke_other_sessions(server, username, keep_token=token)
        try:
            server.audit_log("SESSIONS_REVOKED", handler.client_address[0], f"{removed} session(s) révoquée(s) pour {username}")
        except Exception:
            pass
        handler._json({"ok": True, "revoked": removed, "message": "Les autres sessions ont été déconnectées."})
        return False

    return True


def owner_security_status(server, session: object) -> dict:
    """Small status surface consumed by admin UI/tests."""
    is_owner = admin_owners.is_owner_session(server, session)
    return {
        "is_owner": is_owner,
        "two_factor_expected": bool(is_owner),
        "has_2fa": bool(isinstance(session, dict) and session.get("has_2fa", False)),
    }
