"""Automatic reconciliation between citizen requests and the BININGA CRM.

The CRM is person-centric while each public submission remains a distinct case.
Every reconciliation keeps a ``dossiers`` history on the CRM contact so status,
tracking, evidence, decision, appointment and submitted identity cannot disappear
when the same citizen contacts the cabinet more than once.

The bridge runs both when the CRM is read and immediately after a successful
public ``POST /api/contact``. This prevents a window where a request is persisted
but not yet visible in the CRM.
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


def _crm_source(source: str) -> str:
    """Use only sources accepted by the legacy CRM editor."""
    if source in {"audience", "contact", "reclamation", "signalement", "manuel"}:
        return source
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


def _email(row: dict) -> str:
    return str(row.get("email") or "").strip().lower()


def _phone(row: dict) -> str:
    return "".join(ch for ch in str(row.get("telephone") or row.get("tel") or "") if ch.isdigit())


def _name_key(row: dict) -> str:
    return " ".join(
        part for part in (
            str(row.get("prenom") or "").strip().casefold(),
            str(row.get("nom") or "").strip().casefold(),
        ) if part
    )


def _phone_candidate(candidates: list[dict], raw: dict) -> dict | None:
    """Resolve a phone match without merging unrelated people sharing a number."""
    if not candidates:
        return None
    email = _email(raw)
    name = _name_key(raw)

    if name:
        same_name = [candidate for candidate in candidates if _name_key(candidate) == name]
        if len(same_name) == 1:
            return same_name[0]

    if not email and len(candidates) == 1:
        return candidates[0]

    if email:
        without_email = [candidate for candidate in candidates if not _email(candidate)]
        if len(without_email) == 1:
            return without_email[0]
    return None


def _case_snapshot(raw: dict, source: str, cid: str, created: str) -> dict:
    appointment = raw.get("appointment") if isinstance(raw.get("appointment"), dict) else {}
    return {
        "id": cid,
        "tracking_code": _text(raw.get("tracking_code"), 80),
        "source": source,
        "created_at": created,
        "statut": _crm_status(raw),
        "nom": _text(raw.get("nom"), 200),
        "prenom": _text(raw.get("prenom"), 200),
        "email": _text(raw.get("email"), 200),
        "telephone": _text(raw.get("telephone") or raw.get("tel"), 50),
        "sujet": _text(raw.get("sujet") or raw.get("objet"), 500),
        "message": _text(raw.get("message") or raw.get("demande") or raw.get("raison") or raw.get("description"), 2000),
        "decision": _text(raw.get("decision"), 40),
        "decision_note": _text(raw.get("decision_note"), 500),
        "appointment": {
            "date": _text(appointment.get("date"), 120),
            "type": _text(appointment.get("type"), 40),
            "place": _text(appointment.get("place"), 300),
            "note": _text(appointment.get("note"), 1000),
        } if appointment else {},
        "photo_url": _text(raw.get("photo_url") or raw.get("photo-url"), 500),
        "geo_label": _text(raw.get("geo_label"), 500),
        "geo_lat": _text(raw.get("geo_lat"), 80),
        "geo_lng": _text(raw.get("geo_lng"), 80),
        "geo_maps_url": _text(raw.get("geo_maps_url"), 1000),
    }


def _merge_case(existing: dict, snapshot: dict) -> bool:
    dossiers = existing.get("dossiers")
    if not isinstance(dossiers, list):
        dossiers = []
        existing["dossiers"] = dossiers
    target = next(
        (d for d in dossiers if isinstance(d, dict) and str(d.get("id") or "") == snapshot["id"]),
        None,
    )
    if target is None:
        dossiers.append(snapshot)
        if len(dossiers) > 250:
            del dossiers[:-250]
        return True
    if target != snapshot:
        target.clear()
        target.update(snapshot)
        return True
    return False


def _merge_existing(existing: dict, raw: dict, source: str, case: dict, now: str) -> bool:
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
    if not existing.get("origin_source"):
        existing["origin_source"] = source
        changed = True
    if str(existing.get("source") or "") not in {"audience", "contact", "reclamation", "signalement", "manuel"}:
        existing["source"] = _crm_source(source)
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

    if _merge_case(existing, case):
        changed = True
    if changed:
        existing["updated_at"] = now
    return changed


def sync_contacts_to_crm(server: Any) -> dict:
    """Insert or merge every citizen submission into a person + case CRM model."""
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

        by_id = {
            str(c.get("id") or "").strip(): c
            for c in contacts
            if isinstance(c, dict) and str(c.get("id") or "").strip()
        }
        by_email: dict[str, dict] = {}
        by_phone: dict[str, list[dict]] = {}
        for c in contacts:
            if not isinstance(c, dict):
                continue
            email = _email(c)
            phone = _phone(c)
            if email:
                by_email.setdefault(email, c)
            if phone:
                by_phone.setdefault(phone, []).append(c)

        added = 0
        merged = 0
        for raw in rows if isinstance(rows, list) else []:
            if not isinstance(raw, dict):
                continue
            cid = _stable_id(raw)
            source = _source(raw)
            created = _text(raw.get("ts") or raw.get("_date") or raw.get("created_at") or now, 80)
            case = _case_snapshot(raw, source, cid, created)
            existing = by_id.get(cid)
            email = _email(raw)
            phone = _phone(raw)
            if existing is None and email:
                existing = by_email.get(email)
            if existing is None and phone:
                existing = _phone_candidate(by_phone.get(phone, []), raw)

            if existing is not None:
                if _merge_existing(existing, raw, source, case, now):
                    merged += 1
                by_id[cid] = existing
                current_email = _email(existing)
                current_phone = _phone(existing)
                if current_email:
                    by_email.setdefault(current_email, existing)
                if current_phone:
                    bucket = by_phone.setdefault(current_phone, [])
                    if existing not in bucket:
                        bucket.append(existing)
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
                "source": _crm_source(source),
                "origin_source": source,
                "tags": tags,
                "statut": _crm_status(raw),
                "newsletter": source == "newsletter",
                "notes": [],
                "dossiers": [case],
            }
            contacts.append(contact)
            by_id[cid] = contact
            if email:
                by_email[email] = contact
            if phone:
                by_phone.setdefault(phone, []).append(contact)
            added += 1

        if added or merged:
            server.save_crm(crm)
        return {
            "added": added,
            "merged": merged,
            "total": len(contacts),
            "crm": crm,
            "source_total": len(rows) if isinstance(rows, list) else 0,
        }


def _matches_query(contact: dict, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        str(contact.get(key) or "")
        for key in ("nom", "prenom", "email", "telephone", "sujet", "message", "source", "origin_source", "statut")
    ).lower()
    tags = contact.get("tags") or []
    if isinstance(tags, list):
        haystack += " " + " ".join(str(tag) for tag in tags).lower()
    dossiers = contact.get("dossiers") or []
    if isinstance(dossiers, list):
        for dossier in dossiers:
            if not isinstance(dossier, dict):
                continue
            haystack += " " + " ".join(
                str(dossier.get(key) or "")
                for key in (
                    "id", "tracking_code", "source", "sujet", "message", "statut",
                    "geo_label", "email", "telephone", "nom", "prenom", "decision",
                )
            ).lower()
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
        if source:
            contact_sources = {str(contact.get("source") or ""), str(contact.get("origin_source") or "")}
            dossiers = contact.get("dossiers") or []
            if isinstance(dossiers, list):
                contact_sources.update(
                    str(dossier.get("source") or "")
                    for dossier in dossiers if isinstance(dossier, dict)
                )
            if source not in contact_sources:
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


def _audit_sync(server: Any, handler: Any, result: dict, action: str = "CRM_AUTO_SYNC") -> None:
    if not (result.get("added") or result.get("merged")):
        return
    try:
        ip = handler.client_address[0]
    except Exception:
        ip = "unknown"
    try:
        server.audit_log(
            action,
            ip,
            f"CRM synchronisé automatiquement : +{result['added']} ajout(s), {result['merged']} fusion(s)",
        )
    except Exception:
        pass


def guard_request(server: Any, handler: Any) -> bool:
    """Reconcile and answer GET /api/crm from the same in-memory snapshot."""
    path = str(getattr(handler, "path", "")).split("?", 1)[0]
    method = str(getattr(handler, "command", "GET")).upper()
    if method != "GET" or path != "/api/crm":
        return True
    try:
        result = sync_contacts_to_crm(server)
        _audit_sync(server, handler, result)
        handler._json(_response_payload(handler, result))
        return False
    except Exception as exc:
        print(f"[CRM] Auto-sync fallback: {type(exc).__name__}: {exc}", flush=True)
        return True


def postprocess_response(server: Any, handler: Any) -> None:
    """Make a successful public submission visible in CRM before the request ends."""
    path = str(getattr(handler, "path", "")).split("?", 1)[0]
    method = str(getattr(handler, "command", "GET")).upper()
    status = int(getattr(handler, "_status_code", 200) or 200)
    if method != "POST" or path != "/api/contact" or status < 200 or status >= 300:
        return
    try:
        result = sync_contacts_to_crm(server)
        _audit_sync(server, handler, result, action="CRM_SUBMISSION_SYNC")
    except Exception as exc:
        # The citizen request is already persisted. CRM enrichment must not turn
        # a successful public submission into an HTTP failure, but the issue is
        # deliberately visible in runtime logs and self-heals on the next CRM GET.
        print(f"[CRM] Submission sync deferred: {type(exc).__name__}: {exc}", flush=True)
