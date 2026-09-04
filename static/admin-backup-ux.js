/* BININGA Admin — sauvegardes adaptées au runtime serverless */
(()=>{
  'use strict';
  if(window.__BININGA_BACKUP_UX__)return;
  window.__BININGA_BACKUP_UX__=true;

  const originalLoad=typeof window.loadBackups==='function'?window.loadBackups:null;
  const originalRun=typeof window.runBackupNow==='function'?window.runBackupNow:null;
  let serverlessMode=null;

  const q=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  const fmtBytes=n=>{
    const bytes=Number(n||0);if(!bytes)return '—';
    if(bytes<1024)return `${bytes} o`;
    if(bytes<1024*1024)return `${(bytes/1024).toFixed(1)} Ko`;
    return `${(bytes/1024/1024).toFixed(1)} Mo`;
  };

  async function fetchBackupState(){
    const res=await apiFetch('/api/backups',{headers:{'X-Admin-Token':SESSION_TOKEN},cache:'no-store'});
    const data=await res.json();
    if(!data.ok)throw new Error(data.message||'Chargement impossible');
    return data;
  }

  function configureButtons(isServerless){
    const run=q('btn-run-backup'),download=q('btn-download-backup');
    if(!run||!download)return;
    if(isServerless){
      run.textContent='Créer et télécharger une sauvegarde';
      run.title='Génère une archive complète et la télécharge immédiatement sur votre appareil.';
      download.style.display='none';
    }else{
      run.textContent='Créer une sauvegarde maintenant';
      run.title='';
      download.style.display='';
    }
  }

  function renderServerless(data){
    const list=q('backup-list');
    const rows=Array.isArray(data.backups)?data.backups:[];
    const latest=data.latest||{};
    if(q('backup-last-date'))q('backup-last-date').textContent=latest.created_at?String(latest.created_at).replace('T',' ').slice(0,16):'—';
    if(q('backup-photo-count'))q('backup-photo-count').textContent=latest.photo_count??'—';
    if(q('backup-copy-count'))q('backup-copy-count').textContent=rows.length;
    if(q('backup-storage-label'))q('backup-storage-label').textContent='archives téléchargées — historique conservé';
    if(!list)return;
    if(!rows.length){
      list.innerHTML='<div class="msg-empty">Aucune archive exportée pour le moment. Utilisez « Créer et télécharger une sauvegarde ».</div>';
      return;
    }
    list.innerHTML=rows.map(row=>`
      <div class="log-item backup-history-item">
        <div class="log-main">
          <div class="log-title">${esc(row.name||'Archive BININGA')}</div>
          <div class="log-detail">
            ${esc((row.created_at||'').replace('T',' ').slice(0,19))}
            · ${Number(row.photo_count||0)} photo(s)
            · ${Number(row.store_count||0)} bloc(s)
            · ${fmtBytes(row.bytes)}
          </div>
          <div class="log-meta">Archive exportée${row.downloaded_by?` par ${esc(row.downloaded_by)}`:''} — fichier à conserver sur votre appareil ou votre stockage sécurisé.</div>
        </div>
      </div>
    `).join('');
  }

  async function load(){
    const list=q('backup-list');
    if(list)list.innerHTML='<div class="msg-empty">Chargement…</div>';
    try{
      const data=await fetchBackupState();
      serverlessMode=data.storage?.mode==='download'||data.storage?.history_durable===true;
      configureButtons(serverlessMode);
      if(serverlessMode)renderServerless(data);
      else if(originalLoad)return await originalLoad();
    }catch(err){
      if(originalLoad)return await originalLoad();
      if(list)list.innerHTML=`<div class="msg-empty">Erreur : ${esc(err.message)}</div>`;
    }
  }

  async function run(){
    if(serverlessMode===null){
      try{const data=await fetchBackupState();serverlessMode=data.storage?.mode==='download'||data.storage?.history_durable===true;}catch(_){serverlessMode=false;}
    }
    configureButtons(serverlessMode);
    if(!serverlessMode&&originalRun)return originalRun();

    const btn=q('btn-run-backup');
    if(btn){btn.disabled=true;btn.textContent="Préparation et téléchargement…";}
    try{
      await downloadBackup();
      await load();
    }finally{
      if(btn){btn.disabled=false;btn.textContent='Créer et télécharger une sauvegarde';}
    }
  }

  window.loadBackups=load;
  window.runBackupNow=run;

  function init(){
    if(q('panel-backups'))load().catch(()=>{});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
  window.addEventListener('bininga:admin-modules-ready',()=>load().catch(()=>{}));
})();
