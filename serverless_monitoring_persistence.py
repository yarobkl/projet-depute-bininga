"""Reliable monitoring writes and on-demand analysis for serverless BININGA.

The regular monitoring module batches writes in a daemon thread for low latency
on long-lived hosts. A Vercel invocation may be frozen before that thread gets
its 0.5 s flush window, so metrics can be lost. On serverless runtimes this
bridge writes each small monitoring event synchronously to the configured SQL
backend before the invocation returns.

Long-lived hosts also run a scheduler that periodically computes system status
and alert rules. Vercel does not keep such a scheduler alive, so this bridge
refreshes that analysis on demand (throttled per warm instance) when the admin
reads Monitoring.
"""
from __future__ import annotations

from datetime import datetime
import os
import time
from typing import Any


def _is_serverless() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def install(server: Any) -> None:
    if not _is_serverless():
        return
    mon = getattr(server, "_mon", None)
    if not mon or getattr(mon, "_bininga_serverless_sync_installed", False):
        return

    originals = {
        "request": getattr(mon, "record_request", None),
        "error": getattr(mon, "record_error", None),
        "visit": getattr(mon, "record_visit", None),
        "prog_view": getattr(mon, "record_prog_view", None),
        "summary": getattr(mon, "get_summary", None),
        "alerts": getattr(mon, "get_alerts", None),
    }

    try:
        mon.init_db()
    except Exception:
        pass

    def _write(item) -> bool:
        try:
            backend, _ = mon._db_config()
            if backend:
                conn, actual_backend = mon._sql_conn()
                if conn is None:
                    return False
                mon._execute_write(conn, actual_backend, item)
                return True

            # Local fallback remains useful for development-like serverless
            # previews without DATABASE_URL, even though /tmp is not durable.
            conn = mon.sqlite3.connect(mon.DB_FILE, timeout=5)
            try:
                mon._execute_write(conn, None, item)
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as exc:
            print(f"[MON] Écriture serverless directe ignorée: {type(exc).__name__}", flush=True)
            return False

    def record_request(method: str, path: str, status_code: int, duration_ms: float, ip: str = ""):
        item = ("request", method, path, status_code, duration_ms, ip, datetime.now())
        if not _write(item) and callable(originals["request"]):
            originals["request"](method, path, status_code, duration_ms, ip)

    def record_error(path: str, error_type: str, message: str, ip: str = ""):
        item = ("error", path, error_type, message, ip, datetime.now())
        if not _write(item) and callable(originals["error"]):
            originals["error"](path, error_type, message, ip)

    def record_visit(ip: str = "", page: str = "/"):
        item = ("visit", ip, page, datetime.now())
        if not _write(item) and callable(originals["visit"]):
            originals["visit"](ip, page)

    def record_prog_view(ip: str = ""):
        item = ("prog_view", ip, datetime.now())
        if not _write(item) and callable(originals["prog_view"]):
            originals["prog_view"](ip)

    last_analysis = {"at": 0.0, "sessions": 0, "blocked": 0}

    def _refresh_analysis(active_sessions: int = 0, blocked_ips: int = 0) -> None:
        now = time.monotonic()
        if now - last_analysis["at"] < 30:
            return
        last_analysis["at"] = now
        last_analysis["sessions"] = int(active_sessions or 0)
        last_analysis["blocked"] = int(blocked_ips or 0)
        try:
            mon.analyze_metrics(last_analysis["sessions"], last_analysis["blocked"])
        except Exception as exc:
            print(f"[MON] Analyse serverless à la demande ignorée: {type(exc).__name__}", flush=True)

    def get_summary(active_sessions: int = 0, blocked_ips: int = 0):
        _refresh_analysis(active_sessions, blocked_ips)
        if callable(originals["summary"]):
            return originals["summary"](active_sessions, blocked_ips)
        return {"global_status": "UNKNOWN", "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    def get_alerts(include_resolved: bool = False, limit: int = 100):
        # If alerts are requested before summary in a parallel admin refresh,
        # compute once with the latest known counters rather than returning a
        # perpetually empty list on a serverless runtime without scheduler.
        _refresh_analysis(last_analysis["sessions"], last_analysis["blocked"])
        if callable(originals["alerts"]):
            return originals["alerts"](include_resolved, limit)
        return []

    mon.record_request = record_request
    mon.record_error = record_error
    mon.record_visit = record_visit
    mon.record_prog_view = record_prog_view
    mon.get_summary = get_summary
    mon.get_alerts = get_alerts
    mon._bininga_serverless_sync_installed = True
