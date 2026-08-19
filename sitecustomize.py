"""Runtime-only environment compatibility and bootstrap safety for Vercel.

Python imports ``sitecustomize`` automatically when it is present on sys.path.
Keep this module deliberately small: it resolves a durable PostgreSQL URL
without storing database credentials in GitHub, then prevents the legacy
server import from generating a credential that it would otherwise print to
runtime logs.
"""

import json
import os
import secrets
import urllib.error
import urllib.request


_DB_BRIDGE_URL = (
    "https://gcklaqpesdsnjzgkccdq.supabase.co/functions/v1/"
    "bininga-vercel-db-bridge"
)


def _install_database_url_alias() -> None:
    """Populate DATABASE_URL from managed envs or the Vercel OIDC bridge.

    The preferred path remains a normal server-side DATABASE_URL (or a
    provider-managed Postgres alias).  When those variables are absent on
    Vercel, the deployment's short-lived VERCEL_OIDC_TOKEN authenticates to a
    Supabase Edge Function which validates the exact team/project/environment
    claims before returning the connection URL over HTTPS.  The URL is kept
    only in process memory and is never printed or committed.
    """
    if os.environ.get("DATABASE_URL"):
        return

    for key in ("POSTGRES_PRISMA_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING"):
        value = os.environ.get(key, "").strip()
        if value:
            os.environ["DATABASE_URL"] = value
            return

    if not os.environ.get("VERCEL"):
        return

    oidc_token = os.environ.get("VERCEL_OIDC_TOKEN", "").strip()
    if not oidc_token:
        return

    request = urllib.request.Request(
        _DB_BRIDGE_URL,
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {oidc_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "bininga-vercel-runtime/1",
        },
    )

    # Cold starts must not hang if the external exchange is temporarily
    # unavailable.  A second short retry absorbs most transient network races;
    # the existing Vercel durable-write guard remains fail-closed if both fail.
    for _attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=4) as response:
                if response.status != 200:
                    continue
                payload = json.loads(response.read(8192).decode("utf-8"))
                value = str(payload.get("database_url", "")).strip()
                if payload.get("ok") is True and value.startswith(("postgres://", "postgresql://")):
                    os.environ["DATABASE_URL"] = value
                    return
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            continue
        except Exception:
            # Never expose token/URL details through startup logs.
            continue


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
