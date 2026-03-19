"""
Serveur public — Site web Bininga
Sert les pages publiques et relaie les appels API vers le serveur admin.
L'URL de l'admin est définie via la variable d'environnement ADMIN_URL.
"""

import http.server
import os
import posixpath
import urllib.request
import urllib.error
import ssl
import json
import secrets
import re
from urllib.parse import urlparse, unquote

# ── Configuration ──────────────────────────────────────────
PORT       = int(os.environ.get("PORT", 8080))
ADMIN_URL  = os.environ.get("ADMIN_URL", "").rstrip("/")  # ex: https://xxxxx.up.railway.app
BASE_DIR   = os.path.realpath(os.getcwd())

# Extensions statiques autorisées
ALLOWED_EXT = {".html", ".css", ".js", ".png", ".jpg", ".jpeg",
               ".gif", ".webp", ".svg", ".ico", ".xml", ".txt",
               ".mp4", ".webm"}

# Fichiers sensibles à ne jamais servir
BLOCKED_FILES = {
    "server.py", "server_public.py", "users.json", "sessions.json",
    "audit.log", "contacts.json", "data.json", "cert.pem", "key.pem",
    "admin.js", "admin.css",
}

# Pages réservées à l'admin — redirigées vers le site public
ADMIN_PAGES = {"/admin.html", "/gestion.html", "/ministre.html"}


def _safe_path(relative: str):
    """Retourne le chemin absolu seulement s'il est sûr, sinon None."""
    normalized = posixpath.normpath("/" + relative).lstrip("/")
    filename   = os.path.basename(normalized)

    if filename in BLOCKED_FILES:
        return None

    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in ALLOWED_EXT:
        return None

    resolved = os.path.realpath(os.path.join(BASE_DIR, normalized))
    if not resolved.startswith(BASE_DIR + os.sep) and resolved != BASE_DIR:
        return None

    return resolved if os.path.isfile(resolved) else None


def _proxy_to_admin(handler, method: str, path: str, body: bytes = b""):
    """Relaie une requête vers le serveur admin et renvoie la réponse."""
    if not ADMIN_URL:
        handler._json({"ok": False, "message": "Admin URL non configurée"}, 503)
        return

    target = ADMIN_URL + path
    headers = {
        "Content-Type": handler.headers.get("Content-Type", "application/json"),
        "X-Forwarded-For": handler.client_address[0],
        "X-Public-Proxy": "1",
    }

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(target, data=body if body else None,
                                     headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            raw     = resp.read()
            ctype   = resp.headers.get("Content-Type", "application/json")
            handler.send_response(resp.status)
            handler.send_header("Content-Type", ctype)
            handler.send_header("Content-Length", str(len(raw)))
            _cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        handler.send_response(e.code)
        handler.send_header("Content-Type", "application/json")
        _cors_headers(handler)
        handler.end_headers()
        handler.wfile.write(raw)
    except Exception as e:
        handler._json({"ok": False, "message": f"Erreur proxy : {e}"}, 502)


def _cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")


MIME = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".svg":  "image/svg+xml",
    ".ico":  "image/x-icon",
    ".xml":  "application/xml",
    ".txt":  "text/plain",
    ".mp4":  "video/mp4",
    ".webm": "video/webm",
}


class PublicHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # Silencieux

    def _json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        _cors_headers(self)
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath: str):
        ext  = os.path.splitext(filepath)[1].lower()
        mime = MIME.get(ext, "application/octet-stream")
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        _cors_headers(self)
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = unquote(parsed.path)

        # Bloquer l'accès aux pages admin
        if path in ADMIN_PAGES:
            self.send_response(301)
            self.send_header("Location", "/")
            self.end_headers()
            return

        # Données du site → proxy vers l'admin
        if path in ("/api/load", "/data.json"):
            _proxy_to_admin(self, "GET", "/api/load")
            return

        # Racine → index.html
        if path in ("/", ""):
            path = "/index.html"

        # Fichier statique
        filepath = _safe_path(path.lstrip("/"))
        if filepath:
            self._serve_file(filepath)
            return

        self.send_response(404)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>404 - Page non trouvée</h1>")

    def do_POST(self):
        parsed  = urlparse(self.path)
        path    = unquote(parsed.path)
        length  = int(self.headers.get("Content-Length", 0))
        body    = self.rfile.read(length) if length else b""

        # Formulaire de contact → proxy vers l'admin
        if path == "/api/contact":
            _proxy_to_admin(self, "POST", "/api/contact", body)
            return

        # Upload sinistre → proxy vers l'admin
        if path == "/api/upload-sinistre":
            _proxy_to_admin(self, "POST", "/api/upload-sinistre", body)
            return

        self._json({"ok": False, "message": "Route inconnue"}, 404)


if __name__ == "__main__":
    if not ADMIN_URL:
        print("⚠️  ATTENTION: Variable ADMIN_URL non définie !")
        print("   Définir dans Railway: ADMIN_URL=https://ton-admin.up.railway.app")

    server = http.server.HTTPServer(("0.0.0.0", PORT), PublicHandler)
    print(f"✅ Serveur public démarré sur le port {PORT}")
    print(f"   Admin URL : {ADMIN_URL or '(non définie)'}")
    server.serve_forever()
