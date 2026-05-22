"""Passenger entrypoint for the o2switch deployment.

The project uses a custom ``http.server`` handler in ``server.py``.  cPanel
Passenger expects a WSGI callable, so this adapter feeds WSGI requests into the
existing handler without starting a second HTTP server.
"""

from __future__ import annotations

import http
import io
from email.message import Message

import server as bininga_server


def _bootstrap() -> None:
    """Initialise the same runtime services as the direct server entrypoint."""
    for name in ("init_users", "load_blocked_ips", "load_attack_scores"):
        fn = getattr(bininga_server, name, None)
        if callable(fn):
            fn()

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


_bootstrap()


def application(environ, start_response):
    handler = _PassengerHandler(environ)
    try:
        if handler.command == "GET":
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

    status = handler._status_code
    reason = http.HTTPStatus(status).phrase if status in http.HTTPStatus._value2member_map_ else "OK"
    start_response(f"{status} {reason}", handler._response_headers)
    return [handler.wfile.getvalue()]
