"""Legacy Railway endpoint: permanent redirect to the canonical Vercel site."""
from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, HTTPServer

TARGET = os.environ.get("LEGACY_REDIRECT_TARGET", "https://projet-depute-bininga.vercel.app").rstrip("/")
PORT = int(os.environ.get("PORT", "8080"))


class RedirectHandler(BaseHTTPRequestHandler):
    def _health(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "2")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b"OK")

    def _redirect(self) -> None:
        location = TARGET + self.path
        self.send_response(308)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/health":
            self._health()
            return
        self._redirect()

    def do_HEAD(self) -> None:
        if self.path.split("?", 1)[0] == "/health":
            self._health()
            return
        self._redirect()

    def do_POST(self) -> None:
        self._redirect()

    def log_message(self, fmt: str, *args) -> None:
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), RedirectHandler).serve_forever()
