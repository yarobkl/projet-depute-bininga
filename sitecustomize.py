"""Runtime-only environment compatibility and bootstrap safety for Vercel.

Python imports ``sitecustomize`` automatically when it is present on sys.path.
Keep this module deliberately tiny: it aliases managed Vercel/Supabase Postgres
variables, can obtain a short-lived runtime DB credential through an OIDC-guarded
Supabase broker, and prevents the legacy server import from generating a
credential that it would otherwise print to deployment logs.
"""

import json
import os
import secrets
import urllib.request


_SUPABASE_DB_BRIDGE = (
    "https://gcklaqpesdsnjzgkccdq.supabase.co/functions/v1/"
    "bininga-vercel-db-bridge"
)


def _valid_database_url(value: str) -> bool:
    return value.startswith(("postgres://", "postgresql://", "mysql://", "mariadb://"))


def _install_database_url_alias() -> None:
    if os.environ.get("DATABASE_URL"):
        return

    # Supabase's Vercel integration provisions these server-side variables.
    # Prefer the pooled URL for serverless workloads, then the other managed
    # connection strings. Secret values remain in the deployment environment.
    for key in ("POSTGRES_PRISMA_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING"):
        value = os.environ.get(key, "").strip()
        if value and _valid_database_url(value):
            os.environ["DATABASE_URL"] = value
            return

    # Existing Supabase projects are not always attached through Vercel's
    # Marketplace integration. In that case, exchange Vercel's automatically
    # supplied project OIDC identity for the database URL at runtime. The
    # Supabase function validates issuer, audience, project and environment
    # before returning anything. No database secret is committed or persisted.
    if not os.environ.get("VERCEL"):
        return
    oidc_token = os.environ.get("VERCEL_OIDC_TOKEN", "").strip()
    if not oidc_token:
        return

    request = urllib.request.Request(
        _SUPABASE_DB_BRIDGE,
        method="POST",
        headers={
            "Authorization": f"Bearer {oidc_token}",
            "Content-Type": "application/json",
            "User-Agent": "bininga-vercel-runtime/1",
        },
        data=b"{}",
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            payload = json.loads(response.read(16384).decode("utf-8"))
        value = str(payload.get("database_url", "")).strip()
        if payload.get("ok") is True and _valid_database_url(value):
            os.environ["DATABASE_URL"] = value
    except Exception:
        # Keep fail-closed behaviour: server.py will report no durable database
        # and the persistence guard will reject durable writes.
        return


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
