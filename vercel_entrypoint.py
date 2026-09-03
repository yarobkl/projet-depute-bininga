"""Vercel entrypoint with an explicit hardened DA chat route.

The main Passenger adapter remains authoritative for the rest of the site. This
wrapper makes sure POST /api/chat uses both the hardened security layer and the
human-language understanding layer before any legacy chat handler can run.
"""

from __future__ import annotations

import http
import threading

from vercel_public_fastpath import try_serve


_LEGACY_APP = None
_LEGACY_LOCK = threading.Lock()


def _finish(handler, start_response):
    status = int(handler._status_code)
    reason = http.HTTPStatus(status).phrase if status in http.HTTPStatus._value2member_map_ else "OK"
    start_response(f"{status} {reason}", handler._response_headers)
    return [handler.wfile.getvalue()]


def _load_legacy_application():
    """Initialise l'application complète uniquement pour une route dynamique."""
    global _LEGACY_APP
    if _LEGACY_APP is not None:
        return _LEGACY_APP
    with _LEGACY_LOCK:
        if _LEGACY_APP is not None:
            return _LEGACY_APP

        import chatbot_hardening
        import chatbot_nlu
        import first_person_content_migration
        import passenger_wsgi
        import vercel_session_persistence

        chatbot_nlu.install(chatbot_hardening)
        vercel_session_persistence.install(passenger_wsgi.bininga_server)
        migration = first_person_content_migration.apply(passenger_wsgi.bininga_server)
        if not migration.get("ok"):
            print(f"[EDITORIAL MIGRATION] first-person migration skipped: {migration.get('error')}", flush=True)

        def legacy_application(environ, start_response):
            method = (environ.get("REQUEST_METHOD") or "GET").upper()
            path = environ.get("PATH_INFO") or "/"
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

        _LEGACY_APP = legacy_application
        return _LEGACY_APP


def application(environ, start_response):
    public_response = try_serve(environ, start_response)
    if public_response is not None:
        return public_response
    return _load_legacy_application()(environ, start_response)
