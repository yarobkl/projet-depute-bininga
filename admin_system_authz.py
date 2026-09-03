"""Server-side authorization, durability and public-form guards for BININGA."""

import gzip
import io
import os

import admin_owners
import admin_permissions
import db_resilience

_PERMISSION_RULES = {
    ("GET", "/api/users"): "users.read", ("GET", "/api/crm"): "crm.read",
    ("GET", "/api/crm/export"): "crm.export", ("GET", "/api/backups"): "backup.read",
    ("GET", "/api/logs"): "logs.read", ("GET", "/api/security"): "security.read",
    ("GET", "/api/security/bouclier"): "security.read", ("GET", "/api/monitoring/summary"): "monitoring.read",
    ("GET", "/api/monitoring/alerts"): "monitoring.read", ("GET", "/api/monitoring/endpoints"): "monitoring.read",
    ("GET", "/api/monitoring/requests"): "monitoring.read", ("GET", "/api/monitoring/exceptions"): "monitoring.read",
}
_PREFIX_PERMISSION_RULES = (
    ("POST", "/api/crm/", "crm.write"), ("POST", "/api/backups/", "backup.create"),
    ("POST", "/api/security/", "security.manage"), ("POST", "/api/monitoring/", "monitoring.manage"),
)
_STATELESS_POSTS_WITHOUT_DB = {"/api/login", "/api/logout", "/api/chat", "/api/track-visit", "/api/test/reset"}
_PUBLIC_FORM_SCRIPT = b'\n<script src="/static/public-form-hardening.js?v=20260819-privacy-1" defer></script>\n'


def _response_header(handler, name: str) -> str:
    wanted = name.lower()
    for key, value in getattr(handler, "_response_headers", []):
        if str(key).lower() == wanted: return str(value)
    return ""


def _set_response_body(handler, body: bytes) -> None:
    handler.wfile = io.BytesIO(body)
    handler._response_headers = [(k, v) for k, v in handler._response_headers if str(k).lower() != "content-length"]
    handler._response_headers.append(("Content-Length", str(len(body))))


def _ensure_public_form_hardening(server) -> None:
    handler_cls = server.BiningaHandler
    if getattr(handler_cls, "_bininga_public_forms_wrapped", False): return
    original_get = handler_cls.do_GET
    def hardened_get(self):
        original_get(self)
        if getattr(self, "_status_code", 200) != 200: return
        raw = self.wfile.getvalue(); encoding = _response_header(self, "Content-Encoding").lower(); was_gzip = encoding == "gzip"
        try: body = gzip.decompress(raw) if was_gzip else raw
        except Exception: return
        if b"static/index.js" not in body or b"Espace Administration" in body: return
        if b"static/public-form-hardening.js" in body or b"</body>" not in body: return
        patched = body.replace(b"</body>", _PUBLIC_FORM_SCRIPT + b"</body>", 1)
        if was_gzip: patched = gzip.compress(patched, compresslevel=6)
        _set_response_body(self, patched)
    handler_cls.do_GET = hardened_get; handler_cls._bininga_public_forms_wrapped = True


def _guard_serverless_durability(server, handler, path: str, method: str) -> bool:
    if method != "POST" or not os.environ.get("VERCEL"): return True
    if not path.startswith("/api/") or path in _STATELESS_POSTS_WITHOUT_DB: return True
    if db_resilience.can_persist(server): return True
    try: server.audit_log("PERSISTENCE_REJECT", handler.client_address[0], f"Mutation refusée sans persistance saine : {path}")
    except Exception: pass
    status = db_resilience.public_status(server)
    handler._json({"ok": False, "code": "PERSISTENCE_REQUIRED", "retryable": True, "database": status.get("database"), "circuit_open": status.get("circuit_open", False), "message": "Enregistrement temporairement indisponible. La demande n'a pas été enregistrée ; veuillez réessayer dans quelques instants."}, 503)
    return False


def _required_permission(path: str, method: str):
    direct = _PERMISSION_RULES.get((method, path))
    if direct: return direct
    for rule_method, prefix, permission in _PREFIX_PERMISSION_RULES:
        if method == rule_method and path.startswith(prefix): return permission
    return None


def guard_request(server, handler):
    _ensure_public_form_hardening(server)
    path = handler.path.split("?", 1)[0]; method = handler.command.upper()
    if not _guard_serverless_durability(server, handler, path, method): return False
    permission = _required_permission(path, method)
    if not permission: return True
    token = handler.headers.get("X-Admin-Token", ""); session = server.get_session(token) if token else None
    if not session: return True
    # Owner policy remains the highest, explicit authority boundary.
    if admin_owners.is_owner_session(server, session): return True
    if admin_permissions.has_permission(server, session, permission): return True
    server.audit_log("AUTHZ_REJECT", handler.client_address[0], f"Permission {permission} refusée à {path} pour {session.get('username', '?')}")
    handler._json({"ok": False, "code": "PERMISSION_DENIED", "permission": permission, "message": "Droits insuffisants"}, 403)
    return False
