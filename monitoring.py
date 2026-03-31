"""
monitoring.py — Module de monitoring backend BININGA
=====================================================
Surveillance des performances, erreurs, alertes et métriques système.
stdlib uniquement — aucune dépendance externe.
Intégration non-bloquante : les écritures passent par une queue async.
"""
from __future__ import annotations
import sqlite3, threading, time, json, os, re, queue
from datetime import datetime, timedelta

# ── Configuration ──────────────────────────────────────────────────────────────
_BASE          = os.path.dirname(os.path.abspath(__file__))
DB_FILE        = os.path.join(_BASE, "monitoring.db")
RETENTION_DAYS = 7      # Purge auto des données > 7 jours
SCHEDULER_SEC  = 60     # Analyse toutes les 60 s

# Seuils d'alerte
THRESHOLDS = {
    "err_warn":  0.20,   # 20% erreurs/5min → WARNING
    "err_crit":  0.40,   # 40% erreurs/5min → CRITICAL
    "lat_warn":  2000,   # latence moy >2s → WARNING
    "lat_crit":  5000,   # latence moy >5s → CRITICAL
    "cpu_warn":  75,     # CPU >75% → WARNING
    "cpu_crit":  90,     # CPU >90% → CRITICAL
    "mem_warn":  80,     # RAM >80% → WARNING
    "mem_crit":  90,     # RAM >90% → CRITICAL
    "burst_min": 500,    # >500 req/min → WARNING
    "exc_warn":  3,      # 3+ exceptions/5min → WARNING
    "exc_crit":  10,     # 10+ exceptions/5min → CRITICAL
}

# ── Queue non-bloquante (writes async) ────────────────────────────────────────
_write_queue: queue.Queue = queue.Queue(maxsize=5000)
_writer_started = False
_writer_lock    = threading.Lock()


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Initialisation base de données ────────────────────────────────────────────
def init_db():
    """Crée les tables SQLite si elles n'existent pas encore."""
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            method      TEXT,
            path        TEXT,
            status_code INTEGER,
            duration_ms REAL,
            ip          TEXT
        );
        CREATE TABLE IF NOT EXISTS errors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            path        TEXT,
            error_type  TEXT,
            message     TEXT,
            ip          TEXT
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            level       TEXT,
            rule        TEXT,
            message     TEXT,
            resolved    INTEGER DEFAULT 0,
            resolved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS metrics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            metric_name TEXT,
            value       REAL,
            tags        TEXT
        );
        CREATE TABLE IF NOT EXISTS system_status (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              TEXT    NOT NULL,
            cpu_percent     REAL,
            memory_percent  REAL,
            disk_percent    REAL,
            uptime_seconds  INTEGER,
            active_sessions INTEGER,
            blocked_ips     INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_req_ts   ON requests(ts);
        CREATE INDEX IF NOT EXISTS idx_req_path ON requests(path);
        CREATE INDEX IF NOT EXISTS idx_err_ts   ON errors(ts);
        CREATE INDEX IF NOT EXISTS idx_alt_act  ON alerts(resolved, ts);
        CREATE INDEX IF NOT EXISTS idx_met_ts   ON metrics(metric_name, ts);
        CREATE INDEX IF NOT EXISTS idx_sys_ts   ON system_status(ts);
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Writer thread (async SQLite writes) ───────────────────────────────────────
def _writer_loop():
    """Consomme la queue et écrit dans SQLite par batch."""
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        return

    pending = []
    last_flush = time.time()

    while True:
        try:
            item = _write_queue.get(timeout=0.3)
            pending.append(item)
        except queue.Empty:
            pass

        if pending and (time.time() - last_flush > 0.5 or len(pending) >= 50):
            try:
                for item in pending:
                    _execute_write(conn, item)
                conn.commit()
            except Exception:
                try:
                    conn.close()
                    conn = sqlite3.connect(DB_FILE, timeout=10)
                    conn.execute("PRAGMA journal_mode=WAL")
                except Exception:
                    pass
            pending.clear()
            last_flush = time.time()


def _execute_write(conn, item):
    kind = item[0]
    if kind == "request":
        _, method, path, status, dur, ip, ts = item
        conn.execute(
            "INSERT INTO requests (ts,method,path,status_code,duration_ms,ip) VALUES (?,?,?,?,?,?)",
            (ts, method, path, status, round(dur, 2), ip)
        )
    elif kind == "error":
        _, path, etype, msg, ip, ts = item
        conn.execute(
            "INSERT INTO errors (ts,path,error_type,message,ip) VALUES (?,?,?,?,?)",
            (ts, path, str(etype)[:100], str(msg)[:500], ip)
        )


def _ensure_writer():
    global _writer_started
    with _writer_lock:
        if not _writer_started:
            _writer_started = True
            t = threading.Thread(target=_writer_loop, daemon=True, name="mon-writer")
            t.start()


# ── API publique d'enregistrement (non-bloquante) ─────────────────────────────
def record_request(method: str, path: str, status_code: int,
                   duration_ms: float, ip: str = ""):
    """Enregistre une requête HTTP. Non-bloquant."""
    try:
        _ensure_writer()
        _write_queue.put_nowait(("request", method, path, status_code, duration_ms, ip, _ts()))
    except queue.Full:
        pass
    except Exception:
        pass


def record_error(path: str, error_type: str, message: str, ip: str = ""):
    """Enregistre une exception non gérée. Non-bloquant."""
    try:
        _ensure_writer()
        _write_queue.put_nowait(("error", path, error_type, message, ip, _ts()))
    except queue.Full:
        pass
    except Exception:
        pass


# ── Métriques système (stdlib Linux / Railway) ────────────────────────────────
def _cpu_percent() -> float:
    try:
        def _read():
            with open("/proc/stat") as f:
                p = f.readline().split()
            v = list(map(int, p[1:]))
            return v[3], sum(v)
        i1, t1 = _read()
        time.sleep(0.15)
        i2, t2 = _read()
        dt = t2 - t1
        return round((1 - (i2 - i1) / dt) * 100, 1) if dt else 0.0
    except Exception:
        return 0.0


def _memory_percent() -> float:
    try:
        d = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                d[k.strip()] = int(re.sub(r"\D", "", v) or "0")
        total = d.get("MemTotal", 0)
        avail = d.get("MemAvailable", 0)
        return round((1 - avail / total) * 100, 1) if total else 0.0
    except Exception:
        return 0.0


def _disk_percent() -> float:
    try:
        st = os.statvfs(".")
        total = st.f_blocks * st.f_frsize
        free  = st.f_bavail * st.f_frsize
        return round((1 - free / total) * 100, 1) if total else 0.0
    except Exception:
        return 0.0


def _uptime_seconds() -> int:
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return 0


# ── Alertes ────────────────────────────────────────────────────────────────────
def _create_alert(conn, level: str, rule: str, message: str):
    """Crée une alerte si pas de doublon actif dans les 10 dernières minutes."""
    cutoff = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    exists = conn.execute(
        "SELECT id FROM alerts WHERE rule=? AND resolved=0 AND ts>?", (rule, cutoff)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO alerts (ts,level,rule,message) VALUES (?,?,?,?)",
            (_ts(), level, rule, message)
        )


def resolve_alert(alert_id: int):
    """Marque une alerte comme résolue."""
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "UPDATE alerts SET resolved=1, resolved_at=? WHERE id=?",
            (_ts(), int(alert_id))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Analyse par règles (rule-based engine) ────────────────────────────────────
def analyze_metrics(active_sessions: int = 0, blocked_ips: int = 0):
    """
    Analyse les métriques des 5 dernières minutes.
    Déclenche les alertes selon les règles définies dans THRESHOLDS.
    Collecte les métriques système.
    Lance le nettoyage des données anciennes.
    """
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        T   = THRESHOLDS
        now = datetime.now()
        c5m = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        c1m = (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")

        # ── Règle 1 : taux d'erreurs 5min ──────────────────────────────────────
        row = conn.execute(
            "SELECT COUNT(*) total, "
            "SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) errs "
            "FROM requests WHERE ts>?", (c5m,)
        ).fetchone()
        total, errs = (row["total"] or 0), (row["errs"] or 0)
        err_rate = errs / total if total >= 5 else 0

        if err_rate >= T["err_crit"]:
            _create_alert(conn, "CRITICAL", "HIGH_ERROR_RATE",
                f"Taux d'erreurs critique : {err_rate:.0%} ({errs}/{total} req/5min)")
        elif err_rate >= T["err_warn"]:
            _create_alert(conn, "WARNING", "HIGH_ERROR_RATE",
                f"Taux d'erreurs élevé : {err_rate:.0%} ({errs}/{total} req/5min)")

        # ── Règle 2 : latence moyenne 5min ────────────────────────────────────
        row = conn.execute(
            "SELECT AVG(duration_ms) avg FROM requests WHERE ts>?", (c5m,)
        ).fetchone()
        avg_ms = row["avg"] or 0

        if avg_ms >= T["lat_crit"]:
            _create_alert(conn, "CRITICAL", "HIGH_LATENCY",
                f"Latence critique : {avg_ms:.0f}ms (moy 5min)")
        elif avg_ms >= T["lat_warn"]:
            _create_alert(conn, "WARNING", "HIGH_LATENCY",
                f"Latence élevée : {avg_ms:.0f}ms (moy 5min)")

        # ── Règle 3 : burst de requêtes 1min ─────────────────────────────────
        cnt = conn.execute(
            "SELECT COUNT(*) n FROM requests WHERE ts>?", (c1m,)
        ).fetchone()["n"]
        if cnt > T["burst_min"]:
            _create_alert(conn, "WARNING", "REQUEST_BURST",
                f"Pic de trafic : {cnt} requêtes/min")

        # ── Règle 4 : exceptions non gérées 5min ──────────────────────────────
        exc = conn.execute(
            "SELECT COUNT(*) n FROM errors WHERE ts>?", (c5m,)
        ).fetchone()["n"]
        if exc >= T["exc_crit"]:
            _create_alert(conn, "CRITICAL", "ERROR_BURST",
                f"{exc} exceptions non gérées en 5 minutes")
        elif exc >= T["exc_warn"]:
            _create_alert(conn, "WARNING", "ERROR_BURST",
                f"{exc} exceptions non gérées en 5 minutes")

        # ── Métriques système ─────────────────────────────────────────────────
        cpu  = _cpu_percent()
        mem  = _memory_percent()
        disk = _disk_percent()
        up   = _uptime_seconds()

        conn.execute(
            "INSERT INTO system_status "
            "(ts,cpu_percent,memory_percent,disk_percent,uptime_seconds,active_sessions,blocked_ips) "
            "VALUES (?,?,?,?,?,?,?)",
            (_ts(), cpu, mem, disk, up, active_sessions, blocked_ips)
        )

        # ── Règle 5 : CPU ─────────────────────────────────────────────────────
        if cpu >= T["cpu_crit"]:
            _create_alert(conn, "CRITICAL", "HIGH_CPU", f"CPU critique : {cpu}%")
        elif cpu >= T["cpu_warn"]:
            _create_alert(conn, "WARNING", "HIGH_CPU", f"CPU élevé : {cpu}%")

        # ── Règle 6 : mémoire ─────────────────────────────────────────────────
        if mem >= T["mem_crit"]:
            _create_alert(conn, "CRITICAL", "HIGH_MEM", f"Mémoire critique : {mem}%")
        elif mem >= T["mem_warn"]:
            _create_alert(conn, "WARNING", "HIGH_MEM", f"Mémoire élevée : {mem}%")

        # ── Règle 7 : disque ──────────────────────────────────────────────────
        if disk >= 90:
            _create_alert(conn, "CRITICAL", "HIGH_DISK", f"Disque critique : {disk}%")

        # ── Stockage métriques agrégées ───────────────────────────────────────
        ts_now = _ts()
        for name, val, tags in [
            ("error_rate",    round(err_rate * 100, 2), '{"w":"5m"}'),
            ("avg_latency_ms", round(avg_ms, 2),         '{"w":"5m"}'),
            ("cpu",           cpu,                       None),
            ("memory",        mem,                       None),
            ("req_per_min",   float(cnt),                None),
        ]:
            conn.execute(
                "INSERT INTO metrics (ts,metric_name,value,tags) VALUES (?,?,?,?)",
                (ts_now, name, val, tags)
            )

        conn.commit()
        conn.close()

        # ── Nettoyage périodique ───────────────────────────────────────────────
        _cleanup()

    except Exception:
        pass


def _cleanup():
    try:
        cut   = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        cut30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_FILE, timeout=5) as conn:
            conn.execute("DELETE FROM requests WHERE ts<?", (cut,))
            conn.execute("DELETE FROM errors WHERE ts<?", (cut,))
            conn.execute("DELETE FROM metrics WHERE ts<?", (cut,))
            conn.execute("DELETE FROM system_status WHERE ts<?", (cut,))
            conn.execute("DELETE FROM alerts WHERE ts<? AND resolved=1", (cut30,))
    except Exception:
        pass


# ── Requêtes dashboard ────────────────────────────────────────────────────────
def get_summary(active_sessions: int = 0, blocked_ips: int = 0) -> dict:
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        now  = datetime.now()
        c24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        c5m  = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        c1h  = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

        req_24h = conn.execute(
            "SELECT COUNT(*) n FROM requests WHERE ts>?", (c24h,)
        ).fetchone()["n"]

        err_24h = conn.execute(
            "SELECT COUNT(*) n FROM errors WHERE ts>?", (c24h,)
        ).fetchone()["n"]

        avg_lat = round(conn.execute(
            "SELECT AVG(duration_ms) avg FROM requests WHERE ts>?", (c1h,)
        ).fetchone()["avg"] or 0, 1)

        row = conn.execute(
            "SELECT COUNT(*) t, SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) e "
            "FROM requests WHERE ts>?", (c5m,)
        ).fetchone()
        t5, e5 = row["t"] or 0, row["e"] or 0
        err_rate_5m = round(e5 / t5 * 100, 1) if t5 else 0

        alert_counts = {
            r["level"]: r["n"] for r in conn.execute(
                "SELECT level, COUNT(*) n FROM alerts WHERE resolved=0 GROUP BY level"
            ).fetchall()
        }

        top_row = conn.execute(
            "SELECT path, COUNT(*) n FROM requests WHERE ts>? "
            "GROUP BY path ORDER BY n DESC LIMIT 1", (c24h,)
        ).fetchone()
        top_ep = {"path": top_row["path"], "count": top_row["n"]} if top_row else {}

        sys_row = conn.execute(
            "SELECT * FROM system_status ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        sys_data = dict(sys_row) if sys_row else {}
        conn.close()

        crit   = alert_counts.get("CRITICAL", 0)
        warn   = alert_counts.get("WARNING", 0)
        status = "CRITICAL" if crit else ("WARNING" if warn or err_rate_5m > 10 else "OK")

        return {
            "global_status":  status,
            "requests_24h":   req_24h,
            "errors_24h":     err_24h,
            "avg_latency_ms": avg_lat,
            "error_rate_5m":  err_rate_5m,
            "alerts":         alert_counts,
            "top_endpoint":   top_ep,
            "system":         sys_data,
            "active_sessions": active_sessions,
            "blocked_ips":    blocked_ips,
            "ts":             _ts(),
        }
    except Exception as e:
        return {"global_status": "UNKNOWN", "error": str(e), "ts": _ts()}


def get_requests(limit: int = 100, path_filter: str = "") -> list:
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        if path_filter:
            rows = conn.execute(
                "SELECT * FROM requests WHERE path LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{path_filter}%", limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM requests ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_errors(limit: int = 50) -> list:
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM errors ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_alerts(include_resolved: bool = False, limit: int = 100) -> list:
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        if include_resolved:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE resolved=0 ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_top_endpoints(hours: int = 24, limit: int = 10) -> list:
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        cut = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute(
            "SELECT path, COUNT(*) count, AVG(duration_ms) avg_ms, "
            "SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) errors "
            "FROM requests WHERE ts>? GROUP BY path ORDER BY count DESC LIMIT ?",
            (cut, limit)
        ).fetchall()
        conn.close()
        return [
            {"path": r["path"], "count": r["count"],
             "avg_ms": round(r["avg_ms"] or 0, 1), "errors": r["errors"] or 0}
            for r in rows
        ]
    except Exception:
        return []


def get_latency_chart(hours: int = 6) -> list:
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        cut = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute(
            "SELECT strftime('%H:%M', ts) time, AVG(duration_ms) avg_ms, COUNT(*) cnt "
            "FROM requests WHERE ts>? "
            "GROUP BY strftime('%Y-%m-%d %H:%M', ts) ORDER BY ts LIMIT 60",
            (cut,)
        ).fetchall()
        conn.close()
        return [
            {"time": r["time"], "avg_ms": round(r["avg_ms"] or 0, 1), "count": r["cnt"]}
            for r in rows
        ]
    except Exception:
        return []


def generate_report() -> dict:
    """Génère un rapport actionnable sur les dernières 24h."""
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        now  = datetime.now()
        c24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        row = conn.execute(
            "SELECT COUNT(*) n, AVG(duration_ms) avg FROM requests WHERE ts>?", (c24h,)
        ).fetchone()
        req_total, avg_ms = row["n"] or 0, round(row["avg"] or 0, 1)

        err_total = conn.execute(
            "SELECT COUNT(*) n FROM requests WHERE ts>? AND status_code>=500", (c24h,)
        ).fetchone()["n"] or 0

        exc_total = conn.execute(
            "SELECT COUNT(*) n FROM errors WHERE ts>?", (c24h,)
        ).fetchone()["n"] or 0

        alerts = [dict(r) for r in conn.execute(
            "SELECT * FROM alerts WHERE resolved=0 ORDER BY ts DESC"
        ).fetchall()]

        slow = conn.execute(
            "SELECT path, AVG(duration_ms) avg FROM requests WHERE ts>? "
            "GROUP BY path HAVING avg>500 ORDER BY avg DESC LIMIT 5", (c24h,)
        ).fetchall()

        err_paths = conn.execute(
            "SELECT path, COUNT(*) n FROM requests WHERE ts>? AND status_code>=500 "
            "GROUP BY path ORDER BY n DESC LIMIT 5", (c24h,)
        ).fetchall()

        conn.close()

        err_rate  = err_total / req_total * 100 if req_total else 0
        crit_list = [a for a in alerts if a["level"] == "CRITICAL"]
        problems, recs = [], []

        if err_rate > 5:
            problems.append(f"Taux d'erreurs : {err_rate:.1f}% ({err_total}/{req_total})")
            recs.append("Vérifier les logs d'erreurs et les endpoints défaillants")
        if avg_ms > 1000:
            problems.append(f"Latence moyenne élevée : {avg_ms}ms")
            recs.append("Optimiser les endpoints lents ou augmenter les ressources")
        if exc_total > 5:
            problems.append(f"{exc_total} exceptions non gérées en 24h")
            recs.append("Analyser les exceptions dans les logs d'erreurs")
        if crit_list:
            problems.append(f"{len(crit_list)} alerte(s) critique(s) non résolue(s)")
            recs.append("Traiter immédiatement les alertes CRITICAL")

        return {
            "period":          "Dernières 24 heures",
            "generated_at":    _ts(),
            "requests_total":  req_total,
            "errors_total":    err_total,
            "error_rate":      round(err_rate, 1),
            "avg_latency_ms":  avg_ms,
            "exceptions":      exc_total,
            "active_alerts":   len(alerts),
            "critical_alerts": len(crit_list),
            "slow_endpoints":  [{"path": r["path"], "avg_ms": round(r["avg"], 1)} for r in slow],
            "error_endpoints": [{"path": r["path"], "count": r["n"]} for r in err_paths],
            "problems":        problems,
            "recommendations": recs,
            "status":          "CRITICAL" if crit_list else ("WARNING" if problems else "OK"),
        }
    except Exception as e:
        return {"error": str(e), "generated_at": _ts()}


# ── Scheduler (thread périodique) ────────────────────────────────────────────
_scheduler_thread = None


def start_scheduler(get_sessions_fn=None, get_blocked_fn=None):
    """Démarre le scheduler en background (idempotent)."""
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return

    def _run():
        init_db()
        _ensure_writer()
        while True:
            try:
                s = get_sessions_fn() if get_sessions_fn else 0
                b = get_blocked_fn()  if get_blocked_fn  else 0
                analyze_metrics(s, b)
            except Exception:
                pass
            time.sleep(SCHEDULER_SEC)

    _scheduler_thread = threading.Thread(
        target=_run, daemon=True, name="mon-scheduler"
    )
    _scheduler_thread.start()
