"""Chemin public léger pour Vercel.

La page d'accueil et les médias versionnés n'ont pas besoin d'initialiser le
serveur d'administration, PostgreSQL, le moteur IA ou le monitoring. Ce module
sert uniquement les fichiers publics présents dans le dépôt. Toutes les API,
les pages d'article dynamiques et les images de dossiers restent prises en
charge par l'application complète.
"""

from __future__ import annotations

import gzip
import hashlib
import mimetypes
import os
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent
PUBLIC_TEXT_ASSETS = (
    "index.css", "mobile.css", "public-experience.css", "chat.css",
    "i18n.js", "i18n-data.en.js", "i18n-data.es.js", "i18n-data.zh.js",
    "i18n-data.ru.js", "index.js", "index-core.js",
    "public-experience.js", "chat.js", "public-form-hardening.js",
    "analytics-consent.css", "analytics-consent.js",
)
TEXT_MIMES = {"text/css", "text/javascript", "application/javascript"}
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg",
                  ".ico", ".mp4", ".webm", ".ogg", ".mp3"}


def _build_version() -> str:
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
        return sha[:12].lower()
    # Stable in a local checkout and changes whenever the public HTML changes.
    try:
        return hashlib.sha256((ROOT / "index.html").read_bytes()).hexdigest()[:12]
    except Exception:
        return "public"


BUILD_VERSION = _build_version()


def _security_headers() -> list[tuple[str, str]]:
    csp = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https://*.tile.openstreetmap.org "
        "https://www.openstreetmap.org https://www.google-analytics.com "
        "https://www.googletagmanager.com; "
        "frame-src https://www.openstreetmap.org https://www.youtube.com "
        "https://www.youtube-nocookie.com; "
        "connect-src 'self' https://nominatim.openstreetmap.org "
        "https://www.google-analytics.com https://*.google-analytics.com "
        "https://www.googletagmanager.com; "
        "media-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; "
        "upgrade-insecure-requests"
    )
    return [
        ("X-Frame-Options", "DENY"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ("Permissions-Policy", "camera=(), microphone=(), geolocation=(self), payment=()"),
        ("Cross-Origin-Opener-Policy", "same-origin"),
        ("Cross-Origin-Resource-Policy", "same-origin"),
        ("X-Permitted-Cross-Domain-Policies", "none"),
        ("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"),
        ("Content-Security-Policy", csp),
    ]


def _version_html(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="replace")
    for asset in PUBLIC_TEXT_ASSETS:
        text = re.sub(
            rf"(?:/)?static/{re.escape(asset)}(?:\?v=[^\"'<\s]*)?",
            f"/static/{asset}?v={BUILD_VERSION}",
            text,
        )
    return text.encode("utf-8")


def _safe_public_file(path: str) -> tuple[Path, bool] | None:
    if path in ("/", "/index.html"):
        return ROOT / "index.html", True
    if path in ("/robots.txt", "/sitemap.xml"):
        return ROOT / path.lstrip("/"), False
    if not path.startswith(("/static/", "/images/")):
        return None
    # Les pièces jointes des dossiers peuvent venir de PostgreSQL et ne passent
    # donc jamais par ce chemin statique.
    if path.startswith("/images/sinistres/"):
        return None
    prefix = "/static/" if path.startswith("/static/") else "/images/"
    public_root = (ROOT / prefix.strip("/")).resolve()
    try:
        relative_raw = unquote(path[len(prefix):])
        if "\x00" in relative_raw:
            return None
        normalized = posixpath.normpath(relative_raw)
        if normalized in ("", ".") or normalized.startswith("../") or normalized == "..":
            return None
        resolved = (public_root / normalized).resolve()
        resolved.relative_to(public_root)
    except (ValueError, OSError):
        return None
    if not resolved.is_file():
        return None
    return resolved, False


def _mime(path: Path) -> str:
    suffix = path.suffix.lower()
    explicit = {
        ".js": "text/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".xml": "application/xml; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
    }
    return explicit.get(suffix, mimetypes.guess_type(str(path))[0] or "application/octet-stream")


def _etag(path: Path, html: bool = False) -> str:
    stat = path.stat()
    version = f"-{BUILD_VERSION}" if html else ""
    return f'W/"{stat.st_size:x}-{stat.st_mtime_ns:x}{version}"'


def _cache_control(path: Path, html: bool, query: str) -> str:
    if html:
        return "no-cache, no-store, must-revalidate"
    if path.suffix.lower() in (".css", ".js") and query:
        return "public, max-age=31536000, immutable"
    if path.suffix.lower() in MEDIA_SUFFIXES:
        return "public, max-age=604800, stale-while-revalidate=86400"
    return "public, max-age=3600, must-revalidate"


def try_serve(environ, start_response):
    """Retourne une réponse WSGI publique, ou ``None`` pour l'app complète."""
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    if method not in ("GET", "HEAD"):
        return None
    raw_path = environ.get("PATH_INFO") or "/"
    candidate = _safe_public_file(raw_path)
    if candidate is None:
        return None
    path, is_html = candidate
    mime = "text/html; charset=utf-8" if is_html else _mime(path)
    query = environ.get("QUERY_STRING") or ""
    etag = _etag(path, is_html)
    base_headers = [
        ("Content-Type", mime),
        ("Cache-Control", _cache_control(path, is_html, query)),
        ("ETag", etag),
    ] + _security_headers()

    if environ.get("HTTP_IF_NONE_MATCH") == etag:
        start_response("304 Not Modified", base_headers)
        return [b""]

    data = path.read_bytes()
    if is_html:
        data = _version_html(data)

    range_header = environ.get("HTTP_RANGE", "")
    is_media = mime.startswith(("video/", "audio/"))
    if is_media and range_header.startswith("bytes="):
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match:
            start_response("416 Range Not Satisfiable", base_headers + [
                ("Content-Range", f"bytes */{len(data)}"),
                ("Content-Length", "0"),
            ])
            return [b""]
        start_raw, end_raw = match.groups()
        if not start_raw and not end_raw:
            start_response("416 Range Not Satisfiable", base_headers + [
                ("Content-Range", f"bytes */{len(data)}"),
                ("Content-Length", "0"),
            ])
            return [b""]
        if start_raw:
            start = int(start_raw)
            end = int(end_raw) if end_raw else len(data) - 1
        else:
            length = min(int(end_raw), len(data))
            start, end = len(data) - length, len(data) - 1
        if start >= len(data) or start > end:
            start_response("416 Range Not Satisfiable", base_headers + [
                ("Content-Range", f"bytes */{len(data)}"),
                ("Content-Length", "0"),
            ])
            return [b""]
        end = min(end, len(data) - 1)
        body = data[start:end + 1]
        headers = base_headers + [
            ("Accept-Ranges", "bytes"),
            ("Content-Range", f"bytes {start}-{end}/{len(data)}"),
            ("Content-Length", str(len(body))),
        ]
        start_response("206 Partial Content", headers)
        return [b"" if method == "HEAD" else body]

    headers = base_headers
    if is_media:
        headers.append(("Accept-Ranges", "bytes"))
    accept_encoding = environ.get("HTTP_ACCEPT_ENCODING", "")
    if "gzip" in accept_encoding and (mime.startswith("text/") or mime.startswith("application/json")):
        data = gzip.compress(data, compresslevel=6)
        headers.extend([("Content-Encoding", "gzip"), ("Vary", "Accept-Encoding")])
    headers.append(("Content-Length", str(len(data))))
    start_response("200 OK", headers)
    return [b"" if method == "HEAD" else data]
