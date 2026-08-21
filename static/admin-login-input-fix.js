/* BININGA Admin — mobile login input interaction fix
 * Preserves the existing modern login design. This file only fixes focus/touch
 * handling for the existing #u, #p and #totp fields on mobile browsers.
 */
(() => {
  'use strict';
  if (window.__BININGA_LOGIN_INPUT_FIX__) return;
  window.__BININGA_LOGIN_INPUT_FIX__ = true;

  const FIELD_IDS = ['u', 'p', 'totp'];

  function loginVisible() {
    const login = document.getElementById('login');
    return !!login && !login.classList.contains('hidden');
  }

  function prepareField(field) {
    if (!field) return;
    field.disabled = false;
    field.readOnly = false;
    field.removeAttribute('inert');
    field.tabIndex = 0;
    field.style.pointerEvents = 'auto';
    field.style.touchAction = 'manipulation';
    field.style.webkitUserSelect = 'text';
    field.style.userSelect = 'text';
  }

  function focusField(field) {
    if (!loginVisible() || !field) return;
    prepareField(field);
    try { field.focus({ preventScroll: true }); }
    catch (_) { try { field.focus(); } catch (_) {} }
  }

  function bindField(field) {
    if (!field || field.dataset.biningaLoginInputFix === '1') return;
    field.dataset.biningaLoginInputFix = '1';
    prepareField(field);

    // Capture phase prevents parent mobile/sidebar handlers from swallowing the tap.
    const activate = (event) => {
      if (!loginVisible()) return;
      event.stopPropagation();
      focusField(field);
    };

    field.addEventListener('pointerdown', activate, { capture: true, passive: true });
    field.addEventListener('touchstart', activate, { capture: true, passive: true });
    field.addEventListener('click', activate, { capture: true, passive: true });
  }

  function sync() {
    const login = document.getElementById('login');
    if (!login) return;

    FIELD_IDS.forEach(id => bindField(document.getElementById(id)));

    if (loginVisible()) {
      // Remove only stale sidebar state that can disable interactions on mobile.
      document.body.classList.remove('sidebar-open');
      login.removeAttribute('inert');
      login.style.pointerEvents = 'auto';

      const overlay = document.getElementById('sidebar-overlay');
      if (overlay) overlay.style.pointerEvents = 'none';
    }
  }

  function install() {
    sync();
    const login = document.getElementById('login');
    if (login) {
      new MutationObserver(sync).observe(login, {
        attributes: true,
        attributeFilter: ['class', 'style']
      });
    }
    window.addEventListener('pageshow', sync, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
