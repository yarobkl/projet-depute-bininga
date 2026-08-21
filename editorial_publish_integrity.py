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
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

_LOCK = threading.RLock()
_ALLOWED_ROLES = {"admin", "ministre", "editeur"}


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


def _public_record(article: Dict[str, Any], published_at: str) -> Dict[str, Any]:
    title = str(article.get("titre") or "Article").strip()[:180]
    summary = str(article.get("resume") or "").strip()
    body = str(article.get("article") or summary).strip()
    source_name = str(article.get("source_nom") or "").strip()
    source_date = str(article.get("source_date") or "").strip()
    points = article.get("points_cles") if isinstance(article.get("points_cles"), list) else []
    sources = article.get("sources") if isinstance(article.get("sources"), list) else []

    tags = [str(x).strip() for x in points[:4] if str(x).strip()]
    if source_name and source_name not in tags:
        tags.append(source_name)

    return {
        "editorial_id": str(article.get("id", "")),
        "badge": "Actualité",
        "tag": source_name or "BININGA",
        "date": source_date or published_at[:10],
        "title": title,
        "text1": body or summary,
        "quote": "",
        "text2": summary if summary and summary != body else "",
        "tags": tags,
        "sources": [str(x) for x in sources[:8]],
        "published_at": published_at,
        "publication_source": "editorial_ia",
    }


def _upsert_public_article(site_data: Dict[str, Any], public: Dict[str, Any]) -> None:
    actus = site_data.setdefault("actus", {})
    if not isinstance(actus, dict):
        actus = {}
        site_data["actus"] = actus
    vedettes = actus.setdefault("vedettes", [])
    if not isinstance(vedettes, list):
        vedettes = []
        actus["vedettes"] = vedettes

    editorial_id = public["editorial_id"]
    existing = next((i for i, row in enumerate(vedettes)
                     if isinstance(row, dict) and str(row.get("editorial_id", "")) == editorial_id), None)
    if existing is None:
        vedettes.insert(0, public)
    else:
        preserved_image = vedettes[existing].get("image", "") if isinstance(vedettes[existing], dict) else ""
        if preserved_image and not public.get("image"):
            public["image"] = preserved_image
        vedettes[existing] = public


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
    if not session or session.get("role") not in _ALLOWED_ROLES or not _csrf_valid(server, handler, session):
        # Preserve the legacy route's authoritative auth/CSRF error semantics.
        return True

    article_id = str(payload.get("id", "")).strip()
    if not article_id:
        handler._json({"ok": False, "message": "ID article requis"}, 400)
        return False

    with _LOCK:
        articles = _load_editorial(server)
        found = next((row for row in articles if isinstance(row, dict) and str(row.get("id", "")) == article_id), None)
        if not found:
            handler._json({"ok": False, "message": "Article éditorial introuvable"}, 404)
            return False

        old_site = copy.deepcopy(server.load_data())
        old_articles = copy.deepcopy(articles)
        site_data = copy.deepcopy(old_site)
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        public = _public_record(found, now)
        _upsert_public_article(site_data, public)

        # Apply the small editable field set accepted by the legacy route before
        # publishing, then force the authoritative publication metadata.
        for field in ("titre", "resume", "article", "points_cles", "sources"):
            if field in payload:
                found[field] = payload[field]
        # Rebuild once more in case the same request carried edits.
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
