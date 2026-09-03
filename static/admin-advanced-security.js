/* BININGA Admin — advanced security controls.
 * Session incident response + granular permission editor. Server-side checks
 * remain authoritative; this module only exposes safe controls to Owners.
 */
(() => {
  'use strict';
  if (window.__BININGA_ADVANCED_SECURITY__) return;
  window.__BININGA_ADVANCED_SECURITY__ = true;

  const core = () => window.BiningaAdminCore;
  let permissionMeta = null;

  async function apiJson(path, options = {}) {
    const api = core();
    if (!api) throw new Error('Noyau admin indisponible');
    const response = await api.request(path, { cache: 'no-store', ...options });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || 'Requête refusée');
    return data;
  }

  async function loadPermissionMeta() {
    const api = core();
    if (!api || !api.isMainAdmin()) return null;
    try {
      permissionMeta = await apiJson('/api/auth/users-meta', { headers: { 'X-Admin-Token': api.token() } });
      return permissionMeta;
    } catch (_) { return null; }
  }

  function collectPermissionOverrides() {
    const grants = [], revokes = [];
    document.querySelectorAll('#uf-permissions select[data-permission]').forEach(select => {
      if (select.value === 'grant') grants.push(select.dataset.permission);
      if (select.value === 'revoke') revokes.push(select.dataset.permission);
    });
    return { permission_grants: grants, permission_revokes: revokes };
  }

  async function savePermissionOverrides() {
    const api = core();
    if (!api || !api.isMainAdmin()) return;
    const username = document.getElementById('uf-username')?.value.trim() || '';
    if (!username) {
      if (typeof window.showToast === 'function') window.showToast('Sélectionnez d’abord un collaborateur.', true);
      return;
    }
    const overrides = collectPermissionOverrides();
    const payload = {
      username,
      nom: document.getElementById('uf-nom')?.value.trim() || username,
      email: document.getElementById('uf-email')?.value.trim() || '',
      password: '',
      role: document.getElementById('uf-role')?.value || 'lecteur',
      ...overrides,
    };
    try {
      await apiJson('/api/users/upsert', { method: 'POST', headers: api.authHeaders(), body: JSON.stringify(payload) });
      await loadPermissionMeta();
      if (typeof window.showToast === 'function') window.showToast('Permissions du collaborateur enregistrées.');
    } catch (error) {
      if (typeof window.showToast === 'function') window.showToast(error.message || 'Permissions non enregistrées.', true);
    }
  }

  function ensurePermissionEditor() {
    if (document.getElementById('uf-permissions')) return;
    const role = document.getElementById('uf-role');
    if (!role || !role.parentElement?.parentElement) return;
    const group = document.createElement('div');
    group.id = 'uf-permissions';
    group.style.cssText = 'margin-top:14px;padding:12px;border:1px solid rgba(255,255,255,.09);border-radius:10px';
    group.innerHTML = '<div style="font-size:12px;font-weight:700;margin-bottom:8px">Permissions personnalisées</div><div data-permission-list style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:7px"></div><button type="button" data-save-permissions style="margin-top:12px;border:0;border-radius:8px;background:#bb1232;color:#fff;padding:9px 12px;font-size:11px;font-weight:700;cursor:pointer">Appliquer les permissions</button><div style="font-size:10px;color:rgba(255,255,255,.38);margin-top:8px">Le rôle fournit une base. Un Owner peut autoriser ou refuser explicitement chaque capacité.</div>';
    role.parentElement.parentElement.appendChild(group);
    group.querySelector('[data-save-permissions]')?.addEventListener('click', savePermissionOverrides);
  }

  async function renderPermissions(username = '') {
    ensurePermissionEditor();
    const meta = permissionMeta || await loadPermissionMeta();
    const list = document.querySelector('#uf-permissions [data-permission-list]');
    if (!meta || !list) return;
    const user = (meta.users || []).find(u => u.username === username) || {};
    const role = document.getElementById('uf-role')?.value || 'lecteur';
    const baseline = new Set((meta.role_permissions || {})[role] || []);
    const grants = new Set(user.permission_grants || []);
    const revokes = new Set(user.permission_revokes || []);
    list.innerHTML = (meta.available_permissions || []).map(permission => {
      const inherited = baseline.has(permission);
      const state = revokes.has(permission) ? 'revoke' : grants.has(permission) ? 'grant' : 'inherit';
      return `<label style="font-size:11px;display:flex;align-items:center;gap:6px"><select data-permission="${permission}" style="background:#192231;color:#fff;border:1px solid #344056;border-radius:6px;font-size:10px;padding:3px"><option value="inherit"${state==='inherit'?' selected':''}>Hériter</option><option value="grant"${state==='grant'?' selected':''}>Autoriser</option><option value="revoke"${state==='revoke'?' selected':''}>Refuser</option></select><span>${permission}${inherited?' · rôle':''}</span></label>`;
    }).join('');
  }

  window.BiningaPermissionEditor = Object.freeze({ collect: collectPermissionOverrides, renderPermissions, refresh: loadPermissionMeta, save: savePermissionOverrides });

  function addSessionButton() {
    if (document.getElementById('account-sessions-button')) return;
    const card = document.getElementById('profile-avatar')?.closest('.sb-admin-card');
    if (!card) return;
    const button = document.createElement('button');
    button.id = 'account-sessions-button'; button.type = 'button'; button.textContent = 'Sessions';
    button.style.cssText = 'border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.05);color:#dbe2ec;border-radius:8px;padding:7px 9px;font-size:11px;cursor:pointer';
    button.addEventListener('click', showSessions); card.appendChild(button);
  }

  async function showSessions() {
    const api = core(); if (!api) return;
    try {
      const data = await apiJson('/api/auth/sessions', { headers: { 'X-Admin-Token': api.token() } });
      const text = (data.sessions || []).map(s => `${s.current ? '• Cette session' : '• Session'} — ${s.ip || 'IP inconnue'}${s.user_agent ? ' — ' + s.user_agent.slice(0, 70) : ''}`).join('\n') || 'Aucune session.';
      if (!window.confirm(`${text}\n\nDéconnecter toutes les AUTRES sessions ?`)) return;
      const result = await apiJson('/api/auth/revoke-sessions', { method: 'POST', headers: api.authHeaders(), body: '{}' });
      if (typeof window.showToast === 'function') window.showToast(result.message || 'Sessions révoquées.');
    } catch (error) {
      if (typeof window.showToast === 'function') window.showToast(error.message || 'Impossible de lire les sessions.', true);
    }
  }

  function patchEditUser() {
    if (typeof window.editUser !== 'function' || window.editUser.__permissionWrapped) return;
    const original = window.editUser;
    const wrapped = function(username) {
      const result = original.apply(this, arguments);
      window.setTimeout(() => renderPermissions(username), 0);
      return result;
    };
    wrapped.__permissionWrapped = true; window.editUser = wrapped;
  }

  function install() {
    ensurePermissionEditor(); addSessionButton(); patchEditUser(); loadPermissionMeta();
    document.getElementById('uf-role')?.addEventListener('change', () => renderPermissions(document.getElementById('uf-username')?.value || ''));
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true }); else install();
  window.addEventListener('bininga:admin-modules-ready', install);
})();
