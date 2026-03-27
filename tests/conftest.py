"""
conftest.py — Fixture pytest pour démarrer le serveur de test BININGA
"""
import http.server
import json
import os
import shutil
import sys
import threading
import time

# Ajoute le dossier parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = 18080
TEST_PASS = "test123"
_httpd = None
_users_backup = None
USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "users.json")
SESSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions.json")


def pytest_configure(config):
    """Démarre le serveur une seule fois avant tous les tests."""
    global _httpd, _users_backup

    os.environ["BININGA_TEST"] = "1"
    os.environ["BININGA_PASS"] = TEST_PASS

    # Sauvegarde users.json et le remplace par un fichier de test
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            _users_backup = f.read()

    import server as srv

    # Crée un users.json de test avec le mot de passe connu
    test_users = [{
        "username": "admin",
        "password_hash": srv._hash_new(TEST_PASS),
        "role": "admin",
        "nom": "Test Admin"
    }]
    with open(USERS_FILE, "w") as f:
        json.dump(test_users, f, indent=2)

    # Vide les sessions existantes
    with open(SESSIONS_FILE, "w") as f:
        json.dump({}, f)

    handler = srv.BiningaHandler
    _httpd = http.server.HTTPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=_httpd.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.5)


def pytest_unconfigure(config):
    global _httpd, _users_backup
    if _httpd:
        _httpd.shutdown()
    # Restaure users.json original
    if _users_backup is not None:
        with open(USERS_FILE, "w") as f:
            f.write(_users_backup)
