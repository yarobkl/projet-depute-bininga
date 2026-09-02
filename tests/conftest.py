"""
conftest.py — Fixture pytest pour démarrer le serveur de test BININGA
"""
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time

# Ajoute le dossier parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = 18080
TEST_PASS = "test123"
_httpd = None
_test_data_dir = None


def pytest_configure(config):
    """Démarre le serveur une seule fois avant tous les tests."""
    global _httpd, _test_data_dir

    os.environ["BININGA_TEST"] = "1"
    os.environ["BININGA_PASS"] = TEST_PASS
    _test_data_dir = tempfile.mkdtemp(prefix="bininga_pytest_")
    os.environ["DATA_DIR"] = _test_data_dir

    import server as srv

    # Le contenu public est copié : aucune sauvegarde de test ne touche le dépôt.
    source_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json")
    srv.DATA_FILE = os.path.join(_test_data_dir, "data.json")
    shutil.copy2(source_data, srv.DATA_FILE)
    srv._DATA_CACHE = None
    srv._DATA_CACHE_AT = 0

    # Crée un users.json de test avec le mot de passe connu
    test_users = [{
        "username": "admin",
        "password_hash": srv._hash_new(TEST_PASS),
        "role": "admin",
        "nom": "Test Admin"
    }]
    with open(srv.USERS_FILE, "w") as f:
        json.dump(test_users, f, indent=2)

    # Vide les sessions existantes
    with open(srv.SESSIONS_FILE, "w") as f:
        json.dump({}, f)

    handler = srv.BiningaHandler
    _httpd = http.server.HTTPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=_httpd.serve_forever)
    thread.daemon = True
    thread.start()
    time.sleep(0.5)


def pytest_unconfigure(config):
    global _httpd, _test_data_dir
    if _httpd:
        _httpd.shutdown()
    if _test_data_dir:
        shutil.rmtree(_test_data_dir, ignore_errors=True)
