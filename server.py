import http.server
import json
import os
from urllib.parse import urlparse, parse_qs
from datetime import datetime

DATA_FILE = "data.json"
ADMIN_USER = "admin"
ADMIN_PASS = "bininga2025"

def load_data():
    """Charge les données depuis data.json"""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    """Sauvegarde les données dans data.json"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class BininigaHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_OPTIONS(self):
        """Gère les requêtes CORS"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.end_headers()
    
    def do_GET(self):
        """Gère les requêtes GET"""
        path = urlparse(self.path).path
        
        # API: Charger les données
        if path == "/api/load":
            self._json(load_data())
            return
        
        # Fichiers statiques
        if path == "/" or path == "":
            path = "BININGA_v5.html"
        elif path == "/admin.html":
            path = "admin.html"
        else:
            if path.startswith("/"):
                path = path[1:]
        
        if os.path.isfile(path):
            try:
                with open(path, "rb") as f:
                    content = f.read()
                
                # Détermine le type MIME
                if path.endswith(".html"):
                    mime = "text/html; charset=utf-8"
                elif path.endswith(".json"):
                    mime = "application/json"
                elif path.endswith(".css"):
                    mime = "text/css"
                elif path.endswith(".js"):
                    mime = "text/javascript"
                elif path.endswith(".png"):
                    mime = "image/png"
                elif path.endswith(".jpg") or path.endswith(".jpeg"):
                    mime = "image/jpeg"
                elif path.endswith(".gif"):
                    mime = "image/gif"
                elif path.endswith(".svg"):
                    mime = "image/svg+xml"
                else:
                    mime = "application/octet-stream"
                
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", len(content))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self._error(500, str(e))
        else:
            self._error(404, "Fichier non trouvé")
    
    def do_POST(self):
        """Gère les requêtes POST"""
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        
        # API: Sauvegarder les données (avec authentification)
        if path == "/api/save":
            # Vérifie l'authentification
            token = self.headers.get("X-Admin-Token", "")
            expected_token = f"{ADMIN_USER}:{ADMIN_PASS}"
            
            if token != expected_token:
                self._json({"ok": False, "message": "Non autorisé"}, 401)
                return
            
            try:
                data = json.loads(body.decode("utf-8"))
                save_data(data)
                print(f"[BININGA] ✅ Données sauvegardées — {datetime.now().strftime('%H:%M:%S')}")
                self._json({"ok": True, "message": "Données sauvegardées"})
            except Exception as e:
                print(f"[BININGA] ❌ Erreur sauvegarde: {str(e)}")
                self._json({"ok": False, "message": f"Erreur: {str(e)}"}, 400)
            return
        
        self._error(404, "Route non trouvée")
    
    def _json(self, data, status=200):
        """Envoie une réponse JSON"""
        response = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response)
    
    def _error(self, code, message):
        """Envoie une erreur"""
        response = f"<h1>{code}</h1><p>{message}</p>".encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response)
    
    def log_message(self, format, *args):
        """Log personnalisé"""
        method = args[0] if args else "?"
        path = args[1] if len(args) > 1 else "?"
        print(f"[BININGA] {method} {path}")

if __name__ == "__main__":
    PORT = 8080
    
    print("""
╔══════════════════════════════════════════╗
  ║   BININGA — Serveur local               ║
  ║   http://localhost:8080                 ║
  ║                                        ║
  ║   Site  →  http://localhost:8080       ║
  ║   Admin →  http://localhost:8080/admin.html  ║
  ║                                        ║
  ║   Admin: admin / bininga2025            ║
  ╚══════════════════════════════════════════╝
    """)
    
    server = http.server.HTTPServer(("0.0.0.0", PORT), BininigaHandler)
    print(f"✅ Serveur lancé sur http://localhost:{PORT}\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n❌ Serveur arrêté")
        server.server_close()
