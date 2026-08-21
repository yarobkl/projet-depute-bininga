/* BININGA Admin — mobile navigation interaction fix v2
 * Uses a dedicated always-visible mobile menu trigger and hard-resets stale
 * sidebar/overlay states that can make the whole admin untouchable on iOS.
 */
(() => {
  'use strict';
  if (window.__BININGA_MOBILE_NAV_FIX_V2__) return;
  window.__BININGA_MOBILE_NAV_FIX_V2__ = true;

  const mobile = () => window.matchMedia('(max-width: 768px)').matches;

  function refs() {
    return {
      body: document.body,
      sidebar: document.getElementById('sidebar'),
      overlay: document.getElementById('sidebar-overlay'),
      hamburger: document.getElementById('hamburger'),
      main: document.querySelector('.main')
    };
  }

  function isOpen() {
    const { body, sidebar } = refs();
    return !!(body?.classList.contains('sidebar-open') || sidebar?.classList.contains('open'));
  }

  function ensureFab() {
    let fab = document.getElementById('bininga-mobile-menu-fab');
    if (fab) return fab;
    fab = document.createElement('button');
    fab.id = 'bininga-mobile-menu-fab';
    fab.type = 'button';
    fab.setAttribute('aria-label', 'Ouvrir le menu administration');
    fab.innerHTML = '&#9776;';
    fab.style.cssText = [
      'position:fixed','left:0','top:50%','transform:translateY(-50%)',
      'width:42px','height:68px','border:0','border-radius:0 12px 12px 0',
      'background:#C8102E','color:#fff','font-size:24px','font-weight:800',
      'display:flex','align-items:center','justify-content:center',
      'z-index:2147483646','pointer-events:auto','touch-action:manipulation',
      '-webkit-tap-highlight-color:transparent','box-shadow:3px 0 18px rgba(0,0,0,.35)'
    ].join(';');
    document.body.appendChild(fab);
    fab.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      setOpen(!isOpen());
    }, { passive:false });
    return fab;
  }

  function setOpen(open) {
    const { body, sidebar, overlay, hamburger, main } = refs();
    if (!body || !sidebar) return;

    body.classList.toggle('sidebar-open', open);
    sidebar.classList.toggle('open', open);
    sidebar.classList.remove('active');
    sidebar.style.setProperty('left', open ? '0' : 'calc(-1 * min(84vw, 304px))', 'important');
    sidebar.style.setProperty('pointer-events', open ? 'auto' : 'none', 'important');
    sidebar.style.setProperty('z-index', '2147483645', 'important');

    if (overlay) {
      overlay.classList.toggle('open', open);
      overlay.classList.remove('active');
      overlay.style.setProperty('display', open ? 'block' : 'none', 'important');
      overlay.style.setProperty('pointer-events', open ? 'auto' : 'none', 'important');
      overlay.style.setProperty('z-index', '2147483644', 'important');
    }

    if (main) {
      // Never leave the admin frozen. The overlay alone captures outside taps.
      main.style.setProperty('pointer-events', 'auto', 'important');
      main.style.setProperty('touch-action', 'auto', 'important');
    }

    if (hamburger) {
      hamburger.setAttribute('aria-expanded', open ? 'true' : 'false');
      hamburger.style.setProperty('pointer-events', 'auto', 'important');
      hamburger.style.setProperty('touch-action', 'manipulation', 'important');
      hamburger.style.setProperty('z-index', '2147483646', 'important');
    }

    const fab = ensureFab();
    fab.innerHTML = open ? '&#10005;' : '&#9776;';
    fab.setAttribute('aria-label', open ? 'Fermer le menu administration' : 'Ouvrir le menu administration');
  }

  function install() {
    if (!mobile()) return;
    const { sidebar, overlay, hamburger, main } = refs();
    if (!sidebar || !main) return;

    ensureFab();
    setOpen(false);

    if (hamburger && hamburger.dataset.biningaNavFixV2 !== '1') {
      hamburger.dataset.biningaNavFixV2 = '1';
      hamburger.removeAttribute('onclick');
      hamburger.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        setOpen(!isOpen());
      }, { passive:false });
    }

    if (overlay && overlay.dataset.biningaNavFixV2 !== '1') {
      overlay.dataset.biningaNavFixV2 = '1';
      overlay.removeAttribute('onclick');
      overlay.addEventListener('click', (e) => {
        e.preventDefault();
        setOpen(false);
      }, { passive:false });
    }

    sidebar.querySelectorAll('.sb-item').forEach((item) => {
      if (item.dataset.biningaCloseAfterNavV2 === '1') return;
      item.dataset.biningaCloseAfterNavV2 = '1';
      item.addEventListener('click', () => setTimeout(() => setOpen(false), 30), { passive:true });
    });

    // Override legacy helpers so every old inline button uses the same state machine.
    window.toggleSidebar = () => setOpen(!isOpen());
    window.closeSidebar = () => setOpen(false);
  }

  window.addEventListener('pageshow', install, { passive:true });
  window.addEventListener('resize', () => { if (mobile()) install(); }, { passive:true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once:true });
  else install();
})();
