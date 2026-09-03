"""Regression tests for the Vercel-safe YARO IA restart bridge."""
from __future__ import annotations

import os

import serverless_monitor_restart as bridge


class Handler:
    command = "POST"
    path = "/api/monitor-restart"
    client_address = ("127.0.0.1", 0)

    def __init__(self, token="tok", csrf="csrf"):
        self.headers = {
            "X-Admin-Token": token,
            "X-CSRF-Token": csrf,
        }
        self.response = None

    def _json(self, payload, status=200):
        self.response = (status, payload)


class Server:
    BININGA_TEST = True

    def __init__(self, role="admin", csrf="csrf"):
        self.role = role
        self.csrf = csrf
        self.saved = None
        self.audit = []

    def get_session(self, token):
        if token != "tok":
            return None
        return {"username": "admin", "role": self.role, "csrf_token": self.csrf}

    def load_news(self):
        return {"items": [], "last_run": None, "stats": {"total_found": 2, "runs": 4}}

    def save_news(self, data):
        self.saved = data

    def audit_log(self, action, ip, detail):
        self.audit.append((action, ip, detail))


def test_non_vercel_defers_to_legacy_route():
    old_vercel = os.environ.pop("VERCEL", None)
    old_env = os.environ.pop("VERCEL_ENV", None)
    try:
        handler = Handler()
        server = Server()
        assert bridge.guard_request(server, handler) is True
        assert handler.response is None
        assert server.saved is None
    finally:
        if old_vercel is not None:
            os.environ["VERCEL"] = old_vercel
        if old_env is not None:
            os.environ["VERCEL_ENV"] = old_env


def test_vercel_restart_requires_admin_and_csrf():
    old = os.environ.get("VERCEL")
    os.environ["VERCEL"] = "1"
    try:
        unauth = Handler(token="bad")
        assert bridge.guard_request(Server(), unauth) is False
        assert unauth.response[0] == 401

        ministre = Handler()
        assert bridge.guard_request(Server(role="ministre"), ministre) is False
        assert ministre.response[0] == 403

        bad_csrf = Handler(csrf="wrong")
        assert bridge.guard_request(Server(), bad_csrf) is False
        assert bad_csrf.response[0] == 403
    finally:
        if old is None:
            os.environ.pop("VERCEL", None)
        else:
            os.environ["VERCEL"] = old


def test_vercel_restart_runs_bounded_cycle_and_persists():
    old = os.environ.get("VERCEL")
    os.environ["VERCEL"] = "1"
    try:
        handler = Handler()
        server = Server()
        assert bridge.guard_request(server, handler) is False
        assert handler.response[0] == 200
        payload = handler.response[1]
        assert payload["ok"] is True
        assert payload["mode"] == "serverless"
        assert payload["found"] == 0
        assert server.saved is not None
        assert server.saved["last_run"]
        assert server.saved["stats"]["runs"] == 5
        assert server.saved["stats"]["total_found"] == 2
        assert any(action == "SAVE" for action, _, _ in server.audit)
    finally:
        if old is None:
            os.environ.pop("VERCEL", None)
        else:
            os.environ["VERCEL"] = old


def run_all():
    tests = [
        test_non_vercel_defers_to_legacy_route,
        test_vercel_restart_requires_admin_and_csrf,
        test_vercel_restart_runs_bounded_cycle_and_persists,
    ]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
