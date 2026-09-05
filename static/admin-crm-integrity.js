/* BININGA Admin — CRM integrity & citizen case history
 *
 * Loaded after the admin shell has painted and before legacy init starts.
 * It intentionally performs no network request at module load.
 *
 * Responsibilities:
 * - PostgreSQL/server remains the only CRM source of truth;
 * - remove the legacy browser PII backup and disable automatic resurrection;
 * - expose every structured citizen dossier on the CRM person card;
 * - preserve evidence, geolocation, decision and appointment context;
 * - avoid mutating the notes array when the legacy detail modal renders.
 */
(() => {
  'use strict';
  if (window.__BININGA_CRM_INTEGRITY__) return;
  window.__BININGA_CRM_INTEGRITY__ = true;

  const LEGACY_BACKUP_KEY = 'bininga_crm_backup';

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function safeUrl(value) {
    const url = String(value || '').trim();
    return /^(https?:\/\/|\/)/i.test(url) ? url : '';
  }

  function sourceLabel(source) {
    const labels = {
      audience: 'Demande d’audience',
      reclamation: 'Réclamation',
      signalement: 'Signalement',
      contact: 'Message',
      newsletter: 'Newsletter',
      livre: 'Commande de livre',
      manuel: 'Manuel',
    };
    return labels[String(source || '').trim()] || String(source || 'Interaction');
  }

  function statusLabel(status) {
    const labels = {
      nouveau: 'Nouveau',
      en_attente: 'En attente',
      non_lu: 'Non lu',
      lu: 'Lu',
      en_cours: 'En cours',
      traite: 'Traité',
      archive: 'Archivé',
    };
    return labels[String(status || '').trim()] || String(status || 'Nouveau');
  }

  function decisionLabel(value) {
    const labels = {
      favorable: 'Favorable',
      defavorable: 'Défavorable',
      reportee: 'Reportée',
    };
    return labels[String(value || '').trim()] || String(value || '');
  }

  function currentContacts() {
    try {
      return typeof _crmContacts !== 'undefined' && Array.isArray(_crmContacts) ? _crmContacts : [];
    } catch (_) {
      return [];
    }
  }

  function removeLegacyBackup() {
    try { localStorage.removeItem(LEGACY_BACKUP_KEY); } catch (_) {}
  }

  // The old Railway-era browser backup contained names, emails, phone numbers,
  // messages and notes in persistent localStorage. PostgreSQL is durable now,
  // so browser storage must never be allowed to resurrect stale/deleted CRM data.
  removeLegacyBackup();
  window._crmSaveBackup = function crmBrowserBackupDisabled() {
    removeLegacyBackup();
    return false;
  };
  window._crmRestoreFromBackup = async function crmBrowserRestoreDisabled() {
    removeLegacyBackup();
    return 0;
  };
  window._crmBackupAllInBackground = async function crmBrowserBackupRefreshDisabled() {
    removeLegacyBackup();
    return false;
  };

  function dossierEvidenceHtml(dossier) {
    const chunks = [];
    const photo = safeUrl(dossier.photo_url);
    if (photo) {
      chunks.push(`
        <a href="${esc(photo)}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:8px;text-decoration:none;color:#d0ad4e">
          <img src="${esc(photo)}" alt="Pièce jointe" loading="lazy" style="width:78px;height:58px;object-fit:cover;border-radius:8px;border:1px solid rgba(255,255,255,.09)">
          <span>Voir la photo</span>
        </a>`);
    }

    const mapsUrl = safeUrl(dossier.geo_maps_url) || (
      dossier.geo_lat && dossier.geo_lng
        ? `https://www.google.com/maps?q=${encodeURIComponent(dossier.geo_lat)},${encodeURIComponent(dossier.geo_lng)}`
        : ''
    );
    if (dossier.geo_label || mapsUrl || (dossier.geo_lat && dossier.geo_lng)) {
      const label = dossier.geo_label || `${dossier.geo_lat || ''}, ${dossier.geo_lng || ''}`;
      chunks.push(`
        <div style="font-size:11px;color:rgba(255,255,255,.58);line-height:1.5">
          <strong style="color:rgba(255,255,255,.72)">Localisation :</strong> ${esc(label)}
          ${mapsUrl ? ` · <a href="${esc(mapsUrl)}" target="_blank" rel="noopener" style="color:#d0ad4e">Ouvrir la carte</a>` : ''}
        </div>`);
    }
    return chunks.length
      ? `<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:10px">${chunks.join('')}</div>`
      : '';
  }

  function dossierHtml(dossier, index) {
    const ap = dossier && typeof dossier.appointment === 'object' ? dossier.appointment : {};
    const submittedName = `${String(dossier.prenom || '').trim()} ${String(dossier.nom || '').trim()}`.trim();
    const submittedContact = [dossier.email, dossier.telephone].filter(Boolean).map(esc).join(' · ');
    const decision = decisionLabel(dossier.decision);
    const tracking = String(dossier.tracking_code || '').trim();

    return `
      <article style="padding:13px 14px;border-radius:11px;border:1px solid rgba(255,255,255,.07);background:rgba(255,255,255,.025);margin-top:10px">
        <div style="display:flex;gap:8px;justify-content:space-between;align-items:flex-start;flex-wrap:wrap">
          <div>
            <div style="font-size:12px;font-weight:800;color:#fff">${esc(sourceLabel(dossier.source))}</div>
            <div style="font-size:10px;color:rgba(255,255,255,.36);margin-top:3px">${esc(dossier.created_at || '')}${tracking ? ` · Suivi ${esc(tracking)}` : ''}</div>
          </div>
          <span style="font-size:10px;padding:4px 8px;border-radius:20px;background:rgba(184,151,58,.09);border:1px solid rgba(184,151,58,.18);color:#d0ad4e">${esc(statusLabel(dossier.statut))}</span>
        </div>
        ${(submittedName || submittedContact) ? `<div style="font-size:11px;color:rgba(255,255,255,.52);margin-top:9px">Soumis par ${esc(submittedName || 'Citoyen')}${submittedContact ? ` · ${submittedContact}` : ''}</div>` : ''}
        ${dossier.sujet ? `<div style="font-size:12px;font-weight:700;color:rgba(255,255,255,.78);margin-top:10px">${esc(dossier.sujet)}</div>` : ''}
        ${dossier.message ? `<div style="font-size:12px;color:rgba(255,255,255,.58);line-height:1.55;white-space:pre-wrap;margin-top:5px">${esc(dossier.message)}</div>` : ''}
        ${decision ? `<div style="margin-top:10px;padding:9px 10px;border-radius:8px;background:rgba(46,204,113,.055);border:1px solid rgba(46,204,113,.12);font-size:11px;color:rgba(255,255,255,.7)"><strong>Décision :</strong> ${esc(decision)}${dossier.decision_note ? `<div style="margin-top:4px">${esc(dossier.decision_note)}</div>` : ''}</div>` : ''}
        ${ap && ap.date ? `<div style="margin-top:10px;padding:9px 10px;border-radius:8px;background:rgba(52,152,219,.055);border:1px solid rgba(52,152,219,.12);font-size:11px;color:rgba(255,255,255,.7)"><strong>Rendez-vous :</strong> ${esc(ap.date)}${ap.type ? ` · ${esc(ap.type === 'telephone' ? 'Téléphonique' : 'Présentiel')}` : ''}${ap.place ? `<div style="margin-top:4px">Lieu : ${esc(ap.place)}</div>` : ''}${ap.note ? `<div style="margin-top:4px">${esc(ap.note)}</div>` : ''}</div>` : ''}
        ${dossierEvidenceHtml(dossier)}
      </article>`;
  }

  function appendDossiersToDetail(contact) {
    const body = document.getElementById('crm-detail-body');
    if (!body || !contact) return;
    body.querySelectorAll('[data-crm-dossiers]').forEach(node => node.remove());

    const dossiers = Array.isArray(contact.dossiers) ? contact.dossiers.filter(d => d && typeof d === 'object') : [];
    const section = document.createElement('section');
    section.dataset.crmDossiers = '1';
    section.style.cssText = 'margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,.07)';
    section.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap">
        <div class="notes-title" style="margin:0">Dossiers & interactions (${dossiers.length})</div>
        <span style="font-size:10px;color:rgba(255,255,255,.32)">Historique serveur PostgreSQL</span>
      </div>
      ${dossiers.length
        ? dossiers.slice().reverse().map(dossierHtml).join('')
        : '<div style="font-size:11px;color:rgba(255,255,255,.28);padding:12px 0">Aucun dossier structuré pour ce contact.</div>'}`;

    // Put operational case history before destructive contact actions.
    const actions = body.lastElementChild;
    if (actions && actions.querySelector && actions.querySelector('.btn-danger')) body.insertBefore(section, actions);
    else body.appendChild(section);
  }

  const originalCrmDetail = window.crmDetail;
  if (typeof originalCrmDetail === 'function') {
    window.crmDetail = function crmDetailWithCases(id) {
      const contact = currentContacts().find(row => String(row && row.id || '') === String(id));
      let originalNotes = null;
      if (contact && Array.isArray(contact.notes)) {
        originalNotes = contact.notes;
        contact.notes = originalNotes.slice();
      }
      try {
        originalCrmDetail(id);
      } finally {
        if (contact && originalNotes) contact.notes = originalNotes;
      }
      appendDossiersToDetail(contact);
    };
  }

  function decorateCrmList() {
    const cards = Array.from(document.querySelectorAll('#crm-list .crm-card'));
    const contacts = currentContacts();
    cards.forEach((card, index) => {
      if (card.querySelector('[data-crm-case-count]')) return;
      const contact = contacts[index];
      const count = Array.isArray(contact && contact.dossiers) ? contact.dossiers.length : 0;
      const meta = card.querySelector('.crm-card-footer > div');
      if (!meta) return;
      const span = document.createElement('span');
      span.dataset.crmCaseCount = '1';
      span.textContent = ` · ${count} dossier${count === 1 ? '' : 's'}`;
      meta.appendChild(span);
    });
  }

  const originalRenderCrmList = window.renderCrmList;
  if (typeof originalRenderCrmList === 'function') {
    window.renderCrmList = function renderCrmListWithCases() {
      const result = originalRenderCrmList.apply(this, arguments);
      decorateCrmList();
      return result;
    };
  }

  console.info('[BININGA Admin] CRM server-first integrity active');
})();
