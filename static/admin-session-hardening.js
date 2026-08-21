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
    try {
      const raw = sessionStorage.getItem(KEY);
      if (!raw) return false;
      const saved = JSON.parse(raw);
      if (!saved || !saved.token || Date.now() > Number(saved.expires_at || 0)) { clearSessionCopies(); return false; }
      _applySession(saved, true); return true;
    } catch (_) { clearSessionCopies(); return false; }
  };

  migrateLegacySession();

  function load(marker, src) {
    if (document.querySelector(`script[${marker}]`)) return;
    const script = document.createElement('script'); script.src = src; script.defer = true; script.setAttribute(marker, '1'); document.head.appendChild(script);
  }
  load('data-bininga-login-rescue','/static/admin-login-rescue.js?v=20260821-login-rescue-1');
  load('data-bininga-dashboard-hardening','/static/admin-dashboard-hardening.js?v=20260819-dashboard-1');
  load('data-bininga-production-hardening','/static/admin-production.js?v=20260820-real-actions-1');
  load('data-bininga-cases-ui','/static/admin-cases.js?v=20260820-cases-1');
  load('data-bininga-system-ux','/static/admin-system-ux.js?v=20260821-system-1');

  console.info('[BININGA Admin] Session storage hardened');
})();
