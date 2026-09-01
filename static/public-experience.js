/**
 * Expérience publique du site BININGA.
 * - actualités filtrables et accessibles par URL stable ;
 * - page article avec source et partage ;
 * - tableau de bord du programme sans progression non documentée.
 */
(function () {
  "use strict";

  const DATA_BY_LANG = {
    en: "I18N_DATA_EN",
    es: "I18N_DATA_ES",
    zh: "I18N_DATA_ZH",
    ru: "I18N_DATA_RU"
  };

  const COPY = {
    fr: {
      axis: "Axe", status: "Engagement publié", read: "Lire l'article",
      sourced: "Source externe renseignée", editorial: "Publication éditoriale du site",
      featured: "À lire", archive: "Archive", results: "actualités affichées",
      back: "Retour aux actualités", share: "Partager", copy: "Copier le lien",
      source: "Source externe", sourceNote: "Une source externe est renseignée pour cette publication.",
      sourceLink: "Consulter la publication d'origine", editorialTitle: "Note éditoriale",
      editorialNote: "Cet article est présenté par l'équipe éditoriale du site. Aucune source externe n'est renseignée dans les données publiées.",
      copied: "Lien copié.", shareUnavailable: "Partage indisponible : copiez l'adresse de cette page.",
      notFound: "Article introuvable", notFoundText: "Cette actualité n'existe pas ou son adresse a changé.",
      empty: "Aucune actualité dans cette catégorie.", commitment: "engagement"
    },
    en: {
      axis: "Pillar", status: "Published commitment", read: "Read article",
      sourced: "External source provided", editorial: "Website editorial publication",
      featured: "Featured", archive: "Archive", results: "news items shown",
      back: "Back to news", share: "Share", copy: "Copy link",
      source: "External source", sourceNote: "An external source is provided for this publication.",
      sourceLink: "View the original publication", editorialTitle: "Editorial note",
      editorialNote: "This article is presented by the website's editorial team. No external source is included in the published data.",
      copied: "Link copied.", shareUnavailable: "Sharing is unavailable. Copy this page's address.",
      notFound: "Article not found", notFoundText: "This news item does not exist or its address has changed.",
      empty: "No news in this category.", commitment: "commitment"
    },
    es: {
      axis: "Eje", status: "Compromiso publicado", read: "Leer el artículo",
      sourced: "Fuente externa indicada", editorial: "Publicación editorial del sitio",
      featured: "Destacado", archive: "Archivo", results: "noticias mostradas",
      back: "Volver a noticias", share: "Compartir", copy: "Copiar enlace",
      source: "Fuente externa", sourceNote: "Se indica una fuente externa para esta publicación.",
      sourceLink: "Consultar la publicación original", editorialTitle: "Nota editorial",
      editorialNote: "Este artículo es presentado por el equipo editorial del sitio. Los datos publicados no incluyen una fuente externa.",
      copied: "Enlace copiado.", shareUnavailable: "No se puede compartir. Copie la dirección de esta página.",
      notFound: "Artículo no encontrado", notFoundText: "Esta noticia no existe o su dirección ha cambiado.",
      empty: "No hay noticias en esta categoría.", commitment: "compromiso"
    },
    zh: {
      axis: "方向", status: "已公布承诺", read: "阅读文章",
      sourced: "已注明外部来源", editorial: "网站编辑发布",
      featured: "重点", archive: "资料", results: "条动态",
      back: "返回最新动态", share: "分享", copy: "复制链接",
      source: "外部来源", sourceNote: "本发布内容已注明外部来源。",
      sourceLink: "查看原始发布", editorialTitle: "编辑说明",
      editorialNote: "本文由网站编辑团队发布。已公布的数据中未注明外部来源。",
      copied: "链接已复制。", shareUnavailable: "暂时无法分享，请复制本页地址。",
      notFound: "未找到文章", notFoundText: "该动态不存在或地址已更改。",
      empty: "该类别暂无动态。", commitment: "承诺"
    },
    ru: {
      axis: "Направление", status: "Обязательство опубликовано", read: "Читать статью",
      sourced: "Указан внешний источник", editorial: "Редакционная публикация сайта",
      featured: "Главное", archive: "Архив", results: "новостей показано",
      back: "Вернуться к новостям", share: "Поделиться", copy: "Копировать ссылку",
      source: "Внешний источник", sourceNote: "Для этой публикации указан внешний источник.",
      sourceLink: "Открыть исходную публикацию", editorialTitle: "Примечание редакции",
      editorialNote: "Статья представлена редакцией сайта. В опубликованных данных внешний источник не указан.",
      copied: "Ссылка скопирована.", shareUnavailable: "Поделиться не удалось. Скопируйте адрес страницы.",
      notFound: "Статья не найдена", notFoundText: "Эта новость не существует или её адрес изменился.",
      empty: "В этой категории нет новостей.", commitment: "обязательство"
    }
  };

  let activeFilter = "all";
  let baseTitle = "";
  let baseDescription = "";
  let baseCanonical = "";
  let renderScheduled = false;
  let motionObserver = null;
  let filterRenderToken = 0;
  let surfaceMotionReady = false;
  const openDashboardAxes = new Set([0]);
  const reducedMotionQuery = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : null;

  function motionReduced() {
    return !!(reducedMotionQuery && reducedMotionQuery.matches);
  }

  function runViewTransition(kind, update) {
    const root = document.documentElement;
    if (motionReduced()) {
      update();
      return Promise.resolve();
    }
    if (typeof document.startViewTransition !== "function") {
      root.dataset.motionFallback = kind;
      root.classList.add("motion-fallback-out");
      return new Promise((resolve, reject) => {
        window.setTimeout(() => {
          try {
            update();
          } catch (error) {
            root.classList.remove("motion-fallback-out");
            delete root.dataset.motionFallback;
            reject(error);
            return;
          }
          root.classList.remove("motion-fallback-out");
          root.classList.add("motion-fallback-in");
          window.setTimeout(() => {
            root.classList.remove("motion-fallback-in");
            delete root.dataset.motionFallback;
            resolve();
          }, 360);
        }, kind === "language" ? 110 : 150);
      });
    }
    root.dataset.motionTransition = kind;
    let transition;
    try {
      transition = document.startViewTransition(update);
    } catch (_) {
      delete root.dataset.motionTransition;
      update();
      return Promise.resolve();
    }
    return transition.finished
      .catch(() => {})
      .finally(() => { delete root.dataset.motionTransition; });
  }

  function ensureMotionObserver() {
    if (motionObserver || motionReduced() || !("IntersectionObserver" in window)) return motionObserver;
    motionObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-motion-visible");
        motionObserver.unobserve(entry.target);
      });
    }, { threshold: 0.1, rootMargin: "0px 0px -7% 0px" });
    return motionObserver;
  }

  function prepareMotionElements(elements) {
    const items = Array.from(elements || []);
    const observer = ensureMotionObserver();
    items.forEach((element, index) => {
      element.style.setProperty("--motion-order", String(index % 8));
      if (!observer || motionReduced()) element.classList.add("is-motion-visible");
      else observer.observe(element);
    });
  }

  function clearSharedTransitionNames() {
    document.querySelectorAll("[data-shared-transition]").forEach(element => {
      element.style.removeProperty("view-transition-name");
      element.removeAttribute("data-shared-transition");
    });
  }

  function markSharedElements(container) {
    if (!container) return;
    const image = container.querySelector(".actu-vedette-img img, .actu-card-img img, .article-hero-image");
    const title = container.querySelector(".actu-vedette-title, .actu-card-title, .article-detail-title");
    if (image) {
      image.style.setProperty("view-transition-name", "bininga-article-image");
      image.setAttribute("data-shared-transition", "image");
    }
    if (title) {
      title.style.setProperty("view-transition-name", "bininga-article-title");
      title.setAttribute("data-shared-transition", "title");
    }
  }

  function newsCardForSlug(slug) {
    return Array.from(document.querySelectorAll("[data-article-slug]"))
      .find(element => element.dataset.articleSlug === slug) || null;
  }

  function language() {
    const lang = (document.documentElement.lang || "fr").slice(0, 2).toLowerCase();
    return COPY[lang] ? lang : "fr";
  }

  function words() {
    return COPY[language()];
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function plainLabel(value) {
    return String(value == null ? "" : value).replace(/^\s*📅\s*/, "").trim();
  }

  function slugify(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 96) || "actualite";
  }

  function safeExternalUrl(value) {
    if (!value) return "";
    try {
      const url = new URL(value, location.origin);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
    } catch (_) {
      return "";
    }
  }

  function safeImage(value) {
    const image = String(value || "").trim();
    if (!image || /^(?:javascript|data):/i.test(image)) return "";
    return image;
  }

  function mergeArray(baseItems, translatedItems) {
    const base = Array.isArray(baseItems) ? baseItems : [];
    const translated = Array.isArray(translatedItems) ? translatedItems : [];
    return base.map((item, index) => {
      const merged = Object.assign({}, item || {}, translated[index] || {});
      if (Array.isArray(item && item.points)) {
        merged.points = Array.isArray(translated[index] && translated[index].points)
          ? translated[index].points
          : item.points;
      }
      if (Array.isArray(item && item.tags)) {
        merged.tags = Array.isArray(translated[index] && translated[index].tags)
          ? translated[index].tags
          : item.tags;
      }
      return merged;
    });
  }

  function localizedData() {
    const base = window._FR_DATA;
    if (!base) return null;
    const lang = language();
    if (lang === "fr") return base;
    const translated = window[DATA_BY_LANG[lang]] || {};
    const programmeBase = base.programme || {};
    const programmeTranslated = translated.programme || {};
    const actusBase = base.actus || {};
    const actusTranslated = translated.actus || {};
    return Object.assign({}, base, translated, {
      programme: Object.assign({}, programmeBase, programmeTranslated, {
        axes: mergeArray(programmeBase.axes, programmeTranslated.axes)
      }),
      actus: Object.assign({}, actusBase, actusTranslated, {
        vedettes: mergeArray(actusBase.vedettes, actusTranslated.vedettes),
        cards: mergeArray(actusBase.cards, actusTranslated.cards),
        slides: mergeArray(actusBase.slides, actusTranslated.slides)
      })
    });
  }

  function dateForCard(item) {
    return [item.day, item.month, item.year].filter(Boolean).join(" ");
  }

  function buildRecords(data) {
    const baseActus = (window._FR_DATA && window._FR_DATA.actus) || {};
    const actus = (data && data.actus) || {};
    const featured = mergeArray(baseActus.vedettes, actus.vedettes).map((item, index) => ({
      kind: "featured",
      index,
      slug: slugify(((baseActus.vedettes || [])[index] || {}).title || item.title),
      title: item.title || "",
      summary: item.text1 || "",
      body2: item.text2 || "",
      quote: item.quote || "",
      category: item.tag || "",
      date: plainLabel(item.date || ""),
      image: safeImage(item.image),
      tags: Array.isArray(item.tags) ? item.tags : [],
      sourceUrl: safeExternalUrl(item.sourceUrl),
      sourceLabel: item.sourceLabel || item.source || ""
    }));
    const featuredSlugs = new Set(featured.map(item => item.slug));
    const cards = mergeArray(baseActus.cards, actus.cards).map((item, index) => ({
      kind: "card",
      index,
      slug: slugify(((baseActus.cards || [])[index] || {}).title || item.title),
      title: item.title || "",
      summary: item.desc || "",
      body2: "",
      quote: "",
      category: item.cat || "",
      date: dateForCard(item),
      day: item.day || "",
      month: item.month || "",
      year: item.year || "",
      image: safeImage(item.image),
      tags: [],
      sourceUrl: safeExternalUrl(item.sourceUrl),
      sourceLabel: item.sourceLabel || item.source || ""
    })).filter(item => !featuredSlugs.has(item.slug));
    const bySlug = new Map();
    featured.concat(cards).forEach(item => {
      if (!bySlug.has(item.slug)) bySlug.set(item.slug, item);
    });
    return { featured, cards, bySlug };
  }

  function normalized(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
  }

  function recordCategory(record) {
    const text = normalized([record.title, record.category].concat(record.tags || []).join(" "));
    if (/(ewo|cuvette|village|terrain|energie|emploi|education|jeunesse|bourse|campagne)/.test(text)) return "terrain";
    if (/(diplom|cooperation|international|rwanda|france|aiea|ambassadeur)/.test(text)) return "diplomacy";
    if (/(justice|droit|magistr|autochtone|detention|penitent|epu|onu)/.test(text)) return "justice";
    return "institutions";
  }

  function articleHref(slug) {
    return "/actualites/" + encodeURIComponent(slug);
  }

  function sourceMark(record) {
    const copy = words();
    return `<span class="experience-source-mark${record.sourceUrl ? " is-sourced" : ""}">${escapeHtml(record.sourceUrl ? copy.sourced : copy.editorial)}</span>`;
  }

  function featureTemplate(record, index) {
    const copy = words();
    const image = record.image
      ? `<img src="${escapeHtml(record.image)}" alt="${escapeHtml(record.title)}" loading="lazy" decoding="async">`
      : `<div class="gal-slide-placeholder"><span class="placeholder-mark">AB</span></div>`;
    return `<article class="actu-vedette motion-reveal" data-article-slug="${escapeHtml(record.slug)}" style="--motion-order:${index || 0}">
      <div class="actu-vedette-img">${image}</div>
      <div class="actu-vedette-body">
        <div class="actu-vedette-tag">${escapeHtml(record.category)}</div>
        <div class="actu-vedette-date">${escapeHtml(record.date)}</div>
        <h3 class="actu-vedette-title">${escapeHtml(record.title)}</h3>
        <p class="actu-vedette-txt">${escapeHtml(record.summary)}</p>
        <a class="experience-read-link" href="${articleHref(record.slug)}">${escapeHtml(copy.read)}<span class="sr-only"> : ${escapeHtml(record.title)}</span></a>
        ${sourceMark(record)}
      </div>
    </article>`;
  }

  function cardTemplate(record, index) {
    const copy = words();
    const isFeatured = record.kind === "featured";
    const day = isFeatured ? copy.featured : (record.day || record.year || copy.archive);
    const month = isFeatured
      ? escapeHtml(record.date)
      : (record.day
          ? [record.month, record.year].filter(Boolean).map(escapeHtml).join("<br>")
          : escapeHtml(copy.archive));
    return `<article class="actu-card experience-news-card motion-reveal${record.image ? " actu-card-has-img" : ""}${isFeatured ? " is-feature-derived" : ""}" data-article-slug="${escapeHtml(record.slug)}" style="--motion-order:${index || 0}">
      ${record.image ? `<div class="actu-card-img"><img src="${escapeHtml(record.image)}" alt="${escapeHtml(record.title)}" loading="lazy" decoding="async"></div>` : ""}
      <div class="actu-card-cat">${escapeHtml(record.category)}</div>
      <div class="actu-card-dt"><span class="actu-card-day">${escapeHtml(day)}</span><span class="actu-card-mon">${month}</span></div>
      <h3 class="actu-card-title">${escapeHtml(record.title)}</h3>
      <p class="actu-card-desc">${escapeHtml(record.summary)}</p>
      <a class="experience-read-link" href="${articleHref(record.slug)}">${escapeHtml(copy.read)}<span class="sr-only"> : ${escapeHtml(record.title)}</span></a>
      ${sourceMark(record)}
    </article>`;
  }

  function filtered(records) {
    return activeFilter === "all" ? records : records.filter(item => recordCategory(item) === activeFilter);
  }

  function renderNewsNow(data) {
    const featuredWrap = document.getElementById("actu-vedettes-wrap");
    const cardsGrid = document.getElementById("actu-cards-grid");
    const resultCount = document.getElementById("news-result-count");
    if (!featuredWrap || !cardsGrid) return;
    const records = buildRecords(data);
    const featuredMatches = filtered(records.featured);
    const cardMatches = filtered(records.cards);
    const heroItems = featuredMatches.slice(0, 3);
    const gridItems = featuredMatches.slice(3).concat(cardMatches);
    const total = featuredMatches.length + cardMatches.length;
    const copy = words();

    featuredWrap.innerHTML = heroItems.length
      ? `<div class="experience-feature-list">${heroItems.map(featureTemplate).join("")}</div>`
      : "";
    cardsGrid.innerHTML = gridItems.length
      ? gridItems.map(cardTemplate).join("")
      : `<div class="experience-empty">${escapeHtml(copy.empty)}</div>`;
    if (resultCount) resultCount.textContent = `${total} ${copy.results}`;
    document.querySelectorAll(".news-filter").forEach(button => {
      const selected = button.dataset.filter === activeFilter;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
    prepareMotionElements(featuredWrap.querySelectorAll(".motion-reveal"));
    prepareMotionElements(cardsGrid.querySelectorAll(".motion-reveal"));
  }

  function clearNewsFilteringState() {
    document.querySelectorAll("#actu-vedettes-wrap, #actu-cards-grid, .news-result-count").forEach(region => {
      region.classList.remove("is-filtering-out", "is-filtering-in");
    });
    const newsSection = document.getElementById("actu");
    if (newsSection) newsSection.removeAttribute("aria-busy");
  }

  function renderNews(data, options) {
    const animate = !!(options && options.animate) && !motionReduced();
    if (!animate) {
      filterRenderToken += 1;
      clearNewsFilteringState();
      renderNewsNow(data);
      return;
    }
    const token = ++filterRenderToken;
    const featuredWrap = document.getElementById("actu-vedettes-wrap");
    const cardsGrid = document.getElementById("actu-cards-grid");
    const resultCount = document.getElementById("news-result-count");
    const regions = [featuredWrap, cardsGrid, resultCount].filter(Boolean);
    regions.forEach(region => region.classList.add("is-filtering-out"));
    const newsSection = document.getElementById("actu");
    if (newsSection) newsSection.setAttribute("aria-busy", "true");
    window.setTimeout(() => {
      if (token !== filterRenderToken) {
        clearNewsFilteringState();
        return;
      }
      renderNewsNow(data);
      clearNewsFilteringState();
      regions.forEach(region => {
        if (typeof region.animate !== "function") return;
        region.animate(
          [{ opacity: 0, transform: "translate3d(0,10px,0)" }, { opacity: 1, transform: "translate3d(0,0,0)" }],
          { duration: 340, easing: "cubic-bezier(.22,1,.36,1)" }
        );
      });
    }, 150);
  }

  function renderDashboard(data) {
    const grid = document.getElementById("ewo-dashboard-grid");
    if (!grid) return;
    const axes = (((data || {}).programme || {}).axes || []);
    const commitments = axes.reduce((total, axis) => total + (Array.isArray(axis.points) ? axis.points.length : 0), 0);
    const axisCount = document.getElementById("dashboard-axis-count");
    const commitmentCount = document.getElementById("dashboard-commitment-count");
    if (axisCount) axisCount.textContent = String(axes.length);
    if (commitmentCount) commitmentCount.textContent = String(commitments);
    const copy = words();
    const mobile = window.matchMedia && window.matchMedia("(max-width: 600px)").matches;
    grid.innerHTML = axes.map((axis, index) => {
      const expanded = !mobile || openDashboardAxes.has(index);
      const contentId = `dashboard-axis-content-${index + 1}`;
      return `<article class="dashboard-card motion-reveal${expanded ? "" : " is-collapsed"}" data-axis-index="${index}" style="--motion-order:${index}">
        <button class="dashboard-card-toggle" type="button" aria-expanded="${expanded ? "true" : "false"}" aria-controls="${contentId}">
          <span class="dashboard-card-head">
            <span class="dashboard-card-number" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
            <span><span class="dashboard-card-kicker">${escapeHtml(copy.axis)} ${String(index + 1).padStart(2, "0")}</span><span class="dashboard-card-title">${escapeHtml(axis.title || "")}</span></span>
          </span>
          <span class="dashboard-card-chevron" aria-hidden="true"></span>
        </button>
        <div class="dashboard-card-content" id="${contentId}">
          <div class="dashboard-card-content-inner">
            <p>${escapeHtml(axis.text || "")}</p>
            <ul class="dashboard-commitments">${(axis.points || []).map(point => `<li>${escapeHtml(point)}</li>`).join("")}</ul>
            <span class="dashboard-status">${escapeHtml(copy.status)}</span>
          </div>
        </div>
      </article>`;
    }).join("");
    prepareMotionElements(grid.querySelectorAll(".motion-reveal"));
  }

  function articleSlugFromLocation() {
    const pathMatch = location.pathname.match(/^\/actualites\/([^/]+)\/?$/);
    if (pathMatch) {
      try { return decodeURIComponent(pathMatch[1]); } catch (_) { return pathMatch[1]; }
    }
    const hashMatch = location.hash.match(/^#article\/([^?]+)/);
    if (!hashMatch) return "";
    try { return decodeURIComponent(hashMatch[1]); } catch (_) { return hashMatch[1]; }
  }

  function rememberBaseMetadata(data) {
    if (!baseTitle) baseTitle = ((data || {}).seo || {}).title || document.title;
    if (!baseDescription) {
      const meta = document.querySelector('meta[name="description"]');
      baseDescription = (((data || {}).seo || {}).description || (meta && meta.content) || "");
    }
    if (!baseCanonical) {
      const canonical = document.querySelector('link[rel="canonical"]');
      baseCanonical = (canonical && canonical.href) || (location.origin + "/");
    }
  }

  function setMeta(selector, attribute, value) {
    const element = document.querySelector(selector);
    if (element && value) element.setAttribute(attribute, value);
  }

  function metadataExcerpt(value) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (text.length <= 180) return text;
    const shortened = text.slice(0, 179).replace(/\s+\S*$/, "").replace(/[\s,;:]+$/, "");
    return (shortened || text.slice(0, 176)) + "…";
  }

  function setArticleMetadata(record) {
    const description = metadataExcerpt(record.summary);
    const url = location.origin + articleHref(record.slug);
    const image = record.image ? new URL(record.image, location.origin).href : "";
    document.title = `${record.title} · Aimé BININGA`;
    setMeta('meta[name="description"]', "content", description);
    setMeta('link[rel="canonical"]', "href", url);
    setMeta('meta[property="og:type"]', "content", "article");
    setMeta('meta[property="og:url"]', "content", url);
    setMeta('meta[property="og:title"]', "content", record.title);
    setMeta('meta[property="og:description"]', "content", description);
    if (image) {
      setMeta('meta[property="og:image"]', "content", image);
      setMeta('meta[name="twitter:image"]', "content", image);
    }
    setMeta('meta[name="twitter:title"]', "content", record.title);
    setMeta('meta[name="twitter:description"]', "content", description);
    let jsonLd = document.getElementById("article-jsonld");
    if (!jsonLd) {
      jsonLd = document.createElement("script");
      jsonLd.id = "article-jsonld";
      jsonLd.type = "application/ld+json";
      document.head.appendChild(jsonLd);
    }
    jsonLd.textContent = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      headline: record.title,
      description,
      image: image ? [image] : undefined,
      mainEntityOfPage: url,
      publisher: { "@type": "Organization", name: "Site officiel d'Ange Aimé Wilfrid BININGA" }
    });
  }

  function restoreBaseMetadata() {
    if (!baseTitle) return;
    document.title = baseTitle;
    setMeta('meta[name="description"]', "content", baseDescription);
    setMeta('link[rel="canonical"]', "href", baseCanonical);
    setMeta('meta[property="og:type"]', "content", "website");
    setMeta('meta[property="og:url"]', "content", baseCanonical);
    setMeta('meta[property="og:title"]', "content", baseTitle);
    setMeta('meta[property="og:description"]', "content", baseDescription);
    setMeta('meta[name="twitter:title"]', "content", baseTitle);
    setMeta('meta[name="twitter:description"]', "content", baseDescription);
    const jsonLd = document.getElementById("article-jsonld");
    if (jsonLd) jsonLd.remove();
  }

  function sourceAside(record) {
    const copy = words();
    if (record.sourceUrl) {
      let host = "";
      try { host = new URL(record.sourceUrl).hostname.replace(/^www\./, ""); } catch (_) {}
      const label = record.sourceLabel || host || copy.sourceLink;
      return `<aside class="article-aside">
        <span class="article-aside-label">${escapeHtml(copy.source)}</span>
        <p class="article-source-note">${escapeHtml(copy.sourceNote)}</p>
        <a class="article-source-link" href="${escapeHtml(record.sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(copy.sourceLink)} · ${escapeHtml(label)}</a>
        <div class="article-tags">${record.tags.map(tag => `<span class="article-tag">${escapeHtml(tag)}</span>`).join("")}</div>
      </aside>`;
    }
    return `<aside class="article-aside">
      <span class="article-aside-label">${escapeHtml(copy.editorialTitle)}</span>
      <p class="article-source-note">${escapeHtml(copy.editorialNote)}</p>
      <div class="article-tags">${record.tags.map(tag => `<span class="article-tag">${escapeHtml(tag)}</span>`).join("")}</div>
    </aside>`;
  }

  function renderArticle(data) {
    const container = document.getElementById("article-detail-content");
    if (!container) return;
    rememberBaseMetadata(data);
    const slug = articleSlugFromLocation();
    if (!slug) {
      container.innerHTML = "";
      delete container.dataset.articleSlug;
      restoreBaseMetadata();
      makeArticleNavigationLeaveCleanly();
      return;
    }
    document.body.classList.add("route-page-active", "route-page-article");
    const records = buildRecords(data);
    const record = records.bySlug.get(slug);
    container.dataset.articleSlug = slug;
    const copy = words();
    if (!record) {
      container.innerHTML = `<div class="article-not-found"><h1>${escapeHtml(copy.notFound)}</h1><p>${escapeHtml(copy.notFoundText)}</p><a class="article-action" href="/#actu">${escapeHtml(copy.back)}</a></div>`;
      return;
    }
    setArticleMetadata(record);
    container.innerHTML = `
      <a class="article-back" href="/#actu">${escapeHtml(copy.back)}</a>
      <div class="article-eyebrow"><span class="article-category">${escapeHtml(record.category)}</span><span class="article-date">${escapeHtml(record.date)}</span></div>
      <h1 class="article-detail-title">${escapeHtml(record.title)}</h1>
      <div class="article-actions">
        <button class="article-action" type="button" id="article-share">${escapeHtml(copy.share)}</button>
        <button class="article-action" type="button" id="article-copy">${escapeHtml(copy.copy)}</button>
      </div>
      ${record.image ? `<img class="article-hero-image" src="${escapeHtml(record.image)}" alt="${escapeHtml(record.title)}" decoding="async">` : ""}
      <div class="article-layout">
        <article class="article-prose">
          ${record.summary ? `<p>${escapeHtml(record.summary)}</p>` : ""}
          ${record.quote ? `<blockquote>${escapeHtml(record.quote)}</blockquote>` : ""}
          ${record.body2 ? `<p>${escapeHtml(record.body2)}</p>` : ""}
        </article>
        ${sourceAside(record)}
      </div>
      <p class="article-share-status" id="article-share-status" role="status" aria-live="polite"></p>`;
    if (document.documentElement.dataset.motionTransition && document.documentElement.dataset.motionTransition.indexOf("article") === 0) {
      markSharedElements(container);
    }
    prepareMotionElements(container.querySelectorAll(".article-eyebrow, .article-actions, .article-layout"));
    bindShare(record);
  }

  async function copyArticleLink(url) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(url);
      return;
    }
    const input = document.createElement("textarea");
    input.value = url;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
  }

  function bindShare(record) {
    const share = document.getElementById("article-share");
    const copyButton = document.getElementById("article-copy");
    const status = document.getElementById("article-share-status");
    const url = location.origin + articleHref(record.slug);
    async function copyLink() {
      try {
        await copyArticleLink(url);
        if (status) status.textContent = words().copied;
        if (copyButton) {
          const original = copyButton.textContent;
          copyButton.textContent = words().copied.replace(/[.!。]$/, "");
          copyButton.classList.add("is-success");
          window.setTimeout(() => {
            copyButton.textContent = original;
            copyButton.classList.remove("is-success");
          }, 1800);
        }
      } catch (_) {
        if (status) status.textContent = words().shareUnavailable;
      }
    }
    if (copyButton) copyButton.addEventListener("click", copyLink);
    if (share) share.addEventListener("click", async () => {
      if (!navigator.share) {
        await copyLink();
        return;
      }
      try {
        await navigator.share({ title: record.title, text: record.summary, url });
      } catch (error) {
        if (!error || error.name !== "AbortError") await copyLink();
      }
    });
  }

  function makeArticleNavigationLeaveCleanly() {
    const articleRoute = !!articleSlugFromLocation() && location.pathname.startsWith("/actualites/");
    document.querySelectorAll("a").forEach(link => {
      const savedHref = link.dataset.homeHref;
      if (!articleRoute && savedHref) {
        link.setAttribute("href", savedHref);
        delete link.dataset.homeHref;
        return;
      }
      if (!articleRoute) return;
      const href = link.getAttribute("href");
      if (href && href.startsWith("#") && href !== "#") {
        link.dataset.homeHref = href;
        link.setAttribute("href", "/" + href);
      }
    });
  }

  function updateRoutePresentation() {
    if (typeof updateRouteSections === "function") updateRouteSections();
    else {
      const articleRoute = !!articleSlugFromLocation();
      document.body.classList.toggle("route-page-active", articleRoute);
      document.body.classList.toggle("route-page-article", articleRoute);
    }
    setActiveNavigation(articleSlugFromLocation() ? "actu" : (location.hash.slice(1) || "hero"));
  }

  function articleSlugFromHref(href) {
    try {
      const url = new URL(href, location.href);
      if (url.origin !== location.origin) return "";
      const match = url.pathname.match(/^\/actualites\/([^/]+)\/?$/);
      return match ? decodeURIComponent(match[1]) : "";
    } catch (_) {
      return "";
    }
  }

  function handleArticleNavigation(event) {
    const link = event.target.closest("a");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.classList.contains("article-back")) {
      if (history.state && history.state.biningaView === "article") {
        event.preventDefault();
        history.back();
      }
      return;
    }
    if (!link.classList.contains("experience-read-link")) return;
    const slug = articleSlugFromHref(link.href);
    if (!slug) return;
    event.preventDefault();
    const returnScroll = window.scrollY;
    const currentState = Object.assign({}, history.state || {}, {
      biningaView: "news",
      biningaFilter: activeFilter,
      biningaScroll: returnScroll,
      biningaLastArticle: slug
    });
    history.replaceState(currentState, "", location.href);
    clearSharedTransitionNames();
    markSharedElements(link.closest("[data-article-slug]"));
    runViewTransition("article-forward", () => {
      history.pushState({
        biningaView: "article",
        biningaFilter: activeFilter,
        biningaReturnScroll: returnScroll,
        biningaArticle: slug
      }, "", articleHref(slug));
      updateRoutePresentation();
      renderAll();
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }).finally(clearSharedTransitionNames);
  }

  function handleHistoryNavigation(event) {
    const state = event.state || {};
    const destinationSlug = articleSlugFromLocation();
    const articleContainer = document.getElementById("article-detail-content");
    const leavingSlug = document.body.classList.contains("route-page-article") && articleContainer
      ? (articleContainer.dataset.articleSlug || "")
      : "";
    if (state.biningaFilter) activeFilter = state.biningaFilter;
    clearSharedTransitionNames();
    if (leavingSlug) markSharedElements(document.getElementById("article-detail-content"));
    else if (destinationSlug) markSharedElements(newsCardForSlug(destinationSlug));
    const kind = destinationSlug ? "article-forward" : "article-back";
    runViewTransition(kind, () => {
      updateRoutePresentation();
      renderAll();
      if (destinationSlug) {
        markSharedElements(document.getElementById("article-detail-content"));
        window.scrollTo({ top: 0, left: 0, behavior: "auto" });
      } else {
        markSharedElements(newsCardForSlug(state.biningaLastArticle || leavingSlug));
        const targetScroll = Number.isFinite(state.biningaScroll) ? state.biningaScroll : 0;
        window.scrollTo({ top: targetScroll, left: 0, behavior: "auto" });
        window.setTimeout(() => window.scrollTo({ top: targetScroll, left: 0, behavior: "auto" }), 90);
      }
    }).finally(clearSharedTransitionNames);
  }

  function setActiveNavigation(sectionId) {
    const activeId = document.body.classList.contains("route-page-article") ? "actu" : sectionId;
    document.querySelectorAll(".nlinks a, .mob-nav a").forEach(link => {
      const href = (link.dataset.homeHref || link.getAttribute("href") || "").replace(/^\//, "");
      const current = href === "#" + activeId;
      link.classList.toggle("is-current", current);
      if (current) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function setupActiveNavigation() {
    const sections = ["hero", "missions", "about", "programme", "ewo-dashboard", "actu", "engagement", "contact"]
      .map(id => document.getElementById(id)).filter(Boolean);
    if (!("IntersectionObserver" in window)) return;
    const ratios = new Map();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => ratios.set(entry.target.id, entry.isIntersecting ? entry.intersectionRatio : 0));
      const active = Array.from(ratios.entries()).sort((a, b) => b[1] - a[1])[0];
      if (active && active[1] > 0) setActiveNavigation(active[0]);
    }, { threshold: [0.12, 0.3, 0.55], rootMargin: "-20% 0px -55% 0px" });
    sections.forEach(section => observer.observe(section));
    setActiveNavigation(document.body.classList.contains("route-page-article") ? "actu" : (location.hash.slice(1) || "hero"));
  }

  function toggleDashboardAxis(button) {
    if (!window.matchMedia || !window.matchMedia("(max-width: 600px)").matches) return;
    const card = button.closest(".dashboard-card");
    if (!card) return;
    const index = Number(card.dataset.axisIndex);
    const expanded = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", expanded ? "false" : "true");
    card.classList.toggle("is-collapsed", expanded);
    if (expanded) openDashboardAxes.delete(index);
    else openDashboardAxes.add(index);
  }

  function installSurfaceMotionHooks() {
    const originalThemeToggle = window.toggleBiningaTheme;
    if (typeof originalThemeToggle === "function" && !originalThemeToggle.motionEnhanced) {
      const enhancedThemeToggle = function () {
        if (!surfaceMotionReady) return originalThemeToggle();
        return runViewTransition("theme", originalThemeToggle);
      };
      enhancedThemeToggle.motionEnhanced = true;
      window.toggleBiningaTheme = enhancedThemeToggle;
    }
    const originalApplyI18n = window.applyI18n;
    if (typeof originalApplyI18n === "function" && !originalApplyI18n.motionEnhanced) {
      const enhancedApplyI18n = function (lang) {
        if (!surfaceMotionReady) return originalApplyI18n(lang);
        return runViewTransition("language", () => {
          originalApplyI18n(lang);
          renderAll();
        });
      };
      enhancedApplyI18n.motionEnhanced = true;
      window.applyI18n = enhancedApplyI18n;
    }
  }

  function renderAll() {
    const data = localizedData();
    if (!data) return false;
    rememberBaseMetadata(data);
    renderDashboard(data);
    renderNews(data);
    renderArticle(data);
    makeArticleNavigationLeaveCleanly();
    return true;
  }

  function scheduleRender(delay) {
    if (renderScheduled) return;
    renderScheduled = true;
    window.setTimeout(() => {
      renderScheduled = false;
      renderAll();
    }, delay || 0);
  }

  function waitForData(attempt) {
    if (renderAll()) return;
    if (attempt < 40) window.setTimeout(() => waitForData(attempt + 1), 100);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const filters = document.getElementById("news-filters");
    if (filters) filters.addEventListener("click", event => {
      const button = event.target.closest("button[data-filter]");
      if (!button) return;
      activeFilter = button.dataset.filter || "all";
      const data = localizedData();
      if (data) renderNews(data, { animate: true });
    });
    const dashboard = document.getElementById("ewo-dashboard-grid");
    if (dashboard) dashboard.addEventListener("click", event => {
      const button = event.target.closest(".dashboard-card-toggle");
      if (button) toggleDashboardAxis(button);
    });
    document.addEventListener("click", handleArticleNavigation);
    window.addEventListener("popstate", handleHistoryNavigation);
    setupActiveNavigation();
    waitForData(0);
    window.setTimeout(() => { surfaceMotionReady = true; }, 0);
  });
  installSurfaceMotionHooks();
  document.addEventListener("bininga:dataloaded", () => scheduleRender(0));
  document.addEventListener("bininga:languagechange", () => scheduleRender(0));
  window.addEventListener("hashchange", () => scheduleRender(0));
})();
