/* BININGA Admin — CRM / Utilisateurs / Système : UX + intégrité */
(()=>{
  'use strict';
  if(window.__BININGA_SYSTEM_UX__) return;
  window.__BININGA_SYSTEM_UX__=true;

  const q=(s,r=document)=>r.querySelector(s);
  const mainAdmin=()=>{try{return typeof SESSION_IS_MAIN_ADMIN!=='undefined'&&!!SESSION_IS_MAIN_ADMIN}catch(_){return false}};
  const toast=(m,e=false)=>typeof window.showToast==='function'?window.showToast(m,e):console[e?'error':'info'](m);
  const SYSTEM_PANELS=new Set(['monitoring','backups','logs','users','security']);
  let _panelLoadToken=0;

  function css(){
    if(q('#bininga-system-ux-css'))return;
    const s=document.createElement('style');s.id='bininga-system-ux-css';s.textContent=`
.sys-banner{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 13px;margin:0 0 14px;border:1px solid rgba(184,151,58,.15);background:rgba(184,151,58,.05);border-radius:10px}.sys-banner b{font-size:11px}.sys-banner span{font-size:9px;color:rgba(255,255,255,.38)}.sys-dot{width:7px;height:7px;border-radius:50%;background:#2ecc71;box-shadow:0 0 0 4px rgba(46,204,113,.08)}
#panel-crm .crm-item,#panel-users .user-item{border-radius:12px!important;border:1px solid rgba(255,255,255,.065)!important;background:rgba(255,255,255,.025)!important}#panel-crm .crm-item:hover,#panel-users .user-item:hover{border-color:rgba(184,151,58,.22)!important}.system-readonly-hint{font-size:9px;color:rgba(255,255,255,.34);margin-top:7px}.system-danger-note{font-size:9px;color:#e6a7a7;margin-top:7px}
.system-loading-state{display:flex;align-items:center;gap:8px;padding:10px 12px;margin:0 0 12px;border-radius:9px;background:rgba(52,152,219,.06);border:1px solid rgba(52,152,219,.14);font-size:10px;color:rgba(255,255,255,.48)}.system-loading-state::before{content:'';width:7px;height:7px;border-radius:50%;background:#3498db;box-shadow:0 0 0 4px rgba(52,152,219,.08)}
.system-error-state{padding:12px 14px;margin:0 0 12px;border-radius:9px;background:rgba(231,76,60,.06);border:1px solid rgba(231,76,60,.18);font-size:11px;color:#e9aaaa}.system-error-state button{margin-left:8px}
#panel-monitoring .mon-kpi-grid,#panel-security .sec-grid,#panel-backups .kpi-grid{align-items:stretch}
@media(max-width:620px){.sys-banner{align-items:flex-start;flex-direction:column}.crm-toolbar,.security-toolbar{gap:8px!important}.user-item{align-items:flex-start!important;flex-wrap:wrap!important}.user-item .btn-danger,.user-item .sbtn{margin-left:0!important}}
`;document.head.appendChild(s);
  }

  function banner(panelId,title,detail){
    const p=q('#'+panelId);if(!p||q('.sys-banner',p))return;
    const anchor=q('.panel-header',p)||q('.card',p)||p;const b=document.createElement('div');b.className='sys-banner';
    b.innerHTML=`<div style="display:flex;align-items:center;gap:9px"><span class="sys-dot"></span><div><b>${title}</b><div><span>${detail}</span></div></div></div><span>Données serveur</span>`;
    if(anchor.classList && anchor.classList.contains('panel-header')) anchor.after(b); else anchor.prepend(b);
  }

  function setLoading(name,on){
    const panel=q('#panel-'+name);if(!panel)return;
    let box=q('.system-loading-state',panel);
    if(!on){if(box)box.remove();return;}
    if(!box){box=document.createElement('div');box.className='system-loading-state';box.textContent='Chargement des données système…';const head=q('.panel-header',panel);head?head.after(box):panel.prepend(box);}
  }

  function showSystemError(name,message){
    const panel=q('#panel-'+name);if(!panel)return;
    const old=q('.system-error-state',panel);if(old)old.remove();
    const box=document.createElement('div');box.className='system-error-state';box.textContent=message||'Impossible de charger cette rubrique.';panel.prepend(box);
  }

  function clearSystemError(name){const old=q('#panel-'+name+' .system-error-state');if(old)old.remove()}

  // PostgreSQL/server is authoritative. A stale browser backup must never
  // silently repopulate an empty production CRM after a deploy or deletion.
  window._crmRestoreFromBackup = async function crmRestoreDisabled(){
    console.warn('[BININGA CRM] Restauration locale automatique désactivée; serveur autoritaire.');
    return 0;
  };

  function protectSystemPanels(){
    ['panel-crm','panel-users','panel-security','panel-monitoring','panel-backups','panel-logs'].forEach(id=>{
      const p=q('#'+id);if(!p)return;
      p.querySelectorAll('button,input,select,textarea').forEach(el=>{
        const destructive=/supprim|effac|bloqu|restaur|reset|lockdown|réinitial/i.test((el.textContent||'')+' '+(el.getAttribute('onclick')||''));
        if(!mainAdmin() && destructive){el.disabled=true;el.setAttribute('aria-disabled','true');}
      });
    });
  }

  function hardenUserForm(){
    const original=window.submitUserForm;if(typeof original!=='function'||original.__biningaWrapped)return;
    const wrapped=async function(){
      if(!mainAdmin()){toast('Gestion des utilisateurs réservée à l’administrateur principal.',true);return;}
      const username=(q('#uf-username')?.value||'').trim();const password=q('#uf-password')?.value||'';const role=q('#uf-role')?.value||'';
      if(!/^[A-Za-z0-9._-]{3,64}$/.test(username)){toast('Identifiant invalide : 3 à 64 caractères, lettres/chiffres/._-.',true);return;}
      if(!['admin','editeur','lecteur','ministre'].includes(role)){toast('Rôle utilisateur invalide.',true);return;}
      const editing=typeof _editingUser!=='undefined'&&!!_editingUser;
      if(!editing && password.length<10){toast('Le mot de passe doit contenir au moins 10 caractères.',true);return;}
      return original.apply(this,arguments);
    };wrapped.__biningaWrapped=true;window.submitUserForm=wrapped;
  }

  function wrapMainAdmin(name,label){
    const original=window[name];if(typeof original!=='function'||original.__biningaWrapped)return;
    const wrapped=async function(){if(!mainAdmin()){toast(`${label} réservée à l’administrateur principal.`,true);return;}return original.apply(this,arguments)};
    wrapped.__biningaWrapped=true;window[name]=wrapped;
  }

  function stopMonitoringRefresh(){
    try{if(typeof _monRefreshTimer!=='undefined'&&_monRefreshTimer){clearInterval(_monRefreshTimer);_monRefreshTimer=null;}}catch(_){}
  }

  async function invokeLoader(name){
    const loaders={
      monitoring:()=>typeof window.loadMonitoring==='function'?window.loadMonitoring():null,
      backups:()=>typeof window.loadBackups==='function'?window.loadBackups():null,
      logs:()=>typeof window.loadAuditLogs==='function'?window.loadAuditLogs():null,
      users:()=>typeof window.loadUsers==='function'?window.loadUsers():null,
      security:()=>Promise.allSettled([
        typeof window.loadSecurity==='function'?window.loadSecurity():Promise.resolve(),
        typeof window.loadBouclier==='function'?window.loadBouclier():Promise.resolve()
      ])
    };
    const loader=loaders[name];if(!loader)return;
    const token=++_panelLoadToken;
    clearSystemError(name);setLoading(name,true);
    try{
      await loader();
      if(token===_panelLoadToken)clearSystemError(name);
    }catch(err){
      console.error('[BININGA System] chargement '+name,err);
      if(token===_panelLoadToken)showSystemError(name,'Chargement impossible. Utilisez « Actualiser » ou reconnectez-vous.');
    }finally{
      if(token===_panelLoadToken)setLoading(name,false);
      protectSystemPanels();
    }
  }

  function onPanelChange(name){
    if(name!=='monitoring')stopMonitoringRefresh();
    if(!SYSTEM_PANELS.has(name))return;
    // Le panneau doit être utilisable immédiatement : déclenchement au clic,
    // sans dépendre de l'ancien showPanel() de admin.js qui a été remplacé.
    invokeLoader(name);
  }

  function install(){
    css();
    banner('panel-crm','CRM citoyens','Contacts, historique, notes, import/export et newsletter depuis les données persistantes.');
    banner('panel-users','Utilisateurs et rôles','Comptes, rôles et droits réellement chargés depuis le serveur.');
    banner('panel-security','Sécurité opérationnelle','Blocages, suspects, 2FA et événements issus des contrôles serveur.');
    banner('panel-monitoring','Monitoring','État applicatif, alertes et endpoints depuis les métriques serveur.');
    banner('panel-backups','Sauvegardes','Archives de reprise et état de persistance du serveur.');
    banner('panel-logs','Journaux d’audit','Historique des actions sensibles et administratives enregistrées côté serveur.');
    hardenUserForm();
    ['deleteUser','crmDelete','crmBulkDelete','crmImport','runBackupNow','downloadBackup','manualBlock','unblockIp','activateLockdown','deactivateLockdown','resetSystem'].forEach(n=>wrapMainAdmin(n,'Cette action'));
    protectSystemPanels();
    const role=window.applyRoleUI;
    if(typeof role==='function'&&!role.__systemUxWrapped){const w=function(){const r=role.apply(this,arguments);protectSystemPanels();return r};w.__systemUxWrapped=true;window.applyRoleUI=w;}

    window.addEventListener('admin:panelchange',e=>onPanelChange(e?.detail?.name||''));
    const active=q('.panel.active');
    if(active&&active.id&&active.id.startsWith('panel-'))onPanelChange(active.id.slice(6));
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();