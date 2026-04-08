
const IMG = "images/bininga.jpg";
function escHtml(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

/**
 * sanitizeHtml — Autorise UNIQUEMENT les balises sûres de mise en forme.
 * Tout le reste est échappé. Protège contre les injections XSS dans innerHTML.
 * Tags autorisés : <em> <strong> <br> <span class="..."> (pas d'attribut href/on*)
 */
function sanitizeHtml(s) {
  if (!s) return "";
  // Échapper tout d'abord
  let safe = String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
  // Ré-autoriser uniquement les balises whitelistées (inoffensives)
  safe = safe
    .replace(/&lt;em&gt;/g, "<em>").replace(/&lt;\/em&gt;/g, "</em>")
    .replace(/&lt;strong&gt;/g, "<strong>").replace(/&lt;\/strong&gt;/g, "</strong>")
    .replace(/&lt;br\s*\/?&gt;/g, "<br>")
    .replace(/&lt;span class=&quot;([a-zA-Z0-9_ -]{1,30})&quot;&gt;/g,
             (_, cls) => `<span class="${cls}">`)
    .replace(/&lt;\/span&gt;/g, "</span>");
  return safe;
}

/**
 * safeCta — Valide un href : n'accepte que les URL relatives ou https://.
 * Bloque javascript:, data:, vbscript: etc.
 */
function safeCta(href) {
  if (!href) return null;
  const h = String(href).trim();
  if (/^(https?:\/\/|\/|#|mailto:)/i.test(h)) return h;
  return null; // bloque javascript:, data:, etc.
}

// ── CHARGEMENT DU CONTENU DEPUIS data.json (synchronisé avec l'admin) ─────
function loadContent() {
  fetch("data.json?t=" + Date.now())
    .then(r => r.json())
    .then(d => {
      window._FR_DATA = d; // sauvegarde pour les re-rendus i18n
      const h = d.hero || {};
      const a = d.about || {};

      // Hero — Nom
      const nameEl = document.getElementById("dyn-name");
      if (nameEl && (h.firstName || h.lastName)) {
        nameEl.innerHTML = escHtml(h.firstName || '') + '\n<span>' + escHtml(h.lastName || '') + '</span>';
      }
      // Hero — Rôle
      const roleEl = document.getElementById("dyn-role");
      if (roleEl && h.role) roleEl.textContent = h.role;

      // Hero — Slogan (innerHTML pour supporter les balises em)
      const sloganEl = document.getElementById("dyn-slogan");
      if (sloganEl && h.slogan) sloganEl.innerHTML = sanitizeHtml(h.slogan);

      // Hero — Sous-titre
      const subEl = document.getElementById("dyn-sub");
      if (subEl && h.subtitle) subEl.textContent = h.subtitle;

      // À propos — Titre
      const aboutTitleEl = document.getElementById("dyn-about-title");
      if (aboutTitleEl && a.title) aboutTitleEl.innerHTML = sanitizeHtml(a.title);

      // À propos — Introduction
      const aboutIntroEl = document.getElementById("dyn-about-intro");
      if (aboutIntroEl && a.intro) aboutIntroEl.textContent = a.intro;

      // À propos — Paragraphes biographie
      const aboutBodyEl = document.getElementById("dyn-about-body");
      if (aboutBodyEl && Array.isArray(a.paragraphs) && a.paragraphs.length) {
        aboutBodyEl.innerHTML = a.paragraphs
          .map(p => `<p class="about-body">${p.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}</p>`)
          .join("");
      }

      // À propos — Badges (pills)
      const aboutPillsEl = document.getElementById("dyn-about-pills");
      if (aboutPillsEl && Array.isArray(a.badges) && a.badges.length) {
        aboutPillsEl.innerHTML = a.badges
          .map(b => `<span class="pill">${b.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}</span>`)
          .join("");
      }

      // Contact — informations dynamiques
      const ct = d.contact || {};
      const phoneEl = document.getElementById("dyn-phone");
      if (phoneEl && ct.phone) phoneEl.textContent = ct.phone;

      // Statistiques (hero strip)
      const stats = d.stats || [];
      [0, 1, 2].forEach(i => {
        const s = stats[i];
        if (!s) return;
        const numEl = document.getElementById("dyn-s" + i);
        const lblEl = document.getElementById("dyn-s" + i + "-lbl");
        if (numEl) {
          const n = parseInt(s.num);
          if (!isNaN(n)) {
            numEl.dataset.c = n;
            numEl.textContent = "0";
            // Relancer l'animation compteur avec la nouvelle valeur
            setTimeout(() => aCount(numEl), 100);
          } else {
            // Valeur non-numérique (ex: "50+", "1re") : afficher directement
            delete numEl.dataset.c;
            numEl.textContent = s.num;
          }
        }
        if (lblEl) lblEl.textContent = s.label;
      });

      // Ticker mobile — dupliquer les items pour une boucle sans fin
      if (window.innerWidth <= 768) {
        const track = document.getElementById('stat-ticker-track');
        if (track) {
          const origItems = Array.from(track.querySelectorAll('.hstat'));
          origItems.forEach(item => {
            const clone = item.cloneNode(true);
            // Supprimer les IDs du clone pour éviter les doublons
            clone.querySelectorAll('[id]').forEach(el => el.removeAttribute('id'));
            // Afficher la valeur finale dans le clone (data-c ou textContent déjà défini)
            const numEl = clone.querySelector('.hstat-num');
            if (numEl && numEl.dataset.c) numEl.textContent = numEl.dataset.c;
            track.appendChild(clone);
          });
        }
      }

      // Parcours — en-tête de section
      const pSec = d.parcoursSection || {};
      const pTagEl    = document.getElementById("dyn-parcours-tag");
      const pTitleEl  = document.getElementById("dyn-parcours-title");
      const pAccentEl = document.getElementById("dyn-parcours-accent");
      if (pTagEl    && pSec.tag)         pTagEl.textContent    = pSec.tag;
      if (pAccentEl && pSec.titleAccent) pAccentEl.textContent = pSec.titleAccent;
      if (pTitleEl  && pSec.title) {
        pTitleEl.childNodes[0].textContent = pSec.title + " ";
      }

      // Parcours (timeline)
      const PARCOURS_DEFAULT = [
        { side:"left",  emoji:"📚", year:"Formation",        title:"Doctorat en droit & Inspecteur principal du Trésor",                                tag:"📚 Juriste",                            desc:"Docteur en droit, Ange Aimé Wilfrid BININGA bâtit une carrière de cadre supérieur de l'État au sein de la Direction générale du Trésor public, avant de rejoindre celle de la Santé comme conseiller stratégique du ministre." },
        { side:"right", emoji:"🌱", year:"Engagement politique", title:"Adhésion au PCT & premières actions",                                          tag:"🔴 PCT",                                desc:"Militant du Parti Congolais du Travail, il s'engage activement dans la vie politique d'Ewo et de la Cuvette-Ouest, portant les aspirations de sa communauté." },
        { side:"left",  emoji:"👷", year:"2016",               title:"Ministre de la Fonction publique et de la Réforme de l'État",                    tag:"🏛️ Ministère de la Fonction publique",  desc:"Nommé par le Président de la République au sein du premier gouvernement de la nouvelle République, il porte la modernisation de l'administration publique et l'emploi des jeunes, piliers de la diversification économique nationale." },
        { side:"right", emoji:"🗳️", year:"19 août 2017",      title:"Élu Député de la 1re circonscription d'Ewo",                                    tag:"🗳️ Assemblée Nationale",               desc:"Il est élu Député de la 1re circonscription électorale d'Ewo (département de la Cuvette-Ouest) le 19 août 2017, représentant sa communauté à l'Assemblée Nationale de la République du Congo." },
        { side:"left",  emoji:"📈", year:"2018",               title:"Ministre de la Justice & Haute Autorité anti-corruption",                        tag:"📈 Confiance renouvelée",               desc:"En tant que Ministre de la Justice, il pilote l'adoption par 107 députés de la loi créant la Haute Autorité de lutte contre la corruption (2018), institution indépendante dotée du droit de saisine directe des instances judiciaires." },
        { side:"right", emoji:"⚖️", year:"Aujourd'hui",        title:"Garde des Sceaux, Ministre de la Justice, des Droits Humains et de la Promotion des Peuples Autochtones", tag:"⚖️ Ministère de la Justice", desc:"À ce poste clé du gouvernement, il incarne la diplomatie judiciaire du Congo, notamment avec la renégociation en février 2026 à Paris de la convention de coopération judiciaire Congo-France — accord vieux de plus de 50 ans, renouvelé sur de nouvelles bases modernes." },
        { side:"left",  emoji:"🚀", year:"Législatives 2027",  title:"Candidat pour Ewo · Campagne 2027",                                             tag:"🚀 Campagne en cours",                  desc:"Plus motivé que jamais, fort de son expérience gouvernementale, il se présente aux prochaines élections législatives avec un programme ambitieux pour Ewo et le Congo." }
      ];
      const parcours = (d.parcours && d.parcours.length) ? d.parcours : PARCOURS_DEFAULT;
      const parcoursWrap = document.getElementById("dyn-parcours");
      if (parcours && parcoursWrap && parcours.length) {
        const delays = ["d1","d2","d3","d4","d5","d6"];
        parcoursWrap.innerHTML = parcours.map((p, i) => {
          const isLeft = p.side === "left";
          const card = `<div class="tl-card">
            <div class="tl-year">${escHtml(p.year||"")}</div>
            <div class="tl-title">${escHtml(p.title||"")}</div>
            <div class="tl-desc">${escHtml(p.desc||"")}</div>
            <span class="tl-tag">${escHtml(p.tag||"")}</span>
          </div>`;
          const dot  = `<div class="tl-dot">${escHtml(p.emoji||"•")}</div>`;
          const empty = `<div class="tl-empty"></div>`;
          return `<div class="tl-item rev ${delays[i%6]}">
            ${isLeft ? card : empty}
            ${dot}
            ${isLeft ? empty : card}
          </div>`;
        }).join("");
        // Réactiver les animations reveal sur les nouveaux éléments
        parcoursWrap.querySelectorAll(".rev").forEach(el => rObs.observe(el));
        parcoursWrap.querySelectorAll(".tl-item").forEach((el, i) => {
          el.style.transitionDelay = `${i * 0.13}s`;
        });
      }

      // Programme (6 axes)
      const prog = d.programme;
      const progWrap = document.getElementById("dyn-programme");
      if (prog && progWrap) {
        const axes = prog.axes || [];
        const delays2 = ["d1","d2","d3","d1","d2","d3"];
        const heroTitle = (prog.heroTitle || "").replace(/\n/g, "<br>");
        progWrap.innerHTML = `
          <div class="prog-hero rev">
            <div>
              <h3 class="prog-hero-title">${heroTitle}</h3>
              <p class="prog-hero-sub">${escHtml(prog.heroText||"")}</p>
            </div>
            <div class="prog-hero-big">2032</div>
          </div>
          <div class="prog-grid">
            ${axes.map((ax, i) => `
              <div class="prog-card rev ${delays2[i]}">
                <div class="prog-num">${String(i+1).padStart(2,"0")}</div>
                <span class="prog-icon">${escHtml(ax.icon||"")}</span>
                <h3 class="prog-title">${escHtml(ax.title||"")}</h3>
                <p class="prog-txt">${escHtml(ax.text||"")}</p>
                <ul class="prog-pts">
                  ${(ax.points||[]).map(pt => `<li>${escHtml(pt)}</li>`).join("")}
                </ul>
              </div>`).join("")}
          </div>`;
        progWrap.querySelectorAll(".rev").forEach(el => rObs.observe(el));
      }

      // Galerie
      const gal = d.gallery;
      const galWrap = document.getElementById("gal-wrap");
      if (gal && galWrap) {
        const slides = gal.slides || [];
        const grid   = gal.grid   || [];

        const slidesHtml = slides.map(s => `
          <div class="gal-slide">
            ${s.image
              ? `<img src="${escHtml(s.image)}" alt="${escHtml(s.title||'')}" loading="lazy">`
              : `<div class="gal-slide-placeholder"><div style="font-size:50px">${escHtml(s.emoji||'🖼️')}</div></div>`}
            <div class="gal-cap">
              <h3>${escHtml(s.title||'')}</h3>
              <p>${escHtml(s.subtitle||'')}</p>
            </div>
          </div>`).join("");

        const dotsHtml = slides.map((_, i) =>
          `<button class="gal-dot${i===0?' a':''}" onclick="gGo(${i})"></button>`
        ).join("");

        // data-src et data-alt pour la lightbox, onclick géré en JS après injection
        const gridHtml = grid.map((g, i) =>
          `<div class="gi" data-gi="${i}">${g.image
            ? `<img src="${escHtml(g.image)}" alt="${escHtml(g.alt||'')}" loading="lazy">`
            : `<div class="gi-ph">${escHtml(g.emoji||'🖼️')}</div>`
          }<div class="gi-ov">🔍</div></div>`
        ).join("");

        galWrap.innerHTML = `
          <div class="gal-slider">
            <div class="gal-track" id="galTrack">${slidesHtml}</div>
            <button class="gal-btn p" onclick="gSlide(-1)">‹</button>
            <button class="gal-btn n" onclick="gSlide(1)">›</button>
            <div class="gal-dots" id="galDots">${dotsHtml}</div>
          </div>
          <div class="gal-grid">${gridHtml}</div>`;

        // Attacher la lightbox sur chaque item de la grille
        galWrap.querySelectorAll(".gi").forEach((el, i) => {
          const src = (grid[i] && grid[i].image) ? grid[i].image : null;
          const alt = (grid[i] && grid[i].alt)   ? grid[i].alt   : "";
          if (src) el.addEventListener("click", () => openLightbox(src, alt));
        });

        // Réinitialiser le slider
        initSlider();
      }

      // SEO
      if (d.seo) {
        if (d.seo.title) document.title = d.seo.title;
        const metaDesc = document.querySelector("meta[name=description]");
        if (metaDesc && d.seo.description) metaDesc.content = d.seo.description;
      }

      // ── Hero — éléments supplémentaires ──────────────────────────────
      if (h.eyebrow) { const el=document.getElementById("dyn-hero-eyebrow"); if(el) el.textContent=h.eyebrow; }
      if (h.btn1)    { const el=document.getElementById("dyn-hero-btn1");    if(el) el.textContent=h.btn1; }
      if (h.btn2)    { const el=document.getElementById("dyn-hero-btn2");    if(el) el.textContent=h.btn2; }

      // ── À propos — tag + badge ────────────────────────────────────────
      if (a.sectionTag) { const el=document.getElementById("dyn-about-tag");       if(el) el.textContent=a.sectionTag; }
      if (a.badgeNum)   { const el=document.getElementById("dyn-about-badge-num"); if(el) el.textContent=a.badgeNum; }
      if (a.badgeLbl)   { const el=document.getElementById("dyn-about-badge-lbl"); if(el) el.textContent=a.badgeLbl; }

      // ── Programme — en-tête de section ───────────────────────────────
      const ps = d.programmeSection || {};
      if (ps.tag)    { const el=document.getElementById("dyn-prog-tag");    if(el) el.textContent=ps.tag; }
      if (ps.titleAccent) { const el=document.getElementById("dyn-prog-accent"); if(el) el.textContent=ps.titleAccent; }
      if (ps.title)  {
        const el=document.getElementById("dyn-prog-title");
        if(el) el.childNodes[0].textContent=ps.title+" ";
      }
      if (ps.subtitle) { const el=document.getElementById("dyn-prog-sub"); if(el) el.textContent=ps.subtitle; }

      // ── Galerie — en-tête de section ─────────────────────────────────
      const gs = d.galerieSection || {};
      if (gs.tag)         { const el=document.getElementById("dyn-gal-tag");    if(el) el.textContent=gs.tag; }
      if (gs.titleAccent) { const el=document.getElementById("dyn-gal-accent"); if(el) el.textContent=gs.titleAccent; }
      if (gs.title)       {
        const el=document.getElementById("dyn-gal-title");
        if(el) el.childNodes[0].textContent=gs.title+" ";
      }

      // ── Actualités — en-tête de section + titre grille ───────────────
      const as_ = d.actusSection || {};
      if (as_.tag)         { const el=document.getElementById("dyn-actu-tag");        if(el) el.textContent=as_.tag; }
      if (as_.titleAccent) { const el=document.getElementById("dyn-actu-accent");     if(el) el.textContent=as_.titleAccent; }
      if (as_.gridTitle)   { const el=document.getElementById("dyn-actu-grid-title"); if(el) el.textContent=as_.gridTitle; }
      if (as_.title)       {
        const el=document.getElementById("dyn-actu-title");
        if(el) el.childNodes[0].textContent=as_.title+" ";
      }

      // ── Engagement ───────────────────────────────────────────────────
      const eng = d.engagement || {};
      if (eng.tag)         { const el=document.getElementById("dyn-eng-tag");          if(el) el.textContent=eng.tag; }
      if (eng.titleAccent) { const el=document.getElementById("dyn-eng-title-accent"); if(el) el.textContent=eng.titleAccent; }
      if (eng.title)       {
        const el=document.getElementById("dyn-eng-title");
        if(el) el.childNodes[0].innerHTML=sanitizeHtml(eng.title).replace(/&lt;br&gt;/g,"<br>")+" ";
      }
      if (eng.desc)      { const el=document.getElementById("dyn-eng-desc");      if(el) el.textContent=eng.desc; }
      if (eng.formTitle) { const el=document.getElementById("form-title-aud");    if(el) el.textContent=eng.formTitle; }
      if (eng.formSub)   { const el=document.getElementById("form-sub-aud");      if(el) el.textContent=eng.formSub; }
      if (Array.isArray(eng.cards) && eng.cards.length) {
        const el=document.getElementById("dyn-eng-cards");
        if(el) el.innerHTML=eng.cards.map(c=>`<div class="eng-card"><div class="eng-ci">${escHtml(c.icon||"")}</div><div><div class="eng-ct">${escHtml(c.title||"")}</div><div class="eng-cd">${escHtml(c.desc||"")}</div></div></div>`).join("");
      }

      // ── CTA ──────────────────────────────────────────────────────────
      const cta = d.cta || {};
      if (cta.title)    { const el=document.getElementById("dyn-cta-title"); if(el) el.innerHTML=sanitizeHtml(cta.title).replace(/\n/g,"<br>"); }
      if (cta.subtitle) { const el=document.getElementById("dyn-cta-sub");   if(el) el.textContent=cta.subtitle; }
      if (cta.btn1)     { const el=document.getElementById("dyn-cta-btn1"); if(el){ el.textContent=cta.btn1.text||cta.btn1; const h1=safeCta(cta.btn1.href); if(h1) el.href=h1; } }
      if (cta.btn2)     { const el=document.getElementById("dyn-cta-btn2"); if(el){ el.textContent=cta.btn2.text||cta.btn2; const h2=safeCta(cta.btn2.href); if(h2) el.href=h2; } }
      if (cta.btn3)     { const el=document.getElementById("dyn-cta-btn3"); if(el){ el.textContent=cta.btn3.text||cta.btn3; const h3=safeCta(cta.btn3.href); if(h3) el.href=h3; } }

      // ── Contact — en-tête + coordonnées ──────────────────────────────
      if (ct.sectionTag)    { const el=document.getElementById("dyn-ct-tag");          if(el) el.textContent=ct.sectionTag; }
      if (ct.sectionAccent) { const el=document.getElementById("dyn-ct-accent");       if(el) el.textContent=ct.sectionAccent; }
      if (ct.sectionTitle)  {
        const el=document.getElementById("dyn-ct-title");
        if(el) el.childNodes[0].textContent=ct.sectionTitle+" ";
      }
      if (ct.sidebarTitle)  {
        const el=document.getElementById("dyn-ct-sidebar-title");
        if(el) el.innerHTML=escHtml(ct.sidebarTitle).replace(/\n/g,"<br>");
      }
      if (ct.sidebarDesc)   { const el=document.getElementById("dyn-ct-sidebar-desc"); if(el) el.textContent=ct.sidebarDesc; }
      if (ct.address)       { const el=document.getElementById("dyn-ct-address");      if(el) el.textContent=ct.address; }
      if (ct.email)         { const el=document.getElementById("dyn-ct-email");        if(el) el.textContent=ct.email; }
      if (ct.social)        { const el=document.getElementById("dyn-ct-social");       if(el) el.textContent=ct.social; }

      // ── Footer ───────────────────────────────────────────────────────
      const ft = d.footer || {};
      if (ft.logoName)   { const el=document.getElementById("dyn-ft-logo-name"); if(el) el.textContent=ft.logoName; }
      if (ft.logoSub)    { const el=document.getElementById("dyn-ft-logo-sub");  if(el) el.textContent=ft.logoSub; }
      if (ft.brandText)  { const el=document.getElementById("dyn-ft-brand");     if(el) el.textContent=ft.brandText; }
      if (ft.copyright)  { const el=document.getElementById("dyn-ft-copyright"); if(el) el.textContent=ft.copyright; }
      // ── Contact — titre formulaire message ───────────────────────────
      if (ct.formTitle2) { const el=document.getElementById("dyn-ct-form-title2"); if(el) el.textContent=ct.formTitle2; }

      // ── Actualités — slides, vedettes, cards ─────────────────────────
      const ac = d.actus || {};

      // Slides hero
      const slidesWrap = document.getElementById("actu-hero-track");
      const dotsWrap   = document.getElementById("actu-hero-dots");
      if (slidesWrap && Array.isArray(ac.slides) && ac.slides.length) {
        slidesWrap.innerHTML = ac.slides.map(s => `
          <div class="actu-hero-slide">
            <img src="${escHtml(s.image||'')}" alt="${escHtml(s.alt||'')}">
            <div class="actu-hero-overlay"></div>
            <div class="actu-hero-content">
              <span class="actu-hero-chip"${s.chipColor?` style="background:${escHtml(s.chipColor)}"`:''}">${escHtml(s.chip||'')}</span>
              <div class="actu-hero-date">${escHtml(s.date||'')}</div>
              <h2 class="actu-hero-title">${escHtml(s.title||'').replace(/\n/g,'<br>')}</h2>
              <p class="actu-hero-sub">${escHtml(s.subtitle||'')}</p>
            </div>
          </div>`).join('');
        if (dotsWrap) dotsWrap.innerHTML = ac.slides.map((_,i)=>
          `<button class="actu-hero-dot${i===0?' hd-active':''}" aria-label="Slide ${i+1}"></button>`).join('');
        initActuSlider();
      }

      // Vedettes
      const vedettesWrap = document.getElementById("actu-vedettes-wrap");
      if (vedettesWrap && Array.isArray(ac.vedettes) && ac.vedettes.length) {
        vedettesWrap.innerHTML = ac.vedettes.map((v,i) => {
          const imgSide = v.image
            ? `<img src="${escHtml(v.image)}" alt="${escHtml(v.tag||'')}">
               <span class="actu-vedette-badge"${v.badgeColor?` style="background:${escHtml(v.badgeColor)}"`:''}">${escHtml(v.badge||'')}</span>`
            : `<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;padding:40px;text-align:center">
                 <div style="font-size:56px">${escHtml(v.placeholderEmoji||'📰')}</div>
                 <div style="font-family:'Cormorant Garamond',serif;font-size:22px;font-weight:700;color:rgba(255,255,255,.9);line-height:1.3">${escHtml(v.placeholderTitle||'').replace(/\n/g,'<br>')}</div>
                 <div style="font-size:11px;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,.35);font-weight:700">${escHtml(v.placeholderDate||'')}</div>
               </div>
               <span class="actu-vedette-badge"${v.badgeColor?` style="background:${escHtml(v.badgeColor)}"`:''}">${escHtml(v.badge||'')}</span>`;
          const tagsHtml = (v.tags||[]).map(t=>`<span class="actu-tag">${escHtml(t)}</span>`).join('');
          return `<div class="actu-vedette rev"${i<ac.vedettes.length-1?' style="margin-bottom:32px"':''}>
            <div class="actu-vedette-img"${v.imageBg&&!v.image?` style="background:${v.imageBg}"`:''}">${imgSide}</div>
            <div class="actu-vedette-body">
              <div class="actu-vedette-tag"${v.tagColor?` style="color:${escHtml(v.tagColor)}"`:''}">${escHtml(v.tag||'')}</div>
              <div class="actu-vedette-date">${escHtml(v.date||'')}</div>
              <h3 class="actu-vedette-title">${escHtml(v.title||'')}</h3>
              ${v.text1?`<p class="actu-vedette-txt">${escHtml(v.text1)}</p>`:''}
              ${v.quote?`<div class="actu-vedette-quote"${v.tagColor?` style="border-color:${escHtml(v.tagColor)}"`:''}">${escHtml(v.quote)}</div>`:''}
              ${v.text2?`<p class="actu-vedette-txt">${escHtml(v.text2)}</p>`:''}
              ${tagsHtml?`<div class="actu-vedette-tags">${tagsHtml}</div>`:''}
            </div>
          </div>`;
        }).join('');
        vedettesWrap.querySelectorAll(".rev").forEach(el=>rObs.observe(el));
      }

      // Cards grille
      const cardsGrid = document.getElementById("actu-cards-grid");
      if (cardsGrid && Array.isArray(ac.cards) && ac.cards.length) {
        cardsGrid.innerHTML = ac.cards.map(c => `
          <div class="actu-card rev${c.image?' actu-card-has-img':''}"${c.borderColor?` style="border-color:${escHtml(c.borderColor)}"`:''}>
            ${c.image?`<div class="actu-card-img"><img src="${escHtml(c.image)}" alt="${escHtml(c.title||'')}" loading="lazy"></div>`:''}
            <div class="actu-card-cat"${c.catColor?` style="color:${escHtml(c.catColor)}"`:''}">${escHtml(c.cat||'')}</div>
            <div class="actu-card-ic">${escHtml(c.icon||'')}</div>
            <div class="actu-card-dt">
              <span class="actu-card-day">${escHtml(c.day||'')}</span>
              <span class="actu-card-mon">${escHtml(c.month||'')}<br>${escHtml(c.year||'')}</span>
            </div>
            <div class="actu-card-title">${escHtml(c.title||'')}</div>
            <div class="actu-card-desc">${escHtml(c.desc||'')}</div>
          </div>`).join('');
        cardsGrid.querySelectorAll(".rev").forEach(el=>rObs.observe(el));
      }
    })
    .catch(() => {}); // Fallback : le contenu statique reste affiché
}
loadContent();

// ── TRADUCTION DU CONTENU DYNAMIQUE (changement de langue) ───────────────────
const _DYN_LANG_MAP = { en: "I18N_DATA_EN", es: "I18N_DATA_ES", zh: "I18N_DATA_ZH", ru: "I18N_DATA_RU" };

function applyDynLang(lang) {
  if (lang === "fr") { loadContent(); return; }
  const obj = window[_DYN_LANG_MAP[lang]];
  if (!obj) return; // fichier non chargé
  const d = obj;
  const h = d.hero || {};
  const a = d.about || {};

  // Hero
  const setTxt = (id, v) => { const el=document.getElementById(id); if(el && v!==undefined) el.textContent=v; };
  const setHtml = (id, v) => { const el=document.getElementById(id); if(el && v!==undefined) el.innerHTML=sanitizeHtml(v); };

  if (h.eyebrow) setTxt("dyn-hero-eyebrow", h.eyebrow);
  if (h.role)    setTxt("dyn-role", h.role);
  if (h.slogan)  setHtml("dyn-slogan", h.slogan);
  if (h.subtitle) setTxt("dyn-sub", h.subtitle);
  if (h.btn1)    setTxt("dyn-hero-btn1", h.btn1);
  if (h.btn2)    setTxt("dyn-hero-btn2", h.btn2);

  // À propos
  if (a.sectionTag) setTxt("dyn-about-tag", a.sectionTag);
  if (a.badgeLbl)   setTxt("dyn-about-badge-lbl", a.badgeLbl);
  if (a.title)      setHtml("dyn-about-title", a.title);
  if (a.intro)      setTxt("dyn-about-intro", a.intro);
  if (Array.isArray(a.paragraphs) && a.paragraphs.length) {
    const el = document.getElementById("dyn-about-body");
    if (el) el.innerHTML = a.paragraphs.map(p => `<p class="about-body">${escHtml(p)}</p>`).join("");
  }
  if (Array.isArray(a.badges) && a.badges.length) {
    const el = document.getElementById("dyn-about-pills");
    if (el) el.innerHTML = a.badges.map(b => `<span class="pill">${escHtml(b)}</span>`).join("");
  }

  // Stats — labels uniquement (les chiffres restent de data.json)
  if (Array.isArray(d.stats)) {
    d.stats.forEach((s, i) => {
      if (s && s.label) setTxt("dyn-s" + i + "-lbl", s.label);
    });
  }

  // Parcours — en-tête
  const pSec = d.parcoursSection || {};
  if (pSec.tag)         setTxt("dyn-parcours-tag", pSec.tag);
  if (pSec.titleAccent) setTxt("dyn-parcours-accent", pSec.titleAccent);
  if (pSec.title) {
    const el = document.getElementById("dyn-parcours-title");
    if (el && el.childNodes[0]) el.childNodes[0].textContent = pSec.title + " ";
  }

  // Parcours — timeline
  if (Array.isArray(d.parcours) && d.parcours.length) {
    const parcoursWrap = document.getElementById("dyn-parcours");
    if (parcoursWrap) {
      const delays = ["d1","d2","d3","d4","d5","d6"];
      const sides  = ["left","right","left","right","left","right","left"];
      parcoursWrap.innerHTML = d.parcours.map((p, i) => {
        const isLeft = sides[i] === "left";
        const card = `<div class="tl-card">
          <div class="tl-year">${escHtml(p.year||"")}</div>
          <div class="tl-title">${escHtml(p.title||"")}</div>
          <div class="tl-desc">${escHtml(p.desc||"")}</div>
          <span class="tl-tag">${escHtml(p.tag||"")}</span>
        </div>`;
        const dot   = `<div class="tl-dot">${escHtml(p.emoji||"•")}</div>`;
        const empty = `<div class="tl-empty"></div>`;
        return `<div class="tl-item rev ${delays[i%6]}">
          ${isLeft ? card : empty}
          ${dot}
          ${isLeft ? empty : card}
        </div>`;
      }).join("");
      parcoursWrap.querySelectorAll(".rev").forEach(el => rObs.observe(el));
      parcoursWrap.querySelectorAll(".tl-item").forEach((el, i) => { el.style.transitionDelay = `${i * 0.13}s`; });
    }
  }

  // Programme — en-tête
  const ps = d.programmeSection || {};
  if (ps.tag)         setTxt("dyn-prog-tag", ps.tag);
  if (ps.titleAccent) setTxt("dyn-prog-accent", ps.titleAccent);
  if (ps.title) {
    const el = document.getElementById("dyn-prog-title");
    if (el && el.childNodes[0]) el.childNodes[0].textContent = ps.title + " ";
  }
  if (ps.subtitle) setTxt("dyn-prog-sub", ps.subtitle);

  // Programme — axes
  if (d.programme) {
    const prog = d.programme;
    const progWrap = document.getElementById("dyn-programme");
    if (progWrap) {
      const axes = prog.axes || [];
      const delays2 = ["d1","d2","d3","d1","d2","d3"];
      const heroTitle = (prog.heroTitle || "").replace(/\n/g, "<br>");
      progWrap.innerHTML = `
        <div class="prog-hero rev">
          <div>
            <h3 class="prog-hero-title">${heroTitle}</h3>
            <p class="prog-hero-sub">${escHtml(prog.heroText||"")}</p>
          </div>
          <div class="prog-hero-big">2032</div>
        </div>
        <div class="prog-grid">
          ${axes.map((ax, i) => `
            <div class="prog-card rev ${delays2[i]}">
              <div class="prog-num">${String(i+1).padStart(2,"0")}</div>
              <h3 class="prog-title">${escHtml(ax.title||"")}</h3>
              <p class="prog-txt">${escHtml(ax.text||"")}</p>
              <ul class="prog-pts">
                ${(ax.points||[]).map(pt => `<li>${escHtml(pt)}</li>`).join("")}
              </ul>
            </div>`).join("")}
        </div>`;
      progWrap.querySelectorAll(".rev").forEach(el => rObs.observe(el));
    }
  }

  // Galerie — en-tête
  const gs = d.galerieSection || {};
  if (gs.tag)         setTxt("dyn-gal-tag", gs.tag);
  if (gs.titleAccent) setTxt("dyn-gal-accent", gs.titleAccent);
  if (gs.title) {
    const el = document.getElementById("dyn-gal-title");
    if (el && el.childNodes[0]) el.childNodes[0].textContent = gs.title + " ";
  }

  // Actualités — en-tête
  const as_ = d.actusSection || {};
  if (as_.tag)         setTxt("dyn-actu-tag", as_.tag);
  if (as_.titleAccent) setTxt("dyn-actu-accent", as_.titleAccent);
  if (as_.gridTitle)   setTxt("dyn-actu-grid-title", as_.gridTitle);
  if (as_.title) {
    const el = document.getElementById("dyn-actu-title");
    if (el && el.childNodes[0]) el.childNodes[0].textContent = as_.title + " ";
  }

  // Engagement
  const eng = d.engagement || {};
  if (eng.tag)         setTxt("dyn-eng-tag", eng.tag);
  if (eng.titleAccent) setTxt("dyn-eng-title-accent", eng.titleAccent);
  if (eng.title) {
    const el = document.getElementById("dyn-eng-title");
    if (el && el.childNodes[0]) el.childNodes[0].innerHTML = eng.title.replace(/\n/g,"<br>") + " ";
  }
  if (eng.desc) setTxt("dyn-eng-desc", eng.desc);
  if (Array.isArray(eng.cards) && eng.cards.length) {
    const el = document.getElementById("dyn-eng-cards");
    if (el) el.innerHTML = eng.cards.map(c => `<div class="eng-card"><div class="eng-ct">${escHtml(c.title||"")}</div><div class="eng-cd">${escHtml(c.desc||"")}</div></div>`).join("");
  }
  if (eng.formTitle) setTxt("form-title-aud", eng.formTitle);
  if (eng.formSub)   setTxt("form-sub-aud",   eng.formSub);

  // Actualités — slides, vedettes, cards (re-rendu avec traductions i18n)
  if (d.actus && window._FR_DATA) {
    const frAc = window._FR_DATA.actus || {};
    const i18nAc = d.actus;

    // Slides hero
    if (Array.isArray(i18nAc.slides) && Array.isArray(frAc.slides)) {
      const slidesWrap2 = document.getElementById("actu-hero-track");
      const dotsWrap2   = document.getElementById("actu-hero-dots");
      if (slidesWrap2) {
        const merged = frAc.slides.map((s,i) => { const t=i18nAc.slides[i]||{}; return Object.assign({},s,t); });
        slidesWrap2.innerHTML = merged.map(s => `
          <div class="actu-hero-slide">
            <img src="${escHtml(s.image||'')}" alt="${escHtml(s.alt||'')}">
            <div class="actu-hero-overlay"></div>
            <div class="actu-hero-content">
              <span class="actu-hero-chip"${s.chipColor?` style="background:${escHtml(s.chipColor)}"`:''}">${escHtml(s.chip||'')}</span>
              <div class="actu-hero-date">${escHtml(s.date||'')}</div>
              <h2 class="actu-hero-title">${escHtml(s.title||'').replace(/\n/g,'<br>')}</h2>
              <p class="actu-hero-sub">${escHtml(s.subtitle||'')}</p>
            </div>
          </div>`).join('');
        if (dotsWrap2) dotsWrap2.innerHTML = merged.map((_,i)=>
          `<button class="actu-hero-dot${i===0?' hd-active':''}" aria-label="Slide ${i+1}"></button>`).join('');
        initActuSlider();
      }
    }

    // Vedettes
    if (Array.isArray(i18nAc.vedettes) && Array.isArray(frAc.vedettes)) {
      const vedettesWrap2 = document.getElementById("actu-vedettes-wrap");
      if (vedettesWrap2) {
        const merged = frAc.vedettes.map((v,i) => { const t=i18nAc.vedettes[i]||{}; return Object.assign({},v,t); });
        vedettesWrap2.innerHTML = merged.map((v,i) => {
          const imgSide = v.image
            ? `<img src="${escHtml(v.image)}" alt="${escHtml(v.tag||'')}">
               <span class="actu-vedette-badge"${v.badgeColor?` style="background:${escHtml(v.badgeColor)}"`:''}">${escHtml(v.badge||'')}</span>`
            : `<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;padding:40px;text-align:center">
                 <div style="font-size:56px">${escHtml(v.placeholderEmoji||'📰')}</div>
                 <div style="font-family:'Cormorant Garamond',serif;font-size:22px;font-weight:700;color:rgba(255,255,255,.9);line-height:1.3">${escHtml(v.placeholderTitle||'').replace(/\n/g,'<br>')}</div>
                 <div style="font-size:11px;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,.35);font-weight:700">${escHtml(v.placeholderDate||'')}</div>
               </div>
               <span class="actu-vedette-badge"${v.badgeColor?` style="background:${escHtml(v.badgeColor)}"`:''}">${escHtml(v.badge||'')}</span>`;
          const tagsHtml = (v.tags||[]).map(t=>`<span class="actu-tag">${escHtml(t)}</span>`).join('');
          return `<div class="actu-vedette rev"${i<merged.length-1?' style="margin-bottom:32px"':''}>
            <div class="actu-vedette-img"${v.imageBg&&!v.image?` style="background:${v.imageBg}"`:''}">${imgSide}</div>
            <div class="actu-vedette-body">
              <div class="actu-vedette-tag"${v.tagColor?` style="color:${escHtml(v.tagColor)}"`:''}">${escHtml(v.tag||'')}</div>
              <div class="actu-vedette-date">${escHtml(v.date||'')}</div>
              <h3 class="actu-vedette-title">${escHtml(v.title||'')}</h3>
              ${v.text1?`<p class="actu-vedette-txt">${escHtml(v.text1)}</p>`:''}
              ${v.quote?`<div class="actu-vedette-quote"${v.tagColor?` style="border-color:${escHtml(v.tagColor)}"`:''}">${escHtml(v.quote)}</div>`:''}
              ${v.text2?`<p class="actu-vedette-txt">${escHtml(v.text2)}</p>`:''}
              ${tagsHtml?`<div class="actu-vedette-tags">${tagsHtml}</div>`:''}
            </div>
          </div>`;
        }).join('');
        vedettesWrap2.querySelectorAll(".rev").forEach(el=>rObs.observe(el));
      }
    }

    // Cards grille
    if (Array.isArray(i18nAc.cards) && Array.isArray(frAc.cards)) {
      const cardsGrid2 = document.getElementById("actu-cards-grid");
      if (cardsGrid2) {
        const merged = frAc.cards.map((c,i) => { const t=i18nAc.cards[i]||{}; return Object.assign({},c,t); });
        cardsGrid2.innerHTML = merged.map(c => `
          <div class="actu-card rev${c.image?' actu-card-has-img':''}"${c.borderColor?` style="border-color:${escHtml(c.borderColor)}"`:''}>
            ${c.image?`<div class="actu-card-img"><img src="${escHtml(c.image)}" alt="${escHtml(c.title||'')}" loading="lazy"></div>`:''}
            <div class="actu-card-cat"${c.catColor?` style="color:${escHtml(c.catColor)}"`:''}">${escHtml(c.cat||'')}</div>
            <div class="actu-card-ic">${escHtml(c.icon||'')}</div>
            <div class="actu-card-dt">
              <span class="actu-card-day">${escHtml(c.day||'')}</span>
              <span class="actu-card-mon">${escHtml(c.month||'')}<br>${escHtml(c.year||'')}</span>
            </div>
            <div class="actu-card-title">${escHtml(c.title||'')}</div>
            <div class="actu-card-desc">${escHtml(c.desc||'')}</div>
          </div>`).join('');
        cardsGrid2.querySelectorAll(".rev").forEach(el=>rObs.observe(el));
      }
    }
  }

  // Galerie — slides (re-rendu textes avec traductions i18n)
  if (d.gallery && window._FR_DATA) {
    const frGal = window._FR_DATA.gallery || {};
    const i18nGal = d.gallery;
    if (Array.isArray(i18nGal.slides) && Array.isArray(frGal.slides)) {
      const galTrack2 = document.getElementById("galTrack");
      if (galTrack2) {
        const merged = frGal.slides.map((s,i) => { const t=i18nGal.slides[i]||{}; return Object.assign({},s,t); });
        galTrack2.innerHTML = merged.map(s => `
          <div class="gal-slide">
            ${s.image
              ? `<img src="${escHtml(s.image)}" alt="${escHtml(s.title||'')}">`
              : `<div class="gal-slide-placeholder"><div style="font-size:50px">${escHtml(s.emoji||'🖼️')}</div></div>`}
            <div class="gal-cap">
              <h3>${escHtml(s.title||'')}</h3>
              <p>${escHtml(s.subtitle||'')}</p>
            </div>
          </div>`).join('');
        initSlider();
      }
    }
  }

  // CTA
  const cta = d.cta || {};
  if (cta.title)    { const el=document.getElementById("dyn-cta-title"); if(el) el.innerHTML=sanitizeHtml(cta.title).replace(/\n/g,"<br>"); }
  if (cta.subtitle) setTxt("dyn-cta-sub", cta.subtitle);
  if (cta.btn1)     { const el=document.getElementById("dyn-cta-btn1"); if(el) el.textContent=cta.btn1.text||cta.btn1; }
  if (cta.btn2)     { const el=document.getElementById("dyn-cta-btn2"); if(el) el.textContent=cta.btn2.text||cta.btn2; }
  if (cta.btn3)     { const el=document.getElementById("dyn-cta-btn3"); if(el) el.textContent=cta.btn3.text||cta.btn3; }

  // Contact — en-tête
  const ct = d.contact || {};
  if (ct.tag)          setTxt("dyn-ct-tag", ct.tag);
  if (ct.titleAccent)  setTxt("dyn-ct-accent", ct.titleAccent);
  if (ct.title) {
    const el = document.getElementById("dyn-ct-title");
    if (el && el.childNodes[0]) el.childNodes[0].textContent = ct.title + " ";
  }
  if (ct.sidebarTitle) {
    const el = document.getElementById("dyn-ct-sidebar-title");
    if (el) el.innerHTML = escHtml(ct.sidebarTitle).replace(/\n/g,"<br>");
  }
  if (ct.sidebarDesc)  setTxt("dyn-ct-sidebar-desc", ct.sidebarDesc);

  // Footer
  const ft = d.footer || {};
  if (ft.logoSub)   setTxt("dyn-ft-logo-sub", ft.logoSub);
  if (ft.brand)     setTxt("dyn-ft-brand", ft.brand);
  if (ft.copyright) setTxt("dyn-ft-copyright", ft.copyright);
}

// cursor
const cur=document.getElementById("cursor"),ring=document.getElementById("cursorRing");
document.addEventListener("mousemove",e=>{
  cur.style.left=e.clientX-5+"px";cur.style.top=e.clientY-5+"px";
  ring.style.left=e.clientX-17.5+"px";ring.style.top=e.clientY-17.5+"px";
});
document.addEventListener("mousedown",()=>cur.style.transform="scale(2)");
document.addEventListener("mouseup",()=>cur.style.transform="scale(1)");

// nav scroll
const nav=document.getElementById("nav");
window.addEventListener("scroll",()=>nav.classList.toggle("sc",scrollY>60));

// mobile nav
const hbg=document.getElementById("hbg"),mob=document.getElementById("mobNav");
function mobOpen(v){
  mob.classList.toggle("open",v);
  hbg.setAttribute("aria-expanded", mob.classList.contains("open"));
  document.body.style.overflow = mob.classList.contains("open") ? "hidden" : "";
}
hbg.addEventListener("click",()=>mobOpen());
function cMob(){mobOpen(false)}

// slider
let cs=0, galSlides=[], galDotEls=[], galTrackEl=null, galTimer=null;
function initSlider() {
  galTrackEl = document.getElementById("galTrack");
  if (!galTrackEl) return;
  galSlides = galTrackEl.querySelectorAll(".gal-slide");
  galDotEls = document.querySelectorAll(".gal-dot");
  cs = 0;
  if (galTimer) clearInterval(galTimer);
  galTimer = setInterval(() => gSlide(1), 5500);
  upd();
}
function upd(){if(!galTrackEl)return;galTrackEl.style.transform=`translateX(-${cs*100}%)`;galDotEls.forEach((d,i)=>d.classList.toggle("a",i===cs))}
function gSlide(d){if(!galSlides.length)return;cs=(cs+d+galSlides.length)%galSlides.length;upd()}
function gGo(n){cs=n;upd()}

// counters — effet slot machine
function aCount(el){
  const target=+el.dataset.c;
  if(isNaN(target)){el.textContent=el.dataset.c;return;}
  const totalDur=1800, spinDur=900;
  const start=performance.now();
  function frame(now){
    const elapsed=now-start;
    if(elapsed<spinDur){
      // Phase 1 : chiffres qui défilent en boucle
      el.textContent=Math.floor(Math.random()*99);
      requestAnimationFrame(frame);
    } else if(elapsed<totalDur){
      // Phase 2 : ralentissement vers la cible
      const p=(elapsed-spinDur)/(totalDur-spinDur);
      const ease=1-Math.pow(1-p,3);
      const displayed=Math.round(ease*target);
      el.textContent=displayed;
      requestAnimationFrame(frame);
    } else {
      el.textContent=target;
    }
  }
  requestAnimationFrame(frame);
}
const cObs=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){aCount(e.target);cObs.unobserve(e.target)}})},{threshold:.5});
document.querySelectorAll("[data-c]").forEach(el=>cObs.observe(el));

// reveal
const rObs=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("vis");rObs.unobserve(e.target)}})},{threshold:.12});
document.querySelectorAll(".rev,.rev-l,.rev-r").forEach(el=>rObs.observe(el));

// ── Envoi des formulaires vers le serveur ────────────────────────────
const FORMSPREE = {};
async function sendForm(storageKey, _unused, formData, btn, successMsg) {
  btn.textContent = "⏳ Envoi en cours…";
  btn.disabled = true;

  // Construire l'objet à envoyer
  const entry = {};
  formData.forEach((v, k) => { entry[k] = v; });
  entry.type  = storageKey;
  entry._date = new Date().toLocaleString("fr-FR");
  entry._id   = Date.now() + "-" + Math.random().toString(36).slice(2, 8);

  // 1. Envoi au serveur (persistance)
  let serverOk = false;
  try {
    const res = await fetch("/api/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry)
    });
    serverOk = res.ok;
  } catch (_) { /* serveur non disponible — continuer */ }

  // 2. Copie locale (pour affichage admin en mode hors-ligne)
  try {
    const list = JSON.parse(localStorage.getItem(storageKey) || "[]");
    list.unshift(entry);
    localStorage.setItem(storageKey, JSON.stringify(list));
  } catch (_) {}

  if (!serverOk) {
    btn.textContent = "⚠️ Envoyé (mode hors-ligne)";
    btn.style.background = "#f39c12";
  } else {
    btn.textContent = successMsg;
    btn.style.background = "#2ecc71";
  }
  // Réinitialiser le formulaire après 3 secondes
  const originalText = btn.dataset.originalText || "📨 Soumettre";
  setTimeout(() => {
    const form = btn.closest("form");
    if (form) form.reset();
    btn.style.background = "";
    btn.textContent = originalText;
    btn.disabled = false;
  }, 3000);
}

function fSub(e, f) {
  e.preventDefault();
  const objet = document.getElementById("sel-objet").value;
  const isRecl = objet.normalize("NFC") === "R\u00e9clamation";

  if (isRecl) {
    const desc = document.getElementById("desc-sinistre").value.trim();
    if (!desc) { alert("Veuillez décrire le sinistre ou problème à signaler."); return; }
  } else {
    const raison = document.getElementById("raison-text").value.trim();
    if (!raison) { alert("Veuillez rédiger la raison de votre demande."); return; }
  }

  const fd = new FormData(f);
  const successMsg = isRecl
    ? "✅ Signalement enregistré — Le Député et son équipe ont été alertés"
    : "✅ Demande enregistrée — Réponse sous 48h";

  sendForm("bininga_audiences", FORMSPREE.audience, fd,
    f.querySelector("[type=submit]"),
    successMsg);
}

// ── GÉO-SINISTRE ────────────────────────────────────────────
function toggleGeoFields(sel) {
  const extras = document.getElementById("geo-extras");
  const reason = document.getElementById("aud-reason");
  const raison = document.getElementById("raison-text");
  const isRecl = sel.value.normalize("NFC") === "R\u00e9clamation";
  extras.style.display = isRecl ? "block" : "none";
  reason.style.display = isRecl ? "none" : "block";
  if (raison) raison.required = !isRecl;

  const titles = {
    "Demande d'audience":  ["Demande d'audience auprès du Député", "Expliquez l'objet de votre demande — notre équipe vous contactera sous 48h"],
    "R\u00e9clamation":   ["Signalement officiel au Député", "Géolocalisez le problème et ajoutez une photo — le Député et toute son équipe seront alertés immédiatement"],
    "Question au Député":  ["Poser une question au Député", "Rédigez votre question, le Député ou son équipe vous répondra directement"],
    "Autre":               ["Autre demande", "Décrivez votre demande, notre équipe l'étudiera avec attention"]
  };
  const [t, s] = titles[sel.value] || titles["Demande d'audience"];
  document.getElementById("form-title-aud").textContent = t;
  document.getElementById("form-sub-aud").textContent = s;

  const placeholders = {
    "Demande d'audience":  "Expliquez pourquoi vous souhaitez rencontrer le Député, votre situation et l'objet précis de votre demande…",
    "Question au Député":  "Rédigez votre question pour le Député d'Ewo…",
    "Autre":               "Décrivez votre demande ou votre situation…"
  };
  if (raison) raison.placeholder = placeholders[sel.value] || placeholders["Demande d'audience"];

  document.getElementById("btn-form-aud").textContent = isRecl
    ? "⚠️ Envoyer le signalement" : "📨 Soumettre ma demande";
}

function localizeSinistre() {
  if (!navigator.geolocation) {
    alert("La géolocalisation n'est pas disponible sur cet appareil.");
    return;
  }
  const btn    = document.getElementById("btn-geo");
  const status = document.getElementById("geo-status");
  btn.disabled = true;
  btn.textContent = "⏳ Localisation en cours…";
  status.className = "geo-status";
  status.innerHTML = '<span class="dot"></span> Demande de localisation GPS…';

  navigator.geolocation.getCurrentPosition(
    async pos => {
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      const acc = Math.round(pos.coords.accuracy);

      document.getElementById("geo-lat").value = lat;
      document.getElementById("geo-lng").value = lng;
      const mapsUrl = `https://www.google.com/maps?q=${lat},${lng}&z=16`;
      document.getElementById("geo-maps-url").value = mapsUrl;

      // Reverse geocode via Nominatim (OpenStreetMap, gratuit)
      let label = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
      try {
        const r = await fetch(
          `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&accept-language=fr`,
          { headers: { "User-Agent": "BiningaDepute/1.0" } }
        );
        const d = await r.json();
        if (d.display_name) label = d.display_name;
      } catch (_) {}

      document.getElementById("geo-label").value = label;

      status.className = "geo-status ok";
      status.innerHTML = `<span class="dot"></span> Position capturée (précision ±${acc}m)`;

      const addrEl = document.getElementById("geo-addr");
      addrEl.textContent = "📍 " + label;
      addrEl.style.display = "block";

      // Carte OpenStreetMap embarquée
      const mapEl = document.getElementById("geo-map");
      const δ = 0.008;
      mapEl.style.display = "block";
      mapEl.innerHTML = `<iframe
        src="https://www.openstreetmap.org/export/embed.html?bbox=${lng-δ},${lat-δ},${lng+δ},${lat+δ}&layer=mapnik&marker=${lat},${lng}"
        allowfullscreen loading="lazy"></iframe>`;

      btn.textContent = "✅ Position enregistrée";
    },
    err => {
      status.className = "geo-status err";
      const msgs = {1:"Accès refusé — autorisez la géolocalisation dans votre navigateur",2:"Position introuvable",3:"Délai dépassé"};
      status.innerHTML = `<span class="dot"></span> ${msgs[err.code]||"Erreur"}`;
      btn.disabled = false;
      btn.textContent = "🔄 Réessayer";
    },
    { enableHighAccuracy: true, timeout: 12000 }
  );
}

async function handleSinistrePhoto(input) {
  const file = input.files[0];
  if (!file) return;
  const preview = document.getElementById("photo-preview");
  preview.innerHTML = '<div class="photo-loader">⏳ Compression et envoi de la photo…</div>';

  // Compression canvas → max 900px, JPEG 0.7
  const img = new Image();
  img.onload = async () => {
    const MAX = 900;
    let w = img.width, h = img.height;
    if (w > MAX) { h = Math.round(h * MAX / w); w = MAX; }
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    canvas.getContext("2d").drawImage(img, 0, 0, w, h);
    canvas.toBlob(async blob => {
      if (blob.size > 3 * 1024 * 1024) {
        preview.innerHTML = '<div class="photo-loader" style="color:#e74c3c">❌ Image trop lourde même après compression. Réduisez la taille.</div>';
        return;
      }
      const fd = new FormData();
      fd.append("file", blob, "sinistre.jpg");
      try {
        const res  = await fetch("/api/upload-sinistre", { method: "POST", body: fd });
        const data = await res.json();
        if (data.ok) {
          document.getElementById("photo-url").value = data.path;
          preview.innerHTML = `<img src="${data.path}" alt="Photo du sinistre">
            <div style="font-size:11px;color:#2ecc71;margin-top:4px;font-weight:600">✅ Photo enregistrée</div>`;
        } else {
          preview.innerHTML = `<div class="photo-loader" style="color:#e74c3c">❌ ${data.message}</div>`;
        }
      } catch (_) {
        preview.innerHTML = '<div class="photo-loader" style="color:#e74c3c">❌ Erreur réseau. Réessayez.</div>';
      }
    }, "image/jpeg", 0.7);
  };
  img.onerror = () => { preview.innerHTML = '<div class="photo-loader" style="color:#e74c3c">❌ Fichier image invalide.</div>'; };
  img.src = URL.createObjectURL(file);
}

function fCt(e, f) {
  e.preventDefault();
  sendForm("bininga_contacts", FORMSPREE.contact, new FormData(f),
    f.querySelector("button"),
    "✅ Message envoyé — Réponse sous 24h");
}

// ── SMOOTH SCROLL ANCRES ─────────────────────────────────
document.querySelectorAll("a[href^='#']").forEach(a => a.addEventListener("click", e => {
  const t = document.querySelector(a.getAttribute("href"));
  if(t){ e.preventDefault(); t.scrollIntoView({behavior:"smooth", block:"start"}); }
}));

// ── PAGE LOADER ───────────────────────────────────────────
window.addEventListener("load", () => {
  setTimeout(() => { document.getElementById("loader").classList.add("done"); }, 1400);
});

// ── TRACKING VISITEURS (côté serveur) ────────────────────
(function(){
  fetch("/api/track-visit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ page: "/", kind: "visit" })
  }).catch(()=>{});
})();

// ── TRACKING LECTURES DU PROGRAMME ───────────────────────
(function(){
  const progEl = document.getElementById("programme");
  if(!progEl) return;
  let tracked = false;
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if(e.isIntersecting && !tracked){
        tracked = true;
        fetch("/api/track-visit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ kind: "prog" })
        }).catch(()=>{});
        obs.disconnect();
      }
    });
  }, { threshold: 0.2 });
  obs.observe(progEl);
})();

// ── LIGHTBOX GALERIE ──────────────────────────────────────
function openLightbox(src, alt) {
  const ov = document.createElement("div");
  ov.id = "gal-lightbox";
  ov.style.cssText = "position:fixed;inset:0;z-index:9000;background:rgba(0,0,0,.93);display:flex;align-items:center;justify-content:center;padding:20px;cursor:zoom-out;animation:lb-in .2s ease";
  const img = document.createElement("img");
  img.src = src;
  img.alt = alt || "";
  img.style.cssText = "max-width:90vw;max-height:90vh;object-fit:contain;border-radius:4px;box-shadow:0 0 60px rgba(0,0,0,.8)";
  const close = document.createElement("button");
  close.textContent = "✕";
  close.setAttribute("aria-label","Fermer");
  close.style.cssText = "position:absolute;top:18px;right:22px;background:none;border:none;color:#fff;font-size:28px;cursor:pointer;opacity:.7;line-height:1;z-index:1";
  close.onmouseover = () => close.style.opacity="1";
  close.onmouseout  = () => close.style.opacity=".7";
  const caption = document.createElement("p");
  if(alt){ caption.textContent=alt; caption.style.cssText="position:absolute;bottom:22px;left:0;right:0;text-align:center;color:rgba(255,255,255,.6);font-size:13px;padding:0 20px"; }
  function closeLb(){ ov.remove(); document.removeEventListener("keydown",onKey); }
  function onKey(e){ if(e.key==="Escape") closeLb(); }
  ov.appendChild(img);
  ov.appendChild(close);
  if(alt) ov.appendChild(caption);
  ov.addEventListener("click", e=>{ if(e.target===ov||e.target===close) closeLb(); });
  document.addEventListener("keydown", onKey);
  document.body.appendChild(ov);
}
const _lbStyle = document.createElement("style");
_lbStyle.textContent = "@keyframes lb-in{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:none}}";
document.head.appendChild(_lbStyle);

// ── STAGGER TIMELINE ─────────────────────────────────────
document.querySelectorAll(".tl-item").forEach((el, i) => {
  el.style.transitionDelay = `${i * 0.13}s`;
});

// ── PARALLAX HERO — boucle rAF 120fps avec lerp ───────────
const heroImg = document.querySelector(".hero-img-side");
const heroBg  = document.querySelector(".hero-video-bg");
let pxCur = 0, pxTarget = 0;
window.addEventListener("scroll", () => { pxTarget = window.scrollY; }, { passive: true });
(function parallaxLoop(){
  pxCur += (pxTarget - pxCur) * 0.08;
  if(heroImg) heroImg.style.transform = `translate3d(0,${pxCur * 0.18}px,0)`;
  if(heroBg)  heroBg.style.transform  = `translate3d(0,${pxCur * 0.07}px,0)`;
  requestAnimationFrame(parallaxLoop);
})();

// modales légales
function openLegal(id){document.getElementById("modal-"+id).classList.add("open");document.body.style.overflow="hidden"}
function closeLegal(id){document.getElementById("modal-"+id).classList.remove("open");document.body.style.overflow=""}

// ── ACHAT LIVRE ────────────────────────────────────────────
function openAchat() {
  document.getElementById("modal-achat").classList.add("open");
  document.body.style.overflow = "hidden";
  showBuyOptions();
}
function showBuyOptions() {
  document.getElementById("achat-step-1").style.display = "block";
  document.getElementById("achat-step-2").style.display = "none";
}
function showOrderForm() {
  document.getElementById("achat-step-1").style.display = "none";
  document.getElementById("achat-step-2").style.display = "block";
}
function trackBuy(platform) {
  try { window.plausible && window.plausible("Achat Livre", { props: { plateforme: platform } }); } catch(_){}
  try { const l=JSON.parse(localStorage.getItem("bininga_livre_clics")||"[]"); l.push({platform,_date:new Date().toLocaleString("fr-FR")}); localStorage.setItem("bininga_livre_clics",JSON.stringify(l)); } catch(_){}
}
async function submitOrder(e, f) {
  e.preventDefault();
  const btn = document.getElementById("order-btn");
  btn.disabled = true; btn.textContent = "⏳ Envoi…";
  const fd = new FormData(f);
  const entry = { type:"bininga_commande_livre", livre:"Les mutations constitutionnelles en Afrique noire francophone", _date: new Date().toLocaleString("fr-FR"), _id: Date.now()+"-"+Math.random().toString(36).slice(2,8) };
  fd.forEach((v,k) => { entry[k] = v; });
  trackBuy("bureau");
  try { await fetch("/api/contact",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(entry)}); } catch(_){}
  try { const l=JSON.parse(localStorage.getItem("bininga_commandes")||"[]"); l.push(entry); localStorage.setItem("bininga_commandes",JSON.stringify(l)); } catch(_){}
  f.style.display = "none";
  document.getElementById("order-ok").style.display = "block";
}

// ── NEWSLETTER ─────────────────────────────────────────────
async function subNewsletter(e, f) {
  e.preventDefault();
  const btn = document.getElementById("nl-btn");
  const ok  = document.getElementById("nl-ok");
  const email = f.email.value.trim();
  btn.disabled = true; btn.textContent = "⏳ Envoi…";
  const entry = { email, type:"bininga_newsletter", _date: new Date().toLocaleString("fr-FR"), _id: Date.now()+"-"+Math.random().toString(36).slice(2,8) };
  try { await fetch("/api/contact",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(entry)}); } catch(_){}
  try { const l=JSON.parse(localStorage.getItem("bininga_newsletter")||"[]"); l.push(entry); localStorage.setItem("bininga_newsletter",JSON.stringify(l)); } catch(_){}
  f.style.display = "none";
  ok.style.display = "block";
}

// ── AUTOPLAY VIDÉO ──────────────────────────────────────────
(function(){
  const vid = document.querySelector("#video-section video");
  if(!vid) return;

  function tryPlay(){ vid.muted = true; vid.play().catch(()=>{}); }

  // Démarre uniquement quand la vidéo est visible à l'écran
  if("IntersectionObserver" in window){
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if(e.isIntersecting) tryPlay();
        else vid.pause();
      });
    }, { threshold: 0.5 });
    obs.observe(vid);
  }

  // 3. Fallback : premier scroll ou touch utilisateur (lève la restriction navigateur)
  function onInteract(){
    tryPlay();
    window.removeEventListener("scroll", onInteract);
    window.removeEventListener("touchstart", onInteract);
    window.removeEventListener("click", onInteract);
  }
  window.addEventListener("scroll",     onInteract, { passive: true });
  window.addEventListener("touchstart", onInteract, { passive: true });
  window.addEventListener("click",      onInteract, { once: true });
})();


// ── VIDÉO YOUTUBE ──────────────────────────────────────────
function loadVideo(placeholder) {
  const videoId = "D_aj4bxOsJY";
  const wrap = placeholder.parentElement;
  const iframe = document.createElement("iframe");
  iframe.src = "https://www.youtube.com/embed/" + videoId + "?autoplay=1&rel=0";
  iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
  iframe.allowFullscreen = true;
  iframe.style.cssText = "width:100%;aspect-ratio:16/9;border:none;border-radius:12px;display:block";
  placeholder.remove();
  wrap.appendChild(iframe);
}
document.querySelectorAll(".lmodal-overlay").forEach(o=>o.addEventListener("click",e=>{if(e.target===o){const id=o.id.replace("modal-","");closeLegal(id)}}));
document.addEventListener("keydown",e=>{if(e.key==="Escape")document.querySelectorAll(".lmodal-overlay.open").forEach(o=>o.classList.remove("open"))&&(document.body.style.overflow="")});

// ── BOTTOM TABBAR — active state selon le scroll ──────────
(function(){
  const tabs = document.querySelectorAll(".mob-tab-item");
  if(!tabs.length) return;

  // Correspondance tab → sections
  const tabMap = {
    accueil:  ["main-content"],
    profil:   ["about","parcours","publication"],
    actu:     ["galerie","actu","video-section"],
    audience: ["engagement"],
    contact:  ["cta-band-section","contact","newsletter"]
  };

  function setActive(tabName){
    tabs.forEach(t => t.classList.toggle("active", t.dataset.tab === tabName));
  }

  // Smooth scroll sur clic (déjà géré globalement mais on force sur la tabbar)
  tabs.forEach(tab => {
    tab.addEventListener("click", e => {
      const href = tab.getAttribute("href");
      if(!href || !href.startsWith("#")) return;
      const target = document.querySelector(href);
      if(target){ e.preventDefault(); target.scrollIntoView({behavior:"smooth",block:"start"}); }
    });
  });

  // Scroll spy
  const allSections = document.querySelectorAll("[data-mob-tab]");
  const obs = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if(entry.isIntersecting){
        const tabName = entry.target.dataset.mobTab;
        if(tabName) setActive(tabName);
      }
    });
  }, { threshold: 0.35, rootMargin: "-10% 0px -40% 0px" });

  allSections.forEach(s => obs.observe(s));
})();

// ── ACTU HERO SLIDESHOW ───────────────────────────────────
let _actuTimer = null;
function initActuSlider() {
  if (_actuTimer) clearInterval(_actuTimer);
  const track  = document.getElementById("actu-hero-track");
  const counter= document.getElementById("actu-counter");
  if (!track) return;
  const slides = track.querySelectorAll(".actu-hero-slide");
  const dots   = document.querySelectorAll(".actu-hero-dot");
  if (!slides.length) return;

  let cur = 0;
  const total = slides.length;
  function pad(n){ return String(n).padStart(2,"0"); }

  function goTo(n) {
    slides[cur].classList.remove("hs-active");
    if(dots[cur]) dots[cur].classList.remove("hd-active");
    cur = ((n % total) + total) % total;
    slides[cur].classList.add("hs-active");
    if(dots[cur]) dots[cur].classList.add("hd-active");
    track.style.transform = `translateX(-${cur * 100}%)`;
    if(counter) counter.textContent = pad(cur+1) + " / " + pad(total);
  }

  function startTimer(){ _actuTimer = setInterval(() => goTo(cur+1), 5800); }
  function resetTimer(){ clearInterval(_actuTimer); startTimer(); }

  goTo(0);
  startTimer();

  const prev = document.getElementById("actu-prev");
  const next  = document.getElementById("actu-next");
  if(prev) { prev.replaceWith(prev.cloneNode(true)); document.getElementById("actu-prev").addEventListener("click", () => { goTo(cur-1); resetTimer(); }); }
  if(next)  { next.replaceWith(next.cloneNode(true));  document.getElementById("actu-next").addEventListener("click",  () => { goTo(cur+1); resetTimer(); }); }

  dots.forEach((d,i) => d.addEventListener("click", () => { goTo(i); resetTimer(); }));

  let startX = 0;
  track.addEventListener("touchstart", e => { startX = e.touches[0].clientX; }, {passive:true});
  track.addEventListener("touchend",   e => {
    const dx = e.changedTouches[0].clientX - startX;
    if(Math.abs(dx) > 50){ goTo(dx < 0 ? cur+1 : cur-1); resetTimer(); }
  }, {passive:true});

  const hero = document.getElementById("actu-hero");
  if(hero){
    hero.addEventListener("mouseenter", () => clearInterval(_actuTimer));
    hero.addEventListener("mouseleave", startTimer);
  }
}


