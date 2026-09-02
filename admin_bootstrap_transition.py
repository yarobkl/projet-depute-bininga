"""One-time migration bridge from the historical admin to reserved Owners.

This is deliberately not a third permanent Owner. It only keeps the existing
ADMIN_USER usable while zero designated Owners are active. As soon as the first
reserved Owner completes activation, new legacy logins are rejected and any
legacy session is invalidated before another admin API can run.
"""
from __future__ import annotations

import json

import admin_owners


def _path(handler) -> str:
    return str(getattr(handler, "path", "")).split("?", 1)[0]


def _body(handler) -> dict:
    raw = getattr(handler, "rfile", None)
    if raw is None:
        return {}
    try:
        data = raw.getvalue() if hasattr(raw, "getvalue") else raw.read()
        parsed = json.loads(data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _legacy_username(server) -> str:
    return str(getattr(server, "ADMIN_USER", "admin") or "admin")


def _active_owner_exists(server) -> bool:
    return bool(admin_owners.active_designated_owners(server))


def _ensure_bootstrap_user_is_temporarily_managed(server) -> None:
    username = _legacy_username(server)
    try:
        users = server.load_users()
    except Exception:
        return
    if not isinstance(users, list):
        return
    target = next((u for u in users if isinstance(u, dict) and u.get("username") == username), None)
    if not target or admin_owners.is_designated_owner_user(target):
        return
    if target.get("owner_managed") and target.get("bootstrap_legacy"):
        return
    target["owner_managed"] = True
    target["bootstrap_legacy"] = True
    target["managed_by"] = "migration-bootstrap"
    try:
        server.save_users(users)
    except Exception:
        pass


def _invalidate_legacy_session(server, token: str) -> None:
    sessions = getattr(server, "ACTIVE_SESSIONS", {})
    if isinstance(sessions, dict) and token:
        sessions.pop(token, None)
    saver = getattr(server, "save_sessions", None)
    if callable(saver):
        try:
            saver()
        except Exception:
            pass


def guard_request(server, handler):
    path = _path(handler)
    method = str(getattr(handler, "command", "GET")).upper()
    legacy = _legacy_username(server)
    owners_active = _active_owner_exists(server)

    if method == "POST" and path == "/api/login":
        identifier = str(_body(handler).get("username") or "").strip()
        if identifier == legacy:
            if owners_active:
                handler._json({"ok": False, "message": "Identifiant ou mot de passe incorrect."}, 401)
                return False
            _ensure_bootstrap_user_is_temporarily_managed(server)
            return True

    if owners_active and path.startswith("/api/"):
        token = str(handler.headers.get("X-Admin-Token", "") or "")
        session = server.get_session(token) if token else None
        if isinstance(session, dict) and session.get("username") == legacy:
            _invalidate_legacy_session(server, token)
            handler._json({"ok": False, "message": "Session de migration terminée. Connectez-vous avec un compte Owner."}, 401)
            return False

    return True
