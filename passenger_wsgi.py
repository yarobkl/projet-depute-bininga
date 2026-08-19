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

# Vercel serverless functions expose the deployed code as read-only.
# Keep the app's transient JSON/session files in /tmp so importing server.py
# cannot crash while preserving the normal o2switch/Railway behaviour.
if os.environ.get("VERCEL"):
    os.environ.setdefault("DATA_DIR", "/tmp/bininga")
    os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

import server as bininga_server


def _bootstrap() -> None:
    """Initialise only the lightweight state needed to answer web requests.

    Passenger imports this module inside its app worker. Long-running helper
    processes and background schedulers are intentionally opt-in here: cPanel
    can otherwise keep the worker busy during boot and leave requests hanging.
    """
    for name in ("init_users", "load_blocked_ips", "load_attack_scores"):
        fn = getattr(bininga_server, name, None)
        if callable(fn):
            fn()

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
        self.client_address = (environ.get("REMOTE_ADDR", "127.0.0.1"), 0)
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
    """Return the authenticated main-admin session, otherwise ``None``."""
    token = handler.headers.get("X-Admin-Token", "")
    session = bininga_server.get_session(token) if token else None
    if not session:
        return None
    if session.get("username") != bininga_server.ADMIN_USER:
        return None
    return session


def _harden_admin_authorization(handler: _PassengerHandler) -> bool:
    """Apply server-side authorization rules that the legacy handler under-enforces.

    Returns ``True`` when the request may continue into ``server.py`` and ``False``
    when a response has already been emitted.

    Two dangerous gaps are closed here without rewriting the large legacy server:
      * user creation/deletion is reserved to the main administrator;
      * Hero/About/Parcours data really is main-admin-only, even if a secondary
        admin bypasses the UI and calls ``/api/save`` directly.
    """
    if handler.command != "POST":
        return True

    path = handler.path.split("?", 1)[0]
    token = handler.headers.get("X-Admin-Token", "")
    session = bininga_server.get_session(token) if token else None

    # Let the legacy handler deal with unauthenticated requests so its normal
    # 401/rate-limit/audit behaviour remains unchanged.
    if not session:
        return True

    # The Users panel is visible only to the main admin. Enforce the same rule
    # on the API so a minister/secondary admin cannot create an administrator.
    if path in ("/api/users/upsert", "/api/users/delete"):
        if not _main_admin_session(handler):
            bininga_server.audit_log(
                "AUTHZ_REJECT",
                handler.client_address[0],
                f"Accès refusé à {path} pour {session.get('username', '?')}",
            )
            handler._json({"ok": False, "message": "Réservé à l'administrateur principal"}, 403)
            return False
        return True

    # server.py already labels these keys as main-admin-only, but its legacy
    # role check only distinguishes "admin" from other roles. Sanitize the
    # body before handing it over, preserving the authoritative stored values.
    if path == "/api/save" and session.get("username") != bininga_server.ADMIN_USER:
        raw = handler.rfile.getvalue()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            # Preserve the legacy validation/error response for malformed JSON.
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


def _inject_admin_hardening(handler: _PassengerHandler) -> None:
    """Load the admin integrity patch only on the real administration page.

    This deliberately avoids editing the large legacy admin HTML/JS files in-place.
    The response is changed only when it is clearly the BININGA admin document,
    making this first stabilization step easy to disable or roll back.
    """
    if handler.command != "GET" or handler._status_code != 200:
        return

    body = handler.wfile.getvalue()
    if b"static/admin.js" not in body or b"Espace Administration" not in body:
        return
    if b"static/admin-hardening.js" in body:
        return

    marker = b"</body>"
    if marker not in body:
        return

    script = b'\n<script src="/static/admin-hardening.js?v=20260819-integrity-1" defer></script>\n'
    patched = body.replace(marker, script + marker, 1)
    handler.wfile = io.BytesIO(patched)
    handler._response_headers = [
        (key, value) for key, value in handler._response_headers
        if key.lower() != "content-length"
    ]
    handler._response_headers.append(("Content-Length", str(len(patched))))


_bootstrap()


def application(environ, start_response):
    handler = _PassengerHandler(environ)
    try:
        if not _harden_admin_authorization(handler):
            pass
        elif handler.command == "GET":
            handler.do_GET()
        elif handler.command == "POST":
            handler.do_POST()
        elif handler.command == "OPTIONS":
            handler.do_OPTIONS()
        else:
            handler.send_error(405, "Method Not Allowed")
    except Exception as exc:
        body = f"Internal Server Error: {exc}".encode("utf-8")
        start_response(
            "500 Internal Server Error",
            [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    _inject_admin_hardening(handler)

    status = handler._status_code
    reason = http.HTTPStatus(status).phrase if status in http.HTTPStatus._value2member_map_ else "OK"
    start_response(f"{status} {reason}", handler._response_headers)
    return [handler.wfile.getvalue()]
