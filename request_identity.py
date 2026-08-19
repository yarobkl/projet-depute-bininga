"""Resolve the real client IP for BININGA security controls.

Vercel Functions run behind a trusted edge proxy, so REMOTE_ADDR may be the
local function proxy instead of the visitor. Vercel overwrites X-Forwarded-For
for ordinary deployments to prevent client spoofing; use it only on Vercel and
validate the result before handing it to rate limiting / audit code.
"""

import ipaddress
import os


def client_ip(environ) -> str:
    remote = str(environ.get("REMOTE_ADDR") or "127.0.0.1").strip()
    candidate = remote

    if os.environ.get("VERCEL"):
        forwarded = str(environ.get("HTTP_X_FORWARDED_FOR") or "").strip()
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        try:
            return str(ipaddress.ip_address(remote))
        except ValueError:
            return "127.0.0.1"
