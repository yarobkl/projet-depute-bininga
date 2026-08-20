"""Fail-closed admin bootstrap rules for BININGA on Vercel.

The preferred production configuration remains environment-based. When the
Vercel project has no explicit admin environment variables, this module keeps
the admin usable by applying a one-time, database-persisted recovery bootstrap:
- a stable private admin path is enabled;
- the persisted admin account receives a strong pre-generated password hash;
- a DB marker prevents future cold starts from resetting a password changed
  later through the admin interface.

No plaintext password is stored in the repository and no credential is printed
to deployment logs.
"""

import os


_FALLBACK_ADMIN_PATH = "cabinet-bininga-Ff4wjckb0MG7XRvv"
_RECOVERY_ADMIN_HASH = (
    "pbkdf2:sha256:2e6a037b47e08e30166215594ce1468a:"
    "769d63f8389f1fcd7eabb5d10cb6d84b1ed9c1a751dec5206775ce22f69fef57"
)
_RECOVERY_MARKER_KEY = "admin_bootstrap_20260820_v3"


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
            print(f"[SECURITY] Nettoyage bootstrap différé : {type(exc).__name__}", flush=True)

    server.ADMIN_PASS = ""
    os.environ.pop("BININGA_PASS", None)
    os.environ.pop("BININGA_EPHEMERAL_BOOTSTRAP", None)


def _recovery_marker_present(server) -> bool:
    loader = getattr(server, "_pg_load", None)
    if not callable(loader):
        return False
    try:
        marker = loader(_RECOVERY_MARKER_KEY)
        return isinstance(marker, dict) and marker.get("done") is True
    except Exception:
        return False


def _write_recovery_marker(server) -> bool:
    saver = getattr(server, "_pg_save", None)
    if not callable(saver):
        return False
    try:
        return bool(saver(_RECOVERY_MARKER_KEY, {"done": True, "version": 3}))
    except Exception:
        return False


def _ensure_recovery_admin(server) -> None:
    """Provision the persisted admin once when Vercel env secrets are absent."""
    if os.environ.get("BININGA_PASS", "").strip():
        return

    if _recovery_marker_present(server):
        return

    try:
        users = server.load_users()
        if not isinstance(users, list):
            users = []

        username = getattr(server, "ADMIN_USER", "admin") or "admin"
        found = False
        updated = []

        for raw_user in users:
            user = dict(raw_user) if isinstance(raw_user, dict) else {}
            if user.get("username") == username:
                user["password_hash"] = _RECOVERY_ADMIN_HASH
                user["role"] = "admin"
                user["nom"] = user.get("nom") or "Administration BININGA"
                found = True
            updated.append(user)

        if not found:
            updated.append({
                "username": username,
                "password_hash": _RECOVERY_ADMIN_HASH,
                "role": "admin",
                "nom": "Administration BININGA",
            })

        server.save_users(updated)

        if _write_recovery_marker(server):
            print(
                "[SECURITY] Accès admin de récupération provisionné en base (mot de passe non journalisé).",
                flush=True,
            )
        else:
            print(
                "[SECURITY] Compte admin provisionné; marqueur DB à réessayer au prochain démarrage.",
                flush=True,
            )
    except Exception as exc:
        print(
            f"[SECURITY] Provisionnement admin différé : {type(exc).__name__}",
            flush=True,
        )


def install(server) -> None:
    """Install conservative Vercel-only admin bootstrap protections."""
    if not os.environ.get("VERCEL"):
        return
    if getattr(server, "_bininga_admin_bootstrap_hardened", False):
        return

    _remove_ephemeral_bootstrap_user(server)

    configured_path = os.environ.get("ADMIN_SECRET_PATH", "").strip().strip("/")
    if configured_path:
        server.ADMIN_SECRET_PATH = configured_path
    else:
        server.ADMIN_SECRET_PATH = _FALLBACK_ADMIN_PATH
        print(
            "[SECURITY] ADMIN_SECRET_PATH absent — chemin admin de récupération activé.",
            flush=True,
        )

    original_init_users = server.init_users

    def secure_init_users():
        existing = server.load_users()
        if existing:
            return

        if not server.ADMIN_PASS:
            print(
                "[SECURITY] BININGA_PASS absent — bootstrap legacy désactivé.",
                flush=True,
            )
            return

        return original_init_users()

    server.init_users = secure_init_users
    _ensure_recovery_admin(server)
    server._bininga_admin_bootstrap_hardened = True
