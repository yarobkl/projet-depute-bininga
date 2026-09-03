"""Granular permission policy for BININGA administration.

Owners always receive every permission. Collaborators receive a role baseline
plus optional Owner-managed grants/revocations. The server remains authoritative:
front-end visibility is only a convenience layer.
"""
from __future__ import annotations

import admin_owners


ALL_PERMISSIONS = frozenset({
    "content.read", "content.write", "content.publish",
    "contacts.read", "contacts.write", "contacts.assign",
    "crm.read", "crm.write", "crm.export",
    "users.read", "users.create", "users.update", "users.delete",
    "backup.read", "backup.create", "backup.download",
    "security.read", "security.manage",
    "monitoring.read", "monitoring.manage",
    "logs.read",
    "chatbot.manage",
})

ROLE_PERMISSIONS = {
    "lecteur": frozenset({"content.read", "contacts.read"}),
    "ministre": frozenset({"content.read", "contacts.read", "contacts.write", "crm.read"}),
    "editeur": frozenset({
        "content.read", "content.write", "content.publish",
        "contacts.read", "contacts.write",
    }),
    "admin": frozenset({
        "content.read", "content.write", "content.publish",
        "contacts.read", "contacts.write", "contacts.assign",
        "crm.read", "crm.write", "crm.export",
        "monitoring.read", "logs.read",
    }),
}


def normalize_permission_list(value) -> set[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return set()
    return {str(item) for item in value if str(item) in ALL_PERMISSIONS}


def permissions_for_user(server, user: object) -> frozenset[str]:
    if not isinstance(user, dict):
        return frozenset()
    if admin_owners.is_owner_user(server, user):
        return ALL_PERMISSIONS
    base = set(ROLE_PERMISSIONS.get(str(user.get("role") or "lecteur"), frozenset()))
    grants = normalize_permission_list(user.get("permission_grants"))
    revokes = normalize_permission_list(user.get("permission_revokes"))
    return frozenset((base | grants) - revokes)


def permissions_for_session(server, session: object) -> frozenset[str]:
    if not isinstance(session, dict):
        return frozenset()
    user = admin_owners.find_user_by_username(server, session.get("username"))
    return permissions_for_user(server, user)


def has_permission(server, session: object, permission: str) -> bool:
    return str(permission) in permissions_for_session(server, session)


def apply_owner_managed_permissions(user: dict, grants=None, revokes=None) -> None:
    if not isinstance(user, dict):
        return
    user["permission_grants"] = sorted(normalize_permission_list(grants))
    user["permission_revokes"] = sorted(normalize_permission_list(revokes))
