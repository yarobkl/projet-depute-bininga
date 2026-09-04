"""Regression tests for synchronous monitoring writes on serverless runtimes."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import serverless_monitoring_persistence as bridge


class FakeMon:
    def __init__(self, write_ok=True):
        self.write_ok = write_ok
        self.rows = []
        self.fallback_calls = []
        self.init_calls = 0
        self.analysis_calls = []
        self.sqlite3 = SimpleNamespace(connect=lambda *a, **k: None)
        self.DB_FILE = ":memory:"

    def init_db(self):
        self.init_calls += 1

    def _db_config(self):
        return ("postgresql", {"url": "fake"})

    def _sql_conn(self):
        if not self.write_ok:
            return (None, "postgresql")
        return (object(), "postgresql")

    def _execute_write(self, conn, backend, item):
        self.rows.append(item)

    def record_request(self, *args):
        self.fallback_calls.append(("request", args))

    def record_error(self, *args):
        self.fallback_calls.append(("error", args))

    def record_visit(self, *args):
        self.fallback_calls.append(("visit", args))

    def record_prog_view(self, *args):
        self.fallback_calls.append(("prog_view", args))

    def analyze_metrics(self, active_sessions=0, blocked_ips=0):
        self.analysis_calls.append((active_sessions, blocked_ips))

    def get_summary(self, active_sessions=0, blocked_ips=0):
        return {"global_status": "OK", "system": {"cpu_percent": 12.5}, "active_sessions": active_sessions, "blocked_ips": blocked_ips}

    def get_alerts(self, include_resolved=False, limit=100):
        return [{"level": "WARNING"}] if include_resolved else []


class FakeServer:
    def __init__(self, mon):
        self._mon = mon


def with_vercel(fn):
    old = os.environ.get("VERCEL")
    os.environ["VERCEL"] = "1"
    try:
        fn()
    finally:
        if old is None:
            os.environ.pop("VERCEL", None)
        else:
            os.environ["VERCEL"] = old


def test_serverless_request_is_written_immediately_without_eager_init():
    def run():
        mon = FakeMon()
        bridge.install(FakeServer(mon))
        assert mon.init_calls == 0
        mon.record_request("GET", "/api/stats", 200, 12.3, "127.0.0.1")
        assert mon.init_calls == 0  # SQL connection initializes its tables lazily.
        assert len(mon.rows) == 1
        assert mon.rows[0][0] == "request"
        assert mon.rows[0][2] == "/api/stats"
        assert mon.fallback_calls == []
    with_vercel(run)


def test_all_public_monitoring_events_use_direct_write():
    def run():
        mon = FakeMon()
        bridge.install(FakeServer(mon))
        mon.record_error("/x", "Boom", "message", "1.2.3.4")
        mon.record_visit("1.2.3.4", "/")
        mon.record_prog_view("1.2.3.4")
        assert [row[0] for row in mon.rows] == ["error", "visit", "prog_view"]
    with_vercel(run)


def test_failed_direct_write_falls_back_to_existing_writer():
    def run():
        mon = FakeMon(write_ok=False)
        bridge.install(FakeServer(mon))
        mon.record_request("POST", "/api/test", 500, 1.0, "127.0.0.1")
        assert mon.rows == []
        assert mon.fallback_calls and mon.fallback_calls[0][0] == "request"
    with_vercel(run)


def test_summary_triggers_on_demand_analysis_once_per_window():
    def run():
        mon = FakeMon()
        bridge.install(FakeServer(mon))
        summary = mon.get_summary(3, 2)
        assert summary["global_status"] == "OK"
        assert summary["system"]["cpu_percent"] == 12.5
        assert mon.analysis_calls == [(3, 2)]
        mon.get_alerts(False, 100)
        mon.get_summary(3, 2)
        assert mon.analysis_calls == [(3, 2)]
    with_vercel(run)


def test_non_serverless_keeps_existing_monitoring_functions():
    old_vercel = os.environ.pop("VERCEL", None)
    old_env = os.environ.pop("VERCEL_ENV", None)
    try:
        mon = FakeMon()
        original = mon.record_request
        original_summary = mon.get_summary
        bridge.install(FakeServer(mon))
        assert mon.record_request.__func__ is original.__func__
        assert mon.get_summary.__func__ is original_summary.__func__
        assert mon.init_calls == 0
    finally:
        if old_vercel is not None:
            os.environ["VERCEL"] = old_vercel
        if old_env is not None:
            os.environ["VERCEL_ENV"] = old_env


def run_all():
    for test in (
        test_serverless_request_is_written_immediately_without_eager_init,
        test_all_public_monitoring_events_use_direct_write,
        test_failed_direct_write_falls_back_to_existing_writer,
        test_summary_triggers_on_demand_analysis_once_per_window,
        test_non_serverless_keeps_existing_monitoring_functions,
    ):
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
