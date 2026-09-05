"""Contracts for immediate dashboard rendering after admin login."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as fh:
        return fh.read()


def test_priority_script_is_loaded_by_the_single_session_bootstrap():
    passenger = _read("passenger_wsgi.py")
    session = _read("static/admin-session-hardening.js")
    assert passenger.count("static/admin-session-hardening.js") == 2
    assert "static/admin-dashboard-priority.js" not in passenger
    assert session.index("admin-dashboard-priority.js") < session.index("const optionalModules")


def test_priority_dashboard_renders_shell_before_network_completion():
    js = _read("static/admin-dashboard-priority.js")
    assert "function ensureShell()" in js
    assert "Activité opérationnelle" in js
    assert "Audience numérique" in js
    assert "Chargement…" in js
    assert "bininga:admin-background-starting" in js
    assert "void fastRefresh()" in js
    assert "window.init =" not in js


def test_priority_refresh_does_not_wait_for_contacts_or_messages():
    js = _read("static/admin-dashboard-priority.js")
    assert "fetch('/api/stats'" in js
    assert "fetch('/api/contacts'" not in js
    assert "syncMessages" not in js
    assert "cache: 'no-store'" in js


def run_all():
    tests = [
        test_priority_script_is_loaded_by_the_single_session_bootstrap,
        test_priority_dashboard_renders_shell_before_network_completion,
        test_priority_refresh_does_not_wait_for_contacts_or_messages,
    ]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
