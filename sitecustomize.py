"""Runtime-only environment compatibility and bootstrap safety for Vercel.

Python imports ``sitecustomize`` automatically when it is present on sys.path.
Keep this module deliberately tiny: it aliases managed Vercel/Supabase Postgres
variables and prevents the legacy server import from generating a credential
that it would otherwise print to deployment logs.
"""

import os
import secrets


def _install_database_url_alias() -> None:
    if os.environ.get("DATABASE_URL"):
        return

    # Supabase's Vercel integration provisions these server-side variables.
    # Prefer the pooled URL for serverless workloads, then the other managed
    # connection strings. Secret values remain in the deployment environment.
    for key in ("POSTGRES_PRISMA_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING"):
        value = os.environ.get(key, "").strip()
        if value:
            os.environ["DATABASE_URL"] = value
            break


def _install_safe_bootstrap_placeholder() -> None:
    """Prevent server.py from printing a generated admin password on import.

    server.py performs its first ``init_users()`` call while it is imported,
    before passenger_wsgi can install the normal hardening wrappers. When the
    Vercel deployment has no explicit BININGA_PASS, give that legacy bootstrap
    a process-local random placeholder and mark it for immediate cleanup after
    import. The value is never printed or persisted as a usable credential.
    """
    if not os.environ.get("VERCEL") or os.environ.get("BININGA_PASS"):
        return

    os.environ["BININGA_PASS"] = secrets.token_urlsafe(48)
    os.environ["BININGA_EPHEMERAL_BOOTSTRAP"] = "1"


_install_database_url_alias()
_install_safe_bootstrap_placeholder()
