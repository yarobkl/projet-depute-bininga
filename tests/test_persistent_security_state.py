"""Regression tests for durable security state on serverless runtimes."""
from __future__ import annotations

from types import SimpleNamespace

import persistent_security_state as bridge


class FakeServer(SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.store = {}
        self.BLOCKED_IPS = set()
        self.ATTACK_SCORES = {}
        self.file_blocked = []
        self.file_scores = {}
        self.file_attacks = []

        self.load_blocked_ips = self._legacy_load_blocked
        self.save_blocked_ips = self._legacy_save_blocked
        self.load_attack_scores = self._legacy_load_scores
        self.save_attack_scores = self._legacy_save_scores
        self.record_attack = self._legacy_record_attack
        self.load_attacks = self._legacy_load_attacks

    def _pg_load(self, key):
        return self.store.get(key)

    def _pg_save(self, key, value):
        import copy
        self.store[key] = copy.deepcopy(value)
        return True

    def _legacy_load_blocked(self):
        self.BLOCKED_IPS = set(self.file_blocked)

    def _legacy_save_blocked(self):
        self.file_blocked = sorted(self.BLOCKED_IPS)

    def _legacy_load_scores(self):
        import copy
        self.ATTACK_SCORES = copy.deepcopy(self.file_scores)

    def _legacy_save_scores(self):
        import copy
        self.file_scores = copy.deepcopy(self.ATTACK_SCORES)

    def _legacy_record_attack(self, ip, event_type, score, detail=""):
        entry = self.ATTACK_SCORES.setdefault(ip, {"score": 0, "events": []})
        entry["score"] += score
        entry["events"].append({"type": event_type, "detail": detail})
        if entry["score"] >= 25:
            self.BLOCKED_IPS.add(ip)
            self.save_blocked_ips()

    def _legacy_load_attacks(self, limit=200):
        return list(reversed(self.file_attacks[-limit:]))


def test_blocked_ips_survive_new_runtime():
    first = FakeServer()
    bridge.install(first)
    first.BLOCKED_IPS.add("203.0.113.7")
    first.save_blocked_ips()
    assert first.store["security_blocked_ips"] == ["203.0.113.7"]

    second = FakeServer()
    second.store = first.store
    bridge.install(second)
    second.load_blocked_ips()
    assert "203.0.113.7" in second.BLOCKED_IPS


def test_attack_event_is_flushed_immediately():
    server = FakeServer()
    bridge.install(server)
    server.record_attack("198.51.100.9", "SCANNER_UA", 5, "scanner")
    assert server.store["security_attack_scores"]["198.51.100.9"]["score"] == 5
    attacks = server.store["security_attack_log"]
    assert len(attacks) == 1
    assert attacks[0]["type"] == "SCANNER_UA"


def test_auto_ban_is_durable():
    server = FakeServer()
    bridge.install(server)
    server.record_attack("198.51.100.10", "SQL_INJECTION", 30, "payload")
    assert "198.51.100.10" in server.BLOCKED_IPS
    assert "198.51.100.10" in server.store["security_blocked_ips"]


def test_attack_log_rehydrates_in_reverse_chronological_order():
    server = FakeServer()
    bridge.install(server)
    server.record_attack("1.1.1.1", "ONE", 1, "first")
    server.record_attack("2.2.2.2", "TWO", 1, "second")

    fresh = FakeServer()
    fresh.store = server.store
    bridge.install(fresh)
    rows = fresh.load_attacks(10)
    assert [row["type"] for row in rows] == ["TWO", "ONE"]


def run_all():
    for test in (
        test_blocked_ips_survive_new_runtime,
        test_attack_event_is_flushed_immediately,
        test_auto_ban_is_durable,
        test_attack_log_rehydrates_in_reverse_chronological_order,
    ):
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
