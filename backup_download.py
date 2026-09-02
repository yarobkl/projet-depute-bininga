"""Archive de reprise téléchargeable depuis l'administration BININGA."""

from __future__ import annotations

import secrets

import backup_bininga


ROUTE = "/api/backups/export"


def guard_request(server, handler) -> bool:
    """Intercepte uniquement l'export complet, avec auth admin et CSRF."""
    if handler.command != "POST" or handler.path.split("?", 1)[0] != ROUTE:
        return True

    token = str(handler.headers.get("X-Admin-Token", ""))
    session = server.get_session(token) if token else None
    if not session:
        handler._json({"ok": False, "message": "Non autorisé"}, 401)
        return False
    if session.get("role") != "admin":
        handler._json({"ok": False, "message": "Réservé à l'admin"}, 403)
        return False

    received = str(handler.headers.get("X-CSRF-Token", ""))
    expected = str(session.get("csrf_token", ""))
    if not received or not expected or not secrets.compare_digest(received, expected):
        server.audit_log("CSRF_REJECT", handler.client_address[0], f"Token CSRF invalide sur {ROUTE}")
        handler._json({"ok": False, "message": "Requête invalide (CSRF)"}, 403)
        return False

    try:
        filename, content, manifest = backup_bininga.build_backup_archive()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/zip")
        handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        handler.send_header("Content-Length", str(len(content)))
        handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        handler.send_header("Pragma", "no-cache")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.end_headers()
        handler.wfile.write(content)
        server.audit_log(
            "BACKUP_EXPORT",
            handler.client_address[0],
            f"Archive de reprise téléchargée : {manifest['store_count']} blocs, "
            f"{manifest['photo_count']} photos",
        )
    except Exception as exc:
        server.audit_log("BACKUP_EXPORT_ERROR", handler.client_address[0], type(exc).__name__)
        handler._json({"ok": False, "message": "Export impossible — vérifiez la connexion à la base"}, 500)
    return False
