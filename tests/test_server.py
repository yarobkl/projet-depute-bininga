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


def post(path, data, token=None, csrf=None):
    url = f"http://127.0.0.1:{PORT}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Admin-Token", token)
    if csrf:
        req.add_header("X-CSRF-Token", csrf)
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
    # Utilise les credentials par défaut du serveur
    user = os.environ.get("BININGA_USER", "admin")
    pwd  = os.environ.get("BININGA_PASS", "bininga2025")
    status, body = post("/api/login", {"username": user, "password": pwd})
    assert status == 200, f"Login correct doit retourner 200, reçu {status}"
    assert body.get("ok") == True, "Login correct doit retourner ok=True"
    assert "token" in body, "Login correct doit retourner un token"
    assert "role" in body, "Login doit retourner le rôle"
    assert "nom" in body, "Login doit retourner le nom"
    assert body["role"] == "admin", "Le compte admin doit avoir le rôle admin"
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


def _get_admin_token():
    """Retourne (token, csrf_token) pour le compte admin."""
    user = os.environ.get("BININGA_USER", "admin")
    pwd  = os.environ.get("BININGA_PASS", "bininga2025")
    _, body = post("/api/login", {"username": user, "password": pwd})
    return body.get("token", ""), body.get("csrf_token", "")


def test_logs_avec_token():
    token, _ = _get_admin_token()
    url = f"http://127.0.0.1:{PORT}/api/logs"
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Token", token)
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read().decode("utf-8"))
    assert data.get("ok") == True, "/api/logs doit retourner ok=True"
    assert "logs" in data, "/api/logs doit retourner une clé 'logs'"
    assert isinstance(data["logs"], list), "logs doit être une liste"
    actions = [e["action"] for e in data["logs"]]
    assert "LOGIN_OK" in actions, "Le login réussi doit apparaître dans les logs"
    print("✅ test_logs_avec_token")


def test_users_list():
    token, _ = _get_admin_token()
    url = f"http://127.0.0.1:{PORT}/api/users"
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Token", token)
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read().decode("utf-8"))
    assert data.get("ok") == True, "/api/users doit retourner ok=True"
    assert "users" in data, "/api/users doit retourner une clé 'users'"
    usernames = [u["username"] for u in data["users"]]
    admin_user = os.environ.get("BININGA_USER", "admin")
    assert admin_user in usernames, "Le compte admin doit être dans la liste"
    # Vérifier qu'aucun mot de passe n'est exposé
    for u in data["users"]:
        assert "password_hash" not in u, "Les hashs de mots de passe ne doivent pas être exposés"
    print("✅ test_users_list")


def test_users_sans_token():
    status, _ = get("/api/users")
    assert status == 401, f"/api/users sans token doit retourner 401, reçu {status}"
    print("✅ test_users_sans_token")


def test_users_upsert_et_delete():
    token, csrf = _get_admin_token()
    # Créer un utilisateur test
    status, body = post("/api/users/upsert", {
        "username": "test_user_tmp",
        "nom":      "Utilisateur Test",
        "password": "test1234",
        "role":     "lecteur"
    }, token=token, csrf=csrf)
    assert status == 200 and body.get("ok"), "Création utilisateur doit réussir"
    # Vérifier qu'il apparaît dans la liste
    url = f"http://127.0.0.1:{PORT}/api/users"
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Token", token)
    with urllib.request.urlopen(req, timeout=5) as r:
        users_data = json.loads(r.read().decode("utf-8"))
    usernames = [u["username"] for u in users_data["users"]]
    assert "test_user_tmp" in usernames, "L'utilisateur créé doit apparaître dans la liste"
    # Se connecter avec ce compte
    status2, body2 = post("/api/login", {"username": "test_user_tmp", "password": "test1234"})
    assert status2 == 200 and body2.get("ok"), "Connexion avec le nouveau compte doit réussir"
    assert body2["role"] == "lecteur", "Le rôle doit être lecteur"
    # Supprimer l'utilisateur
    status3, body3 = post("/api/users/delete", {"username": "test_user_tmp"}, token=token, csrf=csrf)
    assert status3 == 200 and body3.get("ok"), "Suppression utilisateur doit réussir"
    print("✅ test_users_upsert_et_delete")


def test_data_json_structure():
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "hero" in data and "firstName" in data["hero"], "hero.firstName manquant"
    actus = data.get("actus", {})
    assert "vedettes" in actus, f"actus.vedettes manquant (clés présentes : {list(actus.keys())})"
    assert "slides" in actus, "actus.slides manquant"
    assert "cards" in actus, "actus.cards manquant"
    assert "gallery" in data and "slides" in data["gallery"], "gallery.slides manquant"
    print("✅ test_data_json_structure")


def test_actus_rwanda_article():
    """L'article Rwanda (visite ambassadeur 12/12/2025) doit être présent."""
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    vedettes = data.get("actus", {}).get("vedettes", [])
    rwanda_found = any(
        "rwanda" in (v.get("title", "") + v.get("text1", "") + v.get("badge", "")).lower()
        or "ambassadeur" in (v.get("title", "") + v.get("text1", "")).lower()
        for v in vedettes
    )
    assert rwanda_found, "L'article sur la visite de l'Ambassadeur Rwanda doit être dans actus.vedettes"
    print("✅ test_actus_rwanda_article")


# ── Tests Veille IA ────────────────────────────────────────────

def test_news_sans_token():
    status, _ = get("/api/news")
    assert status == 401, f"/api/news sans token doit retourner 401, reçu {status}"
    print("✅ test_news_sans_token")


def test_news_avec_token():
    token, csrf = _get_admin_token()
    url = f"http://127.0.0.1:{PORT}/api/news"
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Token", token)
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read().decode("utf-8"))
    assert data.get("ok") == True, "/api/news doit retourner ok=True"
    assert "items" in data, "/api/news doit retourner 'items'"
    assert "last_run" in data, "/api/news doit retourner 'last_run'"
    assert "monitor_running" in data, "/api/news doit retourner 'monitor_running'"
    assert isinstance(data["items"], list), "items doit être une liste"
    print("✅ test_news_avec_token")


def test_news_run_sans_token():
    status, body = post("/api/news/run", {})
    assert status == 401, f"/api/news/run sans token doit retourner 401, reçu {status}"
    print("✅ test_news_run_sans_token")


def test_news_run_cycle_complet():
    """Déclencher un cycle complet sans requête personnalisée."""
    token, csrf = _get_admin_token()
    # Supprimer l'éventuel trigger existant
    import os
    trigger = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "monitor.trigger")
    if os.path.exists(trigger):
        os.unlink(trigger)
    status, body = post("/api/news/run", {}, token=token)
    assert status == 200, f"/api/news/run doit retourner 200, reçu {status}"
    assert body.get("ok") == True, f"ok doit être True, reçu : {body}"
    assert "lancé" in body.get("message", "").lower() or "cycle" in body.get("message", "").lower(), \
        f"Message inattendu : {body.get('message')}"
    # Vérifier que le fichier trigger a été créé
    assert os.path.exists(trigger), "monitor.trigger doit être créé"
    # Contenu vide = cycle complet
    content = open(trigger).read().strip()
    assert content == "", f"Cycle complet : trigger doit être vide, reçu '{content}'"
    os.unlink(trigger)
    print("✅ test_news_run_cycle_complet")


def test_news_run_requete_personnalisee():
    """Déclencher une recherche avec un sujet spécifique."""
    token, csrf = _get_admin_token()
    import os
    trigger = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "monitor.trigger")
    if os.path.exists(trigger):
        os.unlink(trigger)
    query = "nouvelles lois justice Afrique 2026"
    status, body = post("/api/news/run", {"query": query}, token=token)
    assert status == 200 and body.get("ok"), f"Recherche personnalisée doit réussir : {body}"
    assert query in body.get("message", ""), f"La requête doit apparaître dans le message : {body.get('message')}"
    assert os.path.exists(trigger), "monitor.trigger doit être créé"
    content = open(trigger).read().strip()
    assert content == query, f"Trigger doit contenir la requête, reçu '{content}'"
    os.unlink(trigger)
    print("✅ test_news_run_requete_personnalisee")


def test_news_mark_read():
    """Marquer un article comme lu."""
    token, csrf = _get_admin_token()
    # Injecter un article de test dans news_monitor.json
    import os, json as _json
    news_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news_monitor.json")
    test_item = {"id": "test_read_001", "title": "Test", "url": "https://example.com", "source": "test",
                 "published": "", "found_at": "", "summary": "", "read": False, "category": "bininga"}
    data = {"items": [test_item], "last_run": None, "stats": {}}
    with open(news_file, "w") as f:
        _json.dump(data, f)
    # Marquer comme lu
    status, body = post("/api/news/mark-read", {"id": "test_read_001"}, token=token)
    assert status == 200 and body.get("ok"), f"mark-read doit réussir : {body}"
    # Vérifier
    saved = _json.load(open(news_file))
    item = next((a for a in saved["items"] if a["id"] == "test_read_001"), None)
    assert item and item["read"] == True, "L'article doit être marqué lu"
    print("✅ test_news_mark_read")


def test_news_mark_all_read():
    """Marquer tous les articles comme lus."""
    token, csrf = _get_admin_token()
    import os, json as _json
    news_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news_monitor.json")
    items = [
        {"id": f"test_all_{i}", "title": f"Art {i}", "url": "https://example.com",
         "source": "test", "published": "", "found_at": "", "summary": "", "read": False, "category": "bininga"}
        for i in range(3)
    ]
    with open(news_file, "w") as f:
        _json.dump({"items": items, "last_run": None, "stats": {}}, f)
    status, body = post("/api/news/mark-read", {"all": True}, token=token)
    assert status == 200 and body.get("ok"), f"mark-read all doit réussir : {body}"
    saved = _json.load(open(news_file))
    assert all(a["read"] for a in saved["items"]), "Tous les articles doivent être marqués lus"
    print("✅ test_news_mark_all_read")


def test_news_delete_item():
    """Supprimer un article de la veille."""
    token, csrf = _get_admin_token()
    import os, json as _json
    news_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news_monitor.json")
    items = [
        {"id": "del_001", "title": "A supprimer", "url": "https://example.com",
         "source": "test", "published": "", "found_at": "", "summary": "", "read": False, "category": "bininga"},
        {"id": "del_002", "title": "A garder", "url": "https://example.com",
         "source": "test", "published": "", "found_at": "", "summary": "", "read": False, "category": "bininga"},
    ]
    with open(news_file, "w") as f:
        _json.dump({"items": items, "last_run": None, "stats": {}}, f)
    status, body = post("/api/news/delete", {"id": "del_001"}, token=token)
    assert status == 200 and body.get("ok"), f"delete doit réussir : {body}"
    assert body.get("deleted") == 1, f"1 article doit être supprimé, reçu {body.get('deleted')}"
    saved = _json.load(open(news_file))
    ids = [a["id"] for a in saved["items"]]
    assert "del_001" not in ids, "del_001 doit être supprimé"
    assert "del_002" in ids, "del_002 doit rester"
    print("✅ test_news_delete_item")


def test_news_delete_interdit_editeur():
    """Un éditeur ne peut pas supprimer des articles de veille."""
    edit_token, admin_token, admin_csrf = _get_editeur_token()
    status, body = post("/api/news/delete", {"id": "xxx"}, token=edit_token)
    assert status in (403, 401), f"Un éditeur ne peut pas supprimer (attendu 403/401, reçu {status})"
    assert not body.get("ok")
    _cleanup_user("tmp_editeur", admin_token, admin_csrf)
    print("✅ test_news_delete_interdit_editeur")


def test_news_run_interdit_editeur():
    """Un éditeur ne peut pas déclencher le monitor."""
    edit_token, admin_token, admin_csrf = _get_editeur_token()
    status, body = post("/api/news/run", {}, token=edit_token)
    assert status in (401, 403), f"Un éditeur ne peut pas lancer le monitor (attendu 401/403, reçu {status})"
    assert not body.get("ok")
    _cleanup_user("tmp_editeur", admin_token, admin_csrf)
    print("✅ test_news_run_interdit_editeur")


# ── Tests sur les modifications de l'interface admin ──────────

def _get_editeur_token():
    """Crée un compte éditeur temporaire et retourne (edit_token, admin_token, admin_csrf)."""
    admin_token, admin_csrf = _get_admin_token()
    post("/api/users/upsert", {
        "username": "tmp_editeur",
        "nom":      "Editeur Temp",
        "password": "editeur1234",
        "role":     "editeur"
    }, token=admin_token, csrf=admin_csrf)
    _, body = post("/api/login", {"username": "tmp_editeur", "password": "editeur1234"})
    return body.get("token", ""), admin_token, admin_csrf


def _cleanup_user(username, admin_token, admin_csrf=None):
    if admin_csrf is None:
        _, admin_csrf = _get_admin_token()
    post("/api/users/delete", {"username": username}, token=admin_token, csrf=admin_csrf)


def test_upsert_modification_utilisateur():
    """Modifier le nom et le rôle d'un utilisateur existant."""
    admin_token, admin_csrf = _get_admin_token()
    post("/api/users/upsert", {
        "username": "tmp_mod", "nom": "Nom Original", "password": "pass1234", "role": "lecteur"
    }, token=admin_token, csrf=admin_csrf)
    status, body = post("/api/users/upsert", {
        "username": "tmp_mod", "nom": "Nom Modifié", "role": "editeur"
    }, token=admin_token, csrf=admin_csrf)
    assert status == 200 and body.get("ok"), "La modification doit réussir"
    url = f"http://127.0.0.1:{PORT}/api/users"
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Token", admin_token)
    with urllib.request.urlopen(req, timeout=5) as r:
        users = json.loads(r.read().decode("utf-8"))["users"]
    user = next((u for u in users if u["username"] == "tmp_mod"), None)
    assert user and user["nom"] == "Nom Modifié" and user["role"] == "editeur"
    _cleanup_user("tmp_mod", admin_token, admin_csrf)
    print("✅ test_upsert_modification_utilisateur")


def test_upsert_modification_mot_de_passe():
    """Changer le mot de passe d'un utilisateur existant."""
    admin_token, admin_csrf = _get_admin_token()
    post("/api/users/upsert", {
        "username": "tmp_pwd", "nom": "Test MDP", "password": "ancien1234", "role": "lecteur"
    }, token=admin_token, csrf=admin_csrf)
    status, body = post("/api/users/upsert", {
        "username": "tmp_pwd", "nom": "Test MDP", "password": "nouveau5678", "role": "lecteur"
    }, token=admin_token, csrf=admin_csrf)
    assert status == 200 and body.get("ok"), "Le changement de mot de passe doit réussir"
    s1, b1 = post("/api/login", {"username": "tmp_pwd", "password": "ancien1234"})
    assert s1 == 401 and not b1.get("ok"), "L'ancien mot de passe ne doit plus fonctionner"
    s2, b2 = post("/api/login", {"username": "tmp_pwd", "password": "nouveau5678"})
    assert s2 == 200 and b2.get("ok"), "Le nouveau mot de passe doit fonctionner"
    _cleanup_user("tmp_pwd", admin_token, admin_csrf)
    print("✅ test_upsert_modification_mot_de_passe")


def test_upsert_nouveau_sans_mot_de_passe():
    """Créer un utilisateur sans mot de passe doit échouer."""
    admin_token, admin_csrf = _get_admin_token()
    status, body = post("/api/users/upsert", {
        "username": "tmp_nopwd", "nom": "Sans Mot de Passe", "password": "", "role": "lecteur"
    }, token=admin_token, csrf=admin_csrf)
    assert status == 400, f"Création sans mot de passe doit retourner 400, reçu {status}"
    assert not body.get("ok")
    print("✅ test_upsert_nouveau_sans_mot_de_passe")


def test_upsert_role_invalide():
    """Créer un utilisateur avec un rôle invalide doit échouer."""
    admin_token, admin_csrf = _get_admin_token()
    status, body = post("/api/users/upsert", {
        "username": "tmp_badrole", "nom": "Mauvais Rôle", "password": "pass1234", "role": "superadmin"
    }, token=admin_token, csrf=admin_csrf)
    assert status == 400, f"Rôle invalide doit retourner 400, reçu {status}"
    assert not body.get("ok")
    print("✅ test_upsert_role_invalide")


def test_upsert_identifiant_vide():
    """Créer un utilisateur avec identifiant vide doit échouer."""
    admin_token, admin_csrf = _get_admin_token()
    status, body = post("/api/users/upsert", {
        "username": "", "nom": "Vide", "password": "pass1234", "role": "lecteur"
    }, token=admin_token, csrf=admin_csrf)
    assert status == 400, f"Identifiant vide doit retourner 400, reçu {status}"
    assert not body.get("ok")
    print("✅ test_upsert_identifiant_vide")


def test_delete_son_propre_compte():
    """Un admin ne peut pas supprimer son propre compte."""
    admin_token, admin_csrf = _get_admin_token()
    admin_user = os.environ.get("BININGA_USER", "admin")
    status, body = post("/api/users/delete", {"username": admin_user}, token=admin_token, csrf=admin_csrf)
    assert status == 400, f"Suppression du compte propre doit retourner 400, reçu {status}"
    assert not body.get("ok")
    assert "propre" in body.get("message", "").lower() or "impossible" in body.get("message", "").lower()
    print("✅ test_delete_son_propre_compte")


def test_upsert_interdit_pour_editeur():
    """Un éditeur ne peut pas créer ou modifier des utilisateurs."""
    edit_token, admin_token, admin_csrf = _get_editeur_token()
    edit_csrf = ""   # l'éditeur n'a pas de csrf valide pour les endpoints admin
    status, body = post("/api/users/upsert", {
        "username": "tmp_inedit", "nom": "Test", "password": "pass1234", "role": "lecteur"
    }, token=edit_token, csrf=edit_csrf)
    assert status in (403, 401), f"Un éditeur ne peut pas créer d'utilisateur (attendu 403/401, reçu {status})"
    assert not body.get("ok")
    _cleanup_user("tmp_editeur", admin_token, admin_csrf)
    print("✅ test_upsert_interdit_pour_editeur")


def test_delete_interdit_pour_editeur():
    """Un éditeur ne peut pas supprimer des utilisateurs."""
    edit_token, admin_token, admin_csrf = _get_editeur_token()
    post("/api/users/upsert", {
        "username": "tmp_cible", "nom": "Cible", "password": "pass1234", "role": "lecteur"
    }, token=admin_token, csrf=admin_csrf)
    edit_csrf = ""
    status, body = post("/api/users/delete", {"username": "tmp_cible"}, token=edit_token, csrf=edit_csrf)
    assert status in (403, 401), f"Un éditeur ne peut pas supprimer (attendu 403/401, reçu {status})"
    assert not body.get("ok")
    _cleanup_user("tmp_cible", admin_token, admin_csrf)
    _cleanup_user("tmp_editeur", admin_token, admin_csrf)
    print("✅ test_delete_interdit_pour_editeur")


def test_logs_contiennent_user_upsert():
    """L'action USER_UPSERT doit apparaître dans les logs après une création."""
    admin_token, admin_csrf = _get_admin_token()
    post("/api/users/upsert", {
        "username": "tmp_audit_upsert", "nom": "Audit Test", "password": "pass1234", "role": "lecteur"
    }, token=admin_token, csrf=admin_csrf)
    url = f"http://127.0.0.1:{PORT}/api/logs"
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Token", admin_token)
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read().decode("utf-8"))
    actions = [e["action"] for e in data["logs"]]
    assert "USER_UPSERT" in actions, "USER_UPSERT doit apparaître dans les journaux d'audit"
    _cleanup_user("tmp_audit_upsert", admin_token, admin_csrf)
    print("✅ test_logs_contiennent_user_upsert")


def test_logs_contiennent_user_delete():
    """L'action USER_DELETE doit apparaître dans les logs après une suppression."""
    admin_token, admin_csrf = _get_admin_token()
    post("/api/users/upsert", {
        "username": "tmp_audit_del", "nom": "Audit Delete", "password": "pass1234", "role": "lecteur"
    }, token=admin_token, csrf=admin_csrf)
    post("/api/users/delete", {"username": "tmp_audit_del"}, token=admin_token, csrf=admin_csrf)
    url = f"http://127.0.0.1:{PORT}/api/logs"
    req = urllib.request.Request(url)
    req.add_header("X-Admin-Token", admin_token)
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read().decode("utf-8"))
    actions = [e["action"] for e in data["logs"]]
    assert "USER_DELETE" in actions, "USER_DELETE doit apparaître dans les journaux d'audit"
    print("✅ test_logs_contiennent_user_delete")


# ── Tests monitor.py ──────────────────────────────────────────

def test_monitor_legal_queries():
    """monitor.py doit contenir les requêtes de veille juridique mondiale."""
    import os
    monitor_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "monitor.py")
    source = open(monitor_path, encoding="utf-8").read()
    assert "LEGAL_QUERIES" in source, "LEGAL_QUERIES doit être défini dans monitor.py"
    assert "LEGAL_RSS" in source, "LEGAL_RSS doit être défini dans monitor.py"
    assert "loi" in source.lower() or "justice" in source.lower(), "Des requêtes juridiques doivent être présentes"
    assert "OHADA" in source or "ONU" in source or "droits humains" in source.lower(), \
        "Des requêtes spécifiques droits/justice doivent être présentes"
    print("✅ test_monitor_legal_queries")


def test_monitor_trigger_file():
    """monitor.py doit gérer le fichier trigger pour déclenchement manuel."""
    import os
    monitor_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "monitor.py")
    source = open(monitor_path, encoding="utf-8").read()
    assert "TRIGGER_FILE" in source, "TRIGGER_FILE doit être défini dans monitor.py"
    assert "monitor.trigger" in source, "Le nom 'monitor.trigger' doit être dans monitor.py"
    assert "custom_query" in source, "Le paramètre custom_query doit être géré"
    print("✅ test_monitor_trigger_file")


def test_monitor_category_field():
    """run_cycle doit affecter une catégorie à chaque article."""
    import os
    monitor_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "monitor.py")
    source = open(monitor_path, encoding="utf-8").read()
    assert '"category"' in source or "'category'" in source, "Le champ 'category' doit être assigné aux articles"
    assert "bininga" in source, "La catégorie 'bininga' doit exister"
    assert "loi_justice" in source, "La catégorie 'loi_justice' doit exister"
    assert "recherche" in source, "La catégorie 'recherche' doit exister"
    print("✅ test_monitor_category_field")


def test_admin_html_upload_actus():
    """admin.html doit avoir les boutons upload dans les actus slides et vedettes."""
    import os
    admin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "admin.html")
    source = open(admin_path, encoding="utf-8").read()
    assert "uploadForActuSlide" in source, "uploadForActuSlide doit être défini dans admin.html"
    assert "uploadForActuVedette" in source, "uploadForActuVedette doit être défini dans admin.html"
    assert "actu-slide-img-" in source, "Les inputs image slide doivent avoir un id dynamique"
    assert "actu-vedette-img-" in source, "Les inputs image vedette doivent avoir un id dynamique"
    print("✅ test_admin_html_upload_actus")


def test_admin_html_veille_run():
    """admin.html doit avoir le panneau de commande de la veille IA."""
    import os
    admin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "admin.html")
    source = open(admin_path, encoding="utf-8").read()
    assert "runVeille" in source, "runVeille() doit être défini dans admin.html"
    assert "setNewsFilter" in source, "setNewsFilter() doit être défini dans admin.html"
    assert "veille-custom-query" in source, "Le champ de recherche personnalisée doit exister"
    assert "btn-run-veille" in source, "Le bouton 'Lancer maintenant' doit exister"
    assert "filter-bininga" in source, "Le filtre Bininga doit exister"
    assert "filter-loi_justice" in source, "Le filtre Lois & Justice doit exister"
    assert "filter-recherche" in source, "Le filtre Recherche doit exister"
    assert "CAT_LABELS" in source, "CAT_LABELS doit être défini pour les badges de catégorie"
    print("✅ test_admin_html_veille_run")


# ── Lancement ─────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    passed = []
    failed = []

    def run(fn):
        try:
            fn()
            passed.append(fn.__name__)
        except Exception as e:
            failed.append((fn.__name__, str(e)))
            traceback.print_exc()

    print("\n🧪 Lancement des tests BININGA...\n")

    # Tests sans serveur
    for fn in [
        test_data_json_structure,
        test_actus_rwanda_article,
        test_monitor_legal_queries,
        test_monitor_trigger_file,
        test_monitor_category_field,
        test_admin_html_upload_actus,
        test_admin_html_veille_run,
    ]:
        run(fn)

    # Tests avec serveur
    srv = start_test_server()
    try:
        for fn in [
            test_index_accessible,
            test_api_load,
            test_admin_accessible,
            test_404_fichier_inexistant,
            test_login_mauvais_mot_de_passe,
            test_login_correct,
            test_save_sans_token,
            test_logs_sans_token,
            test_logs_avec_token,
            test_users_sans_token,
            test_users_list,
            test_users_upsert_et_delete,
            test_upsert_modification_utilisateur,
            test_upsert_modification_mot_de_passe,
            test_upsert_nouveau_sans_mot_de_passe,
            test_upsert_role_invalide,
            test_upsert_identifiant_vide,
            test_delete_son_propre_compte,
            test_upsert_interdit_pour_editeur,
            test_delete_interdit_pour_editeur,
            test_logs_contiennent_user_upsert,
            test_logs_contiennent_user_delete,
            # Veille IA
            test_news_sans_token,
            test_news_avec_token,
            test_news_run_sans_token,
            test_news_run_cycle_complet,
            test_news_run_requete_personnalisee,
            test_news_mark_read,
            test_news_mark_all_read,
            test_news_delete_item,
            test_news_delete_interdit_editeur,
            test_news_run_interdit_editeur,
        ]:
            run(fn)
    finally:
        srv.shutdown()

    print(f"\n╔══════════════════════════════════════════════╗")
    print(f"  ✅ Réussis  : {len(passed)}")
    if failed:
        print(f"  ❌ Échoués  : {len(failed)}")
        for name, err in failed:
            print(f"     • {name}: {err}")
    print(f"╚══════════════════════════════════════════════╝\n")
    if failed:
        sys.exit(1)
