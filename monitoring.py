"""
monitoring.py — Module de monitoring backend BININGA
=====================================================
Surveillance des performances, erreurs, alertes et métriques système.
Utilise PostgreSQL/MySQL (DATABASE_URL, même base que les contacts) quand
disponible — indispensable sur Vercel où chaque instance serverless a son
propre disque éphémère et ne partage rien avec les autres : un SQLite local
n'y survit ni entre deux invocations, ni entre deux instances. À défaut,
retombe sur un fichier SQLite local (dev/local uniquement).
Intégration non-bloquante : les écritures passent par une queue async.
"""
from __future__ import annotations
import sqlite3, threading, time, json, os, re, queue
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote

# ── Configuration ──────────────────────────────────────────────────────────────
_BASE          = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR d'abord : sur Vercel le répertoire du code est en LECTURE SEULE —
# une base placée à côté du code ne peut jamais recevoir la moindre métrique.
_DATA_DIR      = os.environ.get("DATA_DIR", "").strip() or _BASE
DB_FILE        = os.path.join(_DATA_DIR, "monitoring.db")
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


# ══════════════════════════════════════════════════════════════════════════
# ██  COUCHE BASE DE DONNÉES — PostgreSQL/MySQL (même DATABASE_URL que le    ██
# ██  reste du site) avec repli SQLite local si aucune base n'est configurée ██
# ══════════════════════════════════════════════════════════════════════════
_sql_local = threading.local()  # connexion PG/MySQL par thread


def _db_config():
    """Retourne (backend, config) pour PostgreSQL ou MySQL, ou (None, {})."""
    raw_url = os.environ.get("DATABASE_URL", "").strip().strip("\n").strip("\r")
    if raw_url:
        if raw_url.startswith(("mysql://", "mariadb://")):
            return "mysql", {"url": raw_url}
        return "postgresql", {"url": raw_url.replace("postgres://", "postgresql://", 1)}

    mysql_db   = os.environ.get("MYSQL_DATABASE", "").strip()
    mysql_user = os.environ.get("MYSQL_USER", "").strip()
    mysql_pass = os.environ.get("MYSQL_PASSWORD", "").strip()
    if mysql_db and mysql_user:
        return "mysql", {
            "host": os.environ.get("MYSQL_HOST", "localhost").strip() or "localhost",
            "port": int(os.environ.get("MYSQL_PORT", "3306") or 3306),
            "user": mysql_user,
            "password": mysql_pass,
            "database": mysql_db,
        }
    return None, {}


_PG_TABLES = """
    CREATE TABLE IF NOT EXISTS mon_requests (
        id          SERIAL PRIMARY KEY,
        ts          TIMESTAMP NOT NULL,
        method      TEXT, path TEXT, status_code INTEGER, duration_ms REAL, ip TEXT
    );
    CREATE TABLE IF NOT EXISTS mon_errors (
        id          SERIAL PRIMARY KEY,
        ts          TIMESTAMP NOT NULL,
        path        TEXT, error_type TEXT, message TEXT, ip TEXT
    );
    CREATE TABLE IF NOT EXISTS mon_alerts (
        id          SERIAL PRIMARY KEY,
        ts          TIMESTAMP NOT NULL,
        level       TEXT, rule TEXT, message TEXT,
        resolved    INTEGER DEFAULT 0, resolved_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS mon_metrics (
        id          SERIAL PRIMARY KEY,
        ts          TIMESTAMP NOT NULL,
        metric_name TEXT, value REAL, tags TEXT
    );
    CREATE TABLE IF NOT EXISTS mon_system_status (
        id              SERIAL PRIMARY KEY,
        ts              TIMESTAMP NOT NULL,
        cpu_percent     REAL, memory_percent REAL, disk_percent REAL,
        uptime_seconds  INTEGER, active_sessions INTEGER, blocked_ips INTEGER
    );
    CREATE TABLE IF NOT EXISTS mon_visits (
        id          SERIAL PRIMARY KEY,
        ts          TIMESTAMP NOT NULL,
        ip          TEXT, page TEXT DEFAULT '/'
    );
    CREATE TABLE IF NOT EXISTS mon_prog_views (
        id          SERIAL PRIMARY KEY,
        ts          TIMESTAMP NOT NULL,
        ip          TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_mon_req_ts   ON mon_requests(ts);
    CREATE INDEX IF NOT EXISTS idx_mon_req_path ON mon_requests(path);
    CREATE INDEX IF NOT EXISTS idx_mon_err_ts   ON mon_errors(ts);
    CREATE INDEX IF NOT EXISTS idx_mon_alt_act  ON mon_alerts(resolved, ts);
    CREATE INDEX IF NOT EXISTS idx_mon_met_ts   ON mon_metrics(metric_name, ts);
    CREATE INDEX IF NOT EXISTS idx_mon_sys_ts   ON mon_system_status(ts);
    CREATE INDEX IF NOT EXISTS idx_mon_vis_ts   ON mon_visits(ts);
    CREATE INDEX IF NOT EXISTS idx_mon_prog_ts  ON mon_prog_views(ts);
"""

_MYSQL_TABLES = """
    CREATE TABLE IF NOT EXISTS mon_requests (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        ts          DATETIME NOT NULL,
        method      VARCHAR(16), path VARCHAR(500), status_code INT,
        duration_ms DOUBLE, ip VARCHAR(64),
        INDEX idx_mon_req_ts (ts), INDEX idx_mon_req_path (path(191))
    ) CHARACTER SET utf8mb4;
    CREATE TABLE IF NOT EXISTS mon_errors (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        ts          DATETIME NOT NULL,
        path        VARCHAR(500), error_type VARCHAR(100), message TEXT, ip VARCHAR(64),
        INDEX idx_mon_err_ts (ts)
    ) CHARACTER SET utf8mb4;
    CREATE TABLE IF NOT EXISTS mon_alerts (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        ts          DATETIME NOT NULL,
        level       VARCHAR(16), rule VARCHAR(64), message TEXT,
        resolved    TINYINT DEFAULT 0, resolved_at DATETIME,
        INDEX idx_mon_alt_act (resolved, ts)
    ) CHARACTER SET utf8mb4;
    CREATE TABLE IF NOT EXISTS mon_metrics (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        ts          DATETIME NOT NULL,
        metric_name VARCHAR(64), value DOUBLE, tags VARCHAR(255),
        INDEX idx_mon_met_ts (metric_name, ts)
    ) CHARACTER SET utf8mb4;
    CREATE TABLE IF NOT EXISTS mon_system_status (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        ts              DATETIME NOT NULL,
        cpu_percent     DOUBLE, memory_percent DOUBLE, disk_percent DOUBLE,
        uptime_seconds  INT, active_sessions INT, blocked_ips INT,
        INDEX idx_mon_sys_ts (ts)
    ) CHARACTER SET utf8mb4;
    CREATE TABLE IF NOT EXISTS mon_visits (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        ts          DATETIME NOT NULL,
        ip          VARCHAR(64), page VARCHAR(200) DEFAULT '/',
        INDEX idx_mon_vis_ts (ts)
    ) CHARACTER SET utf8mb4;
    CREATE TABLE IF NOT EXISTS mon_prog_views (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        ts          DATETIME NOT NULL,
        ip          VARCHAR(64),
        INDEX idx_mon_prog_ts (ts)
    ) CHARACTER SET utf8mb4;
"""


def _init_sql_tables(conn, backend: str):
    if backend == "postgresql":
        with conn.cursor() as cur:
            cur.execute(_PG_TABLES)
    else:
        with conn.cursor() as cur:
            for stmt in _MYSQL_TABLES.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)


def _sql_conn():
    """Retourne (conn, backend) — connexion PG/MySQL par thread, ou (None, None)."""
    backend, cfg = _db_config()
    if not backend:
        return None, None
    try:
        conn = getattr(_sql_local, "conn", None)
        conn_backend = getattr(_sql_local, "backend", None)
        is_closed = conn is None
        if conn is not None:
            if backend == "postgresql":
                is_closed = getattr(conn, "closed", 1) != 0
            else:
                try:
                    conn.ping(reconnect=False)
                    is_closed = False
                except Exception:
                    is_closed = True

        if is_closed or conn_backend != backend:
            if backend == "postgresql":
                import psycopg2
                conn = psycopg2.connect(cfg["url"], connect_timeout=5)
                conn.autocommit = True
            else:
                import pymysql
                if "url" in cfg:
                    parsed = urlparse(cfg["url"])
                    conn = pymysql.connect(
                        host=parsed.hostname or "localhost",
                        port=parsed.port or 3306,
                        user=unquote(parsed.username or ""),
                        password=unquote(parsed.password or ""),
                        database=(parsed.path or "").lstrip("/"),
                        charset="utf8mb4", autocommit=True, connect_timeout=5,
                    )
                else:
                    conn = pymysql.connect(
                        host=cfg["host"], port=cfg["port"], user=cfg["user"],
                        password=cfg["password"], database=cfg["database"],
                        charset="utf8mb4", autocommit=True, connect_timeout=5,
                    )
            _init_sql_tables(conn, backend)
            _sql_local.conn = conn
            _sql_local.backend = backend
        return conn, backend
    except Exception as e:
        print(f"[MON] Base indisponible ({backend}) : {e}")
        _sql_local.conn = None
        _sql_local.backend = None
        return None, None


def _minute_expr(backend: str) -> str:
    """Expression SQL groupant ts par minute, pour le graphe de latence."""
    return "to_char(ts,'HH24:MI')" if backend == "postgresql" else "DATE_FORMAT(ts,'%H:%i')"


def _minute_group_expr(backend: str) -> str:
    return "to_char(ts,'YYYY-MM-DD HH24:MI')" if backend == "postgresql" else "DATE_FORMAT(ts,'%Y-%m-%d %H:%i')"


# ── Initialisation base de données ────────────────────────────────────────────
def init_db():
    """Crée les tables (PG/MySQL si configuré, sinon SQLite local)."""
    backend, _ = _db_config()
    if backend:
        _sql_conn()
        return
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
        CREATE TABLE IF NOT EXISTS visits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            ip          TEXT,
            page        TEXT DEFAULT '/'
        );
        CREATE TABLE IF NOT EXISTS prog_views (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            ip          TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_req_ts   ON requests(ts);
        CREATE INDEX IF NOT EXISTS idx_req_path ON requests(path);
        CREATE INDEX IF NOT EXISTS idx_err_ts   ON errors(ts);
        CREATE INDEX IF NOT EXISTS idx_alt_act  ON alerts(resolved, ts);
        CREATE INDEX IF NOT EXISTS idx_met_ts   ON metrics(metric_name, ts);
        CREATE INDEX IF NOT EXISTS idx_sys_ts   ON system_status(ts);
        CREATE INDEX IF NOT EXISTS idx_vis_ts   ON visits(ts);
        CREATE INDEX IF NOT EXISTS idx_prog_ts  ON prog_views(ts);
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Writer thread (async writes) ──────────────────────────────────────────────
def _writer_loop():
    """Consomme la queue et écrit par batch (PG/MySQL si configuré, sinon SQLite)."""
    backend, _ = _db_config()
    conn = None
    if backend:
        conn, backend = _sql_conn()
        if conn is None:
            return
    else:
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
                    _execute_write(conn, backend, item)
                if backend is None:
                    conn.commit()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    if backend:
                        conn, backend = _sql_conn()
                    else:
                        conn = sqlite3.connect(DB_FILE, timeout=10)
                        conn.execute("PRAGMA journal_mode=WAL")
                except Exception:
                    pass
            pending.clear()
            last_flush = time.time()


def _execute_write(conn, backend, item):
    kind = item[0]
    ts = item[-1]
    if backend is not None:
        ts_val = ts  # objet datetime natif — PG/MySQL l'adaptent directement
        ph = "%s"
        prefix = "mon_"
        cur = conn.cursor()
        _run = cur.execute
    else:
        ts_val = ts.strftime("%Y-%m-%d %H:%M:%S")
        ph = "?"
        prefix = ""
        _run = conn.execute

    if kind == "request":
        _, method, path, status, dur, ip, _ts_ = item
        _run(f"INSERT INTO {prefix}requests (ts,method,path,status_code,duration_ms,ip) "
             f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
             (ts_val, method, path, status, round(dur, 2), ip))
    elif kind == "error":
        _, path, etype, msg, ip, _ts_ = item
        _run(f"INSERT INTO {prefix}errors (ts,path,error_type,message,ip) "
             f"VALUES ({ph},{ph},{ph},{ph},{ph})",
             (ts_val, path, str(etype)[:100], str(msg)[:500], ip))
    elif kind == "visit":
        _, ip, page, _ts_ = item
        _run(f"INSERT INTO {prefix}visits (ts,ip,page) VALUES ({ph},{ph},{ph})",
             (ts_val, ip, page[:200]))
    elif kind == "prog_view":
        _, ip, _ts_ = item
        _run(f"INSERT INTO {prefix}prog_views (ts,ip) VALUES ({ph},{ph})",
             (ts_val, ip))


def _ensure_writer():
    global _writer_started
    with _writer_lock:
        if not _writer_started:
            _writer_started = True
            # Serverless : personne n'appelle init_db() au boot (les services
            # de fond sont opt-in) — garantir les tables avant toute écriture.
            init_db()
            t = threading.Thread(target=_writer_loop, daemon=True, name="mon-writer")
            t.start()


# ── API publique d'enregistrement (non-bloquante) ─────────────────────────────
def record_request(method: str, path: str, status_code: int,
                   duration_ms: float, ip: str = ""):
    """Enregistre une requête HTTP. Non-bloquant."""
    try:
        _ensure_writer()
        _write_queue.put_nowait(("request", method, path, status_code, duration_ms, ip, datetime.now()))
    except queue.Full:
        pass
    except Exception:
        pass


def record_error(path: str, error_type: str, message: str, ip: str = ""):
    """Enregistre une exception non gérée. Non-bloquant."""
    try:
        _ensure_writer()
        _write_queue.put_nowait(("error", path, error_type, message, ip, datetime.now()))
    except queue.Full:
        pass
    except Exception:
        pass


def record_visit(ip: str = "", page: str = "/"):
    """Enregistre une visite du site public. Non-bloquant."""
    try:
        _ensure_writer()
        _write_queue.put_nowait(("visit", ip, page, datetime.now()))
    except queue.Full:
        pass
    except Exception:
        pass


def record_prog_view(ip: str = ""):
    """Enregistre une lecture du programme. Non-bloquant."""
    try:
        _ensure_writer()
        _write_queue.put_nowait(("prog_view", ip, datetime.now()))
    except queue.Full:
        pass
    except Exception:
        pass


def get_visit_stats() -> dict:
    """Retourne les compteurs de visites depuis la DB."""
    backend, _ = _db_config()
    if backend:
        conn, backend = _sql_conn()
        if not conn:
            return {"total": 0, "today": 0, "prog_views": 0}
        try:
            cutoff_24h = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM mon_visits")
                total = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM mon_visits WHERE ts >= %s", (cutoff_24h,))
                today = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM mon_prog_views")
                prog = cur.fetchone()[0]
            return {"total": total, "today": today, "prog_views": prog}
        except Exception:
            return {"total": 0, "today": 0, "prog_views": 0}
    try:
        conn = sqlite3.connect(DB_FILE, timeout=5)
        conn.row_factory = sqlite3.Row
        cutoff_24h = datetime.utcnow().strftime("%Y-%m-%d") + " 00:00:00"
        total    = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        today    = conn.execute("SELECT COUNT(*) FROM visits WHERE ts >= ?", (cutoff_24h,)).fetchone()[0]
        prog     = conn.execute("SELECT COUNT(*) FROM prog_views").fetchone()[0]
        conn.close()
        return {"total": total, "today": today, "prog_views": prog}
    except Exception:
        return {"total": 0, "today": 0, "prog_views": 0}


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
def _create_alert_sql(conn, level: str, rule: str, message: str):
    """Crée une alerte si pas de doublon actif dans les 10 dernières minutes (PG/MySQL)."""
    cutoff = datetime.now() - timedelta(minutes=10)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM mon_alerts WHERE rule=%s AND resolved=0 AND ts>%s", (rule, cutoff)
        )
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO mon_alerts (ts,level,rule,message) VALUES (%s,%s,%s,%s)",
                (datetime.now(), level, rule, message)
            )


def _create_alert(conn, level: str, rule: str, message: str):
    """Crée une alerte si pas de doublon actif dans les 10 dernières minutes (SQLite)."""
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
    backend, _ = _db_config()
    if backend:
        conn, backend = _sql_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE mon_alerts SET resolved=1, resolved_at=%s WHERE id=%s",
                    (datetime.now(), int(alert_id))
                )
        except Exception:
            pass
        return
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
    backend, _ = _db_config()
    if backend:
        _analyze_metrics_sql(active_sessions, blocked_ips)
    else:
        _analyze_metrics_sqlite(active_sessions, blocked_ips)


def _analyze_metrics_sql(active_sessions: int, blocked_ips: int):
    try:
        conn, backend = _sql_conn()
        if not conn:
            return
        T   = THRESHOLDS
        now = datetime.now()
        c5m = now - timedelta(minutes=5)
        c1m = now - timedelta(minutes=1)

        with conn.cursor() as cur:
            # ── Règle 1 : taux d'erreurs 5min ──────────────────────────────
            cur.execute(
                "SELECT COUNT(*) total, "
                "SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) errs "
                "FROM mon_requests WHERE ts>%s", (c5m,)
            )
            total, errs = cur.fetchone()
            total, errs = (total or 0), (errs or 0)
            err_rate = errs / total if total >= 5 else 0

            if err_rate >= T["err_crit"]:
                _create_alert_sql(conn, "CRITICAL", "HIGH_ERROR_RATE",
                    f"Taux d'erreurs critique : {err_rate:.0%} ({errs}/{total} req/5min)")
            elif err_rate >= T["err_warn"]:
                _create_alert_sql(conn, "WARNING", "HIGH_ERROR_RATE",
                    f"Taux d'erreurs élevé : {err_rate:.0%} ({errs}/{total} req/5min)")

            # ── Règle 2 : latence moyenne 5min ─────────────────────────────
            cur.execute("SELECT AVG(duration_ms) FROM mon_requests WHERE ts>%s", (c5m,))
            avg_ms = cur.fetchone()[0] or 0

            if avg_ms >= T["lat_crit"]:
                _create_alert_sql(conn, "CRITICAL", "HIGH_LATENCY",
                    f"Latence critique : {avg_ms:.0f}ms (moy 5min)")
            elif avg_ms >= T["lat_warn"]:
                _create_alert_sql(conn, "WARNING", "HIGH_LATENCY",
                    f"Latence élevée : {avg_ms:.0f}ms (moy 5min)")

            # ── Règle 3 : burst de requêtes 1min ───────────────────────────
            cur.execute("SELECT COUNT(*) FROM mon_requests WHERE ts>%s", (c1m,))
            cnt = cur.fetchone()[0]
            if cnt > T["burst_min"]:
                _create_alert_sql(conn, "WARNING", "REQUEST_BURST",
                    f"Pic de trafic : {cnt} requêtes/min")

            # ── Règle 4 : exceptions non gérées 5min ───────────────────────
            cur.execute("SELECT COUNT(*) FROM mon_errors WHERE ts>%s", (c5m,))
            exc = cur.fetchone()[0]
            if exc >= T["exc_crit"]:
                _create_alert_sql(conn, "CRITICAL", "ERROR_BURST",
                    f"{exc} exceptions non gérées en 5 minutes")
            elif exc >= T["exc_warn"]:
                _create_alert_sql(conn, "WARNING", "ERROR_BURST",
                    f"{exc} exceptions non gérées en 5 minutes")

            # ── Métriques système ───────────────────────────────────────────
            cpu  = _cpu_percent()
            mem  = _memory_percent()
            disk = _disk_percent()
            up   = _uptime_seconds()

            cur.execute(
                "INSERT INTO mon_system_status "
                "(ts,cpu_percent,memory_percent,disk_percent,uptime_seconds,active_sessions,blocked_ips) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (datetime.now(), cpu, mem, disk, up, active_sessions, blocked_ips)
            )

            # ── Règle 5 : CPU ────────────────────────────────────────────────
            if cpu >= T["cpu_crit"]:
                _create_alert_sql(conn, "CRITICAL", "HIGH_CPU", f"CPU critique : {cpu}%")
            elif cpu >= T["cpu_warn"]:
                _create_alert_sql(conn, "WARNING", "HIGH_CPU", f"CPU élevé : {cpu}%")

            # ── Règle 6 : mémoire ────────────────────────────────────────────
            if mem >= T["mem_crit"]:
                _create_alert_sql(conn, "CRITICAL", "HIGH_MEM", f"Mémoire critique : {mem}%")
            elif mem >= T["mem_warn"]:
                _create_alert_sql(conn, "WARNING", "HIGH_MEM", f"Mémoire élevée : {mem}%")

            # ── Règle 7 : disque ─────────────────────────────────────────────
            if disk >= 90:
                _create_alert_sql(conn, "CRITICAL", "HIGH_DISK", f"Disque critique : {disk}%")

            # ── Stockage métriques agrégées ──────────────────────────────────
            ts_now = datetime.now()
            for name, val, tags in [
                ("error_rate",    round(err_rate * 100, 2), '{"w":"5m"}'),
                ("avg_latency_ms", round(avg_ms, 2),         '{"w":"5m"}'),
                ("cpu",           cpu,                       None),
                ("memory",        mem,                       None),
                ("req_per_min",   float(cnt),                None),
            ]:
                cur.execute(
                    "INSERT INTO mon_metrics (ts,metric_name,value,tags) VALUES (%s,%s,%s,%s)",
                    (ts_now, name, val, tags)
                )

        _cleanup_sql()

    except Exception:
        pass


def _analyze_metrics_sqlite(active_sessions: int, blocked_ips: int):
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


def _cleanup_sql():
    try:
        conn, backend = _sql_conn()
        if not conn:
            return
        cut   = datetime.now() - timedelta(days=RETENTION_DAYS)
        cut30 = datetime.now() - timedelta(days=30)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mon_requests WHERE ts<%s", (cut,))
            cur.execute("DELETE FROM mon_errors WHERE ts<%s", (cut,))
            cur.execute("DELETE FROM mon_metrics WHERE ts<%s", (cut,))
            cur.execute("DELETE FROM mon_system_status WHERE ts<%s", (cut,))
            cur.execute("DELETE FROM mon_alerts WHERE ts<%s AND resolved=1", (cut30,))
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
    backend, _ = _db_config()
    if backend:
        return _get_summary_sql(active_sessions, blocked_ips)
    return _get_summary_sqlite(active_sessions, blocked_ips)


def _get_summary_sql(active_sessions: int, blocked_ips: int) -> dict:
    try:
        conn, backend = _sql_conn()
        if not conn:
            return {"global_status": "UNKNOWN", "error": "db indisponible", "ts": _ts()}
        now  = datetime.now()
        c24h = now - timedelta(hours=24)
        c5m  = now - timedelta(minutes=5)
        c1h  = now - timedelta(hours=1)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mon_requests WHERE ts>%s", (c24h,))
            req_24h = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM mon_errors WHERE ts>%s", (c24h,))
            err_24h = cur.fetchone()[0]

            cur.execute("SELECT AVG(duration_ms) FROM mon_requests WHERE ts>%s", (c1h,))
            avg_lat = round(cur.fetchone()[0] or 0, 1)

            cur.execute(
                "SELECT COUNT(*) t, SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) e "
                "FROM mon_requests WHERE ts>%s", (c5m,)
            )
            t5, e5 = cur.fetchone()
            t5, e5 = t5 or 0, e5 or 0
            err_rate_5m = round(e5 / t5 * 100, 1) if t5 else 0

            cur.execute("SELECT level, COUNT(*) n FROM mon_alerts WHERE resolved=0 GROUP BY level")
            alert_counts = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute(
                "SELECT path, COUNT(*) n FROM mon_requests WHERE ts>%s "
                "GROUP BY path ORDER BY n DESC LIMIT 1", (c24h,)
            )
            top_row = cur.fetchone()
            top_ep = {"path": top_row[0], "count": top_row[1]} if top_row else {}

            cur.execute("SELECT cpu_percent,memory_percent,disk_percent,uptime_seconds,active_sessions,blocked_ips,ts "
                        "FROM mon_system_status ORDER BY ts DESC LIMIT 1")
            sys_row = cur.fetchone()
            sys_data = {}
            if sys_row:
                sys_data = {
                    "cpu_percent": sys_row[0], "memory_percent": sys_row[1], "disk_percent": sys_row[2],
                    "uptime_seconds": sys_row[3], "active_sessions": sys_row[4], "blocked_ips": sys_row[5],
                    "ts": str(sys_row[6]),
                }

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


def _get_summary_sqlite(active_sessions: int, blocked_ips: int) -> dict:
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
    backend, _ = _db_config()
    if backend:
        try:
            conn, backend = _sql_conn()
            if not conn:
                return []
            with conn.cursor() as cur:
                if path_filter:
                    cur.execute(
                        "SELECT id,ts,method,path,status_code,duration_ms,ip FROM mon_requests "
                        "WHERE path LIKE %s ORDER BY ts DESC LIMIT %s",
                        (f"%{path_filter}%", limit)
                    )
                else:
                    cur.execute(
                        "SELECT id,ts,method,path,status_code,duration_ms,ip FROM mon_requests "
                        "ORDER BY ts DESC LIMIT %s", (limit,)
                    )
                cols = ["id", "ts", "method", "path", "status_code", "duration_ms", "ip"]
                return [dict(zip(cols, (r[0], str(r[1]), *r[2:]))) for r in cur.fetchall()]
        except Exception:
            return []
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
    backend, _ = _db_config()
    if backend:
        try:
            conn, backend = _sql_conn()
            if not conn:
                return []
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id,ts,path,error_type,message,ip FROM mon_errors ORDER BY ts DESC LIMIT %s",
                    (limit,)
                )
                cols = ["id", "ts", "path", "error_type", "message", "ip"]
                return [dict(zip(cols, (r[0], str(r[1]), *r[2:]))) for r in cur.fetchall()]
        except Exception:
            return []
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
    backend, _ = _db_config()
    if backend:
        try:
            conn, backend = _sql_conn()
            if not conn:
                return []
            with conn.cursor() as cur:
                cols = ["id", "ts", "level", "rule", "message", "resolved", "resolved_at"]
                if include_resolved:
                    cur.execute(
                        "SELECT id,ts,level,rule,message,resolved,resolved_at FROM mon_alerts "
                        "ORDER BY ts DESC LIMIT %s", (limit,)
                    )
                else:
                    cur.execute(
                        "SELECT id,ts,level,rule,message,resolved,resolved_at FROM mon_alerts "
                        "WHERE resolved=0 ORDER BY ts DESC LIMIT %s", (limit,)
                    )
                out = []
                for r in cur.fetchall():
                    d = dict(zip(cols, r))
                    d["ts"] = str(d["ts"])
                    d["resolved_at"] = str(d["resolved_at"]) if d["resolved_at"] else None
                    out.append(d)
                return out
        except Exception:
            return []
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
    backend, _ = _db_config()
    if backend:
        try:
            conn, backend = _sql_conn()
            if not conn:
                return []
            cut = datetime.now() - timedelta(hours=hours)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT path, COUNT(*) count, AVG(duration_ms) avg_ms, "
                    "SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END) errors "
                    "FROM mon_requests WHERE ts>%s GROUP BY path ORDER BY count DESC LIMIT %s",
                    (cut, limit)
                )
                return [
                    {"path": r[0], "count": r[1], "avg_ms": round(r[2] or 0, 1), "errors": r[3] or 0}
                    for r in cur.fetchall()
                ]
        except Exception:
            return []
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
    backend, _ = _db_config()
    if backend:
        try:
            conn, backend = _sql_conn()
            if not conn:
                return []
            cut = datetime.now() - timedelta(hours=hours)
            time_expr = _minute_expr(backend)
            group_expr = _minute_group_expr(backend)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {time_expr} time, AVG(duration_ms) avg_ms, COUNT(*) cnt "
                    f"FROM mon_requests WHERE ts>%s "
                    f"GROUP BY {group_expr}, {time_expr} ORDER BY MIN(ts) LIMIT 60",
                    (cut,)
                )
                return [
                    {"time": r[0], "avg_ms": round(r[1] or 0, 1), "count": r[2]}
                    for r in cur.fetchall()
                ]
        except Exception:
            return []
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
    backend, _ = _db_config()
    if backend:
        return _generate_report_sql()
    return _generate_report_sqlite()


def _generate_report_sql() -> dict:
    try:
        conn, backend = _sql_conn()
        if not conn:
            return {"error": "db indisponible", "generated_at": _ts()}
        now  = datetime.now()
        c24h = now - timedelta(hours=24)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) n, AVG(duration_ms) avg FROM mon_requests WHERE ts>%s", (c24h,))
            req_total, avg_ms = cur.fetchone()
            req_total, avg_ms = req_total or 0, round(avg_ms or 0, 1)

            cur.execute("SELECT COUNT(*) FROM mon_requests WHERE ts>%s AND status_code>=500", (c24h,))
            err_total = cur.fetchone()[0] or 0

            cur.execute("SELECT COUNT(*) FROM mon_errors WHERE ts>%s", (c24h,))
            exc_total = cur.fetchone()[0] or 0

            cur.execute("SELECT id,ts,level,rule,message,resolved,resolved_at FROM mon_alerts WHERE resolved=0 ORDER BY ts DESC")
            acols = ["id", "ts", "level", "rule", "message", "resolved", "resolved_at"]
            alerts = [dict(zip(acols, r)) for r in cur.fetchall()]
            for a in alerts:
                a["ts"] = str(a["ts"])

            cur.execute(
                "SELECT path, AVG(duration_ms) avg FROM mon_requests WHERE ts>%s "
                "GROUP BY path HAVING AVG(duration_ms)>500 ORDER BY avg DESC LIMIT 5", (c24h,)
            )
            slow = cur.fetchall()

            cur.execute(
                "SELECT path, COUNT(*) n FROM mon_requests WHERE ts>%s AND status_code>=500 "
                "GROUP BY path ORDER BY n DESC LIMIT 5", (c24h,)
            )
            err_paths = cur.fetchall()

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
            "slow_endpoints":  [{"path": r[0], "avg_ms": round(r[1], 1)} for r in slow],
            "error_endpoints": [{"path": r[0], "count": r[1]} for r in err_paths],
            "problems":        problems,
            "recommendations": recs,
            "status":          "CRITICAL" if crit_list else ("WARNING" if problems else "OK"),
        }
    except Exception as e:
        return {"error": str(e), "generated_at": _ts()}


def _generate_report_sqlite() -> dict:
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
