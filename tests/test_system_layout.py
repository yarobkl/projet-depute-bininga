"""Contracts for the organized SYSTÈME admin layout."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


def test_monitoring_is_split_into_clear_views():
    source = _read("static/admin-system-layout.js")
    for label in ("Vue générale", "Trafic & endpoints", "Erreurs", "Rapport 24h"):
        assert label in source, label
    for target in ("mon-status-bar", "mon-alerts-list", "mon-endpoints-list", "mon-requests-list", "mon-errors-list", "mon-report-box"):
        assert target in source, target


def test_security_is_split_into_clear_views():
    source = _read("static/admin-system-layout.js")
    for label in ("Vue générale", "Attaques", "Compte & 2FA", "Bouclier IA"):
        assert label in source, label
    for target in ("sec-attacks-list", "tfa-status", "bouclier-card"):
        assert target in source, target


def test_users_and_logs_have_search_tools():
    source = _read("static/admin-system-layout.js")
    assert "Rechercher un utilisateur" in source
    assert "Filtrer par rôle" in source
    assert "Rechercher dans les journaux" in source


def test_bootstrap_loads_cache_busted_system_layout():
    session = _read("static/admin-session-hardening.js")
    passenger = _read("passenger_wsgi.py")
    assert "/static/admin-system-layout.js?v=20260903-system-layout-1" in session
    assert "/static/admin-session-hardening.js?v=20260905-admin-boot-1" in passenger


if __name__ == "__main__":
    tests=[fn for name,fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests:
        test(); print("OK",test.__name__)
    print(f"{len(tests)} tests layout SYSTÈME validés")
