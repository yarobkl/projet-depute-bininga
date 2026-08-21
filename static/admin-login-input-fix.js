/* BININGA Admin — mobile login input interaction fix v3
 * Keep the current visual design while restoring native keyboard/focus behavior
 * on iOS Safari/Chrome. Fresh input nodes remove stale element listeners left by
 * the legacy admin bundle; touchend focuses synchronously inside the user gesture.
 */
(() => {
  'use strict';
  if (window.__BININGA_LOGIN_INPUT_FIX_V3__) return;
  window.__BININGA_LOGIN_INPUT_FIX_V3__ = true;

  const FIELD_IDS = ['u', 'p', 'totp'];

  function loginVisible() {
    const login = document.getElementById('login');
    if (!login) return false;
    const cs = getComputedStyle(login);
    return !login.classList.contains('hidden') && cs.display !== 'none' && cs.visibility !== 'hidden';
  }

  function prepareField(field) {
    if (!field) return;
    field.disabled = false;
    field.readOnly = false;
    field.removeAttribute('disabled');
    field.removeAttribute('readonly');
    field.removeAttribute('inert');
    field.tabIndex = 0;
    field.style.setProperty('pointer-events', 'auto', 'important');
    field.style.setProperty('touch-action', 'manipulation', 'important');
    field.style.setProperty('-webkit-user-select', 'text', 'important');
    field.style.setProperty('user-select', 'text', 'important');
    field.style.setProperty('position', 'relative', 'important');
    field.style.setProperty('z-index', '2147483647', 'important');
  }

  function nativeFocus(field) {
    if (!field || !loginVisible()) return;
    prepareField(field);
    try { field.focus({ preventScroll: true }); }
    catch (_) { try { field.focus(); } catch (_) {} }
  }

  function replaceWithFreshNativeInput(id) {
    const oldField = document.getElementById(id);
    if (!oldField || oldField.dataset.biningaFreshInput === '1') return oldField;

    const fresh = oldField.cloneNode(true);
    fresh.dataset.biningaFreshInput = '1';
    fresh.disabled = false;
    fresh.readOnly = false;
    fresh.removeAttribute('disabled');
    fresh.removeAttribute('readonly');
    fresh.removeAttribute('inert');
    oldField.replaceWith(fresh);
    prepareField(fresh);

    // Do not swallow pointerdown/touchstart: iOS needs the native event sequence.
    fresh.addEventListener('touchend', (event) => {
      if (!loginVisible()) return;
      // Synchronous focus from a real user gesture reliably opens the iOS keyboard.
      nativeFocus(fresh);
      event.stopPropagation();
    }, { capture: true, passive: true });

    fresh.addEventListener('click', () => nativeFocus(fresh), { passive: true });
    fresh.addEventListener('focus', () => prepareField(fresh), { passive: true });
    return fresh;
  }

  function isolateLoginLayer(login) {
    document.body.classList.remove('sidebar-open');
    login.removeAttribute('inert');
    login.style.setProperty('pointer-events', 'auto', 'important');
    login.style.setProperty('touch-action', 'auto', 'important');
    login.style.setProperty('z-index', '2147483647', 'important');

    const box = login.querySelector('.login-box');
    if (box) {
      box.style.setProperty('position', 'relative', 'important');
      box.style.setProperty('z-index', '2147483647', 'important');
      box.style.setProperty('pointer-events', 'auto', 'important');
      box.style.setProperty('touch-action', 'auto', 'important');
    }

    ['sidebar-overlay', 'sidebar', 'sb-pull', 'app', 'upload-progress-wrap'].forEach(id => {
      const el = document.getElementById(id);
      if (!el || el === login) return;
      el.style.setProperty('pointer-events', 'none', 'important');
    });
  }

  function sync() {
    const login = document.getElementById('login');
    if (!login || !loginVisible()) return;
    isolateLoginLayer(login);
    FIELD_IDS.forEach(replaceWithFreshNativeInput);
  }

  function install() {
    sync();
    const login = document.getElementById('login');
    if (login) {
      new MutationObserver(sync).observe(login, {
        attributes: true,
        childList: true,
        subtree: true,
        attributeFilter: ['class', 'style', 'disabled', 'readonly', 'inert']
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
