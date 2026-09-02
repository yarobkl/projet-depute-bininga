"""Security contracts for the two-owner BININGA administration model."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import admin_owners


class DummyServer:
    ADMIN_USER = "legacy-admin"

    def __init__(self, users=None):
        self.users = list(users or [])

    def load_users(self):
        return self.users

    def save_users(self, users):
        self.users = list(users)
        return True

    @staticmethod
    def _hash_new(password):
        return "hash:" + str(len(password))


def _with_test_owner_fingerprints():
    original = admin_owners._OWNER_EMAIL_SHA256
    test_email_1 = "owner-one@example.test"
    test_email_2 = "owner-two@example.test"
    admin_owners._OWNER_EMAIL_SHA256 = frozenset({
        admin_owners.email_fingerprint(test_email_1),
        admin_owners.email_fingerprint(test_email_2),
    })
    return original, test_email_1, test_email_2


def test_production_owner_policy_has_exactly_two_reserved_slots():
    assert admin_owners.owner_slots() == 2
    assert len(admin_owners._OWNER_EMAIL_SHA256) == 2
    assert all(len(value) == 64 for value in admin_owners._OWNER_EMAIL_SHA256)


def test_owner_source_does_not_publish_raw_reserved_emails():
    source = open(os.path.join(ROOT, "admin_owners.py"), "r", encoding="utf-8").read().lower()
    assert "@outlook.fr" not in source
    assert "@gmail.com" not in source
    assert "sha-256(normalized_email)" in source


def test_email_matching_is_case_insensitive():
    original, email1, _ = _with_test_owner_fingerprints()
    try:
        assert admin_owners.is_designated_owner_email(email1.upper())
        assert admin_owners.is_designated_owner_email("  " + email1 + "  ")
        assert not admin_owners.is_designated_owner_email("outsider@example.test")
    finally:
        admin_owners._OWNER_EMAIL_SHA256 = original


def test_legacy_admin_is_never_owner_without_reserved_email():
    original, _, _ = _with_test_owner_fingerprints()
    try:
        server = DummyServer([{"username": "legacy-admin", "role": "admin"}])
        assert not admin_owners.is_owner_session(server, {"username": "legacy-admin"})
    finally:
        admin_owners._OWNER_EMAIL_SHA256 = original


def test_pending_designated_owner_does_not_take_control_early():
    original, email1, _ = _with_test_owner_fingerprints()
    try:
        server = DummyServer([
            {"username": "legacy-admin", "role": "admin"},
            {"username": "pending", "email": email1, "role": "admin", "owner_pending": True},
        ])
        assert not admin_owners.is_owner_session(server, {"username": "pending"})
        assert not admin_owners.is_owner_session(server, {"username": "legacy-admin"})
    finally:
        admin_owners._OWNER_EMAIL_SHA256 = original


def test_reserved_owner_can_be_provisioned_without_usable_temporary_password():
    original, email1, _ = _with_test_owner_fingerprints()
    try:
        server = DummyServer([])
        owner = admin_owners.provision_pending_owner(server, email1.upper())
        assert owner is not None
        assert owner["email"] == email1
        assert owner["role"] == "admin"
        assert owner["must_change_password"] is True
        assert owner["owner_pending"] is True
        assert owner["owner_reserved"] is True
        assert str(owner["password_hash"]).startswith("hash:")
        assert admin_owners.owner_count(server) == 0
        assert admin_owners.first_login_available(server) is True
    finally:
        admin_owners._OWNER_EMAIL_SHA256 = original


def test_successful_password_setup_activates_designated_owner():
    original, email1, _ = _with_test_owner_fingerprints()
    try:
        user = {"username": "owner-one", "email": email1, "role": "admin", "owner_pending": True}
        admin_owners.activate_owner_fields(user)
        assert user["owner_pending"] is False
        assert user["owner_reserved"] is True
        assert user["owner_activated_at"]
        server = DummyServer([user])
        assert admin_owners.owner_count(server) == 1
        assert admin_owners.is_owner_session(server, {"username": "owner-one"})
    finally:
        admin_owners._OWNER_EMAIL_SHA256 = original


def test_first_login_disappears_after_both_reserved_owners_are_active():
    original, email1, email2 = _with_test_owner_fingerprints()
    try:
        server = DummyServer([
            {"username": "o1", "email": email1, "role": "admin", "owner_pending": False},
            {"username": "o2", "email": email2, "role": "admin", "owner_pending": False},
        ])
        assert admin_owners.owner_count(server) == 2
        assert admin_owners.first_login_available(server) is False
    finally:
        admin_owners._OWNER_EMAIL_SHA256 = original


def test_owner_sensitive_modules_use_shared_owner_authorization():
    expected = {
        "admin_auth_flow.py": "admin_owners.is_owner_session",
        "passenger_wsgi.py": "admin_owners.is_owner_session",
        "admin_system_authz.py": "admin_owners.is_owner_session",
        "admin_contact_integrity.py": "admin_owners.is_owner_session",
        "chatbot_hardening.py": "admin_owners.is_owner_session",
    }
    for filename, marker in expected.items():
        source = open(os.path.join(ROOT, filename), "r", encoding="utf-8").read()
        assert marker in source, f"{filename} n'utilise pas la politique owner commune"


def test_designated_owner_accounts_are_protected_from_deletion_and_email_reassignment():
    flow = open(os.path.join(ROOT, "admin_auth_flow.py"), "r", encoding="utf-8").read()
    assert "is_protected_owner_user(existing)" in flow
    assert "is_protected_owner_user(target)" in flow
    assert "Un propriétaire BININGA protégé ne peut pas être supprimé." in flow
    assert "L’adresse email d’un propriétaire protégé ne peut pas être remplacée." in flow


def test_owner_state_is_exposed_to_admin_ui_without_new_role_value():
    flow = open(os.path.join(ROOT, "admin_auth_flow.py"), "r", encoding="utf-8").read()
    ui = open(os.path.join(ROOT, "static", "admin-auth-management.js"), "r", encoding="utf-8").read()
    assert 'payload["is_main_admin"] = is_owner' in flow
    assert 'payload["is_owner"] = is_owner' in flow
    assert "Propriétaire — activation en attente" in ui
    assert "· Propriétaire" in ui


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"OK {test.__name__}")
    print(f"{len(tests)} contrats owners validés")
