/* BININGA Admin — case treatment integrity
 * Keeps decisions, appointments and evidence aligned with the server.
 * Loaded as a critical compatibility module after admin-hardening.js.
 */
(() => {
  'use strict';
  if (window.__BININGA_CASE_TREATMENT__) return;
  window.__BININGA_CASE_TREATMENT__ = true;

  const safeJson = (raw, fallback) => {
    try { return JSON.parse(raw || '') ?? fallback; } catch (_) { return fallback; }
  };

  function localList(key) {
    return safeJson(localStorage.getItem(key), []);
  }

  function resolveRecord(storageKey, idOrIdx) {
    const all = localList(storageKey);
    const raw = String(idOrIdx ?? '');
    let decoded = raw;
    try { decoded = decodeURIComponent(raw); } catch (_) {}
    let idx = all.findIndex(x => String(x && (x._id || x.id) || '') === decoded);
    if (idx === -1 && /^\d+$/.test(raw)) {
      const n = Number(raw);
      if (Number.isInteger(n) && n >= 0 && n < all.length) idx = n;
    }
    return { all, idx, item: idx >= 0 ? all[idx] : null };
  }

  async function checkedUpdate(payload, message) {
    const res = await apiFetch('/api/contacts/update', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    });
    let data = {};
    try { data = await res.json(); } catch (_) {}
    if (!res.ok || !data.ok || data.updated === false) {
      throw new Error(data.message || message || `Erreur serveur (${res.status})`);
    }
    return data;
  }

  function rerender(storageKey) {
    try { refreshDashboard(); } catch (_) {}
    if (storageKey === 'bininga_audiences') {
      try { renderAudiences(); } catch (_) {}
      try { renderReclamations(); } catch (_) {}
    } else {
      try { renderContacts(); } catch (_) {}
    }
  }

  window.setDecision = async function setDecisionServerFirst(storageKey, idOrIdx) {
    const ref = resolveRecord(storageKey, idOrIdx);
    if (!ref.item) { showToast('Dossier introuvable.', true); return; }
    const cid = ref.item._id || ref.item.id;
    const sel = document.getElementById('dec-sel-' + idOrIdx);
    const note = document.getElementById('dec-note-' + idOrIdx);
    const decision = sel ? String(sel.value || '').trim() : '';
    const decisionNote = note ? String(note.value || '').trim() : '';
    if (!['favorable', 'defavorable', 'reportee'].includes(decision)) {
      showToast('Sélectionnez une décision valide.', true);
      return;
    }
    try {
      await checkedUpdate({ id: cid, decision, decision_note: decisionNote }, 'La décision n’a pas été enregistrée');
      ref.all[ref.idx].decision = decision;
      ref.all[ref.idx].decision_note = decisionNote;
      ref.all[ref.idx]._decision_at = new Date().toLocaleString('fr-FR');
      localStorage.setItem(storageKey, JSON.stringify(ref.all));
      rerender(storageKey);
      showToast('Décision enregistrée — visible par le demandeur');
    } catch (e) {
      showToast(`Décision non enregistrée : ${e.message}`, true);
    }
  };

  window.setAppointment = async function setAppointmentServerFirst(storageKey, idOrIdx) {
    const ref = resolveRecord(storageKey, idOrIdx);
    if (!ref.item) { showToast('Dossier introuvable.', true); return; }
    const cid = ref.item._id || ref.item.id;
    const dateEl = document.getElementById('apt-date-' + idOrIdx);
    const timeEl = document.getElementById('apt-time-' + idOrIdx);
    const typeEl = document.getElementById('apt-type-' + idOrIdx);
    const placeEl = document.getElementById('apt-place-' + idOrIdx);
    const noteEl = document.getElementById('apt-note-' + idOrIdx);
    const dateVal = dateEl && dateEl.value ? dateEl.value : '';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateVal)) {
      showToast('Choisissez une date de rendez-vous.', true);
      return;
    }
    const [y, mo, d] = dateVal.split('-');
    const timeVal = timeEl && timeEl.value ? timeEl.value : '';
    const display = `${d}/${mo}/${y}${timeVal ? ` à ${timeVal.replace(':', 'h')}` : ''}`;
    const appointment = {
      date: display,
      type: typeEl && typeEl.value === 'telephone' ? 'telephone' : 'presentiel',
      place: placeEl ? String(placeEl.value || '').trim() : '',
      note: noteEl ? String(noteEl.value || '').trim() : '',
    };
    try {
      await checkedUpdate({ id: cid, appointment }, 'Le rendez-vous n’a pas été enregistré');
      ref.all[ref.idx].appointment = appointment;
      ref.all[ref.idx]._appointment_at = new Date().toLocaleString('fr-FR');
      localStorage.setItem(storageKey, JSON.stringify(ref.all));
      rerender(storageKey);
      showToast('Rendez-vous enregistré — visible par le demandeur');
    } catch (e) {
      showToast(`Rendez-vous non enregistré : ${e.message}`, true);
    }
  };

  window.clearAppointment = async function clearAppointmentServerFirst(storageKey, idOrIdx) {
    const ref = resolveRecord(storageKey, idOrIdx);
    if (!ref.item) { showToast('Dossier introuvable.', true); return; }
    const cid = ref.item._id || ref.item.id;
    try {
      await checkedUpdate({ id: cid, appointment: {} }, 'Le rendez-vous n’a pas pu être annulé');
      ref.all[ref.idx].appointment = {};
      localStorage.setItem(storageKey, JSON.stringify(ref.all));
      rerender(storageKey);
      showToast('Rendez-vous annulé');
    } catch (e) {
      showToast(`Rendez-vous non annulé : ${e.message}`, true);
    }
  };

  function installManualLocationRendering() {
    if (window.__BININGA_MANUAL_LOCATION_PATCH__ || typeof window.renderMsgList !== 'function') return;
    window.__BININGA_MANUAL_LOCATION_PATCH__ = true;
    const original = window.renderMsgList;
    window.renderMsgList = function renderMsgListWithManualLocation(containerId, list, storageKey, mode) {
      const result = original.apply(this, arguments);
      const root = document.getElementById(containerId);
      if (!root || !Array.isArray(list)) return result;
      const cards = Array.from(root.querySelectorAll(':scope > .case-card'));
      cards.forEach((card, index) => {
        const row = list[index] || {};
        if ((row.geo_lat && row.geo_lng) || (!row.geo_label && !row.geo_maps_url)) return;
        const main = card.querySelector('.case-main');
        if (!main || main.querySelector('[data-manual-location="1"]')) return;
        let evidence = main.querySelector('.case-evidence');
        if (!evidence) {
          evidence = document.createElement('div');
          evidence.className = 'case-evidence';
          main.appendChild(evidence);
        }
        const location = document.createElement('div');
        location.className = 'case-location';
        location.dataset.manualLocation = '1';
        location.append(document.createTextNode('📍 ' + String(row.geo_label || 'Localisation déclarée')));
        if (row.geo_maps_url) {
          location.append(document.createTextNode(' · '));
          const link = document.createElement('a');
          link.href = String(row.geo_maps_url);
          link.target = '_blank';
          link.rel = 'noopener';
          link.textContent = 'Ouvrir la carte';
          location.appendChild(link);
        }
        evidence.appendChild(location);
      });
      return result;
    };

    const active = document.querySelector('.panel.active');
    const panel = active && active.id ? active.id.replace(/^panel-/, '') : '';
    if (panel === 'audiences') { try { renderAudiences(); } catch (_) {} }
    if (panel === 'reclamations') { try { renderReclamations(); } catch (_) {} }
    if (panel === 'contacts') { try { renderContacts(); } catch (_) {} }
  }

  window.addEventListener('bininga:admin-modules-ready', installManualLocationRendering, { once: true });
  setTimeout(installManualLocationRendering, 1500);
  console.info('[BININGA Admin] Case treatment integrity active');
})();
