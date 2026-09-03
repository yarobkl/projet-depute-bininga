"""Add production DB health endpoint and recovery guard to request pipeline."""
from __future__ import annotations

import db_resilience

HEALTH_PATH = "/api/health"


def guard_request(server, handler):
    path = str(getattr(handler, "path", "")).split("?", 1)[0]
    method = str(getattr(handler, "command", "GET")).upper()
    if method == "GET" and path == HEALTH_PATH:
        status = db_resilience.public_status(server)
        handler._json(status, 200 if status.get("ok") else 503)
        return False
    return True
