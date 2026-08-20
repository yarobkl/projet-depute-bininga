"""Vercel entrypoint with an explicit hardened DA chat route.

The main Passenger adapter remains authoritative for the rest of the site. This
small wrapper makes sure POST /api/chat cannot fall through to the legacy chat
handler in server.py on Vercel.
"""

from __future__ import annotations

import http
import json
import re
import unicodedata

import chatbot_hardening
import passenger_wsgi


def _finish(handler, start_response):
    status = int(handler._status_code)
    reason = http.HTTPStatus(status).phrase if status in http.HTTPStatus._value2member_map_ else "OK"
    start_response(f"{status} {reason}", handler._response_headers)
    return [handler.wfile.getvalue()]


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    value = value.replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s']", " ", value)).strip()


def _capability_reply(handler) -> bool:
    """Answer common 'what can you do?' questions without requiring the DB/AI.

    These are questions about DA itself, not requests for an external fact. They
    must never fall through to the generic 'information not confirmed' reply.
    """
    try:
        raw = handler.rfile.getvalue() if hasattr(handler.rfile, "getvalue") else b""
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        question = _normalize(str(payload.get("message", "")))
    except Exception:
        return False

    phrases = (
        "en quoi tu peux m'aider",
        "en quoi peux tu m'aider",
        "comment tu peux m'aider",
        "comment peux tu m'aider",
        "que peux tu faire",
        "qu'est ce que tu peux faire",
        "qu est ce que tu peux faire",
        "a quoi tu sers",
        "a quoi sers tu",
        "tes fonctions",
        "tes capacites",
        "tu peux m'aider comment",
    )
    if not any(phrase in question for phrase in phrases):
        return False

    reply = (
        "Je peux vous renseigner sur Ange Aimé Wilfrid BININGA : sa biographie, "
        "son parcours, son programme, ses projets et les actualités publiées sur le site. "
        "Je peux aussi vous guider pour une demande d’audience, le suivi d’un dossier, "
        "un contact, une réclamation, la galerie, les publications et les informations "
        "officielles disponibles. Si une information n’est pas vérifiée dans mes sources, "
        "je vous le signalerai plutôt que de l’inventer."
    )
    handler._json({"ok": True, "reply": reply})
    return True


def application(environ, start_response):
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    path = environ.get("PATH_INFO") or "/"

    # Force the public DA endpoint through the hardened implementation before
    # any legacy server.py routing can run.
    if method == "POST" and path.rstrip("/") == "/api/chat":
        handler = passenger_wsgi._PassengerHandler(environ)
        try:
            if _capability_reply(handler):
                return _finish(handler, start_response)
            handled = chatbot_hardening.guard_request(passenger_wsgi.bininga_server, handler)
            if handled is False:
                return _finish(handler, start_response)
        except Exception as exc:
            body = b'{"ok":false,"message":"Service de discussion indisponible"}'
            start_response(
                "500 Internal Server Error",
                [
                    ("Content-Type", "application/json; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            print(f"[CHAT ENTRYPOINT] hardened route error: {type(exc).__name__}", flush=True)
            return [body]

    return passenger_wsgi.application(environ, start_response)
