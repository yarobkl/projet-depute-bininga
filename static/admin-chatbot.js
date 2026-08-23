/* BININGA Admin — DA chatbot control panel
 * Loaded only on the real admin page by passenger_wsgi.
 * It adds a self-contained panel without editing the large legacy admin bundle.
 */
(() => {
  'use strict';

  const SESSION_KEY = 'bininga_session';
  let state = { items: [], editingId: null };

  function session() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || '{}'); }
    catch (_) { return {}; }
  }
  function headers(write = false) {
    const s = session();
    const h = { 'Content-Type': 'application/json' };
    if (s.token) h['X-Admin-Token'] = s.token;
    if (write && s.csrf) h['X-CSRF-Token'] = s.csrf;
    return h;
  }
  async function api(path, opts = {}) {
    const write = (opts.method || 'GET').toUpperCase() !== 'GET';
    const res = await fetch(path, { ...opts, headers: { ...headers(write), ...(opts.headers || {}) } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) throw new Error(data.message || `Erreur ${res.status}`);
    return data;
  }
  function esc(v) {
    return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  }
  function toast(message, ok = true) {
    if (typeof window.showToast === 'function') return window.showToast(message, ok ? 'success' : 'error');
    console[ok ? 'info' : 'error']('[DA Admin]', message);
  }

  function injectNav() {
    if (document.getElementById('bininga-da-nav')) return;
    const editorial = [...document.querySelectorAll('.sb-item')].find(el => /Éditorial IA/i.test(el.textContent || ''));
    if (!editorial) return;
    const item = document.createElement('div');
    item.id = 'bininga-da-nav';
    item.className = 'sb-item role-ministre';
    item.style.display = editorial.style.display || 'none';
    item.innerHTML = '<span class="icon i-message" aria-hidden="true"></span> Assistant DA <span class="sb-badge" id="badge-chatbot" style="display:none"></span>';
    item.onclick = () => {
      if (typeof window.showPanel === 'function') window.showPanel('chatbot-da', item);
      loadAll();
    };
    editorial.insertAdjacentElement('afterend', item);
  }

  function injectPanel() {
    if (document.getElementById('panel-chatbot-da')) return;
    const content = document.querySelector('.content');
    if (!content) return;
    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.id = 'panel-chatbot-da';
    panel.innerHTML = `
      <div class="section-header">
        <div>
          <div class="section-title">Assistant DA</div>
          <div class="section-sub">Sources, fiabilité et questions non résolues</div>
        </div>
        <button class="btn btn-outline" id="da-refresh">Actualiser</button>
      </div>

      <div class="kpi-grid" style="margin-bottom:18px">
        <div class="kpi-card green"><div class="kpi-label">État</div><div class="kpi-val" id="da-status">—</div><div class="kpi-sub">service chatbot</div></div>
        <div class="kpi-card blue"><div class="kpi-label">Sources actives</div><div class="kpi-val" id="da-kb-count">0</div><div class="kpi-sub">base documentaire</div></div>
        <div class="kpi-card gold"><div class="kpi-label">Questions 7 jours</div><div class="kpi-val" id="da-events">0</div><div class="kpi-sub">interactions enregistrées</div></div>
        <div class="kpi-card red"><div class="kpi-label">Sans réponse 7 jours</div><div class="kpi-val" id="da-unanswered">0</div><div class="kpi-sub">à enrichir</div></div>
      </div>

      <div class="card" style="margin-bottom:18px">
        <div class="card-header"><div class="card-title">Configuration DA</div></div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;align-items:end">
          <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="da-enabled"> Assistant activé</label>
          <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="da-external-ai"> IA externe autorisée</label>
          <div><label>Ton</label><select class="field" id="da-tone"><option value="institutionnel">Institutionnel</option><option value="accessible">Accessible</option><option value="concis">Concis</option></select></div>
          <div><label>Messages / minute / visiteur</label><input class="field" id="da-rate" type="number" min="1" max="60" value="10"></div>
        </div>
        <div id="da-providers" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:14px"></div>
        <div style="margin-top:16px;padding:14px;border-radius:12px;background:rgba(184,151,58,.05);border:1px solid rgba(184,151,58,.18)">
          <div style="font-weight:800;font-size:13px;margin-bottom:4px">Clé IA Gemini</div>
          <div id="da-key-status" style="font-size:12px;color:var(--muted,#94a3b8);margin-bottom:10px">Vérification…</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <input class="field" id="da-key-input" type="password" placeholder="Coller la clé (AIza…)" autocomplete="off" style="flex:1;min-width:200px">
            <button class="btn btn-primary" id="da-key-save">Enregistrer la clé</button>
          </div>
          <p style="margin-top:8px;color:var(--muted,#777);font-size:11px">La clé est stockée dans la base de données sécurisée — jamais dans le code, jamais affichée en clair. Active immédiatement pour la Veille Juridique, l'Éditorial IA et l'Assistant.</p>
        </div>
        <div style="margin-top:14px"><button class="btn btn-primary" id="da-save-settings">Enregistrer la configuration</button></div>
        <p style="margin-top:12px;color:var(--muted,#777);font-size:13px">DA privilégie les réponses déterministes et les sources validées. Les données personnelles évidentes sont masquées ou bloquées avant tout envoi vers un fournisseur IA.</p>
      </div>

      <div class="card" style="margin-bottom:18px">
        <div class="card-header" style="display:flex;justify-content:space-between;gap:12px;align-items:center">
          <div class="card-title">Base documentaire DA</div>
          <button class="btn btn-primary" id="da-new">Ajouter une source</button>
        </div>
        <div id="da-knowledge-list"></div>
      </div>

      <div class="card" id="da-editor" style="display:none;margin-bottom:18px">
        <div class="card-header"><div class="card-title" id="da-editor-title">Ajouter une source</div></div>
        <div class="form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div><label>Source</label><input class="field" id="da-source" placeholder="Ex. Journal officiel du Congo"></div>
          <div><label>Catégorie</label><select class="field" id="da-category">
            <option value="general">Général</option><option value="biography">Biographie</option><option value="career">Parcours</option>
            <option value="programme">Programme</option><option value="news">Actualités</option><option value="legal">Juridique</option>
            <option value="journal_officiel">Journal officiel</option><option value="contact">Contact</option><option value="audience">Audience</option>
          </select></div>
          <div style="grid-column:1/-1"><label>Titre</label><input class="field" id="da-title" placeholder="Titre du document ou de la fiche"></div>
          <div style="grid-column:1/-1"><label>Contenu validé</label><textarea class="field" id="da-content" rows="8" placeholder="Texte source ou résumé validé"></textarea></div>
          <div style="grid-column:1/-1"><label>URL source</label><input class="field" id="da-url" placeholder="https://..."></div>
          <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="da-official"> Source officielle</label>
          <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="da-active" checked> Active</label>
        </div>
        <div style="display:flex;gap:10px;margin-top:14px">
          <button class="btn btn-primary" id="da-save">Enregistrer</button>
          <button class="btn btn-outline" id="da-cancel">Annuler</button>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><div class="card-title">Questions sans réponse</div></div>
        <div id="da-unanswered-list"><div class="muted">Aucune donnée chargée.</div></div>
      </div>`;
    content.appendChild(panel);
  }

  function renderStatus(data) {
    const el = id => document.getElementById(id);
    if (el('da-status')) el('da-status').textContent = data.enabled ? 'Actif' : 'Arrêté';
    if (el('da-kb-count')) el('da-kb-count').textContent = data.knowledge || 0;
    if (el('da-events')) el('da-events').textContent = data.events_7d || 0;
    if (el('da-unanswered')) el('da-unanswered').textContent = data.unanswered_7d || 0;
    if (el('da-enabled')) el('da-enabled').checked = !!data.enabled;
    if (el('da-external-ai')) el('da-external-ai').checked = !!data.external_ai_enabled;
    if (el('da-tone')) el('da-tone').value = data.tone || 'institutionnel';
    if (el('da-rate')) el('da-rate').value = data.max_messages_per_minute || 10;
    const p = el('da-providers');
    if (p) {
      p.innerHTML = Object.entries(data.providers || {}).map(([name, active]) =>
        `<span style="padding:7px 11px;border-radius:999px;background:${active ? 'rgba(26,127,71,.12)' : 'rgba(130,130,130,.12)'};font-size:13px;font-weight:700">${esc(name.toUpperCase())} · ${active ? 'configuré' : 'absent'}</span>`
      ).join('');
    }
    const badge = document.getElementById('badge-chatbot');
    if (badge) {
      const n = Number(data.unanswered_7d || 0);
      badge.textContent = n;
      badge.style.display = n ? '' : 'none';
    }
  }

  function renderKnowledge(items) {
    state.items = items || [];
    const box = document.getElementById('da-knowledge-list');
    if (!box) return;
    if (!state.items.length) {
      box.innerHTML = '<div class="empty-state">Aucune source documentaire ajoutée pour le moment.</div>';
      return;
    }
    box.innerHTML = state.items.map(item => `
      <div style="padding:14px 0;border-bottom:1px solid rgba(128,128,128,.18)">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
          <div style="min-width:0">
            <div style="font-weight:800">${esc(item.title)}</div>
            <div style="font-size:12px;color:var(--muted,#777);margin:3px 0 7px">${item.official ? '✓ Officielle · ' : ''}${esc(item.source)} · ${esc(item.category)} · ${item.active ? 'active' : 'inactive'}</div>
            <div style="font-size:13px;line-height:1.45">${esc((item.content || '').slice(0, 260))}${(item.content || '').length > 260 ? '…' : ''}</div>
          </div>
          <div style="display:flex;gap:7px;flex-shrink:0">
            <button class="btn btn-outline da-edit" data-id="${item.id}">Modifier</button>
            <button class="btn btn-outline da-delete" data-id="${item.id}">Supprimer</button>
          </div>
        </div>
      </div>`).join('');
    box.querySelectorAll('.da-edit').forEach(btn => btn.onclick = () => editItem(Number(btn.dataset.id)));
    box.querySelectorAll('.da-delete').forEach(btn => btn.onclick = () => deleteItem(Number(btn.dataset.id)));
  }

  function renderUnanswered(items) {
    const box = document.getElementById('da-unanswered-list');
    if (!box) return;
    if (!items || !items.length) {
      box.innerHTML = '<div class="empty-state">Aucune question non résolue enregistrée.</div>';
      return;
    }
    box.innerHTML = items.map(item => `
      <div style="padding:12px 0;border-bottom:1px solid rgba(128,128,128,.18)">
        <div style="font-size:12px;color:var(--muted,#777)">${esc(item.created_at)} · ${esc(item.intent || 'unknown')}</div>
        <div style="font-weight:650;margin-top:4px">${esc(item.question)}</div>
      </div>`).join('');
  }

  async function saveSettings() {
    try {
      const payload = {
        enabled: document.getElementById('da-enabled').checked,
        external_ai_enabled: document.getElementById('da-external-ai').checked,
        tone: document.getElementById('da-tone').value,
        max_messages_per_minute: Number(document.getElementById('da-rate').value || 10),
      };
      await api('/api/chatbot/settings', { method: 'POST', body: JSON.stringify(payload) });
      toast('Configuration DA enregistrée');
      await loadAll();
    } catch (e) { toast(e.message, false); }
  }

  async function loadAll() {
    try {
      const [status, knowledge, unanswered] = await Promise.all([
        api('/api/chatbot/status'), api('/api/chatbot/knowledge'), api('/api/chatbot/unanswered')
      ]);
      renderStatus(status); renderKnowledge(knowledge.items); renderUnanswered(unanswered.items);
    } catch (e) { toast(e.message, false); }
    loadKeyStatus();
  }

  async function loadKeyStatus() {
    const el = document.getElementById('da-key-status');
    if (!el) return;
    try {
      const st = await api('/api/ia/key');
      el.textContent = st.configured
        ? `✓ Clé configurée (${st.masked})${st.source === 'env' ? ' — via Vercel' : ' — via la base'}`
        : 'Aucune clé enregistrée — le système utilise les flux réels sans IA.';
      el.style.color = st.configured ? '#4ade80' : '';
    } catch (e) {
      el.textContent = 'Statut indisponible : ' + e.message;
    }
  }

  async function saveKey() {
    const input = document.getElementById('da-key-input');
    const key = (input?.value || '').trim();
    if (!key) { toast('Collez la clé avant d’enregistrer', false); return; }
    try {
      const r = await api('/api/ia/key', { method: 'POST', body: JSON.stringify({ key }) });
      input.value = '';
      toast(r.message || 'Clé enregistrée');
      loadKeyStatus();
      loadAll();
    } catch (e) { toast(e.message, false); }
  }

  function openEditor(item = null) {
    state.editingId = item ? item.id : null;
    document.getElementById('da-editor').style.display = '';
    document.getElementById('da-editor-title').textContent = item ? 'Modifier la source' : 'Ajouter une source';
    document.getElementById('da-source').value = item?.source || '';
    document.getElementById('da-category').value = item?.category || 'general';
    document.getElementById('da-title').value = item?.title || '';
    document.getElementById('da-content').value = item?.content || '';
    document.getElementById('da-url').value = item?.source_url || '';
    document.getElementById('da-official').checked = !!item?.official;
    document.getElementById('da-active').checked = item ? !!item.active : true;
    document.getElementById('da-editor').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function editItem(id) { openEditor(state.items.find(x => x.id === id) || null); }
  function closeEditor() { state.editingId = null; document.getElementById('da-editor').style.display = 'none'; }

  async function saveItem() {
    const payload = {
      id: state.editingId,
      source: document.getElementById('da-source').value,
      category: document.getElementById('da-category').value,
      title: document.getElementById('da-title').value,
      content: document.getElementById('da-content').value,
      source_url: document.getElementById('da-url').value,
      official: document.getElementById('da-official').checked,
      active: document.getElementById('da-active').checked,
    };
    try {
      await api('/api/chatbot/knowledge/upsert', { method: 'POST', body: JSON.stringify(payload) });
      toast('Source DA enregistrée'); closeEditor(); await loadAll();
    } catch (e) { toast(e.message, false); }
  }
  async function deleteItem(id) {
    if (!confirm('Supprimer cette source documentaire DA ?')) return;
    try {
      await api('/api/chatbot/knowledge/delete', { method: 'POST', body: JSON.stringify({ id }) });
      toast('Source supprimée'); await loadAll();
    } catch (e) { toast(e.message, false); }
  }

  function bind() {
    document.getElementById('da-refresh').onclick = loadAll;
    document.getElementById('da-key-save').onclick = saveKey;
    document.getElementById('da-save-settings').onclick = saveSettings;
    document.getElementById('da-new').onclick = () => openEditor();
    document.getElementById('da-save').onclick = saveItem;
    document.getElementById('da-cancel').onclick = closeEditor;
  }

  function boot() {
    injectNav(); injectPanel(); bind();
    setTimeout(() => {
      const s = session();
      if (s.token && ['admin', 'ministre'].includes(s.role)) loadAll();
    }, 900);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
