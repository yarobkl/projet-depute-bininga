/**
 * Google Analytics 4 + consentement visiteurs pour le site BININGA.
 *
 * Principe de confidentialité :
 * - le SDK Google n'est jamais téléchargé avant un accord explicite ;
 * - Consent Mode v2 refuse par défaut les stockages Analytics et publicitaires ;
 * - aucune donnée saisie dans les formulaires n'est envoyée à Analytics ;
 * - le refus est aussi simple que l'acceptation et peut être modifié à tout moment.
 */
(function () {
  "use strict";

  const MEASUREMENT_ID = "G-N283W7662X";
  const STORAGE_KEY = "bininga_cookie_consent";
  const CONSENT_VERSION = 1;
  const CONSENT_LIFETIME_MS = 180 * 24 * 60 * 60 * 1000;
  const ANALYTICS_COOKIE_LIFETIME_SECONDS = 13 * 30 * 24 * 60 * 60;

  const COPY = {
    fr: {
      title: "Votre choix en matière de cookies",
      summary: "Avec votre accord, Google Analytics nous aide à comprendre la fréquentation du site et à améliorer ses contenus. Aucun cookie de mesure n'est déposé avant votre choix.",
      essential: "Cookies nécessaires",
      essentialText: "Toujours actifs · fonctionnement, sécurité et mémorisation de votre choix.",
      analytics: "Mesure d'audience",
      analyticsText: "Google Analytics 4 · pages consultées, interactions et origine générale du trafic.",
      accept: "Tout accepter",
      reject: "Tout refuser",
      customize: "Personnaliser",
      save: "Enregistrer mes choix",
      back: "Retour",
      learn: "Consulter la politique des cookies",
      manage: "Modifier mes préférences de cookies",
      dialog: "Préférences relatives aux cookies"
    },
    en: {
      title: "Your cookie choices",
      summary: "With your permission, Google Analytics helps us understand site traffic and improve content. No analytics cookie is stored before you choose.",
      essential: "Necessary cookies",
      essentialText: "Always active · operation, security and storage of your choice.",
      analytics: "Audience measurement",
      analyticsText: "Google Analytics 4 · pages viewed, interactions and general traffic source.",
      accept: "Accept all",
      reject: "Reject all",
      customize: "Customise",
      save: "Save my choices",
      back: "Back",
      learn: "Read the cookie policy",
      manage: "Change my cookie preferences",
      dialog: "Cookie preferences"
    },
    es: {
      title: "Sus preferencias de cookies",
      summary: "Con su permiso, Google Analytics nos ayuda a conocer el tráfico del sitio y mejorar su contenido. No se instala ninguna cookie de medición antes de su elección.",
      essential: "Cookies necesarias",
      essentialText: "Siempre activas · funcionamiento, seguridad y memorización de su elección.",
      analytics: "Medición de audiencia",
      analyticsText: "Google Analytics 4 · páginas consultadas, interacciones y origen general del tráfico.",
      accept: "Aceptar todo",
      reject: "Rechazar todo",
      customize: "Personalizar",
      save: "Guardar mis preferencias",
      back: "Volver",
      learn: "Consultar la política de cookies",
      manage: "Modificar mis preferencias de cookies",
      dialog: "Preferencias de cookies"
    },
    zh: {
      title: "Cookie 选择",
      summary: "经您同意，Google Analytics 可帮助我们了解网站访问情况并改进内容。在您作出选择前，不会存放任何统计 Cookie。",
      essential: "必要 Cookie",
      essentialText: "始终启用 · 用于网站运行、安全及保存您的选择。",
      analytics: "访问统计",
      analyticsText: "Google Analytics 4 · 浏览页面、互动及流量的大致来源。",
      accept: "全部接受",
      reject: "全部拒绝",
      customize: "自定义",
      save: "保存我的选择",
      back: "返回",
      learn: "查看 Cookie 政策",
      manage: "修改 Cookie 偏好",
      dialog: "Cookie 偏好"
    },
    ru: {
      title: "Настройки файлов cookie",
      summary: "С вашего согласия Google Analytics помогает нам оценивать посещаемость и улучшать материалы сайта. Аналитические cookie не сохраняются до вашего выбора.",
      essential: "Необходимые cookie",
      essentialText: "Всегда активны · работа сайта, безопасность и сохранение вашего выбора.",
      analytics: "Измерение аудитории",
      analyticsText: "Google Analytics 4 · просмотренные страницы, взаимодействия и общий источник трафика.",
      accept: "Принять все",
      reject: "Отклонить все",
      customize: "Настроить",
      save: "Сохранить выбор",
      back: "Назад",
      learn: "Открыть политику cookie",
      manage: "Изменить настройки cookie",
      dialog: "Настройки cookie"
    }
  };

  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = window.gtag || gtag;

  // Consent Mode v2 : aucun stockage ni usage publicitaire par défaut.
  window.gtag("consent", "default", {
    analytics_storage: "denied",
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    wait_for_update: 500
  });
  window.gtag("set", "ads_data_redaction", true);
  window.gtag("set", "url_passthrough", false);

  let state = readState();
  let analyticsConfigured = false;
  let analyticsLoading = false;
  let lastPageKey = "";
  let banner = null;
  let preferencesOpen = false;

  function currentLanguage() {
    const value = (document.documentElement.lang || "fr").slice(0, 2).toLowerCase();
    return COPY[value] ? value : "fr";
  }

  function words() {
    return COPY[currentLanguage()];
  }

  function readState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!parsed || parsed.version !== CONSENT_VERSION) return null;
      if (typeof parsed.analytics !== "boolean") return null;
      if (!Number.isFinite(parsed.expiresAt) || parsed.expiresAt <= Date.now()) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }
      return parsed;
    } catch (_) {
      return null;
    }
  }

  function storeState(analytics) {
    const next = {
      version: CONSENT_VERSION,
      necessary: true,
      analytics: !!analytics,
      decidedAt: new Date().toISOString(),
      expiresAt: Date.now() + CONSENT_LIFETIME_MS
    };
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch (_) {}
    state = next;
    return next;
  }

  function analyticsAllowed() {
    return !!(state && state.analytics === true && state.expiresAt > Date.now());
  }

  function safeLocation() {
    try {
      const url = new URL(location.href);
      url.search = "";
      return url.toString();
    } catch (_) {
      return location.origin + location.pathname + location.hash;
    }
  }

  function pageKey() {
    return location.pathname + location.hash;
  }

  function sendPageView(force) {
    if (!analyticsAllowed() || !analyticsConfigured) return;
    const key = pageKey();
    if (!force && key === lastPageKey) return;
    lastPageKey = key;
    window.gtag("event", "page_view", {
      page_title: document.title,
      page_location: safeLocation(),
      page_path: key
    });
  }

  function loadAnalytics() {
    if (!analyticsAllowed()) return;

    window.gtag("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied"
    });

    if (!analyticsLoading) {
      analyticsLoading = true;
      const script = document.createElement("script");
      script.async = true;
      script.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(MEASUREMENT_ID);
      script.id = "bininga-google-analytics";
      document.head.appendChild(script);
    }

    if (!analyticsConfigured) {
      analyticsConfigured = true;
      window.gtag("js", new Date());
      window.gtag("config", MEASUREMENT_ID, {
        send_page_view: false,
        anonymize_ip: true,
        allow_google_signals: false,
        allow_ad_personalization_signals: false,
        cookie_expires: ANALYTICS_COOKIE_LIFETIME_SECONDS,
        cookie_update: true,
        transport_type: "beacon"
      });
      sendPageView(true);
    }
  }

  function deleteAnalyticsCookies() {
    const names = document.cookie.split(";").map(part => part.split("=")[0].trim())
      .filter(name => /^(_ga|_gid|_gat)/.test(name));
    const host = location.hostname.replace(/^www\./, "");
    const domains = ["", location.hostname, "." + host];
    names.forEach(name => {
      domains.forEach(domain => {
        const suffix = domain ? "; domain=" + domain : "";
        document.cookie = name + "=; Max-Age=0; path=/" + suffix + "; SameSite=Lax";
      });
    });
  }

  function disableAnalytics() {
    window.gtag("consent", "update", {
      analytics_storage: "denied",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied"
    });
    window["ga-disable-" + MEASUREMENT_ID] = true;
    deleteAnalyticsCookies();
  }

  function enableAnalytics() {
    window["ga-disable-" + MEASUREMENT_ID] = false;
    loadAnalytics();
  }

  function emitChange() {
    const detail = { necessary: true, analytics: analyticsAllowed() };
    document.dispatchEvent(new CustomEvent("bininga:consentchange", { detail }));
  }

  function applyChoice(analytics) {
    storeState(analytics);
    if (analytics) enableAnalytics();
    else disableAnalytics();
    hideBanner();
    emitChange();
  }

  function setText(selector, value) {
    if (!banner) return;
    const element = banner.querySelector(selector);
    if (element) element.textContent = value;
  }

  function renderCopy() {
    if (!banner) return;
    const copy = words();
    banner.setAttribute("aria-label", copy.dialog);
    setText("[data-cookie-title]", copy.title);
    setText("[data-cookie-summary]", copy.summary);
    setText("[data-cookie-essential]", copy.essential);
    setText("[data-cookie-essential-text]", copy.essentialText);
    setText("[data-cookie-analytics]", copy.analytics);
    setText("[data-cookie-analytics-text]", copy.analyticsText);
    setText("[data-cookie-accept]", copy.accept);
    setText("[data-cookie-reject]", copy.reject);
    setText("[data-cookie-customize]", copy.customize);
    setText("[data-cookie-save]", copy.save);
    setText("[data-cookie-back]", copy.back);
    setText("[data-cookie-learn]", copy.learn);
    const toggle = banner.querySelector("#bininga-analytics-consent");
    if (toggle) toggle.setAttribute("aria-label", copy.analytics);
    document.querySelectorAll("[data-cookie-manage]").forEach(button => {
      button.textContent = copy.manage;
    });
  }

  function showSummary() {
    if (!banner) return;
    preferencesOpen = false;
    banner.querySelector("[data-cookie-summary-view]").hidden = false;
    banner.querySelector("[data-cookie-preferences-view]").hidden = true;
  }

  function showPreferences() {
    if (!banner) createBanner();
    preferencesOpen = true;
    banner.querySelector("[data-cookie-summary-view]").hidden = true;
    banner.querySelector("[data-cookie-preferences-view]").hidden = false;
    const toggle = banner.querySelector("#bininga-analytics-consent");
    if (toggle) toggle.checked = analyticsAllowed();
    showBanner();
    window.setTimeout(() => {
      const heading = banner.querySelector("[data-cookie-title]");
      if (heading) heading.focus();
    }, 0);
  }

  function showBanner() {
    if (!banner) return;
    banner.hidden = false;
    document.body.classList.add("cookie-consent-open");
    requestAnimationFrame(() => banner.classList.add("is-visible"));
  }

  function hideBanner() {
    if (!banner) return;
    banner.classList.remove("is-visible");
    document.body.classList.remove("cookie-consent-open");
    window.setTimeout(() => {
      if (!banner.classList.contains("is-visible")) banner.hidden = true;
    }, 220);
  }

  function installPolicyButton() {
    const body = document.querySelector("#modal-cookies .lmodal-body");
    if (!body || body.querySelector("[data-cookie-manage]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "cookie-policy-manage";
    button.setAttribute("data-cookie-manage", "");
    button.addEventListener("click", function () {
      if (typeof window.closeLegal === "function") window.closeLegal("cookies");
      showPreferences();
    });
    body.appendChild(button);
  }

  function createBanner() {
    if (banner || !document.body) return;
    banner = document.createElement("section");
    banner.id = "bininga-cookie-consent";
    banner.className = "cookie-consent";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-modal", "false");
    banner.setAttribute("aria-live", "polite");
    banner.hidden = true;
    banner.innerHTML = `
      <div class="cookie-consent-inner">
        <div class="cookie-consent-copy">
          <span class="cookie-consent-mark" aria-hidden="true">AB</span>
          <div>
            <h2 class="cookie-consent-title" data-cookie-title tabindex="-1"></h2>
            <p class="cookie-consent-summary" data-cookie-summary></p>
          </div>
        </div>
        <div data-cookie-summary-view>
          <div class="cookie-consent-actions">
            <button type="button" class="cookie-action cookie-action-reject" data-cookie-reject></button>
            <button type="button" class="cookie-action cookie-action-accept" data-cookie-accept></button>
          </div>
          <div class="cookie-consent-links">
            <button type="button" data-cookie-customize></button>
            <button type="button" data-cookie-learn></button>
          </div>
        </div>
        <div class="cookie-preferences" data-cookie-preferences-view hidden>
          <div class="cookie-preference-row">
            <div><strong data-cookie-essential></strong><span data-cookie-essential-text></span></div>
            <span class="cookie-always-on" aria-hidden="true">✓</span>
          </div>
          <label class="cookie-preference-row" for="bininga-analytics-consent">
            <div><strong data-cookie-analytics></strong><span data-cookie-analytics-text></span></div>
            <span class="cookie-switch"><input id="bininga-analytics-consent" type="checkbox"><span aria-hidden="true"></span></span>
          </label>
          <div class="cookie-consent-actions">
            <button type="button" class="cookie-action cookie-action-reject" data-cookie-back></button>
            <button type="button" class="cookie-action cookie-action-accept" data-cookie-save></button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(banner);

    banner.querySelector("[data-cookie-accept]").addEventListener("click", () => applyChoice(true));
    banner.querySelector("[data-cookie-reject]").addEventListener("click", () => applyChoice(false));
    banner.querySelector("[data-cookie-customize]").addEventListener("click", showPreferences);
    banner.querySelector("[data-cookie-back]").addEventListener("click", showSummary);
    banner.querySelector("[data-cookie-save]").addEventListener("click", () => {
      const toggle = banner.querySelector("#bininga-analytics-consent");
      applyChoice(!!(toggle && toggle.checked));
    });
    banner.querySelector("[data-cookie-learn]").addEventListener("click", () => {
      if (typeof window.openLegal === "function") window.openLegal("cookies");
    });
    renderCopy();
  }

  function cleanEventParams(params) {
    const blocked = /(email|mail|phone|telephone|name|nom|prenom|address|adresse|message|reason|raison|code)/i;
    const output = {};
    Object.entries(params || {}).slice(0, 20).forEach(([key, value]) => {
      if (blocked.test(key) || !/^[a-z][a-z0-9_]{0,39}$/i.test(key)) return;
      if (typeof value === "number" && Number.isFinite(value)) {
        output[key] = value;
        return;
      }
      if (typeof value !== "string" && typeof value !== "boolean") return;
      const clean = String(value).replace(/\s+/g, " ").trim().slice(0, 100);
      if (!clean || /@/.test(clean) || /\+?\d[\d\s().-]{7,}/.test(clean)) return;
      output[key] = clean;
    });
    return output;
  }

  function track(name, params) {
    if (!analyticsAllowed() || !analyticsConfigured) return false;
    if (!/^[a-z][a-z0-9_]{0,39}$/.test(String(name || ""))) return false;
    window.gtag("event", name, cleanEventParams(params));
    return true;
  }

  function onAnalytics(callback) {
    if (typeof callback !== "function") return;
    if (analyticsAllowed()) {
      callback();
      return;
    }
    const listener = event => {
      if (!event.detail || !event.detail.analytics) return;
      document.removeEventListener("bininga:consentchange", listener);
      callback();
    };
    document.addEventListener("bininga:consentchange", listener);
  }

  function trackLink(event) {
    const link = event.target.closest && event.target.closest("a[href]");
    if (!link || !analyticsAllowed()) return;
    let url;
    try { url = new URL(link.href, location.href); } catch (_) { return; }
    const label = (link.textContent || link.getAttribute("aria-label") || "link").trim().slice(0, 80);
    if (url.origin !== location.origin) {
      track("click", { link_domain: url.hostname, link_text: label, outbound: true });
    } else if (/\.(pdf|docx?|xlsx?|pptx?|zip)$/i.test(url.pathname)) {
      track("file_download", { file_name: url.pathname.split("/").pop() || "download" });
    }
  }

  function installLocationTracking() {
    ["pushState", "replaceState"].forEach(method => {
      const original = history[method];
      if (typeof original !== "function" || original.__biningaAnalyticsWrapped) return;
      const wrapped = function () {
        const result = original.apply(this, arguments);
        window.setTimeout(() => sendPageView(false), 0);
        return result;
      };
      wrapped.__biningaAnalyticsWrapped = true;
      history[method] = wrapped;
    });
    window.addEventListener("popstate", () => window.setTimeout(() => sendPageView(false), 0));
    window.addEventListener("hashchange", () => window.setTimeout(() => sendPageView(false), 0));
    document.addEventListener("click", trackLink, { passive: true });
  }

  window.BiningaConsent = Object.freeze({
    measurementId: MEASUREMENT_ID,
    hasAnalyticsConsent: analyticsAllowed,
    getState: () => state ? Object.assign({}, state) : null,
    openPreferences: showPreferences,
    acceptAll: () => applyChoice(true),
    rejectAll: () => applyChoice(false),
    onAnalytics
  });
  window.BiningaAnalytics = Object.freeze({
    measurementId: MEASUREMENT_ID,
    track,
    pageView: () => sendPageView(true)
  });

  if (analyticsAllowed()) enableAnalytics();
  else disableAnalytics();
  installLocationTracking();

  document.addEventListener("DOMContentLoaded", function () {
    createBanner();
    installPolicyButton();
    renderCopy();
    if (!state) {
      showSummary();
      showBanner();
    }
  }, { once: true });

  document.addEventListener("bininga:languagechange", renderCopy);
})();
