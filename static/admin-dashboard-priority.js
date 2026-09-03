/* BININGA Admin — affichage prioritaire du dashboard après connexion */
(() => {
  'use strict';

  const q = (s, r = document) => r.querySelector(s);
  const n = v => Number(v || 0);

  function ensureShell() {
    const panel = q('#panel-dashboard');
    if (!panel) return null;
    let suite = q('#dashboard-analytics-suite');
    if (!suite) {
      suite = document.createElement('div');
      suite.id = 'dashboard-analytics-suite';
      suite.className = 'analytics-suite';
      const anchor = q('.dashboard-bottom-grid', panel);
      if (anchor) anchor.before(suite);
      else panel.prepend(suite);
    }
    if (!suite.dataset.priorityReady) {
      suite.dataset.priorityReady = '1';
      suite.innerHTML = `
        <section class="analytics-card" aria-busy="true">
          <div class="analytics-head">
            <div>
              <div class="analytics-title">Activité opérationnelle</div>
              <div class="analytics-sub">Chaque barre ouvre les dossiers correspondants.</div>
            </div>
            <span class="ops-count">Chargement…</span>
          </div>
          <div class="bar-chart">
            ${['Attente','En cours','Traitées','Réclam.','Messages'].map(label => `
              <div class="bar-col">
                <div class="bar-value">—</div>
                <div class="bar-track"><div class="bar-fill" style="height:3%"></div></div>
                <div class="bar-label">${label}</div>
              </div>`).join('')}
          </div>
        </section>
        <section class="analytics-card" aria-busy="true">
          <div class="analytics-head">
            <div>
              <div class="analytics-title">Audience numérique</div>
              <div class="analytics-sub">Fréquentation et lecture du programme.</div>
            </div>
          </div>
          <div class="ratio-ring" style="--ring:0%"><strong>—</strong><small>lecture / visite</small></div>
          <div class="mini-metrics">
            <div class="mini-metric"><strong>—</strong><span>Visiteurs</span></div>
            <div class="mini-metric"><strong>—</strong><span>Lectures programme</span></div>
          </div>
        </section>`;
    }
    return suite;
  }

  function navigate(panel, status) {
    const navItem = [...document.querySelectorAll('.sb-item')].find(el =>
      (el.getAttribute('onclick') || '').includes(`showPanel('${panel}'`)
    );
    if (navItem) navItem.click();
    else if (typeof window.showPanel === 'function') window.showPanel(panel, null);
    if (status) {
      setTimeout(() => {
        const p = q(`#panel-${panel}`);
        if (!p) return;
        const tab = [...p.querySelectorAll('.tab')].find(el =>
          (el.getAttribute('onclick') || '').includes(`'${status}'`)
        );
        if (tab) tab.click();
      }, 30);
    }
  }

  function render(stats, visitorsOverride) {
    const suite = ensureShell();
    if (!suite) return;
    const visitors = visitorsOverride || stats.visitors || {};
    const rows = [
      ['Attente', n(stats.aud_wait), '#f39c12', 'audiences', 'en_attente'],
      ['En cours', n(stats.aud_progress), '#3498db', 'audiences', 'en_cours'],
      ['Traitées', n(stats.aud_done), '#2ecc71', 'audiences', 'traite'],
      ['Réclam.', n(stats.recl_wait ?? stats.recl_total), '#C8102E', 'reclamations', 'en_attente'],
      ['Messages', n(stats.ct_total), '#B8973A', 'contacts', 'all'],
    ];
    const max = Math.max(1, ...rows.map(row => row[1]));
    const visits = n(visitors.total);
    const prog = n(visitors.prog_views);
    const ratio = visits ? Math.min(100, Math.round((prog / visits) * 100)) : 0;

    suite.innerHTML = `
      <section class="analytics-card">
        <div class="analytics-head">
          <div>
            <div class="analytics-title">Activité opérationnelle</div>
            <div class="analytics-sub">Chaque barre ouvre les dossiers correspondants.</div>
          </div>
          <span class="ops-count">Données en direct</span>
        </div>
        <div class="bar-chart">
          ${rows.map((row, i) => `
            <div class="bar-col" data-priority-bar="${i}" tabindex="0">
              <div class="bar-value">${row[1]}</div>
              <div class="bar-track"><div class="bar-fill" style="height:${Math.max(3, Math.round((row[1] / max) * 100))}%;background:${row[2]}"></div></div>
              <div class="bar-label">${row[0]}</div>
            </div>`).join('')}
        </div>
      </section>
      <section class="analytics-card">
        <div class="analytics-head">
          <div>
            <div class="analytics-title">Audience numérique</div>
            <div class="analytics-sub">Fréquentation et lecture du programme.</div>
          </div>
        </div>
        <div class="ratio-ring" style="--ring:${ratio}%"><strong>${ratio}%</strong><small>lecture / visite</small></div>
        <div class="mini-metrics">
          <div class="mini-metric" data-priority-stat><strong>${visits}</strong><span>Visiteurs</span></div>
          <div class="mini-metric" data-priority-stat><strong>${prog}</strong><span>Lectures programme</span></div>
        </div>
      </section>`;

    suite.querySelectorAll('[data-priority-bar]').forEach(el => {
      const row = rows[Number(el.dataset.priorityBar || 0)];
      const go = () => navigate(row[3], row[4]);
      el.onclick = go;
      el.onkeydown = event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          go();
        }
      };
    });
    suite.querySelectorAll('[data-priority-stat]').forEach(el => {
      el.onclick = () => navigate('stats');
    });
  }

  function updateBaseKpis(stats) {
    if (typeof window.setText !== 'function') return;
    [
      ['kpi-aud-total', stats.aud_total],
      ['kpi-aud-wait', stats.aud_wait],
      ['kpi-aud-progress', stats.aud_progress],
      ['kpi-aud-done', stats.aud_done],
      ['kpi-recl', stats.recl_wait],
      ['kpi-ct', stats.ct_total],
    ].forEach(([id, value]) => window.setText(id, value ?? 0));
    if (stats.visitors) {
      window.setText('kpi-visit', stats.visitors.total ?? '—');
      window.setText('kpi-prog', stats.visitors.prog_views ?? '—');
    }
  }

  async function fastRefresh() {
    let token = '';
    try { token = typeof SESSION_TOKEN !== 'undefined' ? SESSION_TOKEN : ''; } catch (_) {}
    if (!token) return;

    try {
      const response = await fetch('/api/stats', {
        headers: { 'X-Admin-Token': token },
        cache: 'no-store',
      });
      const stats = await response.json().catch(() => ({}));
      if (!response.ok || !stats.ok) return;
      updateBaseKpis(stats);
      render(stats);

      if (!stats.visitors) {
        fetch('/api/visit-stats', { cache: 'no-store' })
          .then(r => r.json())
          .then(visitors => {
            if (!visitors || !visitors.ok) return;
            if (typeof window.setText === 'function') {
              window.setText('kpi-visit', visitors.total ?? '—');
              window.setText('kpi-prog', visitors.prog_views ?? '—');
            }
            render(stats, visitors);
          })
          .catch(() => {});
      }
    } catch (error) {
      console.warn('[BININGA] dashboard prioritaire indisponible', error);
    }
  }

  function patchInit() {
    if (typeof window.init !== 'function' || window.init.__biningaDashboardPriority) return;
    const original = window.init;
    const wrapped = function (...args) {
      ensureShell();
      fastRefresh();
      return original.apply(this, args);
    };
    wrapped.__biningaDashboardPriority = true;
    window.init = wrapped;
  }

  ensureShell();
  patchInit();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      ensureShell();
      patchInit();
    }, { once: true });
  }
})();
