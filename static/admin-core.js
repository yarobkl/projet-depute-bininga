/* BININGA Admin — shared runtime core
 *
 * Single source of truth for authenticated admin primitives used by feature
 * modules. The legacy bundle still owns the visual feature handlers while this
 * module centralises session reads, API headers and session-expiry behaviour.
 */
(() => {
  'use strict';

  if (window.BiningaAdminCore) return;

  const SESSION_KEY = 'bininga_session';
  const FIRST_LOGIN = '/static/admin-first-login.html';
  const LOGIN_SHELL = '/static/admin-login-shell.html';

  function token() {
    try { return typeof SESSION_TOKEN !== 'undefined' ? String(SESSION_TOKEN || '') : ''; }
    catch (_) { return ''; }
  }

  function csrf() {
    try { return typeof SESSION_CSRF !== 'undefined' ? String(SESSION_CSRF || '') : ''; }
    catch (_) { return ''; }
  }

  function role() {
    try { return typeof SESSION_ROLE !== 'undefined' ? String(SESSION_ROLE || '') : ''; }
    catch (_) { return ''; }
  }

  function username() {
    try { return typeof SESSION_USERNAME !== 'undefined' ? String(SESSION_USERNAME || '') : ''; }
    catch (_) { return ''; }
  }

  function isMainAdmin() {
    try { return typeof SESSION_IS_MAIN_ADMIN !== 'undefined' && !!SESSION_IS_MAIN_ADMIN; }
    catch (_) { return false; }
  }

  function apiPath(value) {
    try {
      const url = new URL(String(value), window.location.href);
      return url.origin === window.location.origin ? url.pathname : '';
    } catch (_) {
      return '';
    }
  }

  function clearSessionStorage() {
    try { sessionStorage.removeItem(SESSION_KEY); } catch (_) {}
    try { localStorage.removeItem(SESSION_KEY); } catch (_) {}
  }

  function markPasswordChangeRequired() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
      if (saved) {
        saved.must_change_password = true;
        sessionStorage.setItem(SESSION_KEY, JSON.stringify(saved));
      }
    } catch (_) {}
  }

  function authHeaders(extra = {}) {
    const headers = {
      'Content-Type': 'application/json',
      'X-Admin-Token': token(),
      'X-CSRF-Token': csrf(),
      ...extra,
    };
    if (!headers['X-Admin-Token']) delete headers['X-Admin-Token'];
    if (!headers['X-CSRF-Token']) delete headers['X-CSRF-Token'];
    return headers;
  }

  function expireSessionUI() {
    clearSessionStorage();
    try { SESSION_TOKEN = ''; } catch (_) {}
    try { SESSION_CSRF = ''; } catch (_) {}
    try { SESSION_ROLE = ''; } catch (_) {}
    try { SESSION_NOM = ''; } catch (_) {}
    try { SESSION_USERNAME = ''; } catch (_) {}
    try { SESSION_IS_MAIN_ADMIN = false; } catch (_) {}

    if (location.pathname !== LOGIN_SHELL) location.replace(LOGIN_SHELL);
  }

  async function request(url, opts = {}) {
    const response = await window.fetch(url, opts);
    const path = apiPath(url);
    if (response.status === 428 && path.startsWith('/api/')) {
      markPasswordChangeRequired();
      if (location.pathname !== FIRST_LOGIN) window.setTimeout(() => location.replace(FIRST_LOGIN), 50);
      return response;
    }
    if (response.status === 401 && path.startsWith('/api/')) {
      if (typeof window.showToast === 'function') {
        window.showToast('Session expirée — reconnexion…', true);
      }
      window.setTimeout(expireSessionUI, 250);
    }
    return response;
  }

  const core = Object.freeze({
    sessionKey: SESSION_KEY,
    token,
    csrf,
    role,
    username,
    isMainAdmin,
    apiPath,
    authHeaders,
    request,
    clearSessionStorage,
    expireSessionUI,
    markPasswordChangeRequired,
  });

  window.BiningaAdminCore = core;
  window.authHeaders = authHeaders;
  window.apiFetch = request;

  document.documentElement.dataset.adminCoreReady = '1';
})();
