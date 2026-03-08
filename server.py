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
DATA_FILE  = "data.json"
ADMIN_USER = os.environ.get("BININGA_USER", "admin")
ADMIN_PASS = os.environ.get("BININGA_PASS", "bininga2025")

# Token de session généré aléatoirement au démarrage (64 caractères hex)
# Change à chaque redémarrage — jamais visible dans le code source
SESSION_TOKEN = secrets.token_hex(32)

def _hash(val):
    return hashlib.sha256(val.encode()).hexdigest()

H_USER = _hash(ADMIN_USER)
H_PASS = _hash(ADMIN_PASS)

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
                u = _hash(creds.get("username", ""))
                p = _hash(creds.get("password", ""))
                if u == H_USER and p == H_PASS:
                    print(f"[BININGA] 🔓 Connexion admin — {datetime.now().strftime('%H:%M:%S')}")
                    self._json({"ok": True, "token": SESSION_TOKEN})
                else:
                    print(f"[BININGA] ⛔ Tentative de connexion échouée — {datetime.now().strftime('%H:%M:%S')}")
                    self._json({"ok": False, "message": "Identifiant ou mot de passe incorrect"}, 401)
            except Exception as e:
                self._json({"ok": False, "message": str(e)}, 400)
            return

        # ── Vérification token pour les routes protégées ──
        token = self.headers.get("X-Admin-Token", "")
        if token != SESSION_TOKEN:
            self._json({"ok": False, "message": "Non autorisé"}, 401)
            return

        # ── /api/upload ──
        if path == "/api/upload":
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
            print(f"[BININGA] 📷 Image uploadée : {safe_name}")
            self._json({"ok": True, "path": "images/" + safe_name})
            return

        # ── /api/save ──
        if path == "/api/save":
            try:
                data = json.loads(body.decode("utf-8"))
                save_data(data)
                print(f"[BININGA] ✅ Données sauvegardées — {datetime.now().strftime('%H:%M:%S')}")
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
