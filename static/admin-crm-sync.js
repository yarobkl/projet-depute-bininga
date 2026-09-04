/* BININGA Admin — CRM synchronization UX */
(()=>{
  'use strict';
  if(window.__BININGA_CRM_SYNC_UX__) return;
  window.__BININGA_CRM_SYNC_UX__=true;

  function install(){
    const panel=document.getElementById('panel-crm');
    if(!panel)return;

    // CRM is operational data, not site-content editing: hide the global CMS
    // action bar whenever this panel is active (including mobile Safari).
    if(!document.getElementById('bininga-crm-sync-css')){
      const style=document.createElement('style');
      style.id='bininga-crm-sync-css';
      style.textContent=`
        body:has(#panel-crm.active) #admin-actionbar{display:none!important}
        .crm-sync-note{margin:0 0 14px;padding:10px 12px;border:1px solid rgba(46,204,113,.18);background:rgba(46,204,113,.055);border-radius:9px;color:rgba(255,255,255,.58);font-size:11px;line-height:1.5}
        .crm-sync-note strong{color:#72d99b}
      `;
      document.head.appendChild(style);
    }

    const importButton=[...panel.querySelectorAll('button')].find(btn=>/Importer demandes/i.test(btn.textContent||''));
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
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
  window.addEventListener('bininga:admin-modules-ready',install);
})();
