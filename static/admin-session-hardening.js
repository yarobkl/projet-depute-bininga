/* BININGA Admin — session storage hardening
 *
 * Keep credentials in sessionStorage and route unauthenticated visitors through
 * the tiny native login shell. Authenticated modules are loaded deterministically
 * to avoid race conditions between core, dashboard, navigation and action handlers.
 */
(() => {
  'use strict';

  const KEY = 'bininga_session';
  const LOGIN_SHELL = '/static/admin-login-shell.html';
  const FIRST_LOGIN = '/static/admin-first-login.html';

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
      session_duration: data.session_duration || '', must_change_password: !!data.must_change_password,
      email: data.email || '', expires_at: Date.now() + ttlSeconds * 1000
    };
    try { localStorage.removeItem(KEY); } catch (_) {}
    sessionStorage.setItem(KEY, JSON.stringify(payload));
    return payload;
  };

  window.restoreStoredSession = function restoreStoredSessionHardened() {
    const saved = readValidSession();
    if (!saved) return false;
    if (saved.must_change_password) {
      if (location.pathname !== FIRST_LOGIN) location.replace(FIRST_LOGIN);
      return false;
    }
    _applySession(saved, true);
    return true;
  };

  migrateLegacySession();

  const existingSession = readValidSession();
  if (!existingSession) {
    if (location.pathname !== LOGIN_SHELL) location.replace(LOGIN_SHELL);
    return;
  }
  if (existingSession.must_change_password) {
    if (location.pathname !== FIRST_LOGIN) location.replace(FIRST_LOGIN);
    return;
  }

  function appendRetryParam(src) {
    const sep = src.includes('?') ? '&' : '?';
    return `${src}${sep}retry=${Date.now()}`;
  }

  function loadScript(marker, src) {
    return new Promise((resolve) => {
      const existing = document.querySelector(`script[${marker}]`);
      if (existing) {
        if (existing.dataset.loaded === '1') return resolve(true);
        const onLoad = () => resolve(true);
        const onError = () => resolve(false);
        existing.addEventListener('load', onLoad, { once: true });
        existing.addEventListener('error', onError, { once: true });
        return;
      }

      const script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.setAttribute(marker, '1');
      script.addEventListener('load', () => {
        script.dataset.loaded = '1';
        resolve(true);
      }, { once: true });
      script.addEventListener('error', () => resolve(false), { once: true });
      document.head.appendChild(script);
    });
  }

  async function loadOne(marker, src) {
    if (await loadScript(marker, src)) return true;

    console.warn('[BININGA Admin] Premier chargement échoué, nouvelle tentative:', src);
    const failed = document.querySelector(`script[${marker}]`);
    if (failed) failed.remove();

    const ok = await loadScript(marker, appendRetryParam(src));
    if (!ok) console.error('[BININGA Admin] Module indisponible après nouvelle tentative:', src);
    return ok;
  }

  const modules = [
    ['data-bininga-admin-core','/static/admin-core.js?v=20260902-architecture-1'],
    ['data-bininga-admin-auth-management','/static/admin-auth-management.js?v=20260902-auth-lifecycle-1'],
    ['data-bininga-collaborator-management','/static/admin-collaborator-management.js?v=20260902-owner-collab-1'],
    ['data-bininga-admin-navigation','/static/admin-navigation.js?v=20260823-nav-desktop-sidebar-3'],
    ['data-bininga-dashboard-hardening','/static/admin-dashboard-hardening.js?v=20260823-dashboard-3'],
    ['data-bininga-production-hardening','/static/admin-production.js?v=20260902-architecture-1'],
    ['data-bininga-cases-ui','/static/admin-cases.js?v=20260823-cases-actionbar-3'],
    ['data-bininga-system-ux','/static/admin-system-ux.js?v=20260821-system-1']
  ];

  (async () => {
    const failed = [];
    for (const [marker, src] of modules) {
      if (!(await loadOne(marker, src))) failed.push(src);
    }

    if (failed.length) {
      document.documentElement.dataset.adminModulesReady = 'degraded';
      document.documentElement.dataset.adminModulesFailed = String(failed.length);
      window.dispatchEvent(new CustomEvent('bininga:admin-modules-degraded', { detail: { failed } }));
      console.error('[BININGA Admin] Démarrage dégradé:', failed);
      return;
    }

    document.documentElement.dataset.adminModulesReady = '1';
    document.documentElement.removeAttribute('data-admin-modules-failed');
    window.dispatchEvent(new CustomEvent('bininga:admin-modules-ready'));
    console.info('[BININGA Admin] Authenticated modules loaded in stable order');
  })();
})();
