import http.server
import json
import os
import io
import ssl
import secrets
import hashlib
import time
import threading
import posixpath
import re
import gzip
from email.parser import BytesParser
from email.policy import default as email_policy_default
from urllib.parse import urlparse, unquote
from datetime import datetime

# ── Configuration ──────────────────────────────────────────
DATA_FILE       = "data.json"
AUDIT_FILE      = "audit.log"
USERS_FILE      = "users.json"
SESSIONS_FILE   = "sessions.json"
BININGA_TEST    = os.environ.get("BININGA_TEST", "") == "1"  # Mode test uniquement
ADMIN_USER      = os.environ.get("BININGA_USER", "admin")
ADMIN_PASS      = os.environ.get("BININGA_PASS", "")
PROTECTED_USER  = os.environ.get("BININGA_PROTECTED", "rodrin")

# Origines autorisées pour CORS
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "BININGA_ORIGINS",
    "https://bininga.cg,https://www.bininga.cg,"
    "http://localhost:8080,https://localhost:8443,http://127.0.0.1:8080"
).split(",") if o.strip()]
BASE_DIR        = os.path.realpath(os.getcwd())

# Sessions actives : token → {username, role, nom, created_at, csrf_token}
ACTIVE_SESSIONS = {}
SESSION_TTL     = 86400  # 24 heures

# Fichier de contact
CONTACT_FILE = "contacts.json"

# Fichier de veille IA
NEWS_FILE = "news_monitor.json"

# Rate limiting : ip → {count, blocked_until}
LOGIN_ATTEMPTS  = {}
MAX_ATTEMPTS    = 5
LOCKOUT_SECONDS = 1800  # 30 minutes

# Rotation des logs
MAX_LOG_SIZE     = 500 * 1024   # 500 Ko
MAX_LOG_ARCHIVES = 5

# ── Sécurité — mots de passe ────────────────────────────────
def _hash_new(password: str) -> str:
    """Hash pbkdf2-sha256 avec sel aléatoire (format: pbkdf2:sha256:<salt>:<hash>)."""
    salt = secrets.token_hex(16)
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 260_000)
    return f"pbkdf2:sha256:{salt}:{dk.hex()}"

def _verify_password(password: str, stored: str) -> bool:
    """Vérifie le mot de passe — supporte pbkdf2 (nouveau) et sha256 (legacy)."""
    if stored.startswith("pbkdf2:sha256:"):
        parts = stored.split(":")
        if len(parts) != 4:
            return False
        _, _, salt, dk_stored = parts
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 260_000)
        return secrets.compare_digest(dk.hex(), dk_stored)
    # Legacy SHA-256 sans sel — accepté jusqu'au prochain changement de mot de passe
    return secrets.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored)

# ── Sécurité — path traversal ──────────────────────────────
# Fichiers serveur à ne jamais servir comme statiques
BLOCKED_STATIC = {
    "users.json", "sessions.json", "audit.log",
    "contacts.json", "server.py", "cert.pem", "key.pem",
}
# Extensions autorisées pour les fichiers statiques
ALLOWED_STATIC_EXT = {".html", ".css", ".js", ".png", ".jpg", ".jpeg",
                      ".gif", ".webp", ".svg", ".ico", ".xml", ".txt", ".mp4", ".webm"}

def _safe_path(relative: str):
    """Retourne le chemin absolu seulement s'il reste dans BASE_DIR
    et ne correspond pas à un fichier sensible, sinon None."""
    # Normaliser d'abord le chemin pour éliminer les séquences ../
    normalized = posixpath.normpath("/" + relative).lstrip("/")
    filename = os.path.basename(normalized)

    # Bloquer les fichiers sensibles
    if filename in BLOCKED_STATIC:
        return None

    # Bloquer les extensions non autorisées (sauf data.json accessible via /api/load)
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in ALLOWED_STATIC_EXT:
        return None

    resolved = os.path.realpath(os.path.join(BASE_DIR, normalized))
    if resolved == BASE_DIR or resolved.startswith(BASE_DIR + os.sep):
        return resolved
    return None

# ── Sécurité — rate limiting ───────────────────────────────
def _is_rate_limited(ip: str) -> bool:
    record = LOGIN_ATTEMPTS.get(ip)
    if not record:
        return False
    return record.get("blocked_until", 0) > time.time()

def _record_failed_login(ip: str):
    record = LOGIN_ATTEMPTS.get(ip, {"count": 0, "blocked_until": 0})
    record["count"] = record.get("count", 0) + 1
    if record["count"] >= MAX_ATTEMPTS:
        record["blocked_until"] = time.time() + LOCKOUT_SECONDS
        record["count"] = 0
        audit_log("BRUTE_FORCE", ip, f"IP bloquée {LOCKOUT_SECONDS}s après {MAX_ATTEMPTS} échecs")
    LOGIN_ATTEMPTS[ip] = record

def _reset_login_attempts(ip: str):
    LOGIN_ATTEMPTS.pop(ip, None)

# ══════════════════════════════════════════════════════════
# ██  MODULE ANTI-INTRUSION — BININGA SECURITY ENGINE     ██
# ══════════════════════════════════════════════════════════

BLOCKED_IPS_FILE  = "blocked_ips.json"
ATTACK_LOG_FILE   = "attacks.log"
USE_SSL           = False   # mis à jour dans __main__

# ── IPs définitivement bannies ─────────────────────────────
BLOCKED_IPS: set = set()

# ── Scores d'attaque cumulatifs par IP ─────────────────────
# ip → {"score": int, "events": [{"ts","type","detail"}]}
ATTACK_SCORES: dict = {}
ATTACK_BAN_THRESHOLD  = 25   # score → bannissement auto
ATTACK_WARN_THRESHOLD = 10   # score → tarpit

# ── Rate limiting global (toutes routes) ───────────────────
REQUEST_COUNTS: dict = {}    # ip → {"n": int, "t": float}
GLOBAL_RATE_LIMIT = 150      # requêtes / 60 s / IP

# ── Délai sur échec login (ralentit brute-force + timing) ──
LOGIN_FAIL_DELAY = 0.4       # secondes

# ── Tarpit ─────────────────────────────────────────────────
TARPIT_TABLE = {10: 1.0, 15: 2.5, 20: 5.0}  # score → délai (s)

# ── Chemins pièges (honeypots) ─────────────────────────────
HONEYPOT_PATHS = frozenset({
    "/wp-admin", "/wp-login.php", "/wp-config.php", "/xmlrpc.php",
    "/phpmyadmin", "/pma", "/mysql",
    "/.env", "/.env.bak", "/.env.local", "/.env.production",
    "/shell.php", "/cmd.php", "/c99.php", "/r57.php", "/webshell.php",
    "/.git/config", "/.git/HEAD",
    "/.aws/credentials", "/.ssh/id_rsa", "/.ssh/authorized_keys",
    "/config.php", "/configuration.php", "/settings.php", "/db.php",
    "/backup.sql", "/dump.sql", "/database.sql", "/db.sql",
    "/admin.php", "/admin/config", "/manager/html",
    "/actuator/env", "/actuator/health", "/v1/secret",
    "/etc/passwd", "/proc/self/environ",
})

# ── Patterns d'attaque ─────────────────────────────────────
_RE_FLAGS = re.IGNORECASE
ATTACK_PATTERNS = [
    # SQL Injection
    (re.compile(
        r"(?:union\s+(?:all\s+)?select|drop\s+(?:table|database|schema)"
        r"|insert\s+into|delete\s+from|update\s+\w+\s+set"
        r"|exec\s*\(|xp_cmdshell|information_schema|sys\.tables"
        r"|benchmark\s*\(|sleep\s*\(\d|waitfor\s+delay)", _RE_FLAGS),
     "SQL_INJECTION", 15),
    # Command Injection
    (re.compile(
        r"(?:(?:;|\||\|\||&&)\s*(?:ls|cat|id|whoami|uname|wget|curl\b|nc\s"
        r"|bash|sh\s|python|php\s|perl|ruby|node)\b|\$\([^)]*\)|`[^`]*`)",
        _RE_FLAGS),
     "CMD_INJECTION", 20),
    # XSS / Script Injection
    (re.compile(
        r"(?:<script[\s/>]|javascript\s*:|vbscript\s*:|data\s*:text/html"
        r"|onerror\s*=|onload\s*=|onclick\s*=|onfocus\s*=|onmouseover\s*="
        r"|<iframe[\s/>]|<object[\s/>]|<embed[\s/>]|<svg\s+on\w+="
        r"|eval\s*\(|setTimeout\s*\(|setInterval\s*\()", _RE_FLAGS),
     "XSS_ATTEMPT", 10),
    # Path Traversal dans le corps de requête
    (re.compile(r"(?:\.\./){3,}|(?:%2e%2e[/\\%]){2,}", _RE_FLAGS),
     "PATH_TRAVERSAL_DEEP", 15),
    # Scanners connus dans User-Agent
    (re.compile(
        r"(?:sqlmap|nikto|nmap|masscan|zgrab|nessus|openvas|acunetix"
        r"|burpsuite|dirbuster|gobuster|wfuzz|ffuf|nuclei"
        r"|metasploit|w3af|arachni|havij|atscan)", _RE_FLAGS),
     "SCANNER_UA", 25),
    # Tentatives de lecture de fichiers sensibles
    (re.compile(
        r"(?:/etc/passwd|/etc/shadow|/proc/self|/sys/class"
        r"|win\.ini|boot\.ini|system32|cmd\.exe|powershell\.exe)", _RE_FLAGS),
     "FILE_READ_ATTEMPT", 12),
]

# ── Persistance des IPs bloquées ───────────────────────────
def load_blocked_ips():
    global BLOCKED_IPS
    if not os.path.exists(BLOCKED_IPS_FILE):
        return
    try:
        with open(BLOCKED_IPS_FILE, "r") as f:
            BLOCKED_IPS = set(json.load(f))
    except Exception:
        pass

def save_blocked_ips():
    try:
        with open(BLOCKED_IPS_FILE, "w") as f:
            json.dump(sorted(BLOCKED_IPS), f, indent=2)
    except Exception:
        pass

# ── Enregistrer un événement d'attaque ─────────────────────
def record_attack(ip: str, event_type: str, score: int, detail: str = ""):
    """Cumule le score d'attaque de l'IP et bannit si seuil atteint."""
    entry = ATTACK_SCORES.setdefault(ip, {"score": 0, "events": []})
    entry["score"] += score
    entry["events"].append({
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": event_type,
        "score": score,
        "detail": detail[:200],
    })
    # Garder seulement les 50 derniers événements
    entry["events"] = entry["events"][-50:]

    # Écriture dans attacks.log
    try:
        with open(ATTACK_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ip": ip, "type": event_type, "score": score, "detail": detail[:200]
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # Bannissement automatique si seuil dépassé
    if entry["score"] >= ATTACK_BAN_THRESHOLD and ip not in BLOCKED_IPS:
        BLOCKED_IPS.add(ip)
        save_blocked_ips()
        audit_log("AUTO_BAN", ip, f"Bannissement automatique — score {entry['score']} ({event_type})")
        print(f"[BININGA] 🚫 IP bannie automatiquement : {ip} (score={entry['score']})")

def check_and_ban_ip(ip: str) -> bool:
    """Retourne True si l'IP est bloquée."""
    return ip in BLOCKED_IPS

# ── Rate limiting global ────────────────────────────────────
def check_global_rate(ip: str) -> bool:
    """Retourne True si l'IP a dépassé la limite globale."""
    now  = time.time()
    rec  = REQUEST_COUNTS.get(ip)
    if not rec or now - rec["t"] > 60:
        REQUEST_COUNTS[ip] = {"n": 1, "t": now}
        return False
    rec["n"] += 1
    if rec["n"] > GLOBAL_RATE_LIMIT:
        record_attack(ip, "RATE_ABUSE", 3, f"{rec['n']} req/min")
        return True
    return False

# ── Tarpit ─────────────────────────────────────────────────
def maybe_tarpit(ip: str):
    """Introduit un délai proportionnel au score d'attaque de l'IP."""
    score = ATTACK_SCORES.get(ip, {}).get("score", 0)
    delay = 0.0
    for threshold, d in sorted(TARPIT_TABLE.items(), reverse=True):
        if score >= threshold:
            delay = d
            break
    if delay > 0:
        time.sleep(delay)

# ── Scan des patterns d'attaque ────────────────────────────
def scan_for_attacks(ip: str, text: str, context: str = ""):
    """Scanne un texte et enregistre les attaques détectées."""
    for pattern, event_type, score in ATTACK_PATTERNS:
        if event_type == "SCANNER_UA":
            continue  # Scanner UA traité séparément
        m = pattern.search(text)
        if m:
            record_attack(ip, event_type, score,
                          f"{context}: ...{text[max(0,m.start()-20):m.end()+20]}...")

def scan_user_agent(ip: str, ua: str):
    """Détecte les scanners automatiques dans le User-Agent."""
    scanner_pat = ATTACK_PATTERNS[-2][0]  # SCANNER_UA pattern
    if re.search(r"(?:sqlmap|nikto|nmap|masscan|zgrab|nessus|openvas|acunetix"
                 r"|burpsuite|dirbuster|gobuster|wfuzz|ffuf|nuclei"
                 r"|metasploit|w3af|arachni|havij|atscan)", ua, re.I):
        record_attack(ip, "SCANNER_UA", 25, f"UA: {ua[:120]}")

# ── Lecture du rapport de sécurité ─────────────────────────
def load_attacks(limit=200):
    if not os.path.exists(ATTACK_LOG_FILE):
        return []
    try:
        with open(ATTACK_LOG_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return list(reversed(entries))
    except Exception:
        return []

# ── Validation MIME par magic bytes ────────────────────────
def _is_valid_image(data: bytes) -> bool:
    """Vérifie les magic bytes pour JPEG, PNG, GIF, WebP."""
    if len(data) < 12:
        return False
    if data[:3] == b'\xff\xd8\xff':                          # JPEG
        return True
    if data[:4] == b'\x89PNG':                               # PNG
        return True
    if data[:6] in (b'GIF87a', b'GIF89a'):                   # GIF
        return True
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':       # WebP
        return True
    return False

# ── Multipart parser (remplace cgi.FieldStorage dépréciée) ─
def _parse_multipart(content_type: str, body: bytes) -> dict:
    """Parse multipart/form-data → dict {name: part} via email.parser."""
    raw = f"Content-Type: {content_type}\r\n\r\n".encode() + body
    msg = BytesParser(policy=email_policy_default).parsebytes(raw)
    fields = {}
    if msg.is_multipart():
        for part in msg.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name:
                fields[name] = part
    return fields

# ── Utilisateurs ────────────────────────────────────────────
def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def init_users():
    """Crée users.json par défaut si inexistant."""
    if not os.path.exists(USERS_FILE):
        password = ADMIN_PASS
        if not password:
            password = secrets.token_urlsafe(16)
            print(f"[BININGA] ⚠️  BININGA_PASS non défini — mot de passe généré : {password}")
            print(f"[BININGA] ⚠️  Définissez BININGA_PASS=<votre-mot-de-passe> pour un mot de passe fixe.")
        save_users([{
            "username": ADMIN_USER,
            "password_hash": _hash_new(password),
            "role": "admin",
            "nom": "Rodrin Bakala"
        }])
        print(f"[BININGA] 📁 users.json créé (compte : {ADMIN_USER})")
    elif not ADMIN_PASS:
        print(f"[BININGA] ⚠️  BININGA_PASS non défini — définissez la variable d'environnement.")

def find_user(username):
    return next((u for u in load_users() if u["username"] == username), None)

def get_session(token):
    return ACTIVE_SESSIONS.get(token)

def has_role(token, *roles):
    s = get_session(token)
    return s is not None and s["role"] in roles

# ── Sessions persistantes ───────────────────────────────────
def save_sessions():
    """Persiste les sessions actives dans sessions.json."""
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(ACTIVE_SESSIONS, f, ensure_ascii=False)
    except Exception:
        pass

def load_sessions():
    """Recharge les sessions au démarrage et expurge les expirées."""
    global ACTIVE_SESSIONS
    if not os.path.exists(SESSIONS_FILE):
        return
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)
        now = time.time()
        ACTIVE_SESSIONS = {
            token: sess for token, sess in stored.items()
            if now - sess.get("created_at", 0) < SESSION_TTL
        }
        if len(ACTIVE_SESSIONS) != len(stored):
            save_sessions()  # Réécrire sans les sessions expirées
    except Exception:
        pass

# ── Audit ──────────────────────────────────────────────────
def _rotate_audit_if_needed():
    """Archive audit.log si > MAX_LOG_SIZE et garde MAX_LOG_ARCHIVES fichiers."""
    if not os.path.exists(AUDIT_FILE):
        return
    if os.path.getsize(AUDIT_FILE) < MAX_LOG_SIZE:
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = AUDIT_FILE.replace(".log", f"_{ts}.log")
    try:
        os.rename(AUDIT_FILE, archive)
    except Exception:
        return
    archives = sorted(f for f in os.listdir(".") if f.startswith("audit_") and f.endswith(".log"))
    for old in archives[:-MAX_LOG_ARCHIVES]:
        try:
            os.remove(old)
        except Exception:
            pass

def audit_log(action, ip="", detail=""):
    """Écrit une entrée dans audit.log (format JSON Lines) avec rotation automatique."""
    _rotate_audit_if_needed()
    entry = json.dumps({
        "ts":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "ip":     ip,
        "detail": detail
    }, ensure_ascii=False)
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def load_audit(limit=100):
    """Retourne les <limit> dernières entrées du fichier audit.log."""
    if not os.path.exists(AUDIT_FILE):
        return []
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return list(reversed(entries))  # Plus récent en premier
    except Exception:
        return []

# ── Données ────────────────────────────────────────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(data):
    # Backup automatique avant écrasement
    if os.path.exists(DATA_FILE):
        backup = DATA_FILE.replace(".json", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(DATA_FILE, "rb") as src, open(backup, "wb") as dst:
            dst.write(src.read())
        # Garder uniquement les 5 derniers backups
        backups = sorted(f for f in os.listdir(".") if f.startswith("data_backup_"))
        for old in backups[:-5]:
            try:
                os.remove(old)
            except Exception:
                pass
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Veille IA : lecture/écriture ──────────────────────────
def load_news() -> dict:
    if not os.path.exists(NEWS_FILE):
        return {"items": [], "last_run": None, "stats": {"total_found": 0, "runs": 0}}
    try:
        with open(NEWS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": [], "last_run": None, "stats": {"total_found": 0, "runs": 0}}

def save_news(data: dict):
    try:
        with open(NEWS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[BININGA] Erreur sauvegarde news: {e}")

# ── Init au chargement du module ───────────────────────────
init_users()
load_sessions()

# ── Handler ────────────────────────────────────────────────
class BiningaHandler(http.server.SimpleHTTPRequestHandler):

    def _cors_origin(self):
        """Retourne l'origine si elle est autorisée, sinon None."""
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            return origin
        # Fallback : accepter les requêtes sans Origin (même machine, curl, etc.)
        if not origin:
            return None
        return None

    def do_OPTIONS(self):
        origin = self._cors_origin()
        self.send_response(200)
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token, X-CSRF-Token")
        self.end_headers()

    # ── En-têtes de sécurité HTTP ──────────────────────────
    def _security_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy",
                         "camera=(), microphone=(), geolocation=(self), payment=()")
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob: https://*.tile.openstreetmap.org "
            "https://www.openstreetmap.org; "
            "frame-src https://www.openstreetmap.org; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        if USE_SSL:
            csp += "; upgrade-insecure-requests"
            self.send_header("Strict-Transport-Security",
                             "max-age=63072000; includeSubDomains; preload")
        self.send_header("Content-Security-Policy", csp)

    def _guard(self):
        """Vérifie IP bannie + rate limit. Retourne True si la requête doit être bloquée."""
        ip = self.client_address[0]
        if check_and_ban_ip(ip):
            self._error(403, "Accès refusé")
            return True
        if check_global_rate(ip):
            self._json({"ok": False, "message": "Trop de requêtes"}, 429)
            return True
        maybe_tarpit(ip)
        return False

    def do_GET(self):
        # Normaliser le chemin : décoder l'URL, éliminer ../
        path = posixpath.normpath(unquote(urlparse(self.path).path))
        ip   = self.client_address[0]

        if self._guard():
            return

        # Scan User-Agent
        scan_user_agent(ip, self.headers.get("User-Agent", ""))
        if check_and_ban_ip(ip):
            self._error(403, "Accès refusé")
            return

        # Scan de l'URL pour attaques
        scan_for_attacks(ip, self.path, "URL")
        if check_and_ban_ip(ip):
            self._error(403, "Accès refusé")
            return

        # ── Honeypot : banning immédiat ──
        if path in HONEYPOT_PATHS or any(path.startswith(h) for h in HONEYPOT_PATHS if h.endswith("/")):
            record_attack(ip, "HONEYPOT", 30, f"Accès au piège : {path}")
            audit_log("HONEYPOT", ip, f"Chemin piège accédé : {path}")
            self._error(404, "Fichier non trouvé")
            return

        if path in ("/api/load", "/data.json"):
            self._json(load_data())
            return

        if path == "/api/contacts":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "editeur", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            all_contacts = []
            if os.path.exists(CONTACT_FILE):
                try:
                    with open(CONTACT_FILE, "r", encoding="utf-8") as f:
                        all_contacts = json.load(f)
                except Exception:
                    all_contacts = []
            audiences = [c for c in all_contacts if c.get("type") == "bininga_audiences"]
            contacts  = [c for c in all_contacts if c.get("type") != "bininga_audiences"]
            self._json({"ok": True, "audiences": audiences, "contacts": contacts})
            return

        if path == "/api/logs":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            self._json({"ok": True, "logs": load_audit()})
            return

        if path == "/api/security":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            # Top IPs suspectes triées par score décroissant
            suspects = sorted(
                [{"ip": k, **v} for k, v in ATTACK_SCORES.items()],
                key=lambda x: x["score"], reverse=True
            )[:50]
            self._json({
                "ok": True,
                "blocked": sorted(BLOCKED_IPS),
                "suspects": suspects,
                "attacks": load_attacks(100),
            })
            return

        if path == "/api/users":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            session = get_session(token)
            all_users = load_users()
            # Le ministre ne voit pas le compte protégé (Rodrin)
            if session and session["role"] == "ministre":
                all_users = [u for u in all_users if u["username"] != PROTECTED_USER]
            users = [{"username": u["username"], "role": u["role"], "nom": u["nom"]}
                     for u in all_users]
            self._json({"ok": True, "users": users})
            return

        # ── /api/news — Veille IA ──
        if path == "/api/news":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            data = load_news()
            # Vérifie si monitor.py tourne
            pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor.pid")
            monitor_running = False
            if os.path.exists(pid_file):
                try:
                    pid = int(open(pid_file).read().strip())
                    os.kill(pid, 0)   # signal 0 = vérification existence
                    monitor_running = True
                except Exception:
                    pass
            self._json({
                "ok": True,
                "items": data.get("items", []),
                "last_run": data.get("last_run"),
                "stats": data.get("stats", {}),
                "monitor_running": monitor_running,
            })
            return

        # ── Fichiers statiques avec protection path traversal ──
        relative = "index.html" if path in ("/", "") else path.lstrip("/")
        safe = _safe_path(relative)
        if safe and os.path.isfile(safe):
            try:
                with open(safe, "rb") as f:
                    content = f.read()
                mime = self._mime(safe)
                origin = self._cors_origin()
                # Gzip compression pour texte/HTML/CSS/JS/JSON
                accept_enc = self.headers.get("Accept-Encoding", "")
                can_gzip = "gzip" in accept_enc and mime.startswith((
                    "text/", "application/json", "application/javascript"
                ))
                if can_gzip:
                    content = gzip.compress(content, compresslevel=6)
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", len(content))
                if can_gzip:
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Vary", "Accept-Encoding")
                if origin:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                if mime.startswith("text/html") or mime == "application/json":
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                elif mime.startswith("image/") or mime in ("text/css", "text/javascript"):
                    self.send_header("Cache-Control", "public, max-age=86400")
                self._security_headers()
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self._error(500, str(e))
        else:
            self._error(404, "Fichier non trouvé")

    def do_POST(self):
        path   = posixpath.normpath(unquote(urlparse(self.path).path))
        ip     = self.client_address[0]

        # ── /api/test/reset doit bypasser le guard (mode test uniquement) ──
        if BININGA_TEST and path == "/api/test/reset":
            LOGIN_ATTEMPTS.clear()
            ATTACK_SCORES.clear()
            BLOCKED_IPS.clear()
            REQUEST_COUNTS.clear()
            self._json({"ok": True, "message": "All security state reset (test mode)"})
            return

        if self._guard():
            return

        # Scanner UA check
        scan_user_agent(ip, self.headers.get("User-Agent", ""))
        if check_and_ban_ip(ip):
            self._error(403, "Accès refusé")
            return

        # Honeypot sur POST
        if path in HONEYPOT_PATHS:
            record_attack(ip, "HONEYPOT_POST", 30, f"POST piège : {path}")
            self._error(404, "Route non trouvée")
            return

        # Taille max globale (DoS)
        raw_length = int(self.headers.get("Content-Length", 0))
        if raw_length > 20 * 1024 * 1024:  # 20 Mo max absolu
            record_attack(ip, "OVERSIZED_REQUEST", 8, f"Content-Length: {raw_length}")
            self._json({"ok": False, "message": "Requête trop volumineuse"}, 413)
            return

        length = raw_length
        body   = self.rfile.read(length)

        # Scan du corps de la requête (hors uploads binaires)
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            try:
                body_text = body.decode("utf-8", errors="replace")
                scan_for_attacks(ip, body_text, "POST body")
            except Exception:
                pass
        # Scan de l'URL aussi
        scan_for_attacks(ip, self.path, "URL")
        if check_and_ban_ip(ip):
            self._error(403, "Accès refusé — comportement suspect détecté")
            return

        # ── /api/login ──
        if path == "/api/login":
            # Rate limiting : bloquer si trop de tentatives
            if _is_rate_limited(ip):
                self._json({"ok": False, "message": "Trop de tentatives. Réessayez dans 5 minutes."}, 429)
                return
            try:
                creds    = json.loads(body.decode("utf-8"))
                username = creds.get("username", "")
                password = creds.get("password", "")
                user     = find_user(username)
                if user and _verify_password(password, user.get("password_hash", "")):
                    # Mise à niveau automatique sha256 legacy → pbkdf2
                    if not user["password_hash"].startswith("pbkdf2:"):
                        users = load_users()
                        for u in users:
                            if u["username"] == username:
                                u["password_hash"] = _hash_new(password)
                                break
                        save_users(users)
                        print(f"[BININGA] 🔒 Hash mis à jour (pbkdf2) pour : {username}")
                    _reset_login_attempts(ip)
                    token      = secrets.token_hex(32)
                    csrf_token = secrets.token_hex(24)
                    ACTIVE_SESSIONS[token] = {
                        "username":   user["username"],
                        "role":       user["role"],
                        "nom":        user.get("nom", user["username"]),
                        "created_at": time.time(),
                        "csrf_token": csrf_token,
                    }
                    save_sessions()
                    print(f"[BININGA] 🔓 Connexion : {username} ({user['role']}) — {datetime.now().strftime('%H:%M:%S')}")
                    audit_log("LOGIN_OK", ip, f"Connexion de {username} ({user['role']})")
                    self._json({"ok": True, "token": token, "csrf_token": csrf_token,
                                "role": user["role"], "nom": user.get("nom", username)})
                else:
                    _record_failed_login(ip)
                    record_attack(ip, "LOGIN_FAIL", 2, f"Échec login user: {username}")
                    print(f"[BININGA] ⛔ Tentative échouée : {username} — {datetime.now().strftime('%H:%M:%S')}")
                    audit_log("LOGIN_FAIL", ip, f"Identifiant ou mot de passe incorrect (user: {username})")
                    time.sleep(LOGIN_FAIL_DELAY)   # Anti brute-force + anti timing
                    self._json({"ok": False, "message": "Identifiant ou mot de passe incorrect"}, 401)
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/logout ──
        if path == "/api/logout":
            token_out = self.headers.get("X-Admin-Token", "")
            ACTIVE_SESSIONS.pop(token_out, None)
            save_sessions()
            audit_log("LOGOUT", ip, "Déconnexion")
            self._json({"ok": True})
            return

        # ── /api/upload-sinistre (public — photo de réclamation citoyenne) ──
        if path == "/api/upload-sinistre":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._json({"ok": False, "message": "Format invalide"}, 400)
                return
            fields = _parse_multipart(content_type, body)
            if "file" not in fields:
                self._json({"ok": False, "message": "Pas de fichier"}, 400)
                return
            part      = fields["file"]
            raw_name  = part.get_filename() or "sinistre.jpg"
            safe_name = "".join(c for c in os.path.basename(raw_name) if c.isalnum() or c in ".-_") or "sinistre.jpg"
            if not any(safe_name.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                self._json({"ok": False, "message": "Type de fichier non autorisé (jpg/png/webp uniquement)"}, 400)
                return
            data_bytes = part.get_payload(decode=True)
            if not data_bytes or len(data_bytes) > 3 * 1024 * 1024:
                self._json({"ok": False, "message": "Fichier trop volumineux (max 3 Mo)"}, 400)
                return
            if not _is_valid_image(data_bytes):
                self._json({"ok": False, "message": "Contenu du fichier invalide (image corrompue ou format non autorisé)"}, 400)
                return
            uid   = secrets.token_hex(6)
            ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{ts}_{uid}.jpg"
            os.makedirs(os.path.join("images", "sinistres"), exist_ok=True)
            with open(os.path.join("images", "sinistres", fname), "wb") as f:
                f.write(data_bytes)
            audit_log("SINISTRE_PHOTO", ip, f"Photo sinistre reçue : {fname}")
            self._json({"ok": True, "path": "images/sinistres/" + fname})
            return

        # ── /api/contact (public — formulaires du site) ──
        if path == "/api/contact":
            try:
                data = json.loads(body.decode("utf-8"))
                # Sauvegarder tous les champs du formulaire (chaines et nombres seulement)
                PROTECTED = {"ts", "ip"}
                entry = {
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ip": ip,
                }
                for k, v in data.items():
                    k = str(k)[:64]
                    if k in PROTECTED:
                        continue
                    if isinstance(v, str):
                        entry[k] = v[:2000]
                    elif isinstance(v, (int, float, bool)):
                        entry[k] = v
                contacts = []
                if os.path.exists(CONTACT_FILE):
                    try:
                        with open(CONTACT_FILE, "r", encoding="utf-8") as f:
                            contacts = json.load(f)
                    except Exception:
                        contacts = []
                contacts.append(entry)
                with open(CONTACT_FILE, "w", encoding="utf-8") as f:
                    json.dump(contacts, f, indent=2, ensure_ascii=False)
                nom    = entry.get("nom", "")
                prenom = entry.get("prenom", "")
                etype  = entry.get("type", "contact")
                audit_log("CONTACT", ip, f"Message de {nom} {prenom} ({etype})")
                self._json({"ok": True, "message": "Message reçu"})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── Vérification token + CSRF pour les routes protégées ──
        token = self.headers.get("X-Admin-Token", "")
        session = get_session(token)

        if not session:
            self._json({"ok": False, "message": "Non autorisé"}, 401)
            return
        # Validation CSRF sur routes d'écriture
        if path in ("/api/save", "/api/users/upsert", "/api/users/delete", "/api/contacts/clear"):
            csrf_received = self.headers.get("X-CSRF-Token", "")
            csrf_expected = session.get("csrf_token", "")
            if not csrf_expected or not secrets.compare_digest(csrf_received, csrf_expected):
                audit_log("CSRF_REJECT", ip, f"Token CSRF invalide sur {path}")
                self._json({"ok": False, "message": "Requête invalide (CSRF)"}, 403)
                return

        # ── /api/contacts/clear ──
        if path == "/api/contacts/clear":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data     = json.loads(body.decode("utf-8"))
                msg_type = data.get("type", "")
                if not msg_type:
                    self._json({"ok": False, "message": "Type requis"}, 400)
                    return
                all_contacts = []
                if os.path.exists(CONTACT_FILE):
                    with open(CONTACT_FILE, "r", encoding="utf-8") as f:
                        all_contacts = json.load(f)
                kept = [c for c in all_contacts if c.get("type") != msg_type]
                with open(CONTACT_FILE, "w", encoding="utf-8") as f:
                    json.dump(kept, f, indent=2, ensure_ascii=False)
                who = session["username"] if session else "?"
                audit_log("CLEAR_CONTACTS", ip, f"Suppression type={msg_type} par {who}")
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        if path == "/api/security/unblock":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data   = json.loads(body.decode("utf-8"))
                target = data.get("ip", "").strip()
                if not target:
                    self._json({"ok": False, "message": "IP requise"}, 400)
                    return
                BLOCKED_IPS.discard(target)
                ATTACK_SCORES.pop(target, None)
                save_blocked_ips()
                audit_log("UNBLOCK_IP", ip, f"IP débloquée : {target}")
                self._json({"ok": True, "message": f"IP {target} débloquée"})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        if path == "/api/security/block":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data   = json.loads(body.decode("utf-8"))
                target = data.get("ip", "").strip()
                reason = data.get("reason", "Blocage manuel")
                if not target:
                    self._json({"ok": False, "message": "IP requise"}, 400)
                    return
                BLOCKED_IPS.add(target)
                save_blocked_ips()
                audit_log("MANUAL_BAN", ip, f"IP bannie manuellement : {target} — {reason}")
                self._json({"ok": True, "message": f"IP {target} bloquée"})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        if path == "/api/users/upsert":
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Réservé à l'admin ou au ministre"}, 403)
                return
            try:
                data  = json.loads(body.decode("utf-8"))
                uname = data.get("username", "").strip()
                nom   = data.get("nom", "").strip()
                role  = data.get("role", "lecteur")
                pwd   = data.get("password", "").strip()
                if not uname or role not in ("admin", "editeur", "lecteur", "ministre"):
                    self._json({"ok": False, "message": "Données invalides"}, 400)
                    return
                # Le ministre ne peut pas toucher au compte protégé
                session = get_session(token)
                if session and session["role"] == "ministre" and uname == PROTECTED_USER:
                    self._json({"ok": False, "message": "Ce compte est protégé et ne peut pas être modifié"}, 403)
                    return
                users    = load_users()
                existing = next((u for u in users if u["username"] == uname), None)
                if existing:
                    existing["nom"]  = nom or existing["nom"]
                    existing["role"] = role
                    if pwd:
                        existing["password_hash"] = _hash_new(pwd)
                else:
                    if not pwd:
                        self._json({"ok": False, "message": "Mot de passe requis"}, 400)
                        return
                    users.append({"username": uname, "password_hash": _hash_new(pwd), "role": role, "nom": nom or uname})
                save_users(users)
                action = "Modification" if existing else "Création"
                audit_log("USER_UPSERT", ip, f"{action} utilisateur : {uname} ({role})")
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/users/delete ──
        if path == "/api/users/delete":
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Réservé à l'admin ou au ministre"}, 403)
                return
            try:
                data    = json.loads(body.decode("utf-8"))
                uname   = data.get("username", "")
                session = get_session(token)
                if uname == session["username"]:
                    self._json({"ok": False, "message": "Impossible de supprimer son propre compte"}, 400)
                    return
                # Le ministre ne peut pas supprimer le compte protégé
                if session and session["role"] == "ministre" and uname == PROTECTED_USER:
                    self._json({"ok": False, "message": "Ce compte est protégé et ne peut pas être supprimé"}, 403)
                    return
                users = [u for u in load_users() if u["username"] != uname]
                save_users(users)
                audit_log("USER_DELETE", ip, f"Suppression utilisateur : {uname}")
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/upload ──
        if path == "/api/upload":
            if not has_role(token, "admin", "editeur", "ministre"):
                self._json({"ok": False, "message": "Accès refusé"}, 403)
                return
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._json({"ok": False, "message": "Format invalide"}, 400)
                return
            fields = _parse_multipart(content_type, body)
            if "file" not in fields:
                self._json({"ok": False, "message": "Pas de fichier"}, 400)
                return
            part      = fields["file"]
            raw_name  = part.get_filename() or "upload.jpg"
            safe_name = "".join(c for c in os.path.basename(raw_name) if c.isalnum() or c in ".-_") or "image.jpg"
            # Vérifier extension image
            if not any(safe_name.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")):
                self._json({"ok": False, "message": "Type de fichier non autorisé"}, 400)
                return
            data_bytes = part.get_payload(decode=True)
            if not data_bytes or len(data_bytes) > 10 * 1024 * 1024:
                self._json({"ok": False, "message": "Fichier trop volumineux (max 10 Mo)"}, 400)
                return
            # SVG autorisé sans vérification magic bytes (texte XML)
            if not safe_name.lower().endswith(".svg") and not _is_valid_image(data_bytes):
                self._json({"ok": False, "message": "Contenu du fichier invalide (image corrompue ou format non autorisé)"}, 400)
                return
            os.makedirs("images", exist_ok=True)
            with open(os.path.join("images", safe_name), "wb") as f:
                f.write(data_bytes)
            print(f"[BININGA] 📷 Image uploadée : {safe_name}")
            audit_log("UPLOAD", ip, f"Image uploadée : {safe_name}")
            self._json({"ok": True, "path": "images/" + safe_name})
            return

        # ── /api/save ──
        if path == "/api/save":
            if not has_role(token, "admin", "editeur", "ministre"):
                self._json({"ok": False, "message": "Accès refusé"}, 403)
                return
            # Clés réservées à l'admin principal uniquement
            ADMIN_ONLY_KEYS = {"hero", "about", "parcours", "parcoursSection"}
            try:
                data    = json.loads(body.decode("utf-8"))
                session = get_session(token)
                role    = session["role"] if session else "lecteur"
                # Si non-admin : on préserve les clés sensibles de data.json existant
                if role != "admin":
                    existing = load_data()
                    for key in ADMIN_ONLY_KEYS:
                        if key in existing:
                            data[key] = existing[key]
                        elif key in data:
                            del data[key]
                save_data(data)
                who = session["username"] if session else "?"
                print(f"[BININGA] ✅ Données sauvegardées — {datetime.now().strftime('%H:%M:%S')}")
                audit_log("SAVE", ip, f"data.json sauvegardé par {who}")
                self._json({"ok": True, "message": "Données sauvegardées"})
            except Exception as e:
                print(f"[BININGA] ❌ Erreur sauvegarde : {e}")
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/news/mark-read ──
        if path == "/api/news/mark-read":
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                payload = json.loads(body.decode("utf-8"))
                item_id = payload.get("id")
                mark_all = payload.get("all", False)
                data = load_news()
                changed = 0
                for item in data.get("items", []):
                    if mark_all or item.get("id") == item_id:
                        item["read"] = True
                        changed += 1
                save_news(data)
                self._json({"ok": True, "changed": changed})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/news/delete ──
        if path == "/api/news/delete":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                payload = json.loads(body.decode("utf-8"))
                item_id = payload.get("id")
                data = load_news()
                before = len(data.get("items", []))
                data["items"] = [a for a in data.get("items", []) if a.get("id") != item_id]
                save_news(data)
                self._json({"ok": True, "deleted": before - len(data["items"])})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/news/run ── déclenchement manuel de la veille ──
        if path == "/api/news/run":
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                payload = json.loads(body.decode("utf-8")) if body.strip() else {}
                custom_query = (payload.get("query") or "").strip()
                trigger_file = os.path.join(os.path.dirname(__file__), "monitor.trigger")
                with open(trigger_file, "w", encoding="utf-8") as f:
                    f.write(custom_query)
                msg = f"Recherche lancée : « {custom_query} »" if custom_query else "Cycle de veille complet lancé"
                audit_log("SAVE", ip, msg)
                self._json({"ok": True, "message": msg})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        self._error(404, "Route non trouvée")

    # ── Helpers ────────────────────────────────────────────
    def _mime(self, path):
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        return {
            "html": "text/html; charset=utf-8",
            "json": "application/json",
            "css":  "text/css",
            "js":   "text/javascript",
            "png":  "image/png",
            "jpg":  "image/jpeg", "jpeg": "image/jpeg",
            "gif":  "image/gif",
            "svg":  "image/svg+xml",
            "webp": "image/webp",
            "ico":  "image/x-icon",
        }.get(ext, "application/octet-stream")

    def _json(self, data, status=200):
        response = json.dumps(data, ensure_ascii=False).encode("utf-8")
        origin = self._cors_origin()
        accept_enc = self.headers.get("Accept-Encoding", "")
        if "gzip" in accept_enc and len(response) > 512:
            response = gzip.compress(response, compresslevel=6)
            encoding = "gzip"
        else:
            encoding = None
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        if encoding:
            self.send_header("Content-Encoding", encoding)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", len(response))
        self._security_headers()
        self.end_headers()
        self.wfile.write(response)

    def _error(self, code, message):
        response = f"<h1>{code}</h1><p>{message}</p>".encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(response))
        self._security_headers()
        self.end_headers()
        self.wfile.write(response)

    def version_string(self):
        return "BININGA/1.0"  # Masquer la version Python

    def log_message(self, format, *args):
        pass  # Logs gérés manuellement

# ── Lancement ──────────────────────────────────────────────
def generate_self_signed_cert():
    """Génère un certificat SSL auto-signé si absent (localhost dev)."""
    try:
        import subprocess
        result = subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", "key.pem", "-out", "cert.pem",
            "-days", "365", "-nodes",
            "-subj", "/C=CG/ST=Cuvette/L=Ewo/O=Bininga/CN=localhost",
            "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost"
        ], capture_output=True, timeout=30)
        if result.returncode == 0:
            print("[BININGA] ✅ Certificat SSL auto-généré (cert.pem / key.pem)")
            return True
        else:
            print("[BININGA] ⚠️  Impossible de générer le certificat SSL (openssl requis)")
            return False
    except Exception:
        print("[BININGA] ⚠️  openssl non disponible — SSL désactivé")
        return False

def resolve_ssl_certs():
    """Résout les chemins des certificats SSL.

    Priorité :
      1. Variables d'environnement BININGA_CERT / BININGA_KEY
      2. Certificats Let's Encrypt pour bininga.cg
      3. Certificat auto-signé local (cert.pem / key.pem)
    Retourne (cert_path, key_path, source) ou (None, None, None).
    """
    # 1. Variables d'environnement
    env_cert = os.environ.get("BININGA_CERT", "")
    env_key  = os.environ.get("BININGA_KEY", "")
    if env_cert and env_key and os.path.isfile(env_cert) and os.path.isfile(env_key):
        return env_cert, env_key, "variables d'env"

    # 2. Let's Encrypt
    le_base = "/etc/letsencrypt/live/bininga.cg"
    le_cert = os.path.join(le_base, "fullchain.pem")
    le_key  = os.path.join(le_base, "privkey.pem")
    if os.path.isfile(le_cert) and os.path.isfile(le_key):
        return le_cert, le_key, "Let's Encrypt"

    # 3. Certificat local
    if os.path.isfile("cert.pem") and os.path.isfile("key.pem"):
        return "cert.pem", "key.pem", "auto-signé (local)"

    return None, None, None


def start_monitor():
    """Lance monitor.py en sous-processus daemon si pas déjà actif."""
    import subprocess, sys
    base = os.path.dirname(os.path.abspath(__file__))
    pid_file     = os.path.join(base, "monitor.pid")
    monitor_path = os.path.join(base, "monitor.py")
    log_path     = os.path.join(base, "monitor.log")

    if not os.path.isfile(monitor_path):
        print("[BININGA] ⚠️  monitor.py introuvable — veille désactivée")
        return

    # Vérifier si déjà lancé et toujours vivant
    if os.path.isfile(pid_file):
        try:
            pid = int(open(pid_file).read().strip())
            os.kill(pid, 0)
            print(f"[BININGA] 🤖 YARO IA déjà actif (PID {pid})")
            return
        except (OSError, ValueError):
            # PID mort ou invalide — on relance
            pass

    log_fd = open(log_path, "a")
    proc = subprocess.Popen(
        [sys.executable, monitor_path],
        stdout=log_fd,
        stderr=log_fd,
        start_new_session=True,
    )
    print(f"[BININGA] 🤖 YARO IA lancé (PID {proc.pid}) — logs : {log_path}")


def _monitor_watchdog():
    """Thread watchdog : vérifie toutes les 5 min si YARO IA tourne, le relance si mort."""
    import threading
    def _check():
        while True:
            time.sleep(300)   # 5 minutes
            try:
                base     = os.path.dirname(os.path.abspath(__file__))
                pid_file = os.path.join(base, "monitor.pid")
                alive = False
                if os.path.isfile(pid_file):
                    try:
                        pid = int(open(pid_file).read().strip())
                        os.kill(pid, 0)
                        alive = True
                    except (OSError, ValueError):
                        pass
                if not alive:
                    print("[BININGA] ⚠️  YARO IA inactif — redémarrage automatique…", flush=True)
                    start_monitor()
            except Exception as e:
                print(f"[BININGA] Watchdog erreur : {e}", flush=True)
    t = threading.Thread(target=_check, daemon=True, name="yaro-watchdog")
    t.start()


if __name__ == "__main__":
    init_users()
    load_blocked_ips()
    start_monitor()
    _monitor_watchdog()

    # Génère un certificat auto-signé si aucun n'existe du tout
    if not (os.path.isfile("cert.pem") and os.path.isfile("key.pem")
            or os.path.isfile("/etc/letsencrypt/live/bininga.cg/fullchain.pem")):
        generate_self_signed_cert()

    CERT_FILE, KEY_FILE, CERT_SOURCE = resolve_ssl_certs()
    # Disable SSL when running on Railway (or any reverse-proxy that handles TLS termination)
    _on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
    _force_http = os.environ.get("BININGA_FORCE_HTTP", "") == "1"
    USE_SSL  = CERT_FILE is not None and not _on_railway and not _force_http
    PORT     = int(os.environ.get("PORT", 443 if (USE_SSL and CERT_SOURCE == "Let's Encrypt") else 8443 if USE_SSL else 8080))
    protocol = "https" if USE_SSL else "http"

    ssl_label = f"✅ {CERT_SOURCE}" if USE_SSL else "⚠️  Désactivé"
    print(f"""
╔══════════════════════════════════════════════╗
  ║   BININGA — Serveur                         ║
  ║                                            ║
  ║   Site  →  {protocol}://bininga.cg:{PORT}       ║
  ║   Admin →  {protocol}://bininga.cg:{PORT}/admin.html ║
  ║                                            ║
  ║   SSL : {ssl_label:<38}║
  ╚══════════════════════════════════════════════╝
    """)

    server = http.server.HTTPServer(("0.0.0.0", PORT), BiningaHandler)

    if USE_SSL:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(CERT_FILE, KEY_FILE)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)

        # Serveur HTTP dédié → redirection 301 vers HTTPS
        REDIRECT_PORT = int(os.environ.get("REDIRECT_PORT", 80 if CERT_SOURCE == "Let's Encrypt" else 8080))
        HTTPS_PORT    = PORT

        class _RedirectHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                host = self.headers.get("Host", f"bininga.cg").split(":")[0]
                location = f"https://{host}{self.path}" if HTTPS_PORT == 443 else f"https://{host}:{HTTPS_PORT}{self.path}"
                self.send_response(301)
                self.send_header("Location", location)
                self.end_headers()
            def do_POST(self):
                self.do_GET()
            def log_message(self, *args):
                pass

        redirect_srv = http.server.HTTPServer(("0.0.0.0", REDIRECT_PORT), _RedirectHandler)
        threading.Thread(target=redirect_srv.serve_forever, daemon=True).start()
        print(f"🔄 Redirection HTTP:{REDIRECT_PORT} → HTTPS:{HTTPS_PORT}")
        print(f"🔒 HTTPS activé ({CERT_SOURCE})")

    print(f"✅ Serveur lancé sur {protocol}://bininga.cg:{PORT}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Serveur arrêté")
        server.server_close()
