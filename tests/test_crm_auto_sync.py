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
    assert len(server.crm["contacts"]) == 2
    kept = next(row for row in server.crm["contacts"] if row["id"] == "manual-1")
    assert kept["tags"] == ["vip"]
    assert kept["notes"] == [{"texte": "À rappeler"}]


def test_existing_same_identity_is_merged_not_duplicated():
    server = FakeServer([
        {
            "_id": "newsletter-original", "type": "bininga_newsletter",
            "email": "citoyen@example.com", "nom": "Makosso", "ts": "2026-09-04 10:15:00",
        },
    ], {
        "contacts": [{
            "id": "legacy-import", "email": "citoyen@example.com", "nom": "Makosso",
            "created_at": "2026-09-04 09:00:00", "source": "contact", "statut": "nouveau",
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


def test_guard_runs_on_crm_get_and_audits_changes():
    server = FakeServer([
        {"_id": "aud-3", "type": "bininga_audiences", "nom": "Test", "email": "test@example.com", "ts": "2026-09-04 14:00:00"},
    ])
    handler = Handler()
    assert crm_auto_sync.guard_request(server, handler) is True
    assert len(server.crm["contacts"]) == 1
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


def run_all():
    for test in (
        test_historical_requests_are_added_automatically,
        test_second_sync_is_idempotent_and_keeps_manual_contacts,
        test_existing_same_identity_is_merged_not_duplicated,
        test_guard_runs_on_crm_get_and_audits_changes,
        test_unrelated_get_does_nothing,
    ):
        test()
        print(f"✅ {test.__name__}")


if __name__ == "__main__":
    run_all()
