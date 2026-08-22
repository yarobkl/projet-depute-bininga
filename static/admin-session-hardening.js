/* BININGA Admin — session storage hardening
 *
 * Keep credentials in sessionStorage and route unauthenticated visitors through
 * the tiny native login shell. Authenticated modules are loaded deterministically
 * to avoid race conditions between dashboard, navigation and action handlers.
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

  const existingSession = readValidSession();
  if (!existingSession) {
    if (location.pathname !== LOGIN_SHELL) location.replace(LOGIN_SHELL);
    return;
  }

  function loadOne(marker, src) {
    return new Promise((resolve) => {
      const existing = document.querySelector(`script[${marker}]`);
      if (existing) {
        if (existing.dataset.loaded === '1') return resolve();
        existing.addEventListener('load', resolve, { once: true });
        existing.addEventListener('error', resolve, { once: true });
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.setAttribute(marker, '1');
      script.addEventListener('load', () => {
        script.dataset.loaded = '1';
        resolve();
      }, { once: true });
      script.addEventListener('error', () => {
        console.error('[BININGA Admin] Module non chargé:', src);
        resolve();
      }, { once: true });
      document.head.appendChild(script);
    });
  }

  // Dynamic scripts are async by default in browsers. Loading them one by one
  // prevents intermittent handler overrides and broken mobile navigation.
  const modules = [
    ['data-bininga-mobile-nav-fix','/static/admin-mobile-nav-fix.js?v=20260822-nav-3'],
    ['data-bininga-dashboard-hardening','/static/admin-dashboard-hardening.js?v=20260819-dashboard-1'],
    ['data-bininga-production-hardening','/static/admin-production.js?v=20260820-real-actions-1'],
    ['data-bininga-cases-ui','/static/admin-cases.js?v=20260820-cases-1'],
    ['data-bininga-system-ux','/static/admin-system-ux.js?v=20260821-system-1']
  ];

  (async () => {
    for (const [marker, src] of modules) await loadOne(marker, src);
    document.documentElement.dataset.adminModulesReady = '1';
    window.dispatchEvent(new CustomEvent('bininga:admin-modules-ready'));
    console.info('[BININGA Admin] Authenticated modules loaded in stable order');
  })();
})();
