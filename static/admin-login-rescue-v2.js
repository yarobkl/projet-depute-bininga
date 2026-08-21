/* BININGA Admin — standalone login rescue v2
 * Rebuilds the login screen as an isolated native form so no legacy overlay,
 * sidebar listener or admin widget can intercept keyboard/touch interaction.
 */
(()=>{
  'use strict';
  if(window.__BININGA_LOGIN_RESCUE_V2__) return;
  window.__BININGA_LOGIN_RESCUE_V2__=true;

  const KEY='bininga_session';

  function visibleLogin(){
    const login=document.getElementById('login');
    return login && !login.classList.contains('hidden');
  }

  function install(){
    const login=document.getElementById('login');
    if(!login || !visibleLogin()) return;

    document.documentElement.classList.add('bininga-login-v2-active');
    document.body.classList.add('bininga-login-v2-active');
    document.body.classList.remove('sidebar-open');

    const style=document.createElement('style');
    style.id='bininga-login-v2-css';
    style.textContent=`
html.bininga-login-v2-active,body.bininga-login-v2-active{margin:0!important;min-height:100%!important;overflow:auto!important;touch-action:auto!important;background:#060606!important}
body.bininga-login-v2-active>*:not(#login):not(script){display:none!important;pointer-events:none!important}
body.bininga-login-v2-active #login{display:flex!important;position:fixed!important;inset:0!important;z-index:2147483647!important;align-items:center!important;justify-content:center!important;padding:20px!important;background:#060606!important;visibility:visible!important;opacity:1!important;pointer-events:auto!important;touch-action:auto!important;overflow:auto!important}
body.bininga-login-v2-active #login .bininga-login-v2-box{width:min(420px,100%)!important;background:#111!important;border:1px solid rgba(200,16,46,.28)!important;border-radius:16px!important;padding:38px 28px!important;box-shadow:0 30px 90px rgba(0,0,0,.55)!important;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important;color:#fff!important}
body.bininga-login-v2-active #login input{display:block!important;width:100%!important;box-sizing:border-box!important;min-height:52px!important;margin:0 0 12px!important;padding:14px 16px!important;border:1px solid rgba(255,255,255,.14)!important;border-radius:9px!important;background:#1c1c1c!important;color:#fff!important;font-size:16px!important;line-height:1.2!important;opacity:1!important;visibility:visible!important;pointer-events:auto!important;touch-action:manipulation!important;-webkit-user-select:text!important;user-select:text!important;-webkit-appearance:none!important;appearance:none!important;transform:none!important;filter:none!important;outline:none!important;position:relative!important;z-index:2!important}
body.bininga-login-v2-active #login input:focus{border-color:#C8102E!important;box-shadow:0 0 0 3px rgba(200,16,46,.16)!important}
body.bininga-login-v2-active #login button{display:block!important;width:100%!important;min-height:50px!important;margin-top:6px!important;border:0!important;border-radius:9px!important;background:#C8102E!important;color:#fff!important;font-size:15px!important;font-weight:800!important;pointer-events:auto!important;touch-action:manipulation!important;position:relative!important;z-index:2!important}
body.bininga-login-v2-active #login button:disabled{opacity:.55!important}
body.bininga-login-v2-active #login .bininga-login-v2-logo{width:58px;height:58px;border-radius:12px;background:#C8102E;display:grid;place-items:center;margin:0 auto 20px;font:800 26px Georgia,serif}
body.bininga-login-v2-active #login h1{text-align:center;font-size:21px;margin:0 0 7px}
body.bininga-login-v2-active #login p{text-align:center;font-size:12px;color:rgba(255,255,255,.48);margin:0 0 26px}
body.bininga-login-v2-active #login .bininga-login-v2-error{min-height:20px;margin-top:12px;text-align:center;color:#ff7777;font-size:12px;line-height:1.45}
`;
    document.head.appendChild(style);

    login.removeAttribute('inert');
    login.className='';
    login.innerHTML=`
      <form class="bininga-login-v2-box" id="bininga-login-v2-form" autocomplete="on" novalidate>
        <div class="bininga-login-v2-logo">B</div>
        <h1>Espace Administration</h1>
        <p>Administration du site BININGA · Accès sécurisé</p>
        <input type="text" id="u" name="username" placeholder="Identifiant" autocomplete="username" autocapitalize="none" spellcheck="false" enterkeyhint="next" aria-label="Identifiant">
        <input type="password" id="p" name="password" placeholder="Mot de passe" autocomplete="current-password" enterkeyhint="go" aria-label="Mot de passe">
        <div id="totp-row" style="display:none">
          <input type="text" id="totp" name="totp" placeholder="Code 2FA (6 chiffres)" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" aria-label="Code 2FA">
        </div>
        <button type="submit" id="bininga-login-v2-submit">Connexion</button>
        <div class="bininga-login-v2-error" id="err" role="alert" aria-live="polite"></div>
      </form>`;

    const form=document.getElementById('bininga-login-v2-form');
    const u=document.getElementById('u');
    const p=document.getElementById('p');
    const totp=document.getElementById('totp');
    const row=document.getElementById('totp-row');
    const btn=document.getElementById('bininga-login-v2-submit');
    const err=document.getElementById('err');

    // Native inputs should focus by themselves. These listeners only ensure
    // no legacy code can leave them disabled/readOnly after the rebuild.
    [u,p,totp].forEach(field=>{
      if(!field) return;
      const enable=()=>{ field.disabled=false; field.readOnly=false; field.removeAttribute('inert'); };
      field.addEventListener('pointerdown',enable,{passive:true});
      field.addEventListener('touchstart',enable,{passive:true});
      field.addEventListener('focus',enable,{passive:true});
    });

    form.addEventListener('submit',async ev=>{
      ev.preventDefault();
      const username=u.value.trim();
      const password=p.value;
      const code=(totp.value||'').trim();
      if(!username || !password){ err.textContent='Saisissez votre identifiant et votre mot de passe.'; return; }
      btn.disabled=true;
      btn.textContent='Connexion…';
      err.textContent='';
      try{
        const payload={username,password};
        if(code) payload.totp_code=code;
        const res=await fetch('/api/login',{
          method:'POST',
          headers:{'Content-Type':'application/json','Accept':'application/json'},
          body:JSON.stringify(payload),
          credentials:'same-origin',
          cache:'no-store'
        });
        const data=await res.json().catch(()=>({ok:false,message:'Réponse serveur invalide.'}));
        if(data.ok){
          const ttlSeconds=Math.max(60,Number(data.session_ttl||72*3600));
          const saved={
            token:data.token,
            csrf:data.csrf_token||data.csrf||'',
            role:data.role,
            nom:data.nom,
            username:data.username||username,
            is_main_admin:!!data.is_main_admin,
            has_2fa:!!data.has_2fa,
            trusted_ip:!!data.trusted_ip,
            session_duration:data.session_duration||'',
            expires_at:Date.now()+ttlSeconds*1000
          };
          try{ localStorage.removeItem(KEY); }catch(_){}
          sessionStorage.setItem(KEY,JSON.stringify(saved));
          window.location.reload();
          return;
        }
        if(data.require_2fa){
          row.style.display='block';
          err.textContent='Entrez votre code 2FA.';
          try{totp.focus();}catch(_){}
        }else{
          err.textContent=data.message||'Identifiant ou mot de passe incorrect.';
        }
      }catch(_){
        err.textContent='Connexion serveur impossible. Réessayez.';
      }finally{
        btn.disabled=false;
        btn.textContent='Connexion';
      }
    });
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
