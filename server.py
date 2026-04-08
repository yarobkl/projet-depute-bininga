import http.server
import socketserver
import json
import os
import io
import ssl
import secrets
import hashlib
import hmac
import struct
import time
import threading
import queue as _queue_mod
import posixpath
import re
import gzip
import base64
import html as _html
from email.parser import BytesParser
from email.policy import default as email_policy_default
from urllib.parse import urlparse, unquote, parse_qs

# ══════════════════════════════════════════════════════════════════════════════
# ██  BOUCLIER — OPERATION SÉCURITÉ IA & BOTS (multi-couches)                ██
# ══════════════════════════════════════════════════════════════════════════════
try:
    from security_ai_guard import AI_GUARD, is_vault_protected, is_canary_path
    _AI_GUARD_ENABLED = True
    print("[BOUCLIER] Forces Spéciales Numériques activées — 6 couches de défense en ligne")
except ImportError:
    _AI_GUARD_ENABLED = False
    print("[BOUCLIER] Module security_ai_guard non trouvé — protection basique seulement")

# ── SSE — Notifications temps réel admin ──────────────────────────────────────
_SSE_CLIENTS: list = []
_SSE_LOCK = threading.Lock()

def _sse_broadcast(event_type: str, data: dict):
    """Envoie un événement SSE à tous les admins connectés."""
    msg = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
    with _SSE_LOCK:
        dead = []
        for q in _SSE_CLIENTS:
            try:
                q.put_nowait(msg)
            except Exception:
                dead.append(q)
        for q in dead:
            try: _SSE_CLIENTS.remove(q)
            except ValueError: pass
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Notifications email temps réel ────────────────────────────────────────────
# Variables d'environnement requises :
#   NOTIF_EMAIL_FROM  → adresse Gmail d'envoi (ex: monbot@gmail.com)
#   NOTIF_EMAIL_PASS  → mot de passe d'application Gmail (16 caractères)
#   NOTIF_EMAIL_TO    → destinataire(s) séparés par virgule (ex: eliebakala@gmail.com)

def _send_notif_email(entry: dict, notif_type: str):
    """Envoie un email de notification au(x) destinataire(s) configuré(s)."""
    from_addr = os.environ.get("NOTIF_EMAIL_FROM", "").strip()
    password  = os.environ.get("NOTIF_EMAIL_PASS", "").strip()
    to_raw    = os.environ.get("NOTIF_EMAIL_TO", "eliebakala@gmail.com").strip()
    if not from_addr or not password:
        return  # SMTP non configuré — silencieux

    to_list = [a.strip() for a in to_raw.split(",") if a.strip()]
    if not to_list:
        return

    labels = {
        "bininga_audiences":      "📋 Demande d'audience",
        "bininga_contacts":       "✉️ Message de contact",
        "bininga_newsletter":     "📩 Inscription newsletter",
        "bininga_commande_livre": "📚 Commande de livre",
    }
    src    = entry.get("source") or entry.get("type", "contact")
    label  = labels.get(src, "📬 Nouveau message")
    nom    = f"{entry.get('prenom','')} {entry.get('nom','')}".strip() or "Inconnu"
    ts     = entry.get("ts", "")

    # Corps email HTML
    def row(k, v):
        return f'<tr><td style="padding:6px 12px;color:#666;white-space:nowrap">{k}</td><td style="padding:6px 12px;font-weight:600">{v}</td></tr>'

    rows = ""
    for field, display in [
        ("nom",         "Nom"),
        ("prenom",      "Prénom"),
        ("telephone",   "Téléphone"),
        ("email",       "Email"),
        ("adresse",     "Adresse"),
        ("objet",       "Objet"),
        ("raison",      "Raison / Message"),
        ("message",     "Message"),
        ("description", "Description"),
        ("sujet",       "Sujet"),
    ]:
        val = entry.get(field, "").strip() if isinstance(entry.get(field), str) else ""
        if val:
            rows += row(display, val)
    if entry.get("geo_lat"):
        maps = entry.get("geo_maps_url", f"https://maps.google.com/?q={entry['geo_lat']},{entry.get('geo_lng','')}")
        rows += row("Localisation", f'<a href="{maps}">{entry["geo_lat"]}, {entry.get("geo_lng","")}</a>')

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
      <div style="background:#1a1a2e;padding:20px 24px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0;font-size:18px">{label}</h2>
        <p style="color:rgba(255,255,255,.6);margin:4px 0 0;font-size:13px">{ts}</p>
      </div>
      <div style="background:#f9f9f9;padding:4px 0;border-radius:0 0 8px 8px">
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          {rows}
        </table>
      </div>
      <p style="font-size:11px;color:#aaa;margin-top:16px;text-align:center">
        Notif automatique — site bininga.cg
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[BININGA] {label} — {nom}"
    msg["From"]    = from_addr
    msg["To"]      = ", ".join(to_list)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as srv:
            srv.login(from_addr, password)
            srv.sendmail(from_addr, to_list, msg.as_string())
        print(f"[EMAIL] Notification envoyée à {to_list} ({label})")
    except Exception as e:
        print(f"[EMAIL] Erreur envoi : {e}")

def _send_notif_email_async(entry: dict, notif_type: str):
    """Lance l'envoi email dans un thread séparé (non bloquant)."""
    t = threading.Thread(target=_send_notif_email, args=(entry, notif_type), daemon=True)
    t.start()

# ── Module de monitoring (facultatif, stdlib uniquement) ───────────────────────
try:
    import monitoring as _mon
    _MON = True
except Exception:
    _mon = None  # type: ignore
    _MON = False

# ── Version build (cache-busting) ──────────────────────────
def _get_build_version():
    try:
        import subprocess
        h = subprocess.check_output(["git","rev-parse","--short","HEAD"],
                                    stderr=subprocess.DEVNULL).decode().strip()
        return h if h else str(int(datetime.now().timestamp()))
    except Exception:
        return str(int(datetime.now().timestamp()))

BUILD_VERSION = _get_build_version()

# ── Configuration ──────────────────────────────────────────
# DATA_DIR : répertoire persistant (ex: volume Railway /data).
# Si non défini, utilise le répertoire courant (éphémère sur Railway free tier).
DATA_DIR        = os.environ.get("DATA_DIR", ".")
if DATA_DIR != ".":
    os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE       = "data.json"   # Contenu du site — NE PAS mettre dans DATA_DIR
AUDIT_FILE      = os.path.join(DATA_DIR, "audit.log")
USERS_FILE      = os.path.join(DATA_DIR, "users.json")
SESSIONS_FILE   = os.path.join(DATA_DIR, "sessions.json")
BININGA_TEST    = os.environ.get("BININGA_TEST", "") == "1"  # Mode test uniquement
ADMIN_USER      = os.environ.get("BININGA_USER", "admin")
ADMIN_PASS      = os.environ.get("BININGA_PASS", "")
PROTECTED_USER  = os.environ.get("BININGA_PROTECTED", "rodrin")

# URL secrète de l'espace admin — à définir dans Railway via ADMIN_SECRET_PATH
# Par défaut : une URL non devinable. /admin.html devient un piège canari (ban 24h).
# Exemple Railway : ADMIN_SECRET_PATH=mon-espace-prive-2025
ADMIN_SECRET_PATH = os.environ.get("ADMIN_SECRET_PATH", "espace-ministre-ab-2025").strip("/")

# Origines autorisées pour CORS
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "BININGA_ORIGINS",
    "https://bininga.cg,https://www.bininga.cg,"
    "http://localhost:8080,https://localhost:8443,http://127.0.0.1:8080"
).split(",") if o.strip()]
BASE_DIR        = os.path.realpath(os.getcwd())

# Sessions actives : token → {username, role, nom, created_at, csrf_token, ttl}
ACTIVE_SESSIONS    = {}
SESSION_TTL        = 86400           # 24 heures  (session normale)
SESSION_TTL_LONG   = 7 * 86400       # 7 jours    (IP de confiance)

# IPs de confiance : session longue durée (7 jours) pour l'admin
# Format Railway env : ADMIN_TRUSTED_IPS=1.2.3.4,5.6.7.8
_RAW_TRUSTED = os.environ.get("ADMIN_TRUSTED_IPS", "")
TRUSTED_IPS: set = {ip.strip() for ip in _RAW_TRUSTED.split(",") if ip.strip()}

# Fichier de contact
CONTACT_FILE = os.path.join(DATA_DIR, "contacts.json")

# Fichier de veille IA
NEWS_FILE = os.path.join(DATA_DIR, "news_monitor.json")

# Fichier éditorial IA
EDITORIAL_FILE = os.path.join(DATA_DIR, "editorial.json")

# Fichier YouTube IA
YOUTUBE_FILE = os.path.join(DATA_DIR, "youtube.json")

# Fichier CRM — rétention 10 ans
CRM_FILE             = os.path.join(DATA_DIR, "crm.json")
CRM_RETENTION_YEARS  = 10

# Rate limiting login par IP
LOGIN_ATTEMPTS  = {}
MAX_ATTEMPTS    = 5
LOCKOUT_SECONDS = 1800  # 30 minutes

# Rate limiting login par NOM D'UTILISATEUR (anti-attaque distribuée)
# Une attaque distribuée (50 IPs × 5 tentatives) est stoppée ici.
USERNAME_ATTEMPTS     = {}   # username → {count, blocked_until}
USERNAME_MAX_ATTEMPTS = 10   # 10 échecs toutes IPs confondues → blocage 1h
USERNAME_LOCKOUT_SECS = 3600 # 1 heure

# Rate limiting par token (API calls) : token → {count, window_start}
TOKEN_RATE_COUNTS: dict = {}
TOKEN_RATE_LIMIT  = 300     # requêtes / 60 s / token
TOKEN_RATE_WINDOW = 60      # secondes

# Rate limiting chatbot public : ip → {count, window_start}
CHAT_RATE_COUNTS: dict = {}
CHAT_RATE_LIMIT  = 10       # messages / 60 s / IP (anti-spam/DDoS AI quota)
CHAT_RATE_WINDOW = 60       # secondes

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

# ── Sécurité — 2FA TOTP (RFC 6238, HMAC-SHA1) ──────────────
def _totp_generate_secret() -> str:
    """Génère un secret TOTP encodé en base32 (20 octets = 160 bits)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8")

def _totp_hotp(secret: str, counter: int) -> int:
    """HOTP(K, C) = Truncate(HMAC-SHA1(K, C)) — RFC 4226."""
    key = base64.b32decode(secret.upper() + "=" * ((8 - len(secret) % 8) % 8))
    msg = struct.pack(">Q", counter)
    h   = hmac.new(key, msg, "sha1").digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return code % 1_000_000

def _totp_verify(secret: str, token: str, window: int = 1) -> bool:
    """Vérifie un code TOTP ± window intervalles de 30 s."""
    try:
        code = int(token.strip())
    except (ValueError, TypeError):
        return False
    counter = int(time.time()) // 30
    for delta in range(-window, window + 1):
        if secrets.compare_digest(str(_totp_hotp(secret, counter + delta)).zfill(6), str(code).zfill(6)):
            return True
    return False

def _totp_uri(secret: str, username: str, issuer: str = "BININGA") -> str:
    """Retourne l'URI otpauth:// pour QR code."""
    from urllib.parse import quote
    return (f"otpauth://totp/{quote(issuer)}:{quote(username)}"
            f"?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30")

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

BLOCKED_IPS_FILE    = os.path.join(DATA_DIR, "blocked_ips.json")
ATTACK_LOG_FILE     = os.path.join(DATA_DIR, "attacks.log")
ATTACK_SCORES_FILE  = os.path.join(DATA_DIR, "attack_scores.json")
USE_SSL             = False   # mis à jour dans __main__

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

def load_attack_scores():
    """Recharge les scores d'attaque depuis le fichier de persistance."""
    global ATTACK_SCORES
    if not os.path.exists(ATTACK_SCORES_FILE):
        return
    try:
        with open(ATTACK_SCORES_FILE, "r", encoding="utf-8") as f:
            ATTACK_SCORES = json.load(f)
    except Exception:
        pass

def save_attack_scores():
    """Persiste les scores d'attaque sur disque (survit aux redémarrages)."""
    try:
        with open(ATTACK_SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump(ATTACK_SCORES, f, ensure_ascii=False)
    except Exception:
        pass

# ── Compteur pour flush périodique des scores ──────────────
_ATTACK_SAVE_COUNTER = 0
_ATTACK_SAVE_EVERY   = 10   # Sauvegarder tous les 10 événements

# ── Enregistrer un événement d'attaque ─────────────────────
def record_attack(ip: str, event_type: str, score: int, detail: str = ""):
    """Cumule le score d'attaque de l'IP et bannit si seuil atteint."""
    global _ATTACK_SAVE_COUNTER
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

    # Persistance périodique des scores (tous les N événements)
    _ATTACK_SAVE_COUNTER += 1
    if _ATTACK_SAVE_COUNTER >= _ATTACK_SAVE_EVERY:
        _ATTACK_SAVE_COUNTER = 0
        save_attack_scores()

    # Bannissement automatique si seuil dépassé (jamais les IPs de confiance)
    if entry["score"] >= ATTACK_BAN_THRESHOLD and ip not in BLOCKED_IPS and not _is_trusted_ip(ip):
        BLOCKED_IPS.add(ip)
        save_blocked_ips()
        save_attack_scores()
        audit_log("AUTO_BAN", ip, f"Bannissement automatique — score {entry['score']} ({event_type})")
        print(f"[BININGA] 🚫 IP bannie automatiquement : {ip} (score={entry['score']})")

_NEVER_BAN_IPS = frozenset({"127.0.0.1", "::1"})  # jamais bannir le serveur lui-même

def _is_trusted_ip(ip: str) -> bool:
    """Retourne True si l'IP ne doit jamais être bannie (localhost + admin_trusted_ips)."""
    return ip in _NEVER_BAN_IPS or ip in TRUSTED_IPS

def check_and_ban_ip(ip: str) -> bool:
    """Retourne True si l'IP est bloquée (les IPs de confiance ne peuvent jamais l'être)."""
    if _is_trusted_ip(ip):
        return False
    return ip in BLOCKED_IPS

def check_token_rate(token: str) -> bool:
    """Retourne True si le token a dépassé la limite de requêtes."""
    if not token:
        return False
    now = time.time()
    rec = TOKEN_RATE_COUNTS.get(token)
    if not rec or now - rec["t"] > TOKEN_RATE_WINDOW:
        TOKEN_RATE_COUNTS[token] = {"n": 1, "t": now}
        return False
    rec["n"] += 1
    return rec["n"] > TOKEN_RATE_LIMIT

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

# ── Rate limiting chatbot public ───────────────────────────
def check_chat_rate(ip: str) -> bool:
    """Retourne True si l'IP dépasse la limite chatbot (10 msg/min)."""
    now = time.time()
    rec = CHAT_RATE_COUNTS.get(ip)
    if not rec or now - rec["t"] > CHAT_RATE_WINDOW:
        CHAT_RATE_COUNTS[ip] = {"n": 1, "t": now}
        return False
    rec["n"] += 1
    if rec["n"] > CHAT_RATE_LIMIT:
        record_attack(ip, "CHAT_RATE_ABUSE", 2, f"Chat: {rec['n']} msg/min")
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
    db = _pg_load("users")
    if db is not None:
        return db
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_users(users):
    db_ok = _pg_save("users", users)
    file_ok = False
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        file_ok = True
    except Exception as e:
        print(f"[BININGA] Erreur sauvegarde users fichier : {e}")
    if not db_ok and not file_ok:
        raise RuntimeError("Impossible de sauvegarder les utilisateurs (DB et fichier indisponibles)")

def init_users():
    """Crée le compte admin par défaut si inexistant (DB ou fichier)."""
    existing = load_users()
    if not existing:
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
        print(f"[BININGA] 📁 Compte admin créé ({ADMIN_USER})")
    elif not ADMIN_PASS:
        # En production (Railway) : bloquer le démarrage sans mot de passe défini
        on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
        if on_railway:
            print("[BININGA] ❌ BININGA_PASS est obligatoire en production. Ajoutez la variable d'environnement.")
            import sys; sys.exit(1)
        else:
            print(f"[BININGA] ⚠️  BININGA_PASS non défini — définissez la variable d'environnement.")

def find_user(username):
    return next((u for u in load_users() if u["username"] == username), None)

def get_session(token):
    s = ACTIVE_SESSIONS.get(token)
    if s is None:
        return None
    ttl = s.get("ttl", SESSION_TTL)
    if time.time() - s.get("created_at", 0) > ttl:
        ACTIVE_SESSIONS.pop(token, None)
        return None
    return s

def has_role(token, *roles):
    s = get_session(token)
    return s is not None and s["role"] in roles

# ── Sessions persistantes ───────────────────────────────────
def save_sessions():
    """Persiste les sessions dans PostgreSQL ET sessions.json."""
    _pg_save("sessions", ACTIVE_SESSIONS)  # _pg_save résolu à l'appel
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(ACTIVE_SESSIONS, f, ensure_ascii=False)
    except Exception:
        pass

def load_sessions():
    """Recharge les sessions : PostgreSQL en priorité, fichier en fallback."""
    global ACTIVE_SESSIONS
    now = time.time()

    # Essayer PostgreSQL en priorité
    stored = _pg_load("sessions")  # _pg_load résolu à l'appel
    if stored is None:
        # Fallback fichier
        if not os.path.exists(SESSIONS_FILE):
            return
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
        except Exception:
            return

    ACTIVE_SESSIONS = {
        token: sess for token, sess in stored.items()
        if now - sess.get("created_at", 0) < sess.get("ttl", SESSION_TTL)
    }
    if len(ACTIVE_SESSIONS) != len(stored):
        save_sessions()  # Purger les sessions expirées

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

# ── Données du site (Hero, À propos, Galerie, etc.) ────────
_DATA_CACHE      = None   # contenu en cache
_DATA_CACHE_AT   = 0.0   # timestamp du dernier chargement
_DATA_CACHE_TTL  = 60    # secondes avant rechargement

def load_data():
    """Charge le contenu du site : PostgreSQL en priorité, fichier en fallback.
    Résultat mis en cache 60 s pour éviter un hit DB à chaque message chatbot."""
    global _DATA_CACHE, _DATA_CACHE_AT
    now = time.time()
    if _DATA_CACHE is not None and (now - _DATA_CACHE_AT) < _DATA_CACHE_TTL:
        return _DATA_CACHE
    db = _pg_load("site_data")
    if db is not None:
        _DATA_CACHE, _DATA_CACHE_AT = db, now
        return db
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _DATA_CACHE, _DATA_CACHE_AT = data, now
        return data
    except Exception:
        return {}

def save_data(data):
    """Persiste le contenu du site dans PostgreSQL ET dans le fichier (double sécurité)."""
    global _DATA_CACHE, _DATA_CACHE_AT
    _DATA_CACHE, _DATA_CACHE_AT = data, time.time()  # met à jour le cache immédiatement
    with _DATA_LOCK:
        # 1. PostgreSQL — source de vérité persistante
        db_ok = _pg_save("site_data", data)
        # 2. Fichier local — fallback + backup
        file_ok = False
        try:
            if os.path.exists(DATA_FILE):
                backup = DATA_FILE.replace(".json", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                with open(DATA_FILE, "rb") as src, open(backup, "wb") as dst:
                    dst.write(src.read())
                backups = sorted(f for f in os.listdir(".") if f.startswith("data_backup_"))
                for old in backups[:-5]:
                    try: os.remove(old)
                    except Exception: pass
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            file_ok = True
        except Exception as e:
            print(f"[BININGA] Erreur sauvegarde data.json : {e}")
        if not db_ok and not file_ok:
            raise RuntimeError("Impossible de sauvegarder le contenu du site (DB et fichier indisponibles)")

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

# ══════════════════════════════════════════════════════════════════════════
# ██  COUCHE BASE DE DONNÉES — PostgreSQL + fallback fichiers JSON          ██
# ══════════════════════════════════════════════════════════════════════════
# Utilise PostgreSQL si DATABASE_URL est défini (addon Railway PostgreSQL).
# Écrit aussi dans les fichiers JSON en parallèle (double sécurité).
# Table unique bininga_store : key TEXT PRIMARY KEY, data TEXT (JSON), updated_at

_PG_LOCK  = threading.Lock()   # verrou global (conservé pour compatibilité)
_pg_local = threading.local()  # connexion par thread (thread-safe)

def _pg():
    """Retourne une connexion PostgreSQL par thread, ou None si indisponible.
    Chaque thread HTTP a sa propre connexion (psycopg2 n'est pas thread-safe)."""
    raw_url = os.environ.get("DATABASE_URL", "").strip().strip("\n").strip("\r")
    if not raw_url:
        return None
    url = raw_url.replace("postgres://", "postgresql://", 1) if raw_url.startswith("postgres://") else raw_url
    try:
        import psycopg2
        conn = getattr(_pg_local, 'conn', None)
        if conn is None or conn.closed:
            conn = psycopg2.connect(url, connect_timeout=5)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bininga_store (
                        key         TEXT PRIMARY KEY,
                        data        TEXT NOT NULL,
                        updated_at  TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bininga_photos (
                        id           TEXT PRIMARY KEY,
                        data         BYTEA NOT NULL,
                        content_type TEXT NOT NULL DEFAULT 'image/jpeg',
                        created_at   TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
            _pg_local.conn = conn
        return conn
    except Exception as e:
        print(f"[DB] PostgreSQL indisponible : {e}")
        _pg_local.conn = None
        return None

# ── Helper IA — Gemini + Groq fallback ─────────────────────
_GEMINI_MODEL_CACHE = None  # modèle Gemini fonctionnel mis en cache

def _groq_call(prompt: str, max_tokens: int = 800, timeout: int = 12) -> str:
    """Appelle Groq (llama gratuit) et retourne le texte généré."""
    import urllib.request as ur
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError("GROQ_API_KEY non configuré")
    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }).encode()
    req = ur.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={"content-type": "application/json", "authorization": f"Bearer {key}"},
    )
    with ur.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read())
    return resp["choices"][0]["message"]["content"].strip()

def _gemini_call(prompt: str, max_tokens: int = 800, timeout: int = 12) -> str:
    """Appelle Gemini Flash, avec fallback automatique sur Groq puis Claude."""
    import urllib.request as ur
    global _GEMINI_MODEL_CACHE
    key = os.environ.get("GEMINI_API_KEY", "").strip()

    gemini_err = None
    if key:
        candidates = [
            ("v1beta", "gemini-2.0-flash-lite"),
            ("v1beta", "gemini-2.0-flash-lite-001"),
            ("v1beta", "gemini-2.0-flash"),
            ("v1beta", "gemini-2.5-flash"),
        ]
        if _GEMINI_MODEL_CACHE:
            candidates = [_GEMINI_MODEL_CACHE] + [c for c in candidates if c != _GEMINI_MODEL_CACHE]

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4},
        }).encode()

        for (version, model) in candidates:
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={key}"
            try:
                req = ur.Request(url, data=payload, headers={"content-type": "application/json"})
                with ur.urlopen(req, timeout=timeout) as r:
                    resp = json.loads(r.read())
                parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text  = parts[0].get("text", "").strip() if parts else ""
                if not text:
                    raise ValueError("Réponse vide")
                _GEMINI_MODEL_CACHE = (version, model)
                print(f"[AI] Gemini {version}/{model}")
                return text
            except Exception as e:
                gemini_err = e
                err_str = str(e)
                if "429" in err_str or "404" in err_str:
                    continue
                raise

    # Fallback Groq
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            print(f"[AI] Gemini indisponible ({gemini_err}) — fallback Groq")
            return _groq_call(prompt, max_tokens, timeout=timeout)
        except Exception as ge:
            print(f"[AI] Groq aussi échoué : {ge}")

    # Fallback Claude (Anthropic)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        try:
            print(f"[AI] Groq indisponible — fallback Claude")
            payload_c = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req_c = ur.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload_c,
                headers={
                    "content-type": "application/json",
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with ur.urlopen(req_c, timeout=timeout) as r:
                resp_c = json.loads(r.read())
            text_c = resp_c["content"][0]["text"].strip()
            print("[AI] Claude fallback OK")
            return text_c
        except Exception as ce:
            print(f"[AI] Claude aussi échoué : {ce}")

    raise RuntimeError("Aucune API IA disponible (GEMINI_API_KEY / GROQ_API_KEY / ANTHROPIC_API_KEY non configurés)")

def _pg_load(key: str):
    """Charge une valeur depuis PostgreSQL. Retourne None si absent ou erreur."""
    conn = _pg()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM bininga_store WHERE key = %s", (key,))
            row = cur.fetchone()
            return json.loads(row[0]) if row else None
    except Exception as e:
        print(f"[DB] Erreur lecture '{key}' : {e}")
        _pg_local.conn = None   # force reconnexion au prochain appel
        return None

def _pg_save(key: str, value) -> bool:
    """Sauvegarde une valeur dans PostgreSQL. Retourne True si succès."""
    conn = _pg()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bininga_store (key, data, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE
                SET data = EXCLUDED.data, updated_at = NOW()
            """, (key, json.dumps(value, ensure_ascii=False)))
        return True
    except Exception as e:
        print(f"[DB] Erreur écriture '{key}' : {e}")
        _pg_local.conn = None   # force reconnexion au prochain appel
        return False

def _pg_save_photo(photo_id: str, data_bytes: bytes, content_type: str = "image/jpeg") -> bool:
    """Sauvegarde une photo binaire dans PostgreSQL. Retourne True si succès."""
    conn = _pg()
    if not conn:
        return False
    try:
        import psycopg2
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bininga_photos (id, data, content_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET data = EXCLUDED.data, content_type = EXCLUDED.content_type
            """, (photo_id, psycopg2.Binary(data_bytes), content_type))
        return True
    except Exception as e:
        print(f"[DB] Erreur sauvegarde photo '{photo_id}' : {e}")
        _pg_local.conn = None
        return False

def _pg_load_photo(photo_id: str):
    """Charge une photo depuis PostgreSQL. Retourne (bytes, content_type) ou None."""
    conn = _pg()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data, content_type FROM bininga_photos WHERE id = %s", (photo_id,))
            row = cur.fetchone()
            if row:
                return bytes(row[0]), row[1]
            return None
    except Exception as e:
        print(f"[DB] Erreur lecture photo '{photo_id}' : {e}")
        _pg_local.conn = None
        return None

# ── Contacts (formulaires publics) ──────────────────────────
def load_contacts() -> list:
    """Charge les contacts : PostgreSQL en priorité, fichier en fallback."""
    db = _pg_load("contacts")
    if db is not None:
        return db
    if not os.path.exists(CONTACT_FILE):
        return []
    try:
        with open(CONTACT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_contacts(contacts: list):
    """Persiste les contacts dans PostgreSQL ET dans le fichier."""
    db_ok = _pg_save("contacts", contacts)
    file_ok = False
    try:
        with open(CONTACT_FILE, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2, ensure_ascii=False)
        file_ok = True
    except Exception as e:
        print(f"[BININGA] Erreur sauvegarde contacts : {e}")
    if not db_ok and not file_ok:
        raise RuntimeError("Impossible de sauvegarder les contacts (DB et fichier indisponibles)")

_CONTACT_LOCK = threading.Lock()   # évite les race conditions en multi-thread
_CRM_LOCK     = threading.Lock()   # même protection pour le CRM
_DATA_LOCK    = threading.Lock()   # même protection pour le contenu du site

def append_contact(entry: dict):
    """Ajoute un contact et sauvegarde (lecture-modification-écriture atomique)."""
    with _CONTACT_LOCK:
        contacts = load_contacts()
        contacts.append(entry)
        save_contacts(contacts)

# ── CRM ────────────────────────────────────────────────────
def _crm_expire_date() -> str:
    """Date d'expiration = maintenant + 10 ans (rétention légale)."""
    now = datetime.now()
    try:
        return now.replace(year=now.year + CRM_RETENTION_YEARS).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return now.replace(year=now.year + CRM_RETENTION_YEARS, day=28).strftime("%Y-%m-%d %H:%M:%S")

def load_crm() -> dict:
    """Charge le CRM : PostgreSQL en priorité, fichier en fallback. Purge les expirés."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _purge(data):
        data["contacts"] = [c for c in data.get("contacts", [])
                            if c.get("expires_at", "9999-99-99") >= now_str]
        if "newsletters" not in data:
            data["newsletters"] = []
        return data

    # PostgreSQL en priorité
    db = _pg_load("crm")
    if db is not None:
        return _purge(db)

    # Fallback fichier
    if not os.path.exists(CRM_FILE):
        return {"contacts": [], "newsletters": []}
    try:
        with open(CRM_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _purge(data)
    except Exception:
        return {"contacts": [], "newsletters": []}

def save_crm(data: dict):
    # PostgreSQL (source de vérité)
    db_ok = _pg_save("crm", data)
    # Fichier JSON (backup local)
    file_ok = False
    try:
        with open(CRM_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        file_ok = True
    except Exception as e:
        print(f"[BININGA] Erreur sauvegarde CRM: {e}")
    if not db_ok and not file_ok:
        raise RuntimeError("Impossible de sauvegarder le CRM (DB et fichier indisponibles)")

# ── Migration fichiers → PostgreSQL au démarrage ───────────
def _migrate_files_to_db():
    """Importe les fichiers JSON dans PostgreSQL si la DB est vide (migration initiale)."""
    if not _pg():
        return
    # Contacts
    if _pg_load("contacts") is None and os.path.exists(CONTACT_FILE):
        try:
            with open(CONTACT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                _pg_save("contacts", data)
                print(f"[DB] Migration : {len(data)} contact(s) importé(s) depuis contacts.json")
        except Exception:
            pass
    # CRM
    if _pg_load("crm") is None and os.path.exists(CRM_FILE):
        try:
            with open(CRM_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("contacts") or data.get("newsletters"):
                _pg_save("crm", data)
                print(f"[DB] Migration : {len(data.get('contacts', []))} contact(s) CRM importé(s)")
        except Exception:
            pass
    # Contenu du site (data.json)
    if _pg_load("site_data") is None and os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                _pg_save("site_data", data)
                print(f"[DB] Migration : contenu du site importé depuis data.json")
        except Exception:
            pass
    # Users
    if _pg_load("users") is None and os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                _pg_save("users", data)
                print(f"[DB] Migration : {len(data)} utilisateur(s) importé(s) depuis users.json")
        except Exception:
            pass

# ── Init au chargement du module ───────────────────────────
# 1. Migrer les fichiers JSON → PostgreSQL (avant init_users pour récupérer le compte existant)
_migrate_files_to_db()
# 2. Créer le compte admin si inexistant (vérifie DB en priorité)
init_users()
load_sessions()
# Log statut DB
if os.environ.get("DATABASE_URL"):
    print("[DB] ✅ PostgreSQL connecté — persistance activée")
else:
    print("[DB] ⚠️  Pas de DATABASE_URL — stockage fichiers uniquement (éphémère sur Railway)")

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
        # Headers manquants — isolation cross-origin + clickjacking renforcé
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Permitted-Cross-Domain-Policies", "none")
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

    def _guard(self, path: str = "", method: str = "GET", body_size: int = 0):
        """Vérifie IP bannie + rate limit + Bouclier IA. Retourne True si bloquée."""
        ip = self.client_address[0]

        # ── Bouclier multi-couches (IA/bots/lockdown/coffre-fort/canaris) ──────
        if _AI_GUARD_ENABLED:
            headers_dict = dict(self.headers)
            blocked, reason = AI_GUARD.inspect(ip, method, path, headers_dict, body_size)
            if blocked:
                self._error(403, "Accès refusé")
                return True

        # ── Système existant (IP bannies + rate limiting) ─────────────────────
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
        self._mon_t0   = time.time()   # monitoring : chronomètre
        self._mon_path = path          # monitoring : chemin

        if self._guard(path=path, method="GET"):
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

        # ── /health — Healthcheck Railway / monitoring ──
        if path == "/health":
            db_ok = _pg() is not None
            self._json({
                "ok":        True,
                "status":    "healthy",
                "ts":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sessions":  len(ACTIVE_SESSIONS),
                "blocked":   len(BLOCKED_IPS),
                "database":  "postgresql_ok" if db_ok else "no_database",
            })
            return

        if path in ("/api/load", "/data.json"):
            self._json(load_data())
            return

        # ── /api/debug-ai (diagnostic clé IA — admin uniquement) ──
        if path == "/api/debug-ai":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            import urllib.request as _ur
            gemini = os.environ.get("GEMINI_API_KEY", "").strip()
            groq   = os.environ.get("GROQ_API_KEY", "")
            # Lister les modèles disponibles
            models_list = []
            try:
                url_list = f"https://generativelanguage.googleapis.com/v1/models?key={gemini}"
                with _ur.urlopen(url_list, timeout=10) as r:
                    data_m = json.loads(r.read())
                models_list = [m.get("name","") for m in data_m.get("models", [])]
            except Exception as em:
                models_list = [f"Erreur ListModels : {em}"]
            # Test appel Gemini
            gemini_test = ""
            flash_model = next((m.split("/")[-1] for m in models_list if "flash" in m and "preview" not in m), None)
            try:
                if flash_model:
                    import urllib.request as ur2
                    url_g = f"https://generativelanguage.googleapis.com/v1/models/{flash_model}:generateContent?key={gemini}"
                    payload = json.dumps({"contents": [{"parts": [{"text": "Réponds juste: OK"}]}], "generationConfig": {"maxOutputTokens": 10}}).encode()
                    req = ur2.Request(url_g, data=payload, headers={"content-type": "application/json"})
                    with ur2.urlopen(req, timeout=15) as r:
                        resp = json.loads(r.read())
                    reply = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
                    gemini_test = f"✅ {flash_model} répond : {reply}"
                else:
                    gemini_test = "❌ Aucun modèle flash trouvé"
            except Exception as e:
                gemini_test = f"❌ Erreur : {e}"
            self._json({
                # Ne jamais renvoyer de préfixe de clé côté client
                "GEMINI_API_KEY": f"{'✅ présente ('+str(len(gemini))+' chars)' if gemini else '❌ ABSENTE'}",
                "GROQ_API_KEY":   f"{'✅ présente' if groq else '❌ ABSENTE'}",
                "models_disponibles": models_list,
                "modele_selectionne": flash_model or "aucun",
                "gemini_test":    gemini_test,
            })
            return

        if path == "/api/contacts":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "editeur", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            all_contacts = load_contacts()
            def _is_audience(c):
                return c.get("type") == "bininga_audiences" or c.get("source") == "bininga_audiences"
            def _is_newsletter(c):
                return c.get("type") == "bininga_newsletter" or c.get("source") == "bininga_newsletter"
            audiences = [c for c in all_contacts if _is_audience(c)]
            contacts  = [c for c in all_contacts if not _is_audience(c) and not _is_newsletter(c)]
            self._json({"ok": True, "audiences": audiences, "contacts": contacts})
            return

        if path == "/api/stats":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "editeur", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            all_c = load_contacts()
            def _is_aud(c):
                return c.get("type") == "bininga_audiences" or c.get("source") == "bininga_audiences"
            def _is_nl(c):
                return c.get("type") == "bininga_newsletter" or c.get("source") == "bininga_newsletter"
            audiences = [c for c in all_c if _is_aud(c) and c.get("objet") != "Réclamation"]
            recls     = [c for c in all_c if _is_aud(c) and c.get("objet") == "Réclamation"]
            contacts  = [c for c in all_c if not _is_aud(c) and not _is_nl(c)]
            self._json({
                "ok":          True,
                "aud_total":   len(audiences),
                "aud_wait":    len([a for a in audiences if not a.get("_status") or a["_status"] == "en_attente"]),
                "aud_progress":len([a for a in audiences if a.get("_status") == "en_cours"]),
                "aud_done":    len([a for a in audiences if a.get("_status") == "traite"]),
                "recl_total":  len(recls),
                "recl_wait":   len([r for r in recls if not r.get("_status") or r["_status"] != "traite"]),
                "ct_total":    len(contacts),
                "ct_unread":   len([c for c in contacts if not c.get("_status") or c["_status"] == "non_lu"]),
                **({"visitors": _mon.get_visit_stats()} if _MON else {}),
            })
            return

        if path == "/api/visit-stats":
            # Public — pas de token requis (juste les compteurs)
            if _MON:
                self._json({"ok": True, **_mon.get_visit_stats()})
            else:
                self._json({"ok": True, "total": 0, "today": 0, "prog_views": 0})
            return

        # ── /api/events — SSE notifications temps réel ────────────────────────
        if path == "/api/events":
            qs_ev = parse_qs(urlparse(self.path).query)
            token_ev = qs_ev.get("t", [""])[0]
            if not has_role(token_ev, "admin", "ministre"):
                self._error(401, "Non autorisé")
                return
            client_q = _queue_mod.Queue(maxsize=200)
            with _SSE_LOCK:
                _SSE_CLIENTS.append(client_q)
            sse_origin = self._cors_origin()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            if sse_origin:
                self.send_header("Access-Control-Allow-Origin", sse_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        msg = client_q.get(timeout=25)
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except _queue_mod.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                with _SSE_LOCK:
                    try: _SSE_CLIENTS.remove(client_q)
                    except ValueError: pass
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
            ai_report = AI_GUARD.get_report() if _AI_GUARD_ENABLED else {}
            self._json({
                "ok": True,
                "blocked": sorted(BLOCKED_IPS),
                "suspects": suspects,
                "attacks": load_attacks(100),
                "ai_guard": ai_report,
            })
            return

        # ── /api/security/bouclier — Rapport complet du Bouclier IA ─────────────
        if path == "/api/security/bouclier":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            if not _AI_GUARD_ENABLED:
                self._json({"ok": False, "message": "Bouclier IA non disponible"}, 503)
                return
            self._json({"ok": True, **AI_GUARD.get_report()})
            return

        # ── /api/security/lockdown — Activer/désactiver le mode lockdown ─────────
        if path == "/api/security/lockdown":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            if not _AI_GUARD_ENABLED:
                self._json({"ok": False, "message": "Bouclier IA non disponible"}, 503)
                return
            qs_ld = parse_qs(urlparse(self.path).query)
            action = qs_ld.get("action", ["status"])[0]
            if action == "activate":
                duration = int(qs_ld.get("duration", ["900"])[0])
                reason = qs_ld.get("reason", ["Admin manual"])[0]
                AI_GUARD.lockdown.activate(reason, duration)
                audit_log("LOCKDOWN_ADMIN", ip, f"Lockdown activé {duration}s — {reason}")
                self._json({"ok": True, "message": f"Mode sécurité LOCKDOWN activé ({duration}s)"})
            elif action == "deactivate":
                AI_GUARD.lockdown.deactivate()
                audit_log("LOCKDOWN_ADMIN", ip, "Lockdown désactivé manuellement")
                self._json({"ok": True, "message": "Mode sécurité levé"})
            else:
                self._json({"ok": True, "status": AI_GUARD.lockdown.status()})
            return

        # ── /api/monitoring/* — dashboard de surveillance ──────────────────────
        if path.startswith("/api/monitoring/"):
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            if not _MON:
                self._json({"ok": False, "message": "Module monitoring non disponible"}, 503)
                return
            qs_mon = parse_qs(urlparse(self.path).query)

            if path == "/api/monitoring/summary":
                data = _mon.get_summary(len(ACTIVE_SESSIONS), len(BLOCKED_IPS))
                self._json({"ok": True, **data})
                return

            if path == "/api/monitoring/requests":
                limit_r = min(int(qs_mon.get("limit", [200])[0]), 500)
                pf      = qs_mon.get("path", [""])[0]
                self._json({"ok": True, "requests": _mon.get_requests(limit_r, pf)})
                return

            if path == "/api/monitoring/errors":
                self._json({"ok": True, "errors": _mon.get_errors(100)})
                return

            if path == "/api/monitoring/alerts":
                resolved = qs_mon.get("resolved", ["0"])[0] == "1"
                self._json({"ok": True, "alerts": _mon.get_alerts(resolved)})
                return

            if path == "/api/monitoring/endpoints":
                hours_e = int(qs_mon.get("hours", [24])[0])
                self._json({"ok": True, "endpoints": _mon.get_top_endpoints(hours_e)})
                return

            if path == "/api/monitoring/latency":
                hours_l = int(qs_mon.get("hours", [6])[0])
                self._json({"ok": True, "chart": _mon.get_latency_chart(hours_l)})
                return

            if path == "/api/monitoring/report":
                self._json({"ok": True, "report": _mon.generate_report()})
                return

            self._json({"ok": False, "message": "Endpoint monitoring inconnu"}, 404)
            return

        if path == "/api/2fa/status":
            token = self.headers.get("X-Admin-Token", "")
            session = get_session(token)
            if not session:
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            user = find_user(session["username"])
            self._json({"ok": True, "has_2fa": bool((user or {}).get("totp_secret", ""))})
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
            users = [{"username": u["username"], "role": u["role"], "nom": u["nom"],
                      "created_by": u.get("created_by", "")}
                     for u in all_users]
            self._json({"ok": True, "users": users})
            return

        # ── /api/files — Navigateur de dossiers images ──
        if path == "/api/files":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "editeur", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            qs = parse_qs(urlparse(self.path).query)
            req_dir = qs.get("dir", ["images"])[0]
            # Sécurité : autoriser uniquement les sous-dossiers de images/
            safe_dir = posixpath.normpath(req_dir).lstrip("/")
            if not safe_dir.startswith("images"):
                safe_dir = "images"
            abs_dir = os.path.realpath(os.path.join(BASE_DIR, safe_dir))
            if not abs_dir.startswith(BASE_DIR + os.sep) and abs_dir != BASE_DIR:
                self._json({"ok": False, "message": "Chemin non autorisé"}, 403)
                return
            IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
            files = []
            folders = []
            try:
                for entry in sorted(os.scandir(abs_dir), key=lambda e: (not e.is_dir(), e.name.lower())):
                    if entry.is_dir():
                        folders.append({"name": entry.name, "path": safe_dir + "/" + entry.name})
                    elif entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in IMAGE_EXTS:
                            rel = safe_dir + "/" + entry.name
                            files.append({"name": entry.name, "path": rel})
            except FileNotFoundError:
                pass
            self._json({"ok": True, "dir": safe_dir, "folders": folders, "files": files})
            return

        # ── /api/sinistre-photo/<id> — Sert une photo de réclamation depuis PostgreSQL ──
        if path.startswith("/api/sinistre-photo/"):
            photo_id = path[len("/api/sinistre-photo/"):]
            # Valider l'ID (caractères alphanumériques + _ seulement)
            if not photo_id or not all(c.isalnum() or c in "_" for c in photo_id):
                self.send_error(400)
                return
            result = _pg_load_photo(photo_id)
            if not result:
                self.send_error(404)
                return
            img_bytes, content_type = result
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(img_bytes)))
            self.send_header("Cache-Control", "max-age=86400, private")
            self.end_headers()
            self.wfile.write(img_bytes)
            return

        # ── /api/crm — Liste des contacts CRM avec pagination et recherche ──
        if path == "/api/crm":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            qs      = parse_qs(urlparse(self.path).query)
            page    = max(1, int(qs.get("page",  ["1"])[0]))
            limit   = min(5000, max(10, int(qs.get("limit", ["50"])[0])))
            q       = qs.get("q",      [""])[0].lower().strip()
            f_src   = qs.get("source", [""])[0]
            f_nl    = qs.get("nl",     [""])[0]    # "oui" / "non"
            crm     = load_crm()
            all_c   = crm.get("contacts", [])
            # Filtrage
            filtered = []
            for c in all_c:
                if f_src and c.get("source") != f_src:
                    continue
                if f_nl == "oui" and not (c.get("newsletter") and c.get("email")):
                    continue
                if f_nl == "non" and (c.get("newsletter") and c.get("email")):
                    continue
                if q:
                    hay = f"{c.get('nom','')} {c.get('prenom','')} {c.get('email','')} {c.get('telephone','')} {c.get('sujet','')} {' '.join(c.get('tags',[]))}".lower()
                    if q not in hay:
                        continue
                filtered.append(c)
            total    = len(filtered)
            pages    = max(1, (total + limit - 1) // limit)
            start    = (page - 1) * limit
            contacts = filtered[start:start + limit]
            self._json({
                "ok":        True,
                "contacts":  contacts,
                "newsletters": crm.get("newsletters", []),
                "total":     total,
                "page":      page,
                "pages":     pages,
                "limit":     limit,
                "newsletter_count": sum(1 for c in all_c if c.get("newsletter") and c.get("email")),
            })
            return

        # ── /api/crm/export — Export CSV ──
        if path == "/api/crm/export":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            import csv as _csv, io as _io
            crm = load_crm()
            contacts = crm.get("contacts", [])
            out = _io.StringIO()
            fields = ["id", "created_at", "expires_at", "source", "nom", "prenom",
                      "email", "telephone", "sujet", "message", "tags", "statut", "newsletter"]
            writer = _csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for c in contacts:
                row = {k: c.get(k, "") for k in fields}
                row["tags"]       = ", ".join(c.get("tags", []))
                row["newsletter"] = "oui" if c.get("newsletter") else "non"
                writer.writerow(row)
            csv_bytes = ("\ufeff" + out.getvalue()).encode("utf-8")  # BOM Excel
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="crm_contacts.csv"')
            self.send_header("Content-Length", len(csv_bytes))
            self._security_headers()
            self.end_headers()
            self.wfile.write(csv_bytes)
            audit_log("CRM_EXPORT", self.client_address[0], "Export CSV CRM")
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

        # ── /api/youtube — liste des contenus YouTube (GET) ──
        if path == "/api/youtube":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre", "editeur"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            vids = _pg_load("youtube")
            if vids is None:
                vids = []
                if os.path.exists(YOUTUBE_FILE):
                    try:
                        with open(YOUTUBE_FILE, "r", encoding="utf-8") as f:
                            vids = json.load(f)
                    except Exception:
                        vids = []
            self._json({"ok": True, "videos": vids})
            return

        # ── /api/editorial — liste des articles éditoriaux (GET) ──
        if path == "/api/editorial":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre", "editeur"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            data = _pg_load("editorial")
            if data is None:
                data = []
                if os.path.exists(EDITORIAL_FILE):
                    try:
                        with open(EDITORIAL_FILE, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception:
                        data = []
            self._json({"ok": True, "articles": data, "total": len(data)})
            return

        # ── Protection URL admin ────────────────────────────────────────────────
        # /admin.html est un piège : quiconque y accède est banni 24h.
        # L'espace admin est accessible UNIQUEMENT via ADMIN_SECRET_PATH.
        path_clean = path.lstrip("/")
        if path_clean in ("admin.html", "admin.htm", "admin"):
            # Piège canari : ban immédiat 24h + log
            # (sauf pour les IPs de confiance : localhost, tests, admin whitelisté)
            _admin_probe_trusted = (_is_trusted_ip(ip) or
                                    (_AI_GUARD_ENABLED and AI_GUARD.lockdown.is_whitelisted(ip)))
            if not _admin_probe_trusted:
                record_attack(ip, "ADMIN_PROBE", 30, f"Sonde URL admin publique: {path}")
                audit_log("ADMIN_PROBE", ip, f"Accès /admin.html depuis {ip} — banni 24h")
                if _AI_GUARD_ENABLED:
                    AI_GUARD._temp_ban(ip, 86400, f"Sonde admin URL: {path}")
            self._error(404, "Page non trouvée")
            return
        # URL secrète de l'espace admin → sert admin.html
        if path_clean == ADMIN_SECRET_PATH or path_clean == ADMIN_SECRET_PATH + ".html":
            safe_admin = _safe_path("admin.html")
            if safe_admin and os.path.isfile(safe_admin):
                with open(safe_admin, "rb") as f:
                    content = f.read()
                text = content.decode("utf-8", errors="replace")
                text = text.replace("static/admin.js",  f"static/admin.js?v={BUILD_VERSION}")
                text = text.replace("static/admin.css", f"static/admin.css?v={BUILD_VERSION}")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(text.encode("utf-8")))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("X-Robots-Tag", "noindex, nofollow")
                self._security_headers()
                self.end_headers()
                self.wfile.write(text.encode("utf-8"))
                return
            self._error(404, "Page non trouvée")
            return

        # ── Fichiers statiques avec protection path traversal ──
        relative = "index.html" if path in ("/", "") else path.lstrip("/")
        safe = _safe_path(relative)
        if safe and os.path.isfile(safe):
            try:
                mime   = self._mime(safe)
                origin = self._cors_origin()
                is_video = mime.startswith("video/") or mime.startswith("audio/")
                file_size = os.path.getsize(safe)

                # ── Range request (indispensable pour la lecture vidéo) ──
                range_header = self.headers.get("Range", "")
                if is_video and range_header.startswith("bytes="):
                    try:
                        rng    = range_header[6:]
                        start_s, end_s = rng.split("-", 1)
                        start  = int(start_s) if start_s else 0
                        end    = int(end_s)   if end_s   else file_size - 1
                        end    = min(end, file_size - 1)
                        length = end - start + 1
                        with open(safe, "rb") as f:
                            f.seek(start)
                            chunk = f.read(length)
                        self.send_response(206)
                        self.send_header("Content-Type", mime)
                        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                        self.send_header("Content-Length", length)
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Cache-Control", "public, max-age=86400")
                        if origin:
                            self.send_header("Access-Control-Allow-Origin", origin)
                        self._security_headers()
                        self.end_headers()
                        self.wfile.write(chunk)
                        return
                    except Exception:
                        pass  # Fallback vers la réponse complète

                with open(safe, "rb") as f:
                    content = f.read()

                # Injection version build dans les HTML pour cache-busting automatique
                if mime.startswith("text/html"):
                    text = content.decode("utf-8", errors="replace")
                    text = text.replace("static/admin.js", f"static/admin.js?v={BUILD_VERSION}")
                    text = text.replace("static/admin.css", f"static/admin.css?v={BUILD_VERSION}")
                    text = text.replace("static/index.js", f"static/index.js?v={BUILD_VERSION}")
                    text = text.replace("static/index.css", f"static/index.css?v={BUILD_VERSION}")
                    # Injecter l'URL secrète de l'admin (gestion.html, ministre.html…)
                    text = text.replace("__ADMIN_PATH__", f"/{ADMIN_SECRET_PATH}")
                    content = text.encode("utf-8")

                # Gzip compression pour texte/HTML/CSS/JS/JSON (pas pour vidéo)
                accept_enc = self.headers.get("Accept-Encoding", "")
                can_gzip = not is_video and "gzip" in accept_enc and mime.startswith((
                    "text/", "application/json", "application/javascript"
                ))
                if can_gzip:
                    content = gzip.compress(content, compresslevel=6)
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", len(content))
                if is_video:
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "public, max-age=86400")
                if can_gzip:
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Vary", "Accept-Encoding")
                if origin:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                if mime.startswith("text/html") or mime == "application/json":
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                elif mime.startswith("image/"):
                    self.send_header("Cache-Control", "public, max-age=86400")
                elif mime in ("text/css", "text/javascript"):
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
        self._mon_t0   = time.time()   # monitoring : chronomètre
        self._mon_path = path          # monitoring : chemin

        # ── /api/test/reset — mode test UNIQUEMENT, localhost UNIQUEMENT ──
        if BININGA_TEST and path == "/api/test/reset":
            # Double protection : localhost uniquement même en mode test
            if ip not in ("127.0.0.1", "::1", "localhost"):
                record_attack(ip, "TEST_RESET_ATTEMPT", 25, "Tentative reset depuis IP non-locale en mode test")
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            LOGIN_ATTEMPTS.clear()
            ATTACK_SCORES.clear()
            BLOCKED_IPS.clear()
            REQUEST_COUNTS.clear()
            CHAT_RATE_COUNTS.clear()
            print(f"[SECURITY] /api/test/reset appelé par {ip} — BININGA_TEST=1")
            self._json({"ok": True, "message": "All security state reset (test mode)"})
            return

        raw_length = int(self.headers.get("Content-Length", 0))
        if self._guard(path=path, method="POST", body_size=raw_length):
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
            # Rate limiting par IP
            if _is_rate_limited(ip):
                self._json({"ok": False, "message": "Trop de tentatives. Réessayez dans 5 minutes."}, 429)
                return
            try:
                creds    = json.loads(body.decode("utf-8"))
                username = creds.get("username", "")
                password = creds.get("password", "")
                totp_code = str(creds.get("totp_code", "")).strip()

                # ── Rate limiting par NOM D'UTILISATEUR (anti-attaque distribuée) ──
                # Même si l'attaquant change d'IP à chaque essai, le username est bloqué.
                ukey = username.lower().strip()
                urec = USERNAME_ATTEMPTS.get(ukey, {})
                if urec.get("blocked_until", 0) > time.time():
                    wait = int(urec["blocked_until"] - time.time())
                    audit_log("USERNAME_LOCKED", ip, f"Username {username} verrouillé — encore {wait}s")
                    time.sleep(LOGIN_FAIL_DELAY)
                    self._json({"ok": False, "message": f"Ce compte est temporairement verrouillé. Réessayez dans {wait//60+1} min."}, 429)
                    return

                user     = find_user(username)
                if user and _verify_password(password, user.get("password_hash", "")):
                    # Vérification 2FA si activé
                    totp_secret = user.get("totp_secret", "")
                    if totp_secret:
                        if not totp_code:
                            # Signaler que 2FA est requis sans bloquer
                            time.sleep(LOGIN_FAIL_DELAY)
                            self._json({"ok": False, "require_2fa": True,
                                        "message": "Code d'authentification 2FA requis"}, 401)
                            return
                        if not _totp_verify(totp_secret, totp_code):
                            _record_failed_login(ip)
                            record_attack(ip, "2FA_FAIL", 3, f"2FA échoué pour {username}")
                            audit_log("2FA_FAIL", ip, f"Code 2FA invalide pour {username}")
                            time.sleep(LOGIN_FAIL_DELAY)
                            self._json({"ok": False, "message": "Code 2FA invalide"}, 401)
                            return
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
                    USERNAME_ATTEMPTS.pop(ukey, None)   # reset compteur username
                    token      = secrets.token_hex(32)
                    csrf_token = secrets.token_hex(24)
                    is_trusted = ip in TRUSTED_IPS
                    sess_ttl   = SESSION_TTL_LONG if is_trusted else SESSION_TTL
                    ACTIVE_SESSIONS[token] = {
                        "username":   user["username"],
                        "role":       user["role"],
                        "nom":        user.get("nom", user["username"]),
                        "created_at": time.time(),
                        "csrf_token": csrf_token,
                        "ttl":        sess_ttl,
                        "trusted_ip": is_trusted,
                    }
                    save_sessions()
                    duration_label = "7 jours" if is_trusted else "24 heures"
                    print(f"[BININGA] 🔓 Connexion : {username} ({user['role']}) — {datetime.now().strftime('%H:%M:%S')} {'[IP de confiance — session 7j]' if is_trusted else ''}")
                    audit_log("LOGIN_OK", ip, f"Connexion de {username} ({user['role']}){' [2FA]' if totp_secret else ''}{' [IP fiable — 7j]' if is_trusted else ''}")
                    self._json({"ok": True, "token": token, "csrf_token": csrf_token,
                                "role": user["role"], "nom": user.get("nom", username),
                                "username": user["username"],
                                "is_main_admin": username == ADMIN_USER,
                                "has_2fa": bool(totp_secret),
                                "session_duration": duration_label,
                                "trusted_ip": is_trusted})
                else:
                    _record_failed_login(ip)
                    # Compteur par username (anti-attaque distribuée)
                    urec = USERNAME_ATTEMPTS.get(ukey, {"count": 0, "blocked_until": 0})
                    urec["count"] = urec.get("count", 0) + 1
                    if urec["count"] >= USERNAME_MAX_ATTEMPTS:
                        urec["blocked_until"] = time.time() + USERNAME_LOCKOUT_SECS
                        urec["count"] = 0
                        audit_log("USERNAME_BRUTE", ip, f"Username {username} verrouillé 1h après {USERNAME_MAX_ATTEMPTS} échecs distribués")
                        record_attack(ip, "USERNAME_BRUTE", 15, f"Attaque distribuée sur {username}")
                    USERNAME_ATTEMPTS[ukey] = urec
                    record_attack(ip, "LOGIN_FAIL", 2, f"Échec login user: {username}")
                    print(f"[BININGA] ⛔ Tentative échouée : {username} — {datetime.now().strftime('%H:%M:%S')}")
                    audit_log("LOGIN_FAIL", ip, f"Identifiant ou mot de passe incorrect (user: {username})")
                    time.sleep(LOGIN_FAIL_DELAY)
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
            uid      = secrets.token_hex(6)
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            photo_id = f"{ts}_{uid}"
            # Détecter le type MIME réel
            ext = safe_name.lower().rsplit(".", 1)[-1] if "." in safe_name else "jpg"
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "png": "image/png", "webp": "image/webp"}
            content_type = mime_map.get(ext, "image/jpeg")
            # Stocker dans PostgreSQL (priorité) — survit aux redéploiements
            if _pg_save_photo(photo_id, data_bytes, content_type):
                photo_path = f"/api/sinistre-photo/{photo_id}"
            else:
                # Fallback filesystem si pas de PostgreSQL
                fname = f"{photo_id}.jpg"
                os.makedirs(os.path.join("images", "sinistres"), exist_ok=True)
                with open(os.path.join("images", "sinistres", fname), "wb") as fh:
                    fh.write(data_bytes)
                photo_path = f"images/sinistres/{fname}"
            audit_log("SINISTRE_PHOTO", ip, f"Photo sinistre reçue : {photo_id}")
            self._json({"ok": True, "path": photo_path})
            return

        # ── /api/chat (public — chatbot assistant du site) ──
        if path == "/api/chat":
            ip = self.client_address[0]
            if check_chat_rate(ip):
                self._json({"ok": False, "message": "Trop de messages, patientez 1 minute."}, 429)
                return
            try:
                payload  = json.loads(body.decode("utf-8"))
                question = str(payload.get("message", "")).strip()[:1000]
                if not question:
                    self._json({"ok": False, "message": "Message vide"}, 400)
                    return

                q = question.lower()
                import random

                # Charger le contenu depuis PostgreSQL (ou fichier en fallback)
                data      = load_data()
                hero      = data.get("hero", {})
                about     = data.get("about", {})
                stats     = data.get("stats", [])
                actus     = data.get("actus", {})
                programme = data.get("programme", {})
                parcours  = data.get("parcours", [])
                contact   = data.get("contact", {})

                nom  = f"{hero.get('firstName','')} {hero.get('lastName','')}".strip() or "Ange Aimé Wilfrid BININGA"
                role = hero.get("role", "Garde des Sceaux, Ministre de la Justice, Député d'Ewo")
                reply = None

                # ── Salutations ───────────────────────────────────────────────
                if any(w in q for w in ["bonjour", "bonsoir", "salut", "bonne journée", "bonne soirée", "hey"]) and not any(w in q for w in ["hello", "hi", "how are", "english", "speak"]):
                    reply = random.choice([
                        f"Bonjour ! Bienvenue sur le site officiel de {nom}. Je suis DA, son assistant virtuel. Je peux vous renseigner sur son parcours, ses fonctions, son programme, ses actualités ou la façon de le contacter. Que souhaitez-vous savoir ?",
                        f"Bonjour et bienvenue ! Je suis DA, l'assistant virtuel du Ministre {nom.split()[-1]}. Posez-moi vos questions sur sa biographie, son action ou son programme. Comment puis-je vous aider ?",
                        f"Bonsoir ! Heureux de vous accueillir sur ce site. Je suis DA, l'assistant virtuel dédié à {nom}. Comment puis-je vous aider aujourd'hui ?",
                    ])

                # ── Qui est DA ────────────────────────────────────────────────
                elif any(w in q for w in ["qui es-tu", "qui es tu", "tu es qui", "c'est quoi da", "présente-toi", "tu t'appelles", "tu es quoi"]):
                    reply = f"Je suis DA, l'assistant virtuel du site officiel de {nom}. Je suis là pour répondre à vos questions sur son parcours, ses fonctions, son programme, ses actualités et ses engagements. Je ne suis pas une intelligence artificielle — je me base uniquement sur les informations publiées sur ce site."

                # ── Âge / naissance ───────────────────────────────────────────
                elif any(w in q for w in ["âge", "age", "né", "naissance", "date de naissance", "quel age", "quel âge", "né quand", "né où", "né a", "né à"]):
                    reply = f"{nom} est né à Brazzaville, en République du Congo. Pour toute précision complémentaire, je vous invite à consulter la section biographie du site ou à contacter directement l'équipe."

                # ── Développeur / site ────────────────────────────────────────
                elif any(w in q for w in ["développé", "developpé", "créé", "crée", "site web", "développeur", "developpeur", "qui a fait", "conception", "webmaster", "fait le site", "créé le site"]):
                    reply = "Ce site officiel a été développé par Rodrin Bakala."

                # ── Présentation / biographie ─────────────────────────────────
                elif any(w in q for w in ["qui est", "qui est-il", "présente", "présentation", "c'est qui", "c est qui", "biographie", "bio"]):
                    intro = about.get("intro", "")
                    paras = about.get("paragraphs", [])
                    if intro:
                        reply = intro[:500] + ("..." if len(intro) > 500 else "")
                    elif paras:
                        reply = paras[0][:500] + ("..." if len(paras[0]) > 500 else "")
                    else:
                        reply = f"{nom} est {role}. Docteur en droit et Inspecteur principal du Trésor public, il représente la 1re circonscription d'Ewo à l'Assemblée Nationale depuis 2017."

                # ── Parcours / formation / carrière ───────────────────────────
                elif any(w in q for w in ["parcours", "carrière", "formation", "études", "doctorat", "trésor", "inspecteur", "diplôme", "université", "étudié"]):
                    paras = about.get("paragraphs", [])
                    if len(paras) > 1:
                        reply = paras[1][:500] + ("..." if len(paras[1]) > 500 else "")
                    elif paras:
                        reply = paras[0][:500] + ("..." if len(paras[0]) > 500 else "")
                    else:
                        reply = f"{nom} est Docteur en droit et Inspecteur principal du Trésor public. Il a exercé plusieurs fonctions ministérielles importantes au Congo avant d'être élu Député d'Ewo."

                # ── Fonctions / titre / ministre ──────────────────────────────
                elif any(w in q for w in ["fonction", "rôle", "titre", "ministre", "garde des sceaux", "mandat", "poste", "assemblée", "député", "actuel"]):
                    reply = f"{nom} est actuellement {role}. Il est Député de la 1re circonscription d'Ewo depuis 2017, et a exercé les fonctions de Ministre des Finances avant de prendre en charge la Justice."

                # ── Justice / réformes ────────────────────────────────────────
                elif any(w in q for w in ["justice", "loi", "droit", "réforme", "tribunal", "judiciaire", "juridique", "législation", "code", "pénal", "civil"]):
                    reply = f"En tant que Garde des Sceaux et Ministre de la Justice, {nom} pilote les grandes réformes judiciaires du Congo. Il a notamment porté la modernisation du système judiciaire congolais et renforcé l'accès à la justice pour les citoyens."

                # ── Corruption / HALC ─────────────────────────────────────────
                elif any(w in q for w in ["corruption", "halc", "anti-corruption", "anticorruption", "intégrité", "transparence", "haute autorité"]):
                    reply = f"Sous l'impulsion de {nom}, la loi instituant la Haute Autorité de Lutte contre la Corruption (HALC) a été adoptée en 2018 à 107 voix pour à l'Assemblée Nationale. C'est l'une des réformes majeures de son action ministérielle pour la transparence et l'intégrité publique."

                # ── Droits humains / peuples autochtones ──────────────────────
                elif any(w in q for w in ["droits humains", "droits de l'homme", "autochtone", "peuples autochtones", "pygmée", "droits fondamentaux", "libertés"]):
                    reply = f"{nom} s'engage activement pour la promotion des droits humains et la protection des peuples autochtones au Congo. Cette mission fait partie intégrante de ses attributions au Ministère de la Justice."

                # ── Coopération internationale ────────────────────────────────
                elif any(w in q for w in ["coopération", "international", "france", "darmanin", "étranger", "diplomatique", "partenaire", "accord", "traité"]):
                    reply = f"{nom} est actif sur le plan de la coopération judiciaire internationale. Il a notamment reçu son homologue français Gérald Darmanin à Paris dans le cadre du renforcement de la coopération judiciaire entre la France et la République du Congo."

                # ── Finances / économie (ancienne fonction) ────────────────────
                elif any(w in q for w in ["finance", "économie", "budget", "fiscalité", "trésor", "ministre des finances", "économique"]):
                    reply = f"Avant de prendre en charge le Ministère de la Justice, {nom} a exercé les fonctions de Ministre chargé des Finances. Son expertise en droit et en finances publiques est l'un de ses atouts majeurs."

                # ── Programme ─────────────────────────────────────────────────
                elif any(w in q for w in ["programme", "projet", "plan", "engagements", "promesse", "objectif", "vision", "axe", "priorité"]):
                    axes = programme.get("axes", [])
                    if axes:
                        titres = [ax.get("title","") for ax in axes[:5] if isinstance(ax,dict) and ax.get("title")]
                        reply = f"Le programme de {nom} s'articule autour des axes suivants : {', '.join(titres)}. Consultez la section Programme du site pour le détail complet de ses engagements."
                    else:
                        reply = f"Le programme électoral de {nom} couvre des axes forts pour la justice, le développement local d'Ewo, la lutte contre la corruption et la représentation des citoyens. Consultez la section Programme pour le détail complet."

                # ── Actualités ────────────────────────────────────────────────
                elif any(w in q for w in ["actuali", "nouvelle", "récent", "dernière", "info", "événement", "agenda", "quoi de neuf", "news"]):
                    slides = actus.get("slides", [])
                    items  = [s.get("title","").replace("\n"," ") for s in slides[:3] if isinstance(s,dict) and s.get("title")]
                    if items:
                        reply = "Dernières actualités disponibles sur ce site :\n• " + "\n• ".join(items) + "\n\nRetrouvez toutes les actualités dans la section dédiée du site."
                    else:
                        reply = f"Retrouvez toutes les actualités de {nom} dans la section Actualités du site, régulièrement mise à jour avec ses interventions, déplacements et actions."

                # ── Ewo / circonscription / Cuvette ──────────────────────────
                elif any(w in q for w in ["ewo", "cuvette", "circonscription", "territoire", "région", "villageois", "population", "congo", "brazzaville", "lokomo"]):
                    reply = f"{nom} est le Député de la 1re circonscription d'Ewo, dans la Cuvette-Ouest (République du Congo). Il s'engage personnellement auprès des populations locales, défend leurs intérêts à l'Assemblée Nationale et œuvre pour le développement de cette région."

                # ── Audience / demande d'audience ────────────────────────────
                elif any(w in q for w in ["audience", "rendez-vous", "rencontrer", "rencontrez", "voir le ministre", "solliciter", "demande d'audience", "rdv"]):
                    reply = f"Pour solliciter une audience auprès de {nom}, soumettez votre demande via le formulaire disponible sur ce site. Il n'y a pas de rendez-vous direct — chaque demande est examinée et traitée selon les disponibilités du cabinet. Remplissez bien vos coordonnées et l'objet de votre demande."

                # ── Contact / email ───────────────────────────────────────────
                elif any(w in q for w in ["contact", "contacter", "joindre", "email", "mail", "écrire", "formulaire", "message", "téléphone", "adresse"]):
                    email = contact.get("email", "")
                    tel   = contact.get("phone", "")
                    if email or tel:
                        details = []
                        if email: details.append(f"email : {email}")
                        if tel:   details.append(f"téléphone : {tel}")
                        reply = f"Pour contacter l'équipe de {nom} : {', '.join(details)}. Vous pouvez aussi utiliser le formulaire de contact directement sur ce site."
                    else:
                        reply = f"Pour contacter l'équipe de {nom}, utilisez le formulaire de contact disponible en bas de ce site. L'équipe vous répondra dans les meilleurs délais."

                # ── Réclamation / sinistre ────────────────────────────────────
                elif any(w in q for w in ["réclamation", "reclamation", "plainte", "sinistre", "problème", "signaler", "signalement", "soumettre", "déposer"]):
                    reply = f"Vous pouvez soumettre une réclamation ou signaler un sinistre directement via le formulaire prévu à cet effet sur ce site. Votre dossier sera transmis à l'équipe de {nom} pour traitement."

                # ── Newsletter / inscription ──────────────────────────────────
                elif any(w in q for w in ["newsletter", "inscription", "s'abonner", "abonnement", "suivre", "email actualité", "recevoir"]):
                    reply = f"Pour rester informé des actualités et actions de {nom}, vous pouvez vous inscrire à la newsletter via le formulaire disponible sur ce site. Vous recevrez régulièrement les dernières informations."

                # ── Galerie / photos / vidéos ─────────────────────────────────
                elif any(w in q for w in ["galerie", "photo", "image", "vidéo", "album", "photos", "voir"]):
                    reply = f"La galerie du site regroupe des photos et vidéos des activités, déplacements et événements de {nom}. Consultez la section Galerie pour découvrir l'ensemble des contenus visuels disponibles."

                # ── Livre / publication ───────────────────────────────────────
                elif any(w in q for w in ["livre", "publication", "ouvrage", "écrit", "commande", "commander", "bouquin"]):
                    reply = f"{nom} a publié des ouvrages dans le domaine du droit. Vous pouvez commander ses livres via le formulaire disponible sur ce site."

                # ── Réseaux sociaux ───────────────────────────────────────────
                elif any(w in q for w in ["facebook", "twitter", "instagram", "linkedin", "réseau", "réseaux sociaux", "social media", "tiktok", "youtube"]):
                    reply = f"Pour suivre l'actualité de {nom} sur les réseaux sociaux, consultez la section contact ou le pied de page de ce site où figurent les liens vers ses profils officiels."

                # ── Chiffres / bilan / statistiques ──────────────────────────
                elif any(w in q for w in ["chiffre", "bilan", "résultat", "combien", "statistique", "réalisation", "bilan", "nombre"]):
                    if stats:
                        txt = " | ".join(f"{s.get('num','')} {s.get('label','')}" for s in stats if isinstance(s,dict))
                        reply = f"Quelques chiffres clés sur l'action de {nom} : {txt}."
                    else:
                        reply = f"{nom} cumule plusieurs mandats parlementaires et fonctions ministérielles au service de la République du Congo. Consultez la section Statistiques du site pour les chiffres détaillés."

                # ── Assemblée nationale / parlement ───────────────────────────
                elif any(w in q for w in ["assemblée", "parlement", "parlementaire", "vote", "loi votée", "séance"]):
                    reply = f"{nom} siège à l'Assemblée Nationale en tant que Député de la 1re circonscription d'Ewo depuis 2017. Il y défend activement les intérêts de sa circonscription et porte des textes de loi importants, notamment dans le domaine judiciaire."

                # ── Valeurs / engagement personnel ────────────────────────────
                elif any(w in q for w in ["valeur", "engagement", "conviction", "humain", "citoyen", "peuple", "sert", "servir", "dévouement"]):
                    reply = f"{nom} fonde son action sur des valeurs d'intégrité, de service public et de proximité avec les citoyens. Son engagement au service de la République du Congo et des populations d'Ewo guide l'ensemble de ses décisions."

                # ── Merci / au revoir ─────────────────────────────────────────
                elif any(w in q for w in ["merci", "thank", "au revoir", "bye", "à bientôt", "bonne journée", "bonne soirée", "ciao"]):
                    reply = random.choice([
                        f"Merci pour votre intérêt ! N'hésitez pas à revenir si vous avez d'autres questions sur {nom}. — DA",
                        f"Avec plaisir ! Je reste disponible pour toute autre question. Bonne journée ! — DA",
                        f"Au revoir et à bientôt ! N'hésitez pas à parcourir le site pour en savoir plus sur {nom}. — DA",
                    ])

                # ── Langues étrangères / lingala / kituba / anglais ──────────
                elif any(w in q for w in ["hello", "how are you", "i want", "i need", "can i", "please", "speak english", "english"]) or q.strip() in ["hi"] or q.startswith("hi ") or " hi " in q:
                    reply = "I'm DA, the virtual assistant of Minister BININGA's official website. I mainly respond in French. Please write your question in French and I'll be happy to help you. — DA"

                elif any(w in q for w in ["mbote", "bonjour na lingala", "ndeko", "biso", "moto", "malamu", "nakosala"]):
                    reply = f"Mbote ! DA azali assistant virtuel ya site ya {nom}. Tika koloba na français pona nasalisa yo malamu. Merci !"

                elif any(w in q for w in ["ki ndimu", "bonjour kituba", "beto", "yandi", "mono", "ngeye"]):
                    reply = f"DA i assistant virtuel ya site ya {nom}. Souka koloba na français, DA i salisa nge. Merci !"

                elif any(w in q for w in ["nki", "nki ko", "wana", "yala teke", "téké", "teke", "bonjour teke", "bonjour téké"]):
                    reply = f"Nki ko ! DA kɛ assistant virtuel ya site ya {nom}. Loba na français pona DA salisa nge. Merci !"

                elif any(w in q for w in ["mbochi", "mbosi", "nde ko", "nde mbochi", "bonjour mbochi", "awe", "ebe mbochi", "okele", "mbochi ya"]):
                    reply = f"Nde ko ! DA ɔ assistant virtuel ya site ya {nom}. Lɔbɔ na français pona DA salisa yo. Merci !"

                elif any(w in q for w in ["bembé", "bembe", "bonjour bembé", "bonjour bembe", "wumela bembe", "wumela bembé"]):
                    reply = f"Wumela ! DA i assistant virtuel ya site ya {nom}. Yamba na français pona DA salisa nge. Merci !"

                elif any(w in q for w in ["vili", "mavuba", "bonjour vili", "lumbu", "nge vili", "wumela vili"]):
                    reply = f"Mavuba ! DA i assistant virtuel ya site ya {nom}. Yamba na français pona DA salisa nge. Merci !"

                # ── Urgence / SOS ─────────────────────────────────────────────
                elif any(w in q for w in ["urgent", "urgence", "sos", "emergency", "immédiatement", "tout de suite", "critique", "grave"]):
                    reply = f"⚠️ Pour toute situation urgente, contactez directement l'équipe de {nom} via le formulaire de contact sur ce site en précisant le caractère urgent de votre demande. Vous pouvez aussi appeler les services compétents selon la nature de votre urgence."

                # ── Messages irrespectueux ────────────────────────────────────
                elif any(w in q for w in ["idiot", "nul", "incompétent", "voleur", "menteur", "corrompu", "useless", "inutile", "merde", "con"]):
                    reply = "Je vous invite à formuler votre question de façon respectueuse. Je suis ici pour vous informer et vous aider. Si vous avez une préoccupation sérieuse, le formulaire de contact est à votre disposition."

                # ── Questions fréquentes — Comment faire ─────────────────────
                elif any(w in q for w in ["comment faire", "comment puis-je", "comment je peux", "est-ce que je peux", "c'est possible", "comment ça marche", "procédure", "démarche"]):
                    reply = (
                        f"Voici les principales démarches disponibles sur ce site :\n"
                        f"• 📋 Demander une audience → section Audience du site\n"
                        f"• ✉️ Envoyer un message → formulaire de contact\n"
                        f"• ⚠️ Soumettre une réclamation ou signaler un sinistre → section Réclamations\n"
                        f"• 📰 S'abonner à la newsletter → formulaire d'inscription\n"
                        f"• 📚 Commander un livre → formulaire dédié\n\n"
                        f"Dites-moi ce que vous souhaitez faire, je vous orienterai précisément."
                    )

                # ── Localisation / bureau / adresse ──────────────────────────
                elif any(w in q for w in ["localisation", "adresse", "bureau", "où se trouve", "où est", "office", "siège", "ministère", "bâtiment", "lieu", "venir", "bp", "fax"]):
                    addr    = contact.get("address", "Av. Charles de Gaulle, Brazzaville")
                    bp      = contact.get("bp", "BP : 1375")
                    fax     = contact.get("fax", "04 002 90 90")
                    cabinet = contact.get("cabinet", "Cabinet du Ministre de la Justice")
                    reply = (
                        f"📍 {cabinet} de {nom} :\n"
                        f"• Adresse : {addr}\n"
                        f"• {bp}\n"
                        f"• Fax : {fax}\n\n"
                        f"Pour toute visite, vous devez soumettre une demande d'audience via le formulaire disponible sur ce site. Les demandes sont examinées et traitées selon les disponibilités du cabinet."
                    )

                # ── Horaires ──────────────────────────────────────────────────
                elif any(w in q for w in ["horaire", "heure", "ouvert", "ouverture", "fermé", "fermeture", "disponible", "quand", "à quelle heure"]):
                    reply = (
                        f"Les services de {nom} sont généralement accessibles du lundi au vendredi, "
                        f"aux heures ouvrables (8h–16h, heure de Brazzaville). "
                        f"Pour tout contact en dehors de ces horaires, utilisez le formulaire du site — "
                        f"votre message sera traité dès la reprise."
                    )

                # ── Délais de réponse / suivi ─────────────────────────────────
                elif any(w in q for w in ["délai", "combien de temps", "quand", "réponse", "répondre", "attente", "suivi", "dossier", "traitement", "accepté", "refusé", "statut", "état"]):
                    reply = (
                        f"Les délais de traitement varient selon la nature de votre demande :\n"
                        f"• ✉️ Message de contact → réponse sous 48h à 72h ouvrées\n"
                        f"• 📋 Demande d'audience → traitement sous 5 à 10 jours ouvrés\n"
                        f"• ⚠️ Réclamation / sinistre → prise en charge sous 72h\n\n"
                        f"Si vous n'avez pas de retour après ce délai, n'hésitez pas à renvoyer votre demande via le formulaire de contact en précisant qu'il s'agit d'un suivi."
                    )

                # ── Robot / humain ? ──────────────────────────────────────────
                elif any(w in q for w in ["robot", "humain", "intelligence artificielle", "ia ", "chatbot", "bot", "machine", "programme", "automatique", "réel"]):
                    reply = f"Je suis DA, un assistant virtuel — ni humain, ni intelligence artificielle. Je fonctionne à partir des informations publiées sur ce site officiel de {nom}. Je ne peux donc répondre qu'aux questions liées à son parcours, ses fonctions et ses engagements."

                # ── Compliments / félicitations ───────────────────────────────
                elif any(w in q for w in ["super da", "bravo da", "bien répondu", "excellente réponse", "top da", "tu es bien", "bonne réponse"]):
                    reply = random.choice([
                        "Merci pour votre retour ! Je fais de mon mieux pour vous informer. N'hésitez pas si vous avez d'autres questions. — DA",
                        "C'est très gentil ! Je suis là pour vous aider. Posez-moi toutes vos questions sur Ange Aimé Wilfrid BININGA. — DA",
                        "Merci ! C'est un plaisir de vous être utile. — DA",
                    ])

                # ── Vote / élections / inscription électorale ─────────────────
                elif any(w in q for w in ["voter", "vote", "élection", "liste électorale", "inscription électorale", "bureau de vote", "bulletin", "scrutin", "candidat", "campagne électorale"]):
                    reply = (
                        f"{nom} est candidat à la députation pour la 1re circonscription d'Ewo.\n\n"
                        f"Pour voter, vous devez :\n"
                        f"• ✅ Être inscrit sur les listes électorales de votre circonscription\n"
                        f"• ✅ Vous munir de votre carte d'électeur ou pièce d'identité le jour du scrutin\n"
                        f"• ✅ Vous rendre dans votre bureau de vote aux heures indiquées\n\n"
                        f"Pour toute question sur l'inscription électorale, rapprochez-vous de la Direction Générale des Élections ou de la mairie de votre commune."
                    )

                # ── Bénévolat / rejoindre la campagne ────────────────────────
                elif any(w in q for w in ["bénévole", "bénévolat", "rejoindre", "volontaire", "équipe campagne", "s'engager", "engager", "militant", "soutien", "supporter", "aide campagne"]):
                    reply = (
                        f"Vous souhaitez rejoindre l'équipe de campagne de {nom} ? C'est avec plaisir !\n\n"
                        f"📩 Envoyez votre candidature via le formulaire de contact sur ce site en précisant :\n"
                        f"• Votre nom et prénom\n"
                        f"• Votre localisation (Ewo, Brazzaville, autre)\n"
                        f"• La façon dont vous souhaitez contribuer\n\n"
                        f"L'équipe prendra contact avec vous rapidement."
                    )

                # ── Réalisations concrètes ────────────────────────────────────
                elif any(w in q for w in ["réalisation", "accompli", "construit", "école", "hôpital", "actions concrètes", "résultat concret", "ce qu'il a fait", "bilan concret"]):
                    reply = (
                        f"Parmi les réalisations concrètes de {nom} :\n"
                        f"• ⚖️ Adoption de la loi HALC (Haute Autorité de Lutte contre la Corruption) — 107 voix pour\n"
                        f"• 🏛️ Modernisation du système judiciaire congolais\n"
                        f"• 🤝 Coopération judiciaire internationale renforcée (notamment avec la France)\n"
                        f"• 📋 Réforme de l'administration publique lors de son mandat au Ministère de la Fonction Publique\n"
                        f"• 🌍 Défense des intérêts de la Cuvette-Ouest à l'Assemblée Nationale depuis 2017\n\n"
                        f"Consultez la section Parcours du site pour le détail complet de son action."
                    )

                # ── Distinctions / prix / décorations ────────────────────────
                elif any(w in q for w in ["distinction", "prix", "médaille", "décoration", "récompense", "honorifique", "ordre", "insigne", "titre honorifique"]):
                    reply = f"Pour les distinctions et décorations officielles de {nom}, je vous invite à consulter la section Biographie du site ou à contacter directement l'équipe pour obtenir ces informations précises."

                # ── Citations / devise / slogan ───────────────────────────────
                elif any(w in q for w in ["citation", "phrase", "devise", "slogan", "maxime", "il dit", "il a dit", "parole", "discours", "quote"]):
                    slogan = hero.get("slogan", "").replace("<em>","").replace("</em>","").replace("<br>", " ")
                    reply = (
                        f"La devise de {nom} :\n"
                        f"« {slogan} »\n\n"
                        f"Une vision ancrée dans l'engagement au service du peuple congolais et de la Cuvette-Ouest."
                    )

                # ── Document officiel / attestation ──────────────────────────
                elif any(w in q for w in ["attestation", "certificat", "document officiel", "acte", "légalisation", "apostille", "casier judiciaire", "extrait"]):
                    reply = (
                        f"Pour les demandes de documents officiels (attestations, casier judiciaire, actes légalisés…), "
                        f"ces démarches relèvent des services du Ministère de la Justice ou des greffes des tribunaux compétents.\n\n"
                        f"📍 Ministère de la Justice — Av. Charles de Gaulle, Brazzaville\n"
                        f"Vous pouvez aussi contacter l'équipe de {nom} via le formulaire du site pour être orienté vers le bon service."
                    )

                # ── Problème local / infrastructure ───────────────────────────
                elif any(w in q for w in ["route abîmée", "eau courante", "électricité coupée", "problème local", "infrastructure locale", "panne eau", "panne électricité", "route dégradée", "pont", "forage"]):
                    reply = (
                        f"Pour signaler un problème d'infrastructure dans votre localité (route, eau, électricité, pont…), "
                        f"vous pouvez :\n"
                        f"• 📋 Soumettre un signalement via le formulaire de réclamation sur ce site\n"
                        f"• ✉️ Contacter directement le cabinet de {nom} pour porter le problème à son attention\n\n"
                        f"{nom} s'engage pour le développement de la Cuvette-Ouest et prend en compte les remontées du terrain."
                    )

                # ── Quiz ──────────────────────────────────────────────────────
                elif any(w in q for w in ["quiz", "jeu", "devinette", "question sur bininga", "tester", "test sur", "je sais tout"]):
                    reply = random.choice([
                        f"🎯 Question 1 : Dans quelle circonscription {nom} est-il élu Député ? Répondez et je vous donne la suite !",
                        f"🎯 Question 1 : Quel ministère {nom} dirige-t-il actuellement ? Répondez et je valide !",
                        f"🎯 Question 1 : En quelle année {nom} a-t-il fait adopter la loi HALC à l'Assemblée Nationale ? À vous de jouer !",
                    ])

                # ── Réponse par défaut — IA (Gemini / Groq fallback) ─────────
                else:
                    try:
                        history_ctx = payload.get("history", [])
                        hist_txt = ""
                        for h in history_ctx[-6:]:
                            role_lbl = "Visiteur" if h.get("role") == "user" else "DA"
                            hist_txt += f"{role_lbl}: {h.get('content','')}\n"

                        about_intro = about.get("intro", "")[:200]
                        prog_axes   = ", ".join(
                            ax.get("title","") for ax in programme.get("axes",[])[:4]
                            if isinstance(ax, dict) and ax.get("title")
                        )
                        ai_prompt = f"""Tu es DA, assistante virtuelle du site de {nom}, {role}.
Réponds en français, chaleureusement, en 2-3 phrases max, uniquement sur {nom}.
Si tu ne sais pas, oriente vers le formulaire de contact.
Contexte : {about_intro} Programme : {prog_axes}
{hist_txt}Visiteur: {question}
DA:"""
                        ai_reply = _gemini_call(ai_prompt, max_tokens=150, timeout=12)
                        # Nettoyer si le modèle répète "DA:"
                        if ai_reply.lower().startswith("da:"):
                            ai_reply = ai_reply[3:].strip()
                        reply = ai_reply
                    except Exception:
                        reply = f"Je n'ai pas d'information précise sur ce sujet. Pour toute question, contactez directement l'équipe de {nom} via le formulaire de contact sur ce site."

                self._json({"ok": True, "reply": reply})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ── /api/monitoring/resolve-alert ─────────────────────────────────────
        if path == "/api/monitoring/resolve-alert":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            if _MON:
                try:
                    payload = json.loads(body.decode("utf-8"))
                    _mon.resolve_alert(int(payload.get("id", 0)))
                    audit_log("MONITORING", ip, f"Alerte résolue id={payload.get('id')}")
                except Exception as e:
                    self._json({"ok": False, "message": str(e)}, 400)
                    return
            self._json({"ok": True})
            return

        # ── /api/yaro/* — YARO IA Dashboard ───────────────────────────────────
        if path.startswith("/api/yaro/"):
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return

            _YARO_DB = "news.db"

            def _yaro_conn():
                import sqlite3 as _sq
                c = _sq.connect(_YARO_DB)
                c.row_factory = _sq.Row
                return c

            # GET /api/yaro/stats
            if path == "/api/yaro/stats":
                try:
                    c = _yaro_conn()
                    today = datetime.datetime.utcnow().date().isoformat()
                    total      = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
                    today_cnt  = c.execute("SELECT COUNT(*) FROM articles WHERE ts >= ?", (today,)).fetchone()[0]
                    sources    = [dict(r) for r in c.execute("SELECT source, COUNT(*) as cnt FROM articles GROUP BY source ORDER BY cnt DESC").fetchall()]
                    keywords   = []
                    for kw in ["pétrole", "forêt", "justice", "contrat"]:
                        cnt = c.execute("SELECT COUNT(*) FROM articles WHERE keywords LIKE ?", (f"%{kw}%",)).fetchone()[0]
                        keywords.append({"keyword": kw, "cnt": cnt})
                    last_run   = c.execute("SELECT ts FROM articles ORDER BY ts DESC LIMIT 1").fetchone()
                    c.close()
                    self._json({"ok": True, "total": total, "today": today_cnt,
                                "sources": sources, "keywords": keywords,
                                "last_run": last_run[0] if last_run else None})
                except Exception as e:
                    self._json({"ok": False, "message": str(e)}, 500)
                return

            # GET /api/yaro/articles?page=1&limit=20&source=&keyword=&q=
            if path == "/api/yaro/articles":
                try:
                    qs_y   = parse_qs(urlparse(self.path).query)
                    page   = max(1, int(qs_y.get("page",   ["1"])[0]))
                    limit  = min(50, int(qs_y.get("limit",  ["20"])[0]))
                    source = qs_y.get("source",  [""])[0].strip()
                    kw     = qs_y.get("keyword", [""])[0].strip()
                    q_txt  = qs_y.get("q",       [""])[0].strip()
                    offset = (page - 1) * limit

                    where, params = [], []
                    if source:
                        where.append("source = ?"); params.append(source)
                    if kw:
                        where.append("keywords LIKE ?"); params.append(f"%{kw}%")
                    if q_txt:
                        where.append("(titre_fr LIKE ? OR titre LIKE ? OR url LIKE ?)")
                        params += [f"%{q_txt}%", f"%{q_txt}%", f"%{q_txt}%"]

                    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
                    c = _yaro_conn()
                    total_f = c.execute(f"SELECT COUNT(*) FROM articles {where_sql}", params).fetchone()[0]
                    rows    = c.execute(
                        f"SELECT id,source,titre_fr,titre,url,keywords,lang_orig,ts FROM articles {where_sql} ORDER BY ts DESC LIMIT ? OFFSET ?",
                        params + [limit, offset]
                    ).fetchall()
                    c.close()
                    self._json({"ok": True, "total": total_f, "page": page,
                                "pages": max(1, -(-total_f // limit)),
                                "articles": [dict(r) for r in rows]})
                except Exception as e:
                    self._json({"ok": False, "message": str(e)}, 500)
                return

            # DELETE /api/yaro/article  body: {id}
            if path == "/api/yaro/article":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    payload = json.loads(self.rfile.read(length)) if length else {}
                    art_id  = int(payload.get("id", 0))
                    c = _yaro_conn()
                    c.execute("DELETE FROM articles WHERE id = ?", (art_id,))
                    c.commit(); c.close()
                    self._json({"ok": True})
                except Exception as e:
                    self._json({"ok": False, "message": str(e)}, 500)
                return

            # POST /api/yaro/run — génération veille juridique via IA (inline)
            if path == "/api/yaro/run":
                try:
                    import sqlite3 as _sq3

                    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
                    if not gemini_key:
                        self._json({"ok": False, "message": "GEMINI_API_KEY non configuré — ajoutez la variable sur Railway"}, 400)
                        return

                    YARO_THEMES = [
                        {"source": "OHADA Info",        "sujet": "droit OHADA et droit des affaires en Afrique centrale",                        "keywords": ["contrat", "OHADA"]},
                        {"source": "JO Congo",           "sujet": "Journal Officiel du Congo-Brazzaville — textes législatifs et réglementaires récents", "keywords": ["loi", "décret", "réforme"]},
                        {"source": "Justice Congo",      "sujet": "réforme judiciaire et système de justice au Congo-Brazzaville",                 "keywords": ["justice", "tribunal", "réforme"]},
                        {"source": "Énergie Congo",      "sujet": "réglementation pétrolière, minière et énergétique au Congo-Brazzaville",        "keywords": ["pétrole", "contrat"]},
                        {"source": "Environnement Congo","sujet": "droit forestier, environnemental et foncier au Congo-Brazzaville",              "keywords": ["forêt", "contrat"]},
                        {"source": "Diplomatie Congo",   "sujet": "coopération judiciaire internationale et accords bilatéraux du Congo-Brazzaville","keywords": ["diplomatie", "contrat"]},
                    ]

                    def _yaro_init_db(conn):
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS articles (
                                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                                source    TEXT NOT NULL,
                                titre     TEXT NOT NULL,
                                titre_fr  TEXT,
                                url       TEXT UNIQUE,
                                keywords  TEXT,
                                lang_orig TEXT DEFAULT 'fr',
                                ts        TEXT DEFAULT (datetime('now'))
                            )""")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts  ON articles(ts)")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_src ON articles(source)")
                        conn.commit()

                    def _yaro_save(conn, source, titre, url, kws):
                        try:
                            conn.execute(
                                "INSERT OR IGNORE INTO articles (source, titre, titre_fr, url, keywords, lang_orig) VALUES (?,?,?,?,?,?)",
                                (source, titre[:300], titre[:300], url, ",".join(kws), "fr")
                            )
                            conn.commit()
                        except Exception:
                            pass

                    yaro_db = _sq3.connect(_YARO_DB)
                    _yaro_init_db(yaro_db)
                    total = 0

                    for theme in YARO_THEMES:
                        today_str = datetime.now().strftime("%d %B %Y")
                        prompt = f"""Tu es un expert en veille juridique spécialisé dans le droit africain.

Génère 4 bulletins de veille juridique portant sur : {theme['sujet']}
Date de référence : {today_str}

Chaque bulletin doit couvrir un aspect différent (actualité législative, jurisprudence, accord international, analyse).

Réponds UNIQUEMENT avec ce tableau JSON (sans markdown) :
[
  {{
    "titre": "titre du bulletin (factuel, informatif, max 120 caractères)",
    "url": "https://yaro-ref.cg/{secrets.token_hex(6)}"
  }}
]"""
                        try:
                            raw = _gemini_call(prompt, max_tokens=600)
                            if raw.startswith("```"):
                                raw = "\n".join(raw.split("\n")[1:])
                            if raw.endswith("```"):
                                raw = "\n".join(raw.split("\n")[:-1])
                            items = json.loads(raw.strip())
                            if isinstance(items, list):
                                for it in items:
                                    titre = (it.get("titre") or "").strip()
                                    url_b = (it.get("url") or f"https://yaro-ref.cg/{secrets.token_hex(8)}").strip()
                                    if titre:
                                        _yaro_save(yaro_db, theme["source"], titre, url_b, theme["keywords"])
                                        total += 1
                        except Exception as ge:
                            print(f"[YARO] Erreur thème {theme['source']} : {ge}")

                    yaro_db.close()
                    audit_log("YARO_IA", ip, f"Veille juridique IA lancée — {total} bulletins générés")
                    self._json({"ok": True, "message": f"{total} bulletins générés via IA."})
                except Exception as e:
                    self._json({"ok": False, "message": str(e)}, 500)
                return

            self._json({"ok": False, "message": "Route inconnue"}, 404)
            return

        # ── /api/track-visit (public — compteur de visites côté serveur) ──
        if path == "/api/track-visit":
            body = {}
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length:
                    body = json.loads(self.rfile.read(length))
            except Exception:
                pass
            page = body.get("page", "/")
            kind = body.get("kind", "visit")
            if _MON:
                if kind == "prog":
                    _mon.record_prog_view(ip)
                    _sse_broadcast("prog_view", {"ip": ip[:6] + "***"})
                else:
                    _mon.record_visit(ip, page)
                    _sse_broadcast("visit", {"ip": ip[:6] + "***", "page": page})
            self._json({"ok": True})
            return

        # ── /api/contact (public — formulaires du site) ──
        if path == "/api/contact":
            try:
                data = json.loads(body.decode("utf-8"))
                # Sauvegarder tous les champs du formulaire (chaines et nombres seulement)
                PROTECTED = {"ts", "ip"}
                entry = {
                    "_id": secrets.token_hex(12),
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
                # Normaliser photo-url → photo_url (champ formulaire HTML vs clé Python)
                if "photo-url" in entry and "photo_url" not in entry:
                    entry["photo_url"] = entry.pop("photo-url")
                # Normalisation : s'assurer que type et source sont cohérents
                raw_src = entry.get("source") or entry.get("type", "contact")
                entry["source"] = raw_src
                entry["type"]   = raw_src
                append_contact(entry)
                nom    = entry.get("nom", "")
                prenom = entry.get("prenom", "")
                etype  = raw_src
                audit_log("CONTACT", ip, f"Message de {nom} {prenom} ({etype})")
                # ── Notification SSE temps réel ───────────────────────────────
                _notif_type = {"bininga_audiences": "audience", "bininga_contacts": "contact"}.get(etype, "contact")
                if etype == "bininga_audiences" and entry.get("objet") == "Réclamation":
                    _notif_type = "reclamation"
                _sse_broadcast(_notif_type, {"nom": nom, "prenom": prenom, "objet": entry.get("objet", "")})
                # ── Email de notification temps réel ─────────────────────────────
                _send_notif_email_async(entry, _notif_type)
                # ── Toute interaction → CRM (règle fondamentale : aucune perte) ──
                email_contact = entry.get("email", "").strip()
                phone_contact = entry.get("telephone", "").strip()
                if email_contact or phone_contact:
                    try:
                        source_map = {
                            "bininga_newsletter":      "newsletter",
                            "bininga_audiences":       "audience",
                            "bininga_contacts":        "contact",
                            "bininga_commande_livre":  "livre",
                        }
                        action_map = {
                            "newsletter": "inscription_newsletter",
                            "audience":   "demande_audience",
                            "contact":    "message_contact",
                            "livre":      "commande_livre",
                        }
                        source       = source_map.get(etype, "contact")
                        is_newsletter = etype == "bininga_newsletter"
                        now_str      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        with _CRM_LOCK:
                            crm = load_crm()
                            existing = None
                            if email_contact:
                                existing = next((c for c in crm["contacts"]
                                                 if c.get("email", "").strip().lower() == email_contact.lower()), None)
                            if existing is None and phone_contact:
                                existing = next((c for c in crm["contacts"]
                                                 if c.get("telephone", "").strip() == phone_contact and not c.get("email")), None)
                            if existing is None:
                                tags = [source]
                                if is_newsletter and "newsletter" not in tags:
                                    tags.append("newsletter")
                                crm["contacts"].append({
                                    "id":         entry["_id"],
                                    "nom":        nom,
                                    "prenom":     prenom,
                                    "email":      email_contact,
                                    "telephone":  phone_contact,
                                    "source":     source,
                                    "tags":       tags,
                                    "newsletter": is_newsletter,
                                    "statut":     "nouveau",
                                    "created_at": now_str,
                                    "expires_at": _crm_expire_date(),
                                    "notes":      [],
                                    "historique": [{"ts": now_str, "action": action_map.get(source, "contact"), "detail": f"Via le site public ({etype})"}],
                                    "newsletters": [],
                                })
                            else:
                                if not existing.get("nom")       and nom:           existing["nom"]       = nom
                                if not existing.get("prenom")    and prenom:        existing["prenom"]    = prenom
                                if not existing.get("email")     and email_contact: existing["email"]     = email_contact
                                if not existing.get("telephone") and phone_contact: existing["telephone"] = phone_contact
                                if is_newsletter:
                                    existing["newsletter"] = True
                                    if "newsletter" not in existing.get("tags", []):
                                        existing.setdefault("tags", []).append("newsletter")
                                if source not in existing.get("tags", []):
                                    existing.setdefault("tags", []).append(source)
                                existing.setdefault("historique", []).append({
                                    "ts": now_str, "action": action_map.get(source, "contact"),
                                    "detail": f"Nouveau message via le site ({etype})"
                                })
                            save_crm(crm)
                    except Exception:
                        pass  # CRM non bloquant
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

        # Rate limiting par token authentifié
        if check_token_rate(token):
            self._json({"ok": False, "message": "Trop de requêtes — ralentissez"}, 429)
            return
        # Validation CSRF sur routes d'écriture
        if path in ("/api/save", "/api/users/upsert", "/api/users/delete", "/api/contacts/clear",
                    "/api/contacts/update", "/api/reset",
                    "/api/crm/upsert", "/api/crm/delete", "/api/crm/bulk-delete", "/api/crm/import",
                    "/api/crm/note", "/api/crm/newsletter/send",
                    "/api/2fa/setup", "/api/2fa/activate", "/api/2fa/disable"):
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
                all_contacts = load_contacts()
                kept = [c for c in all_contacts if c.get("type") != msg_type]
                save_contacts(kept)
                who = session["username"] if session else "?"
                audit_log("CLEAR_CONTACTS", ip, f"Suppression type={msg_type} par {who}")
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        if path == "/api/contacts/update":
            if not has_role(token, "admin", "editeur", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                data = json.loads(body.decode("utf-8"))
                cid  = data.get("id", "").strip()
                if not cid:
                    self._json({"ok": False, "message": "ID requis"}, 400)
                    return
                all_c   = load_contacts()
                updated = False
                for c in all_c:
                    if c.get("_id") == cid:
                        if "status"     in data: c["_status"]     = data["status"]
                        if "notes"      in data: c["_notes"]      = data["notes"]
                        if "pinged"     in data: c["_pinged"]     = data["pinged"]
                        if "pinged_date" in data: c["_pinged_date"] = data["pinged_date"]
                        updated = True
                        break
                if updated:
                    save_contacts(all_c)
                self._json({"ok": True, "updated": updated})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        if path == "/api/reset":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data    = json.loads(body.decode("utf-8"))
                targets = data.get("targets", [])
                who     = session["username"] if session else "admin"
                results = {}
                if "contacts" in targets:
                    save_contacts([])
                    results["contacts"] = True
                    audit_log("RESET", ip, f"Contacts réinitialisés par {who}")
                if "crm" in targets:
                    crm = load_crm()
                    crm["contacts"] = []
                    save_crm(crm)
                    results["crm"] = True
                    audit_log("RESET", ip, f"CRM réinitialisé par {who}")
                self._json({"ok": True, "results": results})
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
                if _AI_GUARD_ENABLED:
                    AI_GUARD.manual_unban(target)
                audit_log("UNBLOCK_IP", ip, f"IP débloquée : {target}")
                self._json({"ok": True, "message": f"IP {target} débloquée (Bouclier + système)"})
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
                duration = int(data.get("duration", 86400))
                if not target:
                    self._json({"ok": False, "message": "IP requise"}, 400)
                    return
                BLOCKED_IPS.add(target)
                save_blocked_ips()
                if _AI_GUARD_ENABLED:
                    AI_GUARD.manual_ban(target, duration, reason)
                audit_log("MANUAL_BAN", ip, f"IP bannie manuellement : {target} — {reason}")
                self._json({"ok": True, "message": f"IP {target} bloquée (Bouclier + système)"})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/security/bouclier/lockdown — Lockdown via POST ──────────────────
        if path == "/api/security/bouclier/lockdown":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            if not _AI_GUARD_ENABLED:
                self._json({"ok": False, "message": "Bouclier IA non disponible"}, 503)
                return
            try:
                data     = json.loads(body.decode("utf-8"))
                action   = data.get("action", "status")
                if action == "activate":
                    duration = int(data.get("duration", 900))
                    reason   = data.get("reason", "Admin déclenché manuellement")
                    AI_GUARD.lockdown.activate(reason, duration)
                    audit_log("LOCKDOWN_ADMIN", ip, f"Lockdown activé {duration}s")
                    self._json({"ok": True, "message": f"LOCKDOWN ACTIVE — {duration}s"})
                elif action == "deactivate":
                    AI_GUARD.lockdown.deactivate()
                    audit_log("LOCKDOWN_ADMIN", ip, "Lockdown levé")
                    self._json({"ok": True, "message": "Mode sécurité levé"})
                else:
                    self._json({"ok": True, "status": AI_GUARD.lockdown.status()})
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
                # Seul l'admin principal (ou le créateur) peut modifier un compte administrateur existant
                if existing and existing["role"] == "admin" and session and session["username"] != ADMIN_USER:
                    created_by = existing.get("created_by", "")
                    if created_by != session["username"]:
                        self._json({"ok": False, "message": "Vous ne pouvez modifier que les comptes admin que vous avez créés"}, 403)
                        return
                if existing:
                    existing["nom"]  = nom or existing["nom"]
                    existing["role"] = role
                    if pwd:
                        existing["password_hash"] = _hash_new(pwd)
                else:
                    if not pwd:
                        self._json({"ok": False, "message": "Mot de passe requis"}, 400)
                        return
                    users.append({"username": uname, "password_hash": _hash_new(pwd), "role": role, "nom": nom or uname,
                                  "created_by": session["username"] if session else ""})
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
                all_users = load_users()
                target_user = next((u for u in all_users if u["username"] == uname), None)
                # Le compte ministre ne peut jamais être supprimé
                if target_user and target_user["role"] == "ministre":
                    self._json({"ok": False, "message": "Le compte ministre ne peut pas être supprimé"}, 403)
                    return
                # Seul l'admin principal (ou le créateur) peut supprimer un compte administrateur
                if target_user and target_user["role"] == "admin" and session["username"] != ADMIN_USER:
                    created_by = target_user.get("created_by", "")
                    if created_by != session["username"]:
                        self._json({"ok": False, "message": "Vous ne pouvez supprimer que les comptes admin que vous avez créés"}, 403)
                        return
                # Personne ne peut supprimer l'admin principal lui-même
                if uname == ADMIN_USER:
                    self._json({"ok": False, "message": "Le compte admin principal ne peut pas être supprimé"}, 403)
                    return
                users = [u for u in all_users if u["username"] != uname]
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

        # ── /api/admin/force-sync — force PostgreSQL à reprendre data.json ──
        if path == "/api/admin/force-sync":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                if not os.path.exists(DATA_FILE):
                    self._json({"ok": False, "message": "data.json introuvable"}, 404)
                    return
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    fresh = json.load(f)
                save_data(fresh)
                audit_log("FORCE_SYNC", ip, "Synchronisation forcée data.json → PostgreSQL")
                counts = {
                    "gallery_slides": len(fresh.get("gallery", {}).get("slides", [])),
                    "gallery_grid":   len(fresh.get("gallery", {}).get("grid", [])),
                    "actus_slides":   len(fresh.get("actus", {}).get("slides", [])),
                    "actus_cards":    len(fresh.get("actus", {}).get("cards", [])),
                    "parcours":       len(fresh.get("parcours", [])),
                }
                self._json({"ok": True, "message": "Synchronisation réussie — contenu rechargé depuis data.json", "counts": counts})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
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

        # ── /api/monitor-log ── dernières lignes du log YARO IA ──
        if path == "/api/monitor-log":
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor.log")
            try:
                if not os.path.isfile(log_path):
                    self._json({"ok": True, "lines": ["(monitor.log introuvable — agent pas encore démarré)"]})
                    return
                # Rotation automatique si monitor.log > 1 Mo
                if os.path.getsize(log_path) > 1024 * 1024:
                    ts_rot = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive = log_path.replace(".log", f"_{ts_rot}.log")
                    try:
                        os.rename(log_path, archive)
                        # Supprimer les vieilles archives (garder 3)
                        base_dir = os.path.dirname(log_path)
                        archives = sorted(f for f in os.listdir(base_dir) if f.startswith("monitor_") and f.endswith(".log"))
                        for old in archives[:-3]:
                            try: os.remove(os.path.join(base_dir, old))
                            except Exception: pass
                    except Exception:
                        pass
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                last = [l.rstrip() for l in lines[-100:]]
                self._json({"ok": True, "lines": last})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ── /api/monitor-restart ── redémarrage forcé de YARO IA ──
        if path == "/api/monitor-restart":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                base     = os.path.dirname(os.path.abspath(__file__))
                pid_file = os.path.join(base, "monitor.pid")
                # Tuer le process existant s'il tourne encore
                if os.path.isfile(pid_file):
                    try:
                        pid = int(open(pid_file).read().strip())
                        os.kill(pid, 15)   # SIGTERM
                        time.sleep(1)
                    except Exception:
                        pass
                    try:
                        os.remove(pid_file)
                    except Exception:
                        pass
                start_monitor()
                audit_log("SAVE", ip, "YARO IA redémarré manuellement")
                self._json({"ok": True, "message": "YARO IA redémarré"})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ══════════════════════════════════════════════════════════
        # ── ÉDITORIAL IA ──────────────────────────────────────────
        # ══════════════════════════════════════════════════════════

        # ── /api/editorial/generate — génère un article éditorial depuis une actu ──
        if path == "/api/editorial/generate":
            if not has_role(token, "admin", "ministre", "editeur"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                payload   = json.loads(body.decode("utf-8"))
                news_id   = payload.get("news_id", "")
                titre_src = payload.get("titre", "")
                resume_src= payload.get("resume", "")
                source_nm = payload.get("source", "")
                url_src   = payload.get("url", "")
                date_src  = payload.get("date", "")

                key = os.environ.get("GEMINI_API_KEY", "").strip()
                if not key:
                    self._json({"ok": False, "message": "GEMINI_API_KEY non configuré — ajoutez la variable sur Railway"}, 400)
                    return

                prompt = f"""Tu es un assistant éditorial intégré au système de veille YARO IA du site du Député Ange Aimé Wilfrid BININGA (Congo-Brazzaville).

Transforme cet article de presse en contenu éditorial structuré pour le site du Député.

⚠️ RÈGLES STRICTES :
- Ne jamais inventer d'informations
- Uniquement reformuler et structurer les faits fournis
- Neutralité totale, ton journalistique professionnel
- Mentionner les sources
- Pas d'opinion, pas de biais politique
- Si information insuffisante, reformuler uniquement ce qui est disponible

ARTICLE SOURCE :
Titre : {titre_src}
Résumé : {resume_src}
Source : {source_nm}
Date : {date_src}
URL : {url_src}

Réponds UNIQUEMENT avec ce format JSON (sans markdown, sans commentaire) :
{{
  "titre": "titre clair et neutre",
  "resume": "2 à 4 phrases résumant l'information principale",
  "article": "texte structuré en paragraphes, reformulé professionnellement",
  "points_cles": ["point 1", "point 2", "point 3"],
  "sources": ["{source_nm} — {url_src}"]
}}"""

                try:
                    raw = _gemini_call(prompt, max_tokens=1200)
                except Exception as api_err:
                    err_body = ""
                    try:
                        if hasattr(api_err, 'read'): err_body = api_err.read().decode()
                    except Exception: pass
                    print(f"[EDITORIAL] Erreur Gemini : {api_err} — {err_body}")
                    self._json({"ok": False, "message": f"Erreur API Gemini : {api_err}"}, 500)
                    return

                # Nettoyer le JSON (enlever éventuels blocs markdown)
                if raw.startswith("```"):
                    raw = "\n".join(raw.split("\n")[1:])
                if raw.endswith("```"):
                    raw = "\n".join(raw.split("\n")[:-1])
                editorial = json.loads(raw.strip())

                # Sauvegarder le brouillon
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                article_id = secrets.token_hex(10)
                draft = {
                    "id":         article_id,
                    "news_id":    news_id,
                    "statut":     "brouillon",
                    "created_at": now_str,
                    "updated_at": now_str,
                    "source_url": url_src,
                    "source_nom": source_nm,
                    "source_date": date_src,
                    **editorial,
                }
                arts = _pg_load("editorial") or []
                if not arts and os.path.exists(EDITORIAL_FILE):
                    try:
                        with open(EDITORIAL_FILE, "r", encoding="utf-8") as f:
                            arts = json.load(f)
                    except Exception:
                        arts = []
                arts.insert(0, draft)
                _pg_save("editorial", arts)
                try:
                    with open(EDITORIAL_FILE, "w", encoding="utf-8") as f:
                        json.dump(arts, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                audit_log("EDITORIAL", ip, f"Article éditorial généré : {editorial.get('titre','')[:60]}")
                self._json({"ok": True, "article": draft})
            except json.JSONDecodeError as e:
                self._json({"ok": False, "message": f"Réponse IA invalide : {e}"}, 500)
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ── /api/editorial/save — sauvegarder les modifications d'un article ──
        if path == "/api/editorial/save":
            if not has_role(token, "admin", "ministre", "editeur"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                payload    = json.loads(body.decode("utf-8"))
                article_id = payload.get("id", "")
                arts = _pg_load("editorial") or []
                if not arts and os.path.exists(EDITORIAL_FILE):
                    try:
                        with open(EDITORIAL_FILE, "r", encoding="utf-8") as f:
                            arts = json.load(f)
                    except Exception:
                        arts = []
                found = next((a for a in arts if a["id"] == article_id), None) if article_id else None
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if not found:
                    # Création d'un nouvel article
                    found = {
                        "id":         secrets.token_hex(12),
                        "statut":     "brouillon",
                        "created_at": now_str,
                        "source":     "manuel",
                        "titre":      "",
                        "resume":     "",
                        "contenu":    "",
                        "tags":       [],
                        "points_cles": [],
                    }
                    arts.append(found)
                for field in ("titre", "resume", "contenu", "article", "points_cles", "tags", "statut", "source_url"):
                    if field in payload:
                        found[field] = payload[field]
                found["updated_at"] = now_str
                _pg_save("editorial", arts)
                try:
                    with open(EDITORIAL_FILE, "w", encoding="utf-8") as f:
                        json.dump(arts, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                self._json({"ok": True, "article": found})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ── /api/editorial/delete — supprimer un article éditorial ──
        if path == "/api/editorial/delete":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                payload    = json.loads(body.decode("utf-8"))
                article_id = payload.get("id", "")
                arts = _pg_load("editorial") or []
                if not arts and os.path.exists(EDITORIAL_FILE):
                    try:
                        with open(EDITORIAL_FILE, "r", encoding="utf-8") as f:
                            arts = json.load(f)
                    except Exception:
                        arts = []
                arts = [a for a in arts if a["id"] != article_id]
                _pg_save("editorial", arts)
                try:
                    with open(EDITORIAL_FILE, "w", encoding="utf-8") as f:
                        json.dump(arts, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ── YOUTUBE IA ─────────────────────────────────────────────
        # ════════════════════════════════════════════════════════════

        # ── /api/youtube/generate — génère le contenu YouTube via IA ──
        if path == "/api/youtube/generate":
            if not has_role(token, "admin", "ministre", "editeur"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                payload    = json.loads(body.decode("utf-8"))
                titre_src  = payload.get("titre", "").strip()
                type_video = payload.get("type", "portrait").strip()

                if not titre_src:
                    self._json({"ok": False, "message": "Titre requis"}, 400)
                    return

                key = os.environ.get("GEMINI_API_KEY", "").strip()
                if not key:
                    self._json({"ok": False, "message": "GEMINI_API_KEY non configuré — ajoutez la variable sur Railway"}, 400)
                    return

                # Charger les données du député pour le contexte
                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        site_data = json.load(f)
                    hero  = site_data.get("hero", {})
                    about = site_data.get("about", {})
                    context_name = f"{hero.get('firstName','')} {hero.get('lastName','')}".strip() or "BININGA"
                    context_role = hero.get("role", "Député-Ministre")
                    context_intro = about.get("intro", "")
                except Exception:
                    context_name  = "Ange Aimé Wilfrid BININGA"
                    context_role  = "Député-Ministre de la Justice, Garde des Sceaux (Congo-Brazzaville)"
                    context_intro = ""

                prompt = f"""Tu es un expert en communication politique et création de contenu YouTube francophone.

Personnalité politique : {context_name} — {context_role}
{context_intro}

Génère le contenu YouTube complet pour la vidéo suivante :
Titre : "{titre_src}"
Type : {type_video}

Réponds UNIQUEMENT avec ce JSON (sans markdown ni texte autour) :
{{
  "titre_youtube": "titre accrocheur optimisé SEO (max 70 caractères)",
  "description": "description YouTube complète (300-500 mots) avec paragraphes, appel à l'action et hashtags en fin",
  "script": "script de la vidéo (3-5 minutes de narration, structuré avec intro, développement, conclusion)",
  "tags": ["liste", "de", "15", "tags", "pertinents"],
  "miniature_texte": "texte court pour la miniature (max 5 mots percutants)",
  "duree_estimee": "durée estimée (ex: 4 minutes)"
}}"""

                try:
                    raw = _gemini_call(prompt, max_tokens=2000)
                except Exception as api_err:
                    self._json({"ok": False, "message": f"Erreur API IA : {api_err}"}, 500)
                    return

                # Nettoyer le JSON
                if raw.startswith("```"):
                    raw = "\n".join(raw.split("\n")[1:])
                if raw.endswith("```"):
                    raw = "\n".join(raw.split("\n")[:-1])
                raw = raw.strip()
                contenu = json.loads(raw)

                now_str    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                video_id   = secrets.token_hex(10)
                draft = {
                    "id":         video_id,
                    "titre":      titre_src,
                    "type":       type_video,
                    "statut":     "brouillon",
                    "created_at": now_str,
                    "updated_at": now_str,
                    "contenu":    contenu,
                }
                vids = _pg_load("youtube") or []
                if not vids and os.path.exists(YOUTUBE_FILE):
                    try:
                        with open(YOUTUBE_FILE, "r", encoding="utf-8") as f:
                            vids = json.load(f)
                    except Exception:
                        vids = []
                vids.insert(0, draft)
                _pg_save("youtube", vids)
                try:
                    with open(YOUTUBE_FILE, "w", encoding="utf-8") as f:
                        json.dump(vids, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                audit_log("YOUTUBE", ip, f"Contenu YouTube généré : {titre_src[:60]}")
                self._json({"ok": True, "video": draft})
            except json.JSONDecodeError as e:
                self._json({"ok": False, "message": f"Réponse IA invalide : {e}"}, 500)
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ── /api/youtube/save — modifier le statut ou les données d'un contenu ──
        if path == "/api/youtube/save":
            if not has_role(token, "admin", "ministre", "editeur"):
                self._json({"ok": False, "message": "Non autorisé"}, 403)
                return
            try:
                payload   = json.loads(body.decode("utf-8"))
                video_id  = payload.get("id", "")
                vids = _pg_load("youtube") or []
                if not vids and os.path.exists(YOUTUBE_FILE):
                    try:
                        with open(YOUTUBE_FILE, "r", encoding="utf-8") as f:
                            vids = json.load(f)
                    except Exception:
                        vids = []
                found = next((v for v in vids if v["id"] == video_id), None)
                if not found:
                    self._json({"ok": False, "message": "Contenu introuvable"}, 404)
                    return
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for field in ("titre", "type", "statut", "contenu"):
                    if field in payload:
                        found[field] = payload[field]
                found["updated_at"] = now_str
                _pg_save("youtube", vids)
                try:
                    with open(YOUTUBE_FILE, "w", encoding="utf-8") as f:
                        json.dump(vids, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                self._json({"ok": True, "video": found})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ── /api/youtube/delete — supprimer un contenu YouTube ──
        if path == "/api/youtube/delete":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                payload  = json.loads(body.decode("utf-8"))
                video_id = payload.get("id", "")
                vids = _pg_load("youtube") or []
                if not vids and os.path.exists(YOUTUBE_FILE):
                    try:
                        with open(YOUTUBE_FILE, "r", encoding="utf-8") as f:
                            vids = json.load(f)
                    except Exception:
                        vids = []
                vids = [v for v in vids if v["id"] != video_id]
                _pg_save("youtube", vids)
                try:
                    with open(YOUTUBE_FILE, "w", encoding="utf-8") as f:
                        json.dump(vids, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 500)
            return

        # ── /api/crm/upsert — Créer ou modifier un contact CRM ──
        if path == "/api/crm/upsert":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data        = json.loads(body.decode("utf-8"))
                contact_id  = str(data.get("id", "")).strip()
                crm         = load_crm()
                now_str     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                STATUTS     = {"nouveau", "en_cours", "traite", "archive"}
                SOURCES     = {"audience", "contact", "reclamation", "signalement", "manuel"}
                ALLOWED     = {"nom", "prenom", "email", "telephone", "sujet",
                               "message", "tags", "statut", "newsletter", "source"}
                who         = session["username"] if session else "admin"
                statut  = data.get("statut", "nouveau")
                source  = data.get("source", "manuel")
                if contact_id:
                    # Modification ou restauration (vrai upsert)
                    found = False
                    for c in crm["contacts"]:
                        if c["id"] == contact_id:
                            for k, v in data.items():
                                if k not in ALLOWED:
                                    continue
                                if k == "statut" and v not in STATUTS:
                                    continue
                                if k == "source" and v not in SOURCES:
                                    continue
                                if k == "tags":
                                    v = [str(t)[:50] for t in (v if isinstance(v, list) else []) ][:10]
                                if k == "newsletter":
                                    v = bool(v)
                                if isinstance(v, str):
                                    v = v[:2000]
                                c[k] = v
                            c.setdefault("historique", []).append({
                                "ts": now_str, "action": "modifie",
                                "detail": f"Modifié par {who}"
                            })
                            found = True
                            break
                    if not found:
                        # Contact absent (ex: après redéploiement) — recréer avec l'ID d'origine
                        contact = {
                            "id":          contact_id,
                            "created_at":  str(data.get("created_at", now_str))[:30],
                            "expires_at":  str(data.get("expires_at", _crm_expire_date()))[:30],
                            "source":      source if source in SOURCES else "manuel",
                            "nom":         str(data.get("nom",       ""))[:200],
                            "prenom":      str(data.get("prenom",    ""))[:200],
                            "email":       str(data.get("email",     ""))[:200],
                            "telephone":   str(data.get("telephone", ""))[:50],
                            "sujet":       str(data.get("sujet",     ""))[:500],
                            "message":     str(data.get("message",   ""))[:2000],
                            "tags":        [str(t)[:50] for t in data.get("tags", []) if isinstance(t, str)][:10],
                            "statut":      statut if statut in STATUTS else "nouveau",
                            "newsletter":  bool(data.get("newsletter", False)),
                            "notes":       data.get("notes", []),
                            "historique":  data.get("historique", [{"ts": now_str, "action": "restaure",
                                                                     "detail": "Restauré depuis sauvegarde locale"}]),
                        }
                        crm["contacts"].append(contact)
                        audit_log("CRM_RESTORE", ip,
                                  f"Contact CRM restauré : {contact['nom']} {contact['prenom']} ({contact_id})")
                    else:
                        audit_log("CRM_UPDATE", ip, f"Contact CRM modifié : {data.get('nom','?')} ({contact_id})")
                else:
                    # Création avec nouvel ID
                    new_id  = secrets.token_hex(8)
                    contact = {
                        "id":          new_id,
                        "created_at":  now_str,
                        "expires_at":  _crm_expire_date(),
                        "source":      source  if source  in SOURCES  else "manuel",
                        "nom":         str(data.get("nom",       ""))[:200],
                        "prenom":      str(data.get("prenom",    ""))[:200],
                        "email":       str(data.get("email",     ""))[:200],
                        "telephone":   str(data.get("telephone", ""))[:50],
                        "sujet":       str(data.get("sujet",     ""))[:500],
                        "message":     str(data.get("message",   ""))[:2000],
                        "tags":        [str(t)[:50] for t in data.get("tags", []) if isinstance(t, str)][:10],
                        "statut":      statut if statut in STATUTS else "nouveau",
                        "newsletter":  bool(data.get("newsletter", False)),
                        "notes":       [],
                        "historique":  [{"ts": now_str, "action": "cree",
                                         "detail": f"Créé manuellement par {who}"}],
                    }
                    crm["contacts"].append(contact)
                    audit_log("CRM_CREATE", ip,
                              f"Contact CRM créé : {contact['nom']} {contact['prenom']} ({contact['email']})")
                save_crm(crm)
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/crm/delete ──
        if path == "/api/crm/delete":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data       = json.loads(body.decode("utf-8"))
                contact_id = str(data.get("id", "")).strip()
                crm        = load_crm()
                before     = len(crm["contacts"])
                crm["contacts"] = [c for c in crm["contacts"] if c["id"] != contact_id]
                save_crm(crm)
                audit_log("CRM_DELETE", ip, f"Contact CRM supprimé : {contact_id}")
                self._json({"ok": True, "deleted": before - len(crm["contacts"])})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/crm/bulk-delete — Suppression en masse ──
        if path == "/api/crm/bulk-delete":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data = json.loads(body.decode("utf-8"))
                ids  = [str(i).strip() for i in data.get("ids", []) if i]
                if not ids:
                    self._json({"ok": False, "message": "Liste d'IDs requise"}, 400)
                    return
                crm    = load_crm()
                before = len(crm["contacts"])
                id_set = set(ids)
                crm["contacts"] = [c for c in crm["contacts"] if c["id"] not in id_set]
                save_crm(crm)
                deleted = before - len(crm["contacts"])
                who     = session["username"] if session else "admin"
                audit_log("CRM_BULK_DELETE", ip, f"{deleted} contact(s) supprimé(s) en masse par {who}")
                self._json({"ok": True, "deleted": deleted})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/2fa/setup — Générer un secret TOTP pour l'utilisateur ──
        if path == "/api/2fa/setup":
            try:
                who    = session["username"]
                secret = _totp_generate_secret()
                uri    = _totp_uri(secret, who)
                # Stocker le secret temporairement dans la session (pas encore activé)
                ACTIVE_SESSIONS[token]["pending_totp"] = secret
                save_sessions()
                self._json({"ok": True, "secret": secret, "uri": uri})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/2fa/activate — Confirmer et activer le 2FA ──
        if path == "/api/2fa/activate":
            try:
                data       = json.loads(body.decode("utf-8"))
                totp_code  = str(data.get("code", "")).strip()
                pending    = ACTIVE_SESSIONS.get(token, {}).get("pending_totp", "")
                if not pending:
                    self._json({"ok": False, "message": "Aucun secret en attente. Relancez /api/2fa/setup."}, 400)
                    return
                if not _totp_verify(pending, totp_code):
                    self._json({"ok": False, "message": "Code TOTP invalide — vérifiez votre application"}, 400)
                    return
                # Activer le 2FA
                who   = session["username"]
                users = load_users()
                for u in users:
                    if u["username"] == who:
                        u["totp_secret"] = pending
                        break
                save_users(users)
                ACTIVE_SESSIONS[token].pop("pending_totp", None)
                save_sessions()
                audit_log("2FA_ENABLED", ip, f"2FA activé pour {who}")
                self._json({"ok": True, "message": "2FA activé avec succès"})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/2fa/disable — Désactiver le 2FA ──
        if path == "/api/2fa/disable":
            try:
                data      = json.loads(body.decode("utf-8"))
                totp_code = str(data.get("code", "")).strip()
                who       = session["username"]
                user      = find_user(who)
                secret    = (user or {}).get("totp_secret", "")
                if not secret:
                    self._json({"ok": False, "message": "2FA non activé"}, 400)
                    return
                if not _totp_verify(secret, totp_code):
                    self._json({"ok": False, "message": "Code TOTP invalide"}, 400)
                    return
                users = load_users()
                for u in users:
                    if u["username"] == who:
                        u.pop("totp_secret", None)
                        break
                save_users(users)
                audit_log("2FA_DISABLED", ip, f"2FA désactivé pour {who}")
                self._json({"ok": True, "message": "2FA désactivé"})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/crm/import — Importer depuis contacts.json ──
        if path == "/api/crm/import":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                all_contacts = load_contacts()
                crm     = load_crm()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                exp_str = _crm_expire_date()
                who     = session["username"] if session else "admin"
                # Index des contacts existants pour éviter les doublons
                existing_keys = set()
                for c in crm["contacts"]:
                    key = (c.get("email",""), c.get("nom",""), c.get("created_at","")[:10])
                    existing_keys.add(key)
                TYPE_MAP = {
                    "bininga_audiences":  "audience",
                    "bininga_newsletter": "newsletter",
                    "reclamation":        "reclamation",
                    "contact":            "contact",
                    "signalement":        "signalement",
                }
                imported = 0
                for raw in all_contacts:
                    ts_raw  = raw.get("ts", now_str)
                    key     = (raw.get("email",""), raw.get("nom",""), ts_raw[:10])
                    if key in existing_keys:
                        continue
                    raw_type = raw.get("type", "contact")
                    src_type = TYPE_MAP.get(raw_type, raw_type)
                    is_nl    = raw_type == "bininga_newsletter"
                    contact  = {
                        "id":         raw.get("_id", secrets.token_hex(8)),
                        "created_at": ts_raw,
                        "expires_at": exp_str,
                        "source":     src_type,
                        "nom":        str(raw.get("nom",      ""))[:200],
                        "prenom":     str(raw.get("prenom",   ""))[:200],
                        "email":      str(raw.get("email",    ""))[:200],
                        "telephone":  str(raw.get("telephone", raw.get("tel", "")))[:50],
                        "sujet":      str(raw.get("sujet",    raw.get("objet", "")))[:500],
                        "message":    str(raw.get("message",  raw.get("demande",
                                        raw.get("raison", ""))))[:2000],
                        "tags":       ["newsletter"] if is_nl else [src_type],
                        "statut":     "nouveau",
                        "newsletter": is_nl,
                        "notes":      [],
                        "historique": [{"ts": now_str, "action": "importe",
                                        "detail": f"Importé depuis contacts.json par {who}"}],
                    }
                    crm["contacts"].append(contact)
                    existing_keys.add(key)
                    imported += 1
                save_crm(crm)
                audit_log("CRM_IMPORT", ip,
                          f"{imported} contacts importés depuis contacts.json par {who}")
                self._json({"ok": True, "imported": imported})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/crm/note — Ajouter une note à un contact CRM ──
        if path == "/api/crm/note":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data       = json.loads(body.decode("utf-8"))
                contact_id = str(data.get("id", "")).strip()
                texte      = str(data.get("texte", "")).strip()[:1000]
                if not contact_id or not texte:
                    self._json({"ok": False, "message": "ID et texte requis"}, 400)
                    return
                crm     = load_crm()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                who     = session["username"] if session else "admin"
                found   = False
                for c in crm["contacts"]:
                    if c["id"] == contact_id:
                        c.setdefault("notes", []).append(
                            {"ts": now_str, "texte": texte, "auteur": who}
                        )
                        c.setdefault("historique", []).append(
                            {"ts": now_str, "action": "note",
                             "detail": f"Note ajoutée par {who}"}
                        )
                        found = True
                        break
                if not found:
                    self._json({"ok": False, "message": "Contact introuvable"}, 404)
                    return
                save_crm(crm)
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/crm/newsletter/send — Envoi de newsletter CRM ──
        if path == "/api/crm/newsletter/send":
            if not has_role(token, "admin"):
                self._json({"ok": False, "message": "Réservé à l'admin"}, 403)
                return
            try:
                data    = json.loads(body.decode("utf-8"))
                sujet   = str(data.get("sujet", "")).strip()[:300]
                corps   = str(data.get("corps", "")).strip()[:100000]
                filtre  = data.get("filtre", "newsletter")
                if not sujet or not corps:
                    self._json({"ok": False, "message": "Sujet et corps requis"}, 400)
                    return
                crm = load_crm()
                # Sélection des destinataires
                if filtre == "newsletter":
                    destinataires = [c for c in crm["contacts"]
                                     if c.get("newsletter") and c.get("email")]
                elif filtre == "tous":
                    destinataires = [c for c in crm["contacts"] if c.get("email")]
                elif isinstance(filtre, list):
                    destinataires = [c for c in crm["contacts"]
                                     if c.get("email") and
                                     any(t in c.get("tags", []) for t in filtre)]
                else:
                    destinataires = [c for c in crm["contacts"]
                                     if c.get("email") and filtre in c.get("tags", [])]
                smtp_host = os.environ.get("SMTP_HOST", "")
                smtp_port = int(os.environ.get("SMTP_PORT", "587"))
                smtp_user = os.environ.get("SMTP_USER", "")
                smtp_pass = os.environ.get("SMTP_PASS", "")
                smtp_from = os.environ.get("SMTP_FROM", smtp_user)
                now_str   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                nl_id     = secrets.token_hex(6)
                erreur    = None
                envoyes   = 0
                echecs = 0
                if smtp_host and smtp_user:
                    import smtplib
                    from email.mime.multipart import MIMEMultipart
                    from email.mime.text import MIMEText
                    try:
                        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as srv:
                            srv.ehlo()
                            srv.starttls()
                            srv.login(smtp_user, smtp_pass)
                            for dest in destinataires:
                                email_dest = dest.get("email", "").strip()
                                if not email_dest:
                                    continue
                                nom_dest = (
                                    f"{dest.get('prenom','')} {dest.get('nom','')}".strip()
                                    or email_dest
                                )
                                corps_perso = corps.replace("{{nom}}", nom_dest)
                                msg = MIMEMultipart("alternative")
                                msg["Subject"] = sujet
                                msg["From"]    = smtp_from
                                msg["To"]      = email_dest
                                msg.attach(MIMEText(corps_perso, "html", "utf-8"))
                                try:
                                    srv.sendmail(smtp_from, email_dest, msg.as_string())
                                    envoyes += 1
                                    dest.setdefault("historique", []).append({
                                        "ts": now_str,
                                        "action": "newsletter_envoyee",
                                        "detail": f"Newsletter envoyée : {sujet}"
                                    })
                                except Exception as e_dest:
                                    echecs += 1
                                    print(f"[BININGA] ⚠️  Envoi échoué pour {email_dest}: {e_dest}")
                    except smtplib.SMTPAuthenticationError:
                        erreur = "Authentification SMTP échouée — vérifiez SMTP_USER et SMTP_PASS."
                        print(f"[BININGA] ❌ SMTP auth error: {smtp_host}")
                    except smtplib.SMTPConnectError:
                        erreur = f"Impossible de se connecter au serveur SMTP ({smtp_host}:{smtp_port})."
                        print(f"[BININGA] ❌ SMTP connect error: {smtp_host}:{smtp_port}")
                    except Exception as e_smtp:
                        erreur = f"Erreur SMTP : {str(e_smtp)}"
                        print(f"[BININGA] ❌ SMTP error: {e_smtp}")
                else:
                    erreur = ("SMTP non configuré. "
                              "Définissez SMTP_HOST, SMTP_USER, SMTP_PASS dans les variables d'environnement.")
                    print("[BININGA] ⚠️  Newsletter demandée mais SMTP non configuré.")
                # Historiser la newsletter
                nl_entry = {
                    "id":           nl_id,
                    "ts":           now_str,
                    "sujet":        sujet,
                    "apercu":       corps[:400] + ("…" if len(corps) > 400 else ""),
                    "destinataires": len(destinataires),
                    "envoyes":      envoyes,
                    "statut":       "erreur" if erreur else "envoye",
                    "erreur":       erreur,
                }
                crm.setdefault("newsletters", []).insert(0, nl_entry)
                save_crm(crm)
                who = session["username"] if session else "admin"
                audit_log("CRM_NEWSLETTER", ip,
                          f"Newsletter par {who} : '{sujet}' → {envoyes}/{len(destinataires)}")
                self._json({
                    "ok":      True,
                    "envoyes": envoyes,
                    "echecs":  echecs,
                    "total":   len(destinataires),
                    "erreur":  erreur,
                })
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
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
            "mp4":  "video/mp4",
            "webm": "video/webm",
            "ogg":  "video/ogg",
            "mp3":  "audio/mpeg",
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
        if _MON and hasattr(self, "_mon_t0"):
            _mon.record_request(
                getattr(self, "command", "GET"),
                getattr(self, "_mon_path", "-"),
                status,
                (time.time() - self._mon_t0) * 1000,
                self.client_address[0],
            )

    def _error(self, code, message):
        safe_msg = _html.escape(str(message))
        response = f"<h1>{code}</h1><p>{safe_msg}</p>".encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(response))
        self._security_headers()
        self.end_headers()
        self.wfile.write(response)
        if _MON and hasattr(self, "_mon_t0"):
            _mon.record_request(
                getattr(self, "command", "GET"),
                getattr(self, "_mon_path", "-"),
                code,
                (time.time() - self._mon_t0) * 1000,
                self.client_address[0],
            )

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
    load_attack_scores()
    start_monitor()
    _monitor_watchdog()
    if _MON:
        _mon.init_db()
        _mon.start_scheduler(
            get_sessions_fn=lambda: len(ACTIVE_SESSIONS),
            get_blocked_fn=lambda: len(BLOCKED_IPS),
        )
        print("[BININGA] 📊 Monitoring démarré (monitoring.db)")

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

    class _ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True  # threads meurent quand le serveur s'arrête

    server = _ThreadedHTTPServer(("0.0.0.0", PORT), BiningaHandler)

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

        redirect_srv = _ThreadedHTTPServer(("0.0.0.0", REDIRECT_PORT), _RedirectHandler)
        threading.Thread(target=redirect_srv.serve_forever, daemon=True).start()
        print(f"🔄 Redirection HTTP:{REDIRECT_PORT} → HTTPS:{HTTPS_PORT}")
        print(f"🔒 HTTPS activé ({CERT_SOURCE})")

    print(f"✅ Serveur lancé sur {protocol}://bininga.cg:{PORT}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Serveur arrêté")
        server.server_close()
