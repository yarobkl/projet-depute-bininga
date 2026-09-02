"""Owner + collaborator access model for the BININGA administration.

Rules enforced here:
- exactly the two reserved email identities can become Owner;
- first Owner activation is a public email-verification flow and disappears once
  both reserved identities are active;
- only an Owner can create/update/delete collaborator accounts;
- collaborator roles are delegated permissions, never Owner privileges;
- collaborator accounts created by an Owner may use a username/password without
  requiring a public recovery email;
- historical non-owner accounts are denied until an Owner explicitly saves them.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from typing import Optional

import admin_auth_flow
import admin_owners


BOOTSTRAP_STATUS_PATH = "/api/auth/bootstrap-status"
FIRST_LOGIN_PATH = "/api/auth/first-login"
_PLACEHOLDER_DOMAIN = "accounts.bininga.invalid"


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


def _replace_request_body(handler, payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.rfile = io.BytesIO(encoded)
    try:
        if handler.headers.get("Content-Length") is not None:
            handler.headers.replace_header("Content-Length", str(len(encoded)))
        else:
            handler.headers["Content-Length"] = str(len(encoded))
    except Exception:
        pass


def _response_json(handler) -> Optional[dict]:
    try:
        raw = handler.wfile.getvalue()
        payload = json.loads(raw.decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _replace_response_json(handler, payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.wfile.seek(0)
    handler.wfile.truncate(0)
    handler.wfile.write(encoded)
    handler._response_headers = [
        (key, value) for key, value in getattr(handler, "_response_headers", [])
        if str(key).lower() not in {"content-length", "content-type"}
    ]
    handler._response_headers.append(("Content-Type", "application/json; charset=utf-8"))
    handler._response_headers.append(("Content-Length", str(len(encoded))))


def _session(server, handler):
    token = str(handler.headers.get("X-Admin-Token", "") or "")
    return server.get_session(token) if token else None


def _find_user(server, identifier: object):
    wanted = str(identifier or "").strip()
    wanted_email = wanted.lower()
    try:
        users = server.load_users()
    except Exception:
        return None
    if not isinstance(users, list):
        return None
    return next(
        (
            user for user in users
            if isinstance(user, dict)
            and (
                str(user.get("username") or "") == wanted
                or str(user.get("email") or "").strip().lower() == wanted_email
            )
        ),
        None,
    )


def _placeholder_email(username: str) -> str:
    digest = hashlib.sha256(username.encode("utf-8")).hexdigest()[:24]
    return f"collab-{digest}@{_PLACEHOLDER_DOMAIN}"


def _hidden_recovery_email(user: object) -> bool:
    return bool(isinstance(user, dict) and user.get("email_hidden", False))


def _generic_first_login_message() -> dict:
    return {
        "ok": True,
        "message": "Si cette adresse correspond à un propriétaire BININGA non encore activé, un email de première connexion vient d’être envoyé.",
    }


def _handle_bootstrap_status(server, handler) -> bool:
    handler._json({
        "ok": True,
        "first_login_available": admin_owners.first_login_available(server),
    })
    return False


def _handle_first_login(server, handler) -> bool:
    if not admin_owners.first_login_available(server):
        handler._json({
            "ok": False,
            "first_login_available": False,
            "message": "Les deux comptes propriétaires sont déjà activés. Utilisez « Mot de passe oublié ? » si nécessaire.",
        }, 410)
        return False

    payload = _body(handler)
    email = str(payload.get("email") or payload.get("identifier") or "").strip()
    if not admin_owners.is_designated_owner_email(email):
        handler._json(_generic_first_login_message())
        return False

    existing = admin_owners.find_user_by_email(server, email)
    if existing and admin_owners.is_active_designated_owner_user(existing):
        handler._json(_generic_first_login_message())
        return False

    _replace_request_body(handler, {"identifier": email})
    return admin_auth_flow._handle_forgot(server, handler)


def _guard_login(server, handler) -> bool:
    payload = _body(handler)
    identifier = str(payload.get("username") or "").strip()
    if not identifier:
        return True

    user = _find_user(server, identifier)
    if not user:
        return True

    if admin_owners.is_designated_owner_user(user):
        return True

    if not bool(user.get("owner_managed", False)):
        server.audit_log(
            "LOGIN_REJECT_UNMANAGED",
            handler.client_address[0],
            f"Compte non-owner non validé par un Owner : {user.get('username', '?')}",
        )
        handler._json({"ok": False, "message": "Identifiant ou mot de passe incorrect."}, 401)
        return False

    return True


def _guard_forgot_password(server, handler) -> bool:
    payload = _body(handler)
    identifier = str(payload.get("identifier") or payload.get("email") or payload.get("username") or "").strip()
    user = _find_user(server, identifier)
    if user and not admin_owners.is_designated_owner_user(user):
        if not bool(user.get("owner_managed", False)) or _hidden_recovery_email(user):
            handler._json({
                "ok": True,
                "message": "Si un compte correspond à ces informations, un email de réinitialisation vient d’être envoyé.",
            })
            return False
    return True


def _guard_collaborator_upsert(server, handler) -> bool:
    session = _session(server, handler)
    if not session or not admin_owners.is_owner_session(server, session):
        return True  # the authoritative auth flow will emit the normal 401/403

    payload = _body(handler)
    username = str(payload.get("username") or "").strip()
    email = str(payload.get("email") or "").strip().lower()

    if admin_owners.is_designated_owner_email(username) or admin_owners.is_designated_owner_email(email):
        handler._json({
            "ok": False,
            "message": "Les deux comptes Owner sont réservés. Leur activation et leur mot de passe se gèrent uniquement depuis les parcours Owner.",
        }, 403)
        return False

    if not username:
        return True

    hidden_email = not bool(email)
    if hidden_email:
        payload["email"] = _placeholder_email(username)
        _replace_request_body(handler, payload)

    handler._bininga_collaborator_username = username
    handler._bininga_collaborator_hidden_email = hidden_email
    handler._bininga_collaborator_manager = str(session.get("username") or "")
    return True


def guard_request(server, handler):
    path = _path(handler)
    method = str(getattr(handler, "command", "GET")).upper()

    if method == "GET" and path == BOOTSTRAP_STATUS_PATH:
        return _handle_bootstrap_status(server, handler)

    if method == "POST" and path == FIRST_LOGIN_PATH:
        return _handle_first_login(server, handler)

    if method == "POST" and path == "/api/login":
        return _guard_login(server, handler)

    if method == "POST" and path == "/api/auth/forgot-password":
        if _guard_forgot_password(server, handler) is False:
            return False

    if method == "POST" and path == "/api/users/upsert":
        if _guard_collaborator_upsert(server, handler) is False:
            return False

    return True


def _postprocess_collaborator_upsert(server, handler) -> None:
    username = str(getattr(handler, "_bininga_collaborator_username", "") or "")
    if not username or int(getattr(handler, "_status_code", 200)) != 200:
        return
    payload = _response_json(handler)
    if not payload or not payload.get("ok"):
        return

    users = server.load_users()
    target = next((u for u in users if isinstance(u, dict) and u.get("username") == username), None)
    if not target or admin_owners.is_designated_owner_user(target):
        return

    target["owner_managed"] = True
    target["managed_by"] = str(getattr(handler, "_bininga_collaborator_manager", "") or "")
    target["email_hidden"] = bool(getattr(handler, "_bininga_collaborator_hidden_email", False))
    # The password chosen by an Owner is the collaborator's active credential.
    # The public "Première connexion" flow belongs only to the two Owners.
    target["must_change_password"] = False
    server.save_users(users)

    payload["owner_managed"] = True
    payload["must_change_password"] = False
    _replace_response_json(handler, payload)


def _postprocess_users_meta(server, handler) -> None:
    if int(getattr(handler, "_status_code", 200)) != 200:
        return
    payload = _response_json(handler)
    if not payload or not payload.get("ok") or not isinstance(payload.get("users"), list):
        return

    store = {
        str(user.get("username") or ""): user
        for user in server.load_users()
        if isinstance(user, dict)
    }
    for row in payload["users"]:
        if not isinstance(row, dict):
            continue
        stored = store.get(str(row.get("username") or ""), {})
        row["owner_managed"] = bool(stored.get("owner_managed", False))
        if stored.get("email_hidden"):
            row["email"] = ""

    payload["first_login_available"] = admin_owners.first_login_available(server)
    _replace_response_json(handler, payload)


def postprocess_response(server, handler) -> None:
    path = _path(handler)
    method = str(getattr(handler, "command", "GET")).upper()
    if method == "POST" and path == "/api/users/upsert":
        _postprocess_collaborator_upsert(server, handler)
    elif method == "GET" and path == "/api/auth/users-meta":
        _postprocess_users_meta(server, handler)
