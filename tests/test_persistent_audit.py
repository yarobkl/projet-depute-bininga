"""Regression tests for durable audit logs on serverless hosts."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import persistent_audit


class Server:
    def __init__(self, initial=None, db_ok=True):
        self.store = {} if initial is None else {"audit_log": list(initial)}
        self.db_ok = db_ok
        self.local = []

    def _pg_load(self, key):
        if not self.db_ok:
            return None
        return self.store.get(key)

    def _pg_save(self, key, value):
        if not self.db_ok:
            return False
        self.store[key] = list(value)
        return True

    def audit_log(self, action, ip="", detail=""):
        self.local.append({"action": action, "ip": ip, "detail": detail})

    def load_audit(self, limit=100):
        return list(reversed(self.local[-limit:]))


def test_first_event_seeds_missing_durable_key():
    server = Server()
    persistent_audit.install(server)
    server.audit_log("LOGIN_OK", "127.0.0.1", "Connexion de test")
    assert "audit_log" in server.store
    assert len(server.store["audit_log"]) == 1
    assert server.store["audit_log"][0]["action"] == "LOGIN_OK"
    rows = server.load_audit()
    assert rows and rows[0]["action"] == "LOGIN_OK"


def test_existing_durable_events_are_preserved_and_newest_first():
    server = Server(initial=[{"ts": "2026-01-01 00:00:00", "action": "OLD", "ip": "", "detail": ""}])
    persistent_audit.install(server)
    server.audit_log("SAVE", "127.0.0.1", "Modification")
    assert [row["action"] for row in server.store["audit_log"]] == ["OLD", "SAVE"]
    assert [row["action"] for row in server.load_audit()] == ["SAVE", "OLD"]


def test_local_fallback_remains_available_when_db_is_unavailable():
    server = Server(db_ok=False)
    persistent_audit.install(server)
    server.audit_log("LOGIN_FAIL", "127.0.0.1", "Test")
    assert server.local and server.local[-1]["action"] == "LOGIN_FAIL"
    rows = server.load_audit()
    assert rows and rows[0]["action"] == "LOGIN_FAIL"


def run_all():
    tests = [
        test_first_event_seeds_missing_durable_key,
        test_existing_durable_events_are_preserved_and_newest_first,
        test_local_fallback_remains_available_when_db_is_unavailable,
    ]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
