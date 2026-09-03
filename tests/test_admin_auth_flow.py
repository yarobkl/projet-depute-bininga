"""Contracts for the BININGA administration account lifecycle."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import admin_auth_flow

STATIC = os.path.join(ROOT, "static")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def test_password_policy_is_strong_for_new_credentials():
    assert admin_auth_flow._password_error("Court1!")
    assert admin_auth_flow._password_error("administrateur123!", "administrateur")
    assert not admin_auth_flow._password_error("Solide-Admin-2026!", "agent")


def test_reset_tokens_are_hashed_single_use_and_short_lived():
    source = _read(os.path.join(ROOT, "admin_auth_flow.py"))
    assert "RESET_TTL_SECONDS = 30 * 60" in source
    assert "hashlib.sha256(token.encode" in source
    assert "store[digest]" in source
    assert "store.pop(digest, None)" in source
    assert "store[token]" not in source


def test_password_reset_email_is_french_and_supports_resend_with_smtp_fallback():
    source = _read(os.path.join(ROOT, "admin_auth_flow.py"))
    assert "Réinitialisation de votre mot de passe — BININGA" in source
    assert "valable 30 minutes" in source
    assert "RESEND_API_KEY" in source
    assert "AUTH_SMTP_HOST" in source
    assert "_send_via_resend" in source and "_send_via_smtp" in source
    assert '"User-Agent": "bininga-auth/1.0"' in source


def test_public_forgot_flow_does_not_enumerate_accounts():
    source = _read(os.path.join(ROOT, "admin_auth_flow.py"))
    assert "Si un compte correspond à ces informations" in source
    assert "PASSWORD_RESET_REQUEST" in source
    assert "PASSWORD_RESET_STORE_ERROR" in source


def test_first_login_is_enforced_server_side():
    source = _read(os.path.join(ROOT, "admin_auth_flow.py"))
    assert '"code": "PASSWORD_CHANGE_REQUIRED"' in source
    assert "must_change_password" in source
    assert "_block_until_password_changed" in source
    assert '"/api/auth/change-password"' in source


def test_new_users_require_recovery_email_and_forced_password_change():
    source = _read(os.path.join(ROOT, "admin_auth_flow.py"))
    assert "Une adresse email valide est obligatoire" in source
    assert '"email": email_address' in source
    assert '"must_change_password": True' in source


def test_password_changes_revoke_sessions():
    source = _read(os.path.join(ROOT, "admin_auth_flow.py"))
    assert "def _revoke_user_sessions" in source
    assert source.count("_revoke_user_sessions(server, username)") >= 2
    assert '"reauthenticate": True' in source


def test_login_shell_exposes_forgot_password_and_first_login_redirect():
    shell = _read(os.path.join(STATIC, "admin-login-shell.html"))
    assert "Mot de passe oublié ?" in shell
    assert "/api/auth/forgot-password" in shell
    assert "must_change_password" in shell
    assert "/static/admin-first-login.html" in shell


def test_private_admin_path_is_only_returned_after_successful_login():
    shell = _read(os.path.join(STATIC, "admin-login-shell.html"))
    flow = _read(os.path.join(ROOT, "admin_auth_flow.py"))
    assert "cabinet-bininga-" not in shell
    assert "data.admin_path" in shell
    assert 'payload["admin_path"]' in flow
    assert "ADMIN_SECRET_PATH" in flow


def test_reset_and_first_login_pages_are_real_api_flows():
    reset = _read(os.path.join(STATIC, "admin-reset-password.html"))
    first = _read(os.path.join(STATIC, "admin-first-login.html"))
    assert "/api/auth/reset-password" in reset and "new_password" in reset
    assert "/api/auth/change-password" in first
    assert "X-CSRF-Token" in first and "current_password" in first


def test_admin_account_module_is_loaded_after_shared_core():
    session = _read(os.path.join(STATIC, "admin-session-hardening.js"))
    assert "admin-core.js" in session
    assert "admin-auth-management.js" in session
    assert session.index("admin-core.js") < session.index("admin-auth-management.js")
    assert "must_change_password" in session and "admin-first-login.html" in session


def test_admin_self_service_password_change_and_recovery_email_ui_exist():
    ui = _read(os.path.join(STATIC, "admin-auth-management.js"))
    assert "Adresse email de récupération" in ui
    assert "Modifier mon mot de passe" in ui
    assert "/api/auth/change-password" in ui
    assert "/api/auth/users-meta" in ui
    assert "/api/users/upsert" in ui


def test_auth_flow_is_part_of_authoritative_request_pipeline():
    pipeline = _read(os.path.join(ROOT, "admin_request_pipeline.py"))
    passenger = _read(os.path.join(ROOT, "passenger_wsgi.py"))
    assert "import admin_auth_flow" in pipeline
    assert "admin_auth_flow.guard_request" in pipeline
    assert "admin_auth_flow.postprocess_response" in pipeline
    assert "admin_request_pipeline.process_response" in passenger


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"OK {test.__name__}")
    print(f"{len(tests)} contrats auth admin validés")
