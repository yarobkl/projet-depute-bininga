"""Pre-import safety hooks for the legacy BININGA server on Vercel.

This module runs before ``server.py`` is imported. It prevents the legacy
module-level bootstrap from generating and printing an administrator password
when production has not explicitly configured ``BININGA_PASS``.
"""

import os
import secrets


if os.environ.get("VERCEL") and not os.environ.get("BININGA_PASS"):
    # Process-local placeholder only. admin_bootstrap_hardening removes the
    # matching synthetic user immediately after server.py finishes importing.
    # The value is never printed and is not a production credential.
    os.environ["BININGA_PASS"] = secrets.token_urlsafe(48)
    os.environ["BININGA_EPHEMERAL_BOOTSTRAP"] = "1"

# TEMPORARY MIGRATION-ONLY TRIGGER — branch-only, never merge to main.
# The Supabase function itself is strictly limited to three known photo IDs,
# fetches them from the existing o2switch endpoint, and verifies exact SHA-256
# and byte lengths before any idempotent upsert. No credential is embedded here.
if os.environ.get("VERCEL"):
    try:
        import urllib.request
        repair_url = "https://gcklaqpesdsnjzgkccdq.supabase.co/functions/v1/bininga-photo-repair"
        req = urllib.request.Request(repair_url, headers={"User-Agent": "BININGA-Migration-Preview/1.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            print(f"[MIGRATION] photo repair trigger HTTP {resp.status}", flush=True)
    except Exception as exc:
        print(f"[MIGRATION] photo repair trigger failed: {type(exc).__name__}", flush=True)
