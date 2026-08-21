/* BININGA Admin — login interaction rescue
 * Isolates the login layer from every admin overlay/sidebar and forces real
 * focusable inputs on mobile Safari/Chrome and desktop browsers.
 */
(()=>{
  'use strict';
  if(window.__BININGA_LOGIN_RESCUE__) return;
  window.__BININGA_LOGIN_RESCUE__=true;

  const ids=['u','p','totp'];
  const blockers=['sidebar-overlay','sidebar','sb-pull','upload-progress-wrap','app'];
  const hiddenState=new Map();

  function setStyle(el,key,value){
    if(!el) return;
    const token=el.id+':'+key;
    if(!hiddenState.has(token)) hiddenState.set(token,el.style[key]||'');
    el.style[key]=value;
  }

  function restoreStyle(el,key){
    if(!el) return;
    const token=el.id+':'+key;
    if(hiddenState.has(token)){
      el.style[key]=hiddenState.get(token);
      hiddenState.delete(token);
    }
  }

  function focusField(field){
    if(!field) return;
    field.disabled=false;
    field.readOnly=false;
    field.removeAttribute('inert');
    field.tabIndex=0;
    field.style.pointerEvents='auto';
    field.style.touchAction='manipulation';
    field.style.userSelect='text';
    field.style.webkitUserSelect='text';
    field.style.position='relative';
    field.style.zIndex='2147483647';
    field.style.opacity='1';
    try{ field.focus({preventScroll:true}); }catch(_){ try{field.focus();}catch(__){} }
  }

  function sync(){
    const login=document.getElementById('login');
    if(!login) return;
    const active=!login.classList.contains('hidden');
    document.documentElement.classList.toggle('bininga-login-active',active);
    document.body.classList.toggle('bininga-login-active',active);

    if(active){
      document.body.classList.remove('sidebar-open');
      login.removeAttribute('inert');
      login.style.display='flex';
      login.style.visibility='visible';
      login.style.opacity='1';
      login.style.pointerEvents='auto';
      login.style.touchAction='auto';
      login.style.zIndex='2147483647';
      const box=login.querySelector('.login-box');
      if(box){
        box.style.position='relative';
        box.style.zIndex='2147483647';
        box.style.pointerEvents='auto';
        box.style.touchAction='auto';
      }
      blockers.forEach(id=>{
        const el=document.getElementById(id);
        if(!el || el===login) return;
        setStyle(el,'pointerEvents','none');
        setStyle(el,'visibility','hidden');
      });
      ids.forEach(id=>{
        const field=document.getElementById(id);
        if(!field) return;
        field.disabled=false;
        field.readOnly=false;
        field.removeAttribute('inert');
        field.tabIndex=0;
        field.style.pointerEvents='auto';
        field.style.touchAction='manipulation';
        field.style.userSelect='text';
        field.style.webkitUserSelect='text';
        field.style.position='relative';
        field.style.zIndex='2147483647';
      });
    }else{
      blockers.forEach(id=>{
        const el=document.getElementById(id);
        if(!el) return;
        restoreStyle(el,'pointerEvents');
        restoreStyle(el,'visibility');
      });
    }
  }

  function installFocusRescue(){
    ids.forEach(id=>{
      const field=document.getElementById(id);
      if(!field || field.dataset.loginRescue==='1') return;
      field.dataset.loginRescue='1';
      const activate=()=>focusField(field);
      field.addEventListener('pointerdown',activate,{passive:true});
      field.addEventListener('touchstart',activate,{passive:true});
      field.addEventListener('click',activate,{passive:true});
    });
  }

  function install(){
    const style=document.createElement('style');
    style.id='bininga-login-rescue-css';
    style.textContent=`
html.bininga-login-active,body.bininga-login-active{overflow:auto!important;touch-action:auto!important}
body.bininga-login-active #login{display:flex!important;visibility:visible!important;opacity:1!important;pointer-events:auto!important;touch-action:auto!important;z-index:2147483647!important}
body.bininga-login-active #login .login-box{position:relative!important;z-index:2147483647!important;pointer-events:auto!important;touch-action:auto!important}
body.bininga-login-active #login input,body.bininga-login-active #login button{position:relative!important;z-index:2147483647!important;pointer-events:auto!important;touch-action:manipulation!important;-webkit-user-select:text!important;user-select:text!important}
body.bininga-login-active #sidebar-overlay,body.bininga-login-active #sidebar,body.bininga-login-active #sb-pull,body.bininga-login-active #app{pointer-events:none!important;visibility:hidden!important}
`;
    if(!document.getElementById(style.id)) document.head.appendChild(style);
    installFocusRescue();
    sync();
    const login=document.getElementById('login');
    if(login) new MutationObserver(()=>{sync();installFocusRescue();}).observe(login,{attributes:true,attributeFilter:['class','style']});
    window.addEventListener('pageshow',()=>{sync();installFocusRescue();});
    window.addEventListener('resize',sync,{passive:true});
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
