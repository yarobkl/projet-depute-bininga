/* BININGA Admin — production action hardening
 * Makes the existing admin controls behave like real authenticated production actions:
 * - authenticated/CSRF same-origin API requests
 * - authenticated CSV/download links
 * - main-admin-only UI enforcement
 * - removal of demo/test controls
 * - mobile login interaction recovery
 * - runtime dead-control detection
 */
(() => {
  'use strict';

  if (window.__BININGA_ADMIN_PRODUCTION__) return;
  window.__BININGA_ADMIN_PRODUCTION__ = true;

  const apiPath = value => {
    try {
      const u = new URL(String(value), window.location.href);
      return u.origin === window.location.origin ? u.pathname : '';
    } catch (_) {
      return '';
    }
  };

  const token = () => {
    try { return typeof SESSION_TOKEN !== 'undefined' ? String(SESSION_TOKEN || '') : ''; }
    catch (_) { return ''; }
  };
  const csrf = () => {
    try { return typeof SESSION_CSRF !== 'undefined' ? String(SESSION_CSRF || '') : ''; }
    catch (_) { return ''; }
  };
  const isMainAdmin = () => {
    try { return typeof SESSION_IS_MAIN_ADMIN !== 'undefined' && !!SESSION_IS_MAIN_ADMIN; }
    catch (_) { return false; }
  };

  function toast(message, error = false) {
    if (typeof window.showToast === 'function') {
      window.showToast(message, error);
      return;
    }
    console[error ? 'error' : 'info']('[BININGA Admin]', message);
  }

  // Enforce authentication + CSRF on every same-origin admin API call. This
  // protects older button handlers that forgot one of the headers while keeping
  // login/public calls functional before a session exists.
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function hardenedFetch(input, init = {}) {
    const requestUrl = typeof input === 'string' || input instanceof URL ? input : input.url;
    const path = apiPath(requestUrl);
    if (!path.startsWith('/api/')) return nativeFetch(input, init);

    const method = String(init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    const currentToken = token();
    const currentCsrf = csrf();
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init.headers || {}).forEach((value, key) => headers.set(key, value));

    if (currentToken && path !== '/api/login') {
      if (!headers.has('X-Admin-Token')) headers.set('X-Admin-Token', currentToken);
      if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && currentCsrf && !headers.has('X-CSRF-Token')) {
        headers.set('X-CSRF-Token', currentCsrf);
      }
    }

    const nextInit = { ...init, headers };
    try {
      const response = await nativeFetch(input, nextInit);
      if (currentToken && response.status === 401) {
        toast('Session expirée. Reconnexion nécessaire.', true);
      } else if (currentToken && response.status === 403) {
        toast('Action refusée : droits insuffisants ou contrôle CSRF.', true);
      } else if (currentToken && response.status === 409) {
        toast('Cette donnée a été modifiée ailleurs. Actualisez avant de recommencer.', true);
      } else if (currentToken && response.status === 503) {
        toast('Service temporairement indisponible. Aucune donnée n’a été perdue.', true);
      }
      return response;
    } catch (error) {
      if (path !== '/api/login') toast('Connexion serveur interrompue. Réessayez.', true);
      throw error;
    }
  };

  function enforceDestructiveControls() {
    document.querySelectorAll('[onclick*="clearAll("], [onclick*="runBackupNow("], [onclick*="manualBlock("]').forEach(el => {
      const allowed = isMainAdmin();
      el.style.display = allowed ? '' : 'none';
      el.setAttribute('aria-hidden', allowed ? 'false' : 'true');
      if (!allowed) el.setAttribute('tabindex', '-1');
      else el.removeAttribute('tabindex');
    });
  }

  function patchRoleUI() {
    if (typeof window.applyRoleUI !== 'function' || window.applyRoleUI.__productionWrapped) return;
    const original = window.applyRoleUI;
    const wrapped = function(role) {
      const result = original.apply(this, arguments);
      document.querySelectorAll('.role-superadmin').forEach(el => {
        el.style.display = role === 'admin' && isMainAdmin() ? '' : 'none';
      });
      enforceDestructiveControls();
      return result;
    };
    wrapped.__productionWrapped = true;
    window.applyRoleUI = wrapped;
  }

  function removeDemoControls() {
    document.querySelectorAll('button[onclick]').forEach(btn => {
      const code = btn.getAttribute('onclick') || '';
      if (code.includes("_addNotif('visit'") && btn.textContent.trim().toLowerCase() === 'test') {
        btn.remove();
      }
    });
  }

  function makeSecurityCopyFactual() {
    const replacements = new Map([
      ['30+ agents IA', 'Analyse comportementale'],
      ['20+ fichiers', 'Données protégées'],
      ['40+ pièges', 'Leurres serveur'],
      ['6 couches de défense opérationnelles', 'Contrôles serveur et protections actives'],
    ]);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const value = node.nodeValue.trim();
      if (replacements.has(value)) node.nodeValue = node.nodeValue.replace(value, replacements.get(value));
    }
  }

  async function authenticatedDownload(url, fallbackName = 'export-bininga') {
    const response = await window.fetch(url, { method: 'GET', headers: { Accept: '*/*' } });
    if (!response.ok) {
      let message = `Export impossible (${response.status})`;
      try {
        const data = await response.clone().json();
        if (data && data.message) message = data.message;
      } catch (_) {}
      throw new Error(message);
    }
    const blob = await response.blob();
    const disposition = response.headers.get('content-disposition') || '';
    const match = disposition.match(/filename\*?=(?:UTF-8''|\")?([^\";]+)/i);
    const filename = match ? decodeURIComponent(match[1].replace(/\"/g, '').trim()) : fallbackName;
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
  }

  function protectApiLinks() {
    document.addEventListener('click', async event => {
      const link = event.target.closest('a[href^="/api/"]');
      if (!link || !token()) return;
      event.preventDefault();
      if (link.dataset.downloading === '1') return;
      link.dataset.downloading = '1';
      const oldText = link.textContent;
      link.textContent = 'Téléchargement…';
      try {
        await authenticatedDownload(link.getAttribute('href'), 'export-bininga.csv');
        toast('Export téléchargé.');
      } catch (error) {
        toast(error.message || 'Export impossible.', true);
      } finally {
        link.dataset.downloading = '0';
        link.textContent = oldText;
      }
    }, true);
  }

  function restoreLoginInteraction() {
    const login = document.getElementById('login');
    if (!login || login.classList.contains('hidden')) return;
    document.body.classList.remove('sidebar-open');
    const overlay = document.getElementById('sidebar-overlay');
    if (overlay) overlay.classList.remove('open', 'active');
    ['u', 'p', 'totp'].forEach(id => {
      const field = document.getElementById(id);
      if (!field) return;
      field.disabled = false;
      field.readOnly = false;
      field.style.pointerEvents = 'auto';
      field.style.touchAction = 'manipulation';
    });
    login.style.pointerEvents = 'auto';
    login.style.zIndex = '2147483647';
  }

  function auditInteractiveControls() {
    const events = ['onclick', 'onchange', 'oninput'];
    const missing = [];
    document.querySelectorAll('[onclick],[onchange],[oninput]').forEach(el => {
      for (const attr of events) {
        const code = el.getAttribute(attr);
        if (!code) continue;
        const match = code.match(/^\s*([A-Za-z_$][\w$]*)\s*\(/);
        if (!match) continue;
        const name = match[1];
        if (typeof window[name] !== 'function') {
          missing.push({ el, name, attr });
          el.dataset.actionUnavailable = name;
          el.setAttribute('aria-disabled', 'true');
          el.title = `Action indisponible : ${name}`;
        }
      }
    });
    if (missing.length) {
      console.error('[BININGA Admin] Contrôles sans fonction:', missing.map(x => x.name));
    } else {
      console.info('[BININGA Admin] Contrôle des actions: OK');
    }
    return missing;
  }

  document.addEventListener('click', event => {
    const dead = event.target.closest('[data-action-unavailable]');
    if (!dead) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    toast(`Action indisponible : ${dead.dataset.actionUnavailable}`, true);
  }, true);

  function install() {
    patchRoleUI();
    removeDemoControls();
    makeSecurityCopyFactual();
    protectApiLinks();
    restoreLoginInteraction();
    enforceDestructiveControls();
    auditInteractiveControls();

    const login = document.getElementById('login');
    if (login) {
      new MutationObserver(() => restoreLoginInteraction()).observe(login, { attributes: true, attributeFilter: ['class'] });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
})();
