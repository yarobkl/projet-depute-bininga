/* BININGA Admin — Navigation centralisée
 * Source unique de vérité pour showPanel, toggleSidebar, closeSidebar, openSidebar
 * Tous les modules écoutent via CustomEvent. Les loaders critiques sont aussi
 * déclenchés ici afin qu'un cache/module secondaire défaillant ne puisse pas
 * laisser un panneau affiché avec des données factices.
 */
(()=>{
  'use strict';
  if (window.__BININGA_ADMIN_NAVIGATION__) return;
  window.__BININGA_ADMIN_NAVIGATION__ = true;

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

  function _runPanelLoader(name) {
    const loaders = {
      crm: () => typeof window.loadCrm === 'function' ? window.loadCrm(1) : null,
      monitoring: () => typeof window.loadMonitoring === 'function' ? window.loadMonitoring() : null,
      backups: () => typeof window.loadBackups === 'function' ? window.loadBackups() : null,
      logs: () => typeof window.loadAuditLogs === 'function' ? window.loadAuditLogs() : null,
      users: () => typeof window.loadUsers === 'function' ? window.loadUsers() : null,
      security: () => {
        const tasks=[];
        if(typeof window.loadSecurity==='function') tasks.push(window.loadSecurity());
        if(typeof window.loadBouclier==='function') tasks.push(window.loadBouclier());
        return tasks.length ? Promise.allSettled(tasks) : null;
      },
    };
    const loader = loaders[name];
    if (!loader) return true;
    try {
      const result = loader();
      if (result && typeof result.catch === 'function') {
        result.catch(err => console.error('[BININGA Nav] loader ' + name + ' échoué', err));
      }
      return result !== null;
    } catch (err) {
      console.error('[BININGA Nav] loader ' + name + ' échoué', err);
      return true;
    }
  }

  function _triggerPanelLoader(name) {
    if (_runPanelLoader(name)) return;
    let attempts = 0;
    const retry = () => {
      attempts += 1;
      if (_currentPanel !== name) return;
      if (_runPanelLoader(name)) return;
      if (attempts < 6) setTimeout(retry, 200);
    };
    setTimeout(retry, 100);
  }

  window.showPanel = function showPanel(name, el) {
    if (!name) return;
    _currentPanel = name;

    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.sb-item').forEach(i => i.classList.remove('active'));

    const panel = document.getElementById('panel-' + name);
    if (!panel) {
      if (typeof window.showToast === 'function') window.showToast('Module indisponible', true);
      showPanel('dashboard');
      return;
    }
    panel.classList.add('active');
    if (el) el.classList.add('active');

    const titles = window.PANEL_TITLES || {};
    const title = document.getElementById('topbar-title');
    if (title) title.textContent = titles[name] || name;

    if (isMobile()) closeSidebar();

    // L'événement reste disponible pour l'UX, mais la navigation est l'unique
    // propriétaire des appels réseau. Cela empêche CRM/Système de lancer deux
    // requêtes identiques au même clic.
    window.dispatchEvent(new CustomEvent('admin:panelchange', { detail: { name } }));
    _triggerPanelLoader(name);
  };

  let _lastToggle = 0;
  window.toggleSidebar = function toggleSidebar(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    const now = Date.now();
    if (now - _lastToggle < 350) return;
    _lastToggle = now;
    if (!isMobile()) return;
    if (_sidebarOpen) closeSidebar(); else openSidebar();
  };

  window.openSidebar = function openSidebar() {
    if (!isMobile()) return;
    const { sidebar, overlay, hamburger, main, body } = refs();
    if (!sidebar) return;
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

  function install() {
    const { sidebar, overlay, hamburger, main } = refs();
    if (!sidebar || !hamburger || !main) return;

    hamburger.removeAttribute('onclick');
    hamburger.onclick = null;
    hamburger.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation(); window.toggleSidebar();
    });

    if (overlay) {
      overlay.removeAttribute('onclick');
      overlay.onclick = null;
      overlay.addEventListener('click', (e) => {
        e.preventDefault(); e.stopPropagation(); window.closeSidebar();
      });
    }

    sidebar.querySelectorAll('.sb-item').forEach(item => {
      item.addEventListener('click', () => { if (isMobile()) closeSidebar(); }, { passive: true });
    });

    window.addEventListener('resize', () => {
      if (!isMobile() && _sidebarOpen) closeSidebar();
    }, { passive: true });

    if (isMobile()) closeSidebar();
    else {
      sidebar.classList.remove('open');
      sidebar.style.removeProperty('left');
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();

  console.info('[BININGA Admin] Navigation centralisée chargée');
})();