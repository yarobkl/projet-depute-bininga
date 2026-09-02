/* BININGA Admin — account lifecycle UI
 * Adds recovery email management, first-login status and self-service password
 * changes without growing the legacy admin bundle.
 */
(() => {
  'use strict';

  if (window.__BININGA_ADMIN_AUTH_MANAGEMENT__) return;
  window.__BININGA_ADMIN_AUTH_MANAGEMENT__ = true;

  const core = () => window.BiningaAdminCore;
  const metaByUser = new Map();

  function toast(message, error = false) {
    if (typeof window.showToast === 'function') return window.showToast(message, error);
    console[error ? 'error' : 'info']('[BININGA Admin]', message);
  }

  function injectRecoveryEmailField() {
    if (document.getElementById('uf-email')) return;
    const password = document.getElementById('uf-password');
    if (!password) return;
    const passwordGroup = password.parentElement;
    const group = document.createElement('div');
    group.className = passwordGroup?.className || '';
    group.innerHTML = '<label>Adresse email de récupération</label><input type="email" id="uf-email" placeholder="ex: prenom.nom@example.com" autocomplete="email"><div style="font-size:11px;color:rgba(255,255,255,.35);margin-top:5px">Obligatoire pour la récupération du compte et les emails de réinitialisation.</div>';
    if (passwordGroup?.parentNode) passwordGroup.parentNode.insertBefore(group, passwordGroup);
  }

  async function loadUsersMeta() {
    const api = core();
    if (!api || !api.isMainAdmin()) return;
    try {
      const response = await api.request('/api/auth/users-meta', { headers: { 'X-Admin-Token': api.token() }, cache: 'no-store' });
      const data = await response.json();
      if (!data.ok) return;
      metaByUser.clear();
      (data.users || []).forEach(user => metaByUser.set(user.username, user));
      document.querySelectorAll('.user-item[data-username]').forEach(item => {
        const meta = metaByUser.get(item.dataset.username);
        if (!meta) return;
        item.dataset.email = meta.email || '';
        let detail = item.querySelector('[data-auth-meta]');
        if (!detail) {
          detail = document.createElement('div');
          detail.dataset.authMeta = '1';
          detail.style.cssText = 'font-size:11px;color:rgba(255,255,255,.38);margin-top:3px';
          item.querySelector('.user-info')?.appendChild(detail);
        }
        const state = meta.must_change_password ? ' · Première connexion en attente' : '';
        detail.textContent = (meta.email || 'Email de récupération non renseigné') + state;
      });
    } catch (_) {}
  }

  function patchUserManagement() {
    injectRecoveryEmailField();

    if (typeof window.loadUsers === 'function' && !window.loadUsers.__authWrapped) {
      const original = window.loadUsers;
      const wrapped = async function() {
        const result = await original.apply(this, arguments);
        await loadUsersMeta();
        return result;
      };
      wrapped.__authWrapped = true;
      window.loadUsers = wrapped;
    }

    if (typeof window.editUser === 'function' && !window.editUser.__authWrapped) {
      const original = window.editUser;
      const wrapped = function(username) {
        const result = original.apply(this, arguments);
        const email = document.getElementById('uf-email');
        if (email) email.value = metaByUser.get(username)?.email || '';
        return result;
      };
      wrapped.__authWrapped = true;
      window.editUser = wrapped;
    }

    if (typeof window.resetUserForm === 'function' && !window.resetUserForm.__authWrapped) {
      const original = window.resetUserForm;
      const wrapped = function() {
        const result = original.apply(this, arguments);
        const email = document.getElementById('uf-email');
        if (email) email.value = '';
        return result;
      };
      wrapped.__authWrapped = true;
      window.resetUserForm = wrapped;
    }

    const submit = async function submitUserFormWithRecovery() {
      const api = core();
      if (!api || !api.isMainAdmin()) {
        toast('Action réservée à l’administrateur principal.', true);
        return;
      }
      const username = document.getElementById('uf-username')?.value.trim() || '';
      const email = document.getElementById('uf-email')?.value.trim() || '';
      const payload = {
        username,
        nom: document.getElementById('uf-nom')?.value.trim() || '',
        email,
        password: document.getElementById('uf-password')?.value || '',
        role: document.getElementById('uf-role')?.value || 'lecteur',
      };
      if (!username) return toast('L’identifiant est requis.', true);
      if (!email) return toast('L’adresse email de récupération est obligatoire.', true);
      try {
        const response = await api.request('/api/users/upsert', {
          method: 'POST',
          headers: api.authHeaders(),
          body: JSON.stringify(payload),
          cache: 'no-store',
        });
        const data = await response.json();
        if (!data.ok) return toast(data.message || 'Utilisateur non enregistré.', true);
        toast(payload.password && username !== api.username()
          ? 'Utilisateur enregistré. Le changement de mot de passe sera obligatoire à sa prochaine connexion.'
          : 'Utilisateur enregistré.');
        if (typeof window.resetUserForm === 'function') window.resetUserForm();
        if (typeof window.toggleUserForm === 'function') window.toggleUserForm(false);
        if (typeof window.loadUsers === 'function') await window.loadUsers();
      } catch (_) {
        toast('Impossible d’enregistrer l’utilisateur.', true);
      }
    };
    submit.__authLifecycle = true;
    window.submitUserForm = submit;
  }

  function buildPasswordModal() {
    if (document.getElementById('account-password-modal')) return;
    const modal = document.createElement('div');
    modal.id = 'account-password-modal';
    modal.style.cssText = 'display:none;position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.78);align-items:center;justify-content:center;padding:20px';
    modal.innerHTML = `
      <div style="width:min(440px,100%);background:#111722;border:1px solid #2e3b51;border-radius:16px;padding:24px;box-shadow:0 30px 90px rgba(0,0,0,.55)">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px">
          <div><div style="font-size:17px;font-weight:800">Modifier mon mot de passe</div><div style="font-size:12px;color:rgba(255,255,255,.45);margin-top:3px">Toutes vos sessions seront fermées après la modification.</div></div>
          <button type="button" data-close style="border:0;background:transparent;color:#fff;font-size:22px;cursor:pointer">×</button>
        </div>
        <form id="account-password-form">
          <input id="account-current-password" type="password" autocomplete="current-password" placeholder="Mot de passe actuel" required style="width:100%;height:48px;margin-bottom:10px;border:1px solid #344056;border-radius:10px;background:#192231;color:#fff;padding:0 13px;font-size:15px">
          <input id="account-new-password" type="password" autocomplete="new-password" placeholder="Nouveau mot de passe" required style="width:100%;height:48px;margin-bottom:10px;border:1px solid #344056;border-radius:10px;background:#192231;color:#fff;padding:0 13px;font-size:15px">
          <input id="account-confirm-password" type="password" autocomplete="new-password" placeholder="Confirmer le nouveau mot de passe" required style="width:100%;height:48px;margin-bottom:10px;border:1px solid #344056;border-radius:10px;background:#192231;color:#fff;padding:0 13px;font-size:15px">
          <div style="font-size:11px;color:rgba(255,255,255,.4);line-height:1.45;margin:2px 0 16px">12 caractères minimum et au moins trois catégories : majuscules, minuscules, chiffres, symboles.</div>
          <button id="account-password-submit" type="submit" style="width:100%;height:48px;border:0;border-radius:10px;background:#bb1232;color:#fff;font-weight:800;cursor:pointer">Enregistrer le nouveau mot de passe</button>
          <div id="account-password-error" style="min-height:18px;color:#ff7f8d;font-size:12px;margin-top:10px"></div>
        </form>
      </div>`;
    document.body.appendChild(modal);
    const close = () => { modal.style.display = 'none'; document.getElementById('account-password-form')?.reset(); document.getElementById('account-password-error').textContent = ''; };
    modal.querySelector('[data-close]')?.addEventListener('click', close);
    modal.addEventListener('click', event => { if (event.target === modal) close(); });
    document.getElementById('account-password-form')?.addEventListener('submit', async event => {
      event.preventDefault();
      const api = core();
      if (!api) return;
      const current = document.getElementById('account-current-password').value;
      const next = document.getElementById('account-new-password').value;
      const confirm = document.getElementById('account-confirm-password').value;
      const error = document.getElementById('account-password-error');
      const button = document.getElementById('account-password-submit');
      error.textContent = '';
      if (next !== confirm) { error.textContent = 'Les deux nouveaux mots de passe ne correspondent pas.'; return; }
      button.disabled = true; button.textContent = 'Enregistrement…';
      try {
        const response = await api.request('/api/auth/change-password', {
          method: 'POST', headers: api.authHeaders(), body: JSON.stringify({ current_password: current, new_password: next }), cache: 'no-store'
        });
        const data = await response.json();
        if (!data.ok) { error.textContent = data.message || 'Modification impossible.'; return; }
        api.clearSessionStorage();
        location.replace('/static/admin-login-shell.html?password_changed=1');
      } catch (_) {
        error.textContent = 'Service de sécurité momentanément indisponible.';
      } finally {
        button.disabled = false; button.textContent = 'Enregistrer le nouveau mot de passe';
      }
    });
  }

  function injectPasswordButton() {
    if (document.getElementById('account-change-password')) return;
    const card = document.getElementById('profile-avatar')?.closest('.sb-admin-card');
    if (!card) return;
    const button = document.createElement('button');
    button.id = 'account-change-password';
    button.type = 'button';
    button.textContent = 'Mot de passe';
    button.title = 'Modifier mon mot de passe';
    button.style.cssText = 'margin-left:auto;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.05);color:#dbe2ec;border-radius:8px;padding:7px 9px;font-size:11px;cursor:pointer';
    button.addEventListener('click', () => { buildPasswordModal(); document.getElementById('account-password-modal').style.display = 'flex'; });
    card.appendChild(button);
  }

  function install() {
    patchUserManagement();
    buildPasswordModal();
    injectPasswordButton();
    loadUsersMeta();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
})();
