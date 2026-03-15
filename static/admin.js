// ══════════════════════════════════════════════════════════════════════════
//  SÉCURITÉ — Authentification par hachage SHA-256 (WebCrypto)
//  Les identifiants ne sont jamais stockés en clair dans le code.
// ══════════════════════════════════════════════════════════════════════════
// Session — jamais codée en dur ici, jamais dans sessionStorage
let SESSION_TOKEN = "";
let SESSION_CSRF  = "";
let SESSION_ROLE  = "";
let SESSION_NOM   = "";

// Helper : headers authentifiés avec CSRF
function authHeaders(extra) {
  return Object.assign({
    "Content-Type": "application/json",
    "X-Admin-Token": SESSION_TOKEN,
    "X-CSRF-Token": SESSION_CSRF,
  }, extra);
}

async function doLogin() {
  const u = document.getElementById("u").value.trim();
  const p = document.getElementById("p").value;
  const btn = document.querySelector(".login-btn");
  btn.disabled = true;
  btn.textContent = "Connexion…";
  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p })
    });
    const data = await res.json();
    if (data.ok) {
      SESSION_TOKEN = data.token;
      SESSION_CSRF  = data.csrf_token || "";
      SESSION_ROLE  = data.role;
      SESSION_NOM   = data.nom;
      document.getElementById("login").classList.add("hidden");
      document.getElementById("app").classList.add("visible");
      document.getElementById("last-login").textContent = new Date().toLocaleString("fr-FR");
      document.getElementById("topbar-user").textContent = data.nom + " · " + data.role;
      applyRoleUI(data.role);
      init();
    } else {
      const errEl = document.getElementById("err");
      errEl.textContent = "Identifiant ou mot de passe incorrect.";
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
  SESSION_TOKEN = "";
  SESSION_ROLE  = "";
  SESSION_NOM   = "";
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
    el.style.display = role === "admin" ? "" : "none";
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
  btn.textContent = visible ? "✕ Fermer" : "+ Ajouter un utilisateur";
  if (visible) container.scrollIntoView({ behavior: "smooth", block: "nearest" });
  if (!visible) resetUserForm();
}

async function loadUsers() {
  const el = document.getElementById("user-list");
  el.innerHTML = '<div class="msg-empty">Chargement…</div>';
  try {
    const res  = await fetch("/api/users", { headers: { "X-Admin-Token": SESSION_TOKEN } });
    const data = await res.json();
    setBadge("badge-users", data.ok ? data.users.length : 0);
    if (!data.ok || !data.users.length) {
      el.innerHTML = '<div class="msg-empty">Aucun utilisateur.</div>';
      return;
    }
    const roleLabels = { admin: "Admin", editeur: "Éditeur", lecteur: "Lecteur" };
    const initials   = u => (u.nom || u.username).charAt(0).toUpperCase();
    el.innerHTML = data.users.map(u => `
      <div class="user-item">
        <div class="user-avatar ${esc(u.role)}">${initials(u)}</div>
        <div class="user-info">
          <div class="user-name">${esc(u.nom || u.username)}</div>
          <div class="user-meta">${esc(u.username)}</div>
        </div>
        <span class="role-badge ${esc(u.role)}">${esc(roleLabels[u.role] || u.role)}</span>
        <button class="sbtn sbtn-progress" style="margin-left:8px" onclick="editUser(${JSON.stringify(u.username)},${JSON.stringify(u.nom)},${JSON.stringify(u.role)})">✏️ Modifier</button>
        <button class="btn-danger" style="padding:5px 10px" onclick="deleteUser(${JSON.stringify(u.username)})">🗑</button>
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
    const res  = await fetch("/api/users/upsert", {
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
    const res  = await fetch("/api/users/delete", {
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

function init() {
  loadSiteData();
  syncMessages().then(() => refreshDashboard());
  startNewsPoller();
  // Badge initial
  fetch("/api/news", { headers: { "X-Admin-Token": SESSION_TOKEN } })
    .then(r => r.json())
    .then(d => { if(d.ok) setBadge("badge-veille", (d.items||[]).filter(a=>!a.read).length); })
    .catch(()=>{});
}

// ── Synchronisation des messages depuis le serveur ──────────────────────
async function syncMessages() {
  try {
    const res = await fetch("/api/contacts", { headers: { "X-Admin-Token": SESSION_TOKEN } });
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

      // Conserver les entrées locales non encore synchronisées avec le serveur
      localList.filter(m => m._id && !serverIds.has(m._id)).forEach(m => merged.push(m));

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
            : `<span style="font-size:24px">${esc(s.emoji||'🖼️')}</span>`}
        </div>
        <button class="sbtn sbtn-progress" style="font-size:10px;padding:4px 8px" onclick="uploadForSlide(${i})">📷 Photo</button>
      </div>
      <div class="form-group" style="margin:0">
        <label>Titre</label>
        <input type="text" value="${esc(s.title||'')}" placeholder="Titre de la slide"
          oninput="updSlide(${i},'title',this.value)">
        <label style="margin-top:8px">Emoji (si pas de photo)</label>
        <input type="text" value="${esc(s.emoji||'')}" placeholder="🏛️"
          oninput="updSlide(${i},'emoji',this.value)" style="width:80px">
      </div>
      <div class="form-group" style="margin:0">
        <label>Sous-titre</label>
        <textarea oninput="updSlide(${i},'subtitle',this.value)"
          style="min-height:72px">${esc(s.subtitle||'')}</textarea>
      </div>
      <div style="padding-top:22px;display:flex;flex-direction:column;gap:6px">
        <button class="btn-danger" onclick="delSlide(${i})" title="Supprimer">🗑</button>
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
            : `<span style="font-size:32px">${esc(g.emoji||'🖼️')}</span>`}
        </div>
        <input type="text" value="${esc(g.alt||'')}" placeholder="Description"
          oninput="updGrid(${i},'alt',this.value)"
          style="width:100%;font-size:11px;margin-bottom:6px">
        <div style="display:flex;gap:4px;justify-content:center">
          <button class="sbtn sbtn-progress" style="font-size:10px;padding:3px 7px" onclick="uploadForGrid(${i})">📷</button>
          <input type="text" value="${esc(g.emoji||'')}" placeholder="😀"
            oninput="updGrid(${i},'emoji',this.value)"
            style="width:42px;font-size:13px;text-align:center">
          <button class="btn-danger" style="font-size:11px;padding:3px 7px" onclick="delGrid(${i})">🗑</button>
        </div>
      </div>
    `).join("") + `</div>`;
}

// ── Upload d'image ─────────────────────────────────────────────────────────
function uploadImage(callback) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.onchange = async e => {
    const file = e.target.files[0];
    if (!file) return;
    showToast("⏳ Upload en cours…");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        headers: { "X-Admin-Token": SESSION_TOKEN, "X-CSRF-Token": SESSION_CSRF },
        body: formData
      });
      const data = await res.json();
      if (data.ok) { callback(data.path); showToast("Photo uploadée !"); }
      else showToast("Erreur : " + data.message, true);
    } catch { showToast("Serveur non disponible", true); }
  };
  input.click();
}

function uploadForSlide(i) {
  uploadImage(path => {
    if (!siteData.gallery) siteData.gallery = { slides: [], grid: [] };
    siteData.gallery.slides[i].image = path;
    renderSlides();
  });
}

function uploadForGrid(i) {
  uploadImage(path => {
    if (!siteData.gallery) siteData.gallery = { slides: [], grid: [] };
    siteData.gallery.grid[i].image = path;
    renderGrid();
  });
}

function uploadFeaturedImage() {
  uploadImage(path => {
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
  showToast("Slide supprimée");
}
function addSlide() {
  if (!siteData.gallery) siteData.gallery = { slides: [], grid: [] };
  siteData.gallery.slides.push({ image: "", emoji: "🖼️", title: "", subtitle: "" });
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
  showToast("Photo supprimée");
}
function addGridPhoto() {
  if (!siteData.gallery) siteData.gallery = { slides: [], grid: [] };
  siteData.gallery.grid.push({ image: "", alt: "", emoji: "🖼️" });
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
        <button class="btn-danger" onclick="delActuSlide(${i})" title="Supprimer">🗑</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div class="form-group" style="margin:0"><label>Image</label><div style="display:flex;gap:6px;align-items:center"><input type="text" id="actu-slide-img-${i}" value="${esc(s.image||'')}" placeholder="images/photo.jpg" oninput="updActuSlide(${i},'image',this.value)" style="flex:1"><button class="sbtn sbtn-progress" style="font-size:10px;padding:4px 8px;white-space:nowrap" onclick="uploadForActuSlide(${i})">📷 Upload</button></div></div>
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
  uploadImage(path => {
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
  siteData.actus.slides.splice(i, 1); renderActuSlides(); showToast("Slide supprimée");
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
        <button class="btn-danger" onclick="delActuVedette(${i})" title="Supprimer">🗑</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div class="form-group" style="margin:0"><label>Image</label><div style="display:flex;gap:6px;align-items:center"><input type="text" id="actu-vedette-img-${i}" value="${esc(v.image||'')}" placeholder="images/photo.jpg" oninput="updActuVedette(${i},'image',this.value)" style="flex:1"><button class="sbtn sbtn-progress" style="font-size:10px;padding:4px 8px;white-space:nowrap" onclick="uploadForActuVedette(${i})">📷 Upload</button></div></div>
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
        <div class="form-group" style="margin:0"><label>Emoji placeholder</label><input type="text" value="${esc(v.placeholderEmoji||'')}" placeholder="🏘️" oninput="updActuVedette(${i},'placeholderEmoji',this.value)" style="max-width:80px"></div>
        <div class="form-group" style="margin:0"><label>Titre placeholder (\\n = saut)</label><input type="text" value="${esc(v.placeholderTitle||'')}" oninput="updActuVedette(${i},'placeholderTitle',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Date placeholder</label><input type="text" value="${esc(v.placeholderDate||'')}" oninput="updActuVedette(${i},'placeholderDate',this.value)"></div>
        <div class="form-group" style="margin:0"><label>Fond placeholder (CSS)</label><input type="text" value="${esc(v.imageBg||'')}" placeholder="linear-gradient(…)" oninput="updActuVedette(${i},'imageBg',this.value)"></div>
      </div>
    </div>`).join('');
}
function updActuVedette(i, f, v) { if (siteData.actus.vedettes[i]) siteData.actus.vedettes[i][f] = v; }
function uploadForActuVedette(i) {
  uploadImage(path => {
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
  siteData.actus.vedettes.splice(i, 1); renderActuVedettes(); showToast("Article supprimé");
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
        <button class="btn-danger" onclick="delActuCard(${i})" title="Supprimer">🗑</button>
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
  siteData.actus.cards.splice(i, 1); renderActuCards(); showToast("Carte supprimée");
}

function collectActus() {
  // Tout est déjà mis à jour en temps réel via oninput
}

// ══════════════════════════════════════════════════════════════════════════
//  CONTENU DU SITE (data.json via server.py)
// ══════════════════════════════════════════════════════════════════════════
function loadSiteData() {
  fetch("/api/load")
    .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(applyData)
    .catch(() => {
      // Fallback : lecture directe de data.json (sans serveur)
      fetch("data.json?t=" + Date.now())
        .then(r => r.json())
        .then(applyData)
        .catch(() => showToast("⚠️ Impossible de charger les données", true));
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

function saveData() {
  collectForm();
  collectActus();
  collectProgramme();
  fetch("/api/save", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(siteData)
  })
  .then(r => r.json())
  .then(res => showToast(res.ok ? "Contenu sauvegardé !" : res.message, !res.ok))
  .catch(() => showToast("Serveur non disponible (mode GitHub Pages)", true));
}

// ══════════════════════════════════════════════════════════════════════════
//  DASHBOARD
// ══════════════════════════════════════════════════════════════════════════
function refreshDashboard() {
  const aud  = getAll("bininga_audiences");
  const ct   = getAll("bininga_contacts");
  const prog = parseInt(localStorage.getItem("bininga_prog_views") || "0");
  const vis  = parseInt(localStorage.getItem("bininga_visitors")   || "0");

  // Séparer audiences normales et réclamations
  const audiences    = aud.filter(m => m.objet !== "Réclamation");
  const reclamations = aud.filter(m => m.objet === "Réclamation");

  const wait     = audiences.filter(m => !m._status || m._status === "en_attente").length;
  const inprog   = audiences.filter(m => m._status === "en_cours").length;
  const done     = audiences.filter(m => m._status === "traite").length;
  const reclWait = reclamations.filter(m => !m._status || m._status !== "traite").length;
  const ctUnread = ct.filter(m => !m._status || m._status === "non_lu").length;

  setText("kpi-aud-total",    audiences.length);
  setText("kpi-aud-wait",     wait);
  setText("kpi-aud-progress", inprog);
  setText("kpi-aud-done",     done);
  setText("kpi-recl",         reclWait);
  setText("kpi-ct",           ct.length);
  setText("kpi-prog",         prog);
  setText("kpi-visit",        vis);

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
    const raisonHtml = m.raison ? `<div class="sinistre-desc"><span>📝 Requête</span>${esc(m.raison)}</div>` : "";

    // Description sinistre
    const descHtml = m.description ? `<div class="sinistre-desc"><span>📝 Description</span>${esc(m.description)}</div>` : "";

    // Bloc géolocalisation
    let geoHtml = "";
    if (m.geo_lat && m.geo_lng) {
      const lat = parseFloat(m.geo_lat), lng = parseFloat(m.geo_lng);
      const δ = 0.008;
      const mapsUrl = m.geo_maps_url || `https://www.google.com/maps?q=${lat},${lng}&z=16`;
      geoHtml = `<div class="sinistre-geo">
        <div class="sinistre-geo-header">
          <span class="sinistre-geo-label">📍 Zone du sinistre</span>
          <a href="${esc(mapsUrl)}" target="_blank" class="btn-maps">🗺️ Ouvrir Google Maps</a>
        </div>
        ${m.geo_label ? `<div class="sinistre-addr">${esc(m.geo_label)}</div>` : ""}
        <iframe class="sinistre-map"
          src="https://www.openstreetmap.org/export/embed.html?bbox=${lng-δ},${lat-δ},${lng+δ},${lat+δ}&layer=mapnik&marker=${lat},${lng}"
          allowfullscreen loading="lazy"></iframe>
        <div class="sinistre-coords">🌐 ${Number(lat).toFixed(6)}, ${Number(lng).toFixed(6)}</div>
      </div>`;
    }

    // Photo sinistre
    const photoHtml = m.photo_url ? `<div class="sinistre-photo-wrap">
      <div class="sinistre-photo-label">📷 Photo du sinistre</div>
      <img src="${esc(m.photo_url)}" class="sinistre-photo" onclick="this.classList.toggle('full')" title="Cliquer pour agrandir">
    </div>` : "";

    // Bouton Répondre (uniquement si email disponible)
    const replyBtn = m.email
      ? `<a class="sbtn sbtn-progress" href="mailto:${encodeURIComponent(m.email)}?subject=${encodeURIComponent('Réponse — Cabinet Aimé BININGA')}&body=${encodeURIComponent('Bonjour ' + (m.prenom||'') + ' ' + (m.nom||'') + ',\n\n')}" style="text-decoration:none">📧 Répondre</a>`
      : (m.telephone ? `<span class="sbtn" style="background:rgba(46,204,113,.08);color:#2ecc71;border:1px solid rgba(46,204,113,.2);cursor:default">📞 ${esc(m.telephone)}</span>` : "");

    // Identifiant HTML-safe pour les boutons
    const btnId = msgKey ? encodeURIComponent(msgKey) : String(realIdx);
    // Bouton ping Député (visible sur tous les messages)
    const pingBtn  = m._pinged
      ? `<span class="sbtn" style="background:rgba(231,76,60,.1);color:#e74c3c;border:1px solid rgba(231,76,60,.2);cursor:default">🚨 Député alerté</span>`
      : `<button class="sbtn" style="background:rgba(231,76,60,.1);color:#e74c3c;border:1px solid rgba(231,76,60,.2)" onclick="pingDepute('${storageKey}','${btnId}')">🚨 Alerter le Député</button>`;
    let actions = "";
    if (mode === "status3") {
      actions = `
        <button class="sbtn sbtn-wait"     onclick="setStatus('${storageKey}','${btnId}','en_attente')">⏳ En attente</button>
        <button class="sbtn sbtn-progress" onclick="setStatus('${storageKey}','${btnId}','en_cours')">🔄 En cours</button>
        <button class="sbtn sbtn-done"     onclick="setStatus('${storageKey}','${btnId}','traite')">✅ Traité</button>
        ${replyBtn}
        ${pingBtn}
      `;
    } else {
      actions = `<button class="sbtn sbtn-read" onclick="setStatus('${storageKey}','${btnId}','lu')">✅ Marquer comme lu</button>${replyBtn}${pingBtn}`;
    }

    const hasSinistre = !!(m.geo_lat || m.photo_url || m.description);
    const pingBadge   = m._pinged ? `<span class="badge badge-pinged">🚨 Député alerté</span>` : "";

    return `<div class="msg-item${hasSinistre ? " msg-sinistre" : ""}">
      <div class="msg-top">
        <div>
          <div class="msg-name">${esc(m.prenom||"")} ${esc(m.nom||"")}</div>
          <div class="msg-date">📅 ${esc(m._date||m.ts||"")}${hasSinistre ? ' <span class="sinistre-chip">📍 Géolocalisé</span>' : ""}</div>
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
  if (objet === "Réclamation") return `<span class="badge badge-recl">⚠️ Réclamation</span>`;
  const map = {
    en_attente: `<span class="badge badge-wait">⏳ En attente</span>`,
    en_cours:   `<span class="badge badge-progress">🔄 En cours</span>`,
    traite:     `<span class="badge badge-done">✅ Traité</span>`,
    non_lu:     `<span class="badge badge-unread">🔵 Non lu</span>`,
    lu:         `<span class="badge badge-read">✓ Lu</span>`,
  };
  return map[status] || map.en_attente;
}

function setStatus(storageKey, idOrIdx, status) {
  const all = getAll(storageKey);
  // idOrIdx peut être un _id encodé (string) ou un index numérique (legacy)
  let idx = -1;
  const decoded = decodeURIComponent(String(idOrIdx));
  // Si ça ressemble à un _id (contient "-"), chercher par _id
  if (decoded.includes("-")) {
    idx = all.findIndex(x => x._id === decoded);
  }
  // Fallback : index numérique
  if (idx === -1) {
    const n = parseInt(idOrIdx, 10);
    if (!isNaN(n) && all[n]) idx = n;
  }
  if (idx !== -1) {
    all[idx]._status = status;
    saveAll(storageKey, all);
  }
  refreshDashboard();
  if (storageKey === "bininga_audiences") {
    renderAudiences();
    renderReclamations();
  } else {
    renderContacts();
  }
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
      <div class="notes-title">💬 Notes internes (admin ↔ ministre)</div>
      ${notesHtml || '<div style="font-size:11px;color:rgba(255,255,255,.2);margin-bottom:6px">Aucune note pour l\'instant</div>'}
      <div class="note-form">
        <textarea id="note-ta-${btnId}" placeholder="Ajouter une note interne…" rows="2"></textarea>
        <button onclick="addNote('${storageKey}','${btnId}')">💬 Ajouter</button>
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
  all[idx]._notes.push({ auteur: "Admin", texte, date: new Date().toLocaleString("fr-FR") });
  saveAll(storageKey, all);
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
  refreshDashboard();
  if (storageKey === "bininga_audiences") { renderAudiences(); renderReclamations(); }
  else renderContacts();
  showToast("🚨 Le Député a été alerté sur ce dossier !");
}

// ══════════════════════════════════════════════════════════════════════════
//  SÉCURITÉ — Anti-Intrusion
// ══════════════════════════════════════════════════════════════════════════
const ATTACK_LABELS = {
  SQL_INJECTION:       "💉 SQL Injection",
  CMD_INJECTION:       "💀 Cmd Injection",
  XSS_ATTEMPT:         "🕸️ XSS",
  PATH_TRAVERSAL_DEEP: "📁 Path Traversal",
  SCANNER_UA:          "🤖 Scanner",
  FILE_READ_ATTEMPT:   "🔍 Lecture fichier",
  HONEYPOT:            "🪤 Honeypot",
  HONEYPOT_POST:       "🪤 Honeypot POST",
  LOGIN_FAIL:          "🔑 Échec login",
  RATE_ABUSE:          "🌊 Rate Abuse",
  AUTO_BAN:            "🚫 Ban auto",
  MANUAL_BAN:          "🚫 Ban manuel",
  OVERSIZED_REQUEST:   "📦 Trop grand",
};

async function loadSecurity() {
  const listBlocked  = document.getElementById("sec-blocked-list");
  const listSuspects = document.getElementById("sec-suspects-list");
  const listAttacks  = document.getElementById("sec-attacks-list");
  [listBlocked, listSuspects, listAttacks].forEach(e => {
    e.innerHTML = '<div class="msg-empty">Chargement…</div>';
  });

  try {
    const res  = await fetch("/api/security", { headers: { "X-Admin-Token": SESSION_TOKEN } });
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
      listBlocked.innerHTML = '<div class="msg-empty">Aucune IP bloquée ✅</div>';
    } else {
      listBlocked.innerHTML = data.blocked.map(ip => `
        <div class="ip-row">
          <span class="ip-addr">🚫 ${esc(ip)}</span>
          <span class="ip-score danger">BANNI</span>
          <button class="sbtn sbtn-done" style="font-size:10px;padding:3px 8px"
            onclick="unblockIp('${esc(ip)}')">Débloquer</button>
        </div>
      `).join("");
    }

    // IPs suspectes (non bannis)
    const suspects = data.suspects.filter(s => !data.blocked.includes(s.ip));
    if (!suspects.length) {
      listSuspects.innerHTML = '<div class="msg-empty">Aucune IP suspecte ✅</div>';
    } else {
      listSuspects.innerHTML = suspects.slice(0,20).map(s => {
        const pct   = Math.min(100, Math.round(s.score / 25 * 100));
        const cls   = s.score >= 20 ? "danger" : s.score >= 10 ? "warn" : "info";
        const color = s.score >= 20 ? "#e74c3c" : s.score >= 10 ? "#f39c12" : "#3498db";
        return `<div class="ip-row" style="flex-direction:column;align-items:stretch;gap:4px">
          <div style="display:flex;align-items:center;gap:8px">
            <span class="ip-addr">⚠️ ${esc(s.ip)}</span>
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
      listAttacks.innerHTML = '<div class="msg-empty">Aucune attaque enregistrée ✅</div>';
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
    const res  = await fetch("/api/security/unblock", {
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
    const res  = await fetch("/api/security/block", {
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
    const res  = await fetch("/api/news", { headers: { "X-Admin-Token": SESSION_TOKEN } });
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
  if (btn) { btn.disabled = true; btn.textContent = "⏳ En cours…"; }
  try {
    const res  = await fetch("/api/news/run", {
      method: "POST",
      headers: { "X-Admin-Token": SESSION_TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    if (fb) {
      fb.style.display = "block";
      fb.style.color   = data.ok ? "#2ecc71" : "#ff6b6b";
      fb.textContent   = data.ok ? "✅ " + data.message + " — résultats dans ~30 secondes" : "❌ " + data.message;
      setTimeout(() => { if (fb) fb.style.display = "none"; }, 8000);
    }
    if (data.ok) setTimeout(loadNews, 10000);
  } catch(e) {
    if (fb) { fb.style.display = "block"; fb.style.color = "#ff6b6b"; fb.textContent = "❌ Erreur réseau"; }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "⚡ Lancer maintenant"; }
  }
}

const CAT_LABELS = {
  bininga:     { label: "Bininga",      color: "rgba(200,16,46,.8)",    bg: "rgba(200,16,46,.12)" },
  loi_justice: { label: "⚖️ Lois & Justice", color: "rgba(46,204,113,.9)", bg: "rgba(46,204,113,.1)" },
  recherche:   { label: "🔍 Recherche", color: "rgba(52,152,219,.9)",   bg: "rgba(52,152,219,.1)" },
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
    ? _newsItems.filter(a => (a.category || "bininga") !== "bininga")
    : _newsItems.filter(a => (a.category || "bininga") === _newsFilter);

  // Mise à jour compteurs onglets
  const bCount = _newsItems.filter(a => (a.category || "bininga") === "bininga").length;
  const aCount = _newsItems.filter(a => (a.category || "bininga") !== "bininga").length;
  const bUnread = _newsItems.filter(a => (a.category || "bininga") === "bininga" && !a.read).length;
  const aUnread = _newsItems.filter(a => (a.category || "bininga") !== "bininga" && !a.read).length;
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
      ? `<span style="padding:1px 6px;border-radius:8px;font-size:10px;background:rgba(66,103,178,.15);color:#4267b2;font-weight:700">📘 Facebook</span>`
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
          <a href="${esc(a.url)}" target="_blank" rel="noopener" style="padding:4px 10px;border-radius:5px;font-size:11px;font-weight:600;background:rgba(52,152,219,.1);color:#3498db;border:1px solid rgba(52,152,219,.2);text-decoration:none;white-space:nowrap">🔗 Lire</a>
          ${!isRead?`<button onclick="markNewsRead('${esc(a.id)}')" style="padding:4px 10px;border-radius:5px;font-size:11px;font-weight:600;background:rgba(46,204,113,.08);color:#2ecc71;border:1px solid rgba(46,204,113,.2);cursor:pointer;white-space:nowrap">✓ Lu</button>`:""}
          <button onclick="deleteNewsItem('${esc(a.id)}')" style="padding:4px 10px;border-radius:5px;font-size:11px;font-weight:600;background:rgba(200,16,46,.08);color:#ff6b6b;border:1px solid rgba(200,16,46,.2);cursor:pointer;white-space:nowrap">🗑</button>
        </div>
      </div>
    </div>`;
  }).join("");
}

async function markNewsRead(id) {
  try {
    await fetch("/api/news/mark-read", {
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
    await fetch("/api/news/mark-read", {
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
    await fetch("/api/news/delete", {
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
    fetch("/api/news", { headers: { "X-Admin-Token": SESSION_TOKEN } })
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
    const res = await fetch("/api/logs", {
      headers: { "X-Admin-Token": SESSION_TOKEN }
    });
    const data = await res.json();
    if (!data.ok) { el.innerHTML = '<div class="msg-empty">Erreur de chargement.</div>'; return; }
    if (!data.logs.length) { el.innerHTML = '<div class="msg-empty">Aucune entrée pour le moment.</div>'; return; }

    const icons  = { LOGIN_OK:"🔓", LOGIN_FAIL:"⛔", SAVE:"💾", UPLOAD:"📷", USER_UPSERT:"👤", USER_DELETE:"🗑️" };
    const labels = { LOGIN_OK:"Connexion réussie", LOGIN_FAIL:"Tentative échouée", SAVE:"Sauvegarde", UPLOAD:"Upload image", USER_UPSERT:"Utilisateur créé / modifié", USER_DELETE:"Utilisateur supprimé" };
    const cls    = { LOGIN_OK:"ok", LOGIN_FAIL:"fail", SAVE:"save", UPLOAD:"upload", USER_UPSERT:"ok", USER_DELETE:"fail" };

    el.innerHTML = data.logs.map(log => `
      <div class="log-item">
        <div class="log-icon">${icons[log.action] || "📋"}</div>
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

// ══════════════════════════════════════════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════════════════════════════════════════
const PANEL_TITLES = {
  dashboard:"Tableau de bord", audiences:"Demandes d'audience",
  reclamations:"Réclamations", contacts:"Messages de contact",
  hero:"Section Hero", about:"À propos", stats:"Statistiques", galerie:"Galerie photos",
  actus:"Actualités", parcours:"Parcours — Timeline", programme:"Programme 2027–2032", seo:"SEO",
  logs:"Journaux d'audit", users:"Gestion des utilisateurs", security:"🛡️ Sécurité — Anti-Intrusion",
  veille:"🤖 YARO IA — Actualités Bininga"
};

function showPanel(name, el) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".sb-item").forEach(i => i.classList.remove("active"));
  document.getElementById("panel-"+name).classList.add("active");
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
  if (name === "logs")         loadAuditLogs();
  if (name === "users")        loadUsers();
  if (name === "security")     loadSecurity();
  if (name === "veille")       loadNews();
}

// ══════════════════════════════════════════════════════════════════════════
//  UTILITAIRES
// ══════════════════════════════════════════════════════════════════════════
function getAll(key)       { return JSON.parse(localStorage.getItem(key)||"[]"); }
function saveAll(key, arr) { localStorage.setItem(key, JSON.stringify(arr)); }
function setText(id, val)  { const el=document.getElementById(id); if(el) el.textContent=val; }
function setBadge(id, n)   { const el=document.getElementById(id); if(!el)return; el.style.display=n>0?"inline":"none"; el.textContent=n; }
function esc(s)            { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

async function clearAll(storageKey, panel) {
  if (!confirm("Êtes-vous sûr de vouloir supprimer tous les messages ? Cette action est irréversible.")) return;
  // Suppression côté serveur
  try {
    await fetch("/api/contacts/clear", {
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
        <input type="text" value="${esc(p.emoji||'')}" placeholder="📚" oninput="updParcours(${i},'emoji',this.value)" style="width:60px;text-align:center;font-size:18px">
      </div>
      <div class="form-group" style="margin:0">
        <label>Année / Période</label>
        <input type="text" value="${esc(p.year||'')}" placeholder="2016" oninput="updParcours(${i},'year',this.value)">
        <label style="margin-top:8px">Tag</label>
        <input type="text" value="${esc(p.tag||'')}" placeholder="🏛️ Ministre" oninput="updParcours(${i},'tag',this.value)" style="font-size:12px">
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
        <button class="btn-danger" onclick="delParcoursItem(${i})" title="Supprimer">🗑</button>
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
  siteData.parcours.push({ side, emoji: "📌", year: "", title: "", desc: "", tag: "" });
  renderParcours();
}
function delParcoursItem(i) {
  if (!confirm("Supprimer cette étape du parcours ?")) return;
  siteData.parcours.splice(i, 1);
  renderParcours();
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
          <input type="text" value="${esc(ax.icon||'')}" placeholder="⚖️" oninput="updAxe(${i},'icon',this.value)" style="width:50px;text-align:center;font-size:20px">
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
          <button class="btn-danger" onclick="delAxe(${i})" title="Supprimer">🗑</button>
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
  siteData.programme.axes.push({ icon: "📌", title: "", text: "", points: [] });
  renderAxes();
}
function delAxe(i) {
  if (!confirm("Supprimer cet axe ?")) return;
  siteData.programme.axes.splice(i, 1);
  renderAxes();
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
  setTimeout(() => t.className = "", 3500);
}

function toggleSidebar() {
  const sb = document.getElementById("sidebar");
  const btn = document.getElementById("hamburger");
  const ov = document.getElementById("sidebar-overlay");
  const open = sb.classList.toggle("open");
  btn.classList.toggle("open", open);
  btn.setAttribute("aria-expanded", open);
  ov.classList.toggle("open", open);
  document.body.style.overflow = open ? "hidden" : "";
}
function closeSidebar() {
  const sb = document.getElementById("sidebar");
  const btn = document.getElementById("hamburger");
  const ov = document.getElementById("sidebar-overlay");
  sb.classList.remove("open");
  btn.classList.remove("open");
  btn.setAttribute("aria-expanded", "false");
  ov.classList.remove("open");
  document.body.style.overflow = "";
}

// ── Hamburger menu mobile ──────────────────────────────────────────────────
function toggleSidebar() {
  const sb  = document.getElementById("sidebar");
  const btn = document.getElementById("hamburger");
  const ov  = document.getElementById("sidebar-overlay");
  if (!sb) return;
  const open = sb.classList.toggle("open");
  if (btn) { btn.classList.toggle("open", open); btn.setAttribute("aria-expanded", open); }
  if (ov)  ov.classList.toggle("open", open);
  document.body.style.overflow = open ? "hidden" : "";
}
function closeSidebar() {
  const sb  = document.getElementById("sidebar");
  const btn = document.getElementById("hamburger");
  const ov  = document.getElementById("sidebar-overlay");
  if (sb)  sb.classList.remove("open");
  if (btn) { btn.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
  if (ov)  ov.classList.remove("open");
  document.body.style.overflow = "";
}
