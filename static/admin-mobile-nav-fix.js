/* BININGA Admin — navigation stable (mobile + desktop)
 *
 * Important: this file does not create any shortcut/floating button.
 * It only makes the existing admin hamburger/sidebar reliable and clears stale
 * states left by previous mobile rescue scripts.
 */
(() => {
  'use strict';
  if (window.__BININGA_ADMIN_NAV_STABLE__) return;
  window.__BININGA_ADMIN_NAV_STABLE__ = true;

  const mobile = () => window.matchMedia('(max-width: 768px)').matches;
  let openState = false;
  let lastAction = 0;

  const refs = () => ({
    body: document.body,
    sidebar: document.getElementById('sidebar'),
    overlay: document.getElementById('sidebar-overlay'),
    hamburger: document.getElementById('hamburger'),
    pull: document.getElementById('sb-pull'),
    main: document.querySelector('.main')
  });

  function removeLegacyRescueUI() {
    document.getElementById('bininga-mobile-menu-fab')?.remove();
    const { pull } = refs();
    if (pull) {
      pull.style.setProperty('display', 'none', 'important');
      pull.style.setProperty('visibility', 'hidden', 'important');
      pull.style.setProperty('pointer-events', 'none', 'important');
    }
  }

  function render(open) {
    const { body, sidebar, overlay, hamburger, main } = refs();
    if (!body || !sidebar) return;

    // Desktop keeps its native fixed sidebar visible.
    if (!mobile()) {
      openState = false;
      body.classList.remove('sidebar-open');
      body.style.removeProperty('overflow');
      sidebar.classList.remove('open', 'active');
      ['left','transform','visibility','pointer-events','display','z-index'].forEach(p => sidebar.style.removeProperty(p));
      if (overlay) {
        overlay.classList.remove('open', 'active');
        ['display','visibility','pointer-events','z-index'].forEach(p => overlay.style.removeProperty(p));
      }
      if (hamburger) hamburger.setAttribute('aria-expanded', 'false');
      if (main) {
        main.style.removeProperty('pointer-events');
        main.style.removeProperty('touch-action');
      }
      return;
    }

    openState = !!open;

    // Do not use body.sidebar-open: mobile.css historically disables .main while
    // this class is present, which caused the whole admin to become untouchable.
    body.classList.remove('sidebar-open');
    body.style.overflow = openState ? 'hidden' : '';

    sidebar.classList.toggle('open', openState);
    sidebar.classList.remove('active');
    sidebar.style.setProperty('left', openState ? '0px' : 'calc(-1 * min(84vw, 304px))', 'important');
    sidebar.style.setProperty('transform', 'none', 'important');
    sidebar.style.setProperty('visibility', openState ? 'visible' : 'hidden', 'important');
    sidebar.style.setProperty('pointer-events', openState ? 'auto' : 'none', 'important');
    sidebar.style.setProperty('display', 'block', 'important');
    sidebar.style.setProperty('z-index', '1001', 'important');

    if (overlay) {
      overlay.classList.toggle('open', openState);
      overlay.classList.remove('active');
      overlay.style.setProperty('display', openState ? 'block' : 'none', 'important');
      overlay.style.setProperty('visibility', openState ? 'visible' : 'hidden', 'important');
      overlay.style.setProperty('pointer-events', openState ? 'auto' : 'none', 'important');
      overlay.style.setProperty('z-index', '1000', 'important');
    }

    if (hamburger) {
      hamburger.setAttribute('aria-expanded', openState ? 'true' : 'false');
      hamburger.style.setProperty('pointer-events', 'auto', 'important');
      hamburger.style.setProperty('touch-action', 'manipulation', 'important');
      hamburger.style.setProperty('position', 'relative', 'important');
      hamburger.style.setProperty('z-index', '1002', 'important');
    }

    // Main remains structurally interactive; the overlay alone captures outside
    // taps while the drawer is open. This avoids stale pointer-events:none states.
    if (main) {
      main.style.setProperty('pointer-events', 'auto', 'important');
      main.style.setProperty('touch-action', 'auto', 'important');
    }
  }

  function toggle(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const now = Date.now();
    if (now - lastAction < 220) return;
    lastAction = now;
    render(!openState);
  }

  function close(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    render(false);
  }

  function bindOnce(el, key, handler) {
    if (!el || el.dataset[key] === '1') return;
    el.dataset[key] = '1';
    el.removeAttribute('onclick');
    // Pointer events cover touch, pen and mouse with one event instead of the
    // touchend + synthetic click double-fire that broke iOS.
    el.addEventListener('pointerup', handler, { passive: false });
  }

  function install() {
    removeLegacyRescueUI();
    const { sidebar, overlay, hamburger, main } = refs();
    if (!sidebar || !main) return;

    bindOnce(hamburger, 'biningaNavStable', toggle);
    bindOnce(overlay, 'biningaOverlayStable', close);

    sidebar.querySelectorAll('.sb-item').forEach(item => {
      if (item.dataset.biningaPanelClose === '1') return;
      item.dataset.biningaPanelClose = '1';
      item.addEventListener('click', () => {
        if (mobile()) setTimeout(() => render(false), 0);
      }, { passive: true });
    });

    window.toggleSidebar = () => render(!openState);
    window.openSidebar = () => render(true);
    window.closeSidebar = () => render(false);

    render(false);
  }

  window.addEventListener('pageshow', install, { passive: true });
  window.addEventListener('resize', () => {
    // Browser chrome / orientation changes must preserve an open mobile drawer.
    requestAnimationFrame(() => render(mobile() ? openState : false));
  }, { passive: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
