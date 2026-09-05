"""Automatic reconciliation between citizen requests and the BININGA CRM.

Historically, records received through public forms were stored in the contacts
store and only copied to the CRM when an administrator pressed "Importer
demandes". This bridge makes the CRM self-healing and, for GET /api/crm,
returns the reconciled data directly so the UI cannot observe a stale zero
between reconciliation and the legacy handler's second database read.

The operation is idempotent and preserves manually-created CRM contacts.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _source(raw: dict) -> str:
    value = str(raw.get("source") or raw.get("type") or "contact").strip().lower()
    if value in {"bininga_audiences", "audience", "audiences", "demande_audience"}:
        objet = f"{raw.get('objet', '')} {raw.get('sujet', '')}".lower()
        return "reclamation" if "réclamation" in objet or "reclamation" in objet else "audience"
    if value in {"reclamation", "réclamation"}:
        return "reclamation"
    if value in {"bininga_newsletter", "newsletter"}:
        return "newsletter"
    if value in {"bininga_commande_livre", "commande_livre", "livre"}:
        return "livre"
    if value in {"bininga_contacts", "contact", "message"}:
        return "contact"
    if value == "signalement":
        return "signalement"
    return "contact"


def _crm_status(raw: dict) -> str:
    value = str(raw.get("_status") or raw.get("status") or "").strip().lower()
    if value == "traite":
        return "traite"
    if value == "en_cours":
        return "en_cours"
    if value == "archive":
        return "archive"
    return "nouveau"


def _stable_id(raw: dict) -> str:
    current = str(raw.get("_id") or raw.get("id") or "").strip()
    if current:
        return current
    tracking = str(raw.get("tracking_code") or "").strip().upper()
    if tracking:
        return "tracking_" + tracking
    basis = json.dumps(
        [
            raw.get("source") or raw.get("type"),
            raw.get("ts") or raw.get("_date") or raw.get("created_at"),
            raw.get("email"), raw.get("telephone") or raw.get("tel"),
            raw.get("prenom"), raw.get("nom"), raw.get("objet"),
            raw.get("raison") or raw.get("message"),
        ],
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return "crm_auto_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def _date_key(value: Any) -> str:
    return str(value or "")[:10]


def _identity_key(row: dict) -> tuple[str, str, str, str]:
    email = str(row.get("email") or "").strip().lower()
    phone = "".join(ch for ch in str(row.get("telephone") or row.get("tel") or "") if ch.isdigit())
    name = " ".join(
        p for p in [str(row.get("prenom") or "").strip().lower(), str(row.get("nom") or "").strip().lower()] if p
    )
    created = row.get("created_at") or row.get("ts") or row.get("_date") or ""
    return email, phone, name, _date_key(created)


def _merge_existing(existing: dict, raw: dict, source: str, now: str) -> bool:
    changed = False
    fill = {
        "nom": _text(raw.get("nom"), 200),
        "prenom": _text(raw.get("prenom"), 200),
        "email": _text(raw.get("email"), 200),
        "telephone": _text(raw.get("telephone") or raw.get("tel"), 50),
        "sujet": _text(raw.get("sujet") or raw.get("objet"), 500),
        "message": _text(raw.get("message") or raw.get("demande") or raw.get("raison") or raw.get("description"), 2000),
    }
    for key, value in fill.items():
        if value and not str(existing.get(key) or "").strip():
            existing[key] = value
            changed = True

    if source == "newsletter" and not existing.get("newsletter"):
        existing["newsletter"] = True
        changed = True
    tags = existing.setdefault("tags", [])
    if not isinstance(tags, list):
        tags = []
        existing["tags"] = tags
        changed = True
    for tag in ([source] + (["newsletter"] if source == "newsletter" else [])):
        if tag and tag not in tags:
            tags.append(tag)
            changed = True
    if changed:
        existing["updated_at"] = now
    return changed


def sync_contacts_to_crm(server: Any) -> dict:
    """Insert/merge citizen records that are missing from the CRM."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with contextlib.ExitStack() as stack:
        contact_lock = getattr(server, "_CONTACT_LOCK", None)
        crm_lock = getattr(server, "_CRM_LOCK", None)
        if contact_lock is not None:
            stack.enter_context(contact_lock)
        if crm_lock is not None:
            stack.enter_context(crm_lock)

        rows = server.load_contacts()
        crm = server.load_crm()
        if not isinstance(crm, dict):
            crm = {"contacts": [], "newsletters": []}
        contacts = crm.setdefault("contacts", [])
        if not isinstance(contacts, list):
            contacts = []
            crm["contacts"] = contacts
        crm.setdefault("newsletters", [])

        by_id = {str(c.get("id") or "").strip(): c for c in contacts if isinstance(c, dict) and str(c.get("id") or "").strip()}
        by_identity = {}
        for c in contacts:
            if not isinstance(c, dict):
                continue
            key = _identity_key(c)
            if key[0] or key[1]:
                by_identity.setdefault(key, c)

        added = 0
        merged = 0
        for raw in rows if isinstance(rows, list) else []:
            if not isinstance(raw, dict):
                continue
            cid = _stable_id(raw)
            source = _source(raw)
            created = _text(raw.get("ts") or raw.get("_date") or raw.get("created_at") or now, 80)
            identity = _identity_key({**raw, "created_at": created})
            existing = by_id.get(cid)
            if existing is None and (identity[0] or identity[1]):
                existing = by_identity.get(identity)
            if existing is not None:
                if _merge_existing(existing, raw, source, now):
                    merged += 1
                by_id[cid] = existing
                continue

            tags = [source] if source else []
            if source == "newsletter" and "newsletter" not in tags:
                tags.append("newsletter")
            expiry_fn = getattr(server, "_crm_expire_date", None)
            expires = expiry_fn() if callable(expiry_fn) else ""
            contact = {
                "id": cid,
                "created_at": created,
                "updated_at": now,
                "expires_at": expires,
                "nom": _text(raw.get("nom"), 200),
                "prenom": _text(raw.get("prenom"), 200),
                "email": _text(raw.get("email"), 200),
                "telephone": _text(raw.get("telephone") or raw.get("tel"), 50),
                "sujet": _text(raw.get("sujet") or raw.get("objet"), 500),
                "message": _text(raw.get("message") or raw.get("demande") or raw.get("raison") or raw.get("description"), 2000),
                "source": source,
                "tags": tags,
                "statut": _crm_status(raw),
                "newsletter": source == "newsletter",
                "notes": [],
            }
            contacts.append(contact)
            by_id[cid] = contact
            if identity[0] or identity[1]:
                by_identity[identity] = contact
            added += 1

        if added or merged:
            server.save_crm(crm)
        return {"added": added, "merged": merged, "total": len(contacts), "crm": crm, "source_total": len(rows) if isinstance(rows, list) else 0}


def _matches_query(contact: dict, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        str(contact.get(key) or "")
        for key in ("nom", "prenom", "email", "telephone", "sujet", "message", "source", "statut")
    ).lower()
    tags = contact.get("tags") or []
    if isinstance(tags, list):
        haystack += " " + " ".join(str(tag) for tag in tags).lower()
    return query in haystack


def _response_payload(handler: Any, result: dict) -> dict:
    crm = result.get("crm") if isinstance(result.get("crm"), dict) else {"contacts": [], "newsletters": []}
    all_contacts = [c for c in crm.get("contacts", []) if isinstance(c, dict)]
    qs = parse_qs(urlparse(str(getattr(handler, "path", ""))).query)
    try:
        page = max(1, int(qs.get("page", ["1"])[0]))
    except Exception:
        page = 1
    try:
        limit = min(5000, max(10, int(qs.get("limit", ["50"])[0])))
    except Exception:
        limit = 50
    query = str(qs.get("q", [""])[0]).lower().strip()
    source = str(qs.get("source", [""])[0]).strip()
    newsletter_filter = str(qs.get("nl", [""])[0]).strip().lower()

    filtered = []
    for contact in all_contacts:
        if source and str(contact.get("source") or "") != source:
            continue
        subscribed = bool(contact.get("newsletter"))
        if newsletter_filter == "oui" and not subscribed:
            continue
        if newsletter_filter == "non" and subscribed:
            continue
        if not _matches_query(contact, query):
            continue
        filtered.append(contact)

    filtered.sort(key=lambda c: str(c.get("updated_at") or c.get("created_at") or ""), reverse=True)
    total = len(filtered)
    pages = max(1, math.ceil(total / limit))
    page = min(page, pages)
    start = (page - 1) * limit
    contacts = filtered[start:start + limit]
    return {
        "ok": True,
        "contacts": contacts,
        "newsletters": crm.get("newsletters", []) if isinstance(crm.get("newsletters"), list) else [],
        "total": total,
        "page": page,
        "pages": pages,
        "limit": limit,
        "newsletter_count": sum(1 for c in all_contacts if c.get("newsletter") and c.get("email")),
        "sync": {
            "added": int(result.get("added") or 0),
            "merged": int(result.get("merged") or 0),
            "source_total": int(result.get("source_total") or 0),
            "crm_total": len(all_contacts),
        },
    }


def guard_request(server: Any, handler: Any) -> bool:
    """Reconcile and answer GET /api/crm from the same in-memory snapshot."""
    path = str(getattr(handler, "path", "")).split("?", 1)[0]
    method = str(getattr(handler, "command", "GET")).upper()
    if method != "GET" or path != "/api/crm":
        return True
    try:
        result = sync_contacts_to_crm(server)
        if result["added"] or result["merged"]:
            try:
                ip = handler.client_address[0]
            except Exception:
                ip = "unknown"
            try:
                server.audit_log(
                    "CRM_AUTO_SYNC",
                    ip,
                    f"CRM synchronisé automatiquement : +{result['added']} ajout(s), {result['merged']} fusion(s)",
                )
            except Exception:
                pass
        handler._json(_response_payload(handler, result))
        return False
    except Exception as exc:
        # Preserve availability by falling through to the legacy handler, but
        # make the failure observable in Vercel logs instead of silently
        # returning a stale zero forever.
        print(f"[CRM] Auto-sync fallback: {type(exc).__name__}: {exc}", flush=True)
        return True
