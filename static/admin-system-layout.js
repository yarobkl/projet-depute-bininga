/* BININGA Admin — organisation visuelle du bloc SYSTÈME */
(()=>{
  'use strict';
  if(window.__BININGA_SYSTEM_LAYOUT__) return;
  window.__BININGA_SYSTEM_LAYOUT__=true;

  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];

  function css(){
    if(q('#bininga-system-layout-css'))return;
    const st=document.createElement('style');st.id='bininga-system-layout-css';st.textContent=`
.system-view-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 16px;padding:5px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.065);border-radius:11px}.system-view-tab{appearance:none;border:0;background:transparent;color:rgba(255,255,255,.46);padding:8px 12px;border-radius:8px;font:600 11px/1.2 inherit;cursor:pointer;transition:.18s ease}.system-view-tab:hover{color:#fff;background:rgba(255,255,255,.045)}.system-view-tab.active{color:#fff;background:rgba(184,151,58,.13);box-shadow:inset 0 0 0 1px rgba(184,151,58,.22)}.system-view{display:none}.system-view.active{display:block}.system-view>.card:first-child,.system-view>.sec-grid:first-child{margin-top:0!important}.system-view-note{font-size:10px;color:rgba(255,255,255,.34);margin:-7px 0 14px;line-height:1.5}
.system-list-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 14px}.system-list-tools input,.system-list-tools select{min-height:36px;padding:8px 11px;background:var(--n3);border:1px solid rgba(255,255,255,.08);border-radius:8px;color:#fff;font:500 12px/1 inherit;outline:none}.system-list-tools input{flex:1;min-width:210px}.system-list-tools input:focus,.system-list-tools select:focus{border-color:rgba(184,151,58,.4)}.system-list-count{margin-left:auto;font-size:10px;color:rgba(255,255,255,.35)}
#panel-backups .panel-header .card-actions{display:grid!important;grid-template-columns:auto auto auto;gap:7px!important}#panel-backups #btn-run-backup{background:rgba(46,204,113,.12)!important;color:#45d483!important;border-color:rgba(46,204,113,.25)!important}#panel-backups #btn-download-backup{background:rgba(52,152,219,.09)!important;color:#69b5e8!important;border-color:rgba(52,152,219,.2)!important}
#panel-security .system-view[data-view='shield'] #bouclier-card{border-color:rgba(200,16,46,.18)!important}#panel-security .system-view[data-view='overview'] .sec-grid{margin-bottom:14px}.system-empty-filter{padding:22px;text-align:center;color:rgba(255,255,255,.35);font-size:11px}
@media(max-width:720px){.system-view-tabs{display:grid;grid-template-columns:1fr 1fr}.system-view-tab{text-align:center}.system-list-tools{align-items:stretch}.system-list-tools input,.system-list-tools select{width:100%;min-width:0}.system-list-count{margin-left:0}#panel-backups .panel-header .card-actions{grid-template-columns:1fr!important;width:100%}#panel-backups .panel-header .card-actions>*{width:100%;justify-content:center}}
`;document.head.appendChild(st);
  }

  function titleByText(panel,text){
    return qa(':scope > .mon-section-title',panel).find(el=>(el.textContent||'').toLowerCase().includes(text.toLowerCase()));
  }

  function pairInto(panel,titleText,contentSelector,wrapper){
    const title=titleByText(panel,titleText),content=q(contentSelector,panel);
    if(title)wrapper.appendChild(title);
    if(content)wrapper.appendChild(content);
  }

  function addTabs(panel,tabs,defaultView){
    if(!panel||panel.dataset.systemTabbed==='1')return;
    panel.dataset.systemTabbed='1';
    const bar=document.createElement('div');bar.className='system-view-tabs';bar.setAttribute('role','tablist');
    const anchor=q('.sys-banner',panel)||q('.panel-header',panel);
    tabs.forEach(tab=>{
      tab.wrapper.classList.add('system-view');tab.wrapper.dataset.view=tab.id;
      const btn=document.createElement('button');btn.type='button';btn.className='system-view-tab';btn.dataset.view=tab.id;btn.textContent=tab.label;btn.setAttribute('role','tab');
      btn.onclick=()=>activate(tab.id);
      bar.appendChild(btn);panel.appendChild(tab.wrapper);
    });
    anchor?anchor.after(bar):panel.prepend(bar);
    function activate(id){
      qa('.system-view-tab',bar).forEach(btn=>{const on=btn.dataset.view===id;btn.classList.toggle('active',on);btn.setAttribute('aria-selected',on?'true':'false')});
      tabs.forEach(tab=>tab.wrapper.classList.toggle('active',tab.id===id));
      try{sessionStorage.setItem('bininga_system_view_'+panel.id,id)}catch(_){}
    }
    let wanted=defaultView;
    try{wanted=sessionStorage.getItem('bininga_system_view_'+panel.id)||defaultView}catch(_){}
    if(!tabs.some(t=>t.id===wanted))wanted=defaultView;
    activate(wanted);
  }

  function layoutMonitoring(){
    const p=q('#panel-monitoring');if(!p||p.dataset.systemLayout==='1')return;p.dataset.systemLayout='1';
    const overview=document.createElement('div');overview.innerHTML='<div class="system-view-note">État de santé, charge du serveur et alertes importantes en un coup d’œil.</div>';
    const traffic=document.createElement('div');traffic.innerHTML='<div class="system-view-note">Analyse technique des routes les plus sollicitées et des requêtes récentes.</div>';
    const errors=document.createElement('div');errors.innerHTML='<div class="system-view-note">Exceptions applicatives détectées récemment.</div>';
    const report=document.createElement('div');report.innerHTML='<div class="system-view-note">Synthèse automatique des dernières 24 heures.</div>';

    ['#mon-status-bar','.mon-kpi-grid'].forEach(sel=>{const el=q(':scope > '+sel,p)||q(sel,p);if(el)overview.appendChild(el)});
    pairInto(p,'Métriques système','.mon-sys-grid',overview);
    pairInto(p,'Alertes actives','#mon-alerts-list',overview);
    pairInto(p,'Top endpoints','#mon-endpoints-list',traffic);
    pairInto(p,'Requêtes récentes','#mon-requests-list',traffic);
    pairInto(p,'Dernières exceptions','#mon-errors-list',errors);
    pairInto(p,'Rapport automatique','#mon-report-box',report);

    addTabs(p,[
      {id:'overview',label:'Vue générale',wrapper:overview},
      {id:'traffic',label:'Trafic & endpoints',wrapper:traffic},
      {id:'errors',label:'Erreurs',wrapper:errors},
      {id:'report',label:'Rapport 24h',wrapper:report},
    ],'overview');
  }

  function layoutSecurity(){
    const p=q('#panel-security');if(!p||p.dataset.systemLayout==='1')return;p.dataset.systemLayout='1';
    const overview=document.createElement('div');overview.innerHTML='<div class="system-view-note">Situation actuelle : IP bloquées, signaux suspects et accès à traiter.</div>';
    const attacks=document.createElement('div');attacks.innerHTML='<div class="system-view-note">Journal des détections de sécurité. À consulter lorsqu’un comportement suspect est signalé.</div>';
    const account=document.createElement('div');account.innerHTML='<div class="system-view-note">Protection du compte administrateur et authentification à deux facteurs.</div>';
    const shield=document.createElement('div');shield.innerHTML='<div class="system-view-note">Protection avancée et commandes d’urgence. Les actions sensibles restent protégées par le 2FA.</div>';

    const grids=qa(':scope > .sec-grid',p);
    if(grids[0])overview.appendChild(grids[0]);
    if(grids[1])overview.appendChild(grids[1]);
    const attackList=q('#sec-attacks-list',p);const attackCard=attackList&&attackList.closest('.card');if(attackCard)attacks.appendChild(attackCard);
    const tfa=q('#tfa-status',p);const tfaCard=tfa&&tfa.closest('.card');if(tfaCard)account.appendChild(tfaCard);
    const shieldCard=q('#bouclier-card',p);if(shieldCard)shield.appendChild(shieldCard);

    addTabs(p,[
      {id:'overview',label:'Vue générale',wrapper:overview},
      {id:'attacks',label:'Attaques',wrapper:attacks},
      {id:'account',label:'Compte & 2FA',wrapper:account},
      {id:'shield',label:'Bouclier IA',wrapper:shield},
    ],'overview');
  }

  function installUserTools(){
    const list=q('#user-list'),panel=q('#panel-users');if(!list||!panel||q('[data-system-users-tools]',panel))return;
    const tools=document.createElement('div');tools.className='system-list-tools';tools.dataset.systemUsersTools='1';
    tools.innerHTML='<input type="search" placeholder="Rechercher un utilisateur…" aria-label="Rechercher un utilisateur"><select aria-label="Filtrer par rôle"><option value="">Tous les rôles</option><option value="admin">Administrateurs</option><option value="editeur">Secrétaires</option><option value="lecteur">Consultation</option><option value="ministre">Député</option></select><span class="system-list-count"></span>';
    list.before(tools);const input=q('input',tools),select=q('select',tools),count=q('.system-list-count',tools);
    const run=()=>{const term=(input.value||'').trim().toLowerCase(),role=select.value;let shown=0;qa('.user-item',list).forEach(item=>{const okTerm=!term||(item.textContent||'').toLowerCase().includes(term),okRole=!role||item.dataset.role===role,ok=okTerm&&okRole;item.style.display=ok?'':'none';if(ok)shown++});count.textContent=shown+' affiché(s)'};
    input.oninput=run;select.onchange=run;new MutationObserver(()=>setTimeout(run,0)).observe(list,{childList:true,subtree:true});run();
  }

  function installLogTools(){
    const list=q('#log-list'),panel=q('#panel-logs');if(!list||!panel||q('[data-system-logs-tools]',panel))return;
    const tools=document.createElement('div');tools.className='system-list-tools';tools.dataset.systemLogsTools='1';tools.innerHTML='<input type="search" placeholder="Rechercher dans les journaux…" aria-label="Rechercher dans les journaux"><span class="system-list-count"></span>';
    list.before(tools);const input=q('input',tools),count=q('.system-list-count',tools);
    const run=()=>{const term=(input.value||'').trim().toLowerCase();let shown=0;const rows=qa('.log-item, .audit-item, [data-log-entry]',list);(rows.length?rows:qa(':scope > *',list)).forEach(item=>{if(item.classList.contains('msg-empty'))return;const ok=!term||(item.textContent||'').toLowerCase().includes(term);item.style.display=ok?'':'none';if(ok)shown++});count.textContent=shown?shown+' entrée(s)':''};
    input.oninput=run;new MutationObserver(()=>setTimeout(run,0)).observe(list,{childList:true,subtree:true});run();
  }

  function hierarchyBackups(){
    const p=q('#panel-backups');if(!p)return;const actions=q('.panel-header .card-actions',p);if(actions)actions.setAttribute('aria-label','Actions de sauvegarde');
  }

  function install(){css();layoutMonitoring();layoutSecurity();installUserTools();installLogTools();hierarchyBackups()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
  window.addEventListener('bininga:admin-modules-ready',install);
})();