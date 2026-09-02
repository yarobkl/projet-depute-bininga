"""BININGA multi-owner authorization policy.

The administration has exactly two business owners by email. Owner is an
authorization level layered on top of the legacy ``admin`` role so existing
role checks remain fully compatible.
"""
from __future__ import annotations

import os
import secrets

_DEFAULT_OWNER_EMAILS = (
    "rodrinbakala@outlook.fr",
    "eliebakala@gmail.com",
)
_OWNER_MARKER_KEY = "admin_owners_20260902_v1"


def owner_emails() -> tuple[str, ...]:
    raw = os.environ.get("BININGA_OWNER_EMAILS", "").strip()
    values = [item.strip().lower() for item in raw.split(",") if item.strip()] if raw else list(_DEFAULT_OWNER_EMAILS)
    unique = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    return tuple(unique[:2])


def _users(server) -> list[dict]:
    try:
        users = server.load_users()
        return [dict(user) for user in users if isinstance(user, dict)] if isinstance(users, list) else []
    except Exception:
        return []


def user_email(user: dict) -> str:
    return str(user.get("email") or "").strip().lower()


def is_owner_user(user: dict | None) -> bool:
    return isinstance(user, dict) and user_email(user) in set(owner_emails())


def user_for_session(server, session: dict | None) -> dict | None:
    if not isinstance(session, dict):
        return None
    username = str(session.get("username") or "")
    return next((user for user in _users(server) if str(user.get("username") or "") == username), None)


def is_owner_session(server, session: dict | None) -> bool:
    return is_owner_user(user_for_session(server, session))


def is_owner_username(server, username: str) -> bool:
    wanted = str(username or "")
    user = next((item for item in _users(server) if str(item.get("username") or "") == wanted), None)
    return is_owner_user(user)


def resolve_login_identifier(server, identifier: str) -> str:
    value = str(identifier or "").strip()
    if "@" not in value:
        return value
    wanted = value.lower()
    user = next((item for item in _users(server) if user_email(item) == wanted), None)
    return str(user.get("username") or value) if user else value


def _marker_present(server) -> bool:
    loader = getattr(server, "_pg_load", None)
    if not callable(loader):
        return False
    try:
        value = loader(_OWNER_MARKER_KEY)
        return isinstance(value, dict) and value.get("done") is True
    except Exception:
        return False


def _write_marker(server) -> None:
    saver = getattr(server, "_pg_save", None)
    if callable(saver):
        try:
            saver(_OWNER_MARKER_KEY, {"done": True, "owners": list(owner_emails())})
        except Exception:
            pass


def ensure_owner_accounts(server) -> None:
    """Persist the two owner identities while preserving the current admin secret.

    If the historical ADMIN_USER exists, its current password hash is retained
    and the account becomes the first owner. A missing second owner starts with
    the same *hash* only as a migration bridge and is forced to choose a unique
    password on first login. No plaintext credential is copied or logged.
    """
    if _marker_present(server):
        return
    emails = owner_emails()
    if len(emails) != 2:
        raise RuntimeError("BININGA requires exactly two owner emails")

    users = _users(server)
    admin_username = str(getattr(server, "ADMIN_USER", "admin") or "admin")
    changed = False

    by_email = {user_email(user): user for user in users if user_email(user)}
    first = by_email.get(emails[0])
    if not first:
        first = next((user for user in users if str(user.get("username") or "") == admin_username), None)
        if first:
            first["email"] = emails[0]
            first["nom"] = first.get("nom") or "Rodrin Bakala"
            changed = True
        else:
            first = {
                "username": admin_username,
                "email": emails[0],
                "password_hash": server._hash_new(secrets.token_urlsafe(48)),
                "role": "admin",
                "nom": "Rodrin Bakala",
                "must_change_password": True,
            }
            users.append(first)
            changed = True

    bridge_hash = str(first.get("password_hash") or "") or server._hash_new(secrets.token_urlsafe(48))
    by_email = {user_email(user): user for user in users if user_email(user)}
    second = by_email.get(emails[1])
    if not second:
        second = {
            "username": emails[1],
            "email": emails[1],
            "password_hash": bridge_hash,
            "role": "admin",
            "nom": "Elie Bakala",
            "must_change_password": True,
            "password_changed_at": "",
        }
        users.append(second)
        changed = True

    for user in users:
        email = user_email(user)
        if email in emails:
            if user.get("role") != "admin":
                user["role"] = "admin"
                changed = True
            user["owner"] = True
        else:
            if user.get("role") == "owner":
                user["role"] = "admin"
                changed = True
            user.pop("owner", None)

    if changed:
        server.save_users(users)
    _write_marker(server)


def owner_summary(server) -> list[dict]:
    users = _users(server)
    result = []
    for email in owner_emails():
        user = next((item for item in users if user_email(item) == email), None)
        result.append({
            "email": email,
            "username": str((user or {}).get("username") or ""),
            "active": bool(user),
            "must_change_password": bool((user or {}).get("must_change_password", False)),
        })
    return result
