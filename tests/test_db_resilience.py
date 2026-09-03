"""Database resilience behavior tests using a fake persistent loader."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import db_resilience


class FakeServer:
    def __init__(self, ok=True): self.ok = ok
    def _db_config(self): return ("postgres", "fake")
    def _pg_load(self, key):
        if not self.ok: raise RuntimeError("db down")
        return []


def reset_state():
    db_resilience._STATE.update({"checked_at": 0.0, "healthy": False, "backend": "", "failures": 0, "circuit_until": 0.0, "last_error": ""})


def test_healthy_probe_allows_persistence():
    reset_state(); server = FakeServer(ok=True)
    assert db_resilience.can_persist(server) is True
    status = db_resilience.public_status(server)
    assert status["ok"] is True and status["database"] == "up"


def test_failed_probe_opens_circuit_and_fails_closed():
    reset_state(); server = FakeServer(ok=False)
    assert db_resilience.can_persist(server) is False
    status = db_resilience.public_status(server)
    assert status["ok"] is False and status["database"] == "down" and status["circuit_open"] is True


if __name__ == "__main__":
    tests=[fn for name,fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests: test(); print("OK",test.__name__)
    print(f"{len(tests)} tests résilience DB validés")
