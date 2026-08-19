"""Server-side authorization and durability guards for BININGA admin APIs."""

import os


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

# These POST routes do not claim to durably save business/admin data. They may
# keep working on a serverless instance while the persistent database is being
# configured. Every other API mutation fails closed on Vercel when no DB is
# available, rather than returning a false success for data written only to /tmp.
_STATELESS_POSTS_WITHOUT_DB = {
    "/api/login",
    "/api/logout",
    "/api/chat",
    "/api/track-visit",
    "/api/test/reset",
}


def _guard_serverless_durability(server, handler, path: str, method: str) -> bool:
    """Reject durable mutations on Vercel when no persistent DB is configured."""
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
        server.audit_log(
            "PERSISTENCE_REJECT",
            handler.client_address[0],
            f"Mutation refusée sans base persistante : {path}",
        )
    except Exception:
        pass

    handler._json({
        "ok": False,
        "code": "PERSISTENCE_REQUIRED",
        "retryable": True,
        "message": (
            "Enregistrement temporairement indisponible. "
            "La demande n'a pas été enregistrée ; veuillez réessayer dans quelques instants."
        ),
    }, 503)
    return False


def guard_request(server, handler):
    """Apply durability then System/CRM authorization rules.

    Unauthenticated requests are deliberately left to ``server.py`` whenever
    possible so its existing 401/rate-limit/audit behaviour remains authoritative.
    """
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

    if session.get("username") == server.ADMIN_USER:
        return True

    server.audit_log(
        "AUTHZ_REJECT",
        handler.client_address[0],
        f"Accès système refusé à {path} pour {session.get('username', '?')}",
    )
    handler._json({"ok": False, "message": "Réservé à l'administrateur principal"}, 403)
    return False
