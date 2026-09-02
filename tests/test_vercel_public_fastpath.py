#!/usr/bin/env python3
"""Contrats du chemin public léger Vercel."""

from __future__ import annotations

import gzip
import io
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import vercel_entrypoint  # noqa: E402


def request(path: str, query: str = "", **headers):
    captured = {}
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.input": io.BytesIO(b""),
        "CONTENT_LENGTH": "0",
        "HTTP_ACCEPT_ENCODING": "gzip",
        **headers,
    }

    def start_response(status, response_headers):
        captured["status"] = status
        captured["headers"] = dict(response_headers)

    body = b"".join(vercel_entrypoint.application(environ, start_response))
    return captured["status"], captured["headers"], body


def main() -> None:
    # Une page publique ne doit jamais importer le lourd serveur admin.
    status, headers, body = request("/")
    assert status == "200 OK"
    assert "passenger_wsgi" not in sys.modules
    assert headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
    assert headers["Content-Encoding"] == "gzip"
    html = gzip.decompress(body).decode("utf-8")
    assert "/static/index-core.js?v=" in html
    assert "/static/public-form-hardening.js?v=" in html
    assert '<link rel="icon" href="/images/favicon.svg" type="image/svg+xml">' in html

    status, headers, body = request("/static/index.css", "v=contract")
    assert status == "200 OK"
    assert headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert gzip.decompress(body).startswith(b"*,*::before")
    assert "passenger_wsgi" not in sys.modules

    status, headers, body = request("/images/bininga.jpg")
    assert status == "200 OK" and body.startswith(b"\xff\xd8")
    assert "stale-while-revalidate" in headers["Cache-Control"]

    status, headers, body = request("/images/favicon.svg")
    assert status == "200 OK"
    assert headers["Content-Type"] == "image/svg+xml"
    assert b"Ange Aim" in body

    # Les contenus dynamiques et sensibles restent sur l'application complète.
    assert vercel_entrypoint.try_serve({"REQUEST_METHOD": "GET", "PATH_INFO": "/data.json"}, None) is None
    assert vercel_entrypoint.try_serve({"REQUEST_METHOD": "GET", "PATH_INFO": "/api/load"}, None) is None
    assert vercel_entrypoint.try_serve({"REQUEST_METHOD": "GET", "PATH_INFO": "/actualites/test"}, None) is None
    assert vercel_entrypoint.try_serve({"REQUEST_METHOD": "GET", "PATH_INFO": "/images/sinistres/test.jpg"}, None) is None
    assert vercel_entrypoint.try_serve({"REQUEST_METHOD": "GET", "PATH_INFO": "/static/%2e%2e/server.py"}, None) is None
    assert vercel_entrypoint.try_serve({"REQUEST_METHOD": "GET", "PATH_INFO": "/images/../server.py"}, None) is None

    assert "https://www.youtube.com" in headers.get("Content-Security-Policy", "")
    assert "https://nominatim.openstreetmap.org" in headers.get("Content-Security-Policy", "")

    print("✅ Vercel public fast path — contrats valides")


if __name__ == "__main__":
    main()
