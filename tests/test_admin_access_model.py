"""Contracts for the strict Owner + delegated collaborator access model."""
from __future__ import annotations

import io
import json
import os
import sys
from email.message import Message

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import admin_access_model

STATIC = os.path.join(ROOT, "static")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class DummyServer:
    def __init__(self, users=None, sessions=None):
        self.users = list(users or [])
        self.sessions = dict(sessions or {})
        self.audit = []

    def load_users(self):
        return self.users

    def save_users(self, users):
        self.users = list(users)
        return True

    def get_session(self, token):
        return self.sessions.get(token)

    def audit_log(self, *args):
        self.audit.append(args)


class DummyHandler:
    def __init__(self, payload=None, token=""):
        raw = json.dumps(payload or {}).encode("utf-8")
        self.rfile = io.BytesIO(raw)
        self.wfile = io.BytesIO()
        self.headers = Message()
        self.headers["Content-Length"] = str(len(raw))
        if token:
            self.headers["X-Admin-Token"] = token
        self._status_code = 200
        self._response_headers = []
        self.client_address = ("127.0.0.1", 0)
        self.command = "POST"
        self.path = "/api/login"

    def _json(self, payload, status=200):
        self._status_code = status
        self.wfile = io.BytesIO(json.dumps(payload).encode("utf-8"))


def test_unmanaged_historical_collaborator_cannot_login():
    server = DummyServer([{"username": "old-user", "role": "editeur"}])
    handler = DummyHandler({"username": "old-user", "password": "irrelevant"})
    assert admin_access_model._guard_login(server, handler) is False
    assert handler._status_code == 401


def test_owner_managed_collaborator_is_allowed_to_reach_normal_login():
    server = DummyServer([{"username": "collab", "role": "lecteur", "owner_managed": True}])
    handler = DummyHandler({"username": "collab", "password": "irrelevant"})
    assert admin_access_model._guard_login(server, handler) is True


def test_collaborator_without_email_gets_non_public_placeholder_before_save():
    source = _read(os.path.join(ROOT, "admin_access_model.py"))
    assert "accounts.bininga.invalid" in source
    assert "email_hidden" in source
    assert "owner_managed" in source
    assert 'target["must_change_password"] = False' in source


def test_reserved_owner_emails_cannot_be_created_from_collaborator_form():
    source = _read(os.path.join(ROOT, "admin_access_model.py"))
    assert "is_designated_owner_email(username)" in source
    assert "is_designated_owner_email(email)" in source
    assert "Les deux comptes Owner sont réservés" in source


def test_first_login_is_owner_only_and_dynamic():
    source = _read(os.path.join(ROOT, "admin_access_model.py"))
    shell = _read(os.path.join(STATIC, "admin-login-shell.html"))
    assert 'BOOTSTRAP_STATUS_PATH = "/api/auth/bootstrap-status"' in source
    assert 'FIRST_LOGIN_PATH = "/api/auth/first-login"' in source
    assert "first_login_available" in source
    assert "Première connexion Owner" in shell
    assert "/api/auth/bootstrap-status" in shell
    assert "/api/auth/first-login" in shell
    assert "firstOpen.classList.toggle('hidden',!available)" in shell


def test_collaborator_form_keeps_owner_control_and_optional_recovery_email():
    ui = _read(os.path.join(STATIC, "admin-collaborator-management.js"))
    session = _read(os.path.join(STATIC, "admin-session-hardening.js"))
    assert "Seuls les propriétaires peuvent créer ou modifier un collaborateur." in ui
    assert "Adresse email de récupération (optionnelle)" in ui
    assert "/api/users/upsert" in ui
    assert "admin-collaborator-management.js" in session
    assert session.index("admin-auth-management.js") < session.index("admin-collaborator-management.js")


def test_pipeline_places_access_model_before_legacy_auth_flow():
    pipeline = _read(os.path.join(ROOT, "admin_request_pipeline.py"))
    assert "import admin_access_model" in pipeline
    assert "admin_access_model.guard_request" in pipeline
    assert pipeline.index("admin_access_model.guard_request") < pipeline.index("admin_auth_flow.guard_request")
    assert "admin_access_model.postprocess_response" in pipeline


def test_legacy_admin_fallback_is_removed_from_owner_policy():
    owners = _read(os.path.join(ROOT, "admin_owners.py"))
    assert "legacy ``ADMIN_USER`` value alone never grants Owner privileges" in owners
    assert "return bool(user and is_owner_user(server, user))" in owners
    assert "active_designated_owners(server):\n        return False" not in owners


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"OK {test.__name__}")
    print(f"{len(tests)} contrats modèle d’accès validés")
