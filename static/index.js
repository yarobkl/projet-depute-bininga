// Bootstrap public exécuté avant index-core.js.
// Le cœur est chargé par une balise defer standard : aucun XHR synchrone
// ne bloque le fil principal du navigateur.
(function () {
  "use strict";

  if (window.__BININGA_INDEX_CORE_LOADED__) return;
  window.__BININGA_INDEX_CORE_LOADED__ = true;

  if (!window.rObs) {
    if ("IntersectionObserver" in window) {
      window.rObs = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("vis");
            window.rObs.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12 });
    } else {
      window.rObs = {
        observe: function (el) { if (el) el.classList.add("vis"); },
        unobserve: function () {}
      };
    }
  }

  // ── Optimisation mobile sûre ─────────────────────────────
  // Conserver la photo principale existante et optimiser uniquement
  // son décodage/priorité ainsi que le coût de rendu hors écran.
  var mobile = false;
  try { mobile = window.matchMedia("(max-width: 900px)").matches; } catch (_) {}

  var heroImage = document.querySelector(".hero-img-side img");
  if (heroImage) {
    heroImage.decoding = "async";
    heroImage.setAttribute("fetchpriority", "high");
  }

  document.querySelectorAll("img[loading='lazy']").forEach(function (img) {
    img.decoding = "async";
  });

  if (mobile) {
    var perfStyle = document.createElement("style");
    perfStyle.id = "bininga-mobile-performance";
    perfStyle.textContent = "@supports(content-visibility:auto){@media(max-width:900px){body:not(.route-page-active) #publication,body:not(.route-page-active) #ewo-dashboard,body:not(.route-page-active) #galerie,body:not(.route-page-active) #actu,body:not(.route-page-active) #video-section,body:not(.route-page-active) #contact{content-visibility:auto;contain-intrinsic-size:auto 760px}}}";
    document.head.appendChild(perfStyle);

    var seen = false;
    try { seen = sessionStorage.getItem("bininga_seen") === "1"; } catch (_) {}
    window.setTimeout(function () {
      var loader = document.getElementById("loader");
      if (loader && !loader.classList.contains("done")) loader.classList.add("done");
      try { sessionStorage.setItem("bininga_seen", "1"); } catch (_) {}
    }, seen ? 0 : 480);
  }

  // ── Contenu éditorial : l'admin est l'unique source de vérité ───────
  // Une ancienne protection réécrivait en permanence plusieurs textes
  // français avec des constantes embarquées dans ce fichier. Résultat :
  // des modifications pourtant sauvegardées depuis l'admin pouvaient être
  // aussitôt remplacées dans le navigateur. Ce bootstrap ne contient plus
  // aucune copie éditoriale. Il ne fait que corriger quelques détails de
  // rendu après que index-core.js a chargé data.json depuis le serveur.
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function editableMultilineHtml(value) {
    var normalized = String(value == null ? "" : value)
      .replace(/\\n/g, "\n")
      .replace(/<br\s*\/?\s*>/gi, "\n");
    return escapeHtml(normalized).replace(/\r?\n/g, "<br> ");
  }

  function applyAdminContentCompatibility() {
    var lang = (document.documentElement.lang || "fr").slice(0, 2).toLowerCase();
    if (lang !== "fr") return true;

    var data = window._FR_DATA;
    if (!data || typeof data !== "object") return false;

    // Engagement : index-core.js historique essaye d'écrire innerHTML sur
    // un Text node. On reconstruit uniquement ce titre à partir des données
    // réellement sauvegardées par l'admin, sans texte codé en dur.
    var engagement = data.engagement || {};
    var engagementTitle = document.getElementById("dyn-eng-title");
    if (engagementTitle && (engagement.title || engagement.titleAccent)) {
      var accent = escapeHtml(engagement.titleAccent || "");
      var desired = editableMultilineHtml(engagement.title || "") +
        (accent ? ' <span class="g" id="dyn-eng-title-accent" data-i18n="eng.title.accent">' + accent + "</span>" : "") +
        " ?";
      if (engagementTitle.innerHTML !== desired) engagementTitle.innerHTML = desired;
    }

    // Les champs ci-dessous sont édités comme texte. Accepter aussi bien un
    // vrai saut de ligne qu'un « \\n » tapé dans l'admin, conformément aux
    // indications affichées dans les formulaires.
    var ctaTitle = document.getElementById("dyn-cta-title");
    if (ctaTitle && data.cta && data.cta.title) {
      var ctaHtml = editableMultilineHtml(data.cta.title);
      if (ctaTitle.innerHTML !== ctaHtml) ctaTitle.innerHTML = ctaHtml;
    }

    var contactSidebar = document.getElementById("dyn-ct-sidebar-title");
    if (contactSidebar && data.contact && data.contact.sidebarTitle) {
      var contactHtml = editableMultilineHtml(data.contact.sidebarTitle);
      if (contactSidebar.innerHTML !== contactHtml) contactSidebar.innerHTML = contactHtml;
    }

    var programmeHero = document.querySelector("#dyn-programme .prog-hero-title");
    if (programmeHero && data.programme && data.programme.heroTitle) {
      var programmeHtml = editableMultilineHtml(data.programme.heroTitle);
      if (programmeHero.innerHTML !== programmeHtml) programmeHero.innerHTML = programmeHtml;
    }

    return true;
  }

  function waitForAdminContent(attempt) {
    if (applyAdminContentCompatibility()) return;
    if (attempt >= 30) return;
    window.setTimeout(function () { waitForAdminContent(attempt + 1); }, 120);
  }

  function scheduleAdminContentCompatibility() {
    window.setTimeout(function () { waitForAdminContent(0); }, 0);
    window.setTimeout(applyAdminContentCompatibility, 250);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleAdminContentCompatibility, { once: true });
  } else {
    scheduleAdminContentCompatibility();
  }
  window.addEventListener("pageshow", scheduleAdminContentCompatibility);

  // Lorsque l'utilisateur revient explicitement au français, index-core.js
  // recharge data.json. Rejouer seulement la compatibilité de rendu ensuite.
  document.addEventListener("click", function (event) {
    var langButton = event.target && event.target.closest ? event.target.closest('[data-lang="fr"]') : null;
    if (!langButton) return;
    window.setTimeout(scheduleAdminContentCompatibility, 300);
  }, { passive: true });

  // ── Analytics métier sans donnée personnelle ────────────
  function track(name, params) {
    if (!window.BiningaAnalytics || typeof window.BiningaAnalytics.track !== "function") return;
    window.BiningaAnalytics.track(name, params || {});
  }

  function surfaceOf(el) {
    if (!el || !el.closest) return "public";
    if (el.closest("#hero")) return "hero";
    if (el.closest("#programme")) return "programme";
    if (el.closest("#engagement")) return "engagement";
    if (el.closest("#contact")) return "contact";
    if (el.closest("#actu")) return "actualites";
    if (el.closest("nav")) return "navigation";
    if (el.closest("footer")) return "footer";
    return "public";
  }

  document.addEventListener("click", function (event) {
    var target = event.target && event.target.closest ? event.target.closest("a,button") : null;
    if (!target) return;

    var lang = target.getAttribute("data-lang");
    if (lang) {
      track("language_change", { language: String(lang).slice(0, 8), surface: surfaceOf(target) });
      return;
    }

    if (target.tagName !== "A") return;
    var href = (target.getAttribute("href") || "").trim();
    if (!href) return;
    var surface = surfaceOf(target);

    if (href === "#form-aud" || href === "#engagement") {
      track("audience_cta_click", { surface: surface });
    } else if (href === "#programme") {
      track("programme_cta_click", { surface: surface });
    } else if (href === "#contact") {
      track("contact_section_click", { surface: surface });
    } else if (href === "#galerie") {
      track("gallery_open", { surface: surface });
    } else if (href.indexOf("#article/") === 0 || href.indexOf("/actualites/") !== -1) {
      track("article_open", { surface: surface });
    }

    if (href.indexOf("tel:") === 0) {
      track("contact_click", { channel: "phone", surface: surface });
      return;
    }
    if (href.indexOf("mailto:") === 0) {
      track("contact_click", { channel: "email", surface: surface });
      return;
    }

    var absolute;
    try { absolute = new URL(href, location.href); } catch (_) { return; }
    if (absolute.origin === location.origin) return;

    var host = absolute.hostname.toLowerCase().replace(/^www\./, "");
    var network = "external";
    if (host.indexOf("facebook.com") !== -1) network = "facebook";
    else if (host.indexOf("instagram.com") !== -1) network = "instagram";
    else if (host.indexOf("linkedin.com") !== -1) network = "linkedin";
    else if (host === "x.com" || host.indexOf("twitter.com") !== -1) network = "x";
    else if (host.indexOf("youtube.com") !== -1 || host === "youtu.be") network = "youtube";
    else if (host.indexOf("wa.me") !== -1 || host.indexOf("whatsapp.com") !== -1) network = "whatsapp";

    track(network === "external" ? "outbound_click" : "social_click", {
      destination: network,
      surface: surface
    });
  }, { passive: true });
})();
