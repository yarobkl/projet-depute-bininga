"""Additional contracts for permissions and incident-response behavior."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import admin_permissions


class FakeServer:
    ADMIN_USER = "legacy-admin"
    def __init__(self): self.users = []
    def load_users(self): return self.users


def test_role_baselines_and_owner_override():
    server = FakeServer(); collab = {"username": "reader", "role": "lecteur", "email": "reader@example.test", "owner_managed": True}; server.users = [collab]
    perms = admin_permissions.permissions_for_user(server, collab)
    assert "content.read" in perms and "security.manage" not in perms


def test_explicit_grants_and_revocations_apply_to_collaborator():
    server = FakeServer(); collab = {"username": "editor", "role": "editeur", "email": "editor@example.test", "owner_managed": True, "permission_grants": ["crm.read"], "permission_revokes": ["content.publish"]}; server.users = [collab]
    perms = admin_permissions.permissions_for_user(server, collab)
    assert "crm.read" in perms and "content.publish" not in perms


def test_unknown_permissions_are_dropped():
    user = {}; admin_permissions.apply_owner_managed_permissions(user, ["crm.read", "root.shell"], ["security.manage", "godmode"])
    assert user["permission_grants"] == ["crm.read"] and user["permission_revokes"] == ["security.manage"]


if __name__ == "__main__":
    tests=[fn for name,fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests: test(); print("OK",test.__name__)
    print(f"{len(tests)} tests permissions validés")
