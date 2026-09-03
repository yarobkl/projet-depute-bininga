"""Incident response contract tests."""
from __future__ import annotations

import account_incident_response


class FakeServer:
    def __init__(self):
        self.ACTIVE_SESSIONS = {
            "a": {"username": "u"},
            "b": {"username": "u"},
            "c": {"username": "other"},
        }
        self.saved = False
    def save_sessions(self):
        self.saved = True


def test_revoke_other_sessions_preserves_current_and_other_users():
    server = FakeServer()
    removed = account_incident_response._revoke_other_sessions(server, "u", keep_token="a")
    assert removed == 1
    assert "a" in server.ACTIVE_SESSIONS
    assert "b" not in server.ACTIVE_SESSIONS
    assert "c" in server.ACTIVE_SESSIONS
    assert server.saved is True


def test_session_rows_never_return_bearer_token():
    server = FakeServer()
    rows = account_incident_response._session_rows(server, "u", "a")
    assert rows and all("token" not in row for row in rows)
    assert any(row["current"] for row in rows)


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests:
        test(); print("OK", test.__name__)
    print(f"{len(tests)} tests incident response validés")
