"""Contracts for the SYSTÈME section of the admin UI."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")


def _read(name: str) -> str:
    with open(os.path.join(STATIC, name), "r", encoding="utf-8") as handle:
        return handle.read()


def test_system_panels_listen_to_central_navigation_event():
    source = _read("admin-system-ux.js")
    assert "admin:panelchange" in source
    assert "onPanelChange" in source
    assert "SYSTEM_PANELS" in source


def test_every_system_panel_has_an_automatic_loader():
    source = _read("admin-system-ux.js")
    expected = {
        "monitoring": "loadMonitoring",
        "backups": "loadBackups",
        "logs": "loadAuditLogs",
        "users": "loadUsers",
        "security": "loadSecurity",
    }
    for panel, loader in expected.items():
        assert panel in source, panel
        assert loader in source, loader


def test_monitoring_refresh_stops_when_leaving_panel():
    source = _read("admin-system-ux.js")
    assert "stopMonitoringRefresh" in source
    assert "clearInterval(_monRefreshTimer)" in source
    assert "if(name!=='monitoring')stopMonitoringRefresh()" in source


def test_system_ui_has_explicit_loading_and_error_states():
    source = _read("admin-system-ux.js")
    assert "system-loading-state" in source
    assert "system-error-state" in source
    assert "Chargement des données système" in source


if __name__ == "__main__":
    tests=[fn for name,fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests:
        test(); print("OK",test.__name__)
    print(f"{len(tests)} tests SYSTÈME validés")