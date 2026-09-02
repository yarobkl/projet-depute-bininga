import io
import json

import vercel_entrypoint


def test_hardened_chat_route_is_intercepted(monkeypatch):
    # Le point d'entrée charge volontairement l'application lourde seulement
    # lorsqu'une route dynamique est appelée.
    vercel_entrypoint._load_legacy_application()
    import chatbot_hardening
    import passenger_wsgi

    called = {"hardened": 0, "legacy": 0}

    def fake_guard(server, handler):
        called["hardened"] += 1
        handler._json({"ok": True, "reply": "hardened"})
        return False

    def fake_legacy(environ, start_response):
        called["legacy"] += 1
        start_response("200 OK", [])
        return [b"legacy"]

    monkeypatch.setattr(chatbot_hardening, "guard_request", fake_guard)
    monkeypatch.setattr(passenger_wsgi, "application", fake_legacy)

    payload = json.dumps({"message": "bonjour"}).encode()
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/chat",
        "QUERY_STRING": "",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "REMOTE_ADDR": "127.0.0.1",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(vercel_entrypoint.application(environ, start_response))
    assert captured["status"].startswith("200")
    assert json.loads(body)["reply"] == "hardened"
    assert called == {"hardened": 1, "legacy": 0}
