/* BININGA Admin — mobile navigation interaction fix
 * Restores the red sidebar shortcut, guarantees the main area is clickable when
 * the drawer is closed, and keeps legacy panel handlers intact.
 */
(() => {
  'use strict';
  if (window.__BININGA_MOBILE_NAV_FIX__) return;
  window.__BININGA_MOBILE_NAV_FIX__ = true;

  const mobile = () => window.matchMedia('(max-width: 768px)').matches;

  function refs() {
    return {
      body: document.body,
      sidebar: document.getElementById('sidebar'),
      overlay: document.getElementById('sidebar-overlay'),
      pull: document.getElementById('sb-pull'),
      hamburger: document.getElementById('hamburger'),
      main: document.querySelector('.main')
    };
  }

  function isOpen() {
    const { body, sidebar } = refs();
    return !!(body?.classList.contains('sidebar-open') || sidebar?.classList.contains('open') || sidebar?.classList.contains('active'));
  }

  function setOpen(open) {
    const { body, sidebar, overlay, pull, hamburger, main } = refs();
    if (!body || !sidebar) return;

    body.classList.toggle('sidebar-open', open);
    sidebar.classList.toggle('open', open);
    sidebar.classList.remove('active');

    if (overlay) {
      overlay.classList.toggle('open', open);
      overlay.classList.toggle('active', open);
      overlay.style.pointerEvents = open ? 'auto' : 'none';
      overlay.style.display = open ? 'block' : '';
    }

    if (hamburger) hamburger.setAttribute('aria-expanded', open ? 'true' : 'false');

    if (main) {
      main.style.setProperty('pointer-events', open ? 'none' : 'auto', 'important');
      main.style.setProperty('touch-action', open ? 'none' : 'auto', 'important');
    }

    if (pull) {
      pull.classList.toggle('visible', open);
      pull.setAttribute('aria-label', open ? 'Fermer le menu' : 'Ouvrir le menu');
      pull.innerHTML = open ? '&#8249;' : '&#8250;';
      pull.style.setProperty('pointer-events', 'auto', 'important');
      pull.style.setProperty('touch-action', 'manipulation', 'important');
      pull.style.setProperty('z-index', '2147483000', 'important');
    }
  }

  function install() {
    if (!mobile()) return;
    const { pull, hamburger, overlay, sidebar, main } = refs();
    if (!sidebar || !main) return;

    // Start every authenticated mobile view in a known, interactive closed state.
    setOpen(false);

    if (pull && pull.dataset.biningaNavFix !== '1') {
      pull.dataset.biningaNavFix = '1';
      pull.removeAttribute('onclick');
      pull.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        setOpen(!isOpen());
      }, { passive: false });
    }

    if (hamburger && hamburger.dataset.biningaNavFix !== '1') {
      hamburger.dataset.biningaNavFix = '1';
      hamburger.removeAttribute('onclick');
      hamburger.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        setOpen(!isOpen());
      }, { passive: false });
    }

    if (overlay && overlay.dataset.biningaNavFix !== '1') {
      overlay.dataset.biningaNavFix = '1';
      overlay.removeAttribute('onclick');
      overlay.addEventListener('click', () => setOpen(false), { passive: true });
    }

    sidebar.querySelectorAll('.sb-item').forEach((item) => {
      if (item.dataset.biningaCloseAfterNav === '1') return;
      item.dataset.biningaCloseAfterNav = '1';
      item.addEventListener('click', () => {
        setTimeout(() => setOpen(false), 0);
      }, { passive: true });
    });
  }

  window.addEventListener('pageshow', install, { passive: true });
  window.addEventListener('resize', () => { if (mobile()) install(); }, { passive: true });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
})();
