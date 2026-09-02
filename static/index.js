// Bootstrap correctif exécuté avant index-core.js.
// Le cœur est désormais chargé par une balise defer standard : aucun XHR
// synchrone ne bloque plus le fil principal du navigateur.
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

})();
