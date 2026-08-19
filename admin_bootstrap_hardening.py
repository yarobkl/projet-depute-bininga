"""Fail-closed admin bootstrap rules for BININGA on Vercel.

This module deliberately leaves the legacy o2switch/local behaviour untouched.
On Vercel, however, a source-controlled default admin path and a generated
password printed to logs are not acceptable production fallbacks.
"""

import os
import secrets


def _remove_ephemeral_bootstrap_user(server) -> None:
    """Remove only the synthetic user created during the legacy import path."""
    if os.environ.get("BININGA_EPHEMERAL_BOOTSTRAP") != "1":
        return

    placeholder = getattr(server, "ADMIN_PASS", "")
    verify = getattr(server, "_verify_password", None)
    users = server.load_users()
    kept = []
    removed = False

    for user in users:
        is_synthetic_admin = (
            callable(verify)
            and user.get("username") == server.ADMIN_USER
            and placeholder
            and verify(placeholder, user.get("password_hash", ""))
        )
        if is_synthetic_admin:
            removed = True
            continue
        kept.append(user)

    if removed:
        try:
            server.save_users(kept)
            print(
                "[SECURITY] Compte bootstrap process-local nettoyé après import.",
                flush=True,
            )
        except Exception as exc:
            # Fail closed: the placeholder is unknown outside this process, so
            # even a cleanup failure does not expose a usable credential.
            print(f"[SECURITY] Nettoyage bootstrap différé : {type(exc).__name__}", flush=True)

    # Restore the real runtime state: the deployment did not provide a password.
    server.ADMIN_PASS = ""
    os.environ.pop("BININGA_PASS", None)
    os.environ.pop("BININGA_EPHEMERAL_BOOTSTRAP", None)


def install(server) -> None:
    """Install conservative Vercel-only admin bootstrap protections."""
    if not os.environ.get("VERCEL"):
        return
    if getattr(server, "_bininga_admin_bootstrap_hardened", False):
        return

    # sitecustomize prevents the legacy module-level init_users() call from
    # printing a credential before this module can run. Remove that synthetic
    # bootstrap user now, without touching any pre-existing persisted account.
    _remove_ephemeral_bootstrap_user(server)

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
