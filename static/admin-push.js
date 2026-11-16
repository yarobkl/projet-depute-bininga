/* Owner-only APNs publication. All dynamic content uses textContent. */
(() => {
  const byId = id => document.getElementById(id);
  const status = text => { byId('push-status').textContent = text; };
  let busy = false, audienceCount = 0;
  const labels = {draft:'Brouillon',queued:'Diffusion en cours',complete:'Diffusion terminée',sending:'Ancien test en cours — ne pas renvoyer',accepted:'Accepté par Apple — réception non confirmée',rejected:'Refusé par Apple',unknown:'Résultat indéterminé — ne pas renvoyer automatiquement'};
  async function api(payload) {
    const response = await apiFetch('/api/push/admin', payload ? {
      method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':SESSION_TOKEN,'X-CSRF-Token':SESSION_CSRF},body:JSON.stringify(payload)
    } : {headers:{'X-Admin-Token':SESSION_TOKEN},cache:'no-store'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || 'Service indisponible');
    return data;
  }
  function report(result) {
    return `${result.accepted || 0} accepté(s) par Apple · ${result.rejected || 0} refusé(s) · ${result.unknown || 0} indéterminé(s) · ${result.skipped || 0} désactivé(s) · ${result.pending || 0} restant(s)`;
  }
  async function dispatch(id) {
    let remaining;
    do {
      const data = await api({action:'dispatch',id});
      remaining = data.result.pending;
      status(report(data.result));
      if (remaining) await new Promise(resolve => setTimeout(resolve, 1000));
    } while (remaining);
    await load();
  }
  async function load() {
    try {
      const data = await api();
      audienceCount = data.audience_count;
      status(data.configured ? 'APNs configuré. La réception dépend de la connexion et des réglages iOS.' : 'Clé APNs absente du déploiement.');
      byId('push-audience').textContent = `${audienceCount} appareil(s) ayant autorisé les notifications. Chaque publication est adressée à toute cette audience.`;
      const history = byId('push-history'); history.replaceChildren();
      if (!data.messages.length) history.textContent = 'Aucun brouillon ni envoi.';
      data.messages.forEach(item => {
        const card = document.createElement('article'); card.className = 'card';
        const title = document.createElement('h3'); title.textContent = item.title;
        const body = document.createElement('p'); body.textContent = item.body;
        const state = document.createElement('p'); state.textContent = labels[item.status] || item.status;
        card.append(title,body,state);
        if (item.result && Number.isInteger(item.result.total)) {
          const counts = document.createElement('p'); counts.textContent = report(item.result); card.append(counts);
        }
        if (item.status === 'draft' || item.status === 'queued') {
          const send = document.createElement('button'); send.type='button';
          send.textContent = item.status === 'draft' ? 'Envoyer à tous les abonnés' : 'Reprendre la diffusion';
          send.disabled = busy || (item.status === 'draft' && (!data.configured || audienceCount === 0));
          send.addEventListener('click', () => perform(async () => {
            if (item.status === 'draft') {
              if (!confirm(`Envoyer « ${item.title} » à tous les appareils ayant autorisé les notifications (actuellement ${audienceCount}) ?`)) return;
              await api({action:'send',id:item.id,audience:'all_authorized'});
            }
            await dispatch(item.id);
          }));
          card.append(send);
        }
        history.append(card);
      });
    } catch (error) { status(error.message); }
  }
  async function perform(action) {
    if (busy) return;
    busy = true;
    document.querySelectorAll('#panel-push button').forEach(el => el.disabled = true);
    let failure;
    try { await action(); }
    catch (error) { failure = error.message + ' Une diffusion interrompue reste dans l’historique et peut être reprise sans renvoyer aux appareils déjà traités.'; }
    finally {
      busy = false;
      byId('push-compose').querySelectorAll('button').forEach(el => el.disabled = false);
      byId('push-refresh').disabled = false;
      // Refresh recovers the state after an ambiguous network error; never repost send.
      await load();
      if (failure) status(failure);
    }
  }
  function install() {
    byId('push-compose').addEventListener('submit',event => {
      event.preventDefault(); perform(async () => {
        await api({action:'draft',title:byId('push-title').value,body:byId('push-body').value});
        byId('push-compose').reset(); preview();
      });
    });
    function preview() {
      byId('push-preview-title').textContent = byId('push-title').value || 'Titre';
      byId('push-preview-body').textContent = byId('push-body').value || 'Message';
    }
    byId('push-title').addEventListener('input',preview);
    byId('push-body').addEventListener('input',preview);
    byId('push-refresh').addEventListener('click',load);
    let active = false;
    const syncPanel = () => {
      const next = byId('panel-push').classList.contains('active');
      if (next && !active) {
        const title = byId('topbar-title'); if (title) title.textContent = 'Notifications iPhone';
        load();
      }
      active = next;
    };
    new MutationObserver(syncPanel).observe(byId('panel-push'),{attributes:true,attributeFilter:['class']});
    syncPanel();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
