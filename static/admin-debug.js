/* BININGA Admin Debug — Visual diagnostics for hamburger menu issues
 * This module runs ONLY in non-production or when explicitly enabled
 * It provides visible feedback on the page about menu state without DevTools access
 */
(function() {
  'use strict';
  if (window.__BININGA_ADMIN_DEBUG__) return;
  window.__BININGA_ADMIN_DEBUG__ = true;

  const DEBUG = window.location.search.includes('debug=1') || localStorage.getItem('bininga_debug') === '1';
  if (!DEBUG) return;

  let logs = [];
  const maxLogs = 50;

  function addLog(msg) {
    const time = new Date().toLocaleTimeString();
    logs.push(`[${time}] ${msg}`);
    if (logs.length > maxLogs) logs.shift();
    updatePanel();
  }

  function updatePanel() {
    const panel = document.getElementById('bininga-debug-panel');
    if (!panel) return;
    const logContent = document.getElementById('bininga-debug-logs');
    if (logContent) {
      logContent.textContent = logs.join('\n');
      logContent.scrollTop = logContent.scrollHeight;
    }
  }

  // Intercept console.log
  const originalLog = window.console.log;
  window.console.log = function(...args) {
    originalLog.apply(console, args);
    addLog(args.map(a => String(a)).join(' '));
  };

  // Intercept console.warn
  const originalWarn = window.console.warn;
  window.console.warn = function(...args) {
    originalWarn.apply(console, args);
    addLog('⚠️ ' + args.map(a => String(a)).join(' '));
  };

  // Intercept console.error
  const originalError = window.console.error;
  window.console.error = function(...args) {
    originalError.apply(console, args);
    addLog('❌ ' + args.map(a => String(a)).join(' '));
  };

  function installDebugPanel() {
    if (document.getElementById('bininga-debug-panel')) return;

    const panel = document.createElement('div');
    panel.id = 'bininga-debug-panel';
    panel.style.cssText = `
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      max-height: 200px;
      background: rgba(0,0,0,.95);
      color: #0f0;
      border-top: 2px solid #0f0;
      z-index: 99999;
      font-family: monospace;
      font-size: 10px;
      line-height: 1.3;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    `;

    const header = document.createElement('div');
    header.style.cssText = `
      padding: 4px 8px;
      background: rgba(0,30,0,.8);
      border-bottom: 1px solid #0f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
    `;
    header.textContent = 'BININGA Debug • Sidebar: ';

    const stateSpan = document.createElement('span');
    stateSpan.id = 'bininga-debug-state';
    stateSpan.style.color = '#f00';
    stateSpan.textContent = 'CLOSED';
    header.appendChild(stateSpan);

    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕';
    closeBtn.style.cssText = `
      background: transparent;
      border: 1px solid #0f0;
      color: #0f0;
      cursor: pointer;
      padding: 2px 6px;
      font-size: 10px;
    `;
    closeBtn.onclick = () => panel.style.display = 'none';
    header.appendChild(closeBtn);

    const logContent = document.createElement('div');
    logContent.id = 'bininga-debug-logs';
    logContent.style.cssText = `
      flex: 1;
      overflow-y: auto;
      padding: 6px 8px;
      white-space: pre-wrap;
      word-break: break-all;
    `;

    panel.appendChild(header);
    panel.appendChild(logContent);
    document.body.appendChild(panel);

    addLog('Debug panel initialized');
    addLog('Hamburger: ' + (document.getElementById('hamburger') ? '✓ found' : '✗ NOT FOUND'));
    addLog('Sidebar: ' + (document.getElementById('sidebar') ? '✓ found' : '✗ NOT FOUND'));
    addLog('Overlay: ' + (document.getElementById('sidebar-overlay') ? '✓ found' : '✗ NOT FOUND'));
    addLog('Main: ' + (document.querySelector('.main') ? '✓ found' : '✗ NOT FOUND'));
  }

  function updateState() {
    const stateSpan = document.getElementById('bininga-debug-state');
    if (!stateSpan) return;
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) {
      stateSpan.textContent = 'N/A';
      stateSpan.style.color = '#f00';
      return;
    }
    const isOpen = sidebar.classList.contains('open');
    const bodyHasSidebar = document.body.classList.contains('sidebar-open');
    stateSpan.textContent = isOpen ? 'OPEN' : 'CLOSED';
    stateSpan.style.color = isOpen ? '#0f0' : '#f00';
    if (bodyHasSidebar !== isOpen) {
      stateSpan.textContent += ' ⚠️ (body.sidebar-open=' + bodyHasSidebar + ')';
    }
  }

  // Wrap the hamburger click handler
  function wrapHamburgerClick() {
    const hamburger = document.getElementById('hamburger');
    if (!hamburger) {
      setTimeout(wrapHamburgerClick, 100);
      return;
    }

    const original = hamburger.onclick;
    hamburger.addEventListener('click', (e) => {
      addLog('🔔 Hamburger CLICKED');
      updateState();
    });

    // Also watch for toggleSidebar calls
    const originalToggle = window.toggleSidebar;
    if (originalToggle) {
      window.toggleSidebar = function(e) {
        addLog('📞 toggleSidebar() called');
        updateState();
        return originalToggle.call(this, e);
      };
    }

    addLog('Hamburger click wrapped');
    updateState();
  }

  window.addEventListener('DOMContentLoaded', () => {
    installDebugPanel();
    wrapHamburgerClick();
  });

  if (document.readyState !== 'loading') {
    installDebugPanel();
    wrapHamburgerClick();
  }

  // Periodically update state
  setInterval(updateState, 500);

  addLog('Debug module loaded');
})();
