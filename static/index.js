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

  // ── Voix éditoriale : présentation personnelle en première personne ──
  // Les actualités et contenus journalistiques restent volontairement à la
  // troisième personne. Ce garde-fou ne s'applique qu'à la version française
  // des surfaces où le candidat parle directement aux visiteurs.
  var FIRST_PERSON_FR = {
    heroSubtitle: "Je suis un homme de terrain, de conviction et de résultats. Mon engagement est au service du peuple congolais et de la Cuvette-Ouest.",
    heroProgramme: "Mon programme",
    aboutTag: "Qui suis-je ?",
    aboutBadge: "Ma circonscription",
    aboutTitle: 'Mon parcours, forgé par <span class="r">le terrain</span>',
    aboutIntro: "Je suis Ange Aimé Wilfrid BININGA. Docteur en droit, Inspecteur principal du Trésor, Député d'Ewo et Garde des Sceaux, j'ai construit mon parcours autour d'une exigence : servir l'État et les citoyens avec rigueur, responsabilité et attachement à mon pays.",
    aboutParagraphs: [
      "Né à Brazzaville, j'ai grandi avec le sens du devoir et du service public. Titulaire d'un doctorat en droit, j'ai intégré la haute fonction publique et gravi les échelons à la Direction générale du Trésor public jusqu'au rang d'Inspecteur principal, une fonction qui exige rigueur, intégrité et maîtrise des finances de l'État. J'ai également mis mon expérience au service de la Direction générale de la Santé, où j'ai exercé des fonctions stratégiques de conseiller ministériel. Ce parcours m'a permis de construire une double expertise, juridique et administrative, au service de l'État.",
      "En 2016, le Président de la République m'a confié le portefeuille de Ministre de la Fonction publique et de la Réforme de l'État. J'ai alors engagé mon action dans la modernisation de l'administration congolaise, l'emploi des jeunes fonctionnaires et les réformes structurelles nécessaires à la diversification économique nationale. Le 19 août 2017, les électeurs de la 1re circonscription d'Ewo m'ont accordé leur confiance en m'élisant Député à l'Assemblée Nationale. Cette confiance constitue pour moi une responsabilité durable envers Ewo et la Cuvette-Ouest.",
      "En tant que Ministre de la Justice, j'ai porté en 2018 la loi instituant la Haute Autorité de lutte contre la corruption. Adopté par 107 voix pour, 6 contre et 1 abstention, ce texte a marqué une étape importante dans le renforcement du cadre institutionnel de lutte contre la corruption et l'impunité. Je considère cette réforme comme l'un des engagements majeurs de mon action publique.",
      "Aujourd'hui, en qualité de Garde des Sceaux, Ministre de la Justice, des Droits Humains et de la Promotion des Peuples Autochtones, je porte la voix du Congo dans les dossiers relevant de mes responsabilités, au niveau national comme international. En février 2026, j'ai conduit à Paris des échanges avec mon homologue français Gérald Darmanin afin de moderniser la coopération judiciaire entre le Congo et la France. Juriste, réformateur et homme de terrain, je défends une vision exigeante du service de l'État, fondée sur la responsabilité, la justice et l'efficacité publique."
    ],
    parcoursTag: "Mon parcours",
    parcoursDescriptions: [
      "Docteur en droit, j'ai bâti une carrière de cadre supérieur de l'État au sein de la Direction générale du Trésor public, avant de rejoindre la Santé comme conseiller stratégique du ministre.",
      "Militant du Parti Congolais du Travail, je me suis engagé activement dans la vie politique d'Ewo et de la Cuvette-Ouest, avec la volonté de porter les aspirations de ma communauté.",
      "Nommé par le Président de la République au sein du premier gouvernement de la nouvelle République, j'ai porté la modernisation de l'administration publique et l'emploi des jeunes, deux enjeux essentiels de la diversification économique nationale.",
      "Le 19 août 2017, les électeurs de la 1re circonscription d'Ewo m'ont élu Député à l'Assemblée Nationale de la République du Congo. Depuis, je représente Ewo et la Cuvette-Ouest avec la responsabilité liée à cette confiance.",
      "En tant que Ministre de la Justice, j'ai piloté l'adoption par 107 députés de la loi créant la Haute Autorité de lutte contre la corruption en 2018, institution indépendante dotée du droit de saisine directe des instances judiciaires.",
      "À ce poste clé du gouvernement, je porte la diplomatie judiciaire du Congo. En février 2026 à Paris, j'ai notamment engagé la modernisation de la coopération judiciaire Congo-France, fondée sur un accord vieux de plus de cinquante ans.",
      "Fort de mon expérience gouvernementale et de mon engagement à Ewo, je me présente aux prochaines élections législatives avec un programme ambitieux pour Ewo et le Congo."
    ],
    programmeTag: "Ma vision",
    programmeHeroText: "Chaque engagement de mon programme est issu de mes échanges directs avec les habitants d'Ewo, les chefs de village, les jeunes, les femmes entrepreneures et les professionnels de santé et d'éducation.",
    programmeEmployment: "Fort de mon expérience au Ministère de la Fonction publique, je porte un plan ambitieux pour l'emploi des jeunes et la dignité des travailleurs d'Ewo."
  };

  var firstPersonScheduled = false;
  function setTextIfDifferent(id, value) {
    var el = document.getElementById(id);
    if (el && el.textContent !== value) el.textContent = value;
  }
  function setHtmlIfDifferent(id, value) {
    var el = document.getElementById(id);
    if (el && el.innerHTML !== value) el.innerHTML = value;
  }
  function applyFirstPersonFrenchCopy() {
    firstPersonScheduled = false;
    var lang = (document.documentElement.lang || "fr").slice(0, 2).toLowerCase();
    if (lang !== "fr") return;

    setTextIfDifferent("dyn-sub", FIRST_PERSON_FR.heroSubtitle);
    setTextIfDifferent("dyn-hero-btn2", FIRST_PERSON_FR.heroProgramme);
    setTextIfDifferent("dyn-about-tag", FIRST_PERSON_FR.aboutTag);
    setTextIfDifferent("dyn-about-badge-lbl", FIRST_PERSON_FR.aboutBadge);
    setHtmlIfDifferent("dyn-about-title", FIRST_PERSON_FR.aboutTitle);
    setTextIfDifferent("dyn-about-intro", FIRST_PERSON_FR.aboutIntro);
    setTextIfDifferent("dyn-parcours-tag", FIRST_PERSON_FR.parcoursTag);
    setTextIfDifferent("dyn-prog-tag", FIRST_PERSON_FR.programmeTag);

    var aboutBody = document.getElementById("dyn-about-body");
    if (aboutBody) {
      var current = Array.from(aboutBody.querySelectorAll("p")).map(function (p) { return p.textContent; });
      if (current.join("\n") !== FIRST_PERSON_FR.aboutParagraphs.join("\n")) {
        aboutBody.innerHTML = FIRST_PERSON_FR.aboutParagraphs.map(function (text) {
          var p = document.createElement("p");
          p.className = "about-body";
          p.textContent = text;
          return p.outerHTML;
        }).join("");
      }
    }

    var timelineDescriptions = document.querySelectorAll("#dyn-parcours .tl-desc");
    FIRST_PERSON_FR.parcoursDescriptions.forEach(function (text, index) {
      var el = timelineDescriptions[index];
      if (el && el.textContent !== text) el.textContent = text;
    });

    var progHeroText = document.querySelector("#dyn-programme .prog-hero-sub");
    if (progHeroText && progHeroText.textContent !== FIRST_PERSON_FR.programmeHeroText) {
      progHeroText.textContent = FIRST_PERSON_FR.programmeHeroText;
    }
    var employmentCard = Array.from(document.querySelectorAll("#dyn-programme .prog-card")).find(function (card) {
      return /Emploi\s*&\s*Travail décent/i.test(card.querySelector(".prog-title")?.textContent || "");
    });
    var employmentText = employmentCard && employmentCard.querySelector(".prog-txt");
    if (employmentText && employmentText.textContent !== FIRST_PERSON_FR.programmeEmployment) {
      employmentText.textContent = FIRST_PERSON_FR.programmeEmployment;
    }
  }

  function scheduleFirstPersonFrenchCopy() {
    if (firstPersonScheduled) return;
    firstPersonScheduled = true;
    Promise.resolve().then(applyFirstPersonFrenchCopy);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleFirstPersonFrenchCopy, { once: true });
  } else {
    scheduleFirstPersonFrenchCopy();
  }
  if ("MutationObserver" in window && document.documentElement) {
    new MutationObserver(scheduleFirstPersonFrenchCopy).observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["lang"]
    });
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
