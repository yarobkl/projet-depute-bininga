/* BININGA Admin — mobile navigation interaction fix v3
 * One deterministic state machine for both red menu buttons.
 * Key fix: never auto-close the drawer on mobile resize/viewport chrome changes.
 */
(() => {
  'use strict';
  if (window.__BININGA_MOBILE_NAV_FIX_V3__) return;
  window.__BININGA_MOBILE_NAV_FIX_V3__ = true;

  const isMobile = () => window.matchMedia('(max-width: 768px)').matches;
  let openState = false;
  let installed = false;
  let lastTap = 0;

  const get = () => ({
    body: document.body,
    sidebar: document.getElementById('sidebar'),
    overlay: document.getElementById('sidebar-overlay'),
    hamburger: document.getElementById('hamburger'),
    main: document.querySelector('.main')
  });

  function ensureFab() {
    let fab = document.getElementById('bininga-mobile-menu-fab');
    if (!fab) {
      fab = document.createElement('button');
      fab.id = 'bininga-mobile-menu-fab';
      fab.type = 'button';
      fab.innerHTML = '&#9776;';
      fab.setAttribute('aria-label', 'Ouvrir le menu administration');
      fab.style.cssText = [
        'position:fixed','left:0','top:50%','transform:translateY(-50%)',
        'width:42px','height:68px','border:0','border-radius:0 12px 12px 0',
        'background:#C8102E','color:#fff','font-size:24px','font-weight:800',
        'display:flex','align-items:center','justify-content:center',
        'z-index:2147483647','pointer-events:auto','touch-action:manipulation',
        '-webkit-tap-highlight-color:transparent','box-shadow:3px 0 18px rgba(0,0,0,.35)'
      ].join(';');
      document.body.appendChild(fab);
    }
    return fab;
  }

  function render(open) {
    const { body, sidebar, overlay, hamburger, main } = get();
    if (!body || !sidebar) return;
    openState = !!open;

    body.classList.toggle('sidebar-open', openState);
    sidebar.classList.toggle('open', openState);
    sidebar.classList.remove('active');
    sidebar.style.setProperty('display', 'block', 'important');
    sidebar.style.setProperty('left', openState ? '0px' : '-110vw', 'important');
    sidebar.style.setProperty('transform', openState ? 'translate3d(0,0,0)' : 'translate3d(-110%,0,0)', 'important');
    sidebar.style.setProperty('visibility', openState ? 'visible' : 'hidden', 'important');
    sidebar.style.setProperty('pointer-events', openState ? 'auto' : 'none', 'important');
    sidebar.style.setProperty('z-index', '2147483646', 'important');

    if (overlay) {
      overlay.classList.toggle('open', openState);
      overlay.classList.remove('active');
      overlay.style.setProperty('display', openState ? 'block' : 'none', 'important');
      overlay.style.setProperty('visibility', openState ? 'visible' : 'hidden', 'important');
      overlay.style.setProperty('pointer-events', openState ? 'auto' : 'none', 'important');
      overlay.style.setProperty('z-index', '2147483645', 'important');
    }

    if (main) {
      main.style.setProperty('pointer-events', 'auto', 'important');
      main.style.setProperty('touch-action', 'auto', 'important');
    }

    const fab = ensureFab();
    fab.innerHTML = openState ? '&#10005;' : '&#9776;';
    fab.setAttribute('aria-label', openState ? 'Fermer le menu administration' : 'Ouvrir le menu administration');

    if (hamburger) {
      hamburger.setAttribute('aria-expanded', openState ? 'true' : 'false');
      hamburger.style.setProperty('pointer-events', 'auto', 'important');
      hamburger.style.setProperty('touch-action', 'manipulation', 'important');
      hamburger.style.setProperty('z-index', '2147483647', 'important');
    }
  }

  function toggleFromEvent(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const now = Date.now();
    if (now - lastTap < 250) return;
    lastTap = now;
    render(!openState);
  }

  function bindTap(el, handler) {
    if (!el || el.dataset.biningaNavBoundV3 === '1') return;
    el.dataset.biningaNavBoundV3 = '1';
    el.removeAttribute('onclick');
    el.addEventListener('touchend', handler, { passive:false });
    el.addEventListener('click', handler, { passive:false });
  }

  function install() {
    if (!isMobile()) return;
    const { sidebar, overlay, hamburger, main } = get();
    if (!sidebar || !main) return;

    const fab = ensureFab();
    bindTap(fab, toggleFromEvent);
    bindTap(hamburger, toggleFromEvent);

    if (overlay && overlay.dataset.biningaOverlayBoundV3 !== '1') {
      overlay.dataset.biningaOverlayBoundV3 = '1';
      overlay.removeAttribute('onclick');
      overlay.addEventListener('touchend', (e) => { e.preventDefault(); render(false); }, { passive:false });
      overlay.addEventListener('click', (e) => { e.preventDefault(); render(false); }, { passive:false });
    }

    if (!installed) {
      sidebar.querySelectorAll('.sb-item').forEach((item) => {
        item.addEventListener('click', () => setTimeout(() => render(false), 50), { passive:true });
      });
      installed = true;
      render(false);
    } else {
      render(openState);
    }

    window.toggleSidebar = () => render(!openState);
    window.closeSidebar = () => render(false);
    window.openSidebar = () => render(true);
  }

  window.addEventListener('pageshow', install, { passive:true });
  // Important on iOS: viewport/browser chrome resizes must NOT close the drawer.
  window.addEventListener('resize', () => { if (isMobile()) requestAnimationFrame(() => render(openState)); }, { passive:true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once:true });
  else install();
})();
