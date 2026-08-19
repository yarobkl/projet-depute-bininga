"""Server-side authorization alignment for BININGA admin system panels."""

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


def guard_request(server, handler):
    """Deny authenticated non-main-admin access to System/CRM APIs.

    Unauthenticated requests are deliberately left to ``server.py`` so its
    existing 401/rate-limit/audit behaviour remains authoritative.
    """
    path = handler.path.split("?", 1)[0]
    method = handler.command.upper()

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
