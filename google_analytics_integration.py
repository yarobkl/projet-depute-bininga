"""Google Analytics 4 + Search Console integration for BININGA admin.

The public site already sends consent-aware GA4 events. This module adds the
read-only Google side of the integration for the private administration area:
OAuth, token refresh, property discovery and a small durable response cache.

Tokens are kept server-side only in the existing durable key/value database and
are never returned to the browser.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import Request, urlopen

import admin_owners

MEASUREMENT_ID = os.environ.get("GOOGLE_ANALYTICS_MEASUREMENT_ID", "G-N283W7662X").strip()
INTEGRATION_KEY = "google_integration"
OAUTH_STATES_KEY = "google_oauth_states"
CACHE_KEY = "google_analytics_cache"
CACHE_TTL_SECONDS = 300
STATE_TTL_SECONDS = 600
SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
)


def _load(server: Any, key: str, default: Any = None) -> Any:
    loader = getattr(server, "_pg_load", None)
    if not callable(loader):
        return default
    try:
        value = loader(key)
    except Exception:
        return default
    return default if value is None else value


def _save(server: Any, key: str, value: Any) -> bool:
    saver = getattr(server, "_pg_save", None)
    if not callable(saver):
        return False
    try:
        return bool(saver(key, value))
    except Exception:
        return False


def _session(server: Any, handler: Any):
    token = str(handler.headers.get("X-Admin-Token", "") or "")
    return server.get_session(token) if token else None


def _can_read(server: Any, session: Any) -> bool:
    if not isinstance(session, dict):
        return False
    return admin_owners.is_owner_session(server, session) or session.get("role") in ("admin", "ministre")


def _can_manage(server: Any, session: Any) -> bool:
    return bool(isinstance(session, dict) and admin_owners.is_owner_session(server, session))


def _csrf_valid(server: Any, handler: Any, session: dict) -> bool:
    received = str(handler.headers.get("X-CSRF-Token", "") or "")
    expected = str(session.get("csrf_token", "") or "")
    if not received or not expected:
        return False
    try:
        return bool(server.secrets.compare_digest(received, expected))
    except Exception:
        return secrets.compare_digest(received, expected)


def _client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def _client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()


def _redirect_uri(handler: Any | None = None) -> str:
    explicit = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        return "https://projet-depute-bininga.vercel.app/api/google/callback"
    public = os.environ.get("AUTH_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public.startswith(("https://", "http://")) and "example" not in public:
        return public + "/api/google/callback"
    if handler is not None:
        host = str(handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host") or "localhost")
        proto = str(handler.headers.get("X-Forwarded-Proto") or "http").split(",", 1)[0].strip()
        return f"{proto}://{host}/api/google/callback"
    return ""


def _configured(handler: Any | None = None) -> bool:
    return bool(_client_id() and _client_secret() and _redirect_uri(handler))


def _request_json(
    url: str,
    *,
    method: str = "GET",
    access_token: str = "",
    json_body: Any = None,
    form_body: dict[str, Any] | None = None,
    timeout: int = 15,
) -> dict:
    headers = {"Accept": "application/json", "User-Agent": "BININGA-Admin/1.0"}
    data = None
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif form_body is not None:
        data = urlencode(form_body).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
            detail = payload.get("error_description") or payload.get("error", {}).get("message") or payload.get("error")
        except Exception:
            detail = raw.decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"Google HTTP {exc.code}: {detail or exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Google indisponible: {exc.reason}") from exc
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("Réponse Google invalide") from exc
    return payload if isinstance(payload, dict) else {}


def _token_exchange(code: str, redirect_uri: str) -> dict:
    return _request_json(
        "https://oauth2.googleapis.com/token",
        method="POST",
        form_body={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )


def _refresh_token(refresh_token: str) -> dict:
    return _request_json(
        "https://oauth2.googleapis.com/token",
        method="POST",
        form_body={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )


def _property_id(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.startswith("properties/"):
        raw = raw.split("/", 1)[1]
    return raw if raw.isdigit() else ""


def _discover_analytics_property(access_token: str) -> dict:
    configured_property = _property_id(os.environ.get("GOOGLE_ANALYTICS_PROPERTY_ID", ""))
    if configured_property:
        return {
            "property_id": configured_property,
            "property_name": os.environ.get("GOOGLE_ANALYTICS_PROPERTY_NAME", "BININGA"),
            "measurement_id": MEASUREMENT_ID,
        }

    summaries = _request_json(
        "https://analyticsadmin.googleapis.com/v1beta/accountSummaries?pageSize=200",
        access_token=access_token,
    )
    candidates: list[tuple[str, str]] = []
    for account in summaries.get("accountSummaries", []) or []:
        if not isinstance(account, dict):
            continue
        for prop in account.get("propertySummaries", []) or []:
            if not isinstance(prop, dict):
                continue
            pid = _property_id(prop.get("property"))
            if pid:
                candidates.append((pid, str(prop.get("displayName") or "Google Analytics")))

    for pid, name in candidates:
        try:
            streams = _request_json(
                f"https://analyticsadmin.googleapis.com/v1beta/properties/{pid}/dataStreams?pageSize=200",
                access_token=access_token,
            )
        except Exception:
            continue
        for stream in streams.get("dataStreams", []) or []:
            if not isinstance(stream, dict):
                continue
            measurement = str((stream.get("webStreamData") or {}).get("measurementId") or "")
            if measurement and measurement == MEASUREMENT_ID:
                return {"property_id": pid, "property_name": name, "measurement_id": measurement}
    return {"property_id": "", "property_name": "", "measurement_id": MEASUREMENT_ID}


def _search_console_hosts() -> list[str]:
    hosts: list[str] = []
    configured = os.environ.get("GOOGLE_SEARCH_CONSOLE_SITE_URL", "").strip()
    if configured:
        hosts.append(configured.lower())
    public = os.environ.get("AUTH_PUBLIC_BASE_URL", "").strip()
    if public.startswith(("http://", "https://")) and "example" not in public:
        hosts.append((urlsplit(public).hostname or "").lower())
    hosts.extend(["projet-depute-bininga.vercel.app", "depute-bininga.vercel.app"])
    return [item for item in hosts if item]


def _discover_search_console(access_token: str) -> dict:
    payload = _request_json("https://www.googleapis.com/webmasters/v3/sites", access_token=access_token)
    entries = [row for row in (payload.get("siteEntry") or []) if isinstance(row, dict)]
    verified = [row for row in entries if row.get("permissionLevel") != "siteUnverifiedUser"]
    hosts = _search_console_hosts()
    for row in verified:
        site_url = str(row.get("siteUrl") or "")
        low = site_url.lower()
        if any(host in low for host in hosts):
            return {"site_url": site_url, "permission_level": row.get("permissionLevel", "")}
    explicit = os.environ.get("GOOGLE_SEARCH_CONSOLE_SITE_URL", "").strip()
    if explicit:
        return {"site_url": explicit, "permission_level": "configured"}
    return {"site_url": "", "permission_level": "", "available_sites": len(verified)}


def _valid_access_token(server: Any) -> tuple[str, dict]:
    integration = _load(server, INTEGRATION_KEY, {})
    if not isinstance(integration, dict) or not integration.get("refresh_token"):
        raise RuntimeError("Google n’est pas connecté")
    now = int(time.time())
    if integration.get("access_token") and int(integration.get("expires_at") or 0) > now + 60:
        return str(integration["access_token"]), integration
    refreshed = _refresh_token(str(integration.get("refresh_token")))
    access_token = str(refreshed.get("access_token") or "")
    if not access_token:
        raise RuntimeError("Impossible de renouveler la connexion Google")
    integration["access_token"] = access_token
    integration["expires_at"] = now + max(60, int(refreshed.get("expires_in") or 3600))
    if refreshed.get("scope"):
        integration["scope"] = refreshed.get("scope")
    if not _save(server, INTEGRATION_KEY, integration):
        raise RuntimeError("Impossible de persister le jeton Google renouvelé")
    return access_token, integration


def _ga_report(access_token: str, property_id: str, body: dict) -> dict:
    return _request_json(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{quote(property_id, safe='')}:runReport",
        method="POST",
        access_token=access_token,
        json_body=body,
    )


def _ga_realtime(access_token: str, property_id: str) -> dict:
    return _request_json(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{quote(property_id, safe='')}:runRealtimeReport",
        method="POST",
        access_token=access_token,
        json_body={"metrics": [{"name": "activeUsers"}, {"name": "eventCount"}]},
    )


def _metric_map(report: dict) -> dict[str, float]:
    headers = [str(row.get("name") or "") for row in (report.get("metricHeaders") or []) if isinstance(row, dict)]
    rows = report.get("rows") or []
    values = rows[0].get("metricValues", []) if rows and isinstance(rows[0], dict) else []
    result: dict[str, float] = {}
    for index, name in enumerate(headers):
        try:
            result[name] = float(values[index].get("value") or 0)
        except Exception:
            result[name] = 0.0
    return result


def _dimension_rows(report: dict, dimension_names: list[str]) -> list[dict]:
    metric_headers = [str(row.get("name") or "") for row in (report.get("metricHeaders") or []) if isinstance(row, dict)]
    result: list[dict] = []
    for row in report.get("rows") or []:
        if not isinstance(row, dict):
            continue
        dimensions = row.get("dimensionValues") or []
        metrics = row.get("metricValues") or []
        item: dict[str, Any] = {}
        for index, name in enumerate(dimension_names):
            item[name] = str(dimensions[index].get("value") or "") if index < len(dimensions) else ""
        for index, name in enumerate(metric_headers):
            try:
                item[name] = float(metrics[index].get("value") or 0)
            except Exception:
                item[name] = 0.0
        result.append(item)
    return result


def _fetch_ga(access_token: str, property_id: str, start_date: str, end_date: str) -> dict:
    ranges = [{"startDate": start_date, "endDate": end_date}]
    summary_metrics = [
        {"name": "activeUsers"}, {"name": "newUsers"}, {"name": "sessions"},
        {"name": "screenPageViews"}, {"name": "eventCount"}, {"name": "engagedSessions"},
        {"name": "engagementRate"}, {"name": "averageSessionDuration"},
    ]
    jobs = {
        "summary": lambda: _ga_report(access_token, property_id, {"dateRanges": ranges, "metrics": summary_metrics}),
        "daily": lambda: _ga_report(access_token, property_id, {"dateRanges": ranges, "dimensions": [{"name": "date"}], "metrics": summary_metrics, "orderBys": [{"dimension": {"dimensionName": "date"}}], "limit": "1000"}),
        "traffic": lambda: _ga_report(access_token, property_id, {"dateRanges": ranges, "dimensions": [{"name": "sessionDefaultChannelGroup"}], "metrics": [{"name": "sessions"}, {"name": "activeUsers"}, {"name": "engagedSessions"}], "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}], "limit": "20"}),
        "pages": lambda: _ga_report(access_token, property_id, {"dateRanges": ranges, "dimensions": [{"name": "pagePath"}], "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}, {"name": "engagementRate"}], "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}], "limit": "20"}),
        "countries": lambda: _ga_report(access_token, property_id, {"dateRanges": ranges, "dimensions": [{"name": "country"}], "metrics": [{"name": "activeUsers"}, {"name": "sessions"}], "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}], "limit": "20"}),
        "devices": lambda: _ga_report(access_token, property_id, {"dateRanges": ranges, "dimensions": [{"name": "deviceCategory"}], "metrics": [{"name": "activeUsers"}, {"name": "sessions"}], "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}], "limit": "20"}),
        "realtime": lambda: _ga_realtime(access_token, property_id),
    }
    reports: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        future_map = {pool.submit(fn): name for name, fn in jobs.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                reports[name] = future.result()
            except Exception as exc:
                reports[name] = {"_error": str(exc)}

    if reports.get("summary", {}).get("_error"):
        raise RuntimeError(reports["summary"]["_error"])
    return {
        "summary": _metric_map(reports.get("summary", {})),
        "daily": _dimension_rows(reports.get("daily", {}), ["date"]),
        "traffic": _dimension_rows(reports.get("traffic", {}), ["channel"]),
        "pages": _dimension_rows(reports.get("pages", {}), ["page"]),
        "countries": _dimension_rows(reports.get("countries", {}), ["country"]),
        "devices": _dimension_rows(reports.get("devices", {}), ["device"]),
        "realtime": _metric_map(reports.get("realtime", {})) if not reports.get("realtime", {}).get("_error") else {},
    }


def _gsc_query(access_token: str, site_url: str, body: dict) -> dict:
    return _request_json(
        f"https://www.googleapis.com/webmasters/v3/sites/{quote(site_url, safe='')}/searchAnalytics/query",
        method="POST",
        access_token=access_token,
        json_body=body,
    )


def _gsc_rows(report: dict, keys: list[str]) -> list[dict]:
    result: list[dict] = []
    for row in report.get("rows") or []:
        if not isinstance(row, dict):
            continue
        raw_keys = row.get("keys") or []
        item: dict[str, Any] = {}
        for index, name in enumerate(keys):
            item[name] = str(raw_keys[index]) if index < len(raw_keys) else ""
        item.update({
            "clicks": float(row.get("clicks") or 0),
            "impressions": float(row.get("impressions") or 0),
            "ctr": float(row.get("ctr") or 0),
            "position": float(row.get("position") or 0),
        })
        result.append(item)
    return result


def _fetch_search_console(access_token: str, site_url: str, start_date: str, end_date: str) -> dict:
    base = {"startDate": start_date, "endDate": end_date, "dataState": "all"}
    jobs = {
        "summary": lambda: _gsc_query(access_token, site_url, {**base, "rowLimit": 1}),
        "daily": lambda: _gsc_query(access_token, site_url, {**base, "dimensions": ["date"], "rowLimit": 1000}),
        "queries": lambda: _gsc_query(access_token, site_url, {**base, "dimensions": ["query"], "rowLimit": 20}),
        "pages": lambda: _gsc_query(access_token, site_url, {**base, "dimensions": ["page"], "rowLimit": 20}),
    }
    reports: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {pool.submit(fn): name for name, fn in jobs.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                reports[name] = future.result()
            except Exception as exc:
                reports[name] = {"_error": str(exc)}
    if reports.get("summary", {}).get("_error"):
        raise RuntimeError(reports["summary"]["_error"])
    summary_rows = _gsc_rows(reports.get("summary", {}), [])
    summary = summary_rows[0] if summary_rows else {"clicks": 0.0, "impressions": 0.0, "ctr": 0.0, "position": 0.0}
    return {
        "summary": summary,
        "daily": _gsc_rows(reports.get("daily", {}), ["date"]),
        "queries": _gsc_rows(reports.get("queries", {}), ["query"]),
        "pages": _gsc_rows(reports.get("pages", {}), ["page"]),
    }


def _data(server: Any, days: int, refresh: bool) -> dict:
    access_token, integration = _valid_access_token(server)
    property_id = _property_id(integration.get("property_id"))
    site_url = str(integration.get("site_url") or "")
    today = date.today()
    start = today - timedelta(days=max(1, days) - 1)
    start_date, end_date = start.isoformat(), today.isoformat()
    cache_key = f"{days}|{property_id}|{site_url}"
    now = int(time.time())
    cached = _load(server, CACHE_KEY, {})
    if (
        not refresh and isinstance(cached, dict) and cached.get("key") == cache_key
        and now - int(cached.get("fetched_at_epoch") or 0) < CACHE_TTL_SECONDS
        and isinstance(cached.get("data"), dict)
    ):
        data = dict(cached["data"])
        data["cached"] = True
        return data

    analytics: dict[str, Any]
    search_console: dict[str, Any]
    if property_id:
        try:
            analytics = _fetch_ga(access_token, property_id, start_date, end_date)
        except Exception as exc:
            analytics = {"error": str(exc)}
    else:
        analytics = {"error": f"Aucune propriété GA4 liée à {MEASUREMENT_ID} n’a été trouvée"}

    if site_url:
        try:
            search_console = _fetch_search_console(access_token, site_url, start_date, end_date)
        except Exception as exc:
            search_console = {"error": str(exc)}
    else:
        search_console = {"error": "Aucune propriété Search Console BININGA n’a été identifiée"}

    data = {
        "ok": not (analytics.get("error") and search_console.get("error")),
        "days": days,
        "range": {"start": start_date, "end": end_date},
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "cached": False,
        "analytics": analytics,
        "search_console": search_console,
        "integration": {
            "email": integration.get("email", ""),
            "property_id": property_id,
            "property_name": integration.get("property_name", ""),
            "measurement_id": integration.get("measurement_id", MEASUREMENT_ID),
            "site_url": site_url,
        },
    }
    if not _save(server, CACHE_KEY, {"key": cache_key, "fetched_at_epoch": now, "data": data}):
        data["cache_warning"] = True
    integration["last_sync_at"] = data["fetched_at"]
    _save(server, INTEGRATION_KEY, integration)
    return data


def _status(server: Any, handler: Any, session: dict) -> dict:
    integration = _load(server, INTEGRATION_KEY, {})
    if not isinstance(integration, dict):
        integration = {}
    return {
        "ok": True,
        "configured": _configured(handler),
        "connected": bool(integration.get("refresh_token")),
        "can_manage": _can_manage(server, session),
        "measurement_id": MEASUREMENT_ID,
        "redirect_uri": _redirect_uri(handler),
        "email": integration.get("email", ""),
        "property_id": _property_id(integration.get("property_id")),
        "property_name": integration.get("property_name", ""),
        "site_url": integration.get("site_url", ""),
        "last_sync_at": integration.get("last_sync_at", ""),
    }


def _authorization_url(server: Any, handler: Any, session: dict) -> str:
    if not _configured(handler):
        raise RuntimeError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET ne sont pas configurés")
    raw_state = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
    now = int(time.time())
    states = _load(server, OAUTH_STATES_KEY, {})
    if not isinstance(states, dict):
        states = {}
    states = {
        key: value for key, value in states.items()
        if isinstance(value, dict) and int(value.get("expires_at") or 0) > now
    }
    states[state_hash] = {"username": session.get("username", ""), "expires_at": now + STATE_TTL_SECONDS}
    if not _save(server, OAUTH_STATES_KEY, states):
        raise RuntimeError("Impossible de préparer la connexion Google")
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(handler),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": raw_state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def _consume_state(server: Any, raw_state: str) -> dict | None:
    if not raw_state:
        return None
    wanted = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
    states = _load(server, OAUTH_STATES_KEY, {})
    if not isinstance(states, dict):
        return None
    record = states.pop(wanted, None)
    _save(server, OAUTH_STATES_KEY, states)
    if not isinstance(record, dict) or int(record.get("expires_at") or 0) < int(time.time()):
        return None
    return record


def _admin_return_url(server: Any, result: str) -> str:
    admin_path = str(getattr(server, "ADMIN_SECRET_PATH", "") or "").strip().strip("/")
    path = f"/{admin_path}" if admin_path else "/static/admin-login-shell.html"
    return path + "?" + urlencode({"google": result})


def _redirect(handler: Any, location: str) -> None:
    handler.send_response(302)
    handler.send_header("Location", location)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()


def _handle_callback(server: Any, handler: Any) -> bool:
    query = parse_qs(urlsplit(str(handler.path)).query)
    if query.get("error"):
        _redirect(handler, _admin_return_url(server, "error"))
        return False
    code = str((query.get("code") or [""])[0])
    raw_state = str((query.get("state") or [""])[0])
    state = _consume_state(server, raw_state)
    if not code or not state:
        _redirect(handler, _admin_return_url(server, "invalid_state"))
        return False
    try:
        token = _token_exchange(code, _redirect_uri(handler))
        access_token = str(token.get("access_token") or "")
        if not access_token:
            raise RuntimeError("Google n’a pas renvoyé de jeton d’accès")
        existing = _load(server, INTEGRATION_KEY, {})
        if not isinstance(existing, dict):
            existing = {}
        refresh_token = str(token.get("refresh_token") or existing.get("refresh_token") or "")
        if not refresh_token:
            raise RuntimeError("Google n’a pas renvoyé de jeton de renouvellement")
        profile = _request_json("https://openidconnect.googleapis.com/v1/userinfo", access_token=access_token)
        analytics = _discover_analytics_property(access_token)
        search_console = _discover_search_console(access_token)
        now = int(time.time())
        integration = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": now + max(60, int(token.get("expires_in") or 3600)),
            "scope": token.get("scope", ""),
            "token_type": token.get("token_type", "Bearer"),
            "email": profile.get("email", ""),
            "property_id": analytics.get("property_id", ""),
            "property_name": analytics.get("property_name", ""),
            "measurement_id": analytics.get("measurement_id", MEASUREMENT_ID),
            "site_url": search_console.get("site_url", ""),
            "search_console_permission": search_console.get("permission_level", ""),
            "connected_by": state.get("username", ""),
            "connected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "last_sync_at": "",
        }
        if not _save(server, INTEGRATION_KEY, integration):
            raise RuntimeError("Impossible de sauvegarder la connexion Google")
        _save(server, CACHE_KEY, {})
        try:
            server.audit_log("GOOGLE_CONNECTED", handler.client_address[0], f"Google connecté par {state.get('username', '?')}")
        except Exception:
            pass
        _redirect(handler, _admin_return_url(server, "connected"))
    except Exception as exc:
        try:
            server.audit_log("GOOGLE_CONNECT_ERROR", handler.client_address[0], str(exc)[:300])
        except Exception:
            pass
        _redirect(handler, _admin_return_url(server, "error"))
    return False


def guard_request(server: Any, handler: Any) -> bool:
    path = urlsplit(str(getattr(handler, "path", ""))).path
    method = str(getattr(handler, "command", "GET")).upper()
    if not path.startswith("/api/google/"):
        return True

    if path == "/api/google/callback" and method == "GET":
        return _handle_callback(server, handler)

    session = _session(server, handler)
    if not session:
        handler._json({"ok": False, "message": "Non autorisé"}, 401)
        return False
    if not _can_read(server, session):
        handler._json({"ok": False, "message": "Droits insuffisants"}, 403)
        return False

    if path == "/api/google/status" and method == "GET":
        handler._json(_status(server, handler, session))
        return False

    if path == "/api/google/data" and method == "GET":
        query = parse_qs(urlsplit(str(handler.path)).query)
        try:
            days = max(1, min(180, int((query.get("days") or ["28"])[0])))
        except Exception:
            days = 28
        refresh = str((query.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
        try:
            payload = _data(server, days, refresh)
            handler._json(payload, 200 if payload.get("ok") else 502)
        except Exception as exc:
            handler._json({"ok": False, "message": str(exc)}, 502)
        return False

    if path == "/api/google/connect" and method == "POST":
        if not _can_manage(server, session):
            handler._json({"ok": False, "message": "Réservé aux propriétaires"}, 403)
            return False
        if not _csrf_valid(server, handler, session):
            handler._json({"ok": False, "message": "Jeton CSRF invalide"}, 403)
            return False
        try:
            url = _authorization_url(server, handler, session)
            try:
                server.audit_log("GOOGLE_CONNECT_START", handler.client_address[0], f"Connexion Google demandée par {session.get('username', '?')}")
            except Exception:
                pass
            handler._json({"ok": True, "authorization_url": url, "redirect_uri": _redirect_uri(handler)})
        except Exception as exc:
            handler._json({"ok": False, "message": str(exc)}, 503)
        return False

    if path == "/api/google/disconnect" and method == "POST":
        if not _can_manage(server, session):
            handler._json({"ok": False, "message": "Réservé aux propriétaires"}, 403)
            return False
        if not _csrf_valid(server, handler, session):
            handler._json({"ok": False, "message": "Jeton CSRF invalide"}, 403)
            return False
        ok = _save(server, INTEGRATION_KEY, {}) and _save(server, CACHE_KEY, {})
        if ok:
            try:
                server.audit_log("GOOGLE_DISCONNECTED", handler.client_address[0], f"Google déconnecté par {session.get('username', '?')}")
            except Exception:
                pass
        handler._json({"ok": ok, "message": "Google déconnecté" if ok else "Déconnexion impossible"}, 200 if ok else 503)
        return False

    handler._json({"ok": False, "message": "Route Google inconnue"}, 404)
    return False
