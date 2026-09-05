"""End-to-end contracts around citizen case capture and admin treatment."""
from __future__ import annotations

import io
import json
import os
import sys
from email.message import Message

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import admin_contact_integrity as integrity


class FakeServer:
    def __init__(self):
        self.rows = [{"_id": "case-1", "source": "bininga_audiences"}]
        self.secrets = __import__("secrets")

    def get_session(self, token):
        if token != "tok":
            return None
        return {"username": "admin", "role": "admin", "csrf_token": "csrf"}

    def load_contacts(self):
        return list(self.rows)

    def audit_log(self, *args):
        pass


class Handler:
    command = "POST"
    path = "/api/contacts/update"
    client_address = ("127.0.0.1", 0)

    def __init__(self, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.rfile = io.BytesIO(raw)
        self.headers = Message()
        self.headers["Content-Length"] = str(len(raw))
        self.headers["Content-Type"] = "application/json"
        self.headers["X-Admin-Token"] = "tok"
        self.headers["X-CSRF-Token"] = "csrf"
        self.response = None

    def _json(self, payload, status=200):
        self.response = (status, payload)


def rewritten(handler):
    return json.loads(handler.rfile.getvalue().decode("utf-8"))


def test_integrity_guard_preserves_decision_and_appointment():
    handler = Handler({
        "id": "case-1",
        "decision": "favorable",
        "decision_note": "Audience accordée",
        "appointment": {
            "date": "08/09/2026 à 10h30",
            "type": "presentiel",
            "place": "Cabinet du député",
            "note": "Apporter les pièces",
        },
    })
    assert integrity.guard_request(FakeServer(), handler) is True
    body = rewritten(handler)
    assert body["decision"] == "favorable"
    assert body["decision_note"] == "Audience accordée"
    assert body["appointment"]["date"] == "08/09/2026 à 10h30"
    assert body["appointment"]["type"] == "presentiel"
    assert body["appointment"]["place"] == "Cabinet du député"


def test_integrity_guard_allows_appointment_cancellation():
    handler = Handler({"id": "case-1", "appointment": {}})
    assert integrity.guard_request(FakeServer(), handler) is True
    assert rewritten(handler)["appointment"] == {}


def test_integrity_guard_rejects_invalid_decision():
    handler = Handler({"id": "case-1", "decision": "accepter_tout"})
    assert integrity.guard_request(FakeServer(), handler) is False
    assert handler.response[0] == 400
    assert "Décision invalide" in handler.response[1]["message"]


def test_frontend_treatment_is_server_first_and_manual_geo_is_visible():
    source = open(os.path.join(ROOT, "static", "admin-case-treatment.js"), encoding="utf-8").read()
    session = open(os.path.join(ROOT, "static", "admin-session-hardening.js"), encoding="utf-8").read()
    assert "window.setDecision = async" in source
    assert "window.setAppointment = async" in source
    assert "window.clearAppointment = async" in source
    assert "await checkedUpdate({ id: cid, decision" in source
    assert "await checkedUpdate({ id: cid, appointment" in source
    assert "data-manual-location" in source
    assert "row.geo_label" in source and "row.geo_maps_url" in source
    assert "admin-case-treatment.js?v=20260905-case-flow-1" in session


def test_public_forms_capture_expected_evidence_and_sources():
    core = open(os.path.join(ROOT, "static", "index-core.js"), encoding="utf-8").read()
    page = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    hardening = open(os.path.join(ROOT, "static", "public-form-hardening.js"), encoding="utf-8").read()
    server = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    assert 'sendForm("bininga_audiences"' in core
    assert 'fetch("/api/upload-sinistre"' in core
    # JavaScript manipulates DOM ids with dashes; the submitted FormData keys are
    # the hidden input names with underscores. Validate both sides of that bridge.
    for dom_id in ("geo-lat", "geo-lng", "geo-label", "geo-maps-url"):
        assert dom_id in core
    for field_name in ("geo_lat", "geo_lng", "geo_label", "geo_maps_url"):
        assert f'name="{field_name}"' in page
    assert "photo-url" in core
    assert 'name="photo-url"' in page
    assert "entry.type = storageKey" in hardening
    assert 'type: "bininga_commande_livre"' in hardening
    assert 'type: "bininga_newsletter"' in hardening
    assert '"bininga_audiences", "bininga_contacts", "bininga_commande_livre"' in server
    assert "/api/sinistre-photo/" in server
    assert "_pg_save_photo" in server


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("OK", test.__name__)
    print(f"{len(tests)} tests flux dossiers citoyens validés")
