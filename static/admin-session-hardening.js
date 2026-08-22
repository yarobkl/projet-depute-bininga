/* BININGA Admin — session storage hardening
 *
 * Keep credentials in sessionStorage and route unauthenticated visitors through
 * the tiny native login shell. This removes the large admin DOM / overlay stack
 * from the iOS keyboard path while preserving the full admin after login.
 */
(() => {
  'use strict';

  const KEY = 'bininga_session';
  const LOGIN_SHELL = '/static/admin-login-shell.html';

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
    _applySession(saved, true);
    return true;
  };

  migrateLegacySession();

  // Root-cause containment for iOS/Safari/Chrome-in-app: never ask the keyboard
  // to focus fields inside the full admin document. The isolated shell contains
  // only a native <form> and was already verified to accept typing reliably.
  const existingSession = readValidSession();
  if (!existingSession) {
    if (location.pathname !== LOGIN_SHELL) location.replace(LOGIN_SHELL);
    return;
  }

  function load(marker, src) {
    if (document.querySelector(`script[${marker}]`)) return;
    const script = document.createElement('script');
    script.src = src;
    script.defer = true;
    script.setAttribute(marker, '1');
    document.head.appendChild(script);
  }

  // Authenticated-only modules. Keeping login helpers out of the full admin
  // reduces boot work and removes another possible touch/focus interference.
  load('data-bininga-mobile-nav-fix','/static/admin-mobile-nav-fix.js?v=20260822-nav-3');
  load('data-bininga-dashboard-hardening','/static/admin-dashboard-hardening.js?v=20260819-dashboard-1');
  load('data-bininga-production-hardening','/static/admin-production.js?v=20260820-real-actions-1');
  load('data-bininga-cases-ui','/static/admin-cases.js?v=20260820-cases-1');
  load('data-bininga-system-ux','/static/admin-system-ux.js?v=20260821-system-1');

  console.info('[BININGA Admin] Authenticated admin boot hardened');
})();
