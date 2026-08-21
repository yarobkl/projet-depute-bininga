/* BININGA Admin — session storage hardening + isolated mobile login shell */
(() => {
  'use strict';

  const KEY = 'bininga_session';

  function clearSessionCopies() {
    try { localStorage.removeItem(KEY); } catch (_) {}
    try { sessionStorage.removeItem(KEY); } catch (_) {}
  }

  function migrateLegacySession() {
    try {
      const legacy = localStorage.getItem(KEY);
      if (!legacy) return;
      if (!sessionStorage.getItem(KEY)) sessionStorage.setItem(KEY, legacy);
      localStorage.removeItem(KEY);
    } catch (_) {
      try { localStorage.removeItem(KEY); } catch (_) {}
    }
  }

  function readValidSession() {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (!raw) return null;
      const saved = JSON.parse(raw);
      if (!saved || !saved.token || Date.now() > Number(saved.expires_at || 0)) {
        clearSessionCopies();
        return null;
      }
      return saved;
    } catch (_) {
      clearSessionCopies();
      return null;
    }
  }

  window._clearStoredSession = function clearStoredSessionHardened() { clearSessionCopies(); };

  window._storeSession = function storeSessionHardened(data) {
    const ttlSeconds = Math.max(60, Number(data.session_ttl || 72 * 3600));
    const payload = {
      token: data.token, csrf: data.csrf_token || data.csrf || '', role: data.role,
      nom: data.nom, username: data.username || '', is_main_admin: data.is_main_admin || false,
      has_2fa: data.has_2fa || false, trusted_ip: data.trusted_ip || false,
      session_duration: data.session_duration || '', expires_at: Date.now() + ttlSeconds * 1000
    };
    try { localStorage.removeItem(KEY); } catch (_) {}
    sessionStorage.setItem(KEY, JSON.stringify(payload));
    return payload;
  };

  window.restoreStoredSession = function restoreStoredSessionHardened() {
    const saved = readValidSession();
    if (!saved) return false;
    try { _applySession(saved, true); return true; }
    catch (_) { return false; }
  };

  function load(marker, src) {
    if (document.querySelector(`script[${marker}]`)) return;
    const script = document.createElement('script');
    script.src = src;
    script.defer = true;
    script.setAttribute(marker, '1');
    document.head.appendChild(script);
  }

  function loadAuthenticatedModules() {
    load('data-bininga-dashboard-hardening','/static/admin-dashboard-hardening.js?v=20260819-dashboard-1');
    load('data-bininga-production-hardening','/static/admin-production.js?v=20260820-real-actions-1');
    load('data-bininga-cases-ui','/static/admin-cases.js?v=20260820-cases-1');
    load('data-bininga-system-ux','/static/admin-system-ux.js?v=20260821-system-1');
  }

  function mountIsolatedLogin() {
    if (readValidSession()) return;
    if (document.getElementById('bininga-login-frame')) return;

    const legacyLogin = document.getElementById('login');
    if (legacyLogin) {
      legacyLogin.setAttribute('aria-hidden', 'true');
      legacyLogin.style.setProperty('display', 'none', 'important');
      legacyLogin.style.setProperty('pointer-events', 'none', 'important');
    }

    const app = document.getElementById('app');
    if (app) app.style.setProperty('display', 'none', 'important');

    const frame = document.createElement('iframe');
    frame.id = 'bininga-login-frame';
    frame.src = '/static/admin-login-shell.html?v=20260821-shell-1';
    frame.title = 'Connexion administration BININGA';
    frame.setAttribute('allow', '');
    frame.style.cssText = 'position:fixed;inset:0;width:100%;height:100dvh;border:0;margin:0;padding:0;background:#050505;z-index:2147483647;display:block;';
    document.body.appendChild(frame);
  }

  migrateLegacySession();

  if (readValidSession()) {
    loadAuthenticatedModules();
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountIsolatedLogin, { once: true });
  } else {
    mountIsolatedLogin();
  }

  window.addEventListener('pageshow', () => {
    if (!readValidSession()) mountIsolatedLogin();
  }, { passive: true });

  console.info('[BININGA Admin] Session storage hardened; isolated login shell enabled');
})();
