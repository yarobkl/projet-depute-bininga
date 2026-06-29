import "./styles.css";

// ── Configuration ──────────────────────────────────────────
// L'app mobile ne fait QUE consommer l'API publique existante du backend
// Bininga (server.py). Aucun secret, aucun token admin n'est embarqué ici.
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "https://wude3801.odns.fr").replace(/\/$/, "");
const FETCH_TIMEOUT_MS = 10000;

const state = {
  data: null,
  loading: true,
  serverDown: false,
  route: "home",
};

// ── Réseau ──────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        // Content-Type uniquement si on envoie un corps (évite un préflight
        // CORS inutile sur les simples GET comme /api/load ou /api/dossier).
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
    clearTimeout(timer);
    const json = await res.json().catch(() => ({}));
    if (!res.ok && json.ok === undefined) {
      json.ok = false;
      json.message = json.message || `Erreur serveur (${res.status})`;
    }
    setServerStatus(true);
    return json;
  } catch (err) {
    clearTimeout(timer);
    setServerStatus(false);
    return { ok: false, message: "Impossible de contacter le serveur. Vérifiez votre connexion.", offline: true };
  }
}

function setServerStatus(ok) {
  state.serverDown = !ok;
  const banner = document.getElementById("offline-banner");
  if (!banner) return;
  banner.classList.toggle("show", !ok);
}

async function loadPublicData() {
  const json = await apiFetch("/api/load");
  if (json && json.ok !== false) {
    state.data = json;
  }
  state.loading = false;
}

// ── Router ──────────────────────────────────────────────────
const VIEWS = ["home", "programme", "actus", "demarches", "suivi"];

function navigate(route) {
  if (!VIEWS.includes(route)) route = "home";
  state.route = route;
  window.location.hash = `#/${route}`;
  render();
}

window.addEventListener("hashchange", () => {
  const route = (window.location.hash || "#/home").replace("#/", "");
  state.route = VIEWS.includes(route) ? route : "home";
  render();
});

// ── Rendu : nav ─────────────────────────────────────────────
const NAV_ITEMS = [
  { id: "home", label: "Accueil", icon: "🏠" },
  { id: "programme", label: "Programme", icon: "📋" },
  { id: "actus", label: "Actualités", icon: "📰" },
  { id: "demarches", label: "Démarches", icon: "✉️" },
  { id: "suivi", label: "Suivi", icon: "🔍" },
];

function renderNav() {
  return `
    <nav class="bottom-nav">
      ${NAV_ITEMS.map(
        (item) => `
        <button class="nav-btn ${state.route === item.id ? "active" : ""}" data-nav="${item.id}">
          <span class="nav-icon">${item.icon}</span>
          <span>${item.label}</span>
        </button>`
      ).join("")}
    </nav>`;
}

// ── Vue : Accueil ───────────────────────────────────────────
function viewHome() {
  const hero = state.data?.hero || {};
  const about = state.data?.about || {};
  const fullName = [hero.firstName, hero.lastName].filter(Boolean).join(" ");
  return `
    <div class="hero-card">
      <div class="eyebrow">${escapeHtml(hero.eyebrow || "Plateforme citoyenne")}</div>
      <h2>${fullName ? escapeHtml(fullName) : "Bininga"}</h2>
      <p>${escapeHtml(hero.role || "")}</p>
    </div>
    <p style="font-size:14px;color:var(--muted);line-height:1.6;margin-bottom:18px;">
      ${escapeHtml(about.intro || "Suivez l'actualité, consultez le programme et adressez vos demandes directement depuis votre téléphone.")}
    </p>
    <div class="section-title">Accès rapide</div>
    <div class="card" data-nav="demarches">
      <h3>📋 Demande d'audience</h3>
      <p>Sollicitez un rendez-vous officiel.</p>
    </div>
    <div class="card" data-nav="demarches">
      <h3>⚠️ Signalement / réclamation</h3>
      <p>Faites remonter un problème de votre quartier ou village.</p>
    </div>
    <div class="card" data-nav="suivi">
      <h3>🔍 Suivi de dossier</h3>
      <p>Retrouvez l'état d'avancement avec votre numéro de suivi.</p>
    </div>
  `;
}

// ── Vue : Programme ─────────────────────────────────────────
function viewProgramme() {
  const programme = state.data?.programme || {};
  const axes = Array.isArray(programme.axes) ? programme.axes : [];
  if (!axes.length) {
    return `<div class="empty">Le programme n'est pas disponible pour le moment.</div>`;
  }
  return `
    <div class="section-title">${escapeHtml(programme.heroTitle || "Notre programme")}</div>
    <p style="font-size:13.5px;color:var(--muted);margin-bottom:16px;line-height:1.5;">
      ${escapeHtml(programme.heroText || "")}
    </p>
    ${axes
      .map(
        (axe) => `
      <div class="card axis-card">
        <span class="icon">${escapeHtml(axe.icon || "•")}</span>
        <h3>${escapeHtml(axe.title || "")}</h3>
        <p>${escapeHtml(axe.text || "")}</p>
        ${
          Array.isArray(axe.points) && axe.points.length
            ? `<ul>${axe.points.map((p) => `<li>${escapeHtml(p)}</li>`).join("")}</ul>`
            : ""
        }
      </div>`
      )
      .join("")}
  `;
}

// ── Vue : Actualités ────────────────────────────────────────
function viewActus() {
  const cards = state.data?.actus?.cards || [];
  if (!cards.length) {
    return `<div class="empty">Aucune actualité disponible pour le moment.</div>`;
  }
  return `
    <div class="section-title">Actualités</div>
    ${cards
      .slice(0, 20)
      .map(
        (c) => `
      <div class="card actu-card">
        <img src="${API_BASE}/${escapeAttr(c.image || "")}" alt="" loading="lazy" onerror="this.style.display='none'" />
        <div>
          <div class="meta">${escapeHtml(c.cat || "")} ${c.day ? `· ${escapeHtml(c.day)} ${escapeHtml(c.month || "")} ${escapeHtml(c.year || "")}` : ""}</div>
          <h3 style="margin:0 0 4px;">${escapeHtml(c.title || "")}</h3>
          <p>${escapeHtml(c.desc || "")}</p>
        </div>
      </div>`
      )
      .join("")}
  `;
}

// ── Vue : Démarches (audience / réclamation / contact) ──────
let demarchesTab = "audience";

const DEMARCHES_TABS = [
  { id: "audience", label: "Audience" },
  { id: "reclamation", label: "Réclamation" },
  { id: "contact", label: "Contact" },
];

function viewDemarches() {
  return `
    <div class="section-title">Vos démarches</div>
    <div class="tabs-row">
      ${DEMARCHES_TABS.map(
        (t) => `<button class="tab-btn ${demarchesTab === t.id ? "active" : ""}" data-demarche-tab="${t.id}">${t.label}</button>`
      ).join("")}
    </div>
    <div id="demarche-feedback"></div>
    ${renderDemarcheForm(demarchesTab)}
  `;
}

function renderDemarcheForm(tab) {
  if (tab === "audience") {
    return `
      <form id="form-audience">
        <div class="field">
          <label>Nom complet *</label>
          <input type="text" name="nom" required />
        </div>
        <div class="field">
          <label>Téléphone *</label>
          <input type="tel" name="telephone" required />
        </div>
        <div class="field">
          <label>Email</label>
          <input type="email" name="email" />
        </div>
        <div class="field">
          <label>Objet de la demande *</label>
          <input type="text" name="objet" placeholder="Ex : audience pour un projet local" required />
        </div>
        <div class="field">
          <label>Message *</label>
          <textarea name="message" required placeholder="Décrivez votre demande d'audience"></textarea>
        </div>
        <button class="btn-primary" type="submit">Envoyer la demande</button>
        <p class="field-hint">Vous recevrez un numéro de suivi pour suivre l'avancement.</p>
      </form>`;
  }
  if (tab === "reclamation") {
    return `
      <form id="form-reclamation">
        <div class="field">
          <label>Nom complet *</label>
          <input type="text" name="nom" required />
        </div>
        <div class="field">
          <label>Téléphone *</label>
          <input type="tel" name="telephone" required />
        </div>
        <div class="field">
          <label>Localité concernée</label>
          <input type="text" name="localite" placeholder="Ex : Ewo, quartier..." />
        </div>
        <div class="field">
          <label>Description du signalement *</label>
          <textarea name="message" required placeholder="Décrivez le problème rencontré"></textarea>
        </div>
        <button class="btn-primary" type="submit">Envoyer le signalement</button>
        <p class="field-hint">Vous recevrez un numéro de suivi pour suivre le traitement.</p>
      </form>`;
  }
  return `
    <form id="form-contact">
      <div class="field">
        <label>Nom complet *</label>
        <input type="text" name="nom" required />
      </div>
      <div class="field">
        <label>Email *</label>
        <input type="email" name="email" required />
      </div>
      <div class="field">
        <label>Téléphone</label>
        <input type="tel" name="telephone" />
      </div>
      <div class="field">
        <label>Message *</label>
        <textarea name="message" required></textarea>
      </div>
      <button class="btn-primary" type="submit">Envoyer le message</button>
    </form>`;
}

async function handleDemarcheSubmit(tab, form) {
  const feedback = document.getElementById("demarche-feedback");
  const submitBtn = form.querySelector("button[type=submit]");
  const fd = new FormData(form);
  const payload = {};
  for (const [k, v] of fd.entries()) payload[k] = v;

  if (tab === "audience") {
    payload.source = "bininga_audiences";
    payload.type = "bininga_audiences";
  } else if (tab === "reclamation") {
    payload.source = "bininga_audiences";
    payload.type = "bininga_audiences";
    payload.objet = "Réclamation";
  } else {
    payload.source = "bininga_contacts";
    payload.type = "bininga_contacts";
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Envoi en cours…";
  const json = await apiFetch("/api/contact", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  submitBtn.disabled = false;
  submitBtn.textContent = tab === "contact" ? "Envoyer le message" : "Envoyer";

  if (json.ok) {
    form.reset();
    feedback.innerHTML = `
      <div class="alert alert-success">
        Votre demande a bien été envoyée.
        ${json.tracking_code ? `<br/>Numéro de suivi : <strong>${escapeHtml(json.tracking_code)}</strong>` : ""}
      </div>`;
  } else {
    feedback.innerHTML = `<div class="alert alert-error">${escapeHtml(json.message || "Une erreur est survenue. Réessayez.")}</div>`;
  }
}

// ── Vue : Suivi de dossier ───────────────────────────────────
function viewSuivi() {
  return `
    <div class="section-title">Suivi de dossier</div>
    <form id="form-suivi">
      <div class="field">
        <label>Numéro de suivi</label>
        <input type="text" name="code" placeholder="Ex : AB-20260101-XXXXXX" autocapitalize="characters" required />
      </div>
      <button class="btn-primary" type="submit">Rechercher</button>
    </form>
    <div id="suivi-result" style="margin-top:18px;"></div>
  `;
}

async function handleSuiviSubmit(form) {
  const result = document.getElementById("suivi-result");
  const code = form.querySelector("input[name=code]").value.trim();
  if (!code) return;
  result.innerHTML = `<div class="loading">Recherche en cours…</div>`;
  const json = await apiFetch(`/api/dossier?code=${encodeURIComponent(code)}`);
  if (!json.ok) {
    result.innerHTML = `<div class="alert alert-error">${escapeHtml(json.message || "Dossier introuvable.")}</div>`;
    return;
  }
  const steps = Array.isArray(json.steps) ? json.steps : [];
  result.innerHTML = `
    <div class="tracking-code">${escapeHtml(json.tracking_code || code)}</div>
    <div class="alert alert-info">${escapeHtml(json.status_label || "")}</div>
    <div class="steps">
      ${steps
        .map(
          (s) => `
        <div class="step ${s.done ? "done" : ""}">
          <div class="dot"></div>
          <div>
            <div class="label">${escapeHtml(s.label || "")}</div>
            ${s.date ? `<div class="date">${escapeHtml(s.date)}</div>` : ""}
          </div>
        </div>`
        )
        .join("")}
    </div>
    ${
      json.decision_label
        ? `<div class="card"><h3>Décision : ${escapeHtml(json.decision_label)}</h3>${json.decision_note ? `<p>${escapeHtml(json.decision_note)}</p>` : ""}</div>`
        : ""
    }
    ${
      json.appointment && json.appointment.date
        ? `<div class="card"><h3>Rendez-vous programmé</h3><p>${escapeHtml(json.appointment.date)} ${escapeHtml(json.appointment.lieu || "")}</p></div>`
        : ""
    }
  `;
}

// ── Rendu principal ──────────────────────────────────────────
function render() {
  const app = document.getElementById("app");
  let body;
  if (state.loading) {
    body = `<div class="loading">Chargement…</div>`;
  } else {
    switch (state.route) {
      case "programme":
        body = viewProgramme();
        break;
      case "actus":
        body = viewActus();
        break;
      case "demarches":
        body = viewDemarches();
        break;
      case "suivi":
        body = viewSuivi();
        break;
      default:
        body = viewHome();
    }
  }

  app.innerHTML = `
    <header class="topbar">
      <h1>Bininga Citoyen</h1>
      <span class="badge">Officiel</span>
    </header>
    <div id="offline-banner" class="banner ${state.serverDown ? "show" : ""}">
      Serveur indisponible. Vérifiez votre connexion et réessayez.
    </div>
    <main>${body}</main>
    ${renderNav()}
  `;

  bindEvents();
}

function bindEvents() {
  document.querySelectorAll("[data-nav]").forEach((el) => {
    el.addEventListener("click", () => navigate(el.getAttribute("data-nav")));
  });

  document.querySelectorAll("[data-demarche-tab]").forEach((el) => {
    el.addEventListener("click", () => {
      demarchesTab = el.getAttribute("data-demarche-tab");
      render();
    });
  });

  const audienceForm = document.getElementById("form-audience");
  if (audienceForm) audienceForm.addEventListener("submit", (e) => { e.preventDefault(); handleDemarcheSubmit("audience", audienceForm); });

  const reclamationForm = document.getElementById("form-reclamation");
  if (reclamationForm) reclamationForm.addEventListener("submit", (e) => { e.preventDefault(); handleDemarcheSubmit("reclamation", reclamationForm); });

  const contactForm = document.getElementById("form-contact");
  if (contactForm) contactForm.addEventListener("submit", (e) => { e.preventDefault(); handleDemarcheSubmit("contact", contactForm); });

  const suiviForm = document.getElementById("form-suivi");
  if (suiviForm) suiviForm.addEventListener("submit", (e) => { e.preventDefault(); handleSuiviSubmit(suiviForm); });
}

// ── Utils ─────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function escapeAttr(str) {
  return String(str ?? "").replace(/"/g, "&quot;");
}

// ── Démarrage ──────────────────────────────────────────────────
(async function init() {
  const initialRoute = (window.location.hash || "#/home").replace("#/", "");
  state.route = VIEWS.includes(initialRoute) ? initialRoute : "home";
  render();
  await loadPublicData();
  render();
})();
