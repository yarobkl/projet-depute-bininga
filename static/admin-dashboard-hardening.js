/* BININGA Admin — dashboard source-of-truth hardening + professional UX */
(() => {
  'use strict';

  const UX_STYLE_ID = 'bininga-admin-professional-ux';
  const KPI_NAV = {
    'kpi-aud-total': { panel: 'audiences', status: 'all' },
    'kpi-aud-wait': { panel: 'audiences', status: 'en_attente' },
    'kpi-aud-progress': { panel: 'audiences', status: 'en_cours' },
    'kpi-aud-done': { panel: 'audiences', status: 'traite' },
    'kpi-recl': { panel: 'reclamations', status: 'en_attente' },
    'kpi-ct': { panel: 'contacts', status: 'all' },
    'kpi-prog': { panel: 'stats', focus: 'programme' },
    'kpi-visit': { panel: 'stats', focus: 'visiteurs' }
  };

  function injectProfessionalStyles() {
    if (document.getElementById(UX_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = UX_STYLE_ID;
    style.textContent = `
      .kpi-card[data-drilldown="1"]{cursor:pointer!important;outline:none}
      .kpi-card[data-drilldown="1"]:focus-visible{box-shadow:0 0 0 3px rgba(184,151,58,.28)}
      .kpi-card[data-drilldown="1"]::before{content:'Ouvrir';position:absolute;right:14px;bottom:12px;font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:rgba(255,255,255,.28);opacity:0;transform:translateY(3px);transition:.2s ease}
      .kpi-card[data-drilldown="1"]:hover::before{opacity:1;transform:none}
      .analytics-suite{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(260px,.8fr);gap:18px;margin:18px 0}
      .analytics-card{background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.018));border:1px solid rgba(255,255,255,.075);border-radius:14px;padding:20px;min-width:0}
      .analytics-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:18px}
      .analytics-title{font-size:14px;font-weight:800}.analytics-sub{font-size:11px;color:rgba(255,255,255,.34);margin-top:4px}
      .bar-chart{display:flex;align-items:flex-end;gap:12px;height:190px;padding:20px 6px 0;border-bottom:1px solid rgba(255,255,255,.07)}
      .bar-col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:8px;height:100%;cursor:pointer;min-width:0}
      .bar-value{font-weight:800;font-size:13px}.bar-track{height:130px;width:min(54px,80%);display:flex;align-items:flex-end;border-radius:8px 8px 3px 3px;background:rgba(255,255,255,.035);overflow:hidden}
      .bar-fill{width:100%;min-height:4px;border-radius:8px 8px 3px 3px;transition:height .45s cubic-bezier(.22,1,.36,1)}
      .bar-label{font-size:10px;color:rgba(255,255,255,.46);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
      .mini-metrics{display:grid;grid-template-columns:1fr 1fr;gap:10px}.mini-metric{padding:15px;border-radius:10px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.055);cursor:pointer}
      .mini-metric strong{display:block;font-size:24px;margin-bottom:5px}.mini-metric span{font-size:10px;color:rgba(255,255,255,.42);text-transform:uppercase;letter-spacing:.08em}
      .ratio-ring{width:130px;height:130px;margin:4px auto 18px;border-radius:50%;display:grid;place-items:center;position:relative;background:conic-gradient(var(--g) var(--ring,0%),rgba(255,255,255,.055) 0)}
      .ratio-ring::after{content:'';position:absolute;inset:14px;background:var(--n2);border-radius:50%}.ratio-ring strong{position:relative;z-index:1;font-size:26px}.ratio-ring small{position:absolute;z-index:1;margin-top:42px;color:rgba(255,255,255,.35);font-size:9px;text-transform:uppercase}
      .ops-toolbar{display:flex;align-items:center;gap:10px;margin:0 0 14px;flex-wrap:wrap}.ops-search{flex:1;min-width:190px;background:var(--n3);color:#fff;border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:10px 12px;outline:none}.ops-search:focus{border-color:rgba(184,151,58,.45)}
      .ops-summary{font-size:11px;color:rgba(255,255,255,.38);white-space:nowrap}.ops-summary strong{color:#fff}
      .msg-list.experience-list{gap:9px}.msg-list.experience-list .msg-item{border-radius:12px;padding:16px 16px 14px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.065);box-shadow:none}
      .msg-list.experience-list .msg-item:hover{background:rgba(255,255,255,.04);border-color:rgba(184,151,58,.22)}
      .msg-list.experience-list .msg-name{font-size:14px}.msg-list.experience-list .msg-date{font-size:10px;color:rgba(255,255,255,.34)}
      .msg-list.experience-list .msg-fields{gap:5px;margin:8px 0 10px}.msg-list.experience-list .msg-field{font-size:10px;padding:3px 8px;background:rgba(255,255,255,.035);color:rgba(255,255,255,.52)}
      .msg-list.experience-list .msg-field.is-technical{display:none}
      .technical-details{margin:8px 0 0;border-top:1px dashed rgba(255,255,255,.08);padding-top:8px}.technical-details summary{cursor:pointer;color:rgba(255,255,255,.3);font-size:10px;list-style:none}.technical-details summary::-webkit-details-marker{display:none}.technical-details[open] summary{color:rgba(255,255,255,.55)}
      .technical-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.technical-pills .msg-field{display:inline-flex!important}
      .case-banner{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;padding:11px 13px;border-radius:10px;background:rgba(184,151,58,.055);border:1px solid rgba(184,151,58,.12)}
      .case-banner strong{font-size:12px}.case-banner span{font-size:10px;color:rgba(255,255,255,.4)}
      .editorial-workflow{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px}.workflow-step{padding:12px;border-radius:10px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);position:relative}.workflow-step b{display:block;font-size:11px}.workflow-step span{font-size:9px;color:rgba(255,255,255,.35)}.workflow-step.active{border-color:rgba(184,151,58,.35);background:rgba(184,151,58,.07)}
      .editorial-site-link{display:inline-flex;align-items:center;gap:7px;text-decoration:none;color:#d4b96a;border:1px solid rgba(184,151,58,.22);background:rgba(184,151,58,.06);padding:8px 11px;border-radius:8px;font-size:11px;font-weight:700}
      @media(max-width:900px){.analytics-suite{grid-template-columns:1fr}.analytics-card{padding:16px}.editorial-workflow{grid-template-columns:1fr 1fr}.bar-chart{gap:7px}.bar-track{width:min(44px,84%)}}
      @media(max-width:520px){.mini-metrics{grid-template-columns:1fr 1fr}.editorial-workflow{grid-template-columns:1fr}.ops-toolbar{align-items:stretch}.ops-search{width:100%}.bar-label{font-size:9px}}
    `;
    document.head.appendChild(style);
  }

  function setDashboardUnavailable() {
    ['kpi-aud-total','kpi-aud-wait','kpi-aud-progress','kpi-aud-done','kpi-recl','kpi-ct'].forEach(id => setText(id, '—'));
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
      { label: 'Réclamations', count: Number(s.recl_total || 0), color: '#C8102E', base: totalAll }
    ];
    el.innerHTML = rows.map(r => {
      const pct = r.base > 0 ? Math.round((r.count / r.base) * 100) : 0;
      return `<div><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px"><span style="font-size:12px;color:rgba(255,255,255,.55)">${esc(r.label)}</span><span style="font-size:13px;font-weight:700;color:${r.color}">${r.count}</span></div><div class="prog-bar"><div class="prog-bar-fill" style="width:${pct}%;background:${r.color}"></div></div></div>`;
    }).join('');
  }

  function renderRecentActivity(payload) {
    const feed = document.getElementById('feed');
    if (!feed) return;
    const audiences = Array.isArray(payload.audiences) ? payload.audiences : [];
    const contacts = Array.isArray(payload.contacts) ? payload.contacts : [];
    const rows = [...audiences.map(m => ({ ...m, _type: 'audience' })), ...contacts.map(m => ({ ...m, _type: 'contact' }))].sort((a,b) => new Date(b._date || b.ts || 0) - new Date(a._date || a.ts || 0)).slice(0,6);
    if (!rows.length) { feed.innerHTML = '<div class="msg-empty" style="padding:30px">Aucune activité pour le moment.</div>'; return; }
    feed.innerHTML = rows.map(m => {
      const isRecl = m.objet === 'Réclamation';
      const isAud = m._type === 'audience';
      const dot = isRecl ? 'red' : isAud ? 'gold' : 'blue';
      const label = isRecl ? 'Réclamation' : isAud ? "Demande d'audience" : 'Contact';
      const when = m._date || m.ts || '';
      return `<div class="feed-item"><div class="feed-dot ${dot}"></div><div><div class="feed-title">${esc(m.prenom || '')} ${esc(m.nom || '')} — ${esc(label)}</div><div class="feed-sub">${esc(when)}</div></div></div>`;
    }).join('');
  }

  function panelNav(panel, status) {
    const nav = Array.from(document.querySelectorAll('.sb-item')).find(el => String(el.getAttribute('onclick') || '').includes(`showPanel('${panel}'`));
    if (nav) nav.click();
    else if (typeof window.showPanel === 'function') window.showPanel(panel, null);
    if (!status) return;
    setTimeout(() => {
      const root = document.getElementById(`panel-${panel}`);
      const tab = root && Array.from(root.querySelectorAll('.tab')).find(el => String(el.getAttribute('onclick') || '').includes(`'${status}'`));
      if (tab) tab.click();
    }, 30);
  }

  function activateKpiDrilldowns() {
    Object.entries(KPI_NAV).forEach(([id, target]) => {
      const value = document.getElementById(id);
      const card = value && value.closest('.kpi-card');
      if (!card || card.dataset.drilldown === '1') return;
      card.dataset.drilldown = '1';
      card.tabIndex = 0;
      card.setAttribute('role','button');
      card.setAttribute('aria-label', `Ouvrir le détail de ${card.querySelector('.kpi-label')?.textContent || 'cet indicateur'}`);
      const open = () => panelNav(target.panel, target.status);
      card.addEventListener('click', open);
      card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    });
  }

  function renderAnalytics(s) {
    const dashboard = document.getElementById('panel-dashboard');
    if (!dashboard) return;
    let suite = document.getElementById('dashboard-analytics-suite');
    if (!suite) {
      suite = document.createElement('div');
      suite.id = 'dashboard-analytics-suite';
      suite.className = 'analytics-suite';
      const anchor = dashboard.querySelector('.dashboard-bottom-grid');
      if (anchor) anchor.insertAdjacentElement('beforebegin', suite); else dashboard.prepend(suite);
    }
    const vals = [
      {label:'Attente',value:Number(s.aud_wait||0),color:'#f39c12',panel:'audiences',status:'en_attente'},
      {label:'En cours',value:Number(s.aud_progress||0),color:'#3498db',panel:'audiences',status:'en_cours'},
      {label:'Traitées',value:Number(s.aud_done||0),color:'#2ecc71',panel:'audiences',status:'traite'},
      {label:'Réclam.',value:Number(s.recl_wait ?? s.recl_total ?? 0),color:'#C8102E',panel:'reclamations',status:'en_attente'},
      {label:'Messages',value:Number(s.ct_total||0),color:'#B8973A',panel:'contacts',status:'all'}
    ];
    const max = Math.max(1,...vals.map(v=>v.value));
    const visitors = Number(s.visitors?.total || 0);
    const prog = Number(s.visitors?.prog_views || 0);
    const ratio = visitors > 0 ? Math.min(100, Math.round((prog/visitors)*100)) : 0;
    suite.innerHTML = `<section class="analytics-card"><div class="analytics-head"><div><div class="analytics-title">Activité opérationnelle</div><div class="analytics-sub">Cliquez sur une barre pour ouvrir directement les dossiers concernés.</div></div><span class="ops-summary">Données en direct</span></div><div class="bar-chart">${vals.map((v,i)=>`<div class="bar-col" data-chart-index="${i}" tabindex="0"><div class="bar-value">${v.value}</div><div class="bar-track"><div class="bar-fill" style="height:${Math.max(3,Math.round((v.value/max)*100))}%;background:${v.color}"></div></div><div class="bar-label">${v.label}</div></div>`).join('')}</div></section><section class="analytics-card"><div class="analytics-head"><div><div class="analytics-title">Audience numérique</div><div class="analytics-sub">Lecture du programme et fréquentation du site.</div></div></div><div class="ratio-ring" style="--ring:${ratio}%"><strong>${ratio}%</strong><small>ratio lecture</small></div><div class="mini-metrics"><div class="mini-metric" data-mini-panel="stats"><strong>${visitors}</strong><span>Visiteurs</span></div><div class="mini-metric" data-mini-panel="stats"><strong>${prog}</strong><span>Lectures programme</span></div></div></section>`;
    suite.querySelectorAll('.bar-col').forEach(el => {
      const v = vals[Number(el.dataset.chartIndex)];
      const open=()=>panelNav(v.panel,v.status);
      el.addEventListener('click',open); el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});
    });
    suite.querySelectorAll('[data-mini-panel]').forEach(el=>el.addEventListener('click',()=>panelNav(el.dataset.miniPanel)));
  }

  function ensurePanelToolbar(panelId, listId, label) {
    const panel = document.getElementById(panelId);
    const list = document.getElementById(listId);
    if (!panel || !list || panel.querySelector(`[data-toolbar-for="${listId}"]`)) return;
    const toolbar = document.createElement('div');
    toolbar.className = 'ops-toolbar'; toolbar.dataset.toolbarFor = listId;
    toolbar.innerHTML = `<input class="ops-search" type="search" placeholder="Rechercher par nom, objet, message…" aria-label="Rechercher dans ${label}"><div class="ops-summary"><strong data-visible-count>0</strong> ${label}</div>`;
    list.parentElement.insertBefore(toolbar,list);
    const input = toolbar.querySelector('input');
    const apply = () => {
      const q = input.value.trim().toLowerCase(); let shown = 0;
      list.querySelectorAll('.msg-item').forEach(item=>{ const ok=!q || item.textContent.toLowerCase().includes(q); item.style.display=ok?'':'none'; if(ok) shown++; });
      toolbar.querySelector('[data-visible-count]').textContent = shown;
    };
    input.addEventListener('input',apply); setTimeout(apply,0);
  }

  function upgradeMessageItem(item, kind) {
    if (!item || item.dataset.experience === '1') return;
    item.dataset.experience='1';
    const fields=item.querySelector('.msg-fields');
    if (fields) {
      const technical=[];
      Array.from(fields.children).forEach(ch=>{
        const txt=(ch.textContent||'').trim();
        if (/\b(IP|TS|timestamp|user[- ]?agent|fingerprint|token|session|identifiant technique|request id)\b/i.test(txt)) {
          ch.classList.add('is-technical'); technical.push(ch);
        }
      });
      if (technical.length) {
        const details=document.createElement('details'); details.className='technical-details';
        details.innerHTML='<summary>Détails techniques</summary><div class="technical-pills"></div>';
        const pills=details.querySelector('.technical-pills'); technical.forEach(ch=>pills.appendChild(ch));
        fields.insertAdjacentElement('afterend',details);
      }
    }
    if (kind==='reclamations') {
      const banner=document.createElement('div'); banner.className='case-banner';
      banner.innerHTML='<strong>Dossier de réclamation</strong><span>Suivi, statut et actions de traitement</span>';
      item.prepend(banner);
    }
  }

  function upgradeOperationalLists() {
    const configs=[['panel-audiences','list-audiences','demandes','audiences'],['panel-reclamations','list-reclamations','réclamations','reclamations'],['panel-contacts','list-contacts','messages','contacts']];
    configs.forEach(([panelId,listId,label,kind])=>{
      ensurePanelToolbar(panelId,listId,label);
      const list=document.getElementById(listId); if(!list) return;
      list.classList.add('experience-list');
      list.querySelectorAll('.msg-item').forEach(item=>upgradeMessageItem(item,kind));
      const toolbar=document.querySelector(`[data-toolbar-for="${listId}"]`);
      if(toolbar) toolbar.querySelector('[data-visible-count]').textContent=list.querySelectorAll('.msg-item').length;
    });
  }

  function enhanceEditorial() {
    const panel=document.getElementById('panel-editorial');
    if(!panel || panel.dataset.experience==='1') return;
    panel.dataset.experience='1';
    const firstCard=panel.querySelector('.card');
    if(!firstCard) return;
    const flow=document.createElement('div'); flow.className='editorial-workflow';
    flow.innerHTML='<div class="workflow-step active"><b>1. Source</b><span>Veille YARO IA ou saisie</span></div><div class="workflow-step"><b>2. Génération IA</b><span>Article structuré</span></div><div class="workflow-step"><b>3. Validation</b><span>Relecture humaine</span></div><div class="workflow-step"><b>4. Publication</b><span>Mise en ligne réelle</span></div>';
    firstCard.prepend(flow);
    const link=document.createElement('a'); link.className='editorial-site-link'; link.href='index.html#actualites'; link.target='_blank'; link.rel='noopener'; link.textContent='Voir les actualités publiées';
    const head=firstCard.querySelector('.card-header'); if(head) head.appendChild(link);
  }

  async function fetchJson(url) {
    const res = await apiFetch(url, { headers: { 'X-Admin-Token': SESSION_TOKEN }, cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) throw new Error(data.message || `Erreur ${res.status}`);
    return data;
  }

  window.refreshDashboard = async function refreshDashboardAuthoritative() {
    if (!SESSION_TOKEN) return;
    try {
      const [stats, contacts] = await Promise.all([fetchJson('/api/stats'), fetchJson('/api/contacts')]);
      setText('kpi-aud-total', stats.aud_total ?? 0); setText('kpi-aud-wait', stats.aud_wait ?? 0); setText('kpi-aud-progress', stats.aud_progress ?? 0); setText('kpi-aud-done', stats.aud_done ?? 0); setText('kpi-recl', stats.recl_wait ?? 0); setText('kpi-ct', stats.ct_total ?? 0);
      setBadge('badge-aud', stats.aud_wait ?? 0); setBadge('badge-recl', stats.recl_wait ?? 0); setBadge('badge-ct', stats.ct_unread ?? 0);
      if (stats.visitors) { setText('kpi-visit', stats.visitors.total ?? '—'); setText('kpi-prog', stats.visitors.prog_views ?? '—'); }
      else { fetch('/api/visit-stats',{cache:'no-store'}).then(r=>r.json()).then(v=>{ if(v.ok){setText('kpi-visit',v.total??'—');setText('kpi-prog',v.prog_views??'—');renderAnalytics({...stats,visitors:v});} }).catch(()=>{}); }
      renderBreakdown(stats); renderRecentActivity(contacts); renderAnalytics(stats); activateKpiDrilldowns();
    } catch (err) {
      setDashboardUnavailable();
      const feed=document.getElementById('feed'); if(feed) feed.innerHTML='<div class="msg-empty" style="padding:30px">Données serveur momentanément indisponibles.</div>';
      console.warn('[BININGA Admin] Dashboard server sync failed:',err&&err.message?err.message:err);
    }
  };

  function bootExperience() {
    injectProfessionalStyles(); activateKpiDrilldowns(); upgradeOperationalLists(); enhanceEditorial();
    const observer=new MutationObserver(()=>{ upgradeOperationalLists(); activateKpiDrilldowns(); enhanceEditorial(); });
    observer.observe(document.body,{subtree:true,childList:true});
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',bootExperience,{once:true}); else bootExperience();
  console.info('[BININGA Admin] Professional dashboard and operational UX active');
})();
