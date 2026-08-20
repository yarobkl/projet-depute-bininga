"""Vercel entrypoint with an explicit hardened DA chat route.

The main Passenger adapter remains authoritative for the rest of the site. This
wrapper makes sure POST /api/chat uses both the hardened security layer and the
human-language understanding layer before any legacy chat handler can run.
"""

from __future__ import annotations

import http

import chatbot_hardening
import chatbot_nlu
import passenger_wsgi

# Add conversational French/paraphrase understanding without weakening the
# hardened factual, privacy, rate-limit or prompt-injection protections.
chatbot_nlu.install(chatbot_hardening)


def _finish(handler, start_response):
    status = int(handler._status_code)
    reason = http.HTTPStatus(status).phrase if status in http.HTTPStatus._value2member_map_ else "OK"
    start_response(f"{status} {reason}", handler._response_headers)
    return [handler.wfile.getvalue()]


def application(environ, start_response):
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    path = environ.get("PATH_INFO") or "/"

    # Force the public DA endpoint through the hardened implementation before
    # any legacy server.py routing can run.
    if method == "POST" and path.rstrip("/") == "/api/chat":
        handler = passenger_wsgi._PassengerHandler(environ)
        try:
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
