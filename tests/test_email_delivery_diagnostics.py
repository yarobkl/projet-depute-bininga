import contextlib
import io
import os
import pathlib
import sys
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import email_delivery_diagnostics as diag


class DummyAuth:
    @staticmethod
    def _handle_forgot(server, handler):
        handler.original_called = True
        return False


class DummyServer:
    def __init__(self):
        self.audit = []

    def audit_log(self, event, ip, message):
        self.audit.append((event, ip, message))


class DummyHandler:
    def __init__(self):
        self.client_address = ("127.0.0.1", 0)
        self.status = None
        self.payload = None
        self.original_called = False

    def _json(self, payload, status=200):
        self.payload = payload
        self.status = status


@contextlib.contextmanager
def clean_email_env():
    names = [
        "RESEND_API_KEY", "AUTH_EMAIL_FROM", "NOTIF_EMAIL_FROM",
        "AUTH_SMTP_USER", "AUTH_SMTP_PASS", "NOTIF_EMAIL_PASS",
        "AUTH_SMTP_HOST", "AUTH_SMTP_PORT",
    ]
    saved = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ.pop(name, None)
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_presence_only_status():
    with clean_email_env():
        status = diag.provider_status()
        assert status["resend_configured"] is False
        assert status["smtp_configured"] is False
        os.environ["RESEND_API_KEY"] = "secret-value-never-log"
        os.environ["AUTH_EMAIL_FROM"] = "sender@example.test"
        status = diag.provider_status()
        assert status["resend_configured"] is True
        assert "secret-value-never-log" not in repr(status)
        assert "sender@example.test" not in repr(status)


def test_install_and_missing_config_logs_are_safe():
    with clean_email_env():
        diag._INSTALLED = False
        auth = DummyAuth()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            diag.install(auth)
            assert auth._send_via_resend("recipient@example.test", "subject", "<p>x</p>") is False
            assert auth._send_via_smtp("recipient@example.test", "subject", "<p>x</p>") is False
        output = buffer.getvalue()
        assert "provider_status" in output
        assert "resend_skipped" in output
        assert "smtp_skipped" in output
        assert "recipient@example.test" not in output
        assert "secret-value-never-log" not in output


def test_unconfigured_provider_returns_503_without_fake_success():
    with clean_email_env():
        diag._INSTALLED = False
        auth = DummyAuth()
        server = DummyServer()
        handler = DummyHandler()
        diag.install(auth)
        result = auth._handle_forgot(server, handler)
        assert result is False
        assert handler.status == 503
        assert handler.payload["ok"] is False
        assert handler.payload["code"] == "EMAIL_DELIVERY_NOT_CONFIGURED"
        assert "Aucun email n’a été envoyé" in handler.payload["message"]
        assert handler.original_called is False
        assert any(event == "EMAIL_DELIVERY_UNAVAILABLE" for event, _, _ in server.audit)


def test_resend_request_includes_explicit_user_agent():
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    with clean_email_env():
        os.environ["RESEND_API_KEY"] = "secret-value-never-log"
        os.environ["AUTH_EMAIL_FROM"] = "BININGA <onboarding@resend.dev>"
        with mock.patch.object(diag.urllib.request, "urlopen", side_effect=fake_urlopen):
            assert diag._resend_sender("recipient@example.test", "subject", "<p>x</p>") is True

    assert captured["request"].get_header("User-agent") == "bininga-auth/1.0"
    assert captured["timeout"] == 10


def test_source_never_logs_sensitive_fields():
    source = (ROOT / "email_delivery_diagnostics.py").read_text(encoding="utf-8")
    assert '"api_key", "password", "recipient", "to_email", "token", "reset_url"' in source
    assert "print(api_key" not in source
    assert "print(password" not in source
    assert "print(to_email" not in source


if __name__ == "__main__":
    test_presence_only_status()
    test_install_and_missing_config_logs_are_safe()
    test_unconfigured_provider_returns_503_without_fake_success()
    test_resend_request_includes_explicit_user_agent()
    test_source_never_logs_sensitive_fields()
    print("✅ Diagnostic email sécurisé — OK")
