"""Contracts for server-first CRM privacy and dossier-history rendering."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_browser_pii_backup_is_disabled_before_admin_init():
    source = read("static/admin-crm-integrity.js")
    session = read("static/admin-session-hardening.js")
    assert "bininga_crm_backup" in source
    assert "localStorage.removeItem(LEGACY_BACKUP_KEY)" in source
    assert "window._crmSaveBackup" in source
    assert "window._crmRestoreFromBackup" in source
    assert "window._crmBackupAllInBackground" in source
    assert "admin-crm-integrity.js?v=20260905-crm-integrity-1" in session
    critical = session[session.index("const criticalModules"):session.index("const optionalModules")]
    assert "admin-crm-integrity.js" in critical


def test_crm_detail_exposes_complete_case_history():
    source = read("static/admin-crm-integrity.js")
    assert "Dossiers & interactions" in source
    for field in (
        "tracking_code", "source", "statut", "nom", "prenom", "email", "telephone",
        "sujet", "message", "decision", "decision_note", "appointment", "photo_url",
        "geo_label", "geo_lat", "geo_lng", "geo_maps_url",
    ):
        assert field in source, field
    assert "Ouvrir la carte" in source
    assert "Voir la photo" in source
    assert "window.crmDetail" in source
    assert "window.renderCrmList" in source


def test_crm_integrity_has_no_network_or_observer_side_effect_at_load():
    source = read("static/admin-crm-integrity.js")
    assert "MutationObserver" not in source
    assert "fetch(" not in source
    assert "apiFetch(" not in source


def test_request_pipeline_runs_immediate_crm_postprocessing():
    pipeline = read("admin_request_pipeline.py")
    sync = read("crm_auto_sync.py")
    assert "crm_auto_sync.postprocess_response(server, handler)" in pipeline
    assert 'path != "/api/contact"' in sync
    assert "CRM_SUBMISSION_SYNC" in sync


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests:
        test()
        print("OK", test.__name__)
    print(f"{len(tests)} tests intégrité CRM validés")
