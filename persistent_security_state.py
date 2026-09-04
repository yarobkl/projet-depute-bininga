"""Durable security state bridge for BININGA.

Vercel maps ``DATA_DIR`` to ``/tmp/bininga``.  The legacy security engine stores
blocked IPs, attack scores and the attack journal in files under DATA_DIR, which
means those protections can disappear after a cold start.  This module keeps
those files as local fallbacks while making the application's database the
persistent source of truth when it is available.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

_BLOCKED_KEY = "security_blocked_ips"
_SCORES_KEY = "security_attack_scores"
_ATTACKS_KEY = "security_attack_log"
_MAX_ATTACKS = 1000


def _load(server: Any, key: str):
    loader = getattr(server, "_pg_load", None)
    if not callable(loader):
        return None
    try:
        return loader(key)
    except Exception:
        return None


def _save(server: Any, key: str, value) -> bool:
    saver = getattr(server, "_pg_save", None)
    if not callable(saver):
        return False
    try:
        return bool(saver(key, value))
    except Exception:
        return False


def _legacy_call(fn) -> bool:
    if not callable(fn):
        return False
    try:
        fn()
        return True
    except Exception:
        return False


def install(server: Any) -> None:
    if getattr(server, "_bininga_persistent_security_installed", False):
        return

    legacy_load_blocked = getattr(server, "load_blocked_ips", None)
    legacy_save_blocked = getattr(server, "save_blocked_ips", None)
    legacy_load_scores = getattr(server, "load_attack_scores", None)
    legacy_save_scores = getattr(server, "save_attack_scores", None)
    legacy_record_attack = getattr(server, "record_attack", None)
    legacy_load_attacks = getattr(server, "load_attacks", None)

    def load_blocked_ips():
        rows = _load(server, _BLOCKED_KEY)
        if isinstance(rows, list):
            server.BLOCKED_IPS = {str(ip) for ip in rows if str(ip).strip()}
            return

        # Existing non-serverless installations may already have a useful file.
        _legacy_call(legacy_load_blocked)
        current = sorted(str(ip) for ip in getattr(server, "BLOCKED_IPS", set()) if str(ip).strip())
        if current:
            _save(server, _BLOCKED_KEY, current)

    def save_blocked_ips():
        current = sorted(str(ip) for ip in getattr(server, "BLOCKED_IPS", set()) if str(ip).strip())
        durable_ok = _save(server, _BLOCKED_KEY, current)
        file_ok = _legacy_call(legacy_save_blocked)
        if not durable_ok and not file_ok:
            print("[SECURITY] Impossible de persister les IP bloquées", flush=True)

    def load_attack_scores():
        rows = _load(server, _SCORES_KEY)
        if isinstance(rows, dict):
            server.ATTACK_SCORES = rows
            return

        _legacy_call(legacy_load_scores)
        current = getattr(server, "ATTACK_SCORES", {})
        if isinstance(current, dict) and current:
            _save(server, _SCORES_KEY, current)

    def save_attack_scores():
        current = getattr(server, "ATTACK_SCORES", {})
        if not isinstance(current, dict):
            current = {}
        durable_ok = _save(server, _SCORES_KEY, current)
        file_ok = _legacy_call(legacy_save_scores)
        if not durable_ok and not file_ok:
            print("[SECURITY] Impossible de persister les scores d'attaque", flush=True)

    def record_attack(ip: str, event_type: str, score: int, detail: str = ""):
        if callable(legacy_record_attack):
            legacy_record_attack(ip, event_type, score, detail)

        # The legacy implementation only flushes scores every N events.  A
        # serverless invocation may end before that threshold, so force a durable
        # flush after every security event.
        save_attack_scores()

        rows = _load(server, _ATTACKS_KEY)
        if not isinstance(rows, list):
            rows = []
        rows.append({
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ip": str(ip or ""),
            "type": str(event_type or ""),
            "score": int(score or 0),
            "detail": str(detail or "")[:500],
        })
        _save(server, _ATTACKS_KEY, rows[-_MAX_ATTACKS:])

    def load_attacks(limit: int = 200):
        try:
            limit_i = max(1, min(int(limit or 200), _MAX_ATTACKS))
        except Exception:
            limit_i = 200
        rows = _load(server, _ATTACKS_KEY)
        if isinstance(rows, list):
            clean = [row for row in rows if isinstance(row, dict)]
            return list(reversed(clean[-limit_i:]))
        if callable(legacy_load_attacks):
            try:
                return legacy_load_attacks(limit_i)
            except Exception:
                return []
        return []

    server.load_blocked_ips = load_blocked_ips
    server.save_blocked_ips = save_blocked_ips
    server.load_attack_scores = load_attack_scores
    server.save_attack_scores = save_attack_scores
    server.record_attack = record_attack
    server.load_attacks = load_attacks
    server._bininga_persistent_security_installed = True
