"""Regression contracts for the two-owner BININGA administration policy."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import owner_policy


def test_exact_default_owner_emails_are_normalized():
    assert owner_policy.owner_emails() == (
        "rodrinbakala@outlook.fr",
        "eliebakala@gmail.com",
    )


def test_owner_recognition_is_email_based_not_legacy_username():
    assert owner_policy.is_owner_user({"username": "anything", "email": "RodrinBakala@outlook.fr"})
    assert owner_policy.is_owner_user({"username": "anything", "email": "ElieBakala@gmail.com"})
    assert not owner_policy.is_owner_user({"username": "admin", "email": "other@example.com"})


def test_login_identifier_can_resolve_owner_email():
    class Server:
        def load_users(self):
            return [
                {"username": "admin", "email": "rodrinbakala@outlook.fr"},
                {"username": "eliebakala@gmail.com", "email": "eliebakala@gmail.com"},
            ]
    server = Server()
    assert owner_policy.resolve_login_identifier(server, "RodrinBakala@outlook.fr") == "admin"
    assert owner_policy.resolve_login_identifier(server, "ElieBakala@gmail.com") == "eliebakala@gmail.com"


def test_all_privileged_guards_use_owner_policy():
    files = [
        "admin_system_authz.py",
        "admin_contact_integrity.py",
        "admin_auth_flow.py",
        "passenger_wsgi.py",
        "chatbot_hardening.py",
    ]
    for name in files:
        source = open(os.path.join(ROOT, name), encoding="utf-8").read()
        assert "owner_policy" in source, f"{name} doit utiliser owner_policy"


def test_owner_accounts_are_protected_from_standard_delete_and_email_reassignment():
    source = open(os.path.join(ROOT, "admin_auth_flow.py"), encoding="utf-8").read()
    assert "Un compte owner protégé ne peut pas être supprimé" in source
    assert "L’adresse email d’un owner ne peut pas être remplacée" in source


def test_login_response_exposes_owner_state_to_existing_admin_ui():
    source = open(os.path.join(ROOT, "admin_auth_flow.py"), encoding="utf-8").read()
    assert 'payload["is_main_admin"] = is_owner' in source
    assert 'payload["is_owner"] = is_owner' in source
    assert 'payload["role"] = "owner" if is_owner' in source


def test_second_owner_migration_uses_hash_only_and_forces_unique_password_after_first_login():
    source = open(os.path.join(ROOT, "owner_policy.py"), encoding="utf-8").read()
    assert 'bridge_hash = str(first.get("password_hash")' in source
    assert '"password_hash": bridge_hash' in source
    assert '"must_change_password": True' in source
    assert "plaintext" in source.lower()


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"OK {test.__name__}")
    print(f"{len(tests)} contrats owner validés")
