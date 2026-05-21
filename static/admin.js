// ══════════════════════════════════════════════════════════════════════════
//  SÉCURITÉ — Authentification par hachage SHA-256 (WebCrypto)
//  Les identifiants ne sont jamais stockés en clair dans le code.
// ══════════════════════════════════════════════════════════════════════════
// Session — jamais codée en dur ici, jamais dans sessionStorage
let SESSION_TOKEN        = "";
let SESSION_CSRF         = "";
let SESSION_ROLE         = "";
let SESSION_NOM          = "";
let SESSION_USERNAME     = "";
let SESSION_IS_MAIN_ADMIN = false;

// Helper : headers authentifiés avec CSRF
function authHeaders(extra) {
  return Object.assign({
    "Content-Type": "application/json",
    "X-Admin-Token": SESSION_TOKEN,
    "X-CSRF-Token": SESSION_CSRF,
  }, extra);
}

// Wrapper fetch avec détection session expirée
async function apiFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  if (res.status === 401) {
    showToast("Session expirée — reconnexion…", true);
    setTimeout(() => {
      SESSION_TOKEN = ""; SESSION_CSRF = ""; SESSION_ROLE = "";
      document.getElementById("app").classList.remove("visible");
      document.getElementById("login").classList.remove("hidden");
      document.getElementById("u").value = "";
      document.getElementById("p").value = "";
    }, 1500);
  }
  return res;
}

async function doLogin() {
  const u    = document.getElementById("u").value.trim();
  const p    = document.getElementById("p").value;
  const totp = (document.getElementById("totp")?.value || "").trim();
  const btn  = document.querySelector(".login-btn");
  btn.disabled = true;
  btn.textContent = "Connexion…";
  try {
    const payload = { username: u, password: p };
    if (totp) payload.totp_code = totp;
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.ok) {
      SESSION_TOKEN         = data.token;
      SESSION_CSRF          = data.csrf_token || "";
      SESSION_ROLE          = data.role;
      SESSION_NOM           = data.nom;
      SESSION_USERNAME      = data.username || "";
      SESSION_IS_MAIN_ADMIN = data.is_main_admin || false;
      window._sessionHas2fa = data.has_2fa || false;
      sessionStorage.setItem("bininga_session", JSON.stringify({ token: data.token, csrf: data.csrf_token || "", role: data.role, nom: data.nom, username: data.username || "", is_main_admin: data.is_main_admin || false, has_2fa: data.has_2fa || false }));
      // Masquer le champ 2FA après connexion
      const totpRow = document.getElementById("totp-row");
      if (totpRow) totpRow.style.display = "none";
      document.getElementById("login").classList.add("hidden");
      document.getElementById("app").classList.add("visible");
      document.getElementById("last-login").textContent = new Date().toLocaleString("fr-FR");
      const durLabel = data.trusted_ip ? "Session active 7 jours (IP de confiance)" : "";
      document.getElementById("topbar-user").textContent = data.nom + " · " + data.role + (durLabel ? "  |  " + durLabel : "");
      applyRoleUI(data.role);
      init();
      initNotifications();
    } else if (data.require_2fa) {
      // Afficher le champ 2FA
      const totpRow = document.getElementById("totp-row");
      if (totpRow) { totpRow.style.display = ""; document.getElementById("totp")?.focus(); }
      const errEl = document.getElementById("err");
      errEl.textContent = "Entrez votre code 2FA (application d'authentification).";
      setTimeout(() => errEl.textContent = "", 5000);
    } else {
      const errEl = document.getElementById("err");
      errEl.textContent = data.message || "Identifiant ou mot de passe incorrect.";
      setTimeout(() => errEl.textContent = "", 3500);
    }
  } catch(e) {
    const errEl = document.getElementById("err");
    errEl.textContent = "Erreur de connexion au serveur.";
    setTimeout(() => errEl.textContent = "", 3500);
  } finally {
    btn.disabled = false;
    btn.textContent = "Connexion";
  }
}

async function logout() {
  try {
    await fetch("/api/logout", { method: "POST", headers: { "X-Admin-Token": SESSION_TOKEN } });
  } catch (_) {}
  SESSION_TOKEN         = "";
  SESSION_ROLE          = "";
  SESSION_NOM           = "";
  SESSION_IS_MAIN_ADMIN = false;
  // Couper la connexion SSE proprement
  if (_sseRetryTimer) { clearTimeout(_sseRetryTimer); _sseRetryTimer = null; }
  if (_sseSource) { try { _sseSource.close(); } catch {} _sseSource = null; }
  sessionStorage.removeItem("bininga_session");
  document.getElementById("login").classList.remove("hidden");
  document.getElementById("app").classList.remove("visible");
  document.getElementById("u").value = "";
  document.getElementById("p").value = "";
}

document.addEventListener("keydown", e => {
  if (e.key === "Enter" && !document.getElementById("login").classList.contains("hidden")) doLogin();
});

// ══════════════════════════════════════════════════════════════════════════
//  RÔLES — Affichage selon les permissions
// ══════════════════════════════════════════════════════════════════════════
function applyRoleUI(role) {
  // .role-editeur = visible pour editeur ET admin
  const canEdit = role === "admin" || role === "editeur";
  document.querySelectorAll(".role-editeur").forEach(el => {
    el.style.display = canEdit ? "" : "none";
  });
  // .role-admin = visible pour admin seulement
  document.querySelectorAll(".role-admin").forEach(el => {
    el.style.display = SESSION_IS_MAIN_ADMIN ? "" : "none";
  });
  // .role-superadmin = réservé UNIQUEMENT à l'admin principal (Hero, À propos, Parcours)
  document.querySelectorAll(".role-superadmin").forEach(el => {
    el.style.display = role === "admin" ? "" : "none";
  });
  // .role-ministre = visible pour admin ET ministre uniquement
  document.querySelectorAll(".role-ministre").forEach(el => {
    el.style.display = (role === "admin" || role === "ministre") ? "" : "none";
  });
}

// ══════════════════════════════════════════════════════════════════════════
//  GESTION DES UTILISATEURS
// ══════════════════════════════════════════════════════════════════════════
let _editingUser = null;

function toggleUserForm(show) {
  const container = document.getElementById("user-form-container");
  const btn       = document.getElementById("btn-add-user");
  const visible   = show !== undefined ? show : container.style.display === "none";
  container.style.display = visible ? "" : "none";
  btn.textContent = visible ? "Fermer le formulaire" : "Ajouter un utilisateur";
  if (visible) container.scrollIntoView({ behavior: "smooth", block: "nearest" });
  if (!visible) resetUserForm();
}

function canDeleteUser(u) {
  // Impossible de supprimer : le ministre, soi-même, ou l'admin principal
  if (u.role === "ministre") return false;
  if (u.username === SESSION_USERNAME) return false;
  // Un admin ne peut supprimer un autre admin que s'il l'a créé (ou s'il est l'admin principal)
  if (u.role === "admin") {
    if (SESSION_IS_MAIN_ADMIN) return true;
    return u.created_by === SESSION_USERNAME;
  }
  return true;
}

function canEditUser(u) {
  // Impossible de modifier un admin si on ne l'a pas créé (sauf l'admin principal)
  if (u.role === "admin" && !SESSION_IS_MAIN_ADMIN) {
    return u.created_by === SESSION_USERNAME;
  }
  return true;
}

async function loadUsers() {
  const el = document.getElementById("user-list");
  el.innerHTML = '<div class="msg-empty">Chargement…</div>';
  try {
    const res  = await apiFetch("/api/users", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    setBadge("badge-users", data.ok ? data.users.length : 0);
    if (!data.ok || !data.users.length) {
      el.innerHTML = '<div class="msg-empty">Aucun utilisateur.</div>';
      return;
    }
    const roleLabels = { admin: "Admin", editeur: "Éditeur", lecteur: "Lecteur" };
    const initials   = u => (u.nom || u.username).charAt(0).toUpperCase();
    el.innerHTML = data.users.map(u => `
      <div class="user-item" data-username="${esc(u.username)}" data-nom="${esc(u.nom||u.username)}" data-role="${esc(u.role)}">
        <div class="user-avatar ${esc(u.role)}">${initials(u)}</div>
        <div class="user-info">
          <div class="user-name">${esc(u.nom || u.username)}</div>
          <div class="user-meta">${esc(u.username)}</div>
        </div>
        <span class="role-badge ${esc(u.role)}">${esc(roleLabels[u.role] || u.role)}</span>
        ${canEditUser(u) ? `<button class="sbtn sbtn-progress" style="margin-left:8px" onclick="editUser(this.closest('.user-item').dataset.username,this.closest('.user-item').dataset.nom,this.closest('.user-item').dataset.role)">Modifier</button>` : ''}
        ${canDeleteUser(u) ? `<button class="btn-danger" style="padding:5px 10px" onclick="deleteUser(this.closest('.user-item').dataset.username)">Supprimer</button>` : ''}
      </div>
    `).join("");
  } catch {
    el.innerHTML = '<div class="msg-empty">Serveur non disponible.</div>';
  }
}

function editUser(username, nom, role) {
  _editingUser = username;
  document.getElementById("uf-username").value    = username;
  document.getElementById("uf-username").disabled = true;
  document.getElementById("uf-nom").value         = nom;
  document.getElementById("uf-password").value    = "";
  document.getElementById("uf-role").value        = role;
  document.getElementById("user-form-title").textContent = "Modifier l'utilisateur · " + username;
  toggleUserForm(true);
}

function resetUserForm() {
  _editingUser = null;
  document.getElementById("uf-username").value    = "";
  document.getElementById("uf-username").disabled = false;
  document.getElementById("uf-nom").value         = "";
  document.getElementById("uf-password").value    = "";
  document.getElementById("uf-role").value        = "lecteur";
  document.getElementById("user-form-title").textContent = "Ajouter un utilisateur";
}

async function submitUserForm() {
  const payload = {
    username: document.getElementById("uf-username").value.trim(),
    nom:      document.getElementById("uf-nom").value.trim(),
    password: document.getElementById("uf-password").value,
    role:     document.getElementById("uf-role").value,
  };
  if (!payload.username) { showToast("L'identifiant est requis", true); return; }
  try {
    const res  = await apiFetch("/api/users/upsert", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.ok) {
      showToast(_editingUser ? "Utilisateur modifié !" : "Utilisateur créé !");
      resetUserForm();
      loadUsers();
    } else {
      showToast(data.message || "Erreur", true);
    }
  } catch { showToast("Serveur non disponible", true); }
}

async function deleteUser(username) {
  if (!confirm(`Supprimer l'utilisateur « ${username} » ?`)) return;
  try {
    const res  = await apiFetch("/api/users/delete", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ username })
    });
    const data = await res.json();
    if (data.ok) { showToast("Utilisateur supprimé"); loadUsers(); }
    else showToast(data.message || "Erreur", true);
  } catch { showToast("Serveur non disponible", true); }
}

// ══════════════════════════════════════════════════════════════════════════
//  INITIALISATION
// ══════════════════════════════════════════════════════════════════════════
let siteData = {};

let _contactsPoller = null;

function _startContactsPoller() {
  if (_contactsPoller) clearInterval(_contactsPoller);
  // Sync toutes les 2 minutes (filet de sécurité si le SSE se coupe)
  _contactsPoller = setInterval(() => {
    if (!SESSION_TOKEN) return;
    syncMessages().then(() => {
      if (_currentPanel === "contacts")     renderContacts();
      if (_currentPanel === "audiences")    renderAudiences();
      if (_currentPanel === "reclamations") renderReclamations();
      if (_currentPanel === "dashboard")    refreshDashboard();
    });
  }, 2 * 60 * 1000);
}

function init() {
  loadSiteData();
  syncMessages().then(() => refreshDashboard());
  startNewsPoller();
  _startContactsPoller();
  // Resync + reconnexion SSE quand l'onglet redevient visible (mobile: retour d'écran off)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && SESSION_TOKEN) {
      syncMessages().then(() => {
        if (_currentPanel === "contacts")     renderContacts();
        if (_currentPanel === "audiences")    renderAudiences();
        if (_currentPanel === "reclamations") renderReclamations();
        if (_currentPanel === "dashboard")    refreshDashboard();
      });
      // Reconnecter le SSE si coupé
      if (!_sseSource) _connectSSE();
    }
  });
  // Badge initial
  apiFetch("/api/news", { headers: { "X-Admin-Token": SESSION_TOKEN } })
    .then(r => r.json())
    .then(d => { if(d.ok) setBadge("badge-veille", (d.items||[]).filter(a=>!a.read).length); })
    .catch(()=>{});
  // Auto-sauvegarde : écoute tous les inputs/textareas/selects du panneau admin
  document.getElementById("app").addEventListener("input", e => {
    const tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") scheduleAutoSave();
  });
  document.getElementById("app").addEventListener("change", e => {
    const tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") scheduleAutoSave();
  });
}

// ── Synchronisation des messages depuis le serveur ──────────────────────
async function syncMessages() {
  try {
    const res = await apiFetch("/api/contacts", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    if (!data.ok) return;

    const mapping = [
      ["bininga_audiences", data.audiences || []],
      ["bininga_contacts",  data.contacts  || []]
    ];

    for (const [key, serverList] of mapping) {
      const localList = JSON.parse(localStorage.getItem(key) || "[]");
      // Construire un index des métadonnées locales (_status, _notes, _pinged) par _id
      const localMeta = {};
      localList.forEach(m => { if (m._id) localMeta[m._id] = m; });

      // Fusionner : données serveur + métadonnées locales
      const serverIds = new Set(serverList.map(m => m._id).filter(Boolean));
      const merged = serverList.map(m => {
        const local = localMeta[m._id] || {};
        return Object.assign({}, m, {
          _status: local._status || m._status,
          _notes:  local._notes  || m._notes,
          _pinged: local._pinged || m._pinged
        });
      });

      // Conserver les entrées locales absentes du serveur (redéploiement ou hors-ligne)
      localList.filter(m => !serverIds.has(m._id || "__none__")).forEach(m => merged.push(m));

      localStorage.setItem(key, JSON.stringify(merged));
    }
  } catch (_) {
    // Serveur non disponible — le localStorage existant est utilisé
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  GALERIE
// ══════════════════════════════════════════════════════════════════════════
function renderGalerie() {
  renderSlides();
  renderGrid();
}

function renderSlides() {
  const slides = (siteData.gallery && siteData.gallery.slides) || [];
  const list = document.getElementById("slides-list");
  if (!slides.length) {
    list.innerHTML = '<div class="msg-empty">Aucune slide. Cliquez sur "+ Ajouter".</div>';
    return;
  }
  list.innerHTML = slides.map((s, i) => `
    <div class="stats-row" style="grid-template-columns:90px 1fr 1fr auto;gap:12px;align-items:start;padding:14px 0">
      <div style="text-align:center">
        <div style="width:80px;height:56px;border-radius:6px;overflow:hidden;background:#1c1c1c;display:flex;align-items:center;justify-content:center;margin-bottom:6px;border:1px solid rgba(255,255,255,.08)">
          ${s.image
            ? `<img src="${esc(s.image)}" style="width:100%;height:100%;object-fit:cover">`
            : `<span style="font-size:24px">Image</span>`}
        </div>
        <button class="sbtn sbtn-progress" style="font-size:10px;padding:4px 8px" onclick="uploadForSlide(${i})">Photo</button>
      </div>
      <div class="form-group" style="margin:0">
        <label>Titre</label>
        <input type="text" value="${esc(s.title||'')}" placeholder="Titre de la slide"
          oninput="updSlide(${i},'title',this.value)">
        <label style="margin-top:8px">Emoji (si pas de photo)</label>
        <input type="text" value="${esc(s.emoji||'')}" placeholder="Icône"
          oninput="updSlide(${i},'emoji',this.value)" style="width:80px">
      </div>
      <div class="form-group" style="margin:0">
        <label>Sous-titre</label>
        <textarea oninput="updSlide(${i},'subtitle',this.value)"
          style="min-height:72px">${esc(s.subtitle||'')}</textarea>
      </div>
      <div style="padding-top:22px;display:flex;flex-direction:column;gap:6px">
        <button class="btn-danger" onclick="delSlide(${i})" title="Supprimer">Supprimer</button>
        ${i > 0 ? `<button class="sbtn sbtn-wait" onclick="moveSlide(${i},-1)" title="Monter">↑</button>` : ''}
        ${i < slides.length-1 ? `<button class="sbtn sbtn-wait" onclick="moveSlide(${i},1)" title="Descendre">↓</button>` : ''}
      </div>
    </div>
  `).join('<div style="border-bottom:1px solid rgba(255,255,255,.05)"></div>');
}

function renderGrid() {
  const grid = (siteData.gallery && siteData.gallery.grid) || [];
  const list = document.getElementById("grid-list");
  if (!grid.length) {
    list.innerHTML = '<div class="msg-empty">Aucune photo. Cliquez sur "+ Ajouter".</div>';
    return;
  }
  list.innerHTML = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:8px 0">` +
    grid.map((g, i) => `
      <div style="background:var(--n3);border:1px solid rgba(255,255,255,.07);border-radius:8px;padding:10px;text-align:center">
        <div style="width:100%;aspect-ratio:1;border-radius:6px;overflow:hidden;background:#111;display:flex;align-items:center;justify-content:center;margin-bottom:8px">
          ${g.image
            ? `<img src="${esc(g.image)}" style="width:100%;height:100%;object-fit:cover">`
            : `<span style="font-size:32px">Image</span>`}
        </div>
        <input type="text" value="${esc(g.alt||'')}" placeholder="Description"
          oninput="updGrid(${i},'alt',this.value)"
          style="width:100%;font-size:11px;margin-bottom:6px">
        <div style="display:flex;gap:4px;justify-content:center">
          <button class="sbtn sbtn-progress" style="font-size:10px;padding:3px 7px" onclick="uploadForGrid(${i})">Photo</button>
          <input type="text" value="${esc(g.emoji||'')}" placeholder="Icône"
            oninput="updGrid(${i},'emoji',this.value)"
            style="width:42px;font-size:13px;text-align:center">
          <button class="btn-danger" style="font-size:11px;padding:3px 7px" onclick="delGrid(${i})">Supprimer</button>
        </div>
      </div>
    `).join("") + `</div>`;
}

// ── Upload d'image ─────────────────────────────────────────────────────────
function uploadImage(callback) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.onchange = e => {
    const file = e.target.files[0];
    if (!file) return;

    // Barre de progression
    const progressBar = document.getElementById("upload-progress-bar");
    const progressWrap = document.getElementById("upload-progress-wrap");
    if (progressWrap) progressWrap.style.display = "block";
    if (progressBar) { progressBar.style.width = "0%"; progressBar.textContent = "0%"; }

    const formData = new FormData();
    formData.append("file", file);
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", ev => {
      if (ev.lengthComputable && progressBar) {
        const pct = Math.round((ev.loaded / ev.total) * 100);
        progressBar.style.width = pct + "%";
        progressBar.textContent = pct + "%";
      }
    });

    xhr.addEventListener("load", () => {
      if (progressWrap) progressWrap.style.display = "none";
      try {
        const data = JSON.parse(xhr.responseText);
        if (data.ok) { callback(data.path); showToast("Photo uploadée !"); }
        else showToast("Erreur : " + data.message, true);
      } catch { showToast("Réponse invalide du serveur", true); }
    });

    xhr.addEventListener("error", () => {
      if (progressWrap) progressWrap.style.display = "none";
      showToast("Serveur non disponible", true);
    });

    xhr.open("POST", "/api/upload");
    xhr.setRequestHeader("X-Admin-Token", SESSION_TOKEN);
    xhr.setRequestHeader("X-CSRF-Token", SESSION_CSRF);
    xhr.send(formData);
  };
  input.click();
}

function uploadForSlide(i) {
  pickOrUploadImage(path => {
    if (!siteData.gallery) siteData.gallery = { slides: [], grid: [] };
    siteData.gallery.slides[i].image = path;
    renderSlides();
  });
}

function uploadForGrid(i) {
  pickOrUploadImage(path => {
    if (!siteData.gallery) siteData.gallery = { slides: [], grid: [] };
    siteData.gallery.grid[i].image = path;
    renderGrid();
  });
}

function uploadFeaturedImage() {
  pickOrUploadImage(path => {
    if (!siteData.actus) siteData.actus = { featured: {}, items: [] };
    if (!siteData.actus.featured) siteData.actus.featured = {};
    siteData.actus.featured.image = path;
    const el = document.getElementById("feat-img-path");
    if (el) el.textContent = path;
    showToast("Photo de l'article mise à jour !");
  });
}

// ── CRUD Slides ────────────────────────────────────────────────────────────
function updSlide(i, field, val) {
  if (siteData.gallery && siteData.gallery.slides[i])
    siteData.gallery.slides[i][field] = val;
}
function delSlide(i) {
  if (!confirm("Supprimer cette slide ?")) return;
  siteData.gallery.slides.splice(i, 1);
  renderSlides();
  saveData(true);
  showToast("Slide supprimée");
}
function addSlide() {
  if (!siteData.gallery) siteData.gallery = { slides: [], grid: [] };
  siteData.gallery.slides.push({ image: "", emoji: "", title: "", subtitle: "" });
  renderSlides();
}
function moveSlide(i, dir) {
  const arr = siteData.gallery.slides;
  const j = i + dir;
  if (j < 0 || j >= arr.length) return;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  renderSlides();
}

// ── CRUD Grid ──────────────────────────────────────────────────────────────
function updGrid(i, field, val) {
  if (siteData.gallery && siteData.gallery.grid[i])
    siteData.gallery.grid[i][field] = val;
}
function delGrid(i) {
  if (!confirm("Supprimer cette photo ?")) return;
  siteData.gallery.grid.splice(i, 1);
  renderGrid();
  saveData(true);
  showToast("Photo supprimée");
}
function addGridPhoto() {
  if (!siteData.gallery) siteData.gallery = { slides: [], grid: [] };
  siteData.gallery.grid.push({ image: "", alt: "", emoji: "" });
  renderGrid();
}

// ══════════════════════════════════════════════════════════════════════════
//  ACTUALITÉS
// ══════════════════════════════════════════════════════════════════════════
// Articles par défaut (issus du HTML statique de index.html)
function renderActus() {
  if (!siteData.actus) siteData.actus = {};
  renderActuSlides();
  renderActuVedettes();
  renderActuCards();
}

// ── SLIDES ────────────────────────────────────────────────────────────
function renderActuSlides() {
  const slides = (siteData.actus && siteData.actus.slides) || [];
  const el = document.getElementById("actu-slides-list");
  const ct = document.getElementById("slides-count");
  if (ct) ct.textContent = slides.length ? `(${slides.length})` : "";
  if (!slides.length) { el.innerHTML = '<div class="msg-empty">Aucune slide. Cliquez sur "+ Ajouter".</div>'; return; }
  el.innerHTML = slides.map((s, i) => `
    <div style="background:var(--n3);border-radius:8px;padding:16px;margin-bottom:12px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.3)">Slide ${i+1}</div>
        <button class="btn-danger" onclick="delActuSlide(${i})" title="Supprimer">Supprimer</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div class="form-group" style="margin:0"><label>Image</label><div style="display:flex;gap:6px;align-items:center"><input type="text" id="actu-slide-img-${i}" value="${esc(s.image||'')}" placeholder="images/photo.jpg" oninput="updActuSlide(${i},'image',this.value)" style="flex:1"><button class="sbtn sbtn-progress" style="font-size:10px;padding:4px 8px;white-space:nowrap" onclick="uploadForActuSlide(${i})">Upload</button></div></div>
        <div class="form-group" style="margin:0"><label>Texte alt</label><input type="text" value="${esc(s.alt||'')}" oninput="updActuSlide(${i},'alt',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Badge (chip)</label><input type="text" value="${esc(s.chip||'')}" oninput="updActuSlide(${i},'chip',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Couleur badge (vide = rouge)</label><input type="text" value="${esc(s.chipColor||'')}" placeholder="#2e7d32" oninput="updActuSlide(${i},'chipColor',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Date / lieu</label><input type="text" value="${esc(s.date||'')}" oninput="updActuSlide(${i},'date',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Titre (\\n pour saut de ligne)</label><input type="text" value="${esc(s.title||'')}" oninput="updActuSlide(${i},'title',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Sous-titre</label><textarea rows="2" oninput="updActuSlide(${i},'subtitle',this.value)">${esc(s.subtitle||'')}</textarea></div>
      </div>
    </div>`).join('');
}
function updActuSlide(i, f, v) { if (siteData.actus.slides[i]) siteData.actus.slides[i][f] = v; }
function uploadForActuSlide(i) {
  pickOrUploadImage(path => {
    if (siteData.actus.slides[i]) siteData.actus.slides[i].image = path;
    const el = document.getElementById("actu-slide-img-" + i);
    if (el) el.value = path;
  });
}
function addActuSlide() {
  if (!siteData.actus.slides) siteData.actus.slides = [];
  siteData.actus.slides.push({ image:"", alt:"", chip:"", chipColor:"", date:"", title:"", subtitle:"" });
  renderActuSlides();
}
function delActuSlide(i) {
  if (!confirm("Supprimer cette slide ?")) return;
  siteData.actus.slides.splice(i, 1); renderActuSlides(); saveData(true); showToast("Slide supprimée");
}

// ── VEDETTES ──────────────────────────────────────────────────────────
function renderActuVedettes() {
  const vedettes = (siteData.actus && siteData.actus.vedettes) || [];
  const el = document.getElementById("actu-vedettes-list");
  const ct = document.getElementById("vedettes-count");
  if (ct) ct.textContent = vedettes.length ? `(${vedettes.length})` : "";
  if (!vedettes.length) { el.innerHTML = '<div class="msg-empty">Aucun article. Cliquez sur "+ Ajouter".</div>'; return; }
  el.innerHTML = vedettes.map((v, i) => `
    <div style="background:var(--n3);border-radius:8px;padding:16px;margin-bottom:14px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.3)">Article ${i+1}</div>
        <button class="btn-danger" onclick="delActuVedette(${i})" title="Supprimer">Supprimer</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div class="form-group" style="margin:0"><label>Image</label><div style="display:flex;gap:6px;align-items:center"><input type="text" id="actu-vedette-img-${i}" value="${esc(v.image||'')}" placeholder="images/photo.jpg" oninput="updActuVedette(${i},'image',this.value)" style="flex:1"><button class="sbtn sbtn-progress" style="font-size:10px;padding:4px 8px;white-space:nowrap" onclick="uploadForActuVedette(${i})">Upload</button></div></div>
        <div class="form-group" style="margin:0"><label>Badge (ex: Diplomatie)</label><input type="text" value="${esc(v.badge||'')}" oninput="updActuVedette(${i},'badge',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Couleur badge (vide = rouge)</label><input type="text" value="${esc(v.badgeColor||'')}" placeholder="#2e7d32" oninput="updActuVedette(${i},'badgeColor',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Catégorie</label><input type="text" value="${esc(v.tag||'')}" oninput="updActuVedette(${i},'tag',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Couleur catégorie (vide = blanc)</label><input type="text" value="${esc(v.tagColor||'')}" placeholder="#4caf50" oninput="updActuVedette(${i},'tagColor',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Date / lieu affiché</label><input type="text" value="${esc(v.date||'')}" oninput="updActuVedette(${i},'date',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Titre de l'article</label><input type="text" value="${esc(v.title||'')}" oninput="updActuVedette(${i},'title',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Paragraphe 1</label><textarea rows="3" oninput="updActuVedette(${i},'text1',this.value)">${esc(v.text1||'')}</textarea></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Citation (encadré)</label><textarea rows="2" oninput="updActuVedette(${i},'quote',this.value)">${esc(v.quote||'')}</textarea></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Paragraphe 2</label><textarea rows="3" oninput="updActuVedette(${i},'text2',this.value)">${esc(v.text2||'')}</textarea></div>
        <div class="form-group" style="margin:0;grid-column:span 2">
          <label>Tags (un par ligne)</label>
          <textarea rows="3" oninput="updActuVedetteTags(${i},this.value)">${esc((v.tags||[]).join('\n'))}</textarea>
        </div>
        <div style="grid-column:span 2;font-size:11px;color:rgba(255,255,255,.25);margin-top:4px">Si pas d'image : renseignez les champs ci-dessous pour le placeholder</div>
        <div class="form-group" style="margin:0"><label>Visuel de remplacement</label><input type="text" value="${esc(v.placeholderEmoji||'')}" placeholder="Icône" oninput="updActuVedette(${i},'placeholderEmoji',this.value)" style="max-width:80px"></div>
        <div class="form-group" style="margin:0"><label>Titre placeholder (\\n = saut)</label><input type="text" value="${esc(v.placeholderTitle||'')}" oninput="updActuVedette(${i},'placeholderTitle',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Date placeholder</label><input type="text" value="${esc(v.placeholderDate||'')}" oninput="updActuVedette(${i},'placeholderDate',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Fond placeholder (CSS)</label><input type="text" value="${esc(v.imageBg||'')}" placeholder="linear-gradient(…)" oninput="updActuVedette(${i},'imageBg',this.value)"></div>
      </div>
    </div>`).join('');
}
function updActuVedette(i, f, v) { if (siteData.actus.vedettes[i]) siteData.actus.vedettes[i][f] = v; }
function uploadForActuVedette(i) {
  pickOrUploadImage(path => {
    if (siteData.actus.vedettes[i]) siteData.actus.vedettes[i].image = path;
    const el = document.getElementById("actu-vedette-img-" + i);
    if (el) el.value = path;
  });
}
function updActuVedetteTags(i, val) { if (siteData.actus.vedettes[i]) siteData.actus.vedettes[i].tags = val.split('\n').map(t=>t.trim()).filter(t=>t); }
function addActuVedette() {
  if (!siteData.actus.vedettes) siteData.actus.vedettes = [];
  siteData.actus.vedettes.push({ image:"", badge:"", tag:"", date:"", title:"", text1:"", quote:"", text2:"", tags:[] });
  renderActuVedettes();
}
function delActuVedette(i) {
  if (!confirm("Supprimer cet article vedette ?")) return;
  siteData.actus.vedettes.splice(i, 1); renderActuVedettes(); saveData(true); showToast("Article supprimé");
}

// ── CARDS ─────────────────────────────────────────────────────────────
function renderActuCards() {
  const cards = (siteData.actus && siteData.actus.cards) || [];
  const el = document.getElementById("actu-cards-list");
  const ct = document.getElementById("cards-count");
  if (ct) ct.textContent = cards.length ? `(${cards.length})` : "";
  if (!cards.length) { el.innerHTML = '<div class="msg-empty">Aucune carte. Cliquez sur "+ Ajouter".</div>'; return; }
  el.innerHTML = cards.map((c, i) => `
    <div style="background:var(--n3);border-radius:8px;padding:14px;margin-bottom:10px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
        <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.3)">Carte ${i+1}</div>
        <button class="btn-danger" onclick="delActuCard(${i})" title="Supprimer">Supprimer</button>
      </div>
      <div style="display:grid;grid-template-columns:50px 50px 70px 1fr 1fr auto;gap:8px;align-items:start">
        <div class="form-group" style="margin:0"><label>Icône</label><input type="text" value="${esc(c.icon||'')}" oninput="updActuCard(${i},'icon',this.value)" style="text-align:center"></div>
        <div class="form-group" style="margin:0"><label>Jour</label><input type="text" value="${esc(c.day||'')}" oninput="updActuCard(${i},'day',this.value)" style="text-align:center;font-weight:700"></div>
        <div class="form-group" style="margin:0"><label>Mois</label><input type="text" value="${esc(c.month||'')}" oninput="updActuCard(${i},'month',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Année</label><input type="text" value="${esc(c.year||'')}" oninput="updActuCard(${i},'year',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Catégorie</label><input type="text" value="${esc(c.cat||'')}" oninput="updActuCard(${i},'cat',this.value)"></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">
        <div class="form-group" style="margin:0"><label>Couleur catégorie (vide = blanc)</label><input type="text" value="${esc(c.catColor||'')}" placeholder="#4caf50" oninput="updActuCard(${i},'catColor',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Couleur bordure (vide = défaut)</label><input type="text" value="${esc(c.borderColor||'')}" placeholder="rgba(46,125,50,.25)" oninput="updActuCard(${i},'borderColor',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Titre</label><input type="text" value="${esc(c.title||'')}" oninput="updActuCard(${i},'title',this.value)"></div>
        <div class="form-group" style="margin:0;grid-column:span 2"><label>Description</label><textarea rows="2" oninput="updActuCard(${i},'desc',this.value)">${esc(c.desc||'')}</textarea></div>
      </div>
    </div>`).join('');
}
function updActuCard(i, f, v) { if (siteData.actus.cards[i]) siteData.actus.cards[i][f] = v; }
function addActuCard() {
  if (!siteData.actus.cards) siteData.actus.cards = [];
  siteData.actus.cards.push({ icon:"", day:"", month:"", year:"", cat:"", catColor:"", borderColor:"", title:"", desc:"" });
  renderActuCards();
}
function delActuCard(i) {
  if (!confirm("Supprimer cette carte ?")) return;
  siteData.actus.cards.splice(i, 1); renderActuCards(); saveData(true); showToast("Carte supprimée");
}

function collectActus() {
  // Tout est déjà mis à jour en temps réel via oninput
}

// ══════════════════════════════════════════════════════════════════════════
//  CONTENU DU SITE (data.json via server.py)
// ══════════════════════════════════════════════════════════════════════════
function loadSiteData() {
  apiFetch("/api/load")
    .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(applyData)
    .catch(() => {
      // Fallback : lecture directe de data.json (sans serveur)
      fetch("data.json?t=" + Date.now())
        .then(r => r.json())
        .then(applyData)
        .catch(() => showToast("Impossible de charger les données", true));
    });
}

function applyData(d) {
  siteData = d;
  [populateForm, renderStats, renderActus, renderGalerie, renderParcours, renderProgramme, renderEngCards]
    .forEach(fn => { try { fn(); } catch(e) { console.error(fn.name, e); } });
}

function populateForm() {
  document.querySelectorAll("[data-key]").forEach(el => {
    const keys = el.dataset.key.split(".");
    let val = siteData;
    keys.forEach(k => val = (val && val[k] !== undefined) ? val[k] : "");
    el.value = val;
  });
  // Biographie : paragraphs → textarea (un paragraphe par bloc, séparé par ligne vide)
  const pTa = document.getElementById("about-paragraphs-ta");
  if (pTa) {
    const ps = (siteData.about || {}).paragraphs || [];
    pTa.value = ps.join("\n\n");
  }
  // Badges → textarea (un par ligne)
  const bTa = document.getElementById("about-badges-ta");
  if (bTa) {
    const bs = (siteData.about || {}).badges || [];
    bTa.value = bs.join("\n");
  }
  // CTA — boutons (objets imbriqués)
  const cta = siteData.cta || {};
  [1,2,3].forEach(n => {
    const btn = cta["btn"+n] || {};
    const t = document.getElementById("cta-btn"+n+"-text");
    const h = document.getElementById("cta-btn"+n+"-href");
    if (t) t.value = btn.text || "";
    if (h) h.value = btn.href || "";
  });
}

function renderStats() {
  const list = document.getElementById("stats-list");
  list.innerHTML = "";
  (siteData.stats || []).forEach((s, i) => {
    const div = document.createElement("div");
    div.className = "stats-row";
    div.innerHTML = `
      <div class="form-group" style="margin:0">
        <label>Chiffre ${i+1}</label>
        <input type="text" value="${esc(s.num||'')}" onchange="siteData.stats[${i}].num=this.value">
      </div>
      <div class="form-group" style="margin:0">
        <label>Libellé ${i+1}</label>
        <input type="text" value="${esc(s.label||'')}" onchange="siteData.stats[${i}].label=this.value">
      </div>
    `;
    list.appendChild(div);
  });
}

function collectForm() {
  document.querySelectorAll("[data-key]").forEach(el => {
    const keys = el.dataset.key.split(".");
    let obj = siteData;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!obj[keys[i]]) obj[keys[i]] = {};
      obj = obj[keys[i]];
    }
    obj[keys[keys.length-1]] = el.value;
  });
  // Biographie : textarea → array de paragraphes (split sur lignes vides)
  const pTa = document.getElementById("about-paragraphs-ta");
  if (pTa) {
    if (!siteData.about) siteData.about = {};
    siteData.about.paragraphs = pTa.value.split(/\n\s*\n/).map(p => p.trim()).filter(p => p);
  }
  // Badges : textarea → array (une ligne = un badge)
  const bTa = document.getElementById("about-badges-ta");
  if (bTa) {
    if (!siteData.about) siteData.about = {};
    siteData.about.badges = bTa.value.split("\n").map(b => b.trim()).filter(b => b);
  }
  // CTA buttons (collect from manual id inputs)
  if (!siteData.cta) siteData.cta = {};
  [1,2,3].forEach(n => {
    const t = document.getElementById("cta-btn"+n+"-text");
    const h = document.getElementById("cta-btn"+n+"-href");
    if (t || h) {
      if (!siteData.cta["btn"+n] || typeof siteData.cta["btn"+n] !== "object") siteData.cta["btn"+n] = {};
      if (t) siteData.cta["btn"+n].text = t.value;
      if (h) siteData.cta["btn"+n].href = h.value;
    }
  });
}

// ── CTA buttons (nested objects non gérés par data-key) ──────────────
function updCtaBtn(n, field, val) {
  if (!siteData.cta) siteData.cta = {};
  if (!siteData.cta["btn"+n] || typeof siteData.cta["btn"+n] !== "object") siteData.cta["btn"+n] = {};
  siteData.cta["btn"+n][field] = val;
}

// ── Engagement — cards ────────────────────────────────────────────────
function renderEngCards() {
  const el = document.getElementById("eng-cards-list");
  if (!el) return;
  const cards = (siteData.engagement && siteData.engagement.cards) || [];
  el.innerHTML = cards.map((c, i) => `
    <div style="background:var(--n3);border-radius:8px;padding:14px 16px;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:10px">Carte ${i+1}</div>
      <div class="form-group" style="margin-bottom:8px"><label>Icône</label><input type="text" value="${esc(c.icon||'')}" oninput="siteData.engagement.cards[${i}].icon=this.value" style="max-width:80px"></div>
      <div class="form-group" style="margin-bottom:8px"><label>Titre</label><input type="text" value="${esc(c.title||'')}" oninput="siteData.engagement.cards[${i}].title=this.value"></div>
      <div class="form-group" style="margin:0"><label>Description</label><input type="text" value="${esc(c.desc||'')}" oninput="siteData.engagement.cards[${i}].desc=this.value"></div>
    </div>`).join("");
}

// ── Auto-sauvegarde ───────────────────────────────────────────────────
let _autoSaveTimer = null;
let _autoSaving = false;

function scheduleAutoSave() {
  clearTimeout(_autoSaveTimer);
  const ind = document.getElementById("autosave-indicator");
  if (ind) { ind.textContent = "Modification en cours…"; ind.className = "autosave-pending"; }
  _autoSaveTimer = setTimeout(() => saveData(true), 1500);
}

async function forceSyncData() {
  const ok = prompt("Action dangereuse : cela remplace la base actuelle par data.json.\nTapez RESTAURER pour confirmer.");
  if (ok !== "RESTAURER") return;
  const btn = document.getElementById("btn-force-sync");
  if (btn) { btn.textContent = "Restauration…"; btn.disabled = true; }
  try {
    const res  = await apiFetch("/api/admin/force-sync", { method: "POST", headers: authHeaders() });
    const data = await res.json();
    if (data.ok) {
      showToast("Contenu restauré — galerie, articles et parcours rechargés");
      setTimeout(() => { loadSiteData(); }, 800);
    } else {
      showToast(data.message || "Erreur lors de la restauration", true);
    }
  } catch (e) {
    showToast("Erreur : " + e.message, true);
  } finally {
    if (btn) { btn.textContent = "Restaurer data.json"; btn.disabled = false; }
  }
}

function saveData(silent = false) {
  if (_autoSaving) return;
  _autoSaving = true;
  collectForm();
  collectActus();
  collectProgramme();
  const ind = document.getElementById("autosave-indicator");
  const saveBtn = document.getElementById("btn-save");
  if (ind) { ind.textContent = "Sauvegarde…"; ind.className = "autosave-saving"; }
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.classList.add("is-saving");
    saveBtn.textContent = "Sauvegarde en cours…";
  }
  apiFetch("/api/save", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(siteData)
  })
  .then(r => r.json())
  .then(res => {
    if (res.ok) {
      if (!silent) showToast("Contenu sauvegardé !");
      if (saveBtn) {
        saveBtn.classList.remove("is-saving");
        saveBtn.classList.add("is-saved");
        saveBtn.textContent = "Sauvegardé";
        setTimeout(() => saveBtn.classList.remove("is-saved"), 1400);
      }
      if (ind) { ind.textContent = "Sauvegardé"; ind.className = "autosave-ok"; setTimeout(() => { if(ind) ind.textContent = ""; ind.className = ""; }, 3000); }
    } else {
      showToast(res.message, true);
      if (ind) { ind.textContent = "Erreur sauvegarde"; ind.className = "autosave-err"; }
    }
  })
  .catch(() => {
    showToast("Serveur non disponible (mode GitHub Pages)", true);
    if (ind) { ind.textContent = "Hors ligne"; ind.className = "autosave-err"; }
  })
  .finally(() => {
    _autoSaving = false;
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.classList.remove("is-saving");
      if (!saveBtn.classList.contains("is-saved")) saveBtn.textContent = "Enregistrer le contenu";
      else setTimeout(() => { saveBtn.textContent = "Enregistrer le contenu"; }, 900);
    }
  });
}

// ══════════════════════════════════════════════════════════════════════════
//  DASHBOARD
// ══════════════════════════════════════════════════════════════════════════
function refreshDashboard() {
  // Stats contacts depuis le serveur
  apiFetch("/api/stats", { headers: { "X-Admin-Token": SESSION_TOKEN } })
    .then(r => r.json())
    .then(s => {
      if (!s.ok) throw new Error("stats ko");
      setText("kpi-aud-total",    s.aud_total);
      setText("kpi-aud-wait",     s.aud_wait);
      setText("kpi-aud-progress", s.aud_progress);
      setText("kpi-aud-done",     s.aud_done);
      setText("kpi-recl",         s.recl_wait);
      setText("kpi-ct",           s.ct_total);
      setBadge("badge-aud",  s.aud_wait);
      setBadge("badge-recl", s.recl_wait);
      setBadge("badge-ct",   s.ct_unread);
      // Compteurs de visites (depuis le serveur, pas localStorage)
      if (s.visitors) {
        setText("kpi-visit", s.visitors.total ?? "—");
        setText("kpi-prog",  s.visitors.prog_views ?? "—");
      }
    })
    .catch(() => {});
  // Stats visites publiques (endpoint sans token)
  fetch("/api/visit-stats")
    .then(r => r.json())
    .then(v => {
      if (v.ok) {
        setText("kpi-visit", v.total    ?? "—");
        setText("kpi-prog",  v.prog_views ?? "—");
      }
    })
    .catch(() => {});
  _refreshDashboardLocal();
}

function _refreshDashboardLocal() {
  const aud  = getAll("bininga_audiences");
  const ct   = getAll("bininga_contacts");

  const audiences    = aud.filter(m => m.objet !== "Réclamation");
  const reclamations = aud.filter(m => m.objet === "Réclamation");
  const wait     = audiences.filter(m => !m._status || m._status === "en_attente").length;
  const inprog   = audiences.filter(m => m._status === "en_cours").length;
  const done     = audiences.filter(m => m._status === "traite").length;
  const reclWait = reclamations.filter(m => !m._status || m._status !== "traite").length;
  const ctUnread = ct.filter(m => !m._status || m._status === "non_lu").length;

  setBadge("badge-aud",  wait);
  setBadge("badge-recl", reclWait);
  setBadge("badge-ct",   ctUnread);

  // Répartition graphique
  const total = audiences.length || 1;
  document.getElementById("aud-breakdown").innerHTML = [
    { label:"En attente", count:wait,   color:"#f39c12", pct:Math.round(wait/total*100) },
    { label:"En cours",   count:inprog, color:"#3498db", pct:Math.round(inprog/total*100) },
    { label:"Traitées",   count:done,   color:"#2ecc71", pct:Math.round(done/total*100) },
    { label:"Réclamations", count:reclamations.length, color:"#C8102E", pct:Math.round(reclamations.length/(aud.length||1)*100) },
  ].map(r => `
    <div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span style="font-size:12px;color:rgba(255,255,255,.55)">${esc(r.label)}</span>
        <span style="font-size:13px;font-weight:700;color:${r.color}">${Number(r.count)}</span>
      </div>
      <div class="prog-bar">
        <div class="prog-bar-fill" style="width:${r.pct}%;background:${r.color}"></div>
      </div>
    </div>
  `).join("");

  // Feed activité récente
  const all = [
    ...aud.map(m => ({...m, _type:"audience"})),
    ...ct.map(m => ({...m, _type:"contact"}))
  ].sort((a,b) => new Date(b._date||0) - new Date(a._date||0)).slice(0,6);

  const feed = document.getElementById("feed");
  if (!all.length) {
    feed.innerHTML = '<div class="msg-empty" style="padding:30px">Aucune activité pour le moment.</div>';
    return;
  }
  feed.innerHTML = all.map(m => {
    const isRecl = m.objet === "Réclamation";
    const isAud  = m._type === "audience";
    const dot    = isRecl ? "red" : isAud ? "gold" : "blue";
    const label  = isRecl ? "Réclamation" : isAud ? "Demande d'audience" : "Contact";
    return `<div class="feed-item">
      <div class="feed-dot ${dot}"></div>
      <div>
        <div class="feed-title">${esc(m.prenom||"")} ${esc(m.nom||"")} — ${esc(label)}</div>
        <div class="feed-sub">${esc(m._date||"")}</div>
      </div>
    </div>`;
  }).join("");
}

// ══════════════════════════════════════════════════════════════════════════
//  AUDIENCES
// ══════════════════════════════════════════════════════════════════════════
let audFilter = "all";

function filterAud(f, el) {
  audFilter = f;
  document.querySelectorAll("#panel-audiences .tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
  renderAudiences();
}

function renderAudiences() {
  const all  = getAll("bininga_audiences").filter(m => m.objet !== "Réclamation");
  const list = audFilter === "all" ? all : all.filter(m => (m._status||"en_attente") === audFilter);
  renderMsgList("list-audiences", list, "bininga_audiences", "status3");
}

// ══════════════════════════════════════════════════════════════════════════
//  RÉCLAMATIONS
// ══════════════════════════════════════════════════════════════════════════
let reclFilter = "all";

function filterRecl(f, el) {
  reclFilter = f;
  document.querySelectorAll("#panel-reclamations .tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
  renderReclamations();
}

function renderReclamations() {
  const all  = getAll("bininga_audiences").filter(m => m.objet === "Réclamation");
  const list = reclFilter === "all" ? all : all.filter(m => (m._status||"en_attente") === reclFilter);
  renderMsgList("list-reclamations", list, "bininga_audiences", "status3");
}

// ══════════════════════════════════════════════════════════════════════════
//  CONTACTS
// ══════════════════════════════════════════════════════════════════════════
let ctFilter = "all";

function filterCt(f, el) {
  ctFilter = f;
  document.querySelectorAll("#panel-contacts .tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
  renderContacts();
}

function renderContacts() {
  const all  = getAll("bininga_contacts");
  const list = ctFilter === "all" ? all : all.filter(m => (m._status||"non_lu") === ctFilter);
  renderMsgList("list-contacts", list, "bininga_contacts", "status2");
}

// ══════════════════════════════════════════════════════════════════════════
//  RENDU GÉNÉRIQUE DES MESSAGES
// ══════════════════════════════════════════════════════════════════════════
function renderMsgList(containerId, list, storageKey, mode) {
  const el = document.getElementById(containerId);
  if (!list.length) {
    el.innerHTML = '<div class="msg-empty">Aucun message dans cette catégorie.</div>';
    return;
  }

  const allData = getAll(storageKey);

  el.innerHTML = list.map(m => {
    // Identifiant stable : _id si présent, sinon fallback _date+prenom+nom
    const msgKey  = m._id || null;
    const realIdx = msgKey
      ? allData.findIndex(x => x._id === msgKey)
      : allData.findIndex(x => x._date === m._date && x.prenom === m.prenom && x.nom === m.nom);
    const status  = m._status || (mode === "status2" ? "non_lu" : "en_attente");
    const badge   = buildBadge(status, m.objet);
    const geoSkip = new Set(["_date","_status","_reply","_reply_date","_pinged","_pinged_date","_notes","_id","geo_lat","geo_lng","geo_label","geo_maps_url","photo_url","description","raison"]);
    const fields  = Object.entries(m)
      .filter(([k]) => !geoSkip.has(k))
      .map(([k,v]) => `<div class="msg-field"><strong>${esc(k)} :</strong>${esc(v)}</div>`)
      .join("");

    // Raison demande d'audience / question
    const raisonHtml = m.raison ? `<div class="sinistre-desc"><span>Requête</span>${esc(m.raison)}</div>` : "";

    // Description sinistre
    const descHtml = m.description ? `<div class="sinistre-desc"><span>Description</span>${esc(m.description)}</div>` : "";

    // Bloc géolocalisation
    let geoHtml = "";
    if (m.geo_lat && m.geo_lng) {
      const lat = parseFloat(m.geo_lat), lng = parseFloat(m.geo_lng);
      const δ = 0.008;
      const mapsUrl = m.geo_maps_url || `https://www.google.com/maps?q=${lat},${lng}&z=16`;
      geoHtml = `<div class="sinistre-geo">
        <div class="sinistre-geo-header">
          <span class="sinistre-geo-label">Zone du sinistre</span>
          <a href="${esc(mapsUrl)}" target="_blank" class="btn-maps">Ouvrir Google Maps</a>
        </div>
        ${m.geo_label ? `<div class="sinistre-addr">${esc(m.geo_label)}</div>` : ""}
        <iframe class="sinistre-map"
          src="https://www.openstreetmap.org/export/embed.html?bbox=${lng-δ},${lat-δ},${lng+δ},${lat+δ}&layer=mapnik&marker=${lat},${lng}"
          allowfullscreen loading="lazy"></iframe>
        <div class="sinistre-coords">${Number(lat).toFixed(6)}, ${Number(lng).toFixed(6)}</div>
      </div>`;
    }

    // Photo sinistre
    const photoHtml = m.photo_url ? `<div class="sinistre-photo-wrap">
      <div class="sinistre-photo-label">Photo du sinistre</div>
      <img src="${esc(m.photo_url)}" class="sinistre-photo" onclick="this.classList.toggle('full')" title="Cliquer pour agrandir">
    </div>` : "";

    // Bouton Répondre (uniquement si email disponible)
    const replyBtn = m.email
      ? `<a class="sbtn sbtn-progress" href="mailto:${m.email}?subject=${encodeURIComponent('Réponse — Cabinet Aimé BININGA')}&body=${encodeURIComponent('Bonjour ' + (m.prenom||'') + ' ' + (m.nom||'') + ',\n\n')}" style="text-decoration:none">Répondre</a>`
      : (m.telephone ? `<span class="sbtn" style="background:rgba(46,204,113,.08);color:#2ecc71;border:1px solid rgba(46,204,113,.2);cursor:default">Tél. ${esc(m.telephone)}</span>` : "");

    // Identifiant HTML-safe pour les boutons
    const btnId = msgKey ? encodeURIComponent(msgKey) : String(realIdx);
    // Bouton ping Député (visible sur tous les messages)
    const pingBtn  = m._pinged
      ? `<span class="sbtn" style="background:rgba(231,76,60,.1);color:#e74c3c;border:1px solid rgba(231,76,60,.2);cursor:default">Député alerté</span>`
      : `<button class="sbtn" style="background:rgba(231,76,60,.1);color:#e74c3c;border:1px solid rgba(231,76,60,.2)" onclick="pingDepute('${storageKey}','${btnId}')">Alerter le Député</button>`;
    let actions = "";
    if (mode === "status3") {
      actions = `
        <button class="sbtn sbtn-wait"     onclick="setStatus('${storageKey}','${btnId}','en_attente')">En attente</button>
        <button class="sbtn sbtn-progress" onclick="setStatus('${storageKey}','${btnId}','en_cours')">En cours</button>
        <button class="sbtn sbtn-done"     onclick="setStatus('${storageKey}','${btnId}','traite')">Traité</button>
        ${replyBtn}
        ${pingBtn}
      `;
    } else {
      actions = `<button class="sbtn sbtn-read" onclick="setStatus('${storageKey}','${btnId}','lu')">Marquer comme lu</button>${replyBtn}${pingBtn}`;
    }

    const hasSinistre = !!(m.geo_lat || m.photo_url || m.description);
    const pingBadge   = m._pinged ? `<span class="badge badge-pinged">Député alerté</span>` : "";

    return `<div class="msg-item${hasSinistre ? " msg-sinistre" : ""}">
      <div class="msg-top">
        <div>
          <div class="msg-name">${esc(m.prenom||"")} ${esc(m.nom||"")}</div>
          <div class="msg-date">${esc(m._date||m.ts||"")}${hasSinistre ? ' <span class="sinistre-chip">Géolocalisé</span>' : ""}</div>
        </div>
        <div style="display:flex;gap:6px;align-items:center">${pingBadge}${badge}</div>
      </div>
      <div class="msg-fields">${fields}</div>
      ${raisonHtml}
      ${descHtml}
      ${geoHtml}
      ${photoHtml}
      ${buildNotesSection(m, storageKey, btnId)}
      <div class="msg-footer">${actions}</div>
    </div>`;
  }).join("");
}

function buildBadge(status, objet) {
  if (objet === "Réclamation") return `<span class="badge badge-recl">Réclamation</span>`;
  const map = {
    en_attente: `<span class="badge badge-wait">En attente</span>`,
    en_cours:   `<span class="badge badge-progress">En cours</span>`,
    traite:     `<span class="badge badge-done">Traité</span>`,
    non_lu:     `<span class="badge badge-unread">Non lu</span>`,
    lu:         `<span class="badge badge-read">✓ Lu</span>`,
  };
  return map[status] || map.en_attente;
}

function setStatus(storageKey, idOrIdx, status) {
  const all = getAll(storageKey);
  let idx = -1;
  const decoded = decodeURIComponent(String(idOrIdx));
  if (decoded.includes("-")) idx = all.findIndex(x => x._id === decoded);
  if (idx === -1) { const n = parseInt(idOrIdx, 10); if (!isNaN(n) && all[n]) idx = n; }
  if (idx !== -1) {
    all[idx]._status = status;
    saveAll(storageKey, all);
    // Persister au serveur si l'entrée a un _id
    const cid = all[idx]._id;
    if (cid) {
      apiFetch("/api/contacts/update", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ id: cid, status })
      }).catch(() => {});
    }
  }
  refreshDashboard();
  if (storageKey === "bininga_audiences") { renderAudiences(); renderReclamations(); }
  else renderContacts();
  showToast("Statut mis à jour");
}

// ══════════════════════════════════════════════════════════════════════════
//  NOTES INTERNES
// ══════════════════════════════════════════════════════════════════════════
function buildNotesSection(m, storageKey, btnId) {
  const notes = m._notes || [];
  const notesHtml = notes.map(n => `
    <div class="note-item">
      <div class="note-meta"><strong>${esc(n.auteur||"Admin")}</strong> · ${esc(n.date||"")}</div>
      <div class="note-text">${esc(n.texte)}</div>
    </div>`).join("");
  return `
    <div class="notes-section">
      <div class="notes-title">Notes internes (admin ↔ ministre)</div>
      ${notesHtml || '<div style="font-size:11px;color:rgba(255,255,255,.2);margin-bottom:6px">Aucune note pour l\'instant</div>'}
      <div class="note-form">
        <textarea id="note-ta-${btnId}" placeholder="Ajouter une note interne…" rows="2"></textarea>
        <button onclick="addNote('${storageKey}','${btnId}')">Ajouter</button>
      </div>
    </div>`;
}

function addNote(storageKey, idOrIdx) {
  const ta = document.getElementById("note-ta-" + idOrIdx);
  const texte = ta ? ta.value.trim() : "";
  if (!texte) { showToast("Note vide.", true); return; }

  const all = getAll(storageKey);
  let idx = -1;
  const decoded = decodeURIComponent(String(idOrIdx));
  if (decoded.includes("-")) idx = all.findIndex(x => x._id === decoded);
  if (idx === -1) { const n = parseInt(idOrIdx, 10); if (!isNaN(n) && all[n]) idx = n; }
  if (idx === -1) { showToast("Dossier introuvable.", true); return; }

  if (!all[idx]._notes) all[idx]._notes = [];
  all[idx]._notes.push({ auteur: SESSION_NOM || SESSION_USERNAME || "Admin", texte, date: new Date().toLocaleString("fr-FR") });
  saveAll(storageKey, all);
  const cid = all[idx]._id;
  if (cid) {
    apiFetch("/api/contacts/update", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ id: cid, notes: all[idx]._notes })
    }).catch(() => {});
  }
  if (storageKey === "bininga_audiences") { renderAudiences(); renderReclamations(); }
  else renderContacts();
  showToast("Note ajoutée");
}

// ══════════════════════════════════════════════════════════════════════════
//  PING DÉPUTÉ
// ══════════════════════════════════════════════════════════════════════════
function pingDepute(storageKey, idOrIdx) {
  const all = getAll(storageKey);
  let idx = -1;
  const decoded = decodeURIComponent(String(idOrIdx));
  if (decoded.includes("-")) {
    idx = all.findIndex(x => x._id === decoded);
  }
  if (idx === -1) {
    const n = parseInt(idOrIdx, 10);
    if (!isNaN(n) && all[n]) idx = n;
  }
  if (idx === -1) { showToast("Dossier introuvable.", true); return; }
  all[idx]._pinged      = true;
  all[idx]._pinged_date = new Date().toLocaleString("fr-FR");
  saveAll(storageKey, all);
  const cid = all[idx]._id;
  if (cid) {
    apiFetch("/api/contacts/update", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ id: cid, pinged: true, pinged_date: all[idx]._pinged_date })
    }).catch(() => {});
  }
  refreshDashboard();
  if (storageKey === "bininga_audiences") { renderAudiences(); renderReclamations(); }
  else renderContacts();
  showToast("Le Député a été alerté sur ce dossier.");
}

// ══════════════════════════════════════════════════════════════════════════
//  SÉCURITÉ — Anti-Intrusion
// ══════════════════════════════════════════════════════════════════════════
const ATTACK_LABELS = {
  SQL_INJECTION:       "SQL Injection",
  CMD_INJECTION:       "Cmd Injection",
  XSS_ATTEMPT:         "XSS",
  PATH_TRAVERSAL_DEEP: "Path Traversal",
  SCANNER_UA:          "Scanner",
  FILE_READ_ATTEMPT:   "Lecture fichier",
  HONEYPOT:            "Honeypot",
  HONEYPOT_POST:       "Honeypot POST",
  LOGIN_FAIL:          "Échec login",
  RATE_ABUSE:          "Rate Abuse",
  AUTO_BAN:            "Ban auto",
  MANUAL_BAN:          "Ban manuel",
  OVERSIZED_REQUEST:   "Trop grand",
};

async function loadSecurity() {
  const listBlocked  = document.getElementById("sec-blocked-list");
  const listSuspects = document.getElementById("sec-suspects-list");
  const listAttacks  = document.getElementById("sec-attacks-list");
  [listBlocked, listSuspects, listAttacks].forEach(e => {
    if (e) e.innerHTML = '<div class="msg-empty">Chargement…</div>';
  });
  // Initialiser le statut 2FA pour l'utilisateur courant
  try {
    const tfaRes  = await apiFetch("/api/2fa/status", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const tfaData = await tfaRes.json();
    if (tfaData.ok) {
      window._sessionHas2fa = tfaData.has_2fa;
      tfaRefreshStatus(tfaData.has_2fa);
    }
  } catch { tfaRefreshStatus(window._sessionHas2fa || false); }

  try {
    const res  = await apiFetch("/api/security", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    if (!data.ok) { listBlocked.innerHTML = '<div class="msg-empty">Erreur.</div>'; return; }

    // Compteurs
    const honeypotCount = data.attacks.filter(a => a.type.startsWith("HONEYPOT")).length;
    document.getElementById("sec-n-blocked").textContent  = data.blocked.length;
    document.getElementById("sec-n-suspects").textContent = data.suspects.filter(s => !data.blocked.includes(s.ip)).length;
    document.getElementById("sec-n-attacks").textContent  = data.attacks.length;
    document.getElementById("sec-n-honeypot").textContent = honeypotCount;

    // Badge sidebar
    const badge = document.getElementById("badge-sec");
    if (badge && data.blocked.length > 0) {
      badge.style.display = "inline";
      badge.textContent   = data.blocked.length;
    }

    // IPs bloquées
    if (!data.blocked.length) {
      listBlocked.innerHTML = '<div class="msg-empty">Aucune IP bloquée</div>';
    } else {
      listBlocked.innerHTML = data.blocked.map(ip => `
        <div class="ip-row">
          <span class="ip-addr">${esc(ip)}</span>
          <span class="ip-score danger">BANNI</span>
          <button class="sbtn sbtn-done" style="font-size:10px;padding:3px 8px"
            onclick="unblockIp('${esc(ip)}')">Débloquer</button>
        </div>
      `).join("");
    }

    // IPs suspectes (non bannis)
    const suspects = data.suspects.filter(s => !data.blocked.includes(s.ip));
    if (!suspects.length) {
      listSuspects.innerHTML = '<div class="msg-empty">Aucune IP suspecte</div>';
    } else {
      listSuspects.innerHTML = suspects.slice(0,20).map(s => {
        const pct   = Math.min(100, Math.round(s.score / 25 * 100));
        const cls   = s.score >= 20 ? "danger" : s.score >= 10 ? "warn" : "info";
        const color = s.score >= 20 ? "#e74c3c" : s.score >= 10 ? "#f39c12" : "#3498db";
        return `<div class="ip-row" style="flex-direction:column;align-items:stretch;gap:4px">
          <div style="display:flex;align-items:center;gap:8px">
            <span class="ip-addr">${esc(s.ip)}</span>
            <span class="ip-score ${cls}">Score ${s.score}</span>
            <button class="btn-danger" style="padding:3px 8px;font-size:10px"
              onclick="manualBlockIp('${esc(s.ip)}')">Bannir</button>
          </div>
          <div class="threat-meter"><div class="threat-fill" style="width:${pct}%;background:${color}"></div></div>
          <div style="font-size:10px;color:rgba(255,255,255,.3)">${esc((s.events||[]).slice(-1)[0]?.type||"")} — ${esc((s.events||[]).slice(-1)[0]?.detail?.slice(0,60)||"")}</div>
        </div>`;
      }).join("");
    }

    // Log d'attaques
    if (!data.attacks.length) {
      listAttacks.innerHTML = '<div class="msg-empty">Aucune attaque enregistrée</div>';
    } else {
      listAttacks.innerHTML = data.attacks.map(a => `
        <div class="atk-row">
          <span class="atk-type atk-${esc(a.type)}">${esc(ATTACK_LABELS[a.type] || a.type)}</span>
          <span class="ip-addr" style="max-width:110px">${esc(a.ip)}</span>
          <span class="atk-detail" title="${esc(a.detail)}">${esc(a.detail)}</span>
          <span style="font-size:10px;color:rgba(255,255,255,.25);white-space:nowrap">${esc(a.ts)}</span>
        </div>
      `).join("");
    }
  } catch(e) {
    listBlocked.innerHTML = `<div class="msg-empty">Serveur non disponible. ${esc(e.message)}</div>`;
  }
}

async function unblockIp(ip) {
  if (!confirm(`Débloquer l'IP ${ip} ?`)) return;
  try {
    const res  = await apiFetch("/api/security/unblock", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ ip })
    });
    const data = await res.json();
    showToast(data.ok ? `IP ${ip} débloquée` : data.message, !data.ok);
    if (data.ok) loadSecurity();
  } catch { showToast("Erreur serveur", true); }
}

async function manualBlockIp(ip) {
  if (!confirm(`Bannir manuellement l'IP ${ip} ?`)) return;
  try {
    const res  = await apiFetch("/api/security/block", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ ip, reason: "Blocage manuel depuis admin" })
    });
    const data = await res.json();
    showToast(data.ok ? `IP ${ip} bannie` : data.message, !data.ok);
    if (data.ok) loadSecurity();
  } catch { showToast("Erreur serveur", true); }
}

function manualBlock() {
  const ip = document.getElementById("sec-ip-input").value.trim();
  if (!ip) { showToast("Entrez une adresse IP", true); return; }
  manualBlockIp(ip);
  document.getElementById("sec-ip-input").value = "";
}

// ══════════════════════════════════════════════════════════════════════════
//  BOUCLIER IA — Forces Spéciales Numériques
// ══════════════════════════════════════════════════════════════════════════

const _THREAT_LABELS = { 0: "AUCUNE", 1: "FAIBLE", 2: "MOYENNE", 3: "HAUTE", 4: "CRITIQUE" };
const _THREAT_COLORS = { 0: "#2ecc71", 1: "#3498db", 2: "#f39c12", 3: "#e67e22", 4: "#e74c3c" };

async function loadBouclier() {
  try {
    const res  = await apiFetch("/api/security/bouclier", { headers: authHeaders() });
    const data = await res.json();
    if (!data.ok) {
      document.getElementById("bouclier-threats-list").innerHTML =
        `<div class="msg-empty" style="color:#e74c3c">${esc(data.message || "Bouclier IA non disponible")}</div>`;
      return;
    }
    _renderBouclier(data);
  } catch(e) {
    document.getElementById("bouclier-threats-list").innerHTML =
      `<div class="msg-empty">Serveur non disponible</div>`;
  }
}

function _renderBouclier(d) {
  // Stats
  document.getElementById("bouclier-n-tracked").textContent   = d.tracked_ips    ?? "—";
  document.getElementById("bouclier-n-banned").textContent    = d.temp_banned     ?? "—";
  document.getElementById("bouclier-n-lockdowns").textContent = d.lockdown?.count ?? "—";
  document.getElementById("bouclier-n-ghosts").textContent    = d.ghost_agents    ?? "—";

  // Statut lockdown
  const bar    = document.getElementById("bouclier-status-bar");
  const icon   = document.getElementById("bouclier-status-icon");
  const txt    = document.getElementById("bouclier-status-txt");
  const sub    = document.getElementById("bouclier-status-sub");
  const timer  = document.getElementById("bouclier-lockdown-timer");
  const badge  = document.getElementById("bouclier-badge");
  const ld     = d.lockdown || {};

  if (ld.active) {
    bar.style.background   = "rgba(231,76,60,.08)";
    bar.style.borderColor  = "rgba(231,76,60,.3)";
    icon.textContent       = "!!";
    txt.textContent        = "MODE LOCKDOWN — Site en protection totale";
    txt.style.color        = "#e74c3c";
    sub.textContent        = ld.reason || "";
    timer.style.display    = "";
    timer.textContent      = `Jusqu'à ${ld.until || "—"}`;
    badge.style.display    = "";
  } else {
    bar.style.background   = "rgba(46,204,113,.06)";
    bar.style.borderColor  = "rgba(46,204,113,.15)";
    icon.textContent       = "🟢";
    txt.textContent        = "Bouclier actif — protection en cours";
    txt.style.color        = "#2ecc71";
    sub.textContent        = "7 couches de défense opérationnelles";
    timer.style.display    = "none";
    badge.style.display    = "none";
  }

  // Top menaces
  const list    = document.getElementById("bouclier-threats-list");
  const threats = d.top_threats || [];
  if (!threats.length) {
    list.innerHTML = '<div class="msg-empty">Aucune menace active</div>';
    return;
  }
  list.innerHTML = threats.map(t => {
    const lvl   = t.level ?? 0;
    const color = _THREAT_COLORS[lvl] || "#888";
    const label = _THREAT_LABELS[lvl] || "?";
    const pct   = Math.min(100, Math.round(t.score / 60 * 100));
    return `<div style="display:flex;align-items:center;gap:8px;padding:7px 10px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:7px">
      <span style="font-family:monospace;font-size:12px;color:#fff;flex:0 0 110px;overflow:hidden;text-overflow:ellipsis">${esc(t.ip)}</span>
      <div style="flex:1;height:5px;background:rgba(255,255,255,.07);border-radius:3px;overflow:hidden">
        <div style="height:100%;width:${pct}%;background:${color};border-radius:3px;transition:.3s"></div>
      </div>
      <span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;background:${color}22;color:${color};border:1px solid ${color}44;white-space:nowrap">${label} (${t.score})</span>
      <button onclick="manualBlockIp('${esc(t.ip)}')" style="padding:3px 8px;background:rgba(231,76,60,.1);color:#e74c3c;border:1px solid rgba(231,76,60,.25);border-radius:5px;font-size:10px;cursor:pointer;flex-shrink:0">Bannir</button>
    </div>`;
  }).join("");
}

async function activateLockdown() {
  const reason   = (document.getElementById("lockdown-reason")?.value.trim()  || "Menace détectée");
  const duration = parseInt(document.getElementById("lockdown-duration")?.value || "15", 10) * 60;
  if (!confirm(`Activer le LOCKDOWN ?\n\nRaison : ${reason}\nDurée : ${Math.round(duration/60)} min\n\nLe site sera inaccessible au public.`)) return;
  try {
    const res  = await apiFetch("/api/security/bouclier/lockdown", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ action: "activate", reason, duration })
    });
    const data = await res.json();
    showToast(data.ok ? "Lockdown activé" : (data.message || "Erreur"), !data.ok);
    if (data.ok) loadBouclier();
  } catch { showToast("Erreur serveur", true); }
}

async function deactivateLockdown() {
  if (!confirm("Lever le lockdown ? Le site redeviendra accessible.")) return;
  try {
    const res  = await apiFetch("/api/security/bouclier/lockdown", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ action: "deactivate" })
    });
    const data = await res.json();
    showToast(data.ok ? "Lockdown levé" : (data.message || "Erreur"), !data.ok);
    if (data.ok) loadBouclier();
  } catch { showToast("Erreur serveur", true); }
}

// ══════════════════════════════════════════════════════════════════════════
//  JOURNAUX D'AUDIT
// ══════════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════
//  VEILLE IA
// ══════════════════════════════════════════════════════════════════════════

let _newsItems = [];
let _newsPoller = null;
let _newsFilter = "bininga";
let _newsSort = "date_desc";

async function loadNews() {
  const list = document.getElementById("veille-list");
  if (!list) return;
  try {
    const res  = await apiFetch("/api/news", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    if (!data.ok) { list.innerHTML = '<div style="text-align:center;color:rgba(255,255,255,.3);padding:40px 0">Erreur de chargement.</div>'; return; }
    _newsItems = data.items || [];

    // Statut agent
    const dot  = document.getElementById("veille-dot");
    const stxt = document.getElementById("veille-status-txt");
    const hint = document.getElementById("veille-start-hint");
    const lr   = document.getElementById("veille-last-run");
    if (data.monitor_running) {
      dot.style.background = "#2ecc71";
      stxt.textContent = "Agent actif";
      hint.style.display = "none";
    } else {
      dot.style.background = "#e74c3c";
      stxt.textContent = "Agent inactif";
      hint.style.display = "block";
    }
    if (data.last_run) {
      try {
        lr.textContent = "Dernière veille : " + new Date(data.last_run).toLocaleString("fr-FR");
      } catch(e) { lr.textContent = ""; }
    }

    // Badge sidebar
    const unread = _newsItems.filter(a => !a.read).length;
    setBadge("badge-veille", unread);

    renderNewsItems();
  } catch(e) {
    if (list) list.innerHTML = '<div style="text-align:center;color:rgba(255,255,255,.3);padding:40px 0">Impossible de charger les actualités.</div>';
  }
}

function setNewsFilter(f) {
  _newsFilter = f;
  // Onglet Bininga
  const tabB = document.getElementById("tab-bininga");
  const tabA = document.getElementById("tab-all");
  if (tabB) {
    const active = f === "bininga";
    tabB.style.color = active ? "#fff" : "rgba(255,255,255,.4)";
    tabB.style.borderBottom = active ? "2px solid var(--r)" : "2px solid transparent";
  }
  if (tabA) {
    const active = f === "all";
    tabA.style.color = active ? "#fff" : "rgba(255,255,255,.4)";
    tabA.style.borderBottom = active ? "2px solid var(--r)" : "2px solid transparent";
  }
  renderNewsItems();
}

function setNewsSort(s) {
  _newsSort = s;
  const SORTS = { pertinence: "sort-pertinence", date_desc: "sort-date-desc", date_asc: "sort-date-asc" };
  Object.entries(SORTS).forEach(([key, id]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    const active = key === s;
    btn.style.background   = active ? "rgba(52,152,219,.15)" : "rgba(255,255,255,.04)";
    btn.style.color        = active ? "#3498db"              : "rgba(255,255,255,.4)";
    btn.style.borderColor  = active ? "rgba(52,152,219,.3)"  : "rgba(255,255,255,.08)";
  });
  renderNewsItems();
}

async function runVeille(preset) {
  const input = document.getElementById("veille-custom-query");
  const query = preset !== undefined ? preset : (input ? input.value.trim() : "");
  const btn   = document.getElementById("btn-run-veille");
  const fb    = document.getElementById("veille-run-feedback");
  if (btn) { btn.disabled = true; btn.textContent = "Recherche en cours…"; }
  try {
    const res  = await apiFetch("/api/news/run", {
      method: "POST",
      headers: { "X-Admin-Token": SESSION_TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    if (fb) {
      fb.style.display = "block";
      fb.style.color   = data.ok ? "#2ecc71" : "#ff6b6b";
      fb.textContent   = data.ok ? data.message + " — résultats dans environ 30 secondes" : data.message;
      setTimeout(() => { if (fb) fb.style.display = "none"; }, 8000);
    }
    if (data.ok) setTimeout(loadNews, 10000);
  } catch(e) {
    if (fb) { fb.style.display = "block"; fb.style.color = "#ff6b6b"; fb.textContent = "Erreur réseau"; }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Lancer maintenant"; }
  }
}

async function restartMonitor() {
  try {
    const res  = await apiFetch("/api/monitor-restart", {
      method: "POST",
      headers: { "X-Admin-Token": SESSION_TOKEN },
    });
    const data = await res.json();
    if (data.ok) {
      showToast("YARO IA redémarré avec succès");
      setTimeout(loadNews, 2000);
    } else {
      showToast("Erreur : " + data.message, true);
    }
  } catch(e) {
    showToast("Erreur réseau lors du redémarrage", true);
  }
}

async function toggleMonitorLog() {
  const box = document.getElementById("monitor-log-box");
  if (!box) return;
  if (box.style.display !== "none") { box.style.display = "none"; return; }
  box.style.display = "block";
  box.textContent = "Chargement…";
  try {
    const res  = await apiFetch("/api/monitor-log", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    box.textContent = data.ok ? (data.lines.join("\n") || "(log vide)") : "Erreur : " + data.message;
    box.scrollTop = box.scrollHeight;
  } catch(e) {
    box.textContent = "Erreur réseau";
  }
}

const CAT_LABELS = {
  bininga:     { label: "Bininga",      color: "rgba(200,16,46,.8)",    bg: "rgba(200,16,46,.12)" },
  loi_justice: { label: "Lois & Justice", color: "rgba(46,204,113,.9)", bg: "rgba(46,204,113,.1)" },
  recherche:   { label: "Recherche", color: "rgba(52,152,219,.9)",   bg: "rgba(52,152,219,.1)" },
};

function _newsDate(a) {
  const d = a.published || a.found_at || "";
  if (!d) return 0;
  try { return new Date(d).getTime(); } catch(e) { return 0; }
}

function _newsScore(a) {
  let score = 0;
  if (!a.read) score += 100;
  const t = (a.title || "").toLowerCase();
  if (t.includes("bininga")) score += 50;
  if (t.includes("ministre") || t.includes("justice") || t.includes("congo")) score += 20;
  if (a.ai_summary) score += 10;
  if (a.summary) score += 5;
  return score;
}

function renderNewsItems() {
  const list = document.getElementById("veille-list");
  if (!list) return;
  const filtered = _newsFilter === "all"
    ? _newsItems
    : _newsItems.filter(a => (a.category || "bininga") === _newsFilter);

  // Mise à jour compteurs onglets
  const bCount = _newsItems.filter(a => (a.category || "bininga") === "bininga").length;
  const aCount = _newsItems.length;
  const bUnread = _newsItems.filter(a => (a.category || "bininga") === "bininga" && !a.read).length;
  const aUnread = _newsItems.filter(a => !a.read).length;
  const tbc = document.getElementById("tab-bininga-count");
  const tac = document.getElementById("tab-all-count");
  if (tbc) tbc.textContent = bUnread > 0 ? `${bUnread} non lu${bUnread>1?"s":""}` : bCount;
  if (tac) tac.textContent = aUnread > 0 ? `${aUnread} non lu${aUnread>1?"s":""}` : aCount;

  // Tri selon le mode choisi
  const sorted = [...filtered].sort((a, b) => {
    if (_newsSort === "date_desc") return _newsDate(b) - _newsDate(a);
    if (_newsSort === "date_asc")  return _newsDate(a) - _newsDate(b);
    // pertinence (score) puis date décroissante
    const sd = _newsScore(b) - _newsScore(a);
    if (sd !== 0) return sd;
    return _newsDate(b) - _newsDate(a);
  });
  if (!sorted.length) {
    list.innerHTML = '<div style="text-align:center;color:rgba(255,255,255,.3);padding:40px 0;font-size:13px">Aucune actualité dans cette catégorie.<br><small>L\'agent surveille Google News toutes les 15 minutes.</small></div>';
    return;
  }
  list.innerHTML = sorted.map(a => {
    const isRead   = a.read;
    const cat      = CAT_LABELS[a.category] || CAT_LABELS.bininga;
    const catBadge = `<span style="padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;background:${cat.bg};color:${cat.color};flex-shrink:0">${cat.label}</span>`;
    const dateStr  = a.published ? (() => { try { return new Date(a.published).toLocaleDateString("fr-FR",{day:"2-digit",month:"short",year:"numeric"}); } catch(e) { return a.published; } })() : "";
    const foundStr = a.found_at ? (() => { try { return new Date(a.found_at).toLocaleString("fr-FR"); } catch(e) { return ""; } })() : "";
    const src = (a.source || "").toLowerCase();
    const socialBadge = src.includes("twitter") || src.includes("nitter")
      ? `<span style="padding:1px 6px;border-radius:8px;font-size:10px;background:rgba(29,161,242,.15);color:#1da1f2;font-weight:700">𝕏 Twitter</span>`
      : src.includes("youtube")
      ? `<span style="padding:1px 6px;border-radius:8px;font-size:10px;background:rgba(255,0,0,.12);color:#ff4444;font-weight:700">▶ YouTube</span>`
      : src.includes("facebook") || src.includes("instagram")
      ? `<span style="padding:1px 6px;border-radius:8px;font-size:10px;background:rgba(66,103,178,.15);color:#4267b2;font-weight:700">Facebook</span>`
      : "";
    const aiBlock  = a.ai_summary
      ? `<div style="margin-top:8px;padding:8px 12px;background:rgba(52,152,219,.06);border-left:2px solid rgba(52,152,219,.3);border-radius:0 6px 6px 0;font-size:11.5px;color:rgba(255,255,255,.65);font-style:italic">${esc(a.ai_summary)}</div>`
      : "";
    const summaryBlock = a.summary
      ? `<div style="font-size:12px;color:rgba(255,255,255,.5);margin-top:5px;line-height:1.5">${esc(a.summary.slice(0,300))}${a.summary.length>300?"…":""}</div>`
      : "";
    return `<div style="background:rgba(255,255,255,${isRead?".02":".05"});border:1px solid rgba(255,255,255,${isRead?".04":".09"});border-radius:10px;padding:14px 16px;opacity:${isRead?".6":"1"};transition:.2s">
      <div style="display:flex;align-items:flex-start;gap:10px">
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">
            ${!isRead?'<span style="width:7px;height:7px;border-radius:50%;background:#3498db;flex-shrink:0;display:inline-block"></span>':""}
            ${catBadge}
            <a href="${esc(a.url)}" target="_blank" rel="noopener" style="font-size:13px;font-weight:600;color:var(--w);text-decoration:none;line-height:1.4">${esc(a.title)}</a>
          </div>
          <div style="font-size:11px;color:rgba(255,255,255,.3);margin-bottom:4px;display:flex;align-items:center;gap:6px;flex-wrap:wrap">
            ${socialBadge}
            <span>${esc(a.source)}</span>
            ${dateStr?`<span style="margin:0 4px">·</span><span>${dateStr}</span>`:""}
            ${foundStr?`<span style="margin:0 4px">·</span><span style="color:rgba(255,255,255,.2)">Détecté le ${foundStr}</span>`:""}
          </div>
          ${summaryBlock}
          ${aiBlock}
        </div>
        <div style="display:flex;flex-direction:column;gap:5px;flex-shrink:0">
          <a href="${esc(a.url)}" target="_blank" rel="noopener" style="padding:4px 10px;border-radius:5px;font-size:11px;font-weight:600;background:rgba(52,152,219,.1);color:#3498db;border:1px solid rgba(52,152,219,.2);text-decoration:none;white-space:nowrap">Lire</a>
          ${!isRead?`<button onclick="markNewsRead('${esc(a.id)}')" style="padding:4px 10px;border-radius:5px;font-size:11px;font-weight:600;background:rgba(46,204,113,.08);color:#2ecc71;border:1px solid rgba(46,204,113,.2);cursor:pointer;white-space:nowrap">✓ Lu</button>`:""}
          <button onclick="deleteNewsItem('${esc(a.id)}')" style="padding:4px 10px;border-radius:5px;font-size:11px;font-weight:600;background:rgba(200,16,46,.08);color:#ff6b6b;border:1px solid rgba(200,16,46,.2);cursor:pointer;white-space:nowrap">Supprimer</button>
        </div>
      </div>
    </div>`;
  }).join("");
}

async function markNewsRead(id) {
  try {
    await apiFetch("/api/news/mark-read", {
      method: "POST",
      headers: { "X-Admin-Token": SESSION_TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    const item = _newsItems.find(a => a.id === id);
    if (item) item.read = true;
    const unread = _newsItems.filter(a => !a.read).length;
    setBadge("badge-veille", unread);
    renderNewsItems();
  } catch(e) {}
}

async function markAllNewsRead() {
  try {
    await apiFetch("/api/news/mark-read", {
      method: "POST",
      headers: { "X-Admin-Token": SESSION_TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify({ all: true }),
    });
    _newsItems.forEach(a => a.read = true);
    setBadge("badge-veille", 0);
    renderNewsItems();
    showToast("Toutes les actualités marquées comme lues");
  } catch(e) {}
}

async function deleteNewsItem(id) {
  try {
    await apiFetch("/api/news/delete", {
      method: "POST",
      headers: { "X-Admin-Token": SESSION_TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    _newsItems = _newsItems.filter(a => a.id !== id);
    const unread = _newsItems.filter(a => !a.read).length;
    setBadge("badge-veille", unread);
    renderNewsItems();
  } catch(e) {}
}

function startNewsPoller() {
  if (_newsPoller) return;
  _newsPoller = setInterval(() => {
    // Polling silencieux (badge seulement, pas de re-render si pas sur le panel)
    apiFetch("/api/news", { headers: { "X-Admin-Token": SESSION_TOKEN } })
      .then(r => r.json())
      .then(data => {
        if (!data.ok) return;
        const unread = (data.items || []).filter(a => !a.read).length;
        setBadge("badge-veille", unread);
        // Si panel ouvert, actualiser
        if (document.getElementById("panel-veille")?.classList.contains("active")) {
          _newsItems = data.items || [];
          renderNewsItems();
        }
      })
      .catch(() => {});
  }, 2 * 60 * 1000);   // toutes les 2 minutes
}

async function loadAuditLogs() {
  const el = document.getElementById("log-list");
  el.innerHTML = '<div class="msg-empty">Chargement…</div>';
  try {
    const res = await apiFetch("/api/logs", {
      headers: { "X-Admin-Token": SESSION_TOKEN }
    });
    const data = await res.json();
    if (!data.ok) { el.innerHTML = '<div class="msg-empty">Erreur de chargement.</div>'; return; }
    if (!data.logs.length) { el.innerHTML = '<div class="msg-empty">Aucune entrée pour le moment.</div>'; return; }

    const icons  = { LOGIN_OK:"OK", LOGIN_FAIL:"NO", SAVE:"SV", UPLOAD:"UP", USER_UPSERT:"US", USER_DELETE:"DL" };
    const labels = { LOGIN_OK:"Connexion réussie", LOGIN_FAIL:"Tentative échouée", SAVE:"Sauvegarde", UPLOAD:"Upload image", USER_UPSERT:"Utilisateur créé / modifié", USER_DELETE:"Utilisateur supprimé" };
    const cls    = { LOGIN_OK:"ok", LOGIN_FAIL:"fail", SAVE:"save", UPLOAD:"upload", USER_UPSERT:"ok", USER_DELETE:"fail" };

    el.innerHTML = data.logs.map(log => `
      <div class="log-item">
        <div class="log-icon">${icons[log.action] || "LOG"}</div>
        <div class="log-body">
          <div class="log-action ${cls[log.action] || ''}">${labels[log.action] || esc(log.action)}</div>
          ${log.detail ? `<div class="log-detail">${esc(log.detail)}</div>` : ''}
          <div class="log-meta">${esc(log.ts)} &nbsp;·&nbsp; IP : ${esc(log.ip)}</div>
        </div>
      </div>
    `).join("");
  } catch {
    el.innerHTML = '<div class="msg-empty">Serveur non disponible.</div>';
  }
}

async function loadBackups() {
  const el = document.getElementById("backup-list");
  if (el) el.innerHTML = '<div class="msg-empty">Chargement…</div>';
  try {
    const res = await apiFetch("/api/backups", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    if (!data.ok) {
      if (el) el.innerHTML = `<div class="msg-empty">${esc(data.message || "Impossible de charger les sauvegardes")}</div>`;
      return;
    }
    const latest = data.latest || {};
    setText("backup-last-date", latest.created_at ? latest.created_at.replace("T", " ").slice(0, 16) : "—");
    setText("backup-photo-count", latest.photo_count ?? "—");
    setText("backup-copy-count", data.count || 0);
    if (!el) return;
    if (!data.backups.length) {
      el.innerHTML = '<div class="msg-empty">Aucune sauvegarde trouvée.</div>';
      return;
    }
    el.innerHTML = data.backups.map(b => `
      <div class="log-row">
        <div class="log-icon">BK</div>
        <div class="log-body">
          <div class="log-action save">${esc(b.name)}</div>
          <div class="log-detail">
            ${esc((b.created_at || "").replace("T", " ").slice(0, 19))}
            · ${esc(b.backend || data.database || "db")}
            · ${Number(b.photo_count || 0)} photo(s)
            · ${Number(b.store_count || 0)} bloc(s) données
          </div>
          <div class="log-meta">${esc(b.path || "")}</div>
        </div>
      </div>
    `).join("");
  } catch (e) {
    if (el) el.innerHTML = `<div class="msg-empty">Erreur serveur : ${esc(e.message)}</div>`;
  }
}

async function runBackupNow() {
  const btn = document.getElementById("btn-run-backup");
  if (btn) { btn.disabled = true; btn.textContent = "Sauvegarde en cours…"; }
  try {
    const res = await apiFetch("/api/backups/run", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.ok) {
      showToast(`Sauvegarde créée : ${data.backup.name}`);
      await loadBackups();
    } else {
      showToast(data.message || "Erreur sauvegarde", true);
    }
  } catch (e) {
    showToast("Erreur : " + e.message, true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Créer une sauvegarde maintenant"; }
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════════════════════════════════════════
const PANEL_TITLES = {
  dashboard:"Tableau de bord", audiences:"Demandes d'audience",
  reclamations:"Réclamations", contacts:"Messages de contact",
  crm:"CRM — Base de contacts",
  hero:"Section Hero", about:"À propos", stats:"Statistiques", galerie:"Galerie photos",
  actus:"Actualités", parcours:"Parcours — Timeline", programme:"Programme 2027–2032", seo:"SEO",
  monitoring:"Monitoring — Surveillance temps réel", backups:"Sauvegardes",
  logs:"Journaux d'audit", users:"Gestion des utilisateurs", security:"Sécurité — Anti-Intrusion",
  veille:"YARO IA — Actualités Bininga",
  editorial:"Éditorial IA — Contenus",
  "yaro-legal":"Veille juridique — YARO IA"
};

let _currentPanel = "dashboard";
function showPanel(name, el) {
  _currentPanel = name;
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".sb-item").forEach(i => i.classList.remove("active"));
  const panel = document.getElementById("panel-"+name);
  if (!panel) {
    showToast("Module indisponible", true);
    showPanel("dashboard");
    return;
  }
  panel.classList.add("active");
  if (el) el.classList.add("active");
  document.getElementById("topbar-title").textContent = PANEL_TITLES[name] || name;
  if (name === "dashboard")    syncMessages().then(() => refreshDashboard());
  if (name === "audiences")    syncMessages().then(() => renderAudiences());
  if (name === "reclamations") syncMessages().then(() => renderReclamations());
  if (name === "contacts")     syncMessages().then(() => renderContacts());
  if (name === "stats")        renderStats();
  if (name === "galerie")      renderGalerie();
  if (name === "actus")        renderActus();
  if (name === "parcours")     renderParcours();
  if (name === "programme")    renderProgramme();
  if (name === "monitoring")   loadMonitoring();
  if (name === "backups")      loadBackups();
  if (name === "logs")         loadAuditLogs();
  if (name === "users")        loadUsers();
  if (name === "security")     { loadSecurity(); loadBouclier(); }
  if (name === "veille")       loadNews();
  if (name === "editorial")    loadEditorial();
  if (name === "crm")          loadCrm();
  const formPanels = ["hero","about","seo","engagement","cta","contact-info","footer"];
  if (formPanels.includes(name)) populateForm();
  // Fermer la sidebar sur mobile après sélection
  if (window.innerWidth <= 768) closeSidebar();
}

// ══════════════════════════════════════════════════════════════════════════
//  UTILITAIRES
// ══════════════════════════════════════════════════════════════════════════
function getAll(key)       { return JSON.parse(localStorage.getItem(key)||"[]"); }
function saveAll(key, arr) { localStorage.setItem(key, JSON.stringify(arr)); }
function setText(id, val)  { const el=document.getElementById(id); if(el) el.textContent=val; }
function setBadge(id, n)   { const el=document.getElementById(id); if(!el)return; el.style.display=n>0?"inline":"none"; el.textContent=n; }
function esc(s)            { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

async function resetSystem(targets) {
  const labels = { contacts: "tous les messages/audiences", crm: "les contacts CRM" };
  const desc   = targets.map(t => labels[t] || t).join(" et ");
  if (!confirm(`RÉINITIALISATION GLOBALE\n\nCette action supprimera définitivement :\n→ ${desc}\n\nConfirmez-vous ?`)) return;
  if (!confirm("Dernière confirmation — cette action est irréversible. Continuer ?")) return;
  try {
    const res  = await apiFetch("/api/reset", { method: "POST", headers: authHeaders(), body: JSON.stringify({ targets }) });
    const data = await res.json();
    if (!data.ok) { showToast("Erreur : " + (data.message || "inconnue"), true); return; }
    // Vider localStorage
    if (targets.includes("contacts")) {
      localStorage.removeItem("bininga_audiences");
      localStorage.removeItem("bininga_contacts");
    }
    syncMessages().then(() => refreshDashboard());
    showToast("Réinitialisation effectuée");
  } catch (e) {
    showToast("Erreur réseau", true);
  }
}

async function clearAll(storageKey, panel) {
  if (!confirm("Êtes-vous sûr de vouloir supprimer tous les messages ? Cette action est irréversible.")) return;
  // Suppression côté serveur
  try {
    await apiFetch("/api/contacts/clear", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ type: storageKey })
    });
  } catch (_) {}
  // Suppression locale
  localStorage.removeItem(storageKey);
  refreshDashboard();
  if (panel === "audiences") { renderAudiences(); renderReclamations(); }
  if (panel === "contacts")  renderContacts();
  showToast("Messages supprimés");
}

// ══════════════════════════════════════════════════════════════════════════
//  EXPORT CSV
// ══════════════════════════════════════════════════════════════════════════
function exportCSV(storageKey, type) {
  const data = JSON.parse(localStorage.getItem(storageKey) || "[]");
  let rows = data;
  if (type === "audiences")    rows = data.filter(m => m.objet !== "Réclamation");
  if (type === "reclamations") rows = data.filter(m => m.objet === "Réclamation");
  if (!rows.length) { showToast("Aucune donnée à exporter", true); return; }
  const keys = [...new Set(rows.flatMap(Object.keys))];
  const lines = [keys.join(";")];
  rows.forEach(item => {
    lines.push(keys.map(k => {
      const val = String(item[k] || "").replace(/"/g, '""').replace(/[\r\n]+/g, " ");
      return `"${val}"`;
    }).join(";"));
  });
  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `bininga_${type}_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("Export CSV téléchargé !");
}

// ══════════════════════════════════════════════════════════════════════════
//  PARCOURS (TIMELINE)
// ══════════════════════════════════════════════════════════════════════════
function updParcoursSection(field, val) {
  if (!siteData.parcoursSection) siteData.parcoursSection = {};
  siteData.parcoursSection[field] = val;
}
function renderParcours() {
  const sec = siteData.parcoursSection || {};
  const tagEl    = document.getElementById("parcours-sec-tag");
  const titleEl  = document.getElementById("parcours-sec-title");
  const accentEl = document.getElementById("parcours-sec-accent");
  if (tagEl)    tagEl.value    = sec.tag         || "";
  if (titleEl)  titleEl.value  = sec.title        || "";
  if (accentEl) accentEl.value = sec.titleAccent  || "";

  const items = (siteData.parcours || []);
  const list  = document.getElementById("parcours-list");
  if (!items.length) {
    list.innerHTML = '<div class="msg-empty">Aucune étape. Cliquez sur "+ Ajouter".</div>';
    return;
  }
  list.innerHTML = items.map((p, i) => `
    <div class="stats-row" style="grid-template-columns:80px 80px 1fr 1fr auto;gap:10px;align-items:start;padding:14px 0">
      <div class="form-group" style="margin:0">
        <label>Côté</label>
        <select oninput="updParcours(${i},'side',this.value)" style="width:100%;padding:9px 8px;background:var(--n3);border:1px solid rgba(255,255,255,.08);border-radius:7px;color:var(--w);font-size:13px;font-family:inherit;outline:none">
          <option value="left"  ${p.side==="left" ?"selected":""}>← Gauche</option>
          <option value="right" ${p.side==="right"?"selected":""}>→ Droite</option>
        </select>
        <label style="margin-top:8px">Emoji</label>
        <input type="text" value="${esc(p.emoji||'')}" placeholder="Icône" oninput="updParcours(${i},'emoji',this.value)" style="width:60px;text-align:center;font-size:18px">
      </div>
      <div class="form-group" style="margin:0">
        <label>Année / Période</label>
        <input type="text" value="${esc(p.year||'')}" placeholder="2016" oninput="updParcours(${i},'year',this.value)">
        <label style="margin-top:8px">Tag</label>
        <input type="text" value="${esc(p.tag||'')}" placeholder="Ministre" oninput="updParcours(${i},'tag',this.value)" style="font-size:12px">
      </div>
      <div class="form-group" style="margin:0">
        <label>Titre</label>
        <input type="text" value="${esc(p.title||'')}" placeholder="Titre de l'étape" oninput="updParcours(${i},'title',this.value)">
      </div>
      <div class="form-group" style="margin:0">
        <label>Description</label>
        <textarea oninput="updParcours(${i},'desc',this.value)" style="min-height:80px">${esc(p.desc||'')}</textarea>
      </div>
      <div style="padding-top:22px;display:flex;flex-direction:column;gap:6px">
        <button class="btn-danger" onclick="delParcoursItem(${i})" title="Supprimer">Supprimer</button>
        ${i > 0 ? `<button class="sbtn sbtn-wait" onclick="moveParcours(${i},-1)" title="Monter">↑</button>` : ""}
        ${i < items.length-1 ? `<button class="sbtn sbtn-wait" onclick="moveParcours(${i},1)" title="Descendre">↓</button>` : ""}
      </div>
    </div>
  `).join('<div style="border-bottom:1px solid rgba(255,255,255,.05)"></div>');
}

function updParcours(i, field, val) {
  if (!siteData.parcours) siteData.parcours = [];
  if (siteData.parcours[i]) siteData.parcours[i][field] = val;
}
function addParcoursItem() {
  if (!siteData.parcours) siteData.parcours = [];
  const side = siteData.parcours.length % 2 === 0 ? "left" : "right";
  siteData.parcours.push({ side, emoji: "", year: "", title: "", desc: "", tag: "" });
  renderParcours();
}
function delParcoursItem(i) {
  if (!confirm("Supprimer cette étape du parcours ?")) return;
  siteData.parcours.splice(i, 1);
  renderParcours();
  saveData(true);
  showToast("Étape supprimée");
}
function moveParcours(i, dir) {
  const arr = siteData.parcours;
  const j = i + dir;
  if (j < 0 || j >= arr.length) return;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  renderParcours();
}

// ══════════════════════════════════════════════════════════════════════════
//  PROGRAMME (6 AXES)
// ══════════════════════════════════════════════════════════════════════════
function renderProgramme() {
  const prog = siteData.programme || {};
  const titleEl = document.getElementById("prog-heroTitle");
  const textEl  = document.getElementById("prog-heroText");
  if (titleEl) titleEl.value = prog.heroTitle || "";
  if (textEl)  textEl.value  = prog.heroText  || "";
  renderAxes();
}

function renderAxes() {
  const axes = (siteData.programme && siteData.programme.axes) || [];
  const list  = document.getElementById("axes-list");
  if (!axes.length) {
    list.innerHTML = '<div class="msg-empty">Aucun axe. Cliquez sur "+ Ajouter".</div>';
    return;
  }
  list.innerHTML = axes.map((ax, i) => `
    <div style="background:var(--n3);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:18px;margin-bottom:12px">
      <div style="display:grid;grid-template-columns:50px 1fr 1fr auto;gap:10px;align-items:start;margin-bottom:12px">
        <div class="form-group" style="margin:0">
          <label>Icône</label>
          <input type="text" value="${esc(ax.icon||'')}" placeholder="Icône" oninput="updAxe(${i},'icon',this.value)" style="width:50px;text-align:center;font-size:20px">
        </div>
        <div class="form-group" style="margin:0">
          <label>Titre de l'axe</label>
          <input type="text" value="${esc(ax.title||'')}" placeholder="Justice accessible" oninput="updAxe(${i},'title',this.value)">
        </div>
        <div class="form-group" style="margin:0">
          <label>Description</label>
          <textarea oninput="updAxe(${i},'text',this.value)" style="min-height:64px">${esc(ax.text||'')}</textarea>
        </div>
        <div style="padding-top:22px;display:flex;flex-direction:column;gap:4px">
          <button class="btn-danger" onclick="delAxe(${i})" title="Supprimer">Supprimer</button>
          ${i > 0 ? `<button class="sbtn sbtn-wait" onclick="moveAxe(${i},-1)">↑</button>` : ""}
          ${i < axes.length-1 ? `<button class="sbtn sbtn-wait" onclick="moveAxe(${i},1)">↓</button>` : ""}
        </div>
      </div>
      <div>
        <label style="font-size:10px;color:rgba(255,255,255,.35);display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600">Points clés</label>
        <div style="display:flex;flex-direction:column;gap:6px" id="pts-${i}">
          ${(ax.points||[]).map((pt, j) => `
            <div style="display:flex;gap:6px;align-items:center">
              <input type="text" value="${esc(pt)}" placeholder="Point clé…" oninput="updAxePoint(${i},${j},this.value)"
                style="flex:1;padding:8px 10px;background:var(--n2);border:1px solid rgba(255,255,255,.08);border-radius:6px;color:var(--w);font-size:13px;font-family:inherit;outline:none">
              <button class="btn-danger" style="padding:5px 8px" onclick="delAxePoint(${i},${j})">✕</button>
            </div>`).join("")}
        </div>
        <button class="sbtn sbtn-wait" style="margin-top:8px;font-size:11px" onclick="addAxePoint(${i})">+ Point clé</button>
      </div>
    </div>
  `).join("");
}

function updAxe(i, field, val) {
  if (!siteData.programme) siteData.programme = { heroTitle: "", heroText: "", axes: [] };
  if (siteData.programme.axes[i]) siteData.programme.axes[i][field] = val;
}
function addAxe() {
  if (!siteData.programme) siteData.programme = { heroTitle: "", heroText: "", axes: [] };
  if (!siteData.programme.axes) siteData.programme.axes = [];
  siteData.programme.axes.push({ icon: "", title: "", text: "", points: [] });
  renderAxes();
}
function delAxe(i) {
  if (!confirm("Supprimer cet axe ?")) return;
  siteData.programme.axes.splice(i, 1);
  renderAxes();
  saveData(true);
  showToast("Axe supprimé");
}
function moveAxe(i, dir) {
  const arr = siteData.programme.axes;
  const j = i + dir;
  if (j < 0 || j >= arr.length) return;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  renderAxes();
}
function updAxePoint(i, j, val) {
  if (siteData.programme && siteData.programme.axes[i] && siteData.programme.axes[i].points)
    siteData.programme.axes[i].points[j] = val;
}
function addAxePoint(i) {
  if (siteData.programme && siteData.programme.axes[i]) {
    if (!siteData.programme.axes[i].points) siteData.programme.axes[i].points = [];
    siteData.programme.axes[i].points.push("");
    renderAxes();
  }
}
function delAxePoint(i, j) {
  if (siteData.programme && siteData.programme.axes[i] && siteData.programme.axes[i].points) {
    siteData.programme.axes[i].points.splice(j, 1);
    renderAxes();
  }
}

function collectProgramme() {
  if (!siteData.programme) siteData.programme = { heroTitle: "", heroText: "", axes: [] };
  const titleEl = document.getElementById("prog-heroTitle");
  const textEl  = document.getElementById("prog-heroText");
  if (titleEl) siteData.programme.heroTitle = titleEl.value;
  if (textEl)  siteData.programme.heroText  = textEl.value;
  // Les axes sont déjà mis à jour via oninput
}

function showToast(msg, err=false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "show" + (err ? " err" : "");
  t.setAttribute("role", "status");
  t.setAttribute("aria-live", err ? "assertive" : "polite");
  setTimeout(() => t.className = "", 3500);
}

// ── Hamburger menu mobile ──────────────────────────────────────────────────
function toggleSidebar() {
  const sb   = document.getElementById("sidebar");
  const btn  = document.getElementById("hamburger");
  const ov   = document.getElementById("sidebar-overlay");
  const pull = document.getElementById("sb-pull");
  if (!sb) return;
  const open = sb.classList.toggle("open");
  if (btn)  { btn.classList.toggle("open", open); btn.setAttribute("aria-expanded", open); }
  if (ov)   ov.classList.toggle("open", open);
  if (pull) pull.classList.toggle("visible", open);
  document.body.style.overflow = open ? "hidden" : "";
}
function closeSidebar() {
  const sb   = document.getElementById("sidebar");
  const btn  = document.getElementById("hamburger");
  const ov   = document.getElementById("sidebar-overlay");
  const pull = document.getElementById("sb-pull");
  if (sb)   sb.classList.remove("open");
  if (btn)  { btn.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
  if (ov)   ov.classList.remove("open");
  if (pull) pull.classList.remove("visible");
  document.body.style.overflow = "";
}

// ── Navigateur de dossiers d'images ─────────────────────────────────────────
let _fbCallback   = null;
let _fbCurrentDir = "images";
let _fbHistory    = [];
let _fbSelected   = null;

function openBrowser(callback) {
  _fbCallback   = callback;
  _fbHistory    = [];
  _fbSelected   = null;
  _fbCurrentDir = "images";
  const ov = document.getElementById("file-browser-overlay");
  ov.style.display = "flex";
  document.body.style.overflow = "hidden";
  fbLoad("images");
}

function closeBrowser() {
  const ov = document.getElementById("file-browser-overlay");
  ov.style.display = "none";
  document.body.style.overflow = "";
  _fbCallback  = null;
  _fbSelected  = null;
}

function fbGoBack() {
  if (_fbHistory.length > 0) {
    const prev = _fbHistory.pop();
    _fbCurrentDir = prev;
    fbLoad(prev, false);
  }
}

async function fbLoad(dir, pushHistory = true) {
  if (pushHistory && dir !== _fbCurrentDir) {
    _fbHistory.push(_fbCurrentDir);
  }
  _fbCurrentDir = dir;
  _fbSelected   = null;

  const grid    = document.getElementById("fb-grid");
  const bcEl    = document.getElementById("fb-breadcrumb");
  const pathEl  = document.getElementById("fb-path-label");
  const backBtn = document.getElementById("fb-back-btn");
  const confBtn = document.getElementById("fb-confirm-btn");

  grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:rgba(255,255,255,.25);padding:40px 0;font-size:13px">Chargement…</div>';
  if (bcEl)   bcEl.textContent   = dir + "/";
  if (pathEl) pathEl.textContent = dir + "/";
  if (backBtn) backBtn.disabled = _fbHistory.length === 0;
  if (confBtn) { confBtn.disabled = true; confBtn.style.opacity = ".4"; }
  fbSetPreview(null);

  try {
    const res  = await apiFetch("/api/files?dir=" + encodeURIComponent(dir), {
      headers: { "X-Admin-Token": SESSION_TOKEN }
    });
    const data = await res.json();
    if (!data.ok) { grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:#ff7070;padding:40px 0;font-size:13px">Erreur : ' + esc(data.message||"inconnu") + '</div>'; return; }

    const items = [];

    // Dossiers
    (data.folders || []).forEach(f => {
      items.push(`
        <div onclick="fbLoad('${esc(f.path)}')"
             style="cursor:pointer;background:#161616;border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:12px 8px;text-align:center;transition:all .2s"
             onmouseover="this.style.borderColor='rgba(200,16,46,.4)';this.style.background='#1e1e1e'"
             onmouseout="this.style.borderColor='rgba(255,255,255,.07)';this.style.background='#161616'">
          <div style="font-size:13px;font-weight:700;margin-bottom:8px;color:rgba(255,255,255,.55)">Dossier</div>
          <div style="font-size:11px;color:rgba(255,255,255,.7);word-break:break-word;line-height:1.3">${esc(f.name)}</div>
        </div>`);
    });

    // Fichiers image
    (data.files || []).forEach(f => {
      items.push(`
        <div onclick="fbSelectFile('${esc(f.path)}', this)"
             data-path="${esc(f.path)}"
             style="cursor:pointer;background:#161616;border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:6px;transition:all .2s;position:relative"
             onmouseover="if(!this.classList.contains('fb-sel'))this.style.borderColor='rgba(200,16,46,.3)'"
             onmouseout="if(!this.classList.contains('fb-sel'))this.style.borderColor='rgba(255,255,255,.07)'">
          <img src="${esc(f.path)}" alt="${esc(f.name)}"
               style="width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;display:block"
               onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
          <div style="display:none;width:100%;aspect-ratio:1;background:#1e1e1e;border-radius:6px;align-items:center;justify-content:center;font-size:11px;color:rgba(255,255,255,.45)">Image</div>
          <div style="font-size:10px;color:rgba(255,255,255,.45);margin-top:5px;word-break:break-word;line-height:1.3;padding:0 2px">${esc(f.name)}</div>
        </div>`);
    });

    if (items.length === 0) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:rgba(255,255,255,.2);padding:40px 0;font-size:13px">Dossier vide</div>';
    } else {
      grid.innerHTML = items.join("");
    }
  } catch(e) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:#ff7070;padding:40px 0;font-size:13px">Serveur non disponible</div>';
  }
}

function fbSelectFile(path, el) {
  // Désélectionner l'ancien
  document.querySelectorAll("#fb-grid .fb-sel").forEach(e => {
    e.classList.remove("fb-sel");
    e.style.borderColor = "rgba(255,255,255,.07)";
    e.style.background  = "#161616";
  });
  // Sélectionner le nouveau
  el.classList.add("fb-sel");
  el.style.borderColor = "#C8102E";
  el.style.background  = "rgba(200,16,46,.08)";
  _fbSelected = path;
  fbSetPreview(path);
  const confBtn = document.getElementById("fb-confirm-btn");
  if (confBtn) { confBtn.disabled = false; confBtn.style.opacity = "1"; }
}

function fbSetPreview(path) {
  const el = document.getElementById("fb-selected-preview");
  if (!el) return;
  if (!path) { el.innerHTML = 'Aucune image sélectionnée'; return; }
  el.innerHTML = `<img src="${esc(path)}" style="height:36px;width:36px;object-fit:cover;border-radius:5px;border:1px solid rgba(255,255,255,.1)"><span style="color:rgba(255,255,255,.6)">${esc(path)}</span>`;
}

function confirmBrowserSelection() {
  if (!_fbSelected || !_fbCallback) return;
  const cb = _fbCallback;
  const sel = _fbSelected;
  closeBrowser();
  cb(sel);
}

// Surcharge de uploadImage pour proposer aussi la navigation
function pickOrUploadImage(callback) {
  const modal = document.createElement("div");
  modal.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2500;display:flex;align-items:center;justify-content:center";
  modal.innerHTML = `
    <div style="background:#0e0e0e;border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:32px;text-align:center;width:300px;box-shadow:0 30px 80px rgba(0,0,0,.8)">
      <div style="font-size:15px;font-weight:700;margin-bottom:8px">Choisir une image</div>
      <div style="font-size:12px;color:rgba(255,255,255,.35);margin-bottom:24px">Parcourez les dossiers ou uploadez un nouveau fichier</div>
      <div style="display:flex;flex-direction:column;gap:10px">
        <button id="pick-browse" style="padding:11px 20px;background:rgba(200,16,46,.15);border:1px solid rgba(200,16,46,.3);color:#fff;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600">Parcourir les dossiers</button>
        <button id="pick-upload" style="padding:11px 20px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);color:#fff;border-radius:8px;cursor:pointer;font-size:13px">⬆️ Uploader un fichier</button>
        <button id="pick-cancel" style="padding:9px 20px;background:transparent;border:none;color:rgba(255,255,255,.3);cursor:pointer;font-size:12px">Annuler</button>
      </div>
    </div>`;
  document.body.appendChild(modal);

  modal.querySelector("#pick-browse").onclick = () => {
    document.body.removeChild(modal);
    openBrowser(callback);
  };
  modal.querySelector("#pick-upload").onclick = () => {
    document.body.removeChild(modal);
    uploadImage(callback);
  };
  modal.querySelector("#pick-cancel").onclick = () => {
    document.body.removeChild(modal);
  };
  modal.onclick = e => { if (e.target === modal) { document.body.removeChild(modal); } };
}

// ══════════════════════════════════════════════════════════════════════════
//  CRM — Sauvegarde locale (survie aux redéploiements Railway)
// ══════════════════════════════════════════════════════════════════════════
function _crmSaveBackup(contacts) {
  try {
    localStorage.setItem("bininga_crm_backup", JSON.stringify({
      contacts, saved_at: new Date().toISOString()
    }));
  } catch (_) {}
}

async function _crmRestoreFromBackup() {
  const raw = localStorage.getItem("bininga_crm_backup");
  if (!raw) return 0;
  let contacts;
  try { contacts = JSON.parse(raw).contacts || []; } catch { return 0; }
  if (!contacts.length) return 0;
  let ok = 0;
  for (const c of contacts) {
    try {
      const res = await apiFetch("/api/crm/upsert", {
        method: "POST", headers: authHeaders(), body: JSON.stringify(c)
      });
      const d = await res.json();
      if (d.ok) ok++;
    } catch (_) {}
  }
  return ok;
}

async function _crmBackupAllInBackground() {
  try {
    const res = await apiFetch("/api/crm?limit=5000", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    if (data.ok && (data.contacts || []).length > 0) _crmSaveBackup(data.contacts);
  } catch (_) {}
}

// ══════════════════════════════════════════════════════════════════════════
//  CRM — Gestion des contacts (admin uniquement)
// ══════════════════════════════════════════════════════════════════════════
let _crmContacts    = [];
let _crmNewsletters = [];
let _crmTab         = "contacts";
let _crmPage        = 1;
let _crmTotalPages  = 1;
let _crmTotal       = 0;
let _crmSelected    = new Set();   // IDs sélectionnés pour bulk actions
const _CRM_LIMIT    = 50;

// ── Chargement depuis le serveur (avec pagination & filtres server-side) ──
async function loadCrm(page) {
  if (page !== undefined) _crmPage = page;
  const el = document.getElementById("crm-list");
  if (el) el.innerHTML = '<div class="msg-empty">Chargement…</div>';
  const q    = (document.getElementById("crm-search")?.value || "").trim();
  const fSrc = document.getElementById("crm-filter-source")?.value || "";
  const fNl  = document.getElementById("crm-filter-nl")?.value  || "";
  const params = new URLSearchParams({ page: _crmPage, limit: _CRM_LIMIT });
  if (q)    params.set("q",      q);
  if (fSrc) params.set("source", fSrc);
  if (fNl)  params.set("nl",     fNl);
  try {
    const res  = await apiFetch("/api/crm?" + params, { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    if (!data.ok) { if (el) el.innerHTML = '<div class="msg-empty">Erreur de chargement.</div>'; return; }

    // ── Restauration automatique depuis localStorage si le serveur est vide ──
    if ((data.total || 0) === 0 && !q && !fSrc && !fNl) {
      const raw = localStorage.getItem("bininga_crm_backup");
      if (raw) {
        let cached = [];
        try { cached = JSON.parse(raw).contacts || []; } catch { }
        if (cached.length > 0) {
          if (el) el.innerHTML = `<div class="msg-empty">Restauration de ${cached.length} contact(s) CRM depuis la sauvegarde locale…</div>`;
          const ok = await _crmRestoreFromBackup();
          if (ok > 0) { showToast(`${ok} contact(s) CRM restaurés automatiquement`); loadCrm(1); return; }
        }
      }
    }

    _crmContacts    = data.contacts    || [];
    _crmNewsletters = data.newsletters || [];
    _crmTotal       = data.total       || 0;
    _crmTotalPages  = data.pages       || 1;
    _crmPage        = data.page        || 1;
    setText("crm-kpi-total", data.total || 0);
    setText("crm-kpi-nl",    data.newsletter_count || 0);
    setBadge("badge-crm", data.total || 0);
    _crmSelected.clear();
    renderCrmList();
    renderNlHistory();
    // Mettre à jour la sauvegarde locale en arrière-plan
    if (data.total > 0) setTimeout(_crmBackupAllInBackground, 1500);
  } catch(e) {
    if (el) el.innerHTML = '<div class="msg-empty">Serveur non disponible.</div>';
  }
}

function crmChangePage(delta) {
  const newPage = _crmPage + delta;
  if (newPage < 1 || newPage > _crmTotalPages) return;
  loadCrm(newPage);
}

// ── Navigation entre onglets ─────────────────────────────────────────────
function crmTab(tab, btn) {
  _crmTab = tab;
  document.querySelectorAll("#panel-crm .tab").forEach(t => t.classList.remove("active"));
  if (btn) btn.classList.add("active");
  document.getElementById("crm-tab-contacts").style.display   = tab === "contacts"   ? "" : "none";
  document.getElementById("crm-tab-newsletter").style.display = tab === "newsletter" ? "" : "none";
}

// ── Rendu de la liste de contacts ────────────────────────────────────────
const CRM_SOURCE_BADGE = {
  audience:    `<span class="crm-tag crm-tag-aud">Audience</span>`,
  contact:     `<span class="crm-tag crm-tag-ct">Contact</span>`,
  reclamation: `<span class="crm-tag crm-tag-recl">Réclamation</span>`,
  signalement: `<span class="crm-tag crm-tag-sig">Signalement</span>`,
  newsletter:  `<span class="crm-tag crm-tag-nl">Newsletter</span>`,
  manuel:      `<span class="crm-tag crm-tag-man">Manuel</span>`,
};

function _updateBulkBar() {
  const bar   = document.getElementById("crm-bulk-bar");
  const cnt   = document.getElementById("crm-bulk-count");
  if (!bar) return;
  const n = _crmSelected.size;
  bar.style.display = n > 0 ? "flex" : "none";
  if (cnt) cnt.textContent = `${n} sélectionné(s)`;
}

function crmToggleSelect(id, checked) {
  if (checked) _crmSelected.add(id);
  else _crmSelected.delete(id);
  _updateBulkBar();
}

function crmDeselectAll() {
  _crmSelected.clear();
  document.querySelectorAll(".crm-check").forEach(cb => cb.checked = false);
  _updateBulkBar();
}

async function crmBulkDelete() {
  if (!_crmSelected.size) return;
  const n = _crmSelected.size;
  if (!confirm(`Supprimer ${n} contact(s) sélectionné(s) ? Cette action est irréversible.`)) return;
  try {
    const res  = await apiFetch("/api/crm/bulk-delete", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ ids: [..._crmSelected] })
    });
    const data = await res.json();
    if (data.ok) {
      showToast(`${data.deleted} contact(s) supprimé(s)`);
      _crmSelected.clear();
      await loadCrm(_crmPage);
      setTimeout(_crmBackupAllInBackground, 500);
    } else showToast(data.message || "Erreur", true);
  } catch { showToast("Serveur non disponible", true); }
}

function renderCrmList() {
  const el = document.getElementById("crm-list");
  if (!el) return;

  // Pagination UI
  const pagWrap = document.getElementById("crm-pagination");
  const prevBtn = document.getElementById("crm-prev");
  const nextBtn = document.getElementById("crm-next");
  const pageInfo = document.getElementById("crm-page-info");
  if (pagWrap) pagWrap.style.display = _crmTotalPages > 1 ? "flex" : "none";
  if (pageInfo) pageInfo.textContent = `Page ${_crmPage}/${_crmTotalPages} · ${_crmTotal} contact(s)`;
  if (prevBtn)  prevBtn.disabled = _crmPage <= 1;
  if (nextBtn)  nextBtn.disabled = _crmPage >= _crmTotalPages;

  const list = _crmContacts;

  if (!list.length) {
    el.innerHTML = '<div class="msg-empty">Aucun contact ne correspond aux filtres.</div>';
    _updateBulkBar();
    return;
  }

  el.innerHTML = list.map(c => {
    const checked = _crmSelected.has(c.id) ? "checked" : "";
    const srcTag  = CRM_SOURCE_BADGE[c.source]  || `<span class="crm-tag crm-tag-man">${esc(c.source)}</span>`;
    const nlBadge = c.newsletter && c.email
      ? `<span class="crm-tag crm-tag-nl">Newsletter</span>` : "";
    const tags    = (c.tags || []).map(t => `<span class="crm-tag crm-tag-man">${esc(t)}</span>`).join("");
    const notesCnt = (c.notes || []).length;
    return `
    <div class="crm-card" style="display:flex;gap:10px;align-items:flex-start">
      <input type="checkbox" class="crm-check" ${checked}
        style="margin-top:4px;width:16px;height:16px;accent-color:var(--r);flex-shrink:0;cursor:pointer"
        onchange="crmToggleSelect('${esc(c.id)}',this.checked)">
      <div style="flex:1;min-width:0">
        <div class="crm-card-top">
          <div>
            <div class="crm-card-name">${esc(c.prenom || "")} ${esc(c.nom || "")}</div>
            <div class="crm-card-meta">
              ${c.email ? `<span>Email : ${esc(c.email)}</span>` : ""}
              ${c.telephone ? `<span>Tél. : ${esc(c.telephone)}</span>` : ""}
              <span title="Expiration">Jusqu'au ${esc((c.expires_at||"").slice(0,10))}</span>
            </div>
          </div>
          <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">${srcTag}${nlBadge}${tags}</div>
        </div>
        ${c.sujet ? `<div class="crm-card-sujet">${esc(c.sujet)}</div>` : ""}
        <div class="crm-card-footer">
          <div style="font-size:11px;color:rgba(255,255,255,.3)">
            Créé le ${esc((c.created_at||"").slice(0,10))}
            ${notesCnt ? `· ${notesCnt} note${notesCnt>1?"s":""}` : ""}
          </div>
          <div style="display:flex;gap:6px">
            <button class="sbtn sbtn-progress" onclick="crmDetail('${esc(c.id)}')">Voir</button>
            <button class="sbtn sbtn-read"     onclick="crmEditModal('${esc(c.id)}')">Modifier</button>
            <button class="btn-danger" style="padding:4px 9px" onclick="crmDelete('${esc(c.id)}')">Supprimer</button>
          </div>
        </div>
      </div>
    </div>`;
  }).join("");
  _updateBulkBar();
}

// ── Import depuis contacts.json ──────────────────────────────────────────
async function crmImport() {
  if (!confirm("Importer toutes les demandes reçues (audiences, contacts, réclamations) dans le CRM ?\nLes doublons seront ignorés.")) return;
  try {
    const res  = await apiFetch("/api/crm/import", { method: "POST", headers: authHeaders(), body: JSON.stringify({}) });
    const data = await res.json();
    if (data.ok) {
      showToast(`${data.imported} contact(s) importé(s)`);
      loadCrm();
    } else {
      showToast(data.message || "Erreur", true);
    }
  } catch { showToast("Serveur non disponible", true); }
}

// ── Suppression ──────────────────────────────────────────────────────────
async function crmDelete(id) {
  if (!confirm("Supprimer ce contact du CRM ? Cette action est irréversible.")) return;
  try {
    const res  = await apiFetch("/api/crm/delete", { method: "POST", headers: authHeaders(), body: JSON.stringify({ id }) });
    const data = await res.json();
    if (data.ok) {
      showToast("Contact supprimé");
      await loadCrm();
      setTimeout(_crmBackupAllInBackground, 500);
    } else showToast(data.message || "Erreur", true);
  } catch { showToast("Serveur non disponible", true); }
}

// ── Modal Ajouter ────────────────────────────────────────────────────────
function crmAddModal() {
  document.getElementById("crm-edit-id").value      = "";
  document.getElementById("crm-modal-title").textContent = "Ajouter un contact";
  ["crm-f-nom","crm-f-prenom","crm-f-email","crm-f-tel","crm-f-sujet","crm-f-message","crm-f-tags"].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = "";
  });
  document.getElementById("crm-f-source").value  = "manuel";
  document.getElementById("crm-f-nl").checked    = false;
  document.getElementById("crm-modal").style.display = "flex";
}

// ── Modal Modifier ───────────────────────────────────────────────────────
function crmEditModal(id) {
  const c = _crmContacts.find(x => x.id === id);
  if (!c) return;
  document.getElementById("crm-edit-id").value = c.id;
  document.getElementById("crm-modal-title").textContent = `Modifier : ${c.prenom || ""} ${c.nom || ""}`.trim();
  document.getElementById("crm-f-nom").value     = c.nom      || "";
  document.getElementById("crm-f-prenom").value  = c.prenom   || "";
  document.getElementById("crm-f-email").value   = c.email    || "";
  document.getElementById("crm-f-tel").value     = c.telephone|| "";
  document.getElementById("crm-f-sujet").value   = c.sujet    || "";
  document.getElementById("crm-f-message").value = c.message  || "";
  document.getElementById("crm-f-source").value  = c.source   || "manuel";
  document.getElementById("crm-f-tags").value    = (c.tags || []).join(", ");
  document.getElementById("crm-f-nl").checked    = !!c.newsletter;
  document.getElementById("crm-modal").style.display = "flex";
}

function closeCrmModal() {
  document.getElementById("crm-modal").style.display = "none";
}

// ── Sauvegarde (création ou modification) ────────────────────────────────
async function crmSave() {
  const id    = document.getElementById("crm-edit-id").value.trim();
  const tagsRaw = document.getElementById("crm-f-tags").value;
  const payload = {
    id,
    nom:       document.getElementById("crm-f-nom").value.trim(),
    prenom:    document.getElementById("crm-f-prenom").value.trim(),
    email:     document.getElementById("crm-f-email").value.trim(),
    telephone: document.getElementById("crm-f-tel").value.trim(),
    sujet:     document.getElementById("crm-f-sujet").value.trim(),
    message:   document.getElementById("crm-f-message").value.trim(),
    source:    document.getElementById("crm-f-source").value,
    tags:      tagsRaw.split(",").map(t=>t.trim()).filter(Boolean),
    newsletter: document.getElementById("crm-f-nl").checked,
  };
  if (!payload.nom) { showToast("Le nom est requis", true); return; }
  try {
    const res  = await apiFetch("/api/crm/upsert", { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) });
    const data = await res.json();
    if (data.ok) {
      showToast(id ? "Contact modifié !" : "Contact ajouté !");
      closeCrmModal();
      await loadCrm();
      setTimeout(_crmBackupAllInBackground, 500);
    } else {
      showToast(data.message || "Erreur", true);
    }
  } catch { showToast("Serveur non disponible", true); }
}

// ── Fiche détail ─────────────────────────────────────────────────────────
function crmDetail(id) {
  const c = _crmContacts.find(x => x.id === id);
  if (!c) return;
  const modal = document.getElementById("crm-detail-modal");
  const body  = document.getElementById("crm-detail-body");
  document.getElementById("crm-detail-title").textContent =
    `Fiche : ${c.prenom || ""} ${c.nom || ""}`.trim();

  const srcTag  = CRM_SOURCE_BADGE[c.source] || `<span class="crm-tag crm-tag-man">${esc(c.source)}</span>`;
  const notesCnt = (c.notes || []).length;

  // Notes
  const notesHtml = (c.notes || []).reverse().map(n => `
    <div class="note-item">
      <div class="note-meta"><strong>${esc(n.auteur||"Admin")}</strong> · ${esc(n.ts||"")}</div>
      <div class="note-text">${esc(n.texte)}</div>
    </div>`).join("") || '<div style="font-size:11px;color:rgba(255,255,255,.2)">Aucune note.</div>';

  // Historique
  const histHtml = (c.historique || []).slice(-10).reverse().map(h => `
    <div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.04)">
      <span style="font-size:11px;color:rgba(255,255,255,.25);flex-shrink:0;padding-top:1px">${esc(h.ts||"")}</span>
      <span style="font-size:12px;color:rgba(255,255,255,.6)">${esc(h.detail||h.action||"")}</span>
    </div>`).join("") || '<div style="font-size:11px;color:rgba(255,255,255,.2)">Aucun historique.</div>';

  body.innerHTML = `
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px">
      ${srcTag}
      ${c.newsletter && c.email ? '<span class="crm-tag crm-tag-nl">Newsletter</span>' : ""}
      ${(c.tags||[]).map(t=>`<span class="crm-tag crm-tag-man">${esc(t)}</span>`).join("")}
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px">
      <div class="crm-detail-field"><div class="crm-detail-label">Nom complet</div>${esc(c.prenom||"")} ${esc(c.nom||"")}</div>
      <div class="crm-detail-field"><div class="crm-detail-label">Email</div>${c.email ? `<a href="mailto:${esc(c.email)}" style="color:#3498db">${esc(c.email)}</a>` : "—"}</div>
      <div class="crm-detail-field"><div class="crm-detail-label">Téléphone</div>${c.telephone ? `<a href="tel:${esc(c.telephone)}" style="color:#3498db">${esc(c.telephone)}</a>` : "—"}</div>
      <div class="crm-detail-field"><div class="crm-detail-label">Créé le</div>${esc((c.created_at||"").slice(0,10))}</div>
      <div class="crm-detail-field"><div class="crm-detail-label">Expire le</div>${esc((c.expires_at||"").slice(0,10))}</div>
    </div>
    ${c.sujet ? `<div class="crm-detail-field" style="margin-bottom:12px"><div class="crm-detail-label">Sujet</div>${esc(c.sujet)}</div>` : ""}
    ${c.message ? `<div class="crm-detail-field" style="margin-bottom:18px"><div class="crm-detail-label">Message</div><div style="white-space:pre-wrap;font-size:13px;color:rgba(255,255,255,.7)">${esc(c.message)}</div></div>` : ""}

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
      <div>
        <div class="notes-title">Notes internes (${notesCnt})</div>
        <div id="crm-notes-list-${esc(c.id)}">${notesHtml}</div>
        <div class="note-form" style="margin-top:10px">
          <textarea id="crm-note-ta-${esc(c.id)}" placeholder="Ajouter une note…" rows="2"></textarea>
          <button onclick="crmAddNote('${esc(c.id)}')">Ajouter</button>
        </div>
      </div>
      <div>
        <div class="notes-title">Historique</div>
        <div style="font-size:12px">${histHtml}</div>
      </div>
    </div>

    <div style="display:flex;gap:8px;margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,.06)">
      ${c.email ? `<a href="mailto:${esc(c.email)}?subject=${encodeURIComponent('Réponse Cabinet BININGA')}" class="sbtn sbtn-progress" style="text-decoration:none">Envoyer un email</a>` : ""}
      <button class="sbtn sbtn-read" onclick="crmEditModal('${esc(c.id)}');closeCrmDetail()">Modifier</button>
      <button class="btn-danger" style="padding:5px 11px" onclick="if(confirm('Supprimer ce contact ?')){crmDelete('${esc(c.id)}');closeCrmDetail();}">Supprimer</button>
    </div>`;

  modal.style.display = "flex";
}

function closeCrmDetail() {
  document.getElementById("crm-detail-modal").style.display = "none";
}


// ── Ajouter une note depuis la fiche ────────────────────────────────────
async function crmAddNote(id) {
  const ta = document.getElementById(`crm-note-ta-${id}`);
  const texte = ta ? ta.value.trim() : "";
  if (!texte) { showToast("Note vide", true); return; }
  try {
    const res  = await apiFetch("/api/crm/note", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ id, texte })
    });
    const data = await res.json();
    if (data.ok) {
      showToast("Note ajoutée");
      if (ta) ta.value = "";
      await loadCrm();
      crmDetail(id);  // Recharger la fiche
    } else { showToast(data.message || "Erreur", true); }
  } catch { showToast("Serveur non disponible", true); }
}

// ══════════════════════════════════════════════════════════════════════════
//  NEWSLETTER CRM
// ══════════════════════════════════════════════════════════════════════════

async function nlSend() {
  const sujet  = document.getElementById("nl-sujet").value.trim();
  const corps  = document.getElementById("nl-corps").value.trim();
  const filtre = document.getElementById("nl-filtre").value;
  const btn    = document.getElementById("btn-nl-send");
  const fb     = document.getElementById("nl-feedback");
  if (!sujet || !corps) { showToast("Sujet et corps requis", true); return; }
  const nlCount = filtre === "newsletter" ? _crmContacts.filter(c => c.newsletter && c.email).length
                : filtre === "tous"       ? _crmContacts.filter(c => c.email).length
                : _crmContacts.filter(c => c.email && c.tags && c.tags.includes(filtre)).length;
  if (!confirm(`Envoyer cette newsletter à ${nlCount} destinataire(s) ?`)) return;
  btn.disabled = true; btn.textContent = "Envoi en cours…";
  fb.style.display = "none";
  try {
    const res  = await apiFetch("/api/crm/newsletter/send", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ sujet, corps, filtre })
    });
    const data = await res.json();
    fb.style.display = "block";
    if (data.erreur) {
      fb.style.color   = "#f39c12";
      fb.innerHTML = `Envoyé à ${data.envoyes}/${data.total} destinataires.<br><small>${esc(data.erreur)}</small>`;
    } else {
      fb.style.color   = "#2ecc71";
      fb.textContent   = `Newsletter envoyée à ${data.envoyes} destinataire(s) !`;
      document.getElementById("nl-sujet").value = "";
      document.getElementById("nl-corps").value = "";
    }
    loadCrm();
  } catch(e) {
    fb.style.display = "block";
    fb.style.color   = "#e74c3c";
    fb.textContent   = "Erreur de connexion au serveur.";
  } finally {
    btn.disabled = false; btn.textContent = "Envoyer la newsletter";
  }
}

function renderNlHistory() {
  const el = document.getElementById("nl-history");
  if (!el) return;
  if (!_crmNewsletters.length) {
    el.innerHTML = '<div class="msg-empty">Aucune newsletter envoyée.</div>';
    return;
  }
  el.innerHTML = _crmNewsletters.map(nl => `
    <div class="crm-nl-row">
      <div style="flex:1;min-width:0">
        <div style="font-weight:700;font-size:13px;margin-bottom:4px">${esc(nl.sujet)}</div>
        <div style="font-size:11px;color:rgba(255,255,255,.3);margin-bottom:6px">${esc(nl.ts)} · ${nl.envoyes||0}/${nl.destinataires||0} envoyés</div>
        ${nl.apercu ? `<div style="font-size:12px;color:rgba(255,255,255,.4);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(nl.apercu)}</div>` : ""}
        ${nl.erreur ? `<div style="font-size:11px;color:#f39c12;margin-top:4px">Erreur : ${esc(nl.erreur)}</div>` : ""}
      </div>
      <span class="badge ${nl.statut === 'envoye' ? 'badge-done' : 'badge-wait'}" style="flex-shrink:0">
        ${nl.statut === 'envoye'  ? 'Envoyé' : 'Erreur'}
      </span>
    </div>
  `).join("");
}

// ══════════════════════════════════════════════════════════════════════════
//  2FA — Authentification à deux facteurs (TOTP)
// ══════════════════════════════════════════════════════════════════════════
let _tfaHas2fa = false;

function tfaRefreshStatus(has2fa) {
  _tfaHas2fa = !!has2fa;
  const status   = document.getElementById("tfa-status");
  const btnSetup = document.getElementById("tfa-btn-setup");
  const btnDis   = document.getElementById("tfa-btn-disable");
  if (status) {
    status.innerHTML = _tfaHas2fa
      ? '<span style="color:#2ecc71">2FA activé — votre compte est protégé</span>'
      : '<span style="color:rgba(255,255,255,.4)">2FA non activé — recommandé pour les admins</span>';
  }
  if (btnSetup) btnSetup.style.display = _tfaHas2fa ? "none" : "";
  if (btnDis)   btnDis.style.display   = _tfaHas2fa ? "" : "none";
}

async function tfaStartSetup() {
  try {
    const res  = await apiFetch("/api/2fa/setup", { method: "POST", headers: authHeaders(), body: "{}" });
    const data = await res.json();
    if (!data.ok) { showToast(data.message || "Erreur", true); return; }
    document.getElementById("tfa-secret").textContent   = data.secret;
    document.getElementById("tfa-qr-uri").textContent   = data.uri;
    document.getElementById("tfa-setup-box").style.display  = "";
    document.getElementById("tfa-actions").style.display    = "none";
    document.getElementById("tfa-confirm-code").value = "";
    document.getElementById("tfa-confirm-code").focus();
  } catch { showToast("Serveur non disponible", true); }
}

function tfaCancel() {
  document.getElementById("tfa-setup-box").style.display = "none";
  document.getElementById("tfa-actions").style.display   = "";
}

async function tfaActivate() {
  const code = document.getElementById("tfa-confirm-code").value.trim();
  if (code.length !== 6) { showToast("Code invalide (6 chiffres)", true); return; }
  try {
    const res  = await apiFetch("/api/2fa/activate", { method: "POST", headers: authHeaders(), body: JSON.stringify({ code }) });
    const data = await res.json();
    if (data.ok) {
      showToast("2FA activé avec succès !");
      tfaCancel();
      tfaRefreshStatus(true);
    } else showToast(data.message || "Erreur", true);
  } catch { showToast("Serveur non disponible", true); }
}

function tfaStartDisable() {
  document.getElementById("tfa-disable-box").style.display = "";
  document.getElementById("tfa-actions").style.display     = "none";
  document.getElementById("tfa-disable-code").value = "";
  document.getElementById("tfa-disable-code").focus();
}

function tfaCancelDisable() {
  document.getElementById("tfa-disable-box").style.display = "none";
  document.getElementById("tfa-actions").style.display     = "";
}

async function tfaDisable() {
  const code = document.getElementById("tfa-disable-code").value.trim();
  if (!code) { showToast("Code requis", true); return; }
  try {
    const res  = await apiFetch("/api/2fa/disable", { method: "POST", headers: authHeaders(), body: JSON.stringify({ code }) });
    const data = await res.json();
    if (data.ok) {
      showToast("2FA désactivé");
      tfaCancelDisable();
      tfaRefreshStatus(false);
    } else showToast(data.message || "Erreur", true);
  } catch { showToast("Serveur non disponible", true); }
}

// ════════════════════════════════════════════════════════════
// ── ÉDITORIAL IA ─────────────────────────────────────────────
// ════════════════════════════════════════════════════════════

let _editorialData   = [];
let _editorialFilter = "tous";

function editorialTab(tab, btn) {
  document.getElementById("editorial-tab-articles").style.display = tab === "articles" ? "" : "none";
  document.getElementById("editorial-tab-generer").style.display  = tab === "generer"  ? "" : "none";
  document.querySelectorAll("#panel-editorial .etab-btn, #etab-articles, #etab-generer").forEach(b => {
    b.style.color         = "rgba(255,255,255,.4)";
    b.style.borderBottom  = "2px solid transparent";
  });
  const active = document.getElementById("etab-" + tab);
  if (active) { active.style.color = "#fff"; active.style.borderBottom = "2px solid var(--r)"; }
  if (tab === "generer") loadEdNewsPicker();
}

function filterEditorial(statut, btn) {
  _editorialFilter = statut;
  document.querySelectorAll(".ef-btn").forEach(b => {
    b.style.background = "rgba(255,255,255,.04)";
    b.style.color      = "rgba(255,255,255,.4)";
    b.style.border     = "1px solid rgba(255,255,255,.1)";
  });
  if (btn) {
    const colors = { brouillon: ["rgba(243,156,18,.06)","#f39c12","rgba(243,156,18,.3)"], valide: ["rgba(46,204,113,.06)","#2ecc71","rgba(46,204,113,.3)"], publie: ["rgba(52,152,219,.06)","#3498db","rgba(52,152,219,.3)"], tous: ["rgba(255,255,255,.08)","#fff","rgba(255,255,255,.15)"] };
    const c = colors[statut] || colors.tous;
    btn.style.background = c[0]; btn.style.color = c[1]; btn.style.border = `1px solid ${c[2]}`;
  }
  renderEditorialList();
}

async function loadEditorial() {
  const list = document.getElementById("editorial-list");
  list.innerHTML = '<div style="text-align:center;color:rgba(255,255,255,.3);padding:30px 0;font-size:13px">Chargement…</div>';
  try {
    const res  = await apiFetch("/api/editorial", { headers: authHeaders() });
    const data = await res.json();
    if (!data.ok) { list.innerHTML = `<div style="color:#e74c3c;font-size:13px;padding:20px 0">${data.message}</div>`; return; }
    _editorialData = data.articles || [];
    const badge = document.getElementById("badge-editorial");
    const cnt   = document.getElementById("badge-editorial-count");
    if (_editorialData.length > 0) { if (badge) { badge.textContent = _editorialData.length; badge.style.display = ""; } }
    if (cnt) cnt.textContent = _editorialData.length;
    renderEditorialList();
  } catch { list.innerHTML = '<div style="color:#e74c3c;font-size:13px;padding:20px 0">Serveur non disponible</div>'; }
}

function renderEditorialList() {
  const list = document.getElementById("editorial-list");
  const arts  = _editorialFilter === "tous" ? _editorialData : _editorialData.filter(a => a.statut === _editorialFilter);
  if (!arts.length) {
    list.innerHTML = '<div style="text-align:center;color:rgba(255,255,255,.3);padding:40px 0;font-size:13px">Aucun article' + (_editorialFilter !== "tous" ? " dans cette catégorie" : "") + '.<br><small style="font-size:11px;margin-top:6px;display:block">Utilisez l\'onglet Générer pour créer un premier article.</small></div>';
    return;
  }
  const statutBadge = { brouillon: ['#f39c12','Brouillon'], valide: ['#2ecc71','Validé'], publie: ['#3498db','Publié'] };
  list.innerHTML = arts.map(a => {
    const sb  = statutBadge[a.statut] || ['#888','?'];
    const pts = (a.points_cles || []).slice(0,2).map(p => `<div style="font-size:11px;color:rgba(255,255,255,.45);margin-top:2px">- ${p}</div>`).join("");
    return `<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:12px 14px;cursor:pointer" onclick="openEdModal('${a.id}')">
      <div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:6px">
        <div style="flex:1;font-size:13px;font-weight:700;color:#fff;line-height:1.4">${a.titre || "Sans titre"}</div>
        <span style="flex-shrink:0;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;background:${sb[0]}22;color:${sb[0]};border:1px solid ${sb[0]}44">${sb[1]}</span>
      </div>
      <div style="font-size:11px;color:rgba(255,255,255,.4);margin-bottom:6px;line-height:1.5">${(a.resume || "").slice(0,120)}${(a.resume||"").length>120?"…":""}</div>
      ${pts}
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
        <span style="font-size:10px;color:rgba(255,255,255,.25)">${a.source_nom||""} · ${a.created_at||""}</span>
        <span style="font-size:10px;color:rgba(255,255,255,.35)">Voir →</span>
      </div>
    </div>`;
  }).join("");
}

function openEdModal(id) {
  const a = _editorialData.find(x => x.id === id);
  if (!a) return;
  const sb = { brouillon: ['#f39c12','Brouillon'], valide: ['#2ecc71','Validé'], publie: ['#3498db','Publié'] };
  const s  = sb[a.statut] || ['#888','?'];
  document.getElementById("ed-modal-titre-h").textContent = a.titre || "Article éditorial";
  const pts = (a.points_cles || []).map(p => `<li style="margin-bottom:4px">${p}</li>`).join("");
  const srcs= (a.sources || []).map(s => `<div style="font-size:11px;color:#3498db;word-break:break-all">${s}</div>`).join("");
  document.getElementById("ed-modal-body").innerHTML = `
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
      <span style="font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;background:${s[0]}22;color:${s[0]};border:1px solid ${s[0]}44">${s[1]}</span>
      <span style="font-size:11px;color:rgba(255,255,255,.3)">${a.source_nom||""}</span>
      <span style="font-size:11px;color:rgba(255,255,255,.25)">${a.created_at||""}</span>
    </div>
    <div style="font-size:15px;font-weight:700;color:#fff;margin-bottom:10px;line-height:1.4">${a.titre||""}</div>
    <div style="background:rgba(52,152,219,.06);border-left:3px solid #3498db;padding:10px 12px;border-radius:0 6px 6px 0;margin-bottom:14px">
      <div style="font-size:11px;font-weight:700;color:#3498db;margin-bottom:5px;text-transform:uppercase;letter-spacing:.5px">Résumé</div>
      <div style="font-size:13px;color:rgba(255,255,255,.75);line-height:1.6">${(a.resume||"").replace(/\n/g,"<br>")}</div>
    </div>
    <div style="font-size:12px;color:rgba(255,255,255,.7);line-height:1.7;margin-bottom:14px;white-space:pre-wrap">${a.article||""}</div>
    ${pts ? `<div style="margin-bottom:14px"><div style="font-size:11px;font-weight:700;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Points clés</div><ul style="padding-left:16px;margin:0;color:rgba(255,255,255,.65);font-size:12px;line-height:1.6">${pts}</ul></div>` : ""}
    ${srcs ? `<div style="margin-bottom:14px"><div style="font-size:11px;font-weight:700;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Sources</div>${srcs}</div>` : ""}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,.08)">
      <button onclick="changeEdStatut('${a.id}','valide')" style="flex:1;min-width:100px;padding:9px;border-radius:8px;border:1px solid rgba(46,204,113,.3);background:rgba(46,204,113,.08);color:#2ecc71;font-size:12px;font-weight:700;cursor:pointer">Valider</button>
      <button onclick="changeEdStatut('${a.id}','publie')" style="flex:1;min-width:100px;padding:9px;border-radius:8px;border:1px solid rgba(52,152,219,.3);background:rgba(52,152,219,.08);color:#3498db;font-size:12px;font-weight:700;cursor:pointer">Publier</button>
      <button onclick="deleteEdArticle('${a.id}')" style="padding:9px 14px;border-radius:8px;border:1px solid rgba(231,76,60,.3);background:rgba(231,76,60,.08);color:#e74c3c;font-size:12px;cursor:pointer">Supprimer</button>
    </div>`;
  document.getElementById("ed-modal").style.display = "";
  document.body.style.overflow = "hidden";
}

function closeEdModal() {
  document.getElementById("ed-modal").style.display = "none";
  document.body.style.overflow = "";
}

async function changeEdStatut(id, statut) {
  try {
    const res  = await apiFetch("/api/editorial/save", { method: "POST", headers: authHeaders(), body: JSON.stringify({ id, statut }) });
    const data = await res.json();
    if (data.ok) {
      const a = _editorialData.find(x => x.id === id);
      if (a) a.statut = statut;
      closeEdModal();
      renderEditorialList();
      showToast("Statut mis à jour");
    } else showToast(data.message || "Erreur", true);
  } catch { showToast("Serveur non disponible", true); }
}

async function deleteEdArticle(id) {
  if (!confirm("Supprimer cet article éditorial ?")) return;
  try {
    const res  = await apiFetch("/api/editorial/delete", { method: "POST", headers: authHeaders(), body: JSON.stringify({ id }) });
    const data = await res.json();
    if (data.ok) {
      _editorialData = _editorialData.filter(a => a.id !== id);
      closeEdModal();
      renderEditorialList();
      const cnt = document.getElementById("badge-editorial-count");
      if (cnt) cnt.textContent = _editorialData.length;
      showToast("Article supprimé");
    } else showToast(data.message || "Erreur", true);
  } catch { showToast("Serveur non disponible", true); }
}

async function generateEditorial(newsItem) {
  const btn = document.getElementById("btn-generate-ed");
  const titre  = newsItem ? newsItem.title   : (document.getElementById("ed-titre")?.value.trim()  || "");
  const resume = newsItem ? newsItem.summary  : (document.getElementById("ed-resume")?.value.trim() || "");
  const source = newsItem ? newsItem.source   : (document.getElementById("ed-source")?.value.trim() || "");
  const url    = newsItem ? newsItem.url      : (document.getElementById("ed-url")?.value.trim()    || "");
  const date   = newsItem ? newsItem.published: "";
  const newsId = newsItem ? newsItem.id       : "";

  if (!titre || !resume) { showToast("Titre et résumé requis", true); return; }
  if (btn) { btn.textContent = "Génération en cours…"; btn.disabled = true; }
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 55000); // 55s timeout
    const res  = await apiFetch("/api/editorial/generate", {
      method: "POST", headers: authHeaders(),
      body: JSON.stringify({ news_id: newsId, titre, resume, source, url, date }),
      signal: controller.signal
    });
    clearTimeout(timer);
    const data = await res.json();
    if (data.ok) {
      _editorialData.unshift(data.article);
      const cnt = document.getElementById("badge-editorial-count");
      if (cnt) cnt.textContent = _editorialData.length;
      showToast("Article généré");
      // Passer sur l'onglet articles et ouvrir
      editorialTab("articles", document.getElementById("etab-articles"));
      renderEditorialList();
      openEdModal(data.article.id);
      // Reset formulaire
      ["ed-titre","ed-resume","ed-source","ed-url"].forEach(id => { const el = document.getElementById(id); if(el) el.value=""; });
    } else showToast(data.message || "Erreur génération", true);
  } catch (e) {
    if (e.name === "AbortError") showToast("Délai dépassé — réessayez", true);
    else showToast("Erreur : " + e.message, true);
  }
  finally { if (btn) { btn.textContent = "Générer l'article éditorial"; btn.disabled = false; } }
}

let _edNewsPicker = [];
async function loadEdNewsPicker() {
  const box = document.getElementById("ed-news-picker");
  if (!box) return;
  box.innerHTML = '<div style="text-align:center;color:rgba(255,255,255,.3);padding:16px 0;font-size:12px">Chargement…</div>';
  try {
    const res  = await apiFetch("/api/news", { headers: authHeaders() });
    const data = await res.json();
    const items = (data.items || []).filter(a => a.category === "bininga" || (a.title + (a.summary||"")).toLowerCase().includes("bininga")).slice(0, 20);
    _edNewsPicker = items;
    if (!items.length) { box.innerHTML = '<div style="text-align:center;color:rgba(255,255,255,.3);padding:16px 0;font-size:12px">Aucun article Bininga disponible dans la veille.<br><small>Lancez une recherche dans YARO IA.</small></div>'; return; }
    box.innerHTML = items.map((a,i) => `
      <div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:8px;padding:10px 12px;cursor:pointer;active:background:rgba(255,255,255,.06)" onclick="generateEditorial(_edNewsPicker[${i}])">
        <div style="font-size:12px;font-weight:700;color:#fff;margin-bottom:4px;line-height:1.4">${a.title||"Sans titre"}</div>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:10px;color:rgba(255,255,255,.3)">${a.source||""} · ${(a.published||"").slice(0,10)}</span>
          <span style="font-size:11px;color:var(--r);font-weight:700">Générer →</span>
        </div>
      </div>`).join("");
  } catch { box.innerHTML = '<div style="color:#e74c3c;font-size:12px;padding:16px 0">Impossible de charger les actualités.</div>'; }
}

// ══════════════════════════════════════════════════════════════════════════
//  MONITORING DASHBOARD
// ══════════════════════════════════════════════════════════════════════════
let _monRefreshTimer = null;

async function loadMonitoring() {
  await Promise.all([loadMonSummary(), loadMonAlerts(), loadMonEndpoints(), loadMonRequests(), loadMonExceptions()]);
  // Auto-refresh toutes les 30s
  clearInterval(_monRefreshTimer);
  _monRefreshTimer = setInterval(loadMonitoring, 30000);
}

async function loadMonSummary() {
  try {
    const r = await fetch("/api/monitoring/summary", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    if (!r.ok) return;
    const d = await r.json();
    if (!d.ok) return;

    // Statut global
    const bar  = document.getElementById("mon-status-bar");
    const icon = document.getElementById("mon-status-icon");
    const txt  = document.getElementById("mon-status-text");
    const ts   = document.getElementById("mon-status-ts");
    bar.className = "mon-status-bar mon-" + (d.global_status || "unknown").toLowerCase();
    const statusLabel = { OK: "Système opérationnel", WARNING: "Attention — anomalies détectées", CRITICAL: "CRITIQUE — intervention requise", UNKNOWN: "Statut inconnu" };
    icon.textContent = { OK: "OK", WARNING: "!", CRITICAL: "!!", UNKNOWN: "?" }[d.global_status] || "?";
    txt.textContent  = statusLabel[d.global_status] || d.global_status;
    if (ts) ts.textContent = d.ts || "";

    // Mise à jour badge sidebar
    const badge = document.getElementById("badge-mon");
    const crit  = (d.alerts || {}).CRITICAL || 0;
    const warn  = (d.alerts || {}).WARNING  || 0;
    if (badge) { badge.style.display = (crit + warn > 0) ? "" : "none"; badge.textContent = crit + warn; }

    // KPIs
    _setMon("mon-req-24h",  d.requests_24h  ?? "—");
    _setMon("mon-err-24h",  d.errors_24h    ?? "—");
    _setMon("mon-latency",  d.avg_latency_ms != null ? d.avg_latency_ms + "ms" : "—");
    _setMon("mon-errrate",  d.error_rate_5m  != null ? d.error_rate_5m + "%" : "—");
    _setMon("mon-sessions", d.active_sessions ?? "—");
    _setMon("mon-blocked",  d.blocked_ips    ?? "—");

    // Barres système
    const sys = d.system || {};
    _setBar("cpu",  sys.cpu_percent);
    _setBar("mem",  sys.memory_percent);
    _setBar("disk", sys.disk_percent);

  } catch {}
}

function _setMon(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function _setBar(name, pct) {
  const bar = document.getElementById("mon-bar-" + name);
  const val = document.getElementById("mon-val-" + name);
  if (!bar) return;
  const p = parseFloat(pct) || 0;
  bar.style.width = Math.min(p, 100) + "%";
  bar.className = "mon-bar " + (p >= 90 ? "mon-bar-crit" : p >= 75 ? "mon-bar-warn" : "mon-bar-ok");
  if (val) val.textContent = p + "%";
}

async function loadMonAlerts() {
  const box = document.getElementById("mon-alerts-list");
  if (!box) return;
  try {
    const resolved = document.getElementById("mon-show-resolved")?.checked ? "1" : "0";
    const r = await fetch(`/api/monitoring/alerts?resolved=${resolved}`, { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const d = await r.json();
    if (!d.ok || !d.alerts.length) { box.innerHTML = '<p class="msg-empty">Aucune alerte active.</p>'; return; }
    box.innerHTML = d.alerts.map(a => {
      const cls = a.level === "CRITICAL" ? "mon-alert-crit" : a.level === "WARNING" ? "mon-alert-warn" : "mon-alert-info";
      const mark = a.level === "CRITICAL" ? "!!" : a.level === "WARNING" ? "!" : "i";
      return `<div class="mon-alert-item ${cls}">
        <div>${mark}</div>
        <div class="mon-alert-msg">
          <div class="mon-alert-rule">${esc(a.level)} — ${esc(a.rule)}</div>
          <div>${esc(a.message)}</div>
          <div class="mon-alert-ts">${esc(a.ts)}${a.resolved ? " · Résolu à " + esc(a.resolved_at || "") : ""}</div>
        </div>
        ${!a.resolved ? `<button class="mon-alert-resolve" onclick="resolveAlert(${a.id})">Résoudre</button>` : ""}
      </div>`;
    }).join("");
  } catch { box.innerHTML = '<p style="color:#e74c3c;font-size:12px">Erreur chargement alertes.</p>'; }
}

async function resolveAlert(id) {
  try {
    await fetch("/api/monitoring/resolve-alert", {
      method: "POST",
      headers: { "X-Admin-Token": SESSION_TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    await loadMonAlerts();
    await loadMonSummary();
  } catch {}
}

async function loadMonEndpoints() {
  const box = document.getElementById("mon-endpoints-list");
  if (!box) return;
  try {
    const r = await fetch("/api/monitoring/endpoints?hours=24", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const d = await r.json();
    if (!d.ok || !d.endpoints.length) { box.innerHTML = '<p class="msg-empty">Pas encore de données.</p>'; return; }
    box.innerHTML = `<table class="mon-ep-table">
      <thead><tr><th>Endpoint</th><th>Requêtes</th><th>Latence moy</th><th>Erreurs</th></tr></thead>
      <tbody>${d.endpoints.map(ep => `
        <tr>
          <td class="mon-ep-path">${esc(ep.path)}</td>
          <td>${ep.count}</td>
          <td style="color:${ep.avg_ms > 2000 ? "#e74c3c" : ep.avg_ms > 1000 ? "#f39c12" : "#2ecc71"}">${ep.avg_ms}ms</td>
          <td style="color:${ep.errors > 0 ? "#e74c3c" : "rgba(255,255,255,.5)"}">${ep.errors}</td>
        </tr>`).join("")}
      </tbody></table>`;
  } catch {}
}

async function loadMonRequests() {
  const box    = document.getElementById("mon-requests-list");
  const filter = document.getElementById("mon-req-filter")?.value || "";
  if (!box) return;
  try {
    const url = `/api/monitoring/requests?limit=50${filter ? "&path=" + encodeURIComponent(filter) : ""}`;
    const r = await fetch(url, { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const d = await r.json();
    if (!d.ok || !d.requests.length) { box.innerHTML = '<p class="msg-empty">Aucune requête enregistrée.</p>'; return; }
    box.innerHTML = d.requests.map(req => {
      const mBadge = req.method === "POST" ? "mon-badge-post" : "mon-badge-get";
      const sBadge = req.status_code >= 500 ? "mon-badge-5xx" : "mon-badge-ok";
      const dur    = req.duration_ms != null ? Math.round(req.duration_ms) + "ms" : "—";
      return `<div class="mon-req-item">
        <span class="${mBadge}">${esc(req.method || "GET")}</span>
        <span class="${sBadge}">${req.status_code || "—"}</span>
        <span class="mon-req-path">${esc(req.path)}</span>
        <span class="mon-req-dur">${dur}</span>
        <span style="font-size:10px;color:rgba(255,255,255,.25);min-width:130px;text-align:right">${esc(req.ts || "")}</span>
      </div>`;
    }).join("");
  } catch {}
}

async function loadMonExceptions() {
  const box = document.getElementById("mon-errors-list");
  if (!box) return;
  try {
    const r = await fetch("/api/monitoring/errors", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const d = await r.json();
    if (!d.ok || !d.errors.length) { box.innerHTML = '<p class="msg-empty">Aucune exception enregistrée.</p>'; return; }
    box.innerHTML = d.errors.map(e => `
      <div class="mon-err-item">
        <div class="mon-err-type">${esc(e.error_type || "Exception")}</div>
        <div class="mon-err-msg">${esc(e.message || "")}</div>
        <div class="mon-err-meta">${esc(e.path || "")} · ${esc(e.ts || "")} · IP ${esc(e.ip || "")}</div>
      </div>`).join("");
  } catch {}
}

async function loadMonReport() {
  const box = document.getElementById("mon-report-box");
  if (!box) return;
  box.innerHTML = '<span style="color:rgba(255,255,255,.4);font-size:12px">Génération en cours…</span>';
  try {
    const r = await fetch("/api/monitoring/report", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const d = await r.json();
    if (!d.ok) { box.innerHTML = '<p style="color:#e74c3c">Erreur génération rapport.</p>'; return; }
    const rp = d.report;
    const statusColor = rp.status === "CRITICAL" ? "#e74c3c" : rp.status === "WARNING" ? "#f39c12" : "#2ecc71";
    const problems = rp.problems?.length
      ? `<div style="margin-bottom:10px"><b style="font-size:12px;color:rgba(255,255,255,.5)">PROBLÈMES DÉTECTÉS</b>
           <ul class="mon-problem-list">${rp.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>` : "";
    const recs = rp.recommendations?.length
      ? `<div><b style="font-size:12px;color:rgba(255,255,255,.5)">RECOMMANDATIONS</b>
           <ul class="mon-rec-list">${rp.recommendations.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div>` : "";
    box.innerHTML = `
      <div class="mon-report-status" style="color:${statusColor}">
        ${esc(rp.status || "OK")} — ${esc(rp.period || "")}
      </div>
      <div class="mon-report-row">
        ${[["Requêtes",rp.requests_total],["Erreurs HTTP",rp.errors_total],["Exceptions",rp.exceptions],["Alertes",rp.active_alerts],["Latence moy",rp.avg_latency_ms+"ms"],["Taux err.",rp.error_rate+"%"]].map(([l,v])=>`
          <div class="mon-report-stat"><div class="mon-report-stat-n">${v??'—'}</div><div class="mon-report-stat-l">${l}</div></div>`).join("")}
      </div>
      ${problems}${recs}
      ${rp.slow_endpoints?.length ? `<div style="margin-top:10px"><b style="font-size:12px;color:rgba(255,255,255,.5)">ENDPOINTS LENTS</b>
        ${rp.slow_endpoints.map(e=>`<div style="font-size:12px;padding:4px 0;font-family:monospace;color:rgba(255,255,255,.7)">${esc(e.path)} — <span style="color:#f39c12">${e.avg_ms}ms</span></div>`).join("")}</div>` : ""}
      <div style="font-size:10px;color:rgba(255,255,255,.25);margin-top:14px">Généré le ${esc(rp.generated_at||"")}</div>
      <button class="sbtn sbtn-progress" style="margin-top:12px" onclick="loadMonReport()">Régénérer</button>`;
  } catch { box.innerHTML = '<p style="color:#e74c3c">Erreur réseau.</p>'; }
}

function esc(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

// ══════════════════════════════════════════════════════════════════════════
//  NOTIFICATIONS TEMPS RÉEL (SSE)
// ══════════════════════════════════════════════════════════════════════════
let _notifs      = [];
let _notifCount  = 0;
let _sseSource   = null;
let _audioCtx    = null;
let _notifOpen   = false;

const _NOTIF_META = {
  visit:      { icon: "VI",  title: "Nouveau visiteur",   panel: "monitoring",   color: "#3498db" },
  prog_view:  { icon: "PR",  title: "Programme consulté", panel: "monitoring",   color: "#9b59b6" },
  contact:    { icon: "ME",  title: "Nouveau message",    panel: "contacts",     color: "#2ecc71" },
  audience:   { icon: "PR",  title: "Demande d'audience", panel: "audiences",    color: "#f39c12" },
  reclamation:{ icon: "RE",  title: "Nouvelle réclamation",panel: "reclamations",color: "#e74c3c" },
};

function initNotifications() {
  if (Notification.permission === "default") Notification.requestPermission();
  _connectSSE();
  // Fermer le panel si clic en dehors
  document.addEventListener("click", e => {
    if (_notifOpen && !document.getElementById("notif-bell-wrap")?.contains(e.target)) {
      _closeNotifPanel();
    }
  });
}

let _sseRetryDelay = 3000;
let _sseRetryTimer = null;

function _connectSSE() {
  if (_sseSource) { try { _sseSource.close(); } catch {} _sseSource = null; }
  if (!SESSION_TOKEN) return;  // pas de token valide → pas de connexion

  _sseSource = new EventSource(`/api/events?t=${encodeURIComponent(SESSION_TOKEN)}`);

  _sseSource.onopen = () => {
    _sseRetryDelay = 3000;  // réinitialiser le délai de reconnexion
  };

  ["visit","prog_view","contact","audience","reclamation"].forEach(type => {
    _sseSource.addEventListener(type, e => {
      try { _addNotif(type, JSON.parse(e.data)); } catch {}
    });
  });

  _sseSource.onerror = () => {
    try { _sseSource.close(); } catch {} _sseSource = null;
    if (!SESSION_TOKEN) return;  // déconnecté, ne pas reconnecter
    if (_sseRetryTimer) clearTimeout(_sseRetryTimer);
    _sseRetryTimer = setTimeout(() => {
      _sseRetryDelay = Math.min(_sseRetryDelay * 2, 60000);  // backoff exponentiel max 60s
      _connectSSE();
    }, _sseRetryDelay);
  };
}

function _addNotif(type, data) {
  const meta = _NOTIF_META[type] || { icon: "NT", title: "Notification", panel: "dashboard" };
  let desc = "";
  if (data.nom)   desc = (data.nom + " " + (data.prenom || "")).trim();
  if (data.objet) desc += (desc ? " — " : "") + data.objet;
  if (type === "visit" || type === "prog_view") desc = "IP " + (data.ip || "inconnue");

  const notif = {
    id: Date.now() + Math.random(),
    type, title: meta.title, desc,
    panel: meta.panel, icon: meta.icon,
    ts: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
  };
  _notifs.unshift(notif);
  if (_notifs.length > 60) _notifs.pop();
  _notifCount++;

  _renderNotifBadge();
  _renderNotifList();
  _playNotifSound();
  _shakebell();

  // Rafraîchissement automatique du panneau actif selon le type d'événement
  if (type === "audience" || type === "reclamation") {
    syncMessages().then(() => {
      if (_currentPanel === "audiences")    renderAudiences();
      if (_currentPanel === "reclamations") renderReclamations();
      if (_currentPanel === "dashboard")    refreshDashboard();
    });
  } else if (type === "contact") {
    syncMessages().then(() => {
      if (_currentPanel === "contacts")  renderContacts();
      if (_currentPanel === "dashboard") refreshDashboard();
    });
  }

  // Notification navigateur
  if (Notification.permission === "granted" && document.visibilityState !== "visible") {
    try {
      const n = new Notification("BININGA Admin — " + meta.title, {
        body: desc || "",
        icon: "/images/bininga.jpg",
        tag: type,
      });
      n.onclick = () => { window.focus(); showPanel(meta.panel); n.close(); };
      setTimeout(() => n.close(), 6000);
    } catch {}
  }
}

function _renderNotifBadge() {
  const badge = document.getElementById("notif-badge");
  if (!badge) return;
  if (_notifCount > 0) {
    badge.textContent = _notifCount > 99 ? "99+" : _notifCount;
    badge.style.display = "flex";
  } else {
    badge.style.display = "none";
  }
}

function _renderNotifList() {
  const list = document.getElementById("notif-list");
  if (!list) return;
  if (!_notifs.length) {
    list.innerHTML = '<div class="notif-empty">Aucune notification</div>';
    return;
  }
  list.innerHTML = _notifs.map(n => `
    <div class="notif-item notif-${n.type}" onclick="notifClick('${n.panel}')">
      <div class="notif-icon">${n.icon}</div>
      <div class="notif-body">
        <div class="notif-title">${esc(n.title)}</div>
        <div class="notif-desc">${esc(n.desc || "—")}</div>
        <div class="notif-time">${esc(n.ts)}</div>
      </div>
    </div>`).join("");
}

function _shakebell() {
  const btn = document.getElementById("notif-bell");
  if (!btn) return;
  btn.classList.add("has-notif");
  setTimeout(() => btn.classList.remove("has-notif"), 600);
}

function _playNotifSound() {
  try {
    if (!_audioCtx) _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const now = _audioCtx.currentTime;
    // Deux notes : chime doux
    [[880, 0, 0.15], [660, 0.15, 0.15]].forEach(([freq, delay, dur]) => {
      const osc  = _audioCtx.createOscillator();
      const gain = _audioCtx.createGain();
      osc.connect(gain); gain.connect(_audioCtx.destination);
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now + delay);
      gain.gain.setValueAtTime(0.25, now + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, now + delay + dur);
      osc.start(now + delay);
      osc.stop(now + delay + dur);
    });
  } catch {}
}

function toggleNotifPanel() {
  const panel = document.getElementById("notif-panel");
  if (!panel) return;
  _notifOpen = !_notifOpen;
  panel.style.display = _notifOpen ? "block" : "none";
  if (_notifOpen) { _notifCount = 0; _renderNotifBadge(); }
}

function _closeNotifPanel() {
  _notifOpen = false;
  const panel = document.getElementById("notif-panel");
  if (panel) panel.style.display = "none";
}

function notifClick(panelName) {
  _closeNotifPanel();
  showPanel(panelName, document.querySelector(`.sb-item[onclick*="'${panelName}'"]`));
}

function clearNotifs() {
  _notifs = [];
  _notifCount = 0;
  _renderNotifBadge();
  _renderNotifList();
}
