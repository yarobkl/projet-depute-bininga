"""Unit contracts for real Editorial IA -> public Actualites publication."""
from __future__ import annotations

import io
import json
import secrets

import editorial_publish_integrity as epi


class Headers(dict):
    def get(self, key, default=None):
        for current, value in self.items():
            if current.lower() == key.lower():
                return value
        return default


class Handler:
    command = "POST"
    path = "/api/editorial/save"
    client_address = ("127.0.0.1", 0)

    def __init__(self, payload, token="tok", csrf="csrf"):
        raw = json.dumps(payload).encode()
        self.rfile = io.BytesIO(raw)
        self.headers = Headers({"X-Admin-Token": token, "X-CSRF-Token": csrf})
        self.status = None
        self.response = None

    def _json(self, payload, status=200):
        self.status = status
        self.response = payload


class Server:
    secrets = secrets
    EDITORIAL_FILE = ""

    def __init__(self):
        self.editorial = [{
            "id": "ed-1",
            "statut": "valide",
            "titre": "Une nouvelle route pour Ewo",
            "resume": "Le projet routier entre dans une nouvelle phase.",
            "article": "Le projet routier entre dans une nouvelle phase avec un calendrier public.",
            "points_cles": ["Route", "Ewo"],
            "sources": ["Source officielle"],
            "source_nom": "Cabinet",
            "source_date": "20/08/2026",
        }]
        self.site = {"actus": {"vedettes": []}}
        self.sessions = {"tok": {"username": "admin", "role": "admin", "csrf_token": "csrf"}}
        self.audit = []

    def get_session(self, token):
        return self.sessions.get(token)

    def _pg_load(self, key):
        if key == "editorial":
            return self.editorial
        return None

    def _pg_save(self, key, value):
        assert key == "editorial"
        self.editorial = json.loads(json.dumps(value))
        return True

    def load_data(self):
        return json.loads(json.dumps(self.site))

    def save_data(self, value):
        self.site = json.loads(json.dumps(value))
        return True

    def audit_log(self, action, ip, detail):
        self.audit.append((action, ip, detail))


def test_non_publish_request_is_left_to_legacy_handler():
    server = Server()
    handler = Handler({"id": "ed-1", "statut": "valide"})
    assert epi.guard_request(server, handler) is True
    assert handler.response is None


def test_publish_requires_existing_article():
    server = Server()
    handler = Handler({"id": "missing", "statut": "publie"})
    assert epi.guard_request(server, handler) is False
    assert handler.status == 404
    assert server.site["actus"]["vedettes"] == []


def test_publish_creates_public_actualite_and_marks_editorial_published():
    server = Server()
    handler = Handler({"id": "ed-1", "statut": "publie"})
    assert epi.guard_request(server, handler) is False
    assert handler.status == 200
    assert handler.response["published"] is True

    public = server.site["actus"]["vedettes"][0]
    assert public["editorial_id"] == "ed-1"
    assert public["title"] == "Une nouvelle route pour Ewo"
    assert public["publication_source"] == "editorial_ia"
    assert public["text1"]

    editorial = server.editorial[0]
    assert editorial["statut"] == "publie"
    assert editorial["published_at"]
    assert any(row[0] == "EDITORIAL_PUBLISH" for row in server.audit)


def test_republish_is_idempotent_and_does_not_duplicate_public_article():
    server = Server()
    first = Handler({"id": "ed-1", "statut": "publie"})
    assert epi.guard_request(server, first) is False
    server.site["actus"]["vedettes"][0]["image"] = "images/news.jpg"

    server.editorial[0]["titre"] = "Titre actualisé"
    second = Handler({"id": "ed-1", "statut": "publie"})
    assert epi.guard_request(server, second) is False

    rows = server.site["actus"]["vedettes"]
    assert len(rows) == 1
    assert rows[0]["title"] == "Titre actualisé"
    assert rows[0]["image"] == "images/news.jpg"


def test_invalid_csrf_is_not_intercepted_so_legacy_security_remains_authoritative():
    server = Server()
    handler = Handler({"id": "ed-1", "statut": "publie"}, csrf="wrong")
    assert epi.guard_request(server, handler) is True
    assert server.site["actus"]["vedettes"] == []


if __name__ == "__main__":
    tests = [
        test_non_publish_request_is_left_to_legacy_handler,
        test_publish_requires_existing_article,
        test_publish_creates_public_actualite_and_marks_editorial_published,
        test_republish_is_idempotent_and_does_not_duplicate_public_article,
        test_invalid_csrf_is_not_intercepted_so_legacy_security_remains_authoritative,
    ]
    for test in tests:
        test()
        print("OK", test.__name__)
