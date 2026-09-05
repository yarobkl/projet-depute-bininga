"""Static contracts for the BININGA production admin.

These tests intentionally scan the real admin markup instead of checking a
small hand-picked set of buttons. A new inline control cannot be merged with a
missing JavaScript handler, and authenticated API actions must keep the shared
production hardening layer enabled.
"""
from __future__ import annotations

import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_HTML = os.path.join(ROOT, "admin.html")
STATIC = os.path.join(ROOT, "static")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _admin_sources() -> str:
    parts = [_read(ADMIN_HTML)]
    for path in sorted(glob.glob(os.path.join(STATIC, "admin*.js"))):
        parts.append(_read(path))
    return "\n".join(parts)


def _server_sources() -> str:
    names = (
        "server.py", "passenger_wsgi.py", "admin_request_pipeline.py", "admin_system_authz.py",
        "admin_auth_flow.py", "admin_contact_integrity.py", "editorial_publish_integrity.py", "chatbot_hardening.py",
        "google_analytics_integration.py",
    )
    return "\n".join(_read(os.path.join(ROOT, name)) for name in names if os.path.exists(os.path.join(ROOT, name)))


def _inline_handlers(html: str):
    for attr, code in re.findall(r'\b(onclick|onchange|oninput)="([^"]+)"', html):
        match = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\(", code)
        if match:
            yield attr, match.group(1), code


def _is_defined(name: str, source: str) -> bool:
    patterns = (rf"(?:async\s+)?function\s+{re.escape(name)}\s*\(", rf"\b(?:const|let|var)\s+{re.escape(name)}\s*=", rf"\bwindow\.{re.escape(name)}\s*=")
    return any(re.search(pattern, source) for pattern in patterns)


def _admin_api_paths() -> set[str]:
    source = _admin_sources()
    paths = set(re.findall(r"/api/[A-Za-z0-9_.:/-]+", source))
    return {p.rstrip(".,;:'\"") for p in paths}


def test_every_inline_admin_action_has_a_real_handler():
    html = _read(ADMIN_HTML); source = _admin_sources()
    missing = sorted({name for _, name, _ in _inline_handlers(html) if not _is_defined(name, source)})
    assert not missing, f"Contrôles admin sans fonction JavaScript: {', '.join(missing)}"


def test_every_admin_api_action_has_server_implementation():
    server = _server_sources(); missing = []
    for path in sorted(_admin_api_paths()):
        if path in server: continue
        parent = path.rstrip("/")
        while "/" in parent[len("/api/"):]:
            parent = parent.rsplit("/", 1)[0]
            if parent and parent in server: break
        else: missing.append(path)
    assert not missing, "Routes admin sans implémentation serveur: " + ", ".join(missing)


def test_protected_api_downloads_are_authenticated():
    html = _read(ADMIN_HTML); production = _read(os.path.join(STATIC, "admin-production.js"))
    assert re.search(r'href="/api/', html)
    assert "a[href^=\"/api/\"]" in production and "authenticatedDownload" in production and "X-Admin-Token" in production


def test_all_authenticated_mutations_receive_csrf():
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert "X-CSRF-Token" in production and "['GET', 'HEAD', 'OPTIONS']" in production and "path !== '/api/login'" in production


def test_main_admin_ui_is_not_exposed_to_secondary_admins():
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert ".role-superadmin" in production and "isMainAdmin()" in production


def test_destructive_controls_are_main_admin_only():
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert "enforceDestructiveControls" in production and '[onclick*="clearAll("]' in production and '[onclick*="runBackupNow("]' in production and '[onclick*="manualBlock("]' in production


def test_demo_notification_control_is_removed_in_production():
    html = _read(ADMIN_HTML); production = _read(os.path.join(STATIC, "admin-production.js"))
    assert "_addNotif('visit'" in html and "removeDemoControls" in production and "btn.remove()" in production


def test_security_copy_does_not_claim_fake_counts_in_production():
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert "30+ agents IA" in production and "Analyse comportementale" in production
    assert "20+ fichiers" in production and "Données protégées" in production
    assert "40+ pièges" in production and "Leurres serveur" in production


def test_session_hardening_loads_production_actions():
    session = _read(os.path.join(STATIC, "admin-session-hardening.js"))
    assert "admin-core.js" in session and "data-bininga-admin-core" in session
    assert session.index("admin-core.js") < session.index("admin-production.js")
    assert "admin-production.js" in session and "data-bininga-production-hardening" in session


def test_case_management_ui_is_loaded_and_server_synced():
    session = _read(os.path.join(STATIC, "admin-session-hardening.js")); cases = _read(os.path.join(STATIC, "admin-cases.js")); hardening = _read(os.path.join(STATIC, "admin-hardening.js"))
    assert "admin-cases.js" in session and "data-bininga-cases-ui" in session
    assert "window.renderMsgList" in cases and "Informations complémentaires et techniques" in cases
    assert "mailto:" in cases and "tel:" in cases and "setStatus(" in cases and "addNote(" in cases and "pingDepute(" in cases
    assert "window.syncMessages" in hardening and "'/api/contacts'" in hardening and "'/api/contacts/update'" in hardening


def test_case_mutations_are_server_first_not_fake_success():
    hardening = _read(os.path.join(STATIC, "admin-hardening.js"))
    assert "Persist first, update the cache/UI only after the server confirms the write." in hardening
    assert "await checkedJson(res" in hardening and "Statut non modifié" in hardening and "Note non enregistrée" in hardening and "Alerte non envoyée" in hardening


def test_system_crm_ux_is_loaded_and_server_remains_authoritative():
    session = _read(os.path.join(STATIC, "admin-session-hardening.js")); ux = _read(os.path.join(STATIC, "admin-system-ux.js")); authz = _read(os.path.join(ROOT, "admin_system_authz.py"))
    assert "admin-system-ux.js" in session and "data-bininga-system-ux" in session
    assert "window._crmRestoreFromBackup" in ux and "Restauration locale automatique désactivée" in ux
    assert "hardenUserForm" in ux and "mainAdmin()" in ux
    assert '"/api/crm"' in authz and '"/api/security"' in authz and '"/api/monitoring/summary"' in authz


def test_server_side_system_authorization_stays_enabled():
    passenger = _read(os.path.join(ROOT, "passenger_wsgi.py"))
    pipeline = _read(os.path.join(ROOT, "admin_request_pipeline.py"))
    authz = _read(os.path.join(ROOT, "admin_system_authz.py"))
    assert "admin_request_pipeline.allow_request" in passenger
    assert "admin_system_authz.guard_request" in pipeline
    assert '"/api/security"' in authz and '"/api/backups"' in authz and '"/api/crm"' in authz and '"/api/logs"' in authz


def test_editorial_publish_is_a_real_server_side_publication():
    passenger = _read(os.path.join(ROOT, "passenger_wsgi.py")); editorial = _read(os.path.join(ROOT, "editorial_publish_integrity.py"))
    assert "import editorial_publish_integrity" in passenger and "editorial_publish_integrity.migrate_editorial_vedettes" in passenger
    assert '"/api/editorial/save"' in editorial and 'server.save_data(site_data)' in editorial and 'server._pg_save("editorial", rows)' in editorial
    assert '"publication_source": "editorial_ia"' in editorial and '"EDITORIAL_PUBLISH"' in editorial


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test(); print(f"OK {test.__name__}")
    print(f"{len(tests)} contrats admin validés")
