/* BININGA Admin — canonical authenticated bootstrap
 *
 * This is the only owner of the authenticated admin startup sequence:
 *   session -> visible shell -> critical modules -> legacy init -> optional modules.
 * Feature modules are deliberately loaded after the shell is paintable and may
 * degrade independently without hiding or blocking the dashboard.
 */
(() => {
  'use strict';

  if (window.__BININGA_ADMIN_BOOTSTRAP__) return;
  window.__BININGA_ADMIN_BOOTSTRAP__ = true;

  const KEY = 'bininga_session';
  const LOGIN_SHELL = '/static/admin-login-shell.html';
  const FIRST_LOGIN = '/static/admin-first-login.html';
  const MODULE_TIMEOUT_MS = 10000;

  const state = {
    phase: 'idle',
    started: false,
    backgroundStarted: false,
    fatalShown: false,
  };

  const criticalModules = [
    ['data-bininga-admin-core', '/static/admin-core.js?v=20260905-admin-boot-1'],
    ['data-bininga-admin-navigation', '/static/admin-navigation.js?v=20260905-admin-perf-2'],
    ['data-bininga-admin-integrity', '/static/admin-hardening.js?v=20260819-integrity-1'],
    ['data-bininga-dashboard-priority', '/static/admin-dashboard-priority.js?v=20260905-admin-boot-1'],
  ];

  const optionalModules = [
    ['data-bininga-admin-notifications', '/static/admin-notification-hardening.js?v=20260905-admin-perf-1'],
    ['data-bininga-dashboard-hardening', '/static/admin-dashboard-hardening.js?v=20260905-admin-boot-1'],
    ['data-bininga-admin-auth-management', '/static/admin-auth-management.js?v=20260905-admin-perf-2'],
    ['data-bininga-admin-collaborators', '/static/admin-collaborator-management.js?v=20260902-owner-collab-1'],
    ['data-bininga-production-hardening', '/static/admin-production.js?v=20260902-architecture-1'],
    ['data-bininga-cases-ui', '/static/admin-cases.js?v=20260823-cases-actionbar-3'],
    ['data-bininga-crm-sync', '/static/admin-crm-sync.js?v=20260905-admin-perf-2'],
    ['data-bininga-system-ux', '/static/admin-system-ux.js?v=20260905-admin-perf-2'],
    ['data-bininga-monitoring-serverless', '/static/admin-monitoring-serverless.js?v=20260905-admin-boot-1'],
    ['data-bininga-system-layout', '/static/admin-system-layout.js?v=20260903-system-layout-1'],
    ['data-bininga-backup-ux', '/static/admin-backup-ux.js?v=20260905-admin-perf-2'],
    ['data-bininga-advanced-security', '/static/admin-advanced-security.js?v=20260903-architecture-90'],
    ['data-bininga-admin-chatbot', '/static/admin-chatbot.js?v=20260823-da-keys-2'],
  ];

  function setPhase(phase) {
    state.phase = phase;
    document.documentElement.dataset.adminBootstrapPhase = phase;
  }

  function clearSessionCopies() {
    try { sessionStorage.removeItem(KEY); } catch (_) {}
    try { localStorage.removeItem(KEY); } catch (_) {}
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

  function storeSession(data) {
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
      must_change_password: !!data.must_change_password,
      email: data.email || '',
      expires_at: Date.now() + ttlSeconds * 1000,
    };
    try { localStorage.removeItem(KEY); } catch (_) {}
    sessionStorage.setItem(KEY, JSON.stringify(payload));
    return payload;
  }

  function showFatal(code, error) {
    if (state.fatalShown) return;
    state.fatalShown = true;
    setPhase('failed');
    console.error('[BININGA Admin] critical bootstrap failure', code, error);

    let fallback = document.getElementById('admin-bootstrap-error');
    if (!fallback) {
      fallback = document.createElement('section');
      fallback.id = 'admin-bootstrap-error';
      fallback.setAttribute('role', 'alert');
      fallback.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:grid;place-items:center;padding:24px;background:#05070b;color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';
      fallback.innerHTML = `
        <div style="width:min(100%,520px);padding:28px;border:1px solid #334155;border-radius:16px;background:#111827;box-shadow:0 24px 70px rgba(0,0,0,.5)">
          <div style="font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#f87171">Administration BININGA</div>
          <h1 style="margin:10px 0 8px;font-size:24px;line-height:1.2">Impossible de charger l’administration</h1>
          <p style="margin:0 0 20px;color:#cbd5e1;line-height:1.55">Le tableau de bord n’a pas pu démarrer correctement. Vous pouvez réessayer sans rester sur un écran vide.</p>
          <div style="display:flex;gap:10px;flex-wrap:wrap">
            <button type="button" data-admin-retry style="min-height:44px;padding:0 16px;border:0;border-radius:9px;background:#bb1232;color:#fff;font-weight:800;cursor:pointer">Réessayer</button>
            <button type="button" data-admin-reconnect style="min-height:44px;padding:0 16px;border:1px solid #475569;border-radius:9px;background:#1e293b;color:#fff;font-weight:700;cursor:pointer">Se reconnecter</button>
          </div>
          <code style="display:block;margin-top:18px;color:#94a3b8;font-size:11px">Code : ${String(code || 'ADMIN_BOOT_UNKNOWN').replace(/[^A-Z0-9_-]/gi, '')}</code>
        </div>`;
      document.body.appendChild(fallback);
      fallback.querySelector('[data-admin-retry]').addEventListener('click', () => location.reload());
      fallback.querySelector('[data-admin-reconnect]').addEventListener('click', () => {
        clearSessionCopies();
        location.replace(LOGIN_SHELL);
      });
    }
  }

  function redirectToLogin() {
    clearSessionCopies();
    if (location.pathname !== LOGIN_SHELL) location.replace(LOGIN_SHELL);
  }

  function waitForPaint() {
    return new Promise(resolve => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        resolve();
      };
      setTimeout(finish, 120);
      if (typeof requestAnimationFrame !== 'function') return;
      requestAnimationFrame(() => requestAnimationFrame(finish));
    });
  }

  function loadScript(marker, src) {
    return new Promise(resolve => {
      const existing = document.querySelector(`script[${marker}]`);
      if (existing && existing.dataset.loaded === '1') {
        resolve(true);
        return;
      }

      let settled = false;
      const finish = ok => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        resolve(ok);
      };
      const timeout = setTimeout(() => finish(false), MODULE_TIMEOUT_MS);

      if (existing) {
        existing.addEventListener('load', () => finish(true), { once: true });
        existing.addEventListener('error', () => finish(false), { once: true });
        return;
      }

      const script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.setAttribute(marker, '1');
      script.addEventListener('load', () => {
        script.dataset.loaded = '1';
        finish(true);
      }, { once: true });
      script.addEventListener('error', () => finish(false), { once: true });
      document.head.appendChild(script);
    });
  }

  function retrySrc(src) {
    const separator = src.includes('?') ? '&' : '?';
    return `${src}${separator}retry=${Date.now()}`;
  }

  async function loadOne(marker, src) {
    if (await loadScript(marker, src)) return true;
    const failed = document.querySelector(`script[${marker}]`);
    if (failed) failed.remove();
    return loadScript(marker, retrySrc(src));
  }

  async function loadCriticalModules() {
    const failed = [];
    for (const [marker, src] of criticalModules) {
      if (!(await loadOne(marker, src))) failed.push(src);
    }
    return failed;
  }

  async function loadOptionalModules() {
    const results = await Promise.all(optionalModules.map(async ([marker, src]) => ({
      src,
      ok: await loadOne(marker, src),
    })));
    const failed = results.filter(result => !result.ok).map(result => result.src);
    if (failed.length) {
      document.documentElement.dataset.adminModulesReady = 'degraded';
      document.documentElement.dataset.adminModulesFailed = String(failed.length);
      window.dispatchEvent(new CustomEvent('bininga:admin-modules-degraded', { detail: { failed } }));
    } else {
      document.documentElement.dataset.adminModulesReady = '1';
      document.documentElement.removeAttribute('data-admin-modules-failed');
    }
    window.dispatchEvent(new CustomEvent('bininga:admin-modules-ready', {
      detail: { degraded: failed.length > 0, failed },
    }));
    return failed;
  }

  function startNotificationsSafely() {
    try {
      if (typeof window.initNotifications === 'function') window.initNotifications();
    } catch (error) {
      console.warn('[BININGA Admin] notifications unavailable', error);
      document.documentElement.dataset.adminNotifications = 'degraded';
    }
  }

  async function startWithSession(saved, restored = true) {
    if (!saved || !saved.token || Date.now() > Number(saved.expires_at || 0)) {
      redirectToLogin();
      return false;
    }
    if (saved.must_change_password) {
      if (location.pathname !== FIRST_LOGIN) location.replace(FIRST_LOGIN);
      return false;
    }
    if (state.started) return state.phase !== 'failed';

    state.started = true;
    setPhase('shell');
    try {
      if (typeof window._applySession !== 'function') throw new Error('session shell unavailable');
      window._applySession(saved, restored);
      window.dispatchEvent(new CustomEvent('bininga:admin-shell-ready'));
    } catch (error) {
      showFatal('ADMIN_BOOT_SHELL', error);
      return false;
    }

    await waitForPaint();
    setPhase('critical-modules');
    const criticalFailures = await loadCriticalModules();
    if (criticalFailures.length) {
      console.warn('[BININGA Admin] critical compatibility modules degraded', criticalFailures);
      document.documentElement.dataset.adminCriticalModules = 'degraded';
    }
    if (state.fatalShown) return false;

    setPhase('background');
    window.dispatchEvent(new CustomEvent('bininga:admin-background-starting'));
    try {
      if (typeof window.init !== 'function') throw new Error('admin init unavailable');
      state.backgroundStarted = true;
      const result = window.init();
      if (result && typeof result.catch === 'function') {
        result.catch(error => showFatal('ADMIN_BOOT_INIT_ASYNC', error));
      }
    } catch (error) {
      showFatal('ADMIN_BOOT_INIT', error);
      return false;
    }

    setPhase('ready');
    document.documentElement.dataset.adminReady = '1';
    window.dispatchEvent(new CustomEvent('bininga:admin-ready'));

    loadOptionalModules()
      .then(() => setTimeout(startNotificationsSafely, 300))
      .catch(error => {
        console.warn('[BININGA Admin] optional modules unavailable', error);
        document.documentElement.dataset.adminModulesReady = 'degraded';
      });
    return true;
  }

  function start() {
    migrateLegacySession();
    const saved = readValidSession();
    if (!saved) {
      redirectToLogin();
      return;
    }
    void startWithSession(saved, true);
  }

  window._clearStoredSession = clearSessionCopies;
  window._storeSession = storeSession;
  window.restoreStoredSession = function restoreStoredSessionFromBootstrap() {
    const saved = readValidSession();
    if (!saved) return false;
    void startWithSession(saved, true);
    return true;
  };
  window.BiningaAdminBootstrap = Object.freeze({
    start,
    startWithSession,
    readValidSession,
    showFatal,
    state,
  });

  window.addEventListener('error', event => {
    if (event.target && /^(SCRIPT|LINK|IMG)$/.test(event.target.tagName || '')) return;
    if (state.phase !== 'ready' && state.phase !== 'failed') {
      showFatal('ADMIN_BOOT_RUNTIME', event.error || event.message);
    }
  });
  window.addEventListener('unhandledrejection', event => {
    if (state.phase !== 'ready' && state.phase !== 'failed') {
      showFatal('ADMIN_BOOT_PROMISE', event.reason);
    }
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    const saved = readValidSession();
    if (!saved) {
      redirectToLogin();
      return;
    }
    try {
      window._applySession(saved, true);
      window.dispatchEvent(new CustomEvent('bininga:admin-shell-ready'));
    } catch (error) {
      showFatal('ADMIN_BOOT_BFCACHE', error);
    }
  }, { passive: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
