/* BININGA Admin — Google Analytics 4 + Search Console
 * Optional/lazy module: it injects its own panel after the authenticated shell is
 * ready and performs no Google/API request until the user opens the panel.
 */
(() => {
  'use strict';
  if (window.__BININGA_GOOGLE_ANALYTICS_UI__) return;
  window.__BININGA_GOOGLE_ANALYTICS_UI__ = true;

  const api = window.BiningaAdminCore;
  if (!api) return;

  const canRead = () => api.isMainAdmin() || ['admin', 'ministre'].includes(api.role());
  if (!canRead()) return;

  let days = 28;
  let status = null;
  let loadedOnce = false;
  let inFlight = null;

  const esc = (value) => String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  const num = (value) => new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(Number(value || 0));
  const dec = (value, digits = 1) => new Intl.NumberFormat('fr-FR', { maximumFractionDigits: digits }).format(Number(value || 0));
  const pct = (value) => `${dec(Number(value || 0) * 100, 1)} %`;
  const duration = (value) => {
    const seconds = Math.max(0, Number(value || 0));
    if (seconds < 60) return `${dec(seconds, 0)} s`;
    return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
  };
  const dateLabel = (value) => {
    const raw = String(value || '');
    const normalized = /^\d{8}$/.test(raw) ? `${raw.slice(0,4)}-${raw.slice(4,6)}-${raw.slice(6,8)}` : raw;
    try { return new Date(`${normalized}T12:00:00`).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }); }
    catch (_) { return raw; }
  };

  function injectStyles() {
    if (document.getElementById('google-analytics-admin-style')) return;
    const style = document.createElement('style');
    style.id = 'google-analytics-admin-style';
    style.textContent = `
      body:has(#panel-google-analytics.active) #admin-actionbar{display:none!important}
      #panel-google-analytics{--ga-blue:#4285f4;--ga-green:#34a853;--ga-yellow:#fbbc04;--ga-red:#ea4335}
      .ga-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:16px}
      .ga-head h2{margin:0;font-size:24px}.ga-head p{margin:6px 0 0;color:rgba(255,255,255,.45);font-size:12px;line-height:1.5}
      .ga-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
      .ga-btn{border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.05);color:#fff;border-radius:9px;padding:9px 13px;font:600 12px inherit;cursor:pointer;min-height:38px}
      .ga-btn.primary{background:rgba(66,133,244,.16);border-color:rgba(66,133,244,.35);color:#8ab4f8}.ga-btn.danger{color:#ff8a80;border-color:rgba(234,67,53,.3);background:rgba(234,67,53,.08)}
      .ga-btn:disabled{opacity:.45;cursor:not-allowed}
      .ga-status{display:flex;align-items:center;gap:10px;padding:13px 14px;border-radius:11px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.025);margin-bottom:14px}
      .ga-dot{width:9px;height:9px;border-radius:50%;background:#64748b;box-shadow:0 0 0 5px rgba(100,116,139,.12);flex:0 0 auto}.ga-dot.ok{background:#34a853;box-shadow:0 0 0 5px rgba(52,168,83,.12)}.ga-dot.warn{background:#fbbc04;box-shadow:0 0 0 5px rgba(251,188,4,.12)}
      .ga-status-main{font-size:13px;font-weight:750}.ga-status-sub{font-size:11px;color:rgba(255,255,255,.42);margin-top:3px;line-height:1.45;word-break:break-word}
      .ga-ranges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}.ga-range{padding:6px 11px;border-radius:999px;background:rgba(255,255,255,.04);color:rgba(255,255,255,.55);border:1px solid rgba(255,255,255,.08);font:700 11px inherit;cursor:pointer}.ga-range.active{background:rgba(66,133,244,.16);color:#8ab4f8;border-color:rgba(66,133,244,.35)}
      .ga-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}.ga-kpi{background:var(--n2,#11151f);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:14px;min-height:88px}.ga-kpi span{display:block;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:rgba(255,255,255,.42)}.ga-kpi strong{display:block;font-size:24px;margin-top:8px;line-height:1}.ga-kpi small{display:block;font-size:10px;color:rgba(255,255,255,.3);margin-top:7px}
      .ga-section-title{font-size:12px;font-weight:850;text-transform:uppercase;letter-spacing:.1em;color:rgba(255,255,255,.48);margin:20px 0 9px}
      .ga-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ga-card{background:var(--n2,#11151f);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:14px;min-width:0}.ga-card h3{font-size:13px;margin:0 0 12px}.ga-table{width:100%;border-collapse:collapse;font-size:11px}.ga-table th{text-align:left;color:rgba(255,255,255,.35);font-size:9px;text-transform:uppercase;letter-spacing:.08em;padding:7px 5px;border-bottom:1px solid rgba(255,255,255,.07)}.ga-table td{padding:8px 5px;border-bottom:1px solid rgba(255,255,255,.045);color:rgba(255,255,255,.72);vertical-align:top}.ga-table td:last-child,.ga-table th:last-child{text-align:right}.ga-table tr:last-child td{border-bottom:0}.ga-label{max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .ga-trend{display:flex;align-items:flex-end;gap:4px;height:92px;padding-top:10px}.ga-trend-col{flex:1;min-width:3px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%;gap:4px}.ga-trend-bar{width:100%;max-width:18px;min-height:2px;border-radius:4px 4px 1px 1px;background:linear-gradient(180deg,#8ab4f8,#4285f4)}.ga-trend-col small{font-size:7px;color:rgba(255,255,255,.28);white-space:nowrap;transform:rotate(-35deg);transform-origin:center}
      .ga-empty{padding:24px 10px;text-align:center;color:rgba(255,255,255,.35);font-size:12px;line-height:1.5}.ga-error{padding:12px;border-radius:9px;background:rgba(234,67,53,.07);border:1px solid rgba(234,67,53,.2);color:#ff8a80;font-size:11px;line-height:1.5}.ga-config{padding:14px;border-radius:10px;background:rgba(251,188,4,.06);border:1px solid rgba(251,188,4,.2);font-size:11px;color:#fdd663;line-height:1.55}.ga-config code{color:#fff;word-break:break-all}
      @media(max-width:768px){.ga-head{flex-direction:column}.ga-actions{width:100%;justify-content:stretch}.ga-actions .ga-btn{flex:1}.ga-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.ga-grid{grid-template-columns:1fr}.ga-card{overflow-x:auto}.ga-head h2{font-size:20px}.ga-label{max-width:190px}}
      @media(max-width:390px){.ga-kpis{grid-template-columns:1fr 1fr}.ga-kpi{padding:12px}.ga-kpi strong{font-size:21px}}
    `;
    document.head.appendChild(style);
  }

  function injectUI() {
    if (document.getElementById('panel-google-analytics')) return;
    injectStyles();

    const nav = document.querySelector('.sb-nav');
    const dashboard = nav && nav.querySelector('.sb-item');
    if (nav && dashboard) {
      const item = document.createElement('div');
      item.className = 'sb-item';
      item.id = 'nav-google-analytics';
      item.innerHTML = '<span class="icon i-chart" aria-hidden="true"></span> Analytics Google';
      item.addEventListener('click', () => window.showPanel('google-analytics', item));
      dashboard.insertAdjacentElement('afterend', item);
    }

    const content = document.querySelector('.content');
    if (!content) return;
    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.id = 'panel-google-analytics';
    panel.innerHTML = `
      <div class="ga-head">
        <div><h2>Analytics Google</h2><p>Google Analytics 4 et Search Console · données en lecture seule</p></div>
        <div class="ga-actions">
          <button class="ga-btn primary" id="ga-connect" type="button" style="display:none">Connecter Google</button>
          <button class="ga-btn" id="ga-sync" type="button" disabled>Synchroniser</button>
          <button class="ga-btn danger" id="ga-disconnect" type="button" style="display:none">Déconnecter</button>
        </div>
      </div>
      <div class="ga-status" id="ga-status"><span class="ga-dot" id="ga-status-dot"></span><div><div class="ga-status-main" id="ga-status-main">Vérification de la connexion…</div><div class="ga-status-sub" id="ga-status-sub">Aucune requête Google n'est lancée tant que ce panneau n'est pas ouvert.</div></div></div>
      <div class="ga-ranges" id="ga-ranges"><button class="ga-range" data-days="7">7 jours</button><button class="ga-range active" data-days="28">28 jours</button><button class="ga-range" data-days="90">90 jours</button></div>
      <div id="ga-config-box"></div>
      <div id="ga-data"><div class="ga-empty">Ouvrez ce panneau pour charger les données Google.</div></div>`;
    content.appendChild(panel);

    window.PANEL_TITLES = window.PANEL_TITLES || {};
    window.PANEL_TITLES['google-analytics'] = 'Analytics Google';

    document.getElementById('ga-connect')?.addEventListener('click', connect);
    document.getElementById('ga-sync')?.addEventListener('click', () => loadData(true));
    document.getElementById('ga-disconnect')?.addEventListener('click', disconnect);
    document.getElementById('ga-ranges')?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-days]');
      if (!button) return;
      days = Number(button.dataset.days || 28);
      document.querySelectorAll('.ga-range').forEach(el => el.classList.toggle('active', el === button));
      if (status?.connected) loadData(false);
    });
  }

  async function jsonRequest(url, options = {}) {
    const response = await api.request(url, { cache: 'no-store', ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.message || `Erreur ${response.status}`);
    return payload;
  }

  function renderStatus(data) {
    status = data;
    const dot = document.getElementById('ga-status-dot');
    const main = document.getElementById('ga-status-main');
    const sub = document.getElementById('ga-status-sub');
    const connectBtn = document.getElementById('ga-connect');
    const disconnectBtn = document.getElementById('ga-disconnect');
    const syncBtn = document.getElementById('ga-sync');
    const configBox = document.getElementById('ga-config-box');
    if (!dot || !main || !sub) return;

    dot.className = `ga-dot ${data.connected ? 'ok' : (data.configured ? 'warn' : '')}`;
    if (!data.configured) {
      main.textContent = 'Connexion Google à configurer';
      sub.textContent = `Le suivi public GA4 ${data.measurement_id || ''} reste actif. Il manque uniquement l'accès lecture des données Google dans l'admin.`;
      configBox.innerHTML = `<div class="ga-config">Ajoutez dans Vercel <code>GOOGLE_CLIENT_ID</code> et <code>GOOGLE_CLIENT_SECRET</code>, puis autorisez exactement ce callback dans Google Cloud :<br><code>${esc(data.redirect_uri || '')}</code></div>`;
    } else if (!data.connected) {
      main.textContent = 'Google n’est pas encore associé';
      sub.textContent = `GA4 détecté côté site : ${data.measurement_id || '—'} · connexion OAuth en lecture seule prête.`;
      configBox.innerHTML = '';
    } else {
      main.textContent = 'Google connecté';
      const parts = [data.email, data.property_name && `GA4 : ${data.property_name}`, data.property_id && `propriété ${data.property_id}`, data.site_url && `Search Console : ${data.site_url}`].filter(Boolean);
      sub.textContent = parts.join(' · ') || 'Connexion active';
      configBox.innerHTML = '';
    }
    if (connectBtn) connectBtn.style.display = data.can_manage && data.configured && !data.connected ? '' : 'none';
    if (disconnectBtn) disconnectBtn.style.display = data.can_manage && data.connected ? '' : 'none';
    if (syncBtn) syncBtn.disabled = !data.connected;
  }

  async function loadStatus() {
    try {
      const data = await jsonRequest('/api/google/status', { headers: api.authHeaders() });
      renderStatus(data);
      if (data.connected && !loadedOnce) await loadData(false);
      else if (!data.connected) document.getElementById('ga-data').innerHTML = '<div class="ga-empty">Connectez un compte Google autorisé à lire la propriété GA4 et Search Console de BININGA.</div>';
      return data;
    } catch (error) {
      const main = document.getElementById('ga-status-main');
      const sub = document.getElementById('ga-status-sub');
      if (main) main.textContent = 'Analytics Google indisponible';
      if (sub) sub.textContent = error.message || 'Impossible de lire le statut Google.';
      throw error;
    }
  }

  function kpi(label, value, hint = '') {
    return `<div class="ga-kpi"><span>${esc(label)}</span><strong>${esc(value)}</strong>${hint ? `<small>${esc(hint)}</small>` : ''}</div>`;
  }

  function table(title, rows, labelKey, metricKey, metricLabel, formatter = num) {
    const body = (rows || []).slice(0, 10).map(row => `<tr><td class="ga-label" title="${esc(row[labelKey])}">${esc(row[labelKey] || '(non défini)')}</td><td>${esc(formatter(row[metricKey]))}</td></tr>`).join('');
    return `<div class="ga-card"><h3>${esc(title)}</h3>${body ? `<table class="ga-table"><thead><tr><th>Dimension</th><th>${esc(metricLabel)}</th></tr></thead><tbody>${body}</tbody></table>` : '<div class="ga-empty">Aucune donnée sur cette période.</div>'}</div>`;
  }

  function trend(rows) {
    const values = (rows || []).slice(-14).map(row => Number(row.activeUsers || 0));
    const max = Math.max(1, ...values);
    if (!values.length) return '<div class="ga-empty">Aucune tendance disponible.</div>';
    return `<div class="ga-trend">${(rows || []).slice(-14).map((row, index) => `<div class="ga-trend-col" title="${esc(dateLabel(row.date))} · ${num(values[index])} utilisateurs"><div class="ga-trend-bar" style="height:${Math.max(4, values[index] / max * 72)}px"></div><small>${esc(dateLabel(row.date))}</small></div>`).join('')}</div>`;
  }

  function renderData(payload) {
    const target = document.getElementById('ga-data');
    if (!target) return;
    const ga = payload.analytics || {};
    const gsc = payload.search_console || {};
    const gs = ga.summary || {};
    const ss = gsc.summary || {};
    const realtime = ga.realtime || {};

    const gaError = ga.error ? `<div class="ga-error">Google Analytics : ${esc(ga.error)}</div>` : '';
    const gscError = gsc.error ? `<div class="ga-error">Search Console : ${esc(gsc.error)}</div>` : '';
    target.innerHTML = `
      <div class="ga-section-title">Google Analytics 4 · ${esc(payload.range?.start || '')} → ${esc(payload.range?.end || '')}</div>
      ${gaError}
      <div class="ga-kpis">
        ${kpi('Utilisateurs actifs', num(gs.activeUsers), `${num(gs.newUsers)} nouveaux`)}
        ${kpi('Sessions', num(gs.sessions), `${num(gs.engagedSessions)} engagées`)}
        ${kpi('Pages vues', num(gs.screenPageViews), `${num(gs.eventCount)} événements`)}
        ${kpi('Temps moyen', duration(gs.averageSessionDuration), `${pct(gs.engagementRate)} engagement`)}
        ${kpi('Temps réel', num(realtime.activeUsers), 'utilisateurs actifs maintenant')}
      </div>
      <div class="ga-grid">
        <div class="ga-card"><h3>Utilisateurs — 14 derniers jours</h3>${trend(ga.daily)}</div>
        ${table('Acquisition', ga.traffic, 'channel', 'sessions', 'Sessions')}
        ${table('Pages les plus vues', ga.pages, 'page', 'screenPageViews', 'Vues')}
        ${table('Pays', ga.countries, 'country', 'activeUsers', 'Utilisateurs')}
        ${table('Appareils', ga.devices, 'device', 'activeUsers', 'Utilisateurs')}
      </div>
      <div class="ga-section-title">Google Search Console</div>
      ${gscError}
      <div class="ga-kpis">
        ${kpi('Clics Google', num(ss.clicks))}
        ${kpi('Impressions', num(ss.impressions))}
        ${kpi('CTR', pct(ss.ctr))}
        ${kpi('Position moyenne', dec(ss.position, 1))}
      </div>
      <div class="ga-grid">
        ${table('Requêtes Google', gsc.queries, 'query', 'clicks', 'Clics')}
        ${table('Pages depuis Google', gsc.pages, 'page', 'clicks', 'Clics')}
      </div>
      <div style="margin-top:12px;font-size:10px;color:rgba(255,255,255,.28)">Dernière synchronisation : ${esc(payload.fetched_at || '—')}${payload.cached ? ' · cache 5 min' : ''}</div>`;
  }

  async function loadData(refresh = false) {
    if (!status?.connected) return;
    if (inFlight) return inFlight;
    const syncBtn = document.getElementById('ga-sync');
    if (syncBtn) { syncBtn.disabled = true; syncBtn.textContent = 'Chargement…'; }
    const target = document.getElementById('ga-data');
    if (target && !loadedOnce) target.innerHTML = '<div class="ga-empty">Chargement des données Google…</div>';
    inFlight = (async () => {
      try {
        const payload = await jsonRequest(`/api/google/data?days=${encodeURIComponent(days)}${refresh ? '&refresh=1' : ''}`, { headers: api.authHeaders() });
        loadedOnce = true;
        renderData(payload);
        if (typeof window.showToast === 'function' && refresh) window.showToast('Données Google synchronisées');
        return payload;
      } catch (error) {
        if (target) target.innerHTML = `<div class="ga-error">${esc(error.message || 'Impossible de charger les données Google.')}</div>`;
        if (typeof window.showToast === 'function' && refresh) window.showToast(error.message || 'Synchronisation Google impossible', true);
        throw error;
      } finally {
        inFlight = null;
        if (syncBtn) { syncBtn.disabled = !status?.connected; syncBtn.textContent = 'Synchroniser'; }
      }
    })();
    return inFlight;
  }

  async function connect() {
    const button = document.getElementById('ga-connect');
    try {
      if (button) { button.disabled = true; button.textContent = 'Ouverture Google…'; }
      const data = await jsonRequest('/api/google/connect', { method: 'POST', headers: api.authHeaders(), body: '{}' });
      if (!data.authorization_url) throw new Error('URL Google manquante');
      location.assign(data.authorization_url);
    } catch (error) {
      if (typeof window.showToast === 'function') window.showToast(error.message || 'Connexion Google impossible', true);
      if (button) { button.disabled = false; button.textContent = 'Connecter Google'; }
    }
  }

  async function disconnect() {
    if (!window.confirm('Déconnecter Google Analytics et Search Console de cet espace admin ? Le suivi public GA4 restera actif.')) return;
    try {
      await jsonRequest('/api/google/disconnect', { method: 'POST', headers: api.authHeaders(), body: '{}' });
      loadedOnce = false;
      status = null;
      document.getElementById('ga-data').innerHTML = '<div class="ga-empty">Google est déconnecté de l’espace admin.</div>';
      await loadStatus();
      if (typeof window.showToast === 'function') window.showToast('Google déconnecté de l’admin');
    } catch (error) {
      if (typeof window.showToast === 'function') window.showToast(error.message || 'Déconnexion impossible', true);
    }
  }

  window.loadGoogleAnalytics = async function loadGoogleAnalytics() {
    injectUI();
    return loadStatus();
  };

  injectUI();
  window.addEventListener('admin:panelchange', (event) => {
    if (event.detail?.name !== 'google-analytics') return;
    void loadStatus().catch(error => console.warn('[BININGA Google] status', error));
  });

  const result = new URLSearchParams(location.search).get('google');
  if (result) {
    history.replaceState(null, '', location.pathname + location.hash);
    setTimeout(() => {
      const item = document.getElementById('nav-google-analytics');
      if (typeof window.showPanel === 'function' && item) window.showPanel('google-analytics', item);
      if (typeof window.showToast === 'function') {
        if (result === 'connected') window.showToast('Google Analytics et Search Console connectés');
        else window.showToast('La connexion Google n’a pas abouti', true);
      }
    }, 50);
  }

  console.info('[BININGA Admin] Google Analytics module ready');
})();
