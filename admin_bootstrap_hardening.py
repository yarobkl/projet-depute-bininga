"""Fail-closed admin bootstrap rules for BININGA on Vercel.

This module deliberately leaves the legacy o2switch/local behaviour untouched.
On Vercel, however, a source-controlled default admin path and a generated
password printed to logs are not acceptable production fallbacks.
"""

import os
import secrets


def install(server) -> None:
    """Install conservative Vercel-only admin bootstrap protections."""
    if not os.environ.get("VERCEL"):
        return
    if getattr(server, "_bininga_admin_bootstrap_hardened", False):
        return

    # A default path embedded in a public repository is not secret. If the
    # deployment did not explicitly configure ADMIN_SECRET_PATH, disable the
    # admin document behind an unguessable process-local path. Public pages and
    # APIs keep working; setting ADMIN_SECRET_PATH restores the intended route.
    configured_path = os.environ.get("ADMIN_SECRET_PATH", "").strip().strip("/")
    if not configured_path:
        server.ADMIN_SECRET_PATH = "_admin_disabled_" + secrets.token_urlsafe(32)
        print(
            "[SECURITY] ADMIN_SECRET_PATH absent — interface admin désactivée "
            "jusqu'à configuration explicite.",
            flush=True,
        )

    original_init_users = server.init_users

    def secure_init_users():
        # Preserve already-persisted users. Their password hashes remain the
        # source of truth and no bootstrap password is required.
        existing = server.load_users()
        if existing:
            return

        # The legacy fallback generated a random admin password and printed it
        # to deployment logs. On Vercel, fail closed instead of emitting a
        # credential or creating a different ephemeral account per cold start.
        if not server.ADMIN_PASS:
            print(
                "[SECURITY] BININGA_PASS absent et aucun compte persistant — "
                "bootstrap admin désactivé (aucun secret généré ni journalisé).",
                flush=True,
            )
            return

        return original_init_users()

    server.init_users = secure_init_users
    server._bininga_admin_bootstrap_hardened = True
