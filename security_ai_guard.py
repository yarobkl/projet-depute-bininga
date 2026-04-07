"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         BININGA SECURITY SHIELD — OPERATION BOUCLIER v2.0                  ║
║         Forces Spéciales Numériques — Anti-IA / Anti-Bot / Anti-Intrusion  ║
╚══════════════════════════════════════════════════════════════════════════════╝

6 COUCHES DE DÉFENSE ACTIVE :

  COUCHE 1  RECONNAISSANCE  — Identification des robots, agents IA, crawlers
  COUCHE 2  FIREWALL        — Murs de feu dynamiques qui s'intensifient
  COUCHE 3  LOCKDOWN        — Mode sécurité total (activation automatique)
  COUCHE 4  COFFRE-FORT     — Protection renforcée des fichiers sensibles
  COUCHE 5  CANARIS         — Pièges actifs (honeypots étendus + alertes)
  COUCHE 6  CONTRE-MESURES  — Réponses graduelles : tarpit → challenge → ban

Usage :
    from security_ai_guard import AIGuard
    guard = AIGuard()
    blocked, reason = guard.inspect(ip, method, path, headers, body)
"""

import re
import time
import json
import os
import threading
import hashlib
import ipaddress
from datetime import datetime
from collections import defaultdict, deque
from typing import Optional, Tuple

# ══════════════════════════════════════════════════════════════════════════════
# ██  COUCHE 1 — RECONNAISSANCE  (détection IA/bots/crawlers)                ██
# ══════════════════════════════════════════════════════════════════════════════

# Agents IA connus qui scrappent / crawlent
_AI_AGENTS = re.compile(
    r"(?:"
    r"GPTBot|ChatGPT-User|OAI-SearchBot"           # OpenAI
    r"|Google-Extended|Bard|Gemini"                 # Google
    r"|ClaudeBot|Claude-Web|anthropic-ai"           # Anthropic
    r"|PerplexityBot|Perplexity"                    # Perplexity
    r"|YouBot|you\.com"                             # You.com
    r"|meta-externalagent|FacebookBot|facebookexternalhit"  # Meta
    r"|Applebot-Extended|Applebot"                  # Apple
    r"|Bytespider|TikTokBot"                        # ByteDance
    r"|CCBot|Common Crawl"                          # Common Crawl
    r"|DataForSeoBot|SemrushBot|AhrefsBot"          # SEO scrapers
    r"|MJ12bot|DotBot|BLEXBot|PetalBot"             # Generic crawlers
    r"|ia_archiver|archive\.org"                    # Internet Archive
    r"|Diffbot|ScraperAPI|scrapy"                   # Scrapers
    r"|python-httpx|python-requests|aiohttp"        # Headless libs
    r"|curl/|wget/|libwww|LWP::"                    # CLI tools
    r"|HeadlessChrome|PhantomJS|Puppeteer"          # Headless browsers
    r"|Playwright|Selenium|WebDriver"               # Automation
    r"|Go-http-client|Java/|Faraday|RestSharp"      # Backend clients
    r")",
    re.IGNORECASE
)

# Bots connus légitimes (on les log mais on ne ban pas d'emblée)
_LEGIT_BOTS = re.compile(
    r"(?:Googlebot|Bingbot|Slurp|DuckDuckBot|Baiduspider|YandexBot"
    r"|LinkedInBot|Twitterbot|facebot|ia_archiver/1\.0)",
    re.IGNORECASE
)

# Headers suspects typiques des agents automatisés
_SUSPICIOUS_HEADERS = {
    "x-forwarded-for",      # masquage proxy
    "x-real-ip",
    "via",
    "x-cluster-client-ip",
}

# User-Agents vides ou très courts = bot probable
_MIN_UA_LENGTH = 10

# ══════════════════════════════════════════════════════════════════════════════
# ██  COUCHE 2 — FIREWALL DYNAMIQUE                                           ██
# ══════════════════════════════════════════════════════════════════════════════

# Niveaux de menace
THREAT_NONE     = 0
THREAT_LOW      = 1   # surveillance
THREAT_MEDIUM   = 2   # tarpit + log
THREAT_HIGH     = 3   # challenge + alerte
THREAT_CRITICAL = 4   # ban immédiat + lockdown partiel

# Seuils de score → niveau de menace
_THREAT_LEVELS = [
    (50, THREAT_CRITICAL),
    (30, THREAT_HIGH),
    (15, THREAT_MEDIUM),
    (5,  THREAT_LOW),
]

# Tarpits par niveau (secondes de délai ajoutés)
_TARPIT_BY_LEVEL = {
    THREAT_LOW:      0.5,
    THREAT_MEDIUM:   2.0,
    THREAT_HIGH:     5.0,
    THREAT_CRITICAL: 0.0,   # pas de tarpit : ban direct
}

# Score attribué à chaque signal
_SIGNAL_SCORES = {
    "ai_agent_ua":          20,   # User-Agent identifié comme agent IA
    "headless_browser":     25,   # Navigateur headless détecté
    "scanner_tool":         30,   # Outil de scan (nikto, sqlmap…)
    "empty_ua":             10,   # User-Agent vide/court
    "no_accept_header":      5,   # Pas de header Accept (humains en ont toujours)
    "no_accept_language":    5,   # Pas de Accept-Language
    "suspicious_cadence":   15,   # Requêtes trop régulières (robot cadence)
    "path_explosion":       20,   # Trop de chemins distincts en peu de temps
    "sensitive_file_probe":  25,  # Tentative d'accès fichier sensible
    "canary_triggered":     50,   # Piège canari déclenché → ban immédiat
    "lockdown_violation":   50,   # Accès pendant lockdown sans whitelist
    "repeated_404":         10,   # Beaucoup de 404 = scan de répertoires
    "slow_drip":             8,   # Requêtes lentes espacées = scraper prudent
    "method_abuse":         20,   # Méthodes HTTP inhabituelles (TRACE, etc.)
    "oversized_ua":         10,   # UA très long = forge probable
}

# ══════════════════════════════════════════════════════════════════════════════
# ██  COUCHE 3 — MODE LOCKDOWN                                                ██
# ══════════════════════════════════════════════════════════════════════════════

class LockdownManager:
    """Gère le mode sécurité total (lockdown).
    
    En lockdown :
      - Seules les IPs whitelistées passent
      - Toutes les requêtes publiques retournent 503
      - Durée configurable (défaut : 15 min)
      - Déclenché automatiquement si menace critique ou manuellement
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._active   = False
        self._until    = 0.0
        self._reason   = ""
        self._count    = 0        # nombre de lockdowns depuis démarrage
        self._whitelist: set = set()
        # IPs toujours autorisées (admin local)
        self._whitelist.add("127.0.0.1")
        self._whitelist.add("::1")
        # Charger IPs de confiance depuis env
        trusted = os.environ.get("ADMIN_TRUSTED_IPS", "")
        for ip in trusted.split(","):
            ip = ip.strip()
            if ip:
                self._whitelist.add(ip)

    def activate(self, reason: str, duration_sec: int = 900):
        with self._lock:
            self._active = True
            self._until  = time.time() + duration_sec
            self._reason = reason
            self._count += 1
            print(f"[BOUCLIER] LOCKDOWN ACTIVE — {reason} — durée {duration_sec}s")
        _ai_audit("LOCKDOWN_ACTIVATED", "system", reason)

    def deactivate(self):
        with self._lock:
            self._active = False
            self._reason = ""
        _ai_audit("LOCKDOWN_DEACTIVATED", "system", "Lockdown levé manuellement")

    def is_active(self) -> bool:
        with self._lock:
            if self._active and time.time() > self._until:
                self._active = False
                _ai_audit("LOCKDOWN_EXPIRED", "system", "Lockdown expiré automatiquement")
            return self._active

    def is_whitelisted(self, ip: str) -> bool:
        return ip in self._whitelist

    def add_to_whitelist(self, ip: str):
        self._whitelist.add(ip)

    def status(self) -> dict:
        with self._lock:
            return {
                "active": self._active,
                "until": datetime.fromtimestamp(self._until).strftime("%H:%M:%S") if self._active else None,
                "reason": self._reason,
                "count": self._count,
                "whitelist_size": len(self._whitelist),
            }


# ══════════════════════════════════════════════════════════════════════════════
# ██  COUCHE 4 — COFFRE-FORT (fichiers sensibles)                             ██
# ══════════════════════════════════════════════════════════════════════════════

# Fichiers et chemins jamais accessibles depuis le web
_VAULT_FILES = frozenset({
    # Credentials & secrets
    "users.json", "sessions.json", ".env", ".env.local", ".env.production",
    ".env.bak", "credentials.json", "secrets.json", "config.json",
    # Clés & certificats
    "cert.pem", "key.pem", "privkey.pem", "fullchain.pem",
    "id_rsa", "id_ed25519", "id_ecdsa", ".htpasswd",
    # Logs & données sensibles
    "audit.log", "attacks.log", "attack_scores.json", "blocked_ips.json",
    "monitoring.db", "news.db",
    # Code source
    "server.py", "security_ai_guard.py",
    # Base de données
    "data.db", "database.db", "bininga.db",
    # Sauvegardes
    "backup.sql", "dump.sql", "db.sql", "backup.zip", "backup.tar.gz",
})

_VAULT_EXTENSIONS = frozenset({
    ".py", ".pyc", ".pyo", ".env", ".key", ".pem", ".pfx",
    ".p12", ".crt", ".cer", ".der", ".sh", ".bash", ".sql",
    ".db", ".sqlite", ".sqlite3", ".log", ".bak", ".swp",
    ".orig", ".cfg", ".ini", ".conf", ".config",
})

_VAULT_PREFIXES = (
    "/.git/", "/.ssh/", "/.aws/", "/__pycache__/",
    "/node_modules/", "/.github/",
)

def is_vault_protected(path: str) -> bool:
    """Retourne True si le chemin touche un fichier du coffre-fort."""
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower()

    if filename in _VAULT_FILES:
        return True
    if ext in _VAULT_EXTENSIONS:
        return True
    for prefix in _VAULT_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# ██  COUCHE 5 — CANARIS (pièges actifs étendus)                             ██
# ══════════════════════════════════════════════════════════════════════════════

# Chemins canaris : tout accès déclenche alerte immédiate + score critique
_CANARY_PATHS = frozenset({
    # Fichiers de config piégés
    "/.well-known/secret-admin",
    "/api/internal/dump",
    "/api/v0/users",
    "/api/debug/config",
    "/api/admin/export",
    "/backup",
    "/exports",
    # Chemins WordPress piégés
    "/wp-admin", "/wp-login.php", "/wp-json/wp/v2/users",
    "/wp-content/uploads/", "/xmlrpc.php",
    # Exploits communs
    "/.env", "/.env.bak", "/config.yml", "/config.yaml",
    "/.git/config", "/.git/HEAD", "/.git/FETCH_HEAD",
    "/phpmyadmin/", "/pma/", "/mysql/",
    "/shell.php", "/cmd.php", "/c99.php", "/eval.php",
    "/actuator/env", "/actuator/beans", "/actuator/dump",
    "/v1/secret", "/v2/secret",
    # Chemins API courants
    "/graphql", "/graphiql", "/__graphql",
    "/swagger.json", "/openapi.json", "/api-docs",
    # Fichiers de sauvegarde courants
    "/site.tar.gz", "/www.zip", "/backup.zip",
    "/dump.sql", "/database.sql",
    # Tentatives de lecture système
    "/etc/passwd", "/etc/shadow", "/proc/self/environ",
    "/windows/win.ini", "/boot.ini",
})

def is_canary_path(path: str) -> bool:
    """Vérifie si le chemin est un piège canari."""
    path_lower = path.lower()
    if path_lower in _CANARY_PATHS:
        return True
    # Canaris par suffixe
    for canary in _CANARY_PATHS:
        if path_lower.startswith(canary.rstrip("/") + "/"):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# ██  COUCHE 6 — CONTRE-MESURES (analyse comportementale)                    ██
# ══════════════════════════════════════════════════════════════════════════════

class BehaviorTracker:
    """Analyse comportementale par IP pour détecter les patterns robots."""

    # Fenêtre d'analyse (secondes)
    WINDOW = 60

    # Seuils de détection
    MAX_DISTINCT_PATHS  = 40    # chemins distincts / minute → scan
    MAX_404_COUNT       = 15    # 404 / minute → scanner
    MIN_INTERVAL_MS     = 200   # < 200ms entre requêtes → bot mécanique
    CADENCE_VARIANCE_MS = 50    # variance < 50ms sur 5 req → cadence robot

    def __init__(self):
        self._lock    = threading.Lock()
        # ip → {"timestamps": deque, "paths": set, "404s": int, "intervals": deque}
        self._data: dict = {}

    def _cleanup_old(self, entry: dict, now: float):
        ts = entry["timestamps"]
        while ts and now - ts[0] > self.WINDOW:
            ts.popleft()
        ivs = entry["intervals"]
        while ivs and len(ivs) > 10:
            ivs.popleft()

    def record(self, ip: str, path: str, status: int = 200) -> dict:
        """Enregistre une requête et retourne les signaux détectés."""
        now = time.time()
        signals = {}
        with self._lock:
            if ip not in self._data:
                self._data[ip] = {
                    "timestamps": deque(),
                    "paths": set(),
                    "404s": 0,
                    "intervals": deque(),
                    "last_ts": None,
                }
            entry = self._data[ip]
            self._cleanup_old(entry, now)

            # Intervalle entre requêtes
            if entry["last_ts"] is not None:
                interval_ms = (now - entry["last_ts"]) * 1000
                entry["intervals"].append(interval_ms)
                # Trop rapide → bot mécanique
                if interval_ms < self.MIN_INTERVAL_MS:
                    signals["suspicious_cadence"] = True
                # Cadence très régulière sur plusieurs requêtes
                if len(entry["intervals"]) >= 5:
                    ivs = list(entry["intervals"])[-5:]
                    variance = max(ivs) - min(ivs)
                    if variance < self.CADENCE_VARIANCE_MS:
                        signals["suspicious_cadence"] = True

            entry["last_ts"] = now
            entry["timestamps"].append(now)
            entry["paths"].add(path)

            # 404 répétés
            if status == 404:
                entry["404s"] += 1
                if entry["404s"] > self.MAX_404_COUNT:
                    signals["repeated_404"] = True

            # Explosion de chemins distincts
            if len(entry["paths"]) > self.MAX_DISTINCT_PATHS:
                signals["path_explosion"] = True

        return signals

    def get_stats(self, ip: str) -> dict:
        with self._lock:
            entry = self._data.get(ip, {})
            return {
                "requests_last_min": len(entry.get("timestamps", [])),
                "distinct_paths": len(entry.get("paths", set())),
                "404_count": entry.get("404s", 0),
            }


# ══════════════════════════════════════════════════════════════════════════════
# ██  MOTEUR CENTRAL — AIGuard                                                ██
# ══════════════════════════════════════════════════════════════════════════════

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def _ai_audit(action: str, ip: str, detail: str = ""):
    """Écrit dans le log de sécurité IA."""
    entry = {
        "ts":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "module": "AI_GUARD",
        "action": action,
        "ip":     ip,
        "detail": detail[:300],
    }
    try:
        log_path = os.path.join(_DATA_DIR, "ai_guard.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


class AIGuard:
    """
    Contrôleur principal du Bouclier de Sécurité Bininga.
    
    Instancier une fois au démarrage :
        guard = AIGuard()
    
    Appeler sur chaque requête :
        blocked, reason = guard.inspect(ip, method, path, headers, body_size)
    
    Intégrer le lockdown dans le handler admin :
        guard.lockdown.activate("raison")
        guard.lockdown.deactivate()
        guard.lockdown.status()
    """

    # Score minimal pour ban temporaire automatique
    AUTO_BAN_THRESHOLD = 40

    def __init__(self):
        self.lockdown = LockdownManager()
        self.behavior = BehaviorTracker()
        self._lock    = threading.Lock()
        # ip → cumulative score
        self._scores: dict = {}
        # ips temporairement bannies par ce module (distinct des BLOCKED_IPS server)
        self._temp_banned: dict = {}   # ip → until_ts
        self._load_state()
        self._start_cleanup_thread()

    # ── Persistance ────────────────────────────────────────────────────────────

    def _state_file(self) -> str:
        return os.path.join(_DATA_DIR, "ai_guard_state.json")

    def _load_state(self):
        try:
            with open(self._state_file(), "r") as f:
                state = json.load(f)
            self._scores = state.get("scores", {})
            # Restaurer les bans encore actifs
            now = time.time()
            for ip, until in state.get("temp_banned", {}).items():
                if until > now:
                    self._temp_banned[ip] = until
        except Exception:
            pass

    def _save_state(self):
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            state = {
                "scores":     self._scores,
                "temp_banned": {k: v for k, v in self._temp_banned.items()
                                if v > time.time()},
                "saved_at":   datetime.now().isoformat(),
            }
            with open(self._state_file(), "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── Nettoyage périodique ────────────────────────────────────────────────────

    def _start_cleanup_thread(self):
        def _loop():
            while True:
                time.sleep(300)    # toutes les 5 min
                self._cleanup()
                self._save_state()
        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def _cleanup(self):
        now = time.time()
        with self._lock:
            expired = [ip for ip, until in self._temp_banned.items() if until <= now]
            for ip in expired:
                del self._temp_banned[ip]

    # ── Score & ban ────────────────────────────────────────────────────────────

    def _add_score(self, ip: str, signal: str, detail: str = "") -> int:
        """Ajoute le score du signal et retourne le nouveau total."""
        pts = _SIGNAL_SCORES.get(signal, 5)
        with self._lock:
            self._scores[ip] = self._scores.get(ip, 0) + pts
            total = self._scores[ip]
        _ai_audit(f"SIGNAL_{signal.upper()}", ip, detail or signal)
        return total

    def _get_score(self, ip: str) -> int:
        return self._scores.get(ip, 0)

    def _get_threat_level(self, ip: str) -> int:
        score = self._get_score(ip)
        for threshold, level in _THREAT_LEVELS:
            if score >= threshold:
                return level
        return THREAT_NONE

    def _temp_ban(self, ip: str, duration: int = 3600, reason: str = ""):
        until = time.time() + duration
        with self._lock:
            self._temp_banned[ip] = until
        _ai_audit("TEMP_BAN", ip, f"Banni {duration}s — {reason}")
        print(f"[BOUCLIER] BAN TEMPORAIRE : {ip} pour {duration}s — {reason}")

    def is_banned(self, ip: str) -> bool:
        with self._lock:
            until = self._temp_banned.get(ip, 0)
            if until and time.time() < until:
                return True
            elif until:
                del self._temp_banned[ip]
        return False

    # ── Analyse des headers ────────────────────────────────────────────────────

    def _analyze_headers(self, ip: str, headers: dict) -> list:
        """Retourne la liste des signaux détectés dans les headers."""
        signals = []
        ua = headers.get("user-agent", headers.get("User-Agent", "")).strip()

        # User-Agent vide ou trop court
        if len(ua) < _MIN_UA_LENGTH:
            signals.append(("empty_ua", f"UA trop court: '{ua[:30]}'"))

        # User-Agent trop long (forgé)
        elif len(ua) > 512:
            signals.append(("oversized_ua", f"UA trop long: {len(ua)} chars"))

        # Agent IA connu
        elif _AI_AGENTS.search(ua):
            # Pas de ban d'emblée pour les bots légitimes
            if not _LEGIT_BOTS.search(ua):
                signals.append(("ai_agent_ua", f"Agent IA: {ua[:80]}"))

        # Headless browser
        if re.search(r"HeadlessChrome|PhantomJS|Puppeteer|Playwright|Selenium|WebDriver",
                     ua, re.I):
            signals.append(("headless_browser", f"Headless: {ua[:80]}"))

        # Pas de header Accept (tous les navigateurs l'envoient)
        if not headers.get("accept", headers.get("Accept", "")):
            signals.append(("no_accept_header", "Pas de header Accept"))

        # Pas de Accept-Language
        if not headers.get("accept-language", headers.get("Accept-Language", "")):
            signals.append(("no_accept_language", "Pas de Accept-Language"))

        return signals

    # ── Méthode principale d'inspection ────────────────────────────────────────

    def inspect(
        self,
        ip: str,
        method: str,
        path: str,
        headers: dict,
        body_size: int = 0,
    ) -> Tuple[bool, str]:
        """
        Inspecte une requête entrante.
        
        Retourne (blocked: bool, reason: str).
        Si blocked=True, renvoyer HTTP 403.
        """

        # ── COUCHE 3 : Lockdown ────────────────────────────────────────────────
        if self.lockdown.is_active():
            if not self.lockdown.is_whitelisted(ip):
                score = self._add_score(ip, "lockdown_violation")
                _ai_audit("LOCKDOWN_BLOCK", ip, path)
                return True, f"Mode sécurité actif — accès refusé ({self.lockdown._reason})"

        # ── Ban temporaire existant ────────────────────────────────────────────
        if self.is_banned(ip):
            return True, "IP temporairement bannie (AI Guard)"

        # ── COUCHE 5 : Canaris ─────────────────────────────────────────────────
        if is_canary_path(path):
            score = self._add_score(ip, "canary_triggered", f"Canari: {path}")
            _ai_audit("CANARY_HIT", ip, path)
            # Ban immédiat 24h
            self._temp_ban(ip, 86400, f"Piège canari déclenché: {path}")
            # Si score dépasse le seuil → lockdown partiel
            if score >= 80 and not self.lockdown.is_active():
                self.lockdown.activate(
                    f"Canari déclenché depuis {ip} — {path}",
                    duration_sec=600
                )
            return True, f"Accès refusé (piège détecté)"

        # ── COUCHE 4 : Coffre-fort ─────────────────────────────────────────────
        if is_vault_protected(path):
            score = self._add_score(ip, "sensitive_file_probe", f"Coffre: {path}")
            _ai_audit("VAULT_PROBE", ip, path)
            if score >= self.AUTO_BAN_THRESHOLD:
                self._temp_ban(ip, 7200, f"Sonde fichier sensible: {path}")
            return True, "Accès refusé (fichier protégé)"

        # ── Méthodes HTTP abusives ─────────────────────────────────────────────
        if method in ("TRACE", "TRACK", "DEBUG", "CONNECT"):
            self._add_score(ip, "method_abuse", f"Méthode: {method}")
            return True, f"Méthode HTTP non autorisée: {method}"

        # ── COUCHE 1 : Analyse headers ─────────────────────────────────────────
        header_signals = self._analyze_headers(ip, headers)
        total_score = self._get_score(ip)
        for signal, detail in header_signals:
            total_score = self._add_score(ip, signal, detail)

        # ── COUCHE 6 : Comportement ────────────────────────────────────────────
        behavior_signals = self.behavior.record(ip, path)
        for signal in behavior_signals:
            total_score = self._add_score(ip, signal, f"Comportement: {signal}")

        # ── COUCHE 2 : Niveau de menace et réponse ────────────────────────────
        threat = self._get_threat_level(ip)

        if threat == THREAT_CRITICAL:
            self._temp_ban(ip, 3600, f"Score critique: {total_score}")
            return True, f"Accès refusé — menace critique détectée"

        if threat == THREAT_HIGH:
            # Tarpit intensif
            delay = _TARPIT_BY_LEVEL[THREAT_HIGH]
            time.sleep(delay)
            _ai_audit("TARPIT_HIGH", ip, f"Délai {delay}s, score={total_score}")

        elif threat == THREAT_MEDIUM:
            delay = _TARPIT_BY_LEVEL[THREAT_MEDIUM]
            time.sleep(delay)

        elif threat == THREAT_LOW:
            delay = _TARPIT_BY_LEVEL[THREAT_LOW]
            time.sleep(delay)

        # Blocage si IA agent confirmé et score significatif
        if total_score >= self.AUTO_BAN_THRESHOLD:
            self._temp_ban(ip, 1800, f"Score automatique: {total_score}")
            return True, "Accès refusé — robot/agent IA détecté"

        return False, ""

    # ── API de gestion ─────────────────────────────────────────────────────────

    def get_report(self) -> dict:
        """Retourne un rapport complet pour l'interface admin."""
        now = time.time()
        top_threats = sorted(
            self._scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]
        return {
            "lockdown":   self.lockdown.status(),
            "temp_banned": sum(1 for v in self._temp_banned.values() if v > now),
            "tracked_ips": len(self._scores),
            "top_threats": [
                {"ip": ip, "score": score, "level": self._get_threat_level(ip)}
                for ip, score in top_threats
            ],
        }

    def manual_ban(self, ip: str, duration: int = 86400, reason: str = "Admin"):
        """Ban manuel via l'interface admin."""
        self._temp_ban(ip, duration, f"BAN MANUEL — {reason}")

    def manual_unban(self, ip: str):
        """Levée de ban manuel."""
        with self._lock:
            self._temp_banned.pop(ip, None)
            self._scores.pop(ip, None)
        _ai_audit("MANUAL_UNBAN", ip, "Débannissement manuel")

    def reset_ip(self, ip: str):
        """Remet à zéro le score d'une IP."""
        with self._lock:
            self._scores.pop(ip, None)
            self._temp_banned.pop(ip, None)


# ── Instance globale ────────────────────────────────────────────────────────────
AI_GUARD = AIGuard()
