// Bootstrap correctif — conserve le script historique intact dans index-core.js.
// Le rendu dynamique utilisait rObs hors de sa portée lexicale, ce qui arrêtait
// loadContent() avant la Galerie et les Actualités.
(function () {
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

  try {
    // Chargement synchrone volontaire ici : index.js est déjà un script defer.
    // Le cœur doit être exécuté avant DOMContentLoaded pour préserver tous ses listeners.
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/static/index-core.js?v=20260901-public-experience", false);
    xhr.send(null);
    if (xhr.status < 200 || xhr.status >= 300) {
      throw new Error("index-core.js HTTP " + xhr.status);
    }
    var core = document.createElement("script");
    core.text = xhr.responseText;
    document.head.appendChild(core);
    core.remove();
  } catch (err) {
    console.error("Chargement du script principal impossible", err);
  }
})();
