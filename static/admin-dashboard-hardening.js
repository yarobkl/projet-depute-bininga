/* BININGA Admin — dashboard source-of-truth hardening
 *
 * The legacy dashboard paints authoritative server stats, then immediately
 * overwrites them from localStorage. This layer keeps the API/database as the
 * only source of truth for KPIs, badges, breakdown and recent activity.
 */
(() => {
  'use strict';

  function setDashboardUnavailable() {
    ['kpi-aud-total','kpi-aud-wait','kpi-aud-progress','kpi-aud-done','kpi-recl','kpi-ct']
      .forEach(id => setText(id, '—'));
  }

  function renderBreakdown(s) {
    const el = document.getElementById('aud-breakdown');
    if (!el) return;

    const totalAud = Number(s.aud_total || 0);
    const totalAll = totalAud + Number(s.recl_total || 0);
    const rows = [
      { label: 'En attente', count: Number(s.aud_wait || 0), color: '#f39c12', base: totalAud },
      { label: 'En cours', count: Number(s.aud_progress || 0), color: '#3498db', base: totalAud },
      { label: 'Traitées', count: Number(s.aud_done || 0), color: '#2ecc71', base: totalAud },
      { label: 'Réclamations', count: Number(s.recl_total || 0), color: '#C8102E', base: totalAll },
    ];

    el.innerHTML = rows.map(r => {
      const pct = r.base > 0 ? Math.round((r.count / r.base) * 100) : 0;
      return `
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span style="font-size:12px;color:rgba(255,255,255,.55)">${esc(r.label)}</span>
            <span style="font-size:13px;font-weight:700;color:${r.color}">${r.count}</span>
          </div>
          <div class="prog-bar"><div class="prog-bar-fill" style="width:${pct}%;background:${r.color}"></div></div>
        </div>`;
    }).join('');
  }

  function renderRecentActivity(payload) {
    const feed = document.getElementById('feed');
    if (!feed) return;

    const audiences = Array.isArray(payload.audiences) ? payload.audiences : [];
    const contacts = Array.isArray(payload.contacts) ? payload.contacts : [];
    const rows = [
      ...audiences.map(m => ({ ...m, _type: 'audience' })),
      ...contacts.map(m => ({ ...m, _type: 'contact' })),
    ]
      .sort((a, b) => new Date(b._date || b.ts || 0) - new Date(a._date || a.ts || 0))
      .slice(0, 6);

    if (!rows.length) {
      feed.innerHTML = '<div class="msg-empty" style="padding:30px">Aucune activité pour le moment.</div>';
      return;
    }

    feed.innerHTML = rows.map(m => {
      const isRecl = m.objet === 'Réclamation';
      const isAud = m._type === 'audience';
      const dot = isRecl ? 'red' : isAud ? 'gold' : 'blue';
      const label = isRecl ? 'Réclamation' : isAud ? "Demande d'audience" : 'Contact';
      const when = m._date || m.ts || '';
      return `<div class="feed-item">
        <div class="feed-dot ${dot}"></div>
        <div>
          <div class="feed-title">${esc(m.prenom || '')} ${esc(m.nom || '')} — ${esc(label)}</div>
          <div class="feed-sub">${esc(when)}</div>
        </div>
      </div>`;
    }).join('');
  }

  async function fetchJson(url) {
    const res = await apiFetch(url, {
      headers: { 'X-Admin-Token': SESSION_TOKEN },
      cache: 'no-store'
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) throw new Error(data.message || `Erreur ${res.status}`);
    return data;
  }

  window.refreshDashboard = async function refreshDashboardAuthoritative() {
    if (!SESSION_TOKEN) return;

    try {
      const [stats, contacts] = await Promise.all([
        fetchJson('/api/stats'),
        fetchJson('/api/contacts')
      ]);

      setText('kpi-aud-total', stats.aud_total ?? 0);
      setText('kpi-aud-wait', stats.aud_wait ?? 0);
      setText('kpi-aud-progress', stats.aud_progress ?? 0);
      setText('kpi-aud-done', stats.aud_done ?? 0);
      setText('kpi-recl', stats.recl_wait ?? 0);
      setText('kpi-ct', stats.ct_total ?? 0);
      setBadge('badge-aud', stats.aud_wait ?? 0);
      setBadge('badge-recl', stats.recl_wait ?? 0);
      setBadge('badge-ct', stats.ct_unread ?? 0);

      if (stats.visitors) {
        setText('kpi-visit', stats.visitors.total ?? '—');
        setText('kpi-prog', stats.visitors.prog_views ?? '—');
      } else {
        fetch('/api/visit-stats', { cache: 'no-store' })
          .then(r => r.json())
          .then(v => {
            if (v.ok) {
              setText('kpi-visit', v.total ?? '—');
              setText('kpi-prog', v.prog_views ?? '—');
            }
          })
          .catch(() => {});
      }

      renderBreakdown(stats);
      renderRecentActivity(contacts);
    } catch (err) {
      setDashboardUnavailable();
      const feed = document.getElementById('feed');
      if (feed) feed.innerHTML = '<div class="msg-empty" style="padding:30px">Données serveur momentanément indisponibles.</div>';
      console.warn('[BININGA Admin] Dashboard server sync failed:', err && err.message ? err.message : err);
    }
  };

  console.info('[BININGA Admin] Dashboard source-of-truth hardening active');
})();
