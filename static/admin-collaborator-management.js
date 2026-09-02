/* BININGA Admin — Owner-managed collaborators
 *
 * Owners may create delegated administration accounts with the username,
 * password and role they choose. Recovery email is optional for collaborators.
 * Owner identities themselves are never created from this form.
 */
(() => {
  'use strict';

  if (window.__BININGA_COLLABORATOR_MANAGEMENT__) return;
  window.__BININGA_COLLABORATOR_MANAGEMENT__ = true;

  const core = () => window.BiningaAdminCore;

  function toast(message, error = false) {
    if (typeof window.showToast === 'function') return window.showToast(message, error);
    console[error ? 'error' : 'info']('[BININGA Admin]', message);
  }

  function clarifyCollaboratorForm() {
    const email = document.getElementById('uf-email');
    if (!email) return;
    const group = email.parentElement;
    const label = group?.querySelector('label');
    if (label) label.textContent = 'Adresse email de récupération (optionnelle)';
    email.placeholder = 'Optionnel pour un collaborateur';
    const help = group?.querySelector('div');
    if (help) {
      help.textContent = 'Facultatif pour les collaborateurs. Sans email, le mot de passe pourra être modifié par un Owner depuis cet espace.';
    }
  }

  function installOwnerOnlySubmit() {
    const previous = window.submitUserForm;
    if (previous?.__ownerCollaboratorModel) return;

    const submit = async function submitOwnerManagedCollaborator() {
      const api = core();
      if (!api || !api.isMainAdmin()) {
        toast('Seuls les propriétaires peuvent créer ou modifier un collaborateur.', true);
        return;
      }

      const username = document.getElementById('uf-username')?.value.trim() || '';
      const name = document.getElementById('uf-nom')?.value.trim() || '';
      const email = document.getElementById('uf-email')?.value.trim() || '';
      const password = document.getElementById('uf-password')?.value || '';
      const role = document.getElementById('uf-role')?.value || 'lecteur';

      if (!/^[A-Za-z0-9._@+-]{3,80}$/.test(username)) {
        toast('Identifiant invalide : utilisez au moins 3 caractères.', true);
        return;
      }
      if (!['admin', 'editeur', 'lecteur', 'ministre'].includes(role)) {
        toast('Rôle utilisateur invalide.', true);
        return;
      }

      try {
        const response = await api.request('/api/users/upsert', {
          method: 'POST',
          headers: api.authHeaders(),
          body: JSON.stringify({ username, nom: name, email, password, role }),
          cache: 'no-store',
        });
        const data = await response.json();
        if (!data.ok) {
          toast(data.message || 'Collaborateur non enregistré.', true);
          return;
        }

        toast('Collaborateur enregistré avec les droits sélectionnés.');
        if (typeof window.resetUserForm === 'function') window.resetUserForm();
        if (typeof window.toggleUserForm === 'function') window.toggleUserForm(false);
        if (typeof window.loadUsers === 'function') await window.loadUsers();
      } catch (_) {
        toast('Impossible d’enregistrer le collaborateur.', true);
      }
    };

    submit.__ownerCollaboratorModel = true;
    window.submitUserForm = submit;
  }

  function protectOwnerRows() {
    document.querySelectorAll('.user-item[data-owner="1"]').forEach(item => {
      item.querySelectorAll('button,[onclick]').forEach(control => {
        const text = String(control.textContent || '').toLowerCase();
        const onclick = String(control.getAttribute?.('onclick') || '').toLowerCase();
        if (text.includes('supprim') || text.includes('modifier') || onclick.includes('deleteuser') || onclick.includes('edituser')) {
          control.disabled = true;
          control.setAttribute('aria-disabled', 'true');
          control.title = 'Le compte Owner se gère uniquement via son propre mot de passe.';
          control.style.opacity = '.4';
          control.style.pointerEvents = 'none';
        }
      });
    });
  }

  function wrapLoadUsers() {
    if (typeof window.loadUsers !== 'function' || window.loadUsers.__collabWrapped) return;
    const original = window.loadUsers;
    const wrapped = async function() {
      const result = await original.apply(this, arguments);
      clarifyCollaboratorForm();
      protectOwnerRows();
      return result;
    };
    wrapped.__collabWrapped = true;
    window.loadUsers = wrapped;
  }

  function install() {
    clarifyCollaboratorForm();
    installOwnerOnlySubmit();
    wrapLoadUsers();
    protectOwnerRows();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
})();
