"""
Tests automatiques — Serveur BININGA
Lancés par GitHub Actions à chaque git push
"""
import json
import os
import sys
import threading
import time
import urllib.request
import urllib.error

# Ajoute le dossier parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = 18080  # Port de test (différent du port prod)


def start_test_server():
    """Démarre le serveur dans un thread pour les tests."""
    import http.server
    import server as srv

    handler = srv.BiningaHandler
    httpd = http.server.HTTPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.5)  # Laisse le serveur démarrer
    return httpd


def get(path):
    url = f"http://127.0.0.1:{PORT}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, ""


def post(path, data, token=None):
    url = f"http://127.0.0.1:{PORT}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Admin-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


# ── Tests ─────────────────────────────────────────────────────

def test_index_accessible():
    status, body = get("/")
    assert status == 200, f"index.html doit retourner 200, reçu {status}"
    assert "<html" in body.lower(), "index.html doit contenir du HTML"
    print("✅ test_index_accessible")


def test_api_load():
    status, body = get("/api/load")
    assert status == 200, f"/api/load doit retourner 200, reçu {status}"
    data = json.loads(body)
    for key in ["hero", "about", "actus", "gallery"]:
        assert key in data, f"data.json doit contenir la clé '{key}'"
    print("✅ test_api_load")


def test_admin_accessible():
    status, body = get("/admin.html")
    assert status == 200, f"admin.html doit retourner 200, reçu {status}"
    print("✅ test_admin_accessible")


def test_404_fichier_inexistant():
    status, _ = get("/fichier-qui-nexiste-pas.html")
    assert status == 404, f"Fichier inexistant doit retourner 404, reçu {status}"
    print("✅ test_404_fichier_inexistant")


def test_login_mauvais_mot_de_passe():
    status, body = post("/api/login", {"username": "admin", "password": "mauvais"})
    assert status == 401, f"Mauvais mot de passe doit retourner 401, reçu {status}"
    assert body.get("ok") == False
    print("✅ test_login_mauvais_mot_de_passe")


def test_login_correct():
    import server as srv
    # Utilise les credentials par défaut du serveur
    user = os.environ.get("BININGA_USER", "admin")
    pwd  = os.environ.get("BININGA_PASS", "bininga2025")
    status, body = post("/api/login", {"username": user, "password": pwd})
    assert status == 200, f"Login correct doit retourner 200, reçu {status}"
    assert body.get("ok") == True, "Login correct doit retourner ok=True"
    assert "token" in body, "Login correct doit retourner un token"
    print("✅ test_login_correct")
    return body["token"]


def test_save_sans_token():
    status, body = post("/api/save", {"hero": {}})
    assert status == 401, f"Save sans token doit retourner 401, reçu {status}"
    print("✅ test_save_sans_token")


def test_logs_sans_token():
    status, body = get("/api/logs")
    assert status == 401, f"/api/logs sans token doit retourner 401, reçu {status}"
    print("✅ test_logs_sans_token")


def test_logs_avec_token():
    user = os.environ.get("BININGA_USER", "admin")
    pwd  = os.environ.get("BININGA_PASS", "bininga2025")
    _, login_body = post("/api/login", {"username": user, "password": pwd})
    token = login_body.get("token", "")

    url = f"http://127.0.0.1:{PORT}/api/logs"
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Token", token)
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read().decode("utf-8"))
    assert data.get("ok") == True, "/api/logs doit retourner ok=True"
    assert "logs" in data, "/api/logs doit retourner une clé 'logs'"
    assert isinstance(data["logs"], list), "logs doit être une liste"
    # Vérifie qu'au moins le login précédent est dans les logs
    actions = [e["action"] for e in data["logs"]]
    assert "LOGIN_OK" in actions, "Le login réussi doit apparaître dans les logs"
    print("✅ test_logs_avec_token")


def test_data_json_structure():
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "hero" in data and "firstName" in data["hero"]
    assert "actus" in data and "featured" in data["actus"]
    assert "gallery" in data and "slides" in data["gallery"]
    print("✅ test_data_json_structure")


# ── Lancement ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🧪 Lancement des tests BININGA...\n")

    # Test structure JSON (sans serveur)
    test_data_json_structure()

    # Tests avec serveur
    srv = start_test_server()
    try:
        test_index_accessible()
        test_api_load()
        test_admin_accessible()
        test_404_fichier_inexistant()
        test_login_mauvais_mot_de_passe()
        test_login_correct()
        test_save_sans_token()
        test_logs_sans_token()
        test_logs_avec_token()
    finally:
        srv.shutdown()

    print("\n╔══════════════════════════════════════╗")
    print("  ✅ Tous les tests ont réussi !")
    print("╚══════════════════════════════════════╝\n")
