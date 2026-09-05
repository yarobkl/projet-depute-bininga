/* BININGA Admin — instant first paint / mobile Safari fail-safe
 *
 * The authenticated shell must become visible before any API synchronization,
 * notification transport or secondary module can delay/interrupt bootstrap.
 * This file intentionally contains no network request.
 */
(() => {
  'use strict';
  if (window.__BININGA_INSTANT_BOOT__) return;
  window.__BININGA_INSTANT_BOOT__ = true;

  const KEY = 'bininga_session';

  function validSession() {
    try {
      const raw = sessionStorage.getItem(KEY) || localStorage.getItem(KEY);
      if (!raw) return false;
      const saved = JSON.parse(raw);
      return !!(saved && saved.token && Date.now() <= Number(saved.expires_at || 0));
    } catch (_) {
      return false;
    }
  }

  function forceFirstPaint() {
    if (!validSession()) return;
    const login = document.getElementById('login');
    const app = document.getElementById('app');
    if (!app) return;

    if (login) {
      login.classList.add('hidden');
      login.style.setProperty('display', 'none', 'important');
    }
    app.classList.add('visible');
    // Inline fallback: even if a stylesheet/module is still pending, the shell
    // remains paintable. CSS can take over immediately afterwards.
    app.style.setProperty('display', window.innerWidth <= 768 ? 'block' : 'flex', 'important');
    app.style.setProperty('visibility', 'visible', 'important');
    app.style.setProperty('opacity', '1', 'important');
    app.style.setProperty('min-height', '100vh', 'important');
    document.documentElement.dataset.adminFirstPaint = '1';
  }

  // Some embedded/iOS browsers don't expose the Web Notifications API. The
  // legacy notification initializer reads Notification.permission directly;
  // provide a harmless denied shim so that this optional feature can never
  // abort the authenticated UI bootstrap.
  if (!('Notification' in window)) {
    window.Notification = {
      permission: 'denied',
      requestPermission: () => Promise.resolve('denied')
    };
  }

  // admin.js defines init() before this deferred script executes. Delay the
  // expensive dashboard synchronization until after at least one browser paint.
  const originalInit = typeof window.init === 'function' ? window.init : null;
  if (originalInit && !originalInit.__instantPaintWrapped) {
    const wrappedInit = function () {
      forceFirstPaint();
      const run = () => {
        try { originalInit.apply(this, arguments); }
        catch (error) {
          console.error('[BININGA Admin] background init failed', error);
          document.documentElement.dataset.adminInit = 'degraded';
        }
      };
      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(run, 0)));
      } else {
        setTimeout(run, 0);
      }
    };
    wrappedInit.__instantPaintWrapped = true;
    window.init = wrappedInit;
  }

  // Notifications are non-critical. Delay them further so they can never hold
  // the first dashboard paint or keyboard/navigation on mobile Safari.
  const originalNotifications = typeof window.initNotifications === 'function' ? window.initNotifications : null;
  if (originalNotifications && !originalNotifications.__instantPaintWrapped) {
    const wrappedNotifications = function () {
      const args = arguments;
      setTimeout(() => {
        try { originalNotifications.apply(this, args); }
        catch (error) {
          console.warn('[BININGA Admin] notifications unavailable', error);
        }
      }, 1200);
    };
    wrappedNotifications.__instantPaintWrapped = true;
    window.initNotifications = wrappedNotifications;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', forceFirstPaint, { once: true });
  } else {
    forceFirstPaint();
  }

  // A restored page from Safari's back/forward cache must also repaint without
  // waiting for a new server request.
  window.addEventListener('pageshow', event => {
    if (event.persisted) forceFirstPaint();
  }, { passive: true });
})();
