/* BININGA Admin — Navigation centralisée
 * Source unique de vérité pour showPanel, toggleSidebar, closeSidebar, openSidebar
 * Tous les modules écoutent via CustomEvent, ne pas wrapper showPanel
 */
(()=>{
  'use strict';
  if (window.__BININGA_ADMIN_NAVIGATION__) return;
  window.__BININGA_ADMIN_NAVIGATION__ = true;

  // ─── STATE ───
  let _currentPanel = null;
  let _sidebarOpen = false;

  const isMobile = () => window.matchMedia('(max-width: 768px)').matches;

  const refs = () => ({
    sidebar: document.getElementById('sidebar'),
    overlay: document.getElementById('sidebar-overlay'),
    hamburger: document.getElementById('hamburger'),
    pull: document.getElementById('sb-pull'),
    main: document.querySelector('.main'),
    body: document.body
  });

  // ─── MAIN EXPORTED FUNCTIONS ───

  window.showPanel = function showPanel(name, el) {
    if (!name) return;
    _currentPanel = name;

    // 1. Nettoyer les panels
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.sb-item').forEach(i => i.classList.remove('active'));

    // 2. Afficher le bon panel
    const panel = document.getElementById('panel-' + name);
    if (!panel) {
      if (typeof window.showToast === 'function') window.showToast('Module indisponible', true);
      showPanel('dashboard');
      return;
    }
    panel.classList.add('active');
    if (el) el.classList.add('active');

    // 3. Mise à jour titre
    const titles = window.PANEL_TITLES || {};
    const title = document.getElementById('topbar-title');
    if (title) title.textContent = titles[name] || name;

    // 4. Fermer sidebar sur mobile
    if (isMobile()) closeSidebar();

    // 5. Dispatcher événement pour modules
    window.dispatchEvent(new CustomEvent('admin:panelchange', { detail: { name } }));
  };

  let _lastToggle = 0;
  window.toggleSidebar = function toggleSidebar(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    // Anti double-fire : un tap mobile peut déclencher pointerup + click.
    // Toute seconde invocation sous 350ms est le même geste — on l'ignore.
    const now = Date.now();
    if (now - _lastToggle < 350) {
      console.log('[BININGA Nav] toggleSidebar: doublon ignoré (' + (now - _lastToggle) + 'ms)');
      return;
    }
    _lastToggle = now;
    const mobile = isMobile();
    if (!mobile) {
      console.log('[BININGA Nav] toggleSidebar: not mobile, returning');
      return;
    }
    if (_sidebarOpen) closeSidebar();
    else openSidebar();
  };

  window.openSidebar = function openSidebar() {
    if (!isMobile()) {
      console.log('[BININGA Nav] openSidebar: not mobile');
      return;
    }
    const { sidebar, overlay, hamburger, main, body } = refs();
    if (!sidebar) {
      console.log('[BININGA Nav] openSidebar: sidebar not found');
      return;
    }

    _sidebarOpen = true;
    sidebar.classList.add('open');
    sidebar.style.setProperty('left', '0px', 'important');
    if (overlay) overlay.classList.add('open');
    if (hamburger) hamburger.setAttribute('aria-expanded', 'true');
    if (main) {
      main.style.setProperty('pointer-events', 'auto', 'important');
      main.style.setProperty('touch-action', 'auto', 'important');
    }
    body.style.overflow = 'hidden';
    body.classList.add('sidebar-open');
  };

  window.closeSidebar = function closeSidebar() {
    const { sidebar, overlay, hamburger, pull, main, body } = refs();
    if (!sidebar) return;

    _sidebarOpen = false;
    sidebar.classList.remove('open');
    sidebar.style.setProperty('left', 'calc(-1 * min(84vw, 304px))', 'important');
    if (overlay) overlay.classList.remove('open');
    if (hamburger) hamburger.setAttribute('aria-expanded', 'false');
    if (pull) pull.classList.remove('visible');
    if (main) {
      main.style.setProperty('pointer-events', 'auto', 'important');
      main.style.setProperty('touch-action', 'auto', 'important');
    }
    body.style.overflow = '';
    body.classList.remove('sidebar-open');
  };

  // ─── INSTALLATION ───

  function install() {
    console.log('[BININGA Nav] install() called');
    const { sidebar, overlay, hamburger, main } = refs();
    if (!sidebar || !hamburger) {
      console.log('[BININGA Nav] install: sidebar or hamburger not found', { sidebar: !!sidebar, hamburger: !!hamburger });
      return;
    }
    if (!main) {
      console.log('[BININGA Nav] install: main element not found');
      return;
    }
    console.log('[BININGA Nav] install: binding events');

    // ⚠️ Le HTML porte des onclick inline (toggleSidebar/closeSidebar).
    // On les retire AVANT de lier nos écouteurs, sinon un tap mobile
    // déclenche pointerup + click → le menu s'ouvre puis se referme
    // instantanément (symptôme : « le hamburger ne s'ouvre pas »).
    hamburger.removeAttribute('onclick');
    hamburger.onclick = null;
    hamburger.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      window.toggleSidebar();
    });

    if (overlay) {
      overlay.removeAttribute('onclick');
      overlay.onclick = null;
      overlay.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.closeSidebar();
      });
    }

    // Sidebar items close sidebar on mobile
    sidebar.querySelectorAll('.sb-item').forEach(item => {
      item.addEventListener('click', () => {
        if (isMobile()) closeSidebar();
      }, { passive: true });
    });

    // Resize: close sidebar si on passe desktop
    window.addEventListener('resize', () => {
      if (!isMobile() && _sidebarOpen) closeSidebar();
    }, { passive: true });

    // Initial state
    if (isMobile()) {
      closeSidebar();
    } else {
      // Desktop : sidebar visible, aucun style inline qui cache
      const { sidebar } = refs();
      if (sidebar) {
        sidebar.classList.remove('open');
        sidebar.style.removeProperty('left');
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }

  console.info('[BININGA Admin] Navigation centralisée chargée');
})();
