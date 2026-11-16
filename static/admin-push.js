/* Owner-only APNs composer. Text is rendered with textContent, never HTML. */
(() => {
  const byId = id => document.getElementById(id);
  const status = text => { byId('push-status').textContent = text; };
  let busy = false;
  async function api(payload) {
    const response = await apiFetch('/api/push/admin', payload ? {
      method: 'POST', headers: {'Content-Type':'application/json','X-Admin-Token':SESSION_TOKEN,'X-CSRF-Token':SESSION_CSRF}, body: JSON.stringify(payload)
    } : {headers:{'X-Admin-Token':SESSION_TOKEN},cache:'no-store'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || 'Service indisponible');
    return data;
  }
  const labels = {draft:'Brouillon',sending:'En cours — ne pas renvoyer',accepted:'Accepté par Apple — réception non confirmée',rejected:'Refusé par Apple',unknown:'Résultat indéterminé — vérifier avant de renvoyer'};
  async function load() {
    try {
      const data = await api();
      status(data.configured ? 'Connexion APNs configurée. Un appareil doit autoriser les notifications dans l’application.' : 'Clé APNs absente du déploiement.');
      const select=byId('push-device'); select.replaceChildren(new Option('Choisir un appareil inscrit',''));
      data.devices.forEach(id=>select.add(new Option('Appareil '+id.slice(0,12),id)));
      const history=byId('push-history');history.replaceChildren();
      if (!data.messages.length) history.textContent='Aucun brouillon ni envoi.';
      data.messages.forEach(item=>{
        const card=document.createElement('article');card.className='card';
        const title=document.createElement('h3');title.textContent=item.title;
        const body=document.createElement('p');body.textContent=item.body;
        const state=document.createElement('p');state.textContent=labels[item.status]||item.status;
        card.append(title,body,state);
        if(item.status==='draft') {
          const send=document.createElement('button');send.className='btn-primary';send.textContent='Envoyer sur l’appareil sélectionné';
          send.addEventListener('click',()=>perform(async()=>{
            if(!select.value) throw new Error('Sélectionnez un appareil inscrit.');
            if(!confirm('Envoyer « '+item.title+' » sur cet appareil ?')) return;
            const result=await api({action:'send',id:item.id,device:select.value});
            await load();status(labels[result.status]||result.status);
          }));card.append(send);
        }
        history.append(card);
      });
    } catch(error) { status(error.message); }
  }
  async function perform(action) {
    if(busy)return;busy=true;
    byId('push-compose').querySelectorAll('button').forEach(el=>el.disabled=true);
    try{await action();}catch(error){status(error.message);}finally{
      busy=false;byId('push-compose').querySelectorAll('button').forEach(el=>el.disabled=false);
    }
  }
  document.addEventListener('DOMContentLoaded',()=>{
    byId('push-compose').addEventListener('submit',event=>{
      event.preventDefault();perform(async()=>{
        await api({action:'draft',title:byId('push-title').value,body:byId('push-body').value});
        byId('push-compose').reset();await load();status('Brouillon enregistré. Aucun envoi effectué.');
      });
    });
    const preview=()=>{byId('push-preview-title').textContent=byId('push-title').value||'Titre';byId('push-preview-body').textContent=byId('push-body').value||'Message';};
    byId('push-title').addEventListener('input',preview);byId('push-body').addEventListener('input',preview);
    byId('push-refresh').addEventListener('click',load);
    window.addEventListener('admin:panelchange',event=>{if(event.detail?.name==='push')load();});
  });
})();
