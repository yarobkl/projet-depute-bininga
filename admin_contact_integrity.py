"""Integrity guard for BININGA admin operational records.

This module is intentionally small and loaded from ``passenger_wsgi.py``.  It
hardens the legacy contact/CRM handlers without rewriting the large server.py:

* legacy form records receive stable deterministic IDs;
* source/type aliases are normalized consistently;
* contact updates are validated before they reach the legacy handler;
* destructive contact operations are owner-only;
* read/modify/write mutations are serialized to avoid lost updates.

The public form endpoints and their existing CSRF/auth/rate-limit behaviour stay
inside server.py.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import threading
from typing import Any, Dict, Iterable, List

import admin_owners

_ALLOWED_CONTACT_STATUS = {"en_attente", "en_cours", "traite", "non_lu", "lu"}
_CONTACT_MUTATIONS = {"/api/contacts/update", "/api/contacts/clear"}
_CRM_MUTATIONS = {
    "/api/crm/upsert",
    "/api/crm/delete",
    "/api/crm/bulk-delete",
    "/api/crm/import",
    "/api/crm/note",
    "/api/crm/newsletter/send",
}

_SOURCE_ALIASES = {
    "audience": "bininga_audiences",
    "audiences": "bininga_audiences",
    "demande_audience": "bininga_audiences",
    "reclamation": "bininga_audiences",
    "réclamation": "bininga_audiences",
    "bininga_audiences": "bininga_audiences",
    "contact": "bininga_contacts",
    "message": "bininga_contacts",
    "bininga_contacts": "bininga_contacts",
    "newsletter": "bininga_newsletter",
    "bininga_newsletter": "bininga_newsletter",
    "livre": "bininga_commande_livre",
    "commande_livre": "bininga_commande_livre",
    "bininga_commande_livre": "bininga_commande_livre",
}

_installed = False
_original_load_contacts = None
_original_save_contacts = None


def _canonical_source(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return _SOURCE_ALIASES.get(raw.lower(), raw)


def _legacy_signature(entry: Dict[str, Any]) -> str:
    tracking = str(entry.get("tracking_code", "")).strip().upper()
    if tracking:
        return "tracking|" + tracking

    fields = [
        entry.get("source") or entry.get("type", ""),
        entry.get("ts") or entry.get("_date") or entry.get("created_at", ""),
        entry.get("email", ""),
        entry.get("telephone") or entry.get("tel", ""),
        entry.get("prenom", ""),
        entry.get("nom", ""),
        entry.get("objet", ""),
        entry.get("raison") or entry.get("message", ""),
    ]
    return json.dumps(fields, ensure_ascii=False, separators=(",", ":"), default=str)


def _base_legacy_id(entry: Dict[str, Any]) -> str:
    digest = hashlib.sha256(_legacy_signature(entry).encode("utf-8")).hexdigest()[:24]
    return "legacy_" + digest


def normalize_contacts(rows: Any) -> List[Dict[str, Any]]:
    """Return a normalized copy of contact rows with stable IDs.

    Existing IDs are never changed. Exact duplicate legacy rows get a stable
    occurrence suffix according to their persisted order.
    """
    if not isinstance(rows, list):
        return []

    result: List[Dict[str, Any]] = []
    seen_legacy: Dict[str, int] = {}

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)

        source = _canonical_source(item.get("source") or item.get("type"))
        if source:
            item["source"] = source
            item["type"] = source

        current_id = str(item.get("_id") or "").strip()
        if not current_id:
            base = _base_legacy_id(item)
            occurrence = seen_legacy.get(base, 0)
            seen_legacy[base] = occurrence + 1
            item["_id"] = base if occurrence == 0 else f"{base}_{occurrence}"

        result.append(item)

    return result


def install(server) -> None:
    """Patch only the contact load/save boundary of server.py."""
    global _installed, _original_load_contacts, _original_save_contacts
    if _installed:
        return

    _original_load_contacts = server.load_contacts
    _original_save_contacts = server.save_contacts

    server._CONTACT_LOCK = threading.RLock()
    server._CRM_LOCK = threading.RLock()

    def load_contacts_normalized():
        return normalize_contacts(_original_load_contacts())

    def save_contacts_normalized(rows):
        return _original_save_contacts(normalize_contacts(rows))

    server.load_contacts = load_contacts_normalized
    server.save_contacts = save_contacts_normalized
    _installed = True


def _rewrite_json_body(handler, payload: Dict[str, Any]) -> None:
    patched = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.rfile = io.BytesIO(patched)
    if handler.headers.get("Content-Length") is not None:
        handler.headers.replace_header("Content-Length", str(len(patched)))
    else:
        handler.headers["Content-Length"] = str(len(patched))


def _csrf_is_valid(server, handler, session: Dict[str, Any]) -> bool:
    received = handler.headers.get("X-CSRF-Token", "")
    expected = str(session.get("csrf_token", ""))
    if not received or not expected:
        return False
    try:
        return server.secrets.compare_digest(str(received), expected)
    except Exception:
        return str(received) == expected


def _sanitize_notes(notes: Any) -> List[Dict[str, str]]:
    if not isinstance(notes, list):
        raise ValueError("Format de notes invalide")
    clean: List[Dict[str, str]] = []
    for note in notes[-100:]:
        if not isinstance(note, dict):
            continue
        clean.append({
            "auteur": str(note.get("auteur", "Admin"))[:120],
            "texte": str(note.get("texte", ""))[:2000],
            "date": str(note.get("date") or note.get("ts") or "")[:80],
        })
    return clean


def guard_request(server, handler) -> bool:
    """Validate dangerous contact mutations before server.py handles them."""
    if handler.command != "POST":
        return True

    path = handler.path.split("?", 1)[0]
    if path not in _CONTACT_MUTATIONS and path != "/api/reset":
        return True

    token = handler.headers.get("X-Admin-Token", "")
    session = server.get_session(token) if token else None
    if not session:
        return True

    if path in {"/api/contacts/clear", "/api/reset"}:
        if not admin_owners.is_owner_session(server, session):
            server.audit_log(
                "AUTHZ_REJECT",
                handler.client_address[0],
                f"Opération destructive refusée sur {path} pour {session.get('username', '?')}",
            )
            handler._json({"ok": False, "message": "Réservé aux propriétaires de l’administration"}, 403)
            return False
        return True

    if not _csrf_is_valid(server, handler, session):
        return True

    raw = handler.rfile.getvalue()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return True
    if not isinstance(payload, dict):
        handler._json({"ok": False, "message": "Données invalides"}, 400)
        return False

    cid = str(payload.get("id", "")).strip()
    if not cid:
        handler._json({"ok": False, "message": "ID requis"}, 400)
        return False

    if not any(str(row.get("_id", "")) == cid for row in server.load_contacts()):
        handler._json({"ok": False, "message": "Dossier introuvable"}, 404)
        return False

    clean: Dict[str, Any] = {"id": cid}
    if "status" in payload:
        status = str(payload.get("status", "")).strip()
        if status not in _ALLOWED_CONTACT_STATUS:
            handler._json({"ok": False, "message": "Statut invalide"}, 400)
            return False
        clean["status"] = status

    if "notes" in payload:
        try:
            clean["notes"] = _sanitize_notes(payload.get("notes"))
        except ValueError as exc:
            handler._json({"ok": False, "message": str(exc)}, 400)
            return False

    if "pinged" in payload:
        if not isinstance(payload.get("pinged"), bool):
            handler._json({"ok": False, "message": "Valeur d'alerte invalide"}, 400)
            return False
        clean["pinged"] = payload["pinged"]

    if "pinged_date" in payload:
        clean["pinged_date"] = str(payload.get("pinged_date", ""))[:80]

    if len(clean) == 1:
        handler._json({"ok": False, "message": "Aucune modification valide"}, 400)
        return False

    _rewrite_json_body(handler, clean)
    return True


@contextlib.contextmanager
def mutation_guard(server, handler):
    """Serialize legacy read/modify/write API mutations to avoid lost updates."""
    path = handler.path.split("?", 1)[0]
    with contextlib.ExitStack() as stack:
        if path in _CONTACT_MUTATIONS:
            stack.enter_context(server._CONTACT_LOCK)
        elif path == "/api/reset":
            stack.enter_context(server._CONTACT_LOCK)
            stack.enter_context(server._CRM_LOCK)
        elif path == "/api/crm/import":
            stack.enter_context(server._CONTACT_LOCK)
            stack.enter_context(server._CRM_LOCK)
        elif path in _CRM_MUTATIONS:
            stack.enter_context(server._CRM_LOCK)
        yield
