"""Incident response contract tests."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import account_incident_response


class FakeServer:
    def __init__(self):
        self.ACTIVE_SESSIONS = {"a": {"username": "u"}, "b": {"username": "u"}, "c": {"username": "other"}}
        self.saved = False
    def save_sessions(self): self.saved = True


def test_revoke_other_sessions_preserves_current_and_other_users():
    server = FakeServer(); removed = account_incident_response._revoke_other_sessions(server, "u", keep_token="a")
    assert removed == 1 and "a" in server.ACTIVE_SESSIONS and "b" not in server.ACTIVE_SESSIONS and "c" in server.ACTIVE_SESSIONS and server.saved is True


def test_session_rows_never_return_bearer_token():
    server = FakeServer(); rows = account_incident_response._session_rows(server, "u", "a")
    assert rows and all("token" not in row for row in rows) and any(row["current"] for row in rows)


def test_high_impact_owner_actions_require_2fa_but_setup_remains_reachable():
    assert account_incident_response._requires_owner_2fa("/api/users") is True
    assert account_incident_response._requires_owner_2fa("/api/security/block") is True
    assert account_incident_response._requires_owner_2fa("/api/backups/run") is True
    assert account_incident_response._requires_owner_2fa("/api/2fa/setup") is False
    assert account_incident_response._requires_owner_2fa("/api/auth/revoke-sessions") is False


def test_system_dashboard_reads_do_not_require_owner_2fa():
    for path in (
        "/api/users",
        "/api/security",
        "/api/security/bouclier",
        "/api/backups",
        "/api/monitoring/summary",
        "/api/monitoring/errors",
        "/api/monitoring/report",
        "/api/ia/key",
    ):
        assert account_incident_response._is_safe_owner_read(path, "GET") is True, path


def test_system_mutations_remain_protected_by_owner_2fa():
    for path in (
        "/api/users/upsert",
        "/api/users/delete",
        "/api/security/block",
        "/api/security/lockdown",
        "/api/backups/run",
        "/api/backups/export",
        "/api/monitoring/resolve-alert",
        "/api/ia/key",
    ):
        assert account_incident_response._is_safe_owner_read(path, "POST") is False, path
        assert account_incident_response._requires_owner_2fa(path) is True, path


if __name__ == "__main__":
    tests=[fn for name,fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests: test(); print("OK",test.__name__)
    print(f"{len(tests)} tests incident response validés")