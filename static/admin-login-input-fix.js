/* BININGA Admin — native mobile login fix v4
 * Keep the existing login UI and let iOS handle input focus natively.
 * No DOM replacement, no event interception, no mutation observer, no app/sidebar mutation.
 */
(() => {
  'use strict';
  if (window.__BININGA_LOGIN_INPUT_FIX_V4__) return;
  window.__BININGA_LOGIN_INPUT_FIX_V4__ = true;

  function prepare() {
    const login = document.getElementById('login');
    if (!login || login.classList.contains('hidden')) return;

    login.removeAttribute('inert');
    login.style.pointerEvents = 'auto';

    ['u', 'p', 'totp'].forEach((id) => {
      const field = document.getElementById(id);
      if (!field) return;
      field.disabled = false;
      field.readOnly = false;
      field.removeAttribute('disabled');
      field.removeAttribute('readonly');
      field.removeAttribute('inert');
      field.tabIndex = 0;
      field.style.pointerEvents = 'auto';
      field.style.touchAction = 'manipulation';
      field.style.webkitUserSelect = 'text';
      field.style.userSelect = 'text';
      field.style.fontSize = '16px';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', prepare, { once: true });
  } else {
    prepare();
  }

  window.addEventListener('pageshow', prepare, { passive: true });
})();
