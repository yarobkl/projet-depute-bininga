"""Secure transactional-email diagnostics for BININGA.

This module wraps the legacy auth email senders so production failures become
observable without exposing API keys, SMTP passwords, recipient addresses, or
reset tokens. It is installed at runtime by the Vercel entrypoint.
"""
from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


_INSTALLED = False


def _present(name: str) -> bool:
    return bool(str(os.environ.get(name, "") or "").strip())


def provider_status() -> dict:
    """Return presence-only configuration diagnostics; never return secret values."""
    resend_key = _present("RESEND_API_KEY")
    email_from = _present("AUTH_EMAIL_FROM") or _present("NOTIF_EMAIL_FROM")
    smtp_user = _present("AUTH_SMTP_USER") or _present("NOTIF_EMAIL_FROM")
    smtp_pass = _present("AUTH_SMTP_PASS") or _present("NOTIF_EMAIL_PASS")
    return {
        "resend_configured": bool(resend_key and email_from),
        "smtp_configured": bool(smtp_user and smtp_pass and email_from),
        "resend_key_present": resend_key,
        "sender_present": email_from,
        "smtp_user_present": smtp_user,
        "smtp_password_present": smtp_pass,
    }


def delivery_available() -> bool:
    status = provider_status()
    return bool(status["resend_configured"] or status["smtp_configured"])


def _log(event: str, **fields) -> None:
    safe = {"event": event}
    for key, value in fields.items():
        if key in {"api_key", "password", "recipient", "to_email", "token", "reset_url"}:
            continue
        safe[str(key)] = value
    print("[AUTH_EMAIL] " + json.dumps(safe, ensure_ascii=False, sort_keys=True), flush=True)


def _resend_sender(to_email: str, subject: str, html_body: str) -> bool:
    api_key = str(os.environ.get("RESEND_API_KEY", "") or "").strip()
    from_addr = str(os.environ.get("AUTH_EMAIL_FROM") or os.environ.get("NOTIF_EMAIL_FROM") or "").strip()
    missing = []
    if not api_key:
        missing.append("RESEND_API_KEY")
    if not from_addr:
        missing.append("AUTH_EMAIL_FROM/NOTIF_EMAIL_FROM")
    if missing:
        _log("resend_skipped", reason="missing_configuration", missing=missing)
        return False

    payload = json.dumps({"from": from_addr, "to": [to_email], "subject": subject, "html": html_body}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = int(getattr(response, "status", 0) or 0)
            ok = 200 <= status < 300
            _log("resend_result", ok=ok, http_status=status)
            return ok
    except urllib.error.HTTPError as exc:
        _log("resend_error", error_type="HTTPError", http_status=int(getattr(exc, "code", 0) or 0))
        return False
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        _log("resend_error", error_type="URLError", reason_type=type(reason).__name__ if reason is not None else "unknown")
        return False
    except Exception as exc:
        _log("resend_error", error_type=type(exc).__name__)
        return False


def _smtp_sender(to_email: str, subject: str, html_body: str) -> bool:
    user = str(os.environ.get("AUTH_SMTP_USER") or os.environ.get("NOTIF_EMAIL_FROM") or "").strip()
    password = str(os.environ.get("AUTH_SMTP_PASS") or os.environ.get("NOTIF_EMAIL_PASS") or "").strip()
    from_addr = str(os.environ.get("AUTH_EMAIL_FROM") or user).strip()
    missing = []
    if not user:
        missing.append("AUTH_SMTP_USER/NOTIF_EMAIL_FROM")
    if not password:
        missing.append("AUTH_SMTP_PASS/NOTIF_EMAIL_PASS")
    if not from_addr:
        missing.append("AUTH_EMAIL_FROM/smtp_user")
    if missing:
        _log("smtp_skipped", reason="missing_configuration", missing=missing)
        return False

    host = str(os.environ.get("AUTH_SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com").strip()
    try:
        port = int(os.environ.get("AUTH_SMTP_PORT", "465"))
    except ValueError:
        port = 465

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to_email
    message.attach(MIMEText(
        "Une demande de réinitialisation du mot de passe BININGA a été reçue. Consultez la version HTML de cet email.",
        "plain",
        "utf-8",
    ))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
            smtp.login(user, password)
            smtp.sendmail(from_addr, [to_email], message.as_string())
        _log("smtp_result", ok=True, host=host, port=port)
        return True
    except smtplib.SMTPAuthenticationError as exc:
        _log("smtp_error", error_type="SMTPAuthenticationError", smtp_code=int(getattr(exc, "smtp_code", 0) or 0), host=host, port=port)
        return False
    except smtplib.SMTPResponseException as exc:
        _log("smtp_error", error_type=type(exc).__name__, smtp_code=int(getattr(exc, "smtp_code", 0) or 0), host=host, port=port)
        return False
    except Exception as exc:
        _log("smtp_error", error_type=type(exc).__name__, host=host, port=port)
        return False


def _wrap_forgot_handler(auth_module):
    original = auth_module._handle_forgot

    def guarded_handle_forgot(server, handler):
        # Provider availability is global, so returning 503 here does not reveal
        # whether the submitted account/email exists.
        if not delivery_available():
            status = provider_status()
            _log("delivery_unavailable", **status)
            try:
                server.audit_log(
                    "EMAIL_DELIVERY_UNAVAILABLE",
                    handler.client_address[0],
                    "Aucun fournisseur d'email transactionnel n'est configuré",
                )
            except Exception:
                pass
            handler._json({
                "ok": False,
                "code": "EMAIL_DELIVERY_NOT_CONFIGURED",
                "message": "Le service d’envoi d’emails de l’administration n’est pas encore configuré. Aucun email n’a été envoyé.",
            }, 503)
            return False
        return original(server, handler)

    auth_module._handle_forgot = guarded_handle_forgot


def install(auth_module) -> dict:
    """Install secure observable senders into admin_auth_flow exactly once."""
    global _INSTALLED
    status = provider_status()
    if not _INSTALLED:
        auth_module._send_via_resend = _resend_sender
        auth_module._send_via_smtp = _smtp_sender
        auth_module.email_provider_status = provider_status
        _wrap_forgot_handler(auth_module)
        _INSTALLED = True
    _log("provider_status", **status)
    return status
