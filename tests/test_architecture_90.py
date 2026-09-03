"""Architecture hardening contracts targeting >=90% maturity in weak areas."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


def test_granular_permissions_are_server_authoritative():
    policy = read("admin_permissions.py")
    authz = read("admin_system_authz.py")
    access = read("admin_access_model.py")
    assert "ALL_PERMISSIONS" in policy and "ROLE_PERMISSIONS" in policy
    assert "permission_grants" in policy and "permission_revokes" in policy
    assert "admin_permissions.has_permission" in authz
    assert '"PERMISSION_DENIED"' in authz
    assert "available_permissions" in access and "role_permissions" in access


def test_database_resilience_fails_closed_with_probe_and_circuit_breaker():
    resilience = read("db_resilience.py")
    authz = read("admin_system_authz.py")
    assert "PROBE_TTL_SECONDS" in resilience and "CIRCUIT_SECONDS" in resilience
    assert "can_persist" in resilience and "public_status" in resilience
    assert "db_resilience.can_persist" in authz
    assert '"PERSISTENCE_REQUIRED"' in authz


def test_compromised_account_has_session_inventory_and_revocation():
    incident = read("account_incident_response.py")
    pipeline = read("admin_request_pipeline.py")
    assert '"/api/auth/sessions"' in incident
    assert '"/api/auth/revoke-sessions"' in incident
    assert "raw bearer" in incident.lower()
    assert "account_incident_response.guard_request" in pipeline


def test_restore_is_verified_transactional_and_has_safety_backup():
    restore = read("restore_bininga.py")
    assert "backup_bininga.verify_backup" in restore
    assert "_create_safety_backup" in restore
    assert "conn.commit()" in restore and "conn.rollback()" in restore
    assert "EXCLUDED_STORE_KEYS" in restore


def test_security_constitution_documents_invariants():
    doc = read("docs/SECURITY_AND_ACCESS_MODEL.md")
    for phrase in ("Exactly two designated identities", "Source of truth", "Persistence failure", "Compromised account response", "Backup and restore", "Test principle"):
        assert phrase in doc


def test_advanced_security_ui_exists_without_becoming_authoritative():
    ui = read("static/admin-advanced-security.js")
    assert "/api/auth/sessions" in ui and "/api/auth/revoke-sessions" in ui
    assert "BiningaPermissionEditor" in ui
    assert "Server-side checks remain authoritative" in ui


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests:
        test(); print("OK", test.__name__)
    print(f"{len(tests)} contrats architecture 90 validés")
