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
  // L'ancienne tentative remplaçait la photo principale par une ressource
  // WebP absente. On conserve donc bininga.jpg et on optimise uniquement
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
