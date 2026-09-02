"""Server-side authorization, durability and public-form guards for BININGA."""

import gzip
import io
import os

import owner_policy


_MAIN_ADMIN_GET = {
    "/api/users",
    "/api/crm",
    "/api/crm/export",
    "/api/backups",
    "/api/logs",
    "/api/security",
    "/api/security/bouclier",
    "/api/monitoring/summary",
    "/api/monitoring/alerts",
    "/api/monitoring/endpoints",
    "/api/monitoring/requests",
    "/api/monitoring/exceptions",
}

_MAIN_ADMIN_POST_PREFIXES = (
    "/api/crm/",
    "/api/backups/",
    "/api/security/",
    "/api/monitoring/",
)

_STATELESS_POSTS_WITHOUT_DB = {
    "/api/login",
    "/api/logout",
    "/api/chat",
    "/api/track-visit",
    "/api/test/reset",
}

_PUBLIC_FORM_SCRIPT = b'\n<script src="/static/public-form-hardening.js?v=20260819-privacy-1" defer></script>\n'


def _response_header(handler, name: str) -> str:
    wanted = name.lower()
    for key, value in getattr(handler, "_response_headers", []):
        if str(key).lower() == wanted:
            return str(value)
    return ""


def _set_response_body(handler, body: bytes) -> None:
    handler.wfile = io.BytesIO(body)
    handler._response_headers = [
        (key, value) for key, value in handler._response_headers
        if str(key).lower() != "content-length"
    ]
    handler._response_headers.append(("Content-Length", str(len(body))))


def _ensure_public_form_hardening(server) -> None:
    handler_cls = server.BiningaHandler
    if getattr(handler_cls, "_bininga_public_forms_wrapped", False):
        return
    original_get = handler_cls.do_GET

    def hardened_get(self):
        original_get(self)
        if getattr(self, "_status_code", 200) != 200:
            return
        raw = self.wfile.getvalue()
        encoding = _response_header(self, "Content-Encoding").lower()
        was_gzip = encoding == "gzip"
        try:
            body = gzip.decompress(raw) if was_gzip else raw
        except Exception:
            return
        if b"static/index.js" not in body or b"Espace Administration" in body:
            return
        if b"static/public-form-hardening.js" in body or b"</body>" not in body:
            return
        patched = body.replace(b"</body>", _PUBLIC_FORM_SCRIPT + b"</body>", 1)
        if was_gzip:
            patched = gzip.compress(patched, compresslevel=6)
        _set_response_body(self, patched)

    handler_cls.do_GET = hardened_get
    handler_cls._bininga_public_forms_wrapped = True


def _guard_serverless_durability(server, handler, path: str, method: str) -> bool:
    if method != "POST" or not os.environ.get("VERCEL"):
        return True
    if not path.startswith("/api/") or path in _STATELESS_POSTS_WITHOUT_DB:
        return True
    try:
        backend, _ = server._db_config()
    except Exception:
        backend = None
    if backend:
        return True
    try:
        server.audit_log("PERSISTENCE_REJECT", handler.client_address[0], f"Mutation refusée sans base persistante : {path}")
    except Exception:
        pass
    handler._json({
        "ok": False,
        "code": "PERSISTENCE_REQUIRED",
        "retryable": True,
        "message": "Enregistrement temporairement indisponible. La demande n'a pas été enregistrée ; veuillez réessayer dans quelques instants.",
    }, 503)
    return False


def guard_request(server, handler):
    _ensure_public_form_hardening(server)
    path = handler.path.split("?", 1)[0]
    method = handler.command.upper()
    if not _guard_serverless_durability(server, handler, path, method):
        return False
    protected = path in _MAIN_ADMIN_GET if method == "GET" else (
        method == "POST" and any(path.startswith(prefix) for prefix in _MAIN_ADMIN_POST_PREFIXES)
    )
    if not protected:
        return True
    token = handler.headers.get("X-Admin-Token", "")
    session = server.get_session(token) if token else None
    if not session:
        return True
    if owner_policy.is_owner_session(server, session):
        return True
    server.audit_log("AUTHZ_REJECT", handler.client_address[0], f"Accès système refusé à {path} pour {session.get('username', '?')}")
    handler._json({"ok": False, "message": "Réservé aux propriétaires de l’administration"}, 403)
    return False
