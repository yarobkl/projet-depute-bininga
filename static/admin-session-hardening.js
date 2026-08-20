/* BININGA Admin — session storage hardening
 *
 * The legacy bundle persists bearer + CSRF tokens in localStorage for 72h.
 * Keep the same server-side session duration, but store credentials only in
 * sessionStorage so closing the browser/tab removes the browser copy.
 */
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

  window._clearStoredSession = function clearStoredSessionHardened() {
    clearSessionCopies();
  };

  window._storeSession = function storeSessionHardened(data) {
    const ttlSeconds = Math.max(60, Number(data.session_ttl || 72 * 3600));
    const payload = {
      token: data.token,
      csrf: data.csrf_token || data.csrf || '',
      role: data.role,
      nom: data.nom,
      username: data.username || '',
      is_main_admin: data.is_main_admin || false,
      has_2fa: data.has_2fa || false,
      trusted_ip: data.trusted_ip || false,
      session_duration: data.session_duration || '',
      expires_at: Date.now() + ttlSeconds * 1000
    };

    // Ensure no bearer token survives in persistent browser storage.
    try { localStorage.removeItem(KEY); } catch (_) {}
    sessionStorage.setItem(KEY, JSON.stringify(payload));
    return payload;
  };

  window.restoreStoredSession = function restoreStoredSessionHardened() {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (!raw) return false;
      const saved = JSON.parse(raw);
      if (!saved || !saved.token || Date.now() > Number(saved.expires_at || 0)) {
        clearSessionCopies();
        return false;
      }
      _applySession(saved, true);
      return true;
    } catch (_) {
      clearSessionCopies();
      return false;
    }
  };

  // Move a currently valid legacy session out of localStorage immediately.
  migrateLegacySession();

  // Follow-up hardening stays in isolated files. Loading them here avoids any
  // direct edit of the large legacy admin bundle or document.
  if (!document.querySelector('script[data-bininga-dashboard-hardening]')) {
    const script = document.createElement('script');
    script.src = '/static/admin-dashboard-hardening.js?v=20260819-dashboard-1';
    script.defer = true;
    script.dataset.biningaDashboardHardening = '1';
    document.head.appendChild(script);
  }

  if (!document.querySelector('script[data-bininga-production-hardening]')) {
    const script = document.createElement('script');
    script.src = '/static/admin-production.js?v=20260820-real-actions-1';
    script.defer = true;
    script.dataset.biningaProductionHardening = '1';
    document.head.appendChild(script);
  }

  console.info('[BININGA Admin] Session storage hardened');
})();
