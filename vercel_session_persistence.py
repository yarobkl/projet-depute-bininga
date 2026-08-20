"""Keep admin sessions valid across Vercel serverless workers.

The legacy server keeps an in-memory ACTIVE_SESSIONS dict and also persists it
in PostgreSQL. On Vercel, a login request and the next authenticated request can
land on different warm workers. A worker that booted before the login therefore
has a stale in-memory dict and incorrectly returns 401 although the session is
present in PostgreSQL.

This compatibility layer keeps the fast in-memory path, but on a token miss it
reloads the authoritative persisted sessions from PostgreSQL before rejecting
the request. It does not change the legacy session format, TTL, CSRF logic or
logout semantics.
"""

from __future__ import annotations

import os
import threading
import time

_LOCK = threading.RLock()


def install(server) -> None:
    if not os.environ.get("VERCEL"):
        return
    if getattr(server, "_bininga_vercel_session_persistence", False):
        return

    original_get_session = server.get_session

    def get_session(token):
        if not token:
            return None

        session = original_get_session(token)
        if session is not None:
            return session

        # A different Vercel worker may have created the session after this
        # process booted. Reload only on a miss to avoid a DB read per request.
        with _LOCK:
            session = original_get_session(token)
            if session is not None:
                return session

            try:
                stored = server._pg_load("sessions")
            except Exception:
                stored = None

            if not isinstance(stored, dict):
                return None

            candidate = stored.get(token)
            if not isinstance(candidate, dict):
                return None

            ttl = candidate.get("ttl", server.SESSION_TTL)
            created_at = candidate.get("created_at", 0)
            try:
                expired = time.time() - float(created_at) > float(ttl)
            except (TypeError, ValueError):
                expired = True

            if expired:
                return None

            # Cache only the requested valid token locally. Persisted storage
            # remains authoritative and logout can still remove it normally.
            server.ACTIVE_SESSIONS[token] = candidate
            return candidate

    server.get_session = get_session
    server._bininga_vercel_session_persistence = True
    print("[SESSION] Persistance admin multi-worker Vercel activée.", flush=True)
