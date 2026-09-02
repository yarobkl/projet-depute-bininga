"""Architecture regression contracts for BININGA.

These checks do not require a framework rewrite. They prevent the historical
bundles from regaining cross-cutting responsibilities that now have dedicated
modules.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def size(relative: str) -> int:
    return (ROOT / relative).stat().st_size


def test_admin_core_is_loaded_before_feature_modules() -> None:
    session = read("static/admin-session-hardening.js")
    assert "admin-core.js" in session
    assert session.index("admin-core.js") < session.index("admin-navigation.js")
    assert session.index("admin-core.js") < session.index("admin-production.js")


def test_admin_core_owns_shared_auth_primitives() -> None:
    core = read("static/admin-core.js")
    production = read("static/admin-production.js")
    for name in ("token", "csrf", "role", "username", "isMainAdmin", "apiPath", "authHeaders", "request"):
        assert name in core
    assert "window.BiningaAdminCore = core" in core
    assert "window.authHeaders = authHeaders" in core
    assert "window.apiFetch = request" in core
    assert "const core = window.BiningaAdminCore" in production
    for duplicate in ("const token = () =>", "const csrf = () =>", "const isMainAdmin = () =>", "const apiPath = value =>"):
        assert duplicate not in production


def test_active_admin_session_is_not_persisted_in_local_storage() -> None:
    session = read("static/admin-session-hardening.js")
    core = read("static/admin-core.js")
    assert "sessionStorage.setItem(KEY" in session
    assert "localStorage.setItem(KEY" not in session
    assert "localStorage.setItem(SESSION_KEY" not in core


def test_wsgi_uses_one_named_guard_pipeline() -> None:
    passenger = read("passenger_wsgi.py")
    pipeline = read("admin_request_pipeline.py")
    assert "admin_request_pipeline.allow_request" in passenger
    assert "admin_request_pipeline.mutation_context" in passenger
    for guard in (
        "admin_system_authz.guard_request",
        "admin_contact_integrity.guard_request",
        "backup_download.guard_request",
        "editorial_publish_integrity.guard_request",
        "chatbot_hardening.guard_request",
    ):
        assert guard in pipeline


def test_historical_bundles_have_growth_budgets() -> None:
    # Budgets are intentionally just above the current baseline. New business
    # features must go into dedicated modules instead of silently extending the
    # legacy compatibility bundles.
    assert size("static/admin.js") <= 205_000
    assert size("admin.html") <= 115_000
    assert size("server.py") <= 275_000


def test_architecture_is_documented() -> None:
    doc = read("docs/ARCHITECTURE.md")
    assert "static/admin-core.js" in doc
    assert "admin_request_pipeline.py" in doc
    assert "strangler" in doc.lower()


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"OK {test.__name__}")
    print(f"{len(tests)} contrats d'architecture validés")


if __name__ == "__main__":
    main()
