"""BININGA multi-owner authorization policy.

The administration has exactly two business owners by email. This module
centralizes owner recognition so every privileged endpoint uses the same rule.
"""
from __future__ import annotations

import json
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
    if not isinstance(user, dict):
        return False
    return user_email(user) in set(owner_emails())


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
    """Persist exactly the two configured owner identities without resetting passwords.

    The existing ADMIN_USER account is assigned to the first owner when it has
    no owner email yet, preserving its current password. A missing second owner
    receives a random unknown credential and must activate the account through
    the password-reset flow.
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
            changed = True
        else:
            first = {
                "username": admin_username,
                "email": emails[0],
                "password_hash": server._hash_new(secrets.token_urlsafe(48)),
                "nom": "Rodrin Bakala",
                "must_change_password": True,
            }
            users.append(first)
            changed = True

    by_email = {user_email(user): user for user in users if user_email(user)}
    second = by_email.get(emails[1])
    if not second:
        second = {
            "username": emails[1],
            "email": emails[1],
            "password_hash": server._hash_new(secrets.token_urlsafe(48)),
            "nom": "Elie Bakala",
            "must_change_password": True,
        }
        users.append(second)
        changed = True

    for user in users:
        email = user_email(user)
        desired_role = "owner" if email in emails else ("admin" if user.get("role") == "owner" else user.get("role", "lecteur"))
        if user.get("role") != desired_role:
            user["role"] = desired_role
            changed = True
        if email in emails:
            user["owner"] = True
        else:
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
