/* BININGA Admin — vues métier Messages / Audiences / Réclamations
 * Présentation type messagerie / gestion de dossiers, sans perdre les données
 * techniques ni les actions serveur existantes.
 *
 * ⚠️  Do NOT wrap window.showPanel here. Listen to 'admin:panelchange' instead.
 * This module is loaded AFTER admin-navigation.js defines the centralized
 * navigation functions. Wrapping showPanel creates fragile chained dependencies.
 */
(()=>{
  'use strict';
  if (window.__BININGA_CASES_UI__) return;
  window.__BININGA_CASES_UI__ = true;

  const E = value => typeof window.esc === 'function'
    ? window.esc(String(value ?? ''))
    : String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const enc = value => encodeURIComponent(String(value ?? ''));
  const clean = value => String(value ?? '').trim();

  function installCss(){
    if (document.getElementById('bininga-cases-css')) return;
    const style = document.createElement('style');
    style.id = 'bininga-cases-css';
    style.textContent = `
.case-list{display:grid;gap:12px}.case-card{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.075);border-radius:14px;overflow:hidden;transition:border-color .16s,background .16s}.case-card:hover{border-color:rgba(184,151,58,.22);background:rgba(255,255,255,.035)}
.case-head{display:flex;align-items:flex-start;gap:11px;padding:15px 16px 12px}.case-avatar{width:38px;height:38px;flex:0 0 38px;border-radius:50%;display:grid;place-items:center;background:rgba(184,151,58,.12);border:1px solid rgba(184,151,58,.24);font-weight:800;font-size:12px;color:#e3c978}.case-ident{min-width:0;flex:1}.case-name{font-size:13px;font-weight:800;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.case-subline{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-top:4px;font-size:10px;color:rgba(255,255,255,.42)}.case-source{color:#d0ad4e}.case-status{flex:0 0 auto}
.case-main{padding:0 16px 14px}.case-subject{font-size:12px;font-weight:750;color:rgba(255,255,255,.88);margin:2px 0 8px}.case-message{font-size:12px;line-height:1.65;color:rgba(255,255,255,.68);white-space:pre-wrap;overflow-wrap:anywhere}.case-contact{display:flex;gap:8px;flex-wrap:wrap;margin-top:11px}.case-contact a,.case-contact span{font-size:10px;padding:6px 9px;border-radius:8px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07);color:rgba(255,255,255,.66);text-decoration:none}.case-contact a:hover{border-color:rgba(184,151,58,.28);color:#e3c978}
.case-evidence{margin-top:12px;display:grid;gap:9px}.case-evidence img{max-width:260px;max-height:180px;border-radius:10px;object-fit:cover;border:1px solid rgba(255,255,255,.08)}.case-location{font-size:10px;color:rgba(255,255,255,.48)}.case-location a{color:#d0ad4e;text-decoration:none}
.case-details{margin:0 16px 12px;padding-top:9px;border-top:1px dashed rgba(255,255,255,.07)}.case-details summary{cursor:pointer;font-size:10px;color:rgba(255,255,255,.32)}.case-tech-grid{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.case-tech{font-size:9px;color:rgba(255,255,255,.38);padding:4px 7px;border-radius:7px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.05)}
.case-notes{margin:0 16px 13px;padding:11px;border-radius:10px;background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.055)}.case-notes-title{font-size:10px;font-weight:800;color:rgba(255,255,255,.55);margin-bottom:8px}.case-note{padding:7px 0;border-top:1px solid rgba(255,255,255,.05)}.case-note:first-of-type{border-top:0}.case-note-meta{font-size:9px;color:rgba(255,255,255,.28);margin-bottom:3px}.case-note-text{font-size:11px;line-height:1.5;color:rgba(255,255,255,.62)}.case-note-form{display:flex;gap:7px;margin-top:9px}.case-note-form textarea{flex:1;min-height:38px;resize:vertical;background:var(--n3);border:1px solid rgba(255,255,255,.08);border-radius:8px;color:#fff;padding:8px;font:inherit;font-size:11px}.case-note-form button{align-self:flex-end}
.case-actions{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding:11px 16px;background:rgba(0,0,0,.11);border-top:1px solid rgba(255,255,255,.055)}.case-actions-label{font-size:9px;color:rgba(255,255,255,.3);margin-right:2px}.case-actions .sbtn{min-height:30px}.case-actions .is-current{outline:1px solid currentColor;outline-offset:1px}.case-pinged{font-size:9px;color:#e57f74;margin-left:auto}
@media(max-width:620px){.case-head{padding:13px 13px 10px}.case-main,.case-actions{padding-left:13px;padding-right:13px}.case-details,.case-notes{margin-left:13px;margin-right:13px}.case-avatar{width:34px;height:34px;flex-basis:34px}.case-actions{align-items:stretch}.case-actions .sbtn,.case-actions a.sbtn{flex:1 1 auto;text-align:center;justify-content:center}.case-note-form{flex-direction:column}.case-note-form button{align-self:stretch}.case-evidence img{max-width:100%}}
`;
    document.head.appendChild(style);
  }

  const HIDDEN = new Set([
    '_id','id','_status','_reply','_reply_date','_pinged','_pinged_date','_notes',
    'geo_lat','geo_lng','geo_label','geo_maps_url','photo_url','description','raison','message',
    'prenom','nom','email','telephone','tel','objet','sujet','source','type','_date','ts','created_at'
  ]);
  const TECH = /^(ip|user.?agent|ua|fingerprint|session|token|request.?id|referer|referrer|timestamp|ts)$/i;

  function initials(m){
    const p=clean(m.prenom), n=clean(m.nom), value=(p[0]||'')+(n[0]||'');
    return (value || clean(m.email).slice(0,2) || '??').toUpperCase();
  }
  function dateOf(m){return clean(m._date||m.ts||m.created_at||'');}
  function subjectOf(m, kind){
    return clean(m.objet||m.sujet||(kind==='recl'?'Réclamation':kind==='aud'?'Demande d’audience':'Message'));
  }
  function messageOf(m){return clean(m.raison||m.message||m.description||'');}
  function sourceOf(m,kind){
    if (kind==='recl') return 'Réclamation citoyenne';
    if (kind==='aud') return 'Demande d’audience';
    return clean(m.source_label||m.source||m.type||'Formulaire de contact').replace(/^bininga_/,'');
  }
  function statusOf(m,mode){return clean(m._status)||(mode==='status2'?'non_lu':'en_attente');}
  function statusBadge(status,kind){
    if (typeof window.buildBadge === 'function') return window.buildBadge(status, kind==='recl'?'Réclamation':'');
    return `<span class="badge">${E(status)}</span>`;
  }
  function recordId(m, allData){
    const id=clean(m._id||m.id); if(id) return enc(id);
    const idx=allData.findIndex(x=>x===m || (x._date===m._date&&x.prenom===m.prenom&&x.nom===m.nom));
    return String(Math.max(0,idx));
  }
  function technicalHtml(m){
    const rows=[];
    Object.entries(m||{}).forEach(([k,v])=>{
      if (HIDDEN.has(k) || k.startsWith('_')) return;
      if (v==null || v==='' || typeof v==='object') return;
      const cls=TECH.test(k)?' data-tech="1"':'';
      rows.push(`<span class="case-tech"${cls}><b>${E(k)}</b> · ${E(v)}</span>`);
    });
    // explicitly keep useful technical metadata hidden but accessible
    ['ip','IP','user_agent','ua','fingerprint','session_id','request_id','tracking_code'].forEach(k=>{
      if (m[k]!=null && m[k]!=='' && !rows.some(r=>r.includes(`<b>${E(k)}</b>`))) rows.push(`<span class="case-tech" data-tech="1"><b>${E(k)}</b> · ${E(m[k])}</span>`);
    });
    return rows.join('');
  }
  function contactHtml(m){
    const out=[];
    const email=clean(m.email), tel=clean(m.telephone||m.tel);
    if(email) out.push(`<a href="mailto:${E(email)}">✉ ${E(email)}</a>`);
    if(tel) out.push(`<a href="tel:${E(tel)}">☎ ${E(tel)}</a>`);
    const tracking=clean(m.tracking_code); if(tracking) out.push(`<span>Suivi · ${E(tracking)}</span>`);
    return out.join('');
  }
  function evidenceHtml(m){
    const chunks=[];
    if(m.photo_url) chunks.push(`<img src="${E(m.photo_url)}" alt="Pièce jointe du dossier" loading="lazy">`);
    if(m.geo_lat&&m.geo_lng){
      const url=clean(m.geo_maps_url)||`https://www.google.com/maps?q=${encodeURIComponent(m.geo_lat)},${encodeURIComponent(m.geo_lng)}`;
      chunks.push(`<div class="case-location">📍 ${E(m.geo_label||`${m.geo_lat}, ${m.geo_lng}`)} · <a href="${E(url)}" target="_blank" rel="noopener">Ouvrir la carte</a></div>`);
    }
    return chunks.length?`<div class="case-evidence">${chunks.join('')}</div>`:'';
  }
  function notesHtml(m,storageKey,btnId){
    const notes=Array.isArray(m._notes)?m._notes:[];
    return `<div class="case-notes"><div class="case-notes-title">Notes internes</div>${notes.length?notes.map(n=>`<div class="case-note"><div class="case-note-meta">${E(n.auteur||'Admin')} · ${E(n.date||'')}</div><div class="case-note-text">${E(n.texte||'')}</div></div>`).join(''):'<div class="case-note-text" style="opacity:.45">Aucune note pour ce dossier.</div>'}<div class="case-note-form"><textarea id="note-ta-${btnId}" rows="2" placeholder="Ajouter une note interne…"></textarea><button class="sbtn sbtn-progress" onclick="addNote('${storageKey}','${btnId}')">Ajouter la note</button></div></div>`;
  }
  function actionsHtml(m,storageKey,btnId,mode,kind,status){
    const email=clean(m.email), tel=clean(m.telephone||m.tel), name=`${clean(m.prenom)} ${clean(m.nom)}`.trim();
    let statusActions='';
    if(mode==='status3'){
      statusActions=['en_attente','en_cours','traite'].map(s=>{
        const labels={en_attente:'En attente',en_cours:'En cours',traite:'Traité'};
        const cls={en_attente:'sbtn-wait',en_cours:'sbtn-progress',traite:'sbtn-done'};
        return `<button class="sbtn ${cls[s]}${status===s?' is-current':''}" onclick="setStatus('${storageKey}','${btnId}','${s}')">${labels[s]}</button>`;
      }).join('');
    }else{
      statusActions=`<button class="sbtn sbtn-read${status==='lu'?' is-current':''}" onclick="setStatus('${storageKey}','${btnId}','lu')">${status==='lu'?'Lu':'Marquer lu'}</button>`;
    }
    const reply=email?`<a class="sbtn sbtn-progress" href="mailto:${E(email)}?subject=${enc('Réponse — Cabinet Aimé BININGA')}&body=${enc(`Bonjour ${name},\n\n`)}" style="text-decoration:none">Répondre</a>`:'';
    const call=tel?`<a class="sbtn" href="tel:${E(tel)}" style="text-decoration:none">Appeler</a>`:'';
    const ping=m._pinged?`<span class="case-pinged">Député alerté${m._pinged_date?` · ${E(m._pinged_date)}`:''}</span>`:`<button class="sbtn" onclick="pingDepute('${storageKey}','${btnId}')">Alerter le Député</button>`;
    return `<div class="case-actions"><span class="case-actions-label">Traitement</span>${statusActions}${reply}${call}${ping}</div>`;
  }

  window.renderMsgList = function renderMsgListProfessional(containerId,list,storageKey,mode){
    installCss();
    const el=document.getElementById(containerId); if(!el) return;
    el.classList.add('case-list');
    if(!Array.isArray(list)||!list.length){el.innerHTML='<div class="msg-empty">Aucun dossier dans cette catégorie.</div>';return;}
    const allData=typeof window.getAll==='function'?window.getAll(storageKey):list;
    const kind=containerId.includes('reclam')?'recl':containerId.includes('audience')?'aud':'msg';
    el.innerHTML=list.map(m=>{
      const btnId=recordId(m,allData), status=statusOf(m,mode), name=`${clean(m.prenom)} ${clean(m.nom)}`.trim()||clean(m.email)||'Demandeur';
      const subject=subjectOf(m,kind), body=messageOf(m), technical=technicalHtml(m), contacts=contactHtml(m);
      return `<article class="case-card" data-case-id="${btnId}" data-status="${E(status)}">
        <header class="case-head"><div class="case-avatar">${E(initials(m))}</div><div class="case-ident"><div class="case-name">${E(name)}</div><div class="case-subline"><span class="case-source">${E(sourceOf(m,kind))}</span>${dateOf(m)?`<span>·</span><span>${E(dateOf(m))}</span>`:''}</div></div><div class="case-status">${statusBadge(status,kind)}</div></header>
        <div class="case-main"><div class="case-subject">${E(subject)}</div>${body?`<div class="case-message">${E(body)}</div>`:'<div class="case-message" style="opacity:.4">Aucun texte complémentaire.</div>'}${contacts?`<div class="case-contact">${contacts}</div>`:''}${evidenceHtml(m)}</div>
        ${technical?`<details class="case-details"><summary>Informations complémentaires et techniques</summary><div class="case-tech-grid">${technical}</div></details>`:''}
        ${notesHtml(m,storageKey,btnId)}${actionsHtml(m,storageKey,btnId,mode,kind,status)}
      </article>`;
    }).join('');
  };

  // Sync dossiers via event listener, not by wrapping showPanel
  window.addEventListener('admin:panelchange', (e) => {
    const name = e.detail.name;
    if (['audiences','reclamations','contacts'].includes(name) && typeof window.syncMessages==='function'){
      Promise.resolve(window.syncMessages()).then(()=>{
        if(name==='audiences'&&typeof window.renderAudiences==='function') window.renderAudiences();
        else if(name==='reclamations'&&typeof window.renderReclamations==='function') window.renderReclamations();
        else if(name==='contacts'&&typeof window.renderContacts==='function') window.renderContacts();
      }).catch(err=>{
        console.warn('[BININGA Admin] sync dossiers',err);
        if(typeof window.showToast==='function') window.showToast('Synchronisation des dossiers impossible',true);
      });
    }
  });

  installCss();
  console.info('[BININGA Admin] Vues métier dossiers actives');
})();
