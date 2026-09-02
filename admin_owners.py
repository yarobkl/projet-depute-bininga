"""Authoritative two-owner policy for the BININGA administration.

The repository is public, so the owners' email addresses are deliberately not
stored in clear text here. Ownership is matched against SHA-256 fingerprints of
normalized email addresses.

Exactly two designated identities can ever become Owner. Other administration
accounts may be created by an Owner and receive delegated roles, but a username
or the legacy ``ADMIN_USER`` value alone never grants Owner privileges.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone


# SHA-256(normalized_email). Do not replace these with plaintext addresses.
_OWNER_EMAIL_SHA256 = frozenset({
    "cb127353222654d317816f817a1b3c401faa9877d22d54d1f0f38c818b0ab545",
    "02a930477769090baa89da084f1737a68bef6205d711f432c3622e809b597225",
})


def normalize_email(value: object) -> str:
    return str(value or "").strip().lower()


def email_fingerprint(value: object) -> str:
    normalized = normalize_email(value)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_designated_owner_email(value: object) -> bool:
    fingerprint = email_fingerprint(value)
    return bool(fingerprint and fingerprint in _OWNER_EMAIL_SHA256)


def is_designated_owner_user(user: object) -> bool:
    return isinstance(user, dict) and is_designated_owner_email(user.get("email"))


def is_active_designated_owner_user(user: object) -> bool:
    return bool(
        is_designated_owner_user(user)
        and not bool(user.get("owner_pending", False))
    )


def active_designated_owners(server) -> list[dict]:
    try:
        users = server.load_users()
    except Exception:
        return []
    if not isinstance(users, list):
        return []
    return [u for u in users if is_active_designated_owner_user(u)]


def find_user_by_username(server, username: object):
    wanted = str(username or "")
    if not wanted:
        return None
    try:
        users = server.load_users()
    except Exception:
        return None
    return next((u for u in users if isinstance(u, dict) and u.get("username") == wanted), None)


def find_user_by_email(server, email: object):
    wanted = normalize_email(email)
    if not wanted:
        return None
    try:
        users = server.load_users()
    except Exception:
        return None
    return next(
        (
            u for u in users
            if isinstance(u, dict) and normalize_email(u.get("email")) == wanted
        ),
        None,
    )


def is_owner_user(server, user: object) -> bool:
    """Only an activated designated owner identity has Owner privileges."""
    return is_active_designated_owner_user(user)


def is_owner_session(server, session: object) -> bool:
    if not isinstance(session, dict):
        return False
    user = find_user_by_username(server, session.get("username"))
    return bool(user and is_owner_user(server, user))


def is_protected_owner_user(user: object) -> bool:
    """Designated owner identities cannot be deleted or reassigned."""
    return is_designated_owner_user(user)


def provision_pending_owner(server, email: object):
    """Create one of the two reserved Owner accounts for first activation.

    No usable temporary password is exposed. A random password hash is stored
    and the designated email must complete the one-time password link before
    the account becomes an active Owner.
    """
    normalized = normalize_email(email)
    if not is_designated_owner_email(normalized):
        return None

    users = server.load_users()
    if not isinstance(users, list):
        users = []

    existing = next(
        (
            u for u in users
            if isinstance(u, dict) and normalize_email(u.get("email")) == normalized
        ),
        None,
    )
    if existing:
        changed = False
        if existing.get("role") != "admin":
            existing["role"] = "admin"
            changed = True
        existing["owner_reserved"] = True
        if changed:
            server.save_users(users)
        return existing

    username = normalized
    if any(isinstance(u, dict) and u.get("username") == username for u in users):
        return None

    user = {
        "username": username,
        "password_hash": server._hash_new(secrets.token_urlsafe(48)),
        "role": "admin",
        "nom": "Propriétaire BININGA",
        "email": normalized,
        "created_by": "owner-first-login",
        "must_change_password": True,
        "password_changed_at": "",
        "owner_pending": True,
        "owner_reserved": True,
        "owner_activated_at": "",
    }
    users.append(user)
    server.save_users(users)
    return user


def activate_owner_fields(user: dict) -> None:
    """Mark a designated owner as active after a successful password setup."""
    if not is_designated_owner_user(user):
        return
    user["role"] = "admin"
    user["owner_pending"] = False
    user["owner_reserved"] = True
    user["owner_activated_at"] = datetime.now(timezone.utc).isoformat()


def owner_count(server) -> int:
    return len(active_designated_owners(server))


def owner_slots() -> int:
    return len(_OWNER_EMAIL_SHA256)


def first_login_available(server) -> bool:
    return owner_count(server) < owner_slots()
