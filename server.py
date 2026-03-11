import http.server
import json
import os
import io
import ssl
import cgi
import secrets
import hashlib
from urllib.parse import urlparse
from datetime import datetime

# ── Configuration ──────────────────────────────────────────
DATA_FILE       = "data.json"
AUDIT_FILE      = "audit.log"
USERS_FILE      = "users.json"
ADMIN_USER      = os.environ.get("BININGA_USER", "admin")
ADMIN_PASS      = os.environ.get("BININGA_PASS", "bininga2025")
PROTECTED_USER  = os.environ.get("BININGA_PROTECTED", "rodrin")  # compte intouchable par le ministre

# Sessions actives : token → {username, role, nom}
ACTIVE_SESSIONS = {}

def _hash(val):
    return hashlib.sha256(val.encode()).hexdigest()

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
        save_users([{
            "username": ADMIN_USER,
            "password_hash": _hash(ADMIN_PASS),
            "role": "admin",
            "nom": "Rodrin Bakala"
        }])
        print(f"[BININGA] 📁 users.json créé (compte : {ADMIN_USER})")

def find_user(username):
    return next((u for u in load_users() if u["username"] == username), None)

def get_session(token):
    return ACTIVE_SESSIONS.get(token)

def has_role(token, *roles):
    s = get_session(token)
    return s is not None and s["role"] in roles

# ── Audit ──────────────────────────────────────────────────
def audit_log(action, ip="", detail=""):
    """Écrit une entrée dans audit.log (format JSON Lines)."""
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
            os.remove(old)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Init au chargement du module ───────────────────────────
init_users()

# ── Handler ────────────────────────────────────────────────
class BiningaHandler(http.server.SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/load":
            self._json(load_data())
            return

        if path == "/api/logs":
            token = self.headers.get("X-Admin-Token", "")
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            self._json({"ok": True, "logs": load_audit()})
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

        if path == "/" or path == "":
            path = "index.html"
        elif path.startswith("/"):
            path = path[1:]

        if os.path.isfile(path):
            try:
                with open(path, "rb") as f:
                    content = f.read()
                mime = self._mime(path)
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", len(content))
                self.send_header("Access-Control-Allow-Origin", "*")
                if mime.startswith("text/html"):
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self._error(500, str(e))
        else:
            self._error(404, "Fichier non trouvé")

    def do_POST(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        # ── /api/login : vérifie les credentials côté serveur ──
        if path == "/api/login":
            try:
                creds = json.loads(body.decode("utf-8"))
                username = creds.get("username", "")
                password = creds.get("password", "")
                ip = self.client_address[0]
                user = find_user(username)
                if user and user.get("password_hash") == _hash(password):
                    token = secrets.token_hex(32)
                    ACTIVE_SESSIONS[token] = {
                        "username": user["username"],
                        "role":     user["role"],
                        "nom":      user.get("nom", user["username"])
                    }
                    print(f"[BININGA] 🔓 Connexion : {username} ({user['role']}) — {datetime.now().strftime('%H:%M:%S')}")
                    audit_log("LOGIN_OK", ip, f"Connexion de {username} ({user['role']})")
                    self._json({"ok": True, "token": token,
                                "role": user["role"], "nom": user.get("nom", username)})
                else:
                    print(f"[BININGA] ⛔ Tentative échouée : {username} — {datetime.now().strftime('%H:%M:%S')}")
                    audit_log("LOGIN_FAIL", ip, f"Identifiant ou mot de passe incorrect (user: {username})")
                    self._json({"ok": False, "message": "Identifiant ou mot de passe incorrect"}, 401)
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── /api/upload-sinistre (public — photo de réclamation citoyenne) ──
        if path == "/api/upload-sinistre":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._json({"ok": False, "message": "Format invalide"}, 400)
                return
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(length),
            }
            form = cgi.FieldStorage(fp=io.BytesIO(body), environ=environ)
            if "file" not in form:
                self._json({"ok": False, "message": "Pas de fichier"}, 400)
                return
            file_item = form["file"]
            raw_name  = os.path.basename(file_item.filename or "sinistre.jpg")
            safe_name = "".join(c for c in raw_name if c.isalnum() or c in ".-_") or "sinistre.jpg"
            if not any(safe_name.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                self._json({"ok": False, "message": "Type de fichier non autorisé (jpg/png/webp uniquement)"}, 400)
                return
            data_bytes = file_item.file.read()
            if len(data_bytes) > 3 * 1024 * 1024:
                self._json({"ok": False, "message": "Fichier trop volumineux (max 3 Mo)"}, 400)
                return
            uid = secrets.token_hex(6)
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{ts}_{uid}.jpg"
            os.makedirs(os.path.join("images", "sinistres"), exist_ok=True)
            with open(os.path.join("images", "sinistres", fname), "wb") as f:
                f.write(data_bytes)
            ip = self.client_address[0]
            audit_log("SINISTRE_PHOTO", ip, f"Photo sinistre reçue : {fname}")
            self._json({"ok": True, "path": "images/sinistres/" + fname})
            return

        # ── Vérification token pour les routes protégées ──
        token = self.headers.get("X-Admin-Token", "")
        if not get_session(token):
            self._json({"ok": False, "message": "Non autorisé"}, 401)
            return
        if path == "/api/users/upsert":
            if not has_role(token, "admin", "ministre"):
                self._json({"ok": False, "message": "Réservé à l'admin ou au ministre"}, 403)
                return
            try:
                data = json.loads(body.decode("utf-8"))
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
                users = load_users()
                existing = next((u for u in users if u["username"] == uname), None)
                if existing:
                    existing["nom"]  = nom or existing["nom"]
                    existing["role"] = role
                    if pwd:
                        existing["password_hash"] = _hash(pwd)
                else:
                    if not pwd:
                        self._json({"ok": False, "message": "Mot de passe requis"}, 400)
                        return
                    users.append({"username": uname, "password_hash": _hash(pwd), "role": role, "nom": nom or uname})
                save_users(users)
                ip = self.client_address[0]
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
                data  = json.loads(body.decode("utf-8"))
                uname = data.get("username", "")
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
                ip = self.client_address[0]
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
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(length),
            }
            form = cgi.FieldStorage(fp=io.BytesIO(body), environ=environ)
            if "file" not in form:
                self._json({"ok": False, "message": "Pas de fichier"}, 400)
                return
            file_item = form["file"]
            raw_name  = os.path.basename(file_item.filename or "upload.jpg")
            safe_name = "".join(c for c in raw_name if c.isalnum() or c in ".-_") or "image.jpg"
            # Vérifier extension image
            if not any(safe_name.lower().endswith(ext) for ext in (".jpg",".jpeg",".png",".gif",".webp",".svg")):
                self._json({"ok": False, "message": "Type de fichier non autorisé"}, 400)
                return
            # Limite 10 Mo
            data_bytes = file_item.file.read()
            if len(data_bytes) > 10 * 1024 * 1024:
                self._json({"ok": False, "message": "Fichier trop volumineux (max 10 Mo)"}, 400)
                return
            os.makedirs("images", exist_ok=True)
            with open(os.path.join("images", safe_name), "wb") as f:
                f.write(data_bytes)
            ip = self.client_address[0]
            print(f"[BININGA] 📷 Image uploadée : {safe_name}")
            audit_log("UPLOAD", ip, f"Image uploadée : {safe_name}")
            self._json({"ok": True, "path": "images/" + safe_name})
            return

        # ── /api/save ──
        if path == "/api/save":
            if not has_role(token, "admin", "editeur", "ministre"):
                self._json({"ok": False, "message": "Accès refusé"}, 403)
                return
            try:
                data = json.loads(body.decode("utf-8"))
                ip = self.client_address[0]
                save_data(data)
                print(f"[BININGA] ✅ Données sauvegardées — {datetime.now().strftime('%H:%M:%S')}")
                session = get_session(token)
                who = session["username"] if session else "?"
                audit_log("SAVE", ip, f"data.json sauvegardé par {who}")
                self._json({"ok": True, "message": "Données sauvegardées"})
            except Exception as e:
                print(f"[BININGA] ❌ Erreur sauvegarde : {e}")
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
        }.get(ext, "application/octet-stream")

    def _json(self, data, status=200):
        response = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response)

    def _error(self, code, message):
        response = f"<h1>{code}</h1><p>{message}</p>".encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        pass  # Logs gérés manuellement

# ── Lancement ──────────────────────────────────────────────
if __name__ == "__main__":
    init_users()
    PORT     = int(os.environ.get("PORT", 8080))
    USE_SSL  = os.path.isfile("cert.pem") and os.path.isfile("key.pem")
    protocol = "https" if USE_SSL else "http"

    print(f"""
╔══════════════════════════════════════════════╗
  ║   BININGA — Serveur                         ║
  ║                                            ║
  ║   Site  →  {protocol}://localhost:{PORT}        ║
  ║   Admin →  {protocol}://localhost:{PORT}/admin.html ║
  ║                                            ║
  ║   SSL : {"✅ Activé  (cert.pem + key.pem)" if USE_SSL else "⚠️  Désactivé  (pas de cert.pem)"}  ║
  ╚══════════════════════════════════════════════╝
    """)

    server = http.server.HTTPServer(("0.0.0.0", PORT), BiningaHandler)

    if USE_SSL:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain("cert.pem", "key.pem")
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        print("🔒 HTTPS activé")

    print(f"✅ Serveur lancé sur {protocol}://localhost:{PORT}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Serveur arrêté")
        server.server_close()
