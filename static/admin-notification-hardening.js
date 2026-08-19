/* BININGA Admin — notification transport hardening
 *
 * The legacy admin uses EventSource('/api/events?t=<session token>'). Query-string
 * credentials can leak into request/proxy logs and the WSGI adapter cannot stream
 * that connection efficiently on Vercel. Replace it with small authenticated polls
 * using the existing X-Admin-Token header. No admin token is placed in a URL.
 */
(() => {
  'use strict';

  const POLL_MS = 30000;
  let pollTimer = null;
  let primed = false;
  let seenIds = new Set();

  function recordId(kind, item, index) {
    const stable = item && (item._id || item.id || item.tracking_code);
    if (stable) return `${kind}:${stable}`;
    const fallback = [
      kind,
      item && (item._date || item.ts || item.date || item.created_at) || '',
      item && item.email || '',
      item && item.telephone || '',
      item && item.prenom || '',
      item && item.nom || '',
      index
    ].join('|');
    return fallback;
  }

  function notificationType(kind, item) {
    if (kind === 'audience' && item && item.objet === 'Réclamation') return 'reclamation';
    return kind;
  }

  function scheduleNext() {
    if (pollTimer) clearTimeout(pollTimer);
    if (typeof SESSION_TOKEN === 'undefined' || !SESSION_TOKEN) {
      pollTimer = null;
      return;
    }
    pollTimer = setTimeout(pollOnce, POLL_MS);
  }

  async function pollOnce() {
    if (typeof SESSION_TOKEN === 'undefined' || !SESSION_TOKEN) {
      scheduleNext();
      return;
    }

    try {
      const response = await apiFetch('/api/contacts', {
        headers: { 'X-Admin-Token': SESSION_TOKEN },
        cache: 'no-store'
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) throw new Error(payload.message || 'notifications indisponibles');

      const rows = [];
      (Array.isArray(payload.audiences) ? payload.audiences : []).forEach((item, index) => {
        rows.push({ kind: 'audience', item: item || {}, index });
      });
      (Array.isArray(payload.contacts) ? payload.contacts : []).forEach((item, index) => {
        rows.push({ kind: 'contact', item: item || {}, index });
      });

      const current = new Set();
      for (const row of rows) {
        const id = recordId(row.kind, row.item, row.index);
        current.add(id);
        if (primed && !seenIds.has(id) && typeof _addNotif === 'function') {
          _addNotif(notificationType(row.kind, row.item), {
            nom: row.item.nom || '',
            prenom: row.item.prenom || '',
            objet: row.item.objet || row.item.sujet || ''
          });
        }
      }

      seenIds = current;
      primed = true;
    } catch (_) {
      // apiFetch already handles expired sessions. Notification polling should
      // never block the rest of the administration UI.
    } finally {
      scheduleNext();
    }
  }

  window._connectSSE = function connectNotificationsSafely() {
    // Defensive cleanup in case an older bundle already opened EventSource.
    try {
      if (typeof _sseSource !== 'undefined' && _sseSource) {
        _sseSource.close();
        _sseSource = null;
      }
    } catch (_) {}
    try {
      if (typeof _sseRetryTimer !== 'undefined' && _sseRetryTimer) {
        clearTimeout(_sseRetryTimer);
        _sseRetryTimer = null;
      }
    } catch (_) {}

    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
    primed = false;
    seenIds = new Set();
    pollOnce();
  };

  console.info('[BININGA Admin] Notification transport hardened');
})();
