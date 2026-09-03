"""Contracts for immediate dashboard rendering after admin login."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as fh:
        return fh.read()


def test_priority_script_is_injected_before_session_boot():
    passenger = _read("passenger_wsgi.py")
    dashboard = passenger.index("static/admin-dashboard-hardening.js")
    priority = passenger.index("static/admin-dashboard-priority.js")
    session = passenger.index("static/admin-session-hardening.js")
    assert dashboard < priority < session
    assert 'data-bininga-dashboard-hardening data-loaded="1"' in passenger


def test_priority_dashboard_renders_shell_before_network_completion():
    js = _read("static/admin-dashboard-priority.js")
    assert "function ensureShell()" in js
    assert "Activité opérationnelle" in js
    assert "Audience numérique" in js
    assert "Chargement…" in js
    assert "ensureShell();\n      fastRefresh();\n      return original.apply" in js


def test_priority_refresh_does_not_wait_for_contacts_or_messages():
    js = _read("static/admin-dashboard-priority.js")
    assert "fetch('/api/stats'" in js
    assert "fetch('/api/contacts'" not in js
    assert "syncMessages" not in js
    assert "cache: 'no-store'" in js


def run_all():
    tests = [
        test_priority_script_is_injected_before_session_boot,
        test_priority_dashboard_renders_shell_before_network_completion,
        test_priority_refresh_does_not_wait_for_contacts_or_messages,
    ]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
