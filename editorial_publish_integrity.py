"""Make BININGA editorial publication a real public-site mutation.

The legacy ``/api/editorial/save`` route marks an editorial draft as ``publie``
but does not publish it into the public ``actus`` data consumed by index.html.
This request guard intercepts only a valid transition to ``publie`` and performs
both durable mutations as one guarded operation:

* upsert a public featured-news record identified by ``editorial_id``;
* mark the editorial record as published with timestamps;
* persist both through the existing PostgreSQL-first persistence helpers;
* audit the publication and return the public record to the admin UI.

All other editorial edits continue through the legacy handler unchanged.
"""
from __future__ import annotations

import copy
import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

_LOCK = threading.RLock()
_ALLOWED_ROLES = {"admin", "ministre"}


def _csrf_valid(server, handler, session: Dict[str, Any]) -> bool:
    received = str(handler.headers.get("X-CSRF-Token", ""))
    expected = str(session.get("csrf_token", ""))
    if not received or not expected:
        return False
    try:
        return server.secrets.compare_digest(received, expected)
    except Exception:
        return received == expected


def _load_editorial(server) -> List[Dict[str, Any]]:
    data = server._pg_load("editorial")
    if isinstance(data, list):
        return data
    path = getattr(server, "EDITORIAL_FILE", "")
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _save_editorial(server, rows: List[Dict[str, Any]]) -> None:
    server._pg_save("editorial", rows)
    path = getattr(server, "EDITORIAL_FILE", "")
    if path:
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(rows, handle, ensure_ascii=False, indent=2)
        except Exception:
            # PostgreSQL remains the durable source of truth in production.
            pass


def _publication_validation(article: Dict[str, Any]) -> str:
    """Retourne un motif de blocage, ou une chaîne vide si publiable."""
    if str(article.get("statut") or "") not in {"valide", "publie"}:
        return "L'article doit être validé avant publication"
    if not str(article.get("titre") or "").strip():
        return "Le titre est requis avant publication"
    if not str(article.get("resume") or "").strip():
        return "Le résumé est requis avant publication"
    if not str(article.get("article") or article.get("contenu") or "").strip():
        return "Le contenu de l'article est requis avant publication"

    sources = article.get("sources")
    source_values = [str(value).strip() for value in sources] if isinstance(sources, list) else []
    source_values.extend([
        str(article.get("source_url") or "").strip(),
        str(article.get("source_nom") or "").strip(),
    ])
    if not any(source_values):
        return "Une source doit être renseignée avant publication"

    source_url = str(article.get("source_url") or "").strip()
    if source_url and not source_url.startswith(("https://", "http://")):
        return "L'adresse de la source doit commencer par https:// ou http://"
    return ""


_MONTHS_FR = ["JAN", "FÉV", "MAR", "AVR", "MAI", "JUN",
              "JUL", "AOÛ", "SEP", "OCT", "NOV", "DÉC"]


def _public_record(article: Dict[str, Any], published_at: str) -> Dict[str, Any]:
    """Carte d'actualité pour la grille du bas de la section Actualités.

    Choix éditorial du propriétaire : les articles IA apparaissent comme des
    cartes ordinaires parmi les autres (grille), pas en grande vedette.
    """
    title = str(article.get("titre") or "Article").strip()[:160]
    summary = str(article.get("resume") or "").strip()
    body = str(article.get("article") or summary).strip()
    desc = (summary or body)[:230]
    sources = article.get("sources") if isinstance(article.get("sources"), list) else []
    source_url = str(article.get("source_url") or "").strip()
    if not source_url:
        for source in sources:
            match = re.search(r"https?://[^\s]+", str(source))
            if match:
                source_url = match.group(0).rstrip(".,;)")
                break
    source_label = str(article.get("source_nom") or "").strip()
    if not source_label and sources:
        source_label = re.split(r"\s+[—-]\s+https?://", str(sources[0]), maxsplit=1)[0].strip()
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    return {
        "editorial_id": str(article.get("id", "")),
        "image": str(article.get("image") or "").strip(),
        "cat": "Actualité",
        "icon": "AB",
        "day": f"{dt.day:02d}",
        "month": _MONTHS_FR[dt.month - 1],
        "year": str(dt.year),
        "title": title,
        "desc": desc,
        "body": body,
        "tags": [str(tag).strip() for tag in article.get("tags", []) if str(tag).strip()][:8]
                if isinstance(article.get("tags"), list) else [],
        "sourceUrl": source_url,
        "sourceLabel": source_label,
        "published_at": published_at,
        "publication_source": "editorial_ia",
    }


def _upsert_public_article(site_data: Dict[str, Any], public: Dict[str, Any]) -> None:
    actus = site_data.setdefault("actus", {})
    if not isinstance(actus, dict):
        actus = {}
        site_data["actus"] = actus
    cards = actus.setdefault("cards", [])
    if not isinstance(cards, list):
        cards = []
        actus["cards"] = cards

    editorial_id = public["editorial_id"]

    # Une publication ne doit plus jamais vivre en vedette : retirer toute
    # ancienne entrée du même article dans la liste des grandes actualités.
    vedettes = actus.get("vedettes")
    if isinstance(vedettes, list):
        actus["vedettes"] = [row for row in vedettes
                             if not (isinstance(row, dict)
                                     and str(row.get("editorial_id", "")) == editorial_id)]

    existing = next((i for i, row in enumerate(cards)
                     if isinstance(row, dict) and str(row.get("editorial_id", "")) == editorial_id), None)
    if existing is None:
        cards.append(public)  # en bas de la grille, comme les autres
    else:
        preserved_image = cards[existing].get("image", "") if isinstance(cards[existing], dict) else ""
        if preserved_image and not public.get("image"):
            public["image"] = preserved_image
        cards[existing] = public


def _vedette_to_card(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convertit une ancienne vedette éditoriale au format carte."""
    published = str(row.get("published_at") or "")
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    desc = str(row.get("text2") or row.get("text1") or "").strip()[:230]
    return {
        "editorial_id": str(row.get("editorial_id", "")),
        "image": str(row.get("image") or "").strip(),
        "cat": "Actualité",
        "icon": "AB",
        "day": f"{dt.day:02d}",
        "month": _MONTHS_FR[dt.month - 1],
        "year": str(dt.year),
        "title": str(row.get("title") or "Article").strip()[:160],
        "desc": desc,
        "published_at": published,
        "publication_source": "editorial_ia",
    }


def migrate_editorial_vedettes(server) -> None:
    """Migration unique : déplace les publications éditoriales déjà en
    vedette vers la grille de cartes (choix du propriétaire), avec marqueur
    en base pour ne jamais rejouer la migration."""
    marker_key = "editorial_cards_migration_v1"
    try:
        marker = server._pg_load(marker_key)
        if isinstance(marker, dict) and marker.get("done") is True:
            return
        site = server.load_data()
        actus = site.get("actus") if isinstance(site, dict) else None
        vedettes = actus.get("vedettes") if isinstance(actus, dict) else None
        if not isinstance(vedettes, list):
            server._pg_save(marker_key, {"done": True})
            return
        moved = [row for row in vedettes
                 if isinstance(row, dict) and str(row.get("editorial_id", "")).strip()]
        if moved:
            site = copy.deepcopy(site)
            site["actus"]["vedettes"] = [row for row in site["actus"]["vedettes"]
                                         if not (isinstance(row, dict)
                                                 and str(row.get("editorial_id", "")).strip())]
            cards = site["actus"].setdefault("cards", [])
            known = {str(c.get("editorial_id", "")) for c in cards if isinstance(c, dict)}
            for row in moved:
                if str(row.get("editorial_id", "")) not in known:
                    cards.append(_vedette_to_card(row))
            server.save_data(site)
            server.audit_log("EDITORIAL_MIGRATE", "system",
                             f"{len(moved)} publication(s) déplacée(s) des vedettes vers la grille")
        server._pg_save(marker_key, {"done": True})
    except Exception as exc:
        print(f"[EDITORIAL] Migration vedettes→cartes différée : {exc}", flush=True)


def guard_request(server, handler) -> bool:
    """Handle only a valid editorial publish mutation.

    Return ``False`` after emitting a response; return ``True`` to let the legacy
    route process every non-publication request or its own authentication errors.
    """
    if handler.command != "POST" or handler.path.split("?", 1)[0] != "/api/editorial/save":
        return True

    try:
        payload = json.loads(handler.rfile.getvalue().decode("utf-8"))
    except Exception:
        return True
    if not isinstance(payload, dict) or payload.get("statut") != "publie":
        return True

    token = handler.headers.get("X-Admin-Token", "")
    session = server.get_session(token) if token else None
    if not session or not _csrf_valid(server, handler, session):
        # Preserve the legacy route's authoritative auth/CSRF error semantics.
        return True
    if session.get("role") not in _ALLOWED_ROLES:
        server.audit_log(
            "EDITORIAL_PUBLISH_REJECT",
            handler.client_address[0],
            f"Rôle non autorisé : {session.get('role', '?')}",
        )
        handler._json({"ok": False, "message": "Publication réservée à l'administrateur ou au député"}, 403)
        return False

    article_id = str(payload.get("id", "")).strip()
    if not article_id:
        handler._json({"ok": False, "message": "ID article requis"}, 400)
        return False

    with _LOCK:
        articles = copy.deepcopy(_load_editorial(server))
        found = next((row for row in articles if isinstance(row, dict) and str(row.get("id", "")) == article_id), None)
        if not found:
            handler._json({"ok": False, "message": "Article éditorial introuvable"}, 404)
            return False

        # Apply the small editable field set accepted by the legacy route before
        # validating and publishing, then force the authoritative metadata.
        for field in ("titre", "resume", "article", "contenu", "points_cles", "sources", "source_url", "source_nom"):
            if field in payload:
                found[field] = payload[field]

        validation_error = _publication_validation(found)
        if validation_error:
            server.audit_log("EDITORIAL_PUBLISH_REJECT", handler.client_address[0], f"{article_id}: {validation_error}")
            handler._json({"ok": False, "message": validation_error}, 409)
            return False

        old_site = copy.deepcopy(server.load_data())
        old_articles = copy.deepcopy(_load_editorial(server))
        site_data = copy.deepcopy(old_site)
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        public = _public_record(found, now)
        _upsert_public_article(site_data, public)
        found["statut"] = "publie"
        found["published_at"] = now
        found["updated_at"] = now

        try:
            server.save_data(site_data)
            _save_editorial(server, articles)
        except Exception as exc:
            # Best-effort rollback keeps the two public/editorial states aligned.
            try:
                server.save_data(old_site)
            except Exception:
                pass
            try:
                _save_editorial(server, old_articles)
            except Exception:
                pass
            server.audit_log("EDITORIAL_PUBLISH_ERROR", handler.client_address[0], f"{article_id}: {exc}")
            handler._json({"ok": False, "message": "Publication impossible, aucune modification conservée"}, 500)
            return False

        server.audit_log(
            "EDITORIAL_PUBLISH",
            handler.client_address[0],
            f"Article publié sur le site : {str(found.get('titre', ''))[:80]}",
        )
        handler._json({
            "ok": True,
            "article": found,
            "public_article": public,
            "published": True,
        })
        return False
