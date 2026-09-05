"""Regression tests for automatic citizen-request -> CRM reconciliation."""
from __future__ import annotations

import copy
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import crm_auto_sync


class FakeServer:
    def __init__(self, contacts=None, crm=None):
        self.rows = copy.deepcopy(contacts or [])
        self.crm = copy.deepcopy(crm or {"contacts": [], "newsletters": []})
        self.saved = 0
        self.audit = []
        self._CONTACT_LOCK = threading.RLock()
        self._CRM_LOCK = threading.RLock()

    def load_contacts(self):
        return copy.deepcopy(self.rows)

    def load_crm(self):
        return copy.deepcopy(self.crm)

    def save_crm(self, data):
        self.crm = copy.deepcopy(data)
        self.saved += 1

    def _crm_expire_date(self):
        return "2036-09-04 23:00:00"

    def audit_log(self, action, ip, detail):
        self.audit.append((action, ip, detail))


class Handler:
    command = "GET"
    path = "/api/crm?page=1&limit=50"
    client_address = ("127.0.0.1", 0)

    def __init__(self):
        self.headers = {"X-Admin-Token": "tok"}
        self.response = None

    def _json(self, payload, status=200):
        self.response = (status, payload)


class AuthorizedServer(FakeServer):
    def get_session(self, token):
        return {"username": "admin", "role": "admin"} if token == "tok" else None


def test_historical_requests_are_added_automatically():
    server = FakeServer([
        {
            "_id": "aud-1", "type": "bininga_audiences", "objet": "Demande d'audience",
            "nom": "Mabiala", "prenom": "Chris", "email": "chris@example.com",
            "telephone": "+242061234567", "raison": "Rencontre", "ts": "2026-09-01 10:00:00",
            "_status": "en_cours",
        },
        {
            "_id": "msg-1", "type": "bininga_contacts", "nom": "Ngoma",
            "email": "ngoma@example.com", "message": "Bonjour", "ts": "2026-09-02 11:00:00",
        },
        {
            "_id": "rec-1", "type": "bininga_audiences", "objet": "Réclamation",
            "nom": "Tati", "email": "tati@example.com", "raison": "Dossier", "ts": "2026-09-03 12:00:00",
        },
    ])
    result = crm_auto_sync.sync_contacts_to_crm(server)
    assert result["added"] == 3
    assert result["total"] == 3
    by_id = {row["id"]: row for row in server.crm["contacts"]}
    assert by_id["aud-1"]["source"] == "audience"
    assert by_id["aud-1"]["statut"] == "en_cours"
    assert by_id["aud-1"]["dossiers"][0]["statut"] == "en_cours"
    assert by_id["msg-1"]["source"] == "contact"
    assert by_id["rec-1"]["source"] == "reclamation"
    assert server.saved == 1


def test_second_sync_is_idempotent_and_keeps_manual_contacts():
    manual = {
        "id": "manual-1", "nom": "Contact manuel", "email": "manuel@example.com",
        "created_at": "2026-09-01 08:00:00", "source": "manuel", "statut": "nouveau",
        "tags": ["vip"], "newsletter": False, "notes": [{"texte": "À rappeler"}],
    }
    server = FakeServer([
        {"_id": "msg-2", "type": "bininga_contacts", "nom": "Bemba", "email": "bemba@example.com", "ts": "2026-09-02 10:00:00"},
    ], {"contacts": [manual], "newsletters": []})
    first = crm_auto_sync.sync_contacts_to_crm(server)
    second = crm_auto_sync.sync_contacts_to_crm(server)
    assert first["added"] == 1
    assert second["added"] == 0
    assert second["merged"] == 0
    assert len(server.crm["contacts"]) == 2
    kept = next(row for row in server.crm["contacts"] if row["id"] == "manual-1")
    assert kept["tags"] == ["vip"]
    assert kept["notes"] == [{"texte": "À rappeler"}]


def test_existing_same_email_is_merged_across_days_not_duplicated():
    server = FakeServer([
        {
            "_id": "newsletter-original", "type": "bininga_newsletter",
            "email": "citoyen@example.com", "nom": "Makosso", "ts": "2026-09-05 10:15:00",
        },
    ], {
        "contacts": [{
            "id": "legacy-import", "email": "citoyen@example.com", "nom": "Makosso",
            "created_at": "2026-09-01 09:00:00", "source": "contact", "statut": "nouveau",
            "tags": ["contact"], "newsletter": False, "notes": [],
        }],
        "newsletters": [],
    })
    result = crm_auto_sync.sync_contacts_to_crm(server)
    assert result["added"] == 0
    assert result["merged"] == 1
    assert len(server.crm["contacts"]) == 1
    row = server.crm["contacts"][0]
    assert row["newsletter"] is True
    assert "newsletter" in row["tags"]
    assert row["source"] == "contact"
    assert row["dossiers"][0]["source"] == "newsletter"


def test_same_person_keeps_distinct_cases_and_full_evidence():
    server = FakeServer([
        {
            "_id": "aud-case", "type": "bininga_audiences", "objet": "Réclamation",
            "prenom": "E2E", "nom": "Citoyen", "email": "e2e@example.com",
            "telephone": "+242060000001", "raison": "Route endommagée",
            "tracking_code": "BIN-2026-ABC123", "ts": "2026-09-04 08:00:00",
            "photo_url": "/api/sinistre-photo/photo123", "geo_label": "Ewo, test",
            "geo_lat": "-0.87", "geo_lng": "14.82", "geo_maps_url": "https://maps.example/test",
        },
        {
            "_id": "msg-case", "type": "bininga_contacts", "sujet": "Message cabinet",
            "prenom": "E2E", "nom": "Citoyen", "email": "e2e@example.com",
            "telephone": "+242060000001", "message": "Deuxième interaction",
            "tracking_code": "BIN-2026-DEF456", "ts": "2026-09-05 09:00:00",
        },
    ])
    first = crm_auto_sync.sync_contacts_to_crm(server)
    assert first["added"] == 1
    assert first["merged"] == 1
    assert len(server.crm["contacts"]) == 1
    contact = server.crm["contacts"][0]
    assert len(contact["dossiers"]) == 2
    by_case = {d["id"]: d for d in contact["dossiers"]}
    assert by_case["aud-case"]["tracking_code"] == "BIN-2026-ABC123"
    assert by_case["aud-case"]["photo_url"] == "/api/sinistre-photo/photo123"
    assert by_case["aud-case"]["geo_label"] == "Ewo, test"
    assert by_case["aud-case"]["geo_maps_url"] == "https://maps.example/test"

    server.rows[0]["_status"] = "en_cours"
    server.rows[0]["decision"] = "favorable"
    server.rows[0]["decision_note"] = "Traitement validé"
    server.rows[0]["appointment"] = {
        "date": "08/09/2026 à 10h30", "type": "presentiel", "place": "Cabinet", "note": "Apporter les pièces"
    }
    second = crm_auto_sync.sync_contacts_to_crm(server)
    assert second["added"] == 0
    assert second["merged"] == 1
    assert len(server.crm["contacts"]) == 1
    contact = server.crm["contacts"][0]
    assert len(contact["dossiers"]) == 2
    aud = next(d for d in contact["dossiers"] if d["id"] == "aud-case")
    assert aud["statut"] == "en_cours"
    assert aud["decision"] == "favorable"
    assert aud["decision_note"] == "Traitement validé"
    assert aud["appointment"]["place"] == "Cabinet"


def test_book_and_newsletter_origins_remain_editable_in_legacy_crm():
    server = FakeServer([
        {"_id": "book", "type": "bininga_commande_livre", "email": "book@example.com", "ts": "2026-09-05 10:00:00"},
        {"_id": "news", "type": "bininga_newsletter", "email": "news@example.com", "ts": "2026-09-05 10:01:00"},
    ])
    crm_auto_sync.sync_contacts_to_crm(server)
    rows = {row["id"]: row for row in server.crm["contacts"]}
    assert rows["book"]["source"] == "contact"
    assert rows["book"]["origin_source"] == "livre"
    assert "livre" in rows["book"]["tags"]
    assert rows["news"]["source"] == "contact"
    assert rows["news"]["origin_source"] == "newsletter"
    assert rows["news"]["newsletter"] is True


def test_guard_returns_reconciled_snapshot_directly():
    server = AuthorizedServer([
        {"_id": "aud-3", "type": "bininga_audiences", "nom": "Test", "email": "test@example.com", "ts": "2026-09-04 14:00:00"},
        {"_id": "msg-3", "type": "bininga_contacts", "nom": "Deux", "email": "deux@example.com", "ts": "2026-09-04 15:00:00"},
    ])
    handler = Handler()
    assert crm_auto_sync.guard_request(server, handler) is False
    assert handler.response[0] == 200
    payload = handler.response[1]
    assert payload["ok"] is True
    assert payload["total"] == 2
    assert len(payload["contacts"]) == 2
    assert server.audit and server.audit[0][0] == "CRM_AUTO_SYNC"


def test_unrelated_get_does_nothing():
    server = FakeServer([
        {"_id": "aud-4", "type": "bininga_audiences", "email": "x@example.com"},
    ])
    handler = Handler()
    handler.path = "/api/users"
    assert crm_auto_sync.guard_request(server, handler) is True
    assert server.crm["contacts"] == []
    assert server.saved == 0


def test_navigation_directly_triggers_crm_loader_and_cache_is_busted():
    navigation = open(os.path.join(ROOT, "static", "admin-navigation.js"), encoding="utf-8").read()
    session = open(os.path.join(ROOT, "static", "admin-session-hardening.js"), encoding="utf-8").read()
    passenger = open(os.path.join(ROOT, "passenger_wsgi.py"), encoding="utf-8").read()
    assert "crm: () => typeof window.loadCrm === 'function' ? window.loadCrm(1) : null" in navigation
    assert "_triggerPanelLoader(name)" in navigation
    assert "/static/admin-navigation.js?v=20260905-admin-perf-2" in session
    assert "/static/admin-session-hardening.js?v=20260905-case-flow-1" in passenger


def test_crm_secondary_listener_is_fallback_only():
    ui_path = os.path.join(ROOT, "static", "admin-crm-sync.js")
    ui = open(ui_path, encoding="utf-8").read()
    assert "admin:panelchange" in ui
    assert "event?.detail?.name==='crm'" in ui
    assert "!window.__BININGA_ADMIN_NAVIGATION__" in ui
    assert "window.loadCrm" in ui
    assert "await window.loadCrm(1)" in ui
    assert "crm-kpi-total" in ui and "crm-kpi-nl" in ui


def run_all():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
