"""Vercel entrypoint with an explicit hardened DA chat route.

The main Passenger adapter remains authoritative for the rest of the site. This
wrapper makes sure POST /api/chat uses both the hardened security layer and the
human-language understanding layer before any legacy chat handler can run.
"""

from __future__ import annotations

import http
import importlib
import os
import threading

from vercel_public_fastpath import try_serve


_LEGACY_APP = None
_LEGACY_LOCK = threading.Lock()


def _finish(handler, start_response):
    status = int(handler._status_code)
    reason = http.HTTPStatus(status).phrase if status in http.HTTPStatus._value2member_map_ else "OK"
    start_response(f"{status} {reason}", handler._response_headers)
    return [handler.wfile.getvalue()]


def _import_passenger_without_eager_image_copy():
    """Importe l'app legacy sans recopier tout images/ à chaque cold start Vercel.

    server.py conserve sa migration historique pour les hébergements persistants.
    Sur Vercel, ré-uploader les mêmes images en PostgreSQL à chaque nouveau worker
    est inutile et peut ajouter plusieurs secondes au premier appel admin. Les
    écritures photo normales (upload/sauvegarde) ne sont pas modifiées.
    """
    if not os.environ.get("VERCEL"):
        return importlib.import_module("passenger_wsgi")

    original_walk = os.walk
    images_root = os.path.realpath(os.path.join(os.getcwd(), "images"))

    def serverless_walk(top, *args, **kwargs):
        try:
            current = os.path.realpath(os.fspath(top))
        except Exception:
            current = ""
        if current == images_root:
            print("[VERCEL BOOT] Migration eager de images/ ignorée sur cold start.", flush=True)
            return iter(())
        return original_walk(top, *args, **kwargs)

    os.walk = serverless_walk
    try:
        return importlib.import_module("passenger_wsgi")
    finally:
        os.walk = original_walk


def _load_legacy_application():
    """Initialise l'application complète uniquement pour une route dynamique."""
    global _LEGACY_APP
    if _LEGACY_APP is not None:
        return _LEGACY_APP
    with _LEGACY_LOCK:
        if _LEGACY_APP is not None:
            return _LEGACY_APP

        import admin_auth_flow
        import chatbot_hardening
        import chatbot_nlu
        import email_delivery_diagnostics
        import first_person_content_migration
        import vercel_session_persistence

        passenger_wsgi = _import_passenger_without_eager_image_copy()

        chatbot_nlu.install(chatbot_hardening)
        email_delivery_diagnostics.install(admin_auth_flow)
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
