"""Regression tests for Vercel backup history and download-first UX."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import backup_download
import serverless_backup_history


class Handler:
    command = "GET"
    path = "/api/backups"
    client_address = ("127.0.0.1", 0)

    def __init__(self, token="tok"):
        self.headers = {"X-Admin-Token": token}
        self.response = None

    def _json(self, payload, status=200):
        self.response = (status, payload)


class Server:
    def __init__(self, role="admin"):
        self.role = role
        self.store = {}

    def get_session(self, token):
        return {"username": "admin", "role": self.role} if token == "tok" else None

    def _pg_load(self, key):
        return self.store.get(key)

    def _pg_save(self, key, value):
        self.store[key] = value
        return True

    def _db_label(self):
        return "PostgreSQL"


def test_backup_download_records_durable_history():
    server = Server()
    manifest = {
        "created_at": "2026-09-04T20:00:00Z",
        "backend": "postgresql",
        "store_count": 12,
        "photo_count": 4,
    }
    backup_download._record_history(server, "bininga-test.zip", b"zip-bytes", manifest, {"username": "admin"})
    rows = server.store["backup_history"]
    assert len(rows) == 1
    assert rows[0]["name"] == "bininga-test.zip"
    assert rows[0]["store_count"] == 12
    assert rows[0]["photo_count"] == 4
    assert rows[0]["bytes"] == len(b"zip-bytes")


def test_vercel_backups_get_returns_export_history_not_tmp_folders():
    old = os.environ.get("VERCEL")
    os.environ["VERCEL"] = "1"
    try:
        server = Server()
        server.store["backup_history"] = [
            {"name": "old.zip", "created_at": "2026-09-03T10:00:00Z", "kind": "downloaded_archive"},
            {"name": "new.zip", "created_at": "2026-09-04T10:00:00Z", "kind": "downloaded_archive"},
        ]
        handler = Handler()
        assert serverless_backup_history.guard_request(server, handler) is False
        status, payload = handler.response
        assert status == 200
        assert payload["ok"] is True
        assert payload["storage"]["mode"] == "download"
        assert payload["storage"]["history_durable"] is True
        assert [row["name"] for row in payload["backups"]] == ["new.zip", "old.zip"]
        assert payload["latest"]["name"] == "new.zip"
    finally:
        if old is None:
            os.environ.pop("VERCEL", None)
        else:
            os.environ["VERCEL"] = old


def test_non_vercel_defers_to_legacy_backup_listing():
    old = os.environ.pop("VERCEL", None)
    old_env = os.environ.pop("VERCEL_ENV", None)
    try:
        handler = Handler()
        assert serverless_backup_history.guard_request(Server(), handler) is True
        assert handler.response is None
    finally:
        if old is not None:
            os.environ["VERCEL"] = old
        if old_env is not None:
            os.environ["VERCEL_ENV"] = old_env


def test_download_first_admin_module_is_wired():
    session = (ROOT / "static" / "admin-session-hardening.js").read_text(encoding="utf-8")
    ux = (ROOT / "static" / "admin-backup-ux.js").read_text(encoding="utf-8")
    pipeline = (ROOT / "admin_request_pipeline.py").read_text(encoding="utf-8")
    assert "admin-backup-ux.js" in session
    assert "Créer et télécharger une sauvegarde" in ux
    assert "window.runBackupNow=run" in ux
    assert "history_durable" in ux
    assert "serverless_backup_history.guard_request" in pipeline


def run_all():
    for test in (
        test_backup_download_records_durable_history,
        test_vercel_backups_get_returns_export_history_not_tmp_folders,
        test_non_vercel_defers_to_legacy_backup_listing,
        test_download_first_admin_module_is_wired,
    ):
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
