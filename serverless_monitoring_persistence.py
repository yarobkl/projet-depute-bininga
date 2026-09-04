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

Vercel's function filesystem is ephemeral and its statvfs usage is not an
operator-actionable "server disk" signal. The bridge therefore neutralizes the
legacy HIGH_DISK rule on Vercel, resolves old false HIGH_DISK alerts, and marks
the disk metric as non-actionable in summary responses.
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
        "disk_percent": getattr(mon, "_disk_percent", None),
    }

    # A Vercel function does not expose an operator-managed persistent disk.
    # Returning 0 here prevents analyze_metrics() from creating HIGH_DISK while
    # get_summary() below reports the metric as N/A instead of a fake 0%.
    if callable(originals["disk_percent"]):
        mon._disk_percent = lambda: 0.0

    def _write(item) -> bool:
        try:
            backend, _ = mon._db_config()
            if backend:
                # _sql_conn() initializes the persistent monitoring tables on
                # the first actual metric, not merely because a page loaded.
                conn, actual_backend = mon._sql_conn()
                if conn is None:
                    return False
                mon._execute_write(conn, actual_backend, item)
                return True

            # Development-like serverless preview without DATABASE_URL: only
            # initialize the local SQLite fallback when an event really occurs.
            try:
                mon.init_db()
            except Exception:
                pass
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

    def _cleanup_serverless_alerts() -> None:
        """Resolve Vercel-only disk false positives and duplicate active rules."""
        try:
            backend, _ = mon._db_config()
            if not backend:
                return
            conn, actual_backend = mon._sql_conn()
            if conn is None:
                return
            now = datetime.now()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE mon_alerts SET resolved=1, resolved_at=%s "
                    "WHERE rule=%s AND resolved=0",
                    (now, "HIGH_DISK"),
                )
                if actual_backend == "postgresql":
                    cur.execute(
                        """
                        WITH ranked AS (
                            SELECT id, ROW_NUMBER() OVER (
                                PARTITION BY rule ORDER BY ts DESC, id DESC
                            ) AS rn
                            FROM mon_alerts
                            WHERE resolved=0
                        )
                        UPDATE mon_alerts AS a
                        SET resolved=1, resolved_at=%s
                        FROM ranked AS r
                        WHERE a.id=r.id AND r.rn>1
                        """,
                        (now,),
                    )
                else:
                    # MySQL/MariaDB equivalent: keep only the newest active row
                    # for a rule. This is best-effort and deliberately isolated
                    # from the request if a specific engine rejects the join.
                    cur.execute(
                        """
                        UPDATE mon_alerts a
                        JOIN mon_alerts newer
                          ON newer.rule=a.rule
                         AND newer.resolved=0
                         AND a.resolved=0
                         AND (newer.ts>a.ts OR (newer.ts=a.ts AND newer.id>a.id))
                        SET a.resolved=1, a.resolved_at=%s
                        """,
                        (now,),
                    )
        except Exception as exc:
            print(f"[MON] Nettoyage alertes serverless ignoré: {type(exc).__name__}", flush=True)

    last_analysis = {"at": 0.0, "sessions": 0, "blocked": 0}

    def _refresh_analysis(active_sessions: int = 0, blocked_ips: int = 0) -> None:
        now = time.monotonic()
        if now - last_analysis["at"] < 30:
            return
        last_analysis["at"] = now
        last_analysis["sessions"] = int(active_sessions or 0)
        last_analysis["blocked"] = int(blocked_ips or 0)
        try:
            _cleanup_serverless_alerts()
            mon.analyze_metrics(last_analysis["sessions"], last_analysis["blocked"])
            _cleanup_serverless_alerts()
        except Exception as exc:
            print(f"[MON] Analyse serverless à la demande ignorée: {type(exc).__name__}", flush=True)

    def get_summary(active_sessions: int = 0, blocked_ips: int = 0):
        _refresh_analysis(active_sessions, blocked_ips)
        _cleanup_serverless_alerts()
        if callable(originals["summary"]):
            result = originals["summary"](active_sessions, blocked_ips)
            if isinstance(result, dict):
                result = dict(result)
                system = dict(result.get("system") or {})
                system["disk_percent"] = None
                system["disk_ephemeral"] = True
                system["disk_actionable"] = False
                system["disk_label"] = "N/A — stockage éphémère Vercel"
                result["system"] = system
            return result
        return {"global_status": "UNKNOWN", "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    def get_alerts(include_resolved: bool = False, limit: int = 100):
        _refresh_analysis(last_analysis["sessions"], last_analysis["blocked"])
        _cleanup_serverless_alerts()
        if callable(originals["alerts"]):
            rows = originals["alerts"](include_resolved, limit)
            if include_resolved or not isinstance(rows, list):
                return rows
            # Defensive response-level dedupe in case two different Vercel
            # instances raced before the SQL cleanup became visible.
            seen = set()
            out = []
            for row in rows:
                rule = row.get("rule") if isinstance(row, dict) else None
                key = rule or repr(row)
                if key in seen:
                    continue
                seen.add(key)
                out.append(row)
            return out
        return []

    mon.record_request = record_request
    mon.record_error = record_error
    mon.record_visit = record_visit
    mon.record_prog_view = record_prog_view
    mon.get_summary = get_summary
    mon.get_alerts = get_alerts
    mon._bininga_serverless_sync_installed = True
