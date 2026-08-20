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
        "server.py",
        "passenger_wsgi.py",
        "admin_system_authz.py",
        "admin_contact_integrity.py",
        "editorial_publish_integrity.py",
        "chatbot_hardening.py",
    )
    return "\n".join(_read(os.path.join(ROOT, name)) for name in names if os.path.exists(os.path.join(ROOT, name)))


def _inline_handlers(html: str):
    for attr, code in re.findall(r'\b(onclick|onchange|oninput)="([^"]+)"', html):
        match = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\(", code)
        if match:
            yield attr, match.group(1), code


def _is_defined(name: str, source: str) -> bool:
    patterns = (
        rf"(?:async\s+)?function\s+{re.escape(name)}\s*\(",
        rf"\b(?:const|let|var)\s+{re.escape(name)}\s*=",
        rf"\bwindow\.{re.escape(name)}\s*=",
    )
    return any(re.search(pattern, source) for pattern in patterns)


def _admin_api_paths() -> set[str]:
    source = _admin_sources()
    paths = set(re.findall(r"/api/[A-Za-z0-9_.:/-]+", source))
    return {p.rstrip(".,;:'\"") for p in paths}


def test_every_inline_admin_action_has_a_real_handler():
    html = _read(ADMIN_HTML)
    source = _admin_sources()
    missing = sorted({name for _, name, _ in _inline_handlers(html) if not _is_defined(name, source)})
    assert not missing, f"Contrôles admin sans fonction JavaScript: {', '.join(missing)}"


def test_every_admin_api_action_has_server_implementation():
    server = _server_sources()
    missing = []
    for path in sorted(_admin_api_paths()):
        if path in server:
            continue
        parent = path.rstrip("/")
        while "/" in parent[len("/api/"):]:
            parent = parent.rsplit("/", 1)[0]
            if parent and parent in server:
                break
        else:
            missing.append(path)
    assert not missing, "Routes admin sans implémentation serveur: " + ", ".join(missing)


def test_protected_api_downloads_are_authenticated():
    html = _read(ADMIN_HTML)
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert re.search(r'href="/api/', html), "Le contrat doit couvrir au moins un export API protégé"
    assert "a[href^=\"/api/\"]" in production
    assert "authenticatedDownload" in production
    assert "X-Admin-Token" in production


def test_all_authenticated_mutations_receive_csrf():
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert "X-CSRF-Token" in production
    assert "['GET', 'HEAD', 'OPTIONS']" in production
    assert "path !== '/api/login'" in production


def test_main_admin_ui_is_not_exposed_to_secondary_admins():
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert ".role-superadmin" in production
    assert "isMainAdmin()" in production


def test_destructive_controls_are_main_admin_only():
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert "enforceDestructiveControls" in production
    assert '[onclick*="clearAll("]' in production
    assert '[onclick*="runBackupNow("]' in production
    assert '[onclick*="manualBlock("]' in production
    assert "const allowed = isMainAdmin()" in production


def test_demo_notification_control_is_removed_in_production():
    html = _read(ADMIN_HTML)
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert "_addNotif('visit'" in html
    assert "removeDemoControls" in production
    assert "btn.remove()" in production


def test_security_copy_does_not_claim_fake_counts_in_production():
    production = _read(os.path.join(STATIC, "admin-production.js"))
    assert "30+ agents IA" in production and "Analyse comportementale" in production
    assert "20+ fichiers" in production and "Données protégées" in production
    assert "40+ pièges" in production and "Leurres serveur" in production


def test_session_hardening_loads_production_actions():
    session = _read(os.path.join(STATIC, "admin-session-hardening.js"))
    assert "admin-production.js" in session
    assert "data-bininga-production-hardening" in session


def test_server_side_system_authorization_stays_enabled():
    passenger = _read(os.path.join(ROOT, "passenger_wsgi.py"))
    authz = _read(os.path.join(ROOT, "admin_system_authz.py"))
    assert "admin_system_authz.guard_request" in passenger
    assert '"/api/security"' in authz
    assert '"/api/backups"' in authz
    assert '"/api/crm"' in authz
    assert '"/api/logs"' in authz


def test_editorial_publish_is_a_real_server_side_publication():
    passenger = _read(os.path.join(ROOT, "passenger_wsgi.py"))
    editorial = _read(os.path.join(ROOT, "editorial_publish_integrity.py"))
    assert "import editorial_publish_integrity" in passenger
    assert "editorial_publish_integrity.guard_request" in passenger
    assert '"/api/editorial/save"' in editorial
    assert 'server.save_data(site_data)' in editorial
    assert 'server._pg_save("editorial", rows)' in editorial
    assert '"publication_source": "editorial_ia"' in editorial
    assert '"EDITORIAL_PUBLISH"' in editorial


if __name__ == "__main__":
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"OK {test.__name__}")
    print(f"{len(tests)} contrats admin validés")
