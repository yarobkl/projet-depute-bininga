/*
 * Public form privacy/integrity hardening.
 *
 * Loaded after static/index.js. It keeps failed submissions in the visible form
 * so the visitor can retry, but never writes new names, phones, addresses,
 * complaints or geolocation data to localStorage.
 */
(function () {
  "use strict";

  const LEGACY_QUEUE_KEY = "bininga_pending_forms";
  const LEGACY_QUEUE_TTL_MS = 24 * 60 * 60 * 1000;
  const originalFlush = window.flushPendingForms;

  // index.js registered the original function as an online listener. Remove it
  // before replacing the function so legacy entries are only retried when a
  // durable database is actually available.
  if (typeof originalFlush === "function") {
    try { window.removeEventListener("online", originalFlush); } catch (_) {}
  }

  function formErrorMessage(data, fallback) {
    if (data && typeof data.message === "string" && data.message.trim()) {
      return data.message.trim();
    }
    return fallback || "Envoi impossible pour le moment. Vos informations n'ont pas été enregistrées. Réessayez plus tard.";
  }

  async function serverHasDurableStorage() {
    try {
      const res = await fetch("/health", { cache: "no-store" });
      const data = await res.json();
      return !!(res.ok && data && data.database && data.database !== "no_database");
    } catch (_) {
      return false;
    }
  }

  // New failed submissions are deliberately NOT queued in browser storage.
  window.queuePendingForm = function () {};

  // Preserve old queued entries for at most 24h, and only retry them after the
  // backend reports durable storage. This avoids both silent loss and indefinite
  // retention of sensitive citizen data in the browser.
  window.flushPendingForms = async function () {
    let queue = [];
    try {
      queue = JSON.parse(localStorage.getItem(LEGACY_QUEUE_KEY) || "[]");
    } catch (_) {
      return;
    }
    if (!Array.isArray(queue) || !queue.length) return;

    const cutoff = Date.now() - LEGACY_QUEUE_TTL_MS;
    queue = queue.filter(item => {
      const ts = Date.parse(item && item.queued_at ? item.queued_at : "");
      return Number.isFinite(ts) && ts >= cutoff && item && item.entry;
    });

    if (!queue.length) {
      try { localStorage.removeItem(LEGACY_QUEUE_KEY); } catch (_) {}
      return;
    }

    if (!navigator.onLine || !(await serverHasDurableStorage())) {
      try { localStorage.setItem(LEGACY_QUEUE_KEY, JSON.stringify(queue)); } catch (_) {}
      return;
    }

    const remaining = [];
    for (const item of queue) {
      try {
        const res = await fetch("/api/contact", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(item.entry)
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) throw new Error("not-saved");
      } catch (_) {
        item.attempts = (item.attempts || 0) + 1;
        if (item.attempts < 3) remaining.push(item);
      }
    }

    try {
      if (remaining.length) localStorage.setItem(LEGACY_QUEUE_KEY, JSON.stringify(remaining));
      else localStorage.removeItem(LEGACY_QUEUE_KEY);
    } catch (_) {}
  };

  window.addEventListener("online", window.flushPendingForms);

  window.sendForm = async function (storageKey, _unused, formData, btn, successMsg) {
    if (!btn) return;
    const originalText = btn.dataset.originalText || btn.textContent || "Soumettre";
    btn.dataset.originalText = originalText;
    btn.textContent = "Envoi en cours...";
    btn.disabled = true;
    btn.style.background = "";

    const entry = {};
    formData.forEach((v, k) => { entry[k] = v; });
    entry.type = storageKey;
    entry._date = new Date().toLocaleString("fr-FR");
    entry._id = Date.now() + "-" + Math.random().toString(36).slice(2, 8);

    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) {
        throw new Error(formErrorMessage(data));
      }

      btn.textContent = successMsg;
      btn.style.background = "#2ecc71";
      if (data.tracking_code && typeof window.showTrackingReceipt === "function") {
        window.showTrackingReceipt(data.tracking_code);
      }

      setTimeout(() => {
        const form = btn.closest("form");
        if (form) form.reset();
        btn.style.background = "";
        btn.textContent = originalText;
        btn.disabled = false;
      }, 3000);
    } catch (err) {
      btn.textContent = "Réessayer";
      btn.style.background = "#c0392b";
      btn.disabled = false;
      const message = err && err.message
        ? err.message
        : "Envoi impossible pour le moment. Vos informations n'ont pas été enregistrées. Réessayez plus tard.";
      if (typeof window.showTrackingReceipt === "function") {
        window.showTrackingReceipt("", message);
      }
    }
  };

  window.submitOrder = async function (e, form) {
    e.preventDefault();
    const btn = document.getElementById("order-btn");
    const ok = document.getElementById("order-ok");
    if (!btn || !ok) return;

    btn.disabled = true;
    btn.textContent = "Envoi...";
    ok.style.display = "none";

    const entry = {
      type: "bininga_commande_livre",
      livre: "Les mutations constitutionnelles en Afrique noire francophone",
      _date: new Date().toLocaleString("fr-FR"),
      _id: Date.now() + "-" + Math.random().toString(36).slice(2, 8)
    };
    new FormData(form).forEach((v, k) => { entry[k] = v; });
    try { if (typeof window.trackBuy === "function") window.trackBuy("bureau"); } catch (_) {}

    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) throw new Error(formErrorMessage(data, "Commande non enregistrée. Réessayez plus tard."));

      form.style.display = "none";
      if (data.tracking_code) {
        ok.innerHTML = `Commande enregistrée. Numéro de suivi : <strong>${window.escHtml ? window.escHtml(data.tracking_code) : data.tracking_code}</strong>. Notre équipe vous contacte sous 48h.`;
      } else {
        ok.textContent = "Commande enregistrée. Notre équipe vous contacte sous 48h.";
      }
      ok.style.color = "#2ecc71";
      ok.style.display = "block";
    } catch (err) {
      ok.textContent = err && err.message ? err.message : "Commande non enregistrée. Réessayez plus tard.";
      ok.style.color = "#e74c3c";
      ok.style.display = "block";
      btn.disabled = false;
      btn.textContent = "Envoyer ma commande";
    }
  };

  window.subNewsletter = async function (e, form) {
    e.preventDefault();
    const btn = document.getElementById("nl-btn");
    const ok = document.getElementById("nl-ok");
    if (!btn || !ok) return;

    const email = form.email.value.trim();
    btn.disabled = true;
    btn.textContent = "Envoi...";
    ok.style.display = "none";

    const entry = {
      email,
      type: "bininga_newsletter",
      _date: new Date().toLocaleString("fr-FR"),
      _id: Date.now() + "-" + Math.random().toString(36).slice(2, 8)
    };

    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) throw new Error(formErrorMessage(data, "Inscription non enregistrée. Réessayez plus tard."));

      form.style.display = "none";
      ok.textContent = "Inscription enregistrée.";
      ok.style.color = "#2ecc71";
      ok.style.display = "block";
    } catch (err) {
      ok.textContent = err && err.message ? err.message : "Inscription non enregistrée. Réessayez plus tard.";
      ok.style.color = "#e74c3c";
      ok.style.display = "block";
      btn.disabled = false;
      btn.textContent = "S'inscrire";
    }
  };

  // Run once after this override has replaced the legacy DOMContentLoaded path.
  window.flushPendingForms();
})();
