"""Passenger entrypoint for the o2switch deployment.

The project uses a custom ``http.server`` handler in ``server.py``.  cPanel
Passenger expects a WSGI callable, so this adapter feeds WSGI requests into the
existing handler without starting a second HTTP server.
"""

import http
import io
import json
import os
import sys
from email.message import Message

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

if os.environ.get("VERCEL"):
    os.environ.setdefault("DATA_DIR", "/tmp/bininga")
    os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

import preimport_security  # noqa: F401

import server as bininga_server
import admin_contact_integrity
import admin_bootstrap_hardening
import admin_owners
import admin_request_pipeline
import request_identity
import editorial_publish_integrity
import persistent_audit
import persistent_security_state

persistent_audit.install(bininga_server)
persistent_security_state.install(bininga_server)
admin_contact_integrity.install(bininga_server)
admin_bootstrap_hardening.install(bininga_server)
editorial_publish_integrity.migrate_editorial_vedettes(bininga_server)


def _bootstrap() -> None:
    for name in ("init_users", "load_blocked_ips", "load_attack_scores"):
        fn = getattr(bininga_server, name, None)
        if callable(fn):
            fn()

    try:
        bininga_server.hydrate_ia_keys()
    except Exception:
        pass

    if os.environ.get("BININGA_PASSENGER_BOOT_SERVICES") != "1":
        return

    try:
        for name in ("start_monitor", "_monitor_watchdog"):
            fn = getattr(bininga_server, name, None)
            if callable(fn):
                fn()

        mon = getattr(bininga_server, "_MON", None)
        if mon and hasattr(mon, "init_db") and hasattr(mon, "start_scheduler"):
            mon.init_db()
            mon.start_scheduler(
                get_sessions_fn=lambda: len(getattr(bininga_server, "ACTIVE_SESSIONS", [])),
                get_blocked_fn=lambda: len(getattr(bininga_server, "BLOCKED_IPS", [])),
            )
    except Exception as exc:
        print(f"[PASSENGER] Services arrière-plan ignorés: {exc}", flush=True)


class _PassengerHandler(bininga_server.BiningaHandler):
    """Small response-capturing subclass used by the WSGI adapter."""

    def __init__(self, environ):
        self.environ = environ
        self.command = environ.get("REQUEST_METHOD", "GET").upper()
        self.path = environ.get("PATH_INFO", "") or "/"
        query = environ.get("QUERY_STRING", "")
        if query:
            self.path = f"{self.path}?{query}"
        self.request_version = environ.get("SERVER_PROTOCOL", "HTTP/1.1")
        self.protocol_version = "HTTP/1.1"
        self.client_address = (request_identity.client_ip(environ), 0)
        self.server = None
        self.close_connection = True
        self.headers = self._headers_from_environ(environ)
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(length) if length else b""
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self._status_code = 200
        self._response_headers = []

    @staticmethod
    def _headers_from_environ(environ) -> Message:
        headers = Message()
        if environ.get("CONTENT_TYPE"):
            headers["Content-Type"] = environ["CONTENT_TYPE"]
        if environ.get("CONTENT_LENGTH"):
            headers["Content-Length"] = environ["CONTENT_LENGTH"]
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header = key[5:].replace("_", "-").title()
                headers[header] = value
        return headers

    def send_response(self, code, message=None):
        self._status_code = int(code)

    def send_response_only(self, code, message=None):
        self._status_code = int(code)

    def send_header(self, keyword, value):
        self._response_headers.append((str(keyword), str(value)))

    def end_headers(self):
        return None

    def log_message(self, fmt, *args):
        return None


def _main_admin_session(handler: _PassengerHandler):
    """Compatibility name: returns a session only when it has owner rights."""
    token = handler.headers.get("X-Admin-Token", "")
    session = bininga_server.get_session(token) if token else None
    if not session:
        return None
    if not admin_owners.is_owner_session(bininga_server, session):
        return None
    return session


def _harden_admin_authorization(handler: _PassengerHandler) -> bool:
    if handler.command != "POST":
        return True

    path = handler.path.split("?", 1)[0]
    token = handler.headers.get("X-Admin-Token", "")
    session = bininga_server.get_session(token) if token else None

    if not session:
        return True

    if path in ("/api/users/upsert", "/api/users/delete"):
        if not _main_admin_session(handler):
            bininga_server.audit_log(
                "AUTHZ_REJECT",
                handler.client_address[0],
                f"Accès refusé à {path} pour {session.get('username', '?')}",
            )
            handler._json({"ok": False, "message": "Réservé aux propriétaires de l’administration"}, 403)
            return False
        return True

    if path == "/api/save" and not admin_owners.is_owner_session(bininga_server, session):
        raw = handler.rfile.getvalue()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return True

        if isinstance(payload, dict):
            existing = bininga_server.load_data()
            admin_only_keys = ("hero", "about", "parcours", "parcoursSection")
            for key in admin_only_keys:
                if key in existing:
                    payload[key] = existing[key]
                else:
                    payload.pop(key, None)

            patched = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            handler.rfile = io.BytesIO(patched)
            if handler.headers.get("Content-Length") is not None:
                handler.headers.replace_header("Content-Length", str(len(patched)))
            else:
                handler.headers["Content-Length"] = str(len(patched))

    return True


def _replace_response_body(handler: _PassengerHandler, patched: bytes) -> None:
    handler.wfile = io.BytesIO(patched)
    handler._response_headers = [
        (key, value) for key, value in handler._response_headers
        if key.lower() != "content-length"
    ]
    handler._response_headers.append(("Content-Length", str(len(patched))))


def _inject_admin_hardening(handler: _PassengerHandler) -> None:
    if handler.command != "GET" or handler._status_code != 200:
        return

    body = handler.wfile.getvalue()
    if b"static/admin.js" not in body or b"Espace Administration" not in body:
        return

    patched = body
    preboot_marker = b"data-bininga-admin-preboot"
    if preboot_marker not in patched and b"<head>" in patched:
        preboot = b'''\n<script data-bininga-admin-preboot>\n(function(){\n  try {\n    var raw=sessionStorage.getItem('bininga_session');\n    var s=raw?JSON.parse(raw):null;\n    if(!s||!s.token||Date.now()>Number(s.expires_at||0)){\n      try{sessionStorage.removeItem('bininga_session');}catch(_){}\n      try{localStorage.removeItem('bininga_session');}catch(_){}\n      location.replace('/static/admin-login-shell.html');\n      return;\n    }\n    if(s.must_change_password){location.replace('/static/admin-first-login.html');}\n  } catch(e) {\n    location.replace('/static/admin-login-shell.html');\n  }\n})();\n</script>\n'''
        patched = patched.replace(b"<head>", b"<head>" + preboot, 1)

    marker = b"</body>"
    if marker not in patched:
        if patched != body:
            _replace_response_body(handler, patched)
        return

    scripts = b""
    if b"static/admin-hardening.js" not in patched:
        scripts += b'\n<script src="/static/admin-hardening.js?v=20260819-integrity-1" defer></script>\n'
    if b"static/admin-notification-hardening.js" not in patched:
        scripts += b'\n<script src="/static/admin-notification-hardening.js?v=20260819-token-1" defer></script>\n'
    # Le dashboard métier doit être disponible avant DOMContentLoaded : l'ancien
    # chargeur session le récupérait comme 5e module, ce qui retardait son rendu.
    if b"static/admin-dashboard-hardening.js" not in patched:
        scripts += b'\n<script data-bininga-dashboard-hardening data-loaded="1" src="/static/admin-dashboard-hardening.js?v=20260903-dashboard-priority-1" defer></script>\n'
    if b"static/admin-dashboard-priority.js" not in patched:
        scripts += b'\n<script src="/static/admin-dashboard-priority.js?v=20260903-dashboard-priority-1" defer></script>\n'
    if b"static/admin-session-hardening.js" not in patched:
        scripts += b'\n<script src="/static/admin-session-hardening.js?v=20260903-system-layout-1" defer></script>\n'
    if b"static/admin-chatbot.js" not in patched:
        scripts += b'\n<script src="/static/admin-chatbot.js?v=20260823-da-keys-2" defer></script>\n'
    if scripts:
        patched = patched.replace(marker, scripts + marker, 1)

    if patched != body:
        _replace_response_body(handler, patched)


def _inject_public_form_hardening(handler: _PassengerHandler) -> None:
    if handler.command != "GET" or handler._status_code != 200:
        return

    body = handler.wfile.getvalue()
    if b"static/index.js" not in body or b"Espace Administration" in body:
        return
    if b"static/public-form-hardening.js" in body:
        return

    marker = b"</body>"
    if marker not in body:
        return

    script = b'\n<script src="/static/public-form-hardening.js?v=20260819-privacy-1" defer></script>\n'
    _replace_response_body(handler, body.replace(marker, script + marker, 1))


def _dispatch_request(handler: _PassengerHandler) -> None:
    if handler.command == "GET":
        handler.do_GET()
    elif handler.command == "POST":
        handler.do_POST()
    elif handler.command == "OPTIONS":
        handler.do_OPTIONS()
    else:
        handler.send_error(405, "Method Not Allowed")


_bootstrap()


def application(environ, start_response):
    handler = _PassengerHandler(environ)
    try:
        if admin_request_pipeline.allow_request(
            bininga_server,
            handler,
            legacy_authorization=_harden_admin_authorization,
        ):
            with admin_request_pipeline.mutation_context(bininga_server, handler):
                _dispatch_request(handler)
            admin_request_pipeline.process_response(bininga_server, handler)
    except Exception as exc:
        body = f"Internal Server Error: {exc}".encode("utf-8")
        start_response(
            "500 Internal Server Error",
            [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    _inject_admin_hardening(handler)
    _inject_public_form_hardening(handler)

    status = handler._status_code
    reason = http.HTTPStatus(status).phrase if status in http.HTTPStatus._value2member_map_ else "OK"
    start_response(f"{status} {reason}", handler._response_headers)
    return [handler.wfile.getvalue()]
