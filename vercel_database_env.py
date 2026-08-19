"""Normalize Vercel/Supabase Postgres environment variables for BININGA.

The existing backend reads ``DATABASE_URL``. Vercel's Supabase integration
publishes Postgres URLs under ``POSTGRES_*`` names, so normalize one of those
server-side before importing ``server.py``. No secret values are stored here.
"""

import os


def apply() -> str:
    """Populate DATABASE_URL from a Vercel Postgres alias when needed.

    Prefer the pooled Prisma URL for serverless traffic, then the standard
    pooled URL, then the non-pooling URL. Existing DATABASE_URL always wins.
    Returns the environment-variable name selected, or an empty string.
    """
    if os.environ.get("DATABASE_URL"):
        return "DATABASE_URL"

    for name in ("POSTGRES_PRISMA_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING"):
        value = os.environ.get(name, "").strip()
        if value:
            os.environ["DATABASE_URL"] = value
            return name
    return ""
