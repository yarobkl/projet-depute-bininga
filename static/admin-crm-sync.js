/* BININGA Admin — CRM synchronization UX + lifecycle */
(()=>{
  'use strict';
  if(window.__BININGA_CRM_SYNC_UX__) return;
  window.__BININGA_CRM_SYNC_UX__=true;

  let _loading=false;
  let _queued=false;

  function setKpiLoading(){
    const total=document.getElementById('crm-kpi-total');
    const nl=document.getElementById('crm-kpi-nl');
    if(total) total.textContent='—';
    if(nl) nl.textContent='—';
  }

  async function refreshCrm(){
    if(_loading){ _queued=true; return; }
    if(typeof window.loadCrm!=='function'){
      setTimeout(refreshCrm,120);
      return;
    }
    _loading=true;
    _queued=false;
    setKpiLoading();
    try{
      await window.loadCrm(1);
    }catch(err){
      console.error('[BININGA CRM] chargement impossible',err);
      if(typeof window.showToast==='function') window.showToast('Impossible de charger le CRM',true);
    }finally{
      _loading=false;
      if(_queued) setTimeout(refreshCrm,0);
    }
  }

  function install(){
    const panel=document.getElementById('panel-crm');
    if(!panel)return;

    if(!document.getElementById('bininga-crm-sync-css')){
      const style=document.createElement('style');
      style.id='bininga-crm-sync-css';
      style.textContent=`
        body:has(#panel-crm.active) #admin-actionbar{display:none!important}
        .crm-sync-note{margin:0 0 14px;padding:10px 12px;border:1px solid rgba(46,204,113,.18);background:rgba(46,204,113,.055);border-radius:9px;color:rgba(255,255,255,.58);font-size:11px;line-height:1.5}
        .crm-sync-note strong{color:#72d99b}
        @media(max-width:768px){
          #panel-crm{padding-top:0!important;margin-top:0!important}
          #panel-crm>.kpi-grid:first-child{margin-top:0!important;padding-top:0!important}
        }
      `;
      document.head.appendChild(style);
    }

    const importButton=[...panel.querySelectorAll('button')].find(btn=>/Importer demandes|Synchroniser maintenant/i.test(btn.textContent||''));
    if(importButton){
      importButton.textContent='Synchroniser maintenant';
      importButton.title='La synchronisation est automatique. Utilisez ce bouton pour la relancer immédiatement.';
    }

    if(!panel.querySelector('.crm-sync-note')){
      const cardTitle=[...panel.querySelectorAll('.card-title')].find(el=>/Base de contacts/i.test(el.textContent||''));
      const card=cardTitle&&cardTitle.closest('.card');
      if(card){
        const note=document.createElement('div');
        note.className='crm-sync-note';
        note.innerHTML='<strong>Synchronisation automatique active.</strong> Les demandes d’audience, réclamations, messages et inscriptions citoyennes sont rapprochés du CRM à chaque ouverture, sans doublons.';
        const header=card.querySelector('.card-header');
        if(header)header.after(note); else card.prepend(note);
      }
    }

    // Fallback uniquement si la navigation centrale n'est pas installée.
    if(panel.classList.contains('active') && !window.__BININGA_ADMIN_NAVIGATION__) refreshCrm();
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();

  window.addEventListener('bininga:admin-modules-ready',install);
  window.addEventListener('admin:panelchange',(event)=>{
    if(event?.detail?.name==='crm' && !window.__BININGA_ADMIN_NAVIGATION__) refreshCrm();
  });

  window.refreshCrmFromServer=refreshCrm;
})();