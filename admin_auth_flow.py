"""Secure account lifecycle for the BININGA administration."""
from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import secrets
import smtplib
import time
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import owner_policy

RESET_STORE_KEY = "auth_password_resets_v1"
RESET_TTL_SECONDS = 30 * 60
RESET_COOLDOWN_SECONDS = 60
ALLOWED_ROLES = {"admin", "editeur", "lecteur", "ministre"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PUBLIC_AUTH_POSTS = {"/api/auth/forgot-password", "/api/auth/reset-password"}
PASSWORD_CHANGE_PATHS = {"/api/auth/change-password", "/api/auth/session", "/api/logout"}


def _path(handler) -> str:
    return str(getattr(handler, "path", "")).split("?", 1)[0]


def _body(handler) -> dict:
    raw = getattr(handler, "rfile", None)
    if raw is None:
        return {}
    try:
        data = raw.getvalue() if hasattr(raw, "getvalue") else raw.read()
        parsed = json.loads(data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _rewrite_body(handler, payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.rfile = io.BytesIO(encoded)
    if handler.headers.get("Content-Length") is not None:
        handler.headers.replace_header("Content-Length", str(len(encoded)))
    else:
        handler.headers["Content-Length"] = str(len(encoded))


def _email(value: object) -> str:
    return str(value or "").strip().lower()


def _valid_email(value: str) -> bool:
    return bool(value and len(value) <= 254 and EMAIL_RE.fullmatch(value))


def _password_error(password: str, username: str = "") -> str:
    if len(password) < 12:
        return "Le mot de passe doit contenir au moins 12 caractères."
    categories = sum((
        bool(re.search(r"[a-z]", password)), bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"\d", password)), bool(re.search(r"[^A-Za-z0-9]", password)),
    ))
    if categories < 3:
        return "Utilisez au moins trois types de caractères : majuscules, minuscules, chiffres et symboles."
    if username and len(username) >= 4 and username.lower() in password.lower():
        return "Le mot de passe ne doit pas contenir votre identifiant."
    return ""


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session(server, handler, *, csrf: bool = False):
    token = str(handler.headers.get("X-Admin-Token", "") or "")
    session = server.get_session(token) if token else None
    if not session:
        handler._json({"ok": False, "message": "Session expirée"}, 401)
        return None, ""
    if csrf:
        received = str(handler.headers.get("X-CSRF-Token", "") or "")
        expected = str(session.get("csrf_token", "") or "")
        if not received or not expected or not secrets.compare_digest(received, expected):
            server.audit_log("CSRF_REJECT", handler.client_address[0], f"CSRF invalide sur {_path(handler)}")
            handler._json({"ok": False, "message": "Requête invalide (CSRF)"}, 403)
            return None, ""
    return session, token


def _find_user(server, identifier: str):
    wanted = str(identifier or "").strip()
    wanted_email = wanted.lower()
    for user in server.load_users():
        if user.get("username") == wanted or _email(user.get("email")) == wanted_email:
            return user
    return None


def _find_user_by_username(server, username: str):
    return next((u for u in server.load_users() if u.get("username") == username), None)


def _clean_reset_store(raw: object) -> dict:
    now = time.time()
    source = raw if isinstance(raw, dict) else {}
    return {
        str(digest): dict(item) for digest, item in source.items()
        if isinstance(item, dict) and float(item.get("expires_at") or 0) > now
    }


def _load_reset_store(server) -> dict:
    loader = getattr(server, "_pg_load", None)
    if not callable(loader):
        return {}
    try:
        return _clean_reset_store(loader(RESET_STORE_KEY))
    except Exception:
        return {}


def _save_reset_store(server, store: dict) -> bool:
    saver = getattr(server, "_pg_save", None)
    if not callable(saver):
        return False
    try:
        return bool(saver(RESET_STORE_KEY, store))
    except Exception:
        return False


def _revoke_user_sessions(server, username: str) -> None:
    sessions = getattr(server, "ACTIVE_SESSIONS", {})
    if isinstance(sessions, dict):
        for token, session in list(sessions.items()):
            if isinstance(session, dict) and session.get("username") == username:
                sessions.pop(token, None)
    saver = getattr(server, "save_sessions", None)
    if callable(saver):
        try: saver()
        except Exception: pass


def _safe_base_url(handler) -> str:
    configured = (os.environ.get("AUTH_PUBLIC_BASE_URL") or os.environ.get("BININGA_PUBLIC_URL") or "").strip().rstrip("/")
    if configured.startswith(("https://", "http://")):
        return configured
    host = str(handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::\d{1,5})?", host):
        return ""
    proto = str(handler.headers.get("X-Forwarded-Proto") or ("https" if os.environ.get("VERCEL") else "http")).split(",", 1)[0].strip()
    if proto not in {"http", "https"}: proto = "https"
    return f"{proto}://{host}"


def _email_html(name: str, reset_url: str) -> tuple[str, str]:
    safe_name = html.escape(name or "utilisateur")
    safe_url = html.escape(reset_url, quote=True)
    subject = "Réinitialisation de votre mot de passe — BININGA"
    content = f"""<!doctype html><html lang="fr"><body style="margin:0;background:#f4f5f7;font-family:Arial,sans-serif;color:#172033">
<div style="max-width:600px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;border:1px solid #e5e7eb">
<div style="background:#111722;padding:24px 28px;color:#fff"><div style="font-size:22px;font-weight:800">BININGA</div><div style="opacity:.7;font-size:13px;margin-top:4px">Espace Administration</div></div>
<div style="padding:30px 28px"><h1 style="font-size:22px;margin:0 0 18px">Réinitialisation du mot de passe</h1>
<p>Bonjour {safe_name},</p><p>Une demande de réinitialisation de votre mot de passe a été effectuée pour votre compte d’administration BININGA.</p>
<p>Le lien ci-dessous est <strong>valable 30 minutes</strong> et ne peut être utilisé qu’une seule fois.</p>
<p style="margin:28px 0"><a href="{safe_url}" style="display:inline-block;background:#bb1232;color:#fff;text-decoration:none;padding:14px 22px;border-radius:10px;font-weight:700">Réinitialiser mon mot de passe</a></p>
<p style="font-size:13px;color:#667085">Si vous n’êtes pas à l’origine de cette demande, ignorez simplement cet email. Votre mot de passe actuel reste inchangé.</p>
<p style="font-size:13px;color:#667085">Pour votre sécurité, ne transférez pas cet email et ne partagez pas le lien de réinitialisation.</p></div>
<div style="padding:18px 28px;background:#f8fafc;color:#98a2b3;font-size:12px">Message automatique de sécurité — Administration BININGA</div></div></body></html>"""
    return subject, content


def _send_via_resend(to_email: str, subject: str, html_body: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_addr = (os.environ.get("AUTH_EMAIL_FROM") or os.environ.get("NOTIF_EMAIL_FROM") or "").strip()
    if not api_key or not from_addr: return False
    payload = json.dumps({"from": from_addr, "to": [to_email], "subject": subject, "html": html_body}).encode("utf-8")
    req = urllib.request.Request("https://api.resend.com/emails", data=payload, method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        return False


def _send_via_smtp(to_email: str, subject: str, html_body: str) -> bool:
    user = (os.environ.get("AUTH_SMTP_USER") or os.environ.get("NOTIF_EMAIL_FROM") or "").strip()
    password = (os.environ.get("AUTH_SMTP_PASS") or os.environ.get("NOTIF_EMAIL_PASS") or "").strip()
    from_addr = (os.environ.get("AUTH_EMAIL_FROM") or user).strip()
    if not user or not password or not from_addr: return False
    host = os.environ.get("AUTH_SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com"
    try: port = int(os.environ.get("AUTH_SMTP_PORT", "465"))
    except ValueError: port = 465
    message = MIMEMultipart("alternative")
    message["Subject"], message["From"], message["To"] = subject, from_addr, to_email
    message.attach(MIMEText("Une demande de réinitialisation du mot de passe BININGA a été reçue. Consultez la version HTML de cet email.", "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
            smtp.login(user, password); smtp.sendmail(from_addr, [to_email], message.as_string())
        return True
    except Exception:
        return False


def _send_reset_email(user: dict, reset_url: str) -> bool:
    address = _email(user.get("email"))
    if not _valid_email(address): return False
    subject, html_body = _email_html(str(user.get("nom") or user.get("username") or "utilisateur"), reset_url)
    return _send_via_resend(address, subject, html_body) or _send_via_smtp(address, subject, html_body)


def _handle_forgot(server, handler) -> bool:
    payload = _body(handler)
    identifier = str(payload.get("identifier") or payload.get("email") or payload.get("username") or "").strip()
    generic = {"ok": True, "message": "Si un compte correspond à ces informations, un email de réinitialisation vient d’être envoyé."}
    if not identifier:
        handler._json(generic); return False
    user = _find_user(server, identifier)
    if not user or not _valid_email(_email(user.get("email"))):
        time.sleep(0.15); handler._json(generic); return False
    store, now = _load_reset_store(server), time.time()
    recent = any(isinstance(item, dict) and item.get("username") == user.get("username") and now - float(item.get("created_at") or 0) < RESET_COOLDOWN_SECONDS for item in store.values())
    if recent:
        handler._json(generic); return False
    token = secrets.token_urlsafe(40)
    digest = _token_digest(token)
    store[digest] = {"username": user.get("username"), "created_at": now, "expires_at": now + RESET_TTL_SECONDS}
    if not _save_reset_store(server, store):
        server.audit_log("PASSWORD_RESET_STORE_ERROR", handler.client_address[0], "Impossible de persister le jeton de réinitialisation")
        handler._json(generic); return False
    base_url = _safe_base_url(handler)
    delivered = bool(base_url) and _send_reset_email(user, f"{base_url}/static/admin-reset-password.html?token={token}")
    server.audit_log("PASSWORD_RESET_REQUEST", handler.client_address[0], f"Demande de réinitialisation pour {user.get('username')} — email {'envoyé' if delivered else 'non envoyé'}")
    handler._json(generic); return False


def _handle_reset(server, handler) -> bool:
    payload = _body(handler); token = str(payload.get("token") or "").strip(); password = str(payload.get("new_password") or "")
    if not token:
        handler._json({"ok": False, "message": "Lien de réinitialisation invalide ou expiré."}, 400); return False
    store, digest = _load_reset_store(server), _token_digest(token); item = store.get(digest)
    if not isinstance(item, dict) or float(item.get("expires_at") or 0) <= time.time():
        store.pop(digest, None); _save_reset_store(server, store)
        handler._json({"ok": False, "message": "Ce lien de réinitialisation est invalide ou a expiré."}, 400); return False
    username = str(item.get("username") or ""); user = _find_user_by_username(server, username)
    if not user:
        store.pop(digest, None); _save_reset_store(server, store)
        handler._json({"ok": False, "message": "Ce lien de réinitialisation est invalide ou a expiré."}, 400); return False
    error = _password_error(password, username)
    if error:
        handler._json({"ok": False, "message": error}, 400); return False
    users = server.load_users(); target = next((u for u in users if u.get("username") == username), None)
    if not target:
        handler._json({"ok": False, "message": "Compte introuvable."}, 404); return False
    target["password_hash"] = server._hash_new(password); target["must_change_password"] = False; target["password_changed_at"] = _now_iso()
    server.save_users(users); store.pop(digest, None); _save_reset_store(server, store); _revoke_user_sessions(server, username)
    server.audit_log("PASSWORD_RESET_OK", handler.client_address[0], f"Mot de passe réinitialisé pour {username}")
    handler._json({"ok": True, "message": "Votre mot de passe a été modifié. Vous pouvez maintenant vous connecter."}); return False


def _handle_change(server, handler) -> bool:
    session, _ = _session(server, handler, csrf=True)
    if not session: return False
    payload = _body(handler); current_password = str(payload.get("current_password") or ""); new_password = str(payload.get("new_password") or "")
    username = str(session.get("username") or ""); user = _find_user_by_username(server, username)
    if not user or not server._verify_password(current_password, str(user.get("password_hash") or "")):
        handler._json({"ok": False, "message": "Le mot de passe actuel est incorrect."}, 400); return False
    error = _password_error(new_password, username)
    if error:
        handler._json({"ok": False, "message": error}, 400); return False
    if server._verify_password(new_password, str(user.get("password_hash") or "")):
        handler._json({"ok": False, "message": "Le nouveau mot de passe doit être différent de l’ancien."}, 400); return False
    users = server.load_users(); target = next((u for u in users if u.get("username") == username), None)
    if not target:
        handler._json({"ok": False, "message": "Compte introuvable."}, 404); return False
    target["password_hash"] = server._hash_new(new_password); target["must_change_password"] = False; target["password_changed_at"] = _now_iso()
    server.save_users(users); _revoke_user_sessions(server, username)
    server.audit_log("PASSWORD_CHANGE_OK", handler.client_address[0], f"Mot de passe modifié pour {username}")
    handler._json({"ok": True, "reauthenticate": True, "message": "Mot de passe modifié. Reconnectez-vous avec votre nouveau mot de passe."}); return False


def _handle_session(server, handler) -> bool:
    session, _ = _session(server, handler)
    if not session: return False
    user = _find_user_by_username(server, str(session.get("username") or "")) or {}
    handler._json({"ok": True, "username": session.get("username", ""), "email": _email(user.get("email")), "owner": owner_policy.is_owner_user(user), "must_change_password": bool(user.get("must_change_password", False)), "password_changed_at": user.get("password_changed_at", "")})
    return False


def _handle_users_meta(server, handler) -> bool:
    session, _ = _session(server, handler)
    if not session: return False
    if not owner_policy.is_owner_session(server, session):
        handler._json({"ok": False, "message": "Réservé aux propriétaires de l’administration"}, 403); return False
    users = []
    for user in server.load_users():
        users.append({"username": user.get("username", ""), "email": _email(user.get("email")), "owner": owner_policy.is_owner_user(user), "must_change_password": bool(user.get("must_change_password", False)), "password_changed_at": user.get("password_changed_at", "")})
    handler._json({"ok": True, "users": users, "owners": owner_policy.owner_summary(server)}); return False


def _handle_user_upsert(server, handler) -> bool:
    session, _ = _session(server, handler, csrf=True)
    if not session: return False
    if not owner_policy.is_owner_session(server, session):
        handler._json({"ok": False, "message": "Réservé aux propriétaires de l’administration"}, 403); return False
    data = _body(handler); username = str(data.get("username") or "").strip(); name = str(data.get("nom") or "").strip(); role = str(data.get("role") or "lecteur")
    password = str(data.get("password") or "").strip(); email_address = _email(data.get("email"))
    if not username or role not in ALLOWED_ROLES:
        handler._json({"ok": False, "message": "Données utilisateur invalides."}, 400); return False
    if not _valid_email(email_address):
        handler._json({"ok": False, "message": "Une adresse email valide est obligatoire pour la récupération du compte."}, 400); return False
    users = server.load_users(); existing = next((u for u in users if u.get("username") == username), None)
    if existing and owner_policy.is_owner_user(existing) and email_address != _email(existing.get("email")):
        handler._json({"ok": False, "message": "L’adresse email d’un owner ne peut pas être remplacée depuis la gestion standard des utilisateurs."}, 409); return False
    owner_email = email_address in set(owner_policy.owner_emails())
    final_role = "admin" if owner_email else role
    if existing:
        existing["nom"] = name or existing.get("nom") or username; existing["role"] = final_role; existing["email"] = email_address
        existing["owner"] = owner_email
        if password:
            error = _password_error(password, username)
            if error: handler._json({"ok": False, "message": error}, 400); return False
            existing["password_hash"] = server._hash_new(password)
            if username != session.get("username"):
                existing["must_change_password"] = True; existing["password_changed_at"] = ""; _revoke_user_sessions(server, username)
    else:
        if not password:
            handler._json({"ok": False, "message": "Un mot de passe provisoire est obligatoire."}, 400); return False
        error = _password_error(password, username)
        if error: handler._json({"ok": False, "message": error}, 400); return False
        users.append({"username": username, "password_hash": server._hash_new(password), "role": final_role, "nom": name or username, "email": email_address, "owner": owner_email, "created_by": session.get("username", ""), "must_change_password": True, "password_changed_at": ""})
    server.save_users(users)
    server.audit_log("USER_UPSERT", handler.client_address[0], f"{'Modification' if existing else 'Création'} utilisateur : {username} ({final_role})")
    handler._json({"ok": True, "owner": owner_email, "must_change_password": bool((existing or {}).get("must_change_password", not existing))}); return False


def _handle_owner_delete_guard(server, handler) -> bool:
    payload = _body(handler); username = str(payload.get("username") or "").strip()
    user = _find_user_by_username(server, username)
    if user and owner_policy.is_owner_user(user):
        handler._json({"ok": False, "message": "Un compte owner protégé ne peut pas être supprimé."}, 409); return False
    return True


def _block_until_password_changed(server, handler) -> bool:
    path = _path(handler)
    if not path.startswith("/api/") or path in PASSWORD_CHANGE_PATHS or path in PUBLIC_AUTH_POSTS or path == "/api/login": return True
    token = str(handler.headers.get("X-Admin-Token", "") or ""); session = server.get_session(token) if token else None
    if not session: return True
    user = _find_user_by_username(server, str(session.get("username") or ""))
    if user and user.get("must_change_password"):
        handler._json({"ok": False, "code": "PASSWORD_CHANGE_REQUIRED", "must_change_password": True, "message": "Vous devez définir votre nouveau mot de passe avant d’accéder à l’administration."}, 428); return False
    return True


def _rewrite_email_login(server, handler) -> None:
    payload = _body(handler)
    identifier = str(payload.get("username") or "").strip()
    resolved = owner_policy.resolve_login_identifier(server, identifier)
    if resolved and resolved != identifier:
        payload["username"] = resolved
        _rewrite_body(handler, payload)


def guard_request(server, handler):
    path = _path(handler); method = str(getattr(handler, "command", "GET")).upper()
    if method == "POST" and path == "/api/login":
        _rewrite_email_login(server, handler)
    if not _block_until_password_changed(server, handler): return False
    if method == "POST" and path == "/api/auth/forgot-password": return _handle_forgot(server, handler)
    if method == "POST" and path == "/api/auth/reset-password": return _handle_reset(server, handler)
    if method == "POST" and path == "/api/auth/change-password": return _handle_change(server, handler)
    if method == "GET" and path == "/api/auth/session": return _handle_session(server, handler)
    if method == "GET" and path == "/api/auth/users-meta": return _handle_users_meta(server, handler)
    if method == "POST" and path == "/api/users/upsert": return _handle_user_upsert(server, handler)
    if method == "POST" and path == "/api/users/delete": return _handle_owner_delete_guard(server, handler)
    return True


def _replace_json_response(handler, payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.wfile.seek(0); handler.wfile.truncate(0); handler.wfile.write(encoded)
    handler._response_headers = [(key, value) for key, value in getattr(handler, "_response_headers", []) if str(key).lower() not in {"content-length", "content-type"}]
    handler._response_headers.append(("Content-Type", "application/json; charset=utf-8")); handler._response_headers.append(("Content-Length", str(len(encoded))))


def postprocess_response(server, handler) -> None:
    if str(getattr(handler, "command", "GET")).upper() != "POST" or _path(handler) != "/api/login": return
    if int(getattr(handler, "_status_code", 200)) != 200: return
    try: payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
    except Exception: return
    if not isinstance(payload, dict) or not payload.get("ok"): return
    username = str(payload.get("username") or ""); user = _find_user_by_username(server, username) or {}
    is_owner = owner_policy.is_owner_user(user)
    payload["must_change_password"] = bool(user.get("must_change_password", False)); payload["email"] = _email(user.get("email"))
    payload["is_main_admin"] = is_owner; payload["is_owner"] = is_owner
    admin_path = str(getattr(server, "ADMIN_SECRET_PATH", "") or "").strip().strip("/")
    if admin_path: payload["admin_path"] = f"/{admin_path}"
    _replace_json_response(handler, payload)
