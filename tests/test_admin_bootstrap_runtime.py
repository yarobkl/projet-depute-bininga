"""Regression contracts for the authenticated admin bootstrap and page freezes."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_one_injected_script_owns_authenticated_startup() -> None:
    passenger = read("passenger_wsgi.py")
    injected = passenger[passenger.index('scripts = b""'):passenger.index("if scripts:")]
    assert "admin-session-hardening.js?v=20260905-admin-boot-1" in injected
    for duplicate in (
        "admin-instant-boot.js",
        "admin-dashboard-priority.js",
        "admin-dashboard-hardening.js",
        "admin-notification-hardening.js",
        "admin-chatbot.js",
    ):
        assert duplicate not in injected
    assert not (ROOT / "static" / "admin-instant-boot.js").exists()


def test_bootstrap_sequence_paints_before_background_and_optional_modules() -> None:
    source = read("static/admin-session-hardening.js")
    start = source[source.index("async function startWithSession"):source.index("function start()")]
    assert start.index("window._applySession(saved, restored)") < start.index("await waitForPaint()")
    assert start.index("await waitForPaint()") < start.index("await loadCriticalModules()")
    assert start.index("bininga:admin-background-starting") < start.index("window.init()")
    assert start.index("window.init()") < start.index("setPhase('ready')")
    assert start.index("setPhase('ready')") < start.index("loadOptionalModules()")
    assert "MODULE_TIMEOUT_MS" in source


def test_legacy_bundle_no_longer_autostarts_or_hides_the_shell() -> None:
    source = read("static/admin.js")
    apply_session = source[source.index("function _applySession"):source.index("function restoreStoredSession")]
    assert "init();" not in apply_session
    assert "initNotifications();" not in apply_session
    assert 'DOMContentLoaded", () => {\n  restoreStoredSession()' not in source
    assert "if (_adminInitStarted) return" in source


def test_secondary_modules_cannot_create_self_triggering_observer_loops() -> None:
    monitoring = read("static/admin-monitoring-serverless.js")
    dashboard = read("static/admin-dashboard-hardening.js")
    assert "MutationObserver" not in monitoring
    assert "MutationObserver" not in dashboard
    assert "patchMonitoringLoader" in monitoring
    assert "admin:panelchange" in monitoring
    assert "admin:panelchange" in dashboard


def test_critical_failure_has_visible_recovery_actions() -> None:
    source = read("static/admin-session-hardening.js")
    assert "Impossible de charger l’administration" in source
    assert "data-admin-retry" in source
    assert "data-admin-reconnect" in source
    assert "ADMIN_BOOT_INIT" in source
    assert "ADMIN_BOOT_PROMISE" in source


def test_notifications_are_optional_on_browsers_without_the_api() -> None:
    source = read("static/admin.js")
    assert source.count('"Notification" in window') == 2
    assert "if (_notificationsInitialized) return" in source


def test_active_session_and_expiry_use_one_navigation_model() -> None:
    legacy = read("static/admin.js")
    bootstrap = read("static/admin-session-hardening.js")
    core = read("static/admin-core.js")
    assert "sessionStorage.setItem(SESSION_STORAGE_KEY" in legacy
    assert "localStorage.setItem(SESSION_STORAGE_KEY" not in legacy
    assert "sessionStorage.setItem(KEY" in bootstrap
    assert "localStorage.setItem(KEY" not in bootstrap
    assert "location.replace(LOGIN_SHELL)" in core
    assert 'location.replace("/static/admin-login-shell.html")' in legacy
