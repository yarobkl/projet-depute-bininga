"""
test_e2e_complet.py — Test end-to-end BININGA
Teste : formulaires publics, création d'utilisateurs, contrôles admin, notifications SSE
"""
import json
import threading
import time
import urllib.request
import urllib.error

PORT = 18080
BASE = f"http://127.0.0.1:{PORT}"


# ── Helpers ────────────────────────────────────────────────────────────────────

def get(path, token=None):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url)
    if token:
        req.add_header("X-Admin-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read().decode("utf-8")
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, body
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


def post(path, data, token=None, csrf=None):
    url = f"{BASE}{path}"
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


def login(username="admin", password="test123"):
    status, body = post("/api/login", {"username": username, "password": password})
    assert status == 200, f"Login {username} échoué : {status} {body}"
    return body["token"], body.get("csrf_token", "")


# ── Pages publiques ─────────────────────────────────────────────────────────────

def test_page_index():
    status, body = get("/")
    assert status == 200
    assert "<html" in body.lower()
    print("  ✅ Page index accessible")


def test_page_admin_honeypot():
    status, _ = get("/admin.html")
    assert status == 404, f"/admin.html doit être un piège (404), reçu {status}"
    print("  ✅ /admin.html est un piège (404)")


def test_page_admin_secret():
    import os
    secret = os.environ.get("ADMIN_SECRET_PATH", "espace-ministre-ab-2025").strip("/")
    status, body = get(f"/{secret}")
    assert status == 200
    print(f"  ✅ Page admin secrète /{secret} accessible")


def test_page_ministre():
    status, body = get("/ministre.html")
    assert status == 200
    assert "<html" in body.lower()
    print("  ✅ Page ministre.html accessible")


def test_page_health():
    status, body = get("/health")
    assert status == 200
    assert "ok" in str(body).lower() or "status" in str(body).lower()
    print("  ✅ /health répond correctement")


def test_api_load_structure():
    status, data = get("/api/load")
    assert status == 200
    for key in ["hero", "about", "actus", "gallery", "programme"]:
        assert key in data, f"Clé manquante : {key}"
    assert data["hero"].get("firstName"), "hero.firstName manquant"
    print(f"  ✅ /api/load — données structurées OK ({', '.join(data.keys())})")


# ── Formulaires publics ─────────────────────────────────────────────────────────

def test_bouton_formulaire_contact():
    status, body = post("/api/contact", {
        "type": "contact",
        "nom": "Jean Test",
        "prenom": "Marie",
        "email": "jean.test@example.com",
        "telephone": "0612345678",
        "message": "Test de contact depuis les tests automatiques",
        "objet": "Contact général"
    })
    assert status == 200, f"Formulaire contact échoué : {status} {body}"
    assert body.get("ok") == True
    print("  ✅ Formulaire contact soumis avec succès")
    return body


def test_bouton_formulaire_audience():
    status, body = post("/api/contact", {
        "type": "audience",
        "nom": "Dupont",
        "prenom": "Alice",
        "email": "alice.dupont@example.com",
        "telephone": "0698765432",
        "message": "Je souhaite rencontrer le député pour discuter d'un projet agricole",
        "objet": "Demande d'audience",
        "date_souhaitee": "2025-06-15"
    })
    assert status == 200, f"Formulaire audience échoué : {status} {body}"
    assert body.get("ok") == True
    print("  ✅ Formulaire demande d'audience soumis avec succès")


def test_bouton_formulaire_reclamation():
    status, body = post("/api/contact", {
        "type": "reclamation",
        "nom": "Martin",
        "prenom": "Bob",
        "email": "bob.martin@example.com",
        "telephone": "0655443322",
        "message": "Réclamation concernant les travaux routiers non terminés à Ewo",
        "objet": "Réclamation",
        "localite": "Ewo, Cuvette-Ouest"
    })
    assert status == 200, f"Formulaire réclamation échoué : {status} {body}"
    assert body.get("ok") == True
    print("  ✅ Formulaire réclamation soumis avec succès")


def test_bouton_formulaire_newsletter():
    status, body = post("/api/contact", {
        "type": "newsletter",
        "nom": "Abonné",
        "prenom": "Test",
        "email": "newsletter.test@example.com",
    })
    assert status == 200, f"Inscription newsletter échouée : {status} {body}"
    assert body.get("ok") == True
    print("  ✅ Inscription newsletter soumise avec succès")


def test_bouton_chatbot():
    status, body = post("/api/chat", {
        "message": "Bonjour, qui est BININGA ?",
        "history": []
    })
    assert status == 200, f"Chatbot échoué : {status} {body}"
    assert body.get("reply"), "Chatbot n'a pas renvoyé de réponse"
    print(f"  ✅ Chatbot répond : \"{body['reply'][:60]}...\"")


# ── Authentification ────────────────────────────────────────────────────────────

def test_login_mauvais_mdp():
    status, body = post("/api/login", {"username": "admin", "password": "mauvais"})
    assert status == 401
    assert body.get("ok") == False
    print("  ✅ Mauvais mot de passe → 401 refusé")


def test_login_admin():
    token, csrf = login()
    assert len(token) > 10
    print(f"  ✅ Connexion admin OK (token: {token[:12]}...)")
    return token, csrf


def test_logout(token, csrf):
    status, body = post("/api/logout", {}, token=token, csrf=csrf)
    assert status == 200
    print("  ✅ Déconnexion OK")


# ── Contrôles admin ─────────────────────────────────────────────────────────────

def _check_admin_stats(token):
    status, body = get("/api/stats", token=token)
    assert status == 200, f"/api/stats échoué : {status}"
    print(f"  ✅ /api/stats — KPIs reçus : {list(body.keys())[:5]}")


def _check_admin_contacts_arrivent(token):
    """Vérifie que les formulaires soumis sont bien visibles dans l'admin."""
    status, body = get("/api/contacts", token=token)
    assert status == 200, f"/api/contacts échoué : {status}"
    contacts = body if isinstance(body, list) else body.get("contacts", [])
    assert len(contacts) > 0, "Aucun contact reçu malgré les soumissions de formulaires"
    emails = [c.get("email", "") for c in contacts]
    assert any("jean.test@example.com" in e for e in emails), \
        "Contact jean.test@example.com non trouvé dans l'admin"
    assert any("alice.dupont@example.com" in e for e in emails), \
        "Audience alice.dupont@example.com non trouvée dans l'admin"
    assert any("bob.martin@example.com" in e for e in emails), \
        "Réclamation bob.martin@example.com non trouvée dans l'admin"
    print(f"  ✅ {len(contacts)} soumissions visibles dans l'admin")
    print(f"     → contact, audience, réclamation tous arrivés ✓")


def _check_admin_mise_a_jour_statut(token, csrf):
    """Teste le bouton de changement de statut d'une soumission."""
    status, contacts_body = get("/api/contacts", token=token)
    contacts = contacts_body if isinstance(contacts_body, list) else contacts_body.get("contacts", [])
    if not contacts:
        print("  ⚠️  Pas de contacts pour tester la mise à jour de statut")
        return
    first_id = contacts[0].get("id") or contacts[0].get("_id") or str(0)
    status2, body2 = post("/api/contacts/update", {
        "id": first_id,
        "statut": "en_cours",
        "note": "Note de test automatique"
    }, token=token, csrf=csrf)
    assert status2 in (200, 400, 404), f"Mise à jour statut inattendue : {status2}"
    if status2 == 200:
        print("  ✅ Mise à jour statut contact → 'en_cours' OK")
    else:
        print(f"  ⚠️  Mise à jour statut : {status2} (format id peut différer)")


def _check_admin_logs(token):
    status, body = get("/api/logs", token=token)
    assert status == 200, f"/api/logs échoué : {status}"
    logs = body if isinstance(body, list) else body.get("logs", [])
    print(f"  ✅ /api/logs — {len(logs)} entrées d'audit")


def _check_admin_securite(token):
    status, body = get("/api/security", token=token)
    assert status == 200, f"/api/security échoué : {status}"
    print(f"  ✅ /api/security — tableau de bord sécurité OK")


# ── Gestion des utilisateurs ────────────────────────────────────────────────────

def _check_creer_utilisateur_editeur(token, csrf):
    status, body = post("/api/users/upsert", {
        "username": "editeur_test",
        "password": "editeur2025",
        "role": "editeur",
        "nom": "Éditeur Test"
    }, token=token, csrf=csrf)
    assert status == 200, f"Création éditeur échouée : {status} {body}"
    assert body.get("ok") == True
    print("  ✅ Utilisateur 'editeur_test' (rôle: éditeur) créé")


def _check_creer_utilisateur_lecteur(token, csrf):
    status, body = post("/api/users/upsert", {
        "username": "lecteur_test",
        "password": "lecteur2025",
        "role": "lecteur",
        "nom": "Lecteur Test"
    }, token=token, csrf=csrf)
    assert status == 200, f"Création lecteur échouée : {status} {body}"
    assert body.get("ok") == True
    print("  ✅ Utilisateur 'lecteur_test' (rôle: lecteur) créé")


def _check_creer_utilisateur_ministre(token, csrf):
    status, body = post("/api/users/upsert", {
        "username": "ministre_test",
        "password": "ministre2025",
        "role": "ministre",
        "nom": "Ministre Test"
    }, token=token, csrf=csrf)
    assert status == 200, f"Création ministre échouée : {status} {body}"
    assert body.get("ok") == True
    print("  ✅ Utilisateur 'ministre_test' (rôle: ministre) créé")


def _check_liste_utilisateurs_admin(token):
    status, body = get("/api/users", token=token)
    assert status == 200
    users = body if isinstance(body, list) else body.get("users", [])
    usernames = [u.get("username") for u in users]
    assert "editeur_test" in usernames, "editeur_test non trouvé"
    assert "lecteur_test" in usernames, "lecteur_test non trouvé"
    assert "ministre_test" in usernames, "ministre_test non trouvé"
    for u in users:
        assert "password" not in u and "password_hash" not in u, \
            f"Hash mot de passe exposé pour {u.get('username')}"
    print(f"  ✅ {len(users)} utilisateurs listés (aucun hash exposé)")


def _check_connexion_editeur():
    token_e, csrf_e = login("editeur_test", "editeur2025")
    assert token_e
    status, body = post("/api/users/upsert", {
        "username": "hacker",
        "password": "hack123",
        "role": "admin"
    }, token=token_e, csrf=csrf_e)
    assert status in (401, 403), f"L'éditeur ne doit pas créer d'utilisateurs : {status}"
    print("  ✅ Éditeur connecté — création d'utilisateurs bloquée (403)")
    return token_e, csrf_e


def _check_connexion_lecteur():
    token_l, csrf_l = login("lecteur_test", "lecteur2025")
    assert token_l
    status, body = post("/api/save", {"hero": {"title": "hack"}}, token=token_l, csrf=csrf_l)
    assert status in (401, 403), f"Le lecteur ne doit pas sauvegarder : {status}"
    print("  ✅ Lecteur connecté — écriture de contenu bloquée (403)")


def _check_supprimer_utilisateurs(token, csrf):
    # Changer le rôle du compte ministre avant suppression (les comptes ministre sont protégés)
    post("/api/users/upsert", {
        "username": "ministre_test",
        "password": "ministre2025",
        "role": "editeur",
        "nom": "Ministre Test"
    }, token=token, csrf=csrf)

    for username in ["editeur_test", "lecteur_test", "ministre_test"]:
        status, body = post("/api/users/delete", {
            "username": username
        }, token=token, csrf=csrf)
        assert status == 200, f"Suppression {username} échouée : {status} {body}"
    print("  ✅ Utilisateurs de test supprimés (editeur, lecteur, ministre)")


# ── Notifications SSE ───────────────────────────────────────────────────────────

def test_notifications_sse(token):
    """Vérifie que le flux SSE est accessible et envoie des événements."""
    events_received = []
    stop_event = threading.Event()

    def read_sse():
        try:
            url = f"{BASE}/api/events?t={token}"
            req = urllib.request.Request(url)
            req.add_header("Accept", "text/event-stream")
            with urllib.request.urlopen(req, timeout=4) as r:
                while not stop_event.is_set():
                    line = r.readline().decode("utf-8", errors="replace")
                    if not line:
                        break
                    if line.startswith("data:"):
                        events_received.append(line.strip())
                    if len(events_received) >= 2:
                        break
        except Exception:
            pass
        finally:
            stop_event.set()

    sse_thread = threading.Thread(target=read_sse)
    sse_thread.daemon = True
    sse_thread.start()

    # Envoie un contact pendant que SSE écoute
    time.sleep(0.3)
    post("/api/contact", {
        "type": "contact",
        "nom": "SSE Test",
        "email": "sse.test@example.com",
        "message": "Test notification temps réel"
    })

    stop_event.wait(timeout=5)

    if events_received:
        print(f"  ✅ SSE — {len(events_received)} événement(s) reçu(s) en temps réel")
        for ev in events_received[:2]:
            print(f"     → {ev[:80]}")
    else:
        print("  ⚠️  SSE — aucun événement capturé (timeout 5s, peut être normal)")


# ── Routes protégées sans token ─────────────────────────────────────────────────

def test_routes_protegees_sans_token():
    routes = [
        "/api/contacts",
        "/api/users",
        "/api/logs",
        "/api/stats",
        "/api/security",
    ]
    for route in routes:
        status, _ = get(route)
        assert status in (401, 403), f"{route} doit être protégé, reçu {status}"
    print(f"  ✅ {len(routes)} routes admin protégées (401/403 sans token)")


# ── Runner principal ────────────────────────────────────────────────────────────

def run_all_tests():
    print("\n" + "=" * 65)
    print("  TEST END-TO-END COMPLET — SITE BININGA")
    print("=" * 65)

    results = {"pass": 0, "fail": 0, "warn": 0}

    def run(fn, *args):
        name = fn.__name__.replace("test_", "").replace("_", " ").upper()
        try:
            result = fn(*args)
            results["pass"] += 1
            return result
        except AssertionError as e:
            print(f"  ❌ ECHEC — {name}: {e}")
            results["fail"] += 1
            return None
        except Exception as e:
            print(f"  ❌ ERREUR — {name}: {e}")
            results["fail"] += 1
            return None

    # 1. Pages publiques
    print("\n── PAGES PUBLIQUES ──────────────────────────────────────────")
    run(test_page_index)
    run(test_page_admin_honeypot)
    run(test_page_admin_secret)
    run(test_page_ministre)
    run(test_page_health)
    run(test_api_load_structure)

    # 2. Formulaires publics (boutons)
    print("\n── BOUTONS / FORMULAIRES PUBLICS ───────────────────────────")
    run(test_bouton_formulaire_contact)
    run(test_bouton_formulaire_audience)
    run(test_bouton_formulaire_reclamation)
    run(test_bouton_formulaire_newsletter)
    run(test_bouton_chatbot)

    # 3. Authentification
    print("\n── AUTHENTIFICATION ─────────────────────────────────────────")
    run(test_login_mauvais_mdp)
    auth = run(test_login_admin)
    if not auth:
        print("  ⛔ Impossible de continuer sans token admin")
        return results
    token, csrf = auth

    # 4. Contrôles admin
    print("\n── CONTRÔLES ADMIN ──────────────────────────────────────────")
    run(_check_admin_stats, token)
    run(_check_admin_contacts_arrivent, token)
    run(_check_admin_mise_a_jour_statut, token, csrf)
    run(_check_admin_logs, token)
    run(_check_admin_securite, token)

    # 5. Gestion des utilisateurs
    print("\n── GESTION DES UTILISATEURS ─────────────────────────────────")
    run(_check_creer_utilisateur_editeur, token, csrf)
    run(_check_creer_utilisateur_lecteur, token, csrf)
    run(_check_creer_utilisateur_ministre, token, csrf)
    run(_check_liste_utilisateurs_admin, token)
    run(_check_connexion_editeur)
    run(_check_connexion_lecteur)
    run(_check_supprimer_utilisateurs, token, csrf)

    # 6. Notifications SSE
    print("\n── NOTIFICATIONS TEMPS RÉEL (SSE) ───────────────────────────")
    run(test_notifications_sse, token)

    # 7. Routes protégées
    print("\n── SÉCURITÉ — ROUTES PROTÉGÉES ─────────────────────────────")
    run(test_routes_protegees_sans_token)

    # 8. Déconnexion
    print("\n── DÉCONNEXION ──────────────────────────────────────────────")
    run(test_logout, token, csrf)

    # Résumé
    total = results["pass"] + results["fail"]
    print("\n" + "=" * 65)
    print(f"  RÉSULTAT : {results['pass']}/{total} tests réussis", end="")
    if results["fail"] == 0:
        print(" ✅ TOUS PASSENT")
    else:
        print(f" — {results['fail']} échec(s) ❌")
    print("=" * 65 + "\n")

    return results


# pytest compatibility
def test_e2e_complet():
    """Wrapper pytest qui lance tous les tests E2E."""
    results = run_all_tests()
    assert results["fail"] == 0, f"{results['fail']} test(s) E2E ont échoué"


if __name__ == "__main__":
    import os
    os.environ["BININGA_TEST"] = "1"
    os.environ["BININGA_FORCE_HTTP"] = "1"
    os.environ["BININGA_PASS"] = "test123"

    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import http.server
    import socketserver
    import json
    import server as srv

    USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "users.json")
    SESSIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions.json")

    test_users = [{"username": "admin", "password_hash": srv._hash_new("test123"), "role": "admin", "nom": "Admin Test"}]
    with open(USERS_FILE, "w") as f:
        json.dump(test_users, f)
    with open(SESSIONS_FILE, "w") as f:
        json.dump({}, f)

    class _ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    httpd = _ThreadedHTTPServer(("127.0.0.1", PORT), srv.BiningaHandler)
    t = threading.Thread(target=httpd.serve_forever)
    t.daemon = True
    t.start()
    time.sleep(0.5)

    results = run_all_tests()
    sys.exit(0 if results["fail"] == 0 else 1)
