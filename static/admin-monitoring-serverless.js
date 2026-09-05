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
    }
    if(val&&val.title!=='Le stockage local Vercel est éphémère et ne représente pas un disque serveur administrable.')val.title='Le stockage local Vercel est éphémère et ne représente pas un disque serveur administrable.';
    if(bar){
      if(bar.style.width!=='0%')bar.style.width='0%';
      if(bar.className!=='mon-bar')bar.className='mon-bar';
      if(bar.title!=='Non applicable sur Vercel')bar.title='Non applicable sur Vercel';
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

  function patchMonitoringLoader(){
    const original=window.loadMonitoring;
    if(typeof original!=='function'||original.__biningaServerlessUi)return;
    const wrapped=async function(...args){
      try{return await original.apply(this,args)}
      finally{apply()}
    };
    wrapped.__biningaServerlessUi=true;
    window.loadMonitoring=wrapped;
  }

  function init(){patchMonitoringLoader();apply();detectFromServer();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
  window.addEventListener('admin:panelchange',event=>{if(event.detail&&event.detail.name==='monitoring')setTimeout(apply,0)});
  window.addEventListener('bininga:admin-modules-ready',()=>{patchMonitoringLoader();apply();detectFromServer();});
})();
