"""Runtime-only environment compatibility for managed Postgres providers.

Python imports ``sitecustomize`` automatically when it is present on sys.path.
Keep this module deliberately tiny: it only aliases managed Vercel/Supabase
Postgres connection variables to the ``DATABASE_URL`` name already consumed by
server.py. Secret values remain exclusively in the deployment environment.
"""

import os


def _install_database_url_alias() -> None:
    if os.environ.get("DATABASE_URL"):
        return

    # Supabase's Vercel integration currently provisions these server-side
    # variables. Prefer the pooled URL for serverless workloads, then fall back
    # to the other managed connection strings when available.
    for key in ("POSTGRES_PRISMA_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING"):
        value = os.environ.get(key, "").strip()
        if value:
            os.environ["DATABASE_URL"] = value
            break


_install_database_url_alias()
