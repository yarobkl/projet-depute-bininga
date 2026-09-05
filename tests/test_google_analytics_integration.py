"""Regression tests for BININGA Google Analytics/Search Console integration."""
from __future__ import annotations

import hashlib
import os
import secrets
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import google_analytics_integration as google


class FakeServer:
    ADMIN_USER = "admin"
    secrets = secrets

    def __init__(self):
        self.store = {}
        self.sessions = {
            "owner-token": {"username": "admin", "role": "admin", "csrf_token": "owner-csrf"},
            "admin-token": {"username": "collab", "role": "admin", "csrf_token": "admin-csrf"},
        }
        self.users = [
            {"username": "admin", "role": "admin"},
            {"username": "collab", "role": "admin"},
        ]
        self.audit = []

    def get_session(self, token):
        return self.sessions.get(token)

    def load_users(self):
        return self.users

    def _pg_load(self, key):
        return self.store.get(key)

    def _pg_save(self, key, value):
        self.store[key] = value
        return True

    def audit_log(self, action, ip, detail):
        self.audit.append((action, ip, detail))


class FakeHandler:
    def __init__(self, path, method="GET", token="owner-token", csrf="owner-csrf"):
        self.path = path
        self.command = method
        self.headers = {"Host": "projet-depute-bininga.vercel.app"}
        if token:
            self.headers["X-Admin-Token"] = token
        if csrf:
            self.headers["X-CSRF-Token"] = csrf
        self.client_address = ("127.0.0.1", 1234)
        self.payload = None
        self.status = None
        self.response_headers = {}

    def _json(self, payload, status=200):
        self.payload = payload
        self.status = status

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        return None


def test_status_is_read_only_and_sanitized():
    server = FakeServer()
    server.store[google.INTEGRATION_KEY] = {
        "access_token": "secret-access",
        "refresh_token": "secret-refresh",
        "property_id": "123456789",
        "property_name": "BININGA",
        "measurement_id": google.MEASUREMENT_ID,
        "site_url": "https://projet-depute-bininga.vercel.app/",
        "email": "analytics@example.test",
    }
    handler = FakeHandler("/api/google/status")
    with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "csecret", "GOOGLE_REDIRECT_URI": "https://projet-depute-bininga.vercel.app/api/google/callback"}, clear=False):
        assert google.guard_request(server, handler) is False
    assert handler.status == 200
    assert handler.payload["connected"] is True
    assert handler.payload["property_id"] == "123456789"
    assert "access_token" not in handler.payload
    assert "refresh_token" not in handler.payload


def test_owner_can_prepare_oauth_but_collaborator_cannot():
    server = FakeServer()
    env = {
        "GOOGLE_CLIENT_ID": "client-id",
        "GOOGLE_CLIENT_SECRET": "client-secret",
        "GOOGLE_REDIRECT_URI": "https://projet-depute-bininga.vercel.app/api/google/callback",
    }
    with patch.dict(os.environ, env, clear=False):
        owner = FakeHandler("/api/google/connect", method="POST")
        assert google.guard_request(server, owner) is False
        assert owner.status == 200
        assert owner.payload["authorization_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert server.store[google.OAUTH_STATES_KEY]

        collaborator = FakeHandler("/api/google/connect", method="POST", token="admin-token", csrf="admin-csrf")
        assert google.guard_request(server, collaborator) is False
        assert collaborator.status == 403


def test_callback_consumes_state_and_stores_server_only_tokens():
    server = FakeServer()
    raw_state = "state-value"
    state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
    server.store[google.OAUTH_STATES_KEY] = {
        state_hash: {"username": "admin", "expires_at": int(time.time()) + 300}
    }
    handler = FakeHandler(f"/api/google/callback?code=abc&state={raw_state}", token="", csrf="")
    env = {
        "GOOGLE_CLIENT_ID": "client-id",
        "GOOGLE_CLIENT_SECRET": "client-secret",
        "GOOGLE_REDIRECT_URI": "https://projet-depute-bininga.vercel.app/api/google/callback",
    }
    with patch.dict(os.environ, env, clear=False), \
         patch.object(google, "_token_exchange", return_value={"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}), \
         patch.object(google, "_request_json", return_value={"email": "owner@example.test"}), \
         patch.object(google, "_discover_analytics_property", return_value={"property_id": "987", "property_name": "BININGA GA4", "measurement_id": google.MEASUREMENT_ID}), \
         patch.object(google, "_discover_search_console", return_value={"site_url": "https://projet-depute-bininga.vercel.app/", "permission_level": "siteOwner"}):
        assert google.guard_request(server, handler) is False
    assert handler.status == 302
    assert handler.response_headers["Location"].endswith("?google=connected")
    stored = server.store[google.INTEGRATION_KEY]
    assert stored["access_token"] == "access"
    assert stored["refresh_token"] == "refresh"
    assert stored["property_id"] == "987"
    assert server.store[google.OAUTH_STATES_KEY] == {}


def test_data_endpoint_caches_normalized_google_data():
    server = FakeServer()
    integration = {
        "refresh_token": "refresh",
        "access_token": "access",
        "expires_at": int(time.time()) + 3600,
        "property_id": "987",
        "property_name": "BININGA GA4",
        "measurement_id": google.MEASUREMENT_ID,
        "site_url": "https://projet-depute-bininga.vercel.app/",
    }
    server.store[google.INTEGRATION_KEY] = integration
    ga_result = {"summary": {"activeUsers": 12.0}, "daily": [], "traffic": [], "pages": [], "countries": [], "devices": [], "realtime": {"activeUsers": 2.0}}
    gsc_result = {"summary": {"clicks": 4.0, "impressions": 100.0, "ctr": .04, "position": 8.2}, "daily": [], "queries": [], "pages": []}
    handler = FakeHandler("/api/google/data?days=28")
    with patch.object(google, "_fetch_ga", return_value=ga_result) as ga_mock, patch.object(google, "_fetch_search_console", return_value=gsc_result) as gsc_mock:
        assert google.guard_request(server, handler) is False
        assert handler.status == 200
        assert handler.payload["analytics"]["summary"]["activeUsers"] == 12.0
        assert handler.payload["search_console"]["summary"]["clicks"] == 4.0
        assert "access_token" not in str(handler.payload)
        assert ga_mock.call_count == 1 and gsc_mock.call_count == 1

        second = FakeHandler("/api/google/data?days=28")
        assert google.guard_request(server, second) is False
        assert second.status == 200
        assert second.payload["cached"] is True
        assert ga_mock.call_count == 1 and gsc_mock.call_count == 1


def test_frontend_is_optional_and_lazy():
    bootstrap = (ROOT / "static/admin-session-hardening.js").read_text(encoding="utf-8")
    ui = (ROOT / "static/admin-google-analytics.js").read_text(encoding="utf-8")
    pipeline = (ROOT / "admin_request_pipeline.py").read_text(encoding="utf-8")
    assert "data-bininga-google-analytics" in bootstrap
    assert "admin-google-analytics.js" in bootstrap
    assert "google_analytics_integration.guard_request" in pipeline
    assert "admin:panelchange" in ui
    assert "event.detail?.name !== 'google-analytics'" in ui
    assert "window.init =" not in ui
    assert "MutationObserver" not in ui


def run_all():
    test_status_is_read_only_and_sanitized()
    test_owner_can_prepare_oauth_but_collaborator_cannot()
    test_callback_consumes_state_and_stores_server_only_tokens()
    test_data_endpoint_caches_normalized_google_data()
    test_frontend_is_optional_and_lazy()
    print("Google analytics integration tests: OK")


if __name__ == "__main__":
    run_all()
