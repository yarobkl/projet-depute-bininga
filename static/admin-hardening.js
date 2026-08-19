/* BININGA Admin — emergency data-integrity hardening
 * Loaded after admin.js. Keeps the existing UI intact while making the server
 * authoritative for operational data and preventing false-success destructive actions.
 */
(() => {
  'use strict';

  const CONTENT_PANELS = new Set([
    'hero', 'about', 'stats', 'galerie', 'actus', 'parcours', 'programme',
    'seo', 'engagement', 'cta', 'contact-info', 'footer'
  ]);

  function safeJson(raw, fallback) {
    try { return JSON.parse(raw || '') ?? fallback; } catch (_) { return fallback; }
  }

  function stableMessageId(key, m, idx) {
    if (m && m._id) return String(m._id);
    if (m && m.id) return String(m.id);
    const rawDate = (m && (m._date || m.ts || m.date || m.created_at)) || '';
    const identity = [
      key, rawDate, (m && m.email) || '', (m && m.telephone) || '',
      (m && m.prenom) || '', (m && m.nom) || '', idx
    ].join('|');
    try {
      return `${key}-${btoa(unescape(encodeURIComponent(identity))).replace(/=+$/, '').slice(0, 18)}`;
    } catch (_) {
      return `${key}-${idx}-${String(rawDate).replace(/[^0-9A-Za-z]/g, '').slice(0, 12)}`;
    }
  }

  function normalizeServerMessage(key, m, idx) {
    const rawDate = m._date || m.ts || m.date || m.created_at || '';
    return Object.assign({}, m, {
      _id: stableMessageId(key, m, idx),
      _date: rawDate || new Date().toISOString(),
      _status: m._status || (key === 'bininga_contacts' ? 'non_lu' : 'en_attente')
    });
  }

  function localList(key) {
    return safeJson(localStorage.getItem(key), []);
  }

  function resolveLocalRecord(storageKey, idOrIdx) {
    const all = localList(storageKey);
    const raw = String(idOrIdx ?? '');
    let decoded = raw;
    try { decoded = decodeURIComponent(raw); } catch (_) {}

    let idx = all.findIndex(x => String(x && x._id || '') === decoded);
    if (idx === -1) idx = all.findIndex(x => String(x && x.id || '') === decoded);
    if (idx === -1 && /^\d+$/.test(raw)) {
      const n = Number(raw);
      if (Number.isInteger(n) && n >= 0 && n < all.length) idx = n;
    }
    return { all, idx, item: idx >= 0 ? all[idx] : null };
  }

  async function checkedJson(res, fallbackMessage) {
    let data = {};
    try { data = await res.json(); } catch (_) {}
    if (!res.ok || !data.ok) {
      throw new Error(data.message || fallbackMessage || `Erreur serveur (${res.status})`);
    }
    return data;
  }

  // Server is authoritative. Local storage is only a render/cache layer.
  // Existing local UI metadata is preserved only for records that still exist server-side;
  // local-only orphan records are deliberately not re-added.
  window.syncMessages = async function syncMessagesHardened() {
    const res = await apiFetch('/api/contacts', {
      headers: { 'X-Admin-Token': SESSION_TOKEN }
    });
    const data = await checkedJson(res, 'Impossible de synchroniser les dossiers');

    const mapping = [
      ['bininga_audiences', Array.isArray(data.audiences) ? data.audiences : []],
      ['bininga_contacts', Array.isArray(data.contacts) ? data.contacts : []]
    ];

    for (const [key, serverList] of mapping) {
      const local = localList(key);
      const localMeta = new Map();
      local.forEach((m, idx) => {
        const id = stableMessageId(key, m || {}, idx);
        if (id) localMeta.set(id, m || {});
      });

      const authoritative = serverList.map((m, idx) => {
        const normalized = normalizeServerMessage(key, m || {}, idx);
        const cached = localMeta.get(normalized._id) || {};
        return Object.assign({}, normalized, {
          _status: normalized._status || cached._status,
          _notes: Array.isArray(normalized._notes) ? normalized._notes : (cached._notes || []),
          _pinged: Boolean(normalized._pinged || cached._pinged),
          _pinged_date: normalized._pinged_date || cached._pinged_date || ''
        });
      });

      localStorage.setItem(key, JSON.stringify(authoritative));
    }
    return true;
  };

  // Never report success or erase the browser cache if the server-side deletion failed.
  window.clearAll = async function clearAllHardened(storageKey, panel) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer tous les messages ? Cette action est irréversible.')) return;
    try {
      const res = await apiFetch('/api/contacts/clear', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ type: storageKey })
      });
      await checkedJson(res, 'La suppression serveur a échoué');

      localStorage.removeItem(storageKey);
      await window.syncMessages();
      refreshDashboard();
      if (panel === 'audiences') { renderAudiences(); renderReclamations(); }
      if (panel === 'contacts') renderContacts();
      showToast('Messages supprimés');
    } catch (e) {
      showToast(`Suppression annulée : ${e.message}`, true);
    }
  };

  // Persist first, update the cache/UI only after the server confirms the write.
  window.setStatus = async function setStatusHardened(storageKey, idOrIdx, status) {
    const ref = resolveLocalRecord(storageKey, idOrIdx);
    if (!ref.item) { showToast('Dossier introuvable.', true); return; }
    const cid = ref.item._id || ref.item.id;
    if (!cid) { showToast('Identifiant de dossier invalide.', true); return; }

    try {
      const res = await apiFetch('/api/contacts/update', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ id: cid, status })
      });
      await checkedJson(res, 'La mise à jour du statut a échoué');
      ref.all[ref.idx]._status = status;
      localStorage.setItem(storageKey, JSON.stringify(ref.all));
      refreshDashboard();
      if (storageKey === 'bininga_audiences') { renderAudiences(); renderReclamations(); }
      else renderContacts();
      showToast('Statut mis à jour');
    } catch (e) {
      showToast(`Statut non modifié : ${e.message}`, true);
    }
  };

  window.addNote = async function addNoteHardened(storageKey, idOrIdx) {
    const ta = document.getElementById('note-ta-' + idOrIdx);
    const texte = ta ? ta.value.trim() : '';
    if (!texte) { showToast('Note vide.', true); return; }

    const ref = resolveLocalRecord(storageKey, idOrIdx);
    if (!ref.item) { showToast('Dossier introuvable.', true); return; }
    const cid = ref.item._id || ref.item.id;
    if (!cid) { showToast('Identifiant de dossier invalide.', true); return; }

    const notes = Array.isArray(ref.item._notes) ? ref.item._notes.slice() : [];
    notes.push({
      auteur: SESSION_NOM || SESSION_USERNAME || 'Admin',
      texte,
      date: new Date().toLocaleString('fr-FR')
    });

    try {
      const res = await apiFetch('/api/contacts/update', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ id: cid, notes })
      });
      await checkedJson(res, "L'ajout de la note a échoué");
      ref.all[ref.idx]._notes = notes;
      localStorage.setItem(storageKey, JSON.stringify(ref.all));
      if (storageKey === 'bininga_audiences') { renderAudiences(); renderReclamations(); }
      else renderContacts();
      showToast('Note ajoutée');
    } catch (e) {
      showToast(`Note non enregistrée : ${e.message}`, true);
    }
  };

  window.pingDepute = async function pingDeputeHardened(storageKey, idOrIdx) {
    const ref = resolveLocalRecord(storageKey, idOrIdx);
    if (!ref.item) { showToast('Dossier introuvable.', true); return; }
    const cid = ref.item._id || ref.item.id;
    if (!cid) { showToast('Identifiant de dossier invalide.', true); return; }
    const pingedDate = new Date().toLocaleString('fr-FR');

    try {
      const res = await apiFetch('/api/contacts/update', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ id: cid, pinged: true, pinged_date: pingedDate })
      });
      await checkedJson(res, "L'alerte au Député a échoué");
      ref.all[ref.idx]._pinged = true;
      ref.all[ref.idx]._pinged_date = pingedDate;
      localStorage.setItem(storageKey, JSON.stringify(ref.all));
      refreshDashboard();
      if (storageKey === 'bininga_audiences') { renderAudiences(); renderReclamations(); }
      else renderContacts();
      showToast('Le Député a été alerté sur ce dossier.');
    } catch (e) {
      showToast(`Alerte non envoyée : ${e.message}`, true);
    }
  };

  // The old global listener calls scheduleAutoSave for every admin input. Restrict
  // it to actual website-content panels so CRM/search/security fields cannot save siteData.
  const originalScheduleAutoSave = window.scheduleAutoSave;
  window.scheduleAutoSave = function scheduleAutoSaveScoped() {
    const activePanel = document.querySelector('.panel.active');
    const panelName = activePanel && activePanel.id ? activePanel.id.replace(/^panel-/, '') : '';
    if (!CONTENT_PANELS.has(panelName)) return;
    return originalScheduleAutoSave();
  };

  // Match the documented permission model: superadmin panels are main-admin only.
  window.applyRoleUI = function applyRoleUIHardened(role) {
    updateProfileUI();
    const canEdit = role === 'admin' || role === 'editeur';
    document.querySelectorAll('.role-editeur').forEach(el => { el.style.display = canEdit ? '' : 'none'; });
    document.querySelectorAll('.role-admin').forEach(el => { el.style.display = SESSION_IS_MAIN_ADMIN ? '' : 'none'; });
    document.querySelectorAll('.role-superadmin').forEach(el => { el.style.display = SESSION_IS_MAIN_ADMIN ? '' : 'none'; });
    document.querySelectorAll('.role-ministre').forEach(el => { el.style.display = (role === 'admin' || role === 'ministre') ? '' : 'none'; });
  };

  // Re-apply permissions for an already-restored session, since this file loads last.
  if (typeof SESSION_ROLE !== 'undefined' && SESSION_ROLE) {
    try { window.applyRoleUI(SESSION_ROLE); } catch (_) {}
  }

  console.info('[BININGA Admin] Data-integrity hardening active');
})();
