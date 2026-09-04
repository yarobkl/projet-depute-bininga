/* BININGA Admin — monitoring serverless presentation */
(()=>{
  'use strict';
  if(window.__BININGA_MONITORING_SERVERLESS_UI__)return;
  window.__BININGA_MONITORING_SERVERLESS_UI__=true;

  let enabled=/\.vercel\.app$/i.test(location.hostname);
  const q=id=>document.getElementById(id);

  function apply(){
    if(!enabled)return;
    const val=q('mon-val-disk');
    const bar=q('mon-bar-disk');
    const item=val&&val.closest('.mon-sys-item');
    const label=item&&item.querySelector('.mon-sys-label');
    if(label&&label.textContent!=='Disque éphémère')label.textContent='Disque éphémère';
    if(val&&val.textContent!=='N/A'){
      val.textContent='N/A';
      val.title='Le stockage local Vercel est éphémère et ne représente pas un disque serveur administrable.';
    }
    if(bar){
      bar.style.width='0%';
      bar.className='mon-bar';
      bar.title='Non applicable sur Vercel';
    }
  }

  async function detectFromServer(){
    if(enabled){apply();return;}
    try{
      const token=typeof SESSION_TOKEN!=='undefined'?SESSION_TOKEN:'';
      if(!token)return;
      const r=await fetch('/api/monitoring/summary',{headers:{'X-Admin-Token':token},cache:'no-store'});
      if(!r.ok)return;
      const d=await r.json();
      if(d&&d.system&&d.system.disk_ephemeral===true){enabled=true;apply();}
    }catch(_){}
  }

  function installObserver(){
    const panel=q('panel-monitoring');
    if(!panel)return;
    const obs=new MutationObserver(()=>apply());
    obs.observe(panel,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['style','class']});
    apply();
  }

  function init(){installObserver();detectFromServer();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
  window.addEventListener('bininga:admin-modules-ready',()=>{apply();detectFromServer();});
})();
