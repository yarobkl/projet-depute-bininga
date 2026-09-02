"""Contrats de l'archive de reprise administrateur."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backup_bininga
import backup_download


class Headers(dict):
    def get(self, key, default=None):
        for current, value in self.items():
            if current.lower() == key.lower():
                return value
        return default


class Handler:
    command = "POST"
    path = "/api/backups/export"
    client_address = ("127.0.0.1", 0)

    def __init__(self, token="tok", csrf="csrf"):
        self.headers = Headers({"X-Admin-Token": token, "X-CSRF-Token": csrf})
        self.wfile = io.BytesIO()
        self.status = None
        self.response_headers = {}
        self.response = None

    def _json(self, payload, status=200):
        self.status = status
        self.response = payload

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass


class Server:
    def __init__(self, role="admin"):
        self.sessions = {"tok": {"role": role, "csrf_token": "csrf"}}
        self.audit = []

    def get_session(self, token):
        return self.sessions.get(token)

    def audit_log(self, action, ip, detail):
        self.audit.append((action, ip, detail))


def fake_snapshot():
    store = b'{"data":{"hero":"ok"}}\n'
    photo = b"\xff\xd8test-photo\xff\xd9"
    files = {"bininga_store.json": store, "photos/photo.jpg": photo}
    manifest = {
        "format": "bininga-backup",
        "format_version": 2,
        "created_at": "2026-09-01T00:00:00Z",
        "backend": "test",
        "store_count": 1,
        "photo_count": 1,
        "photos": [{
            "id": "photo", "file": "photos/photo.jpg", "content_type": "image/jpeg",
            "bytes": len(photo), "sha256": backup_bininga._sha256(photo),
        }],
        "files": {
            name: {"bytes": len(content), "sha256": backup_bininga._sha256(content)}
            for name, content in files.items()
        },
    }
    return "bininga-test", manifest, files


def test_archive_is_downloadable_and_verifiable():
    original = backup_bininga.collect_snapshot
    backup_bininga.collect_snapshot = fake_snapshot
    try:
        handler = Handler()
        server = Server()
        assert backup_download.guard_request(server, handler) is False
        assert handler.status == 200
        assert handler.response_headers["Content-Type"] == "application/zip"
        assert handler.response_headers["Cache-Control"].startswith("no-store")
        assert zipfile.is_zipfile(io.BytesIO(handler.wfile.getvalue()))
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "backup.zip"
            archive.write_bytes(handler.wfile.getvalue())
            manifest = backup_bininga.verify_backup(archive)
        assert manifest["photo_count"] == 1
        assert any(row[0] == "BACKUP_EXPORT" for row in server.audit)
    finally:
        backup_bininga.collect_snapshot = original


def test_export_requires_admin_and_csrf():
    handler = Handler()
    assert backup_download.guard_request(Server(role="editeur"), handler) is False
    assert handler.status == 403

    handler = Handler(csrf="wrong")
    assert backup_download.guard_request(Server(), handler) is False
    assert handler.status == 403


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("OK", test.__name__)
