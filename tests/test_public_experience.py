#!/usr/bin/env python3
"""Contrats statiques de l'expérience publique BININGA."""

from __future__ import annotations

import json
import pathlib
import re
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def main() -> None:
    html = read("index.html")
    core = read("static/index-core.js")
    experience = read("static/public-experience.js")
    i18n = read("static/i18n.js")
    server = read("server.py")
    public_server = read("server_public.py")
    data = json.loads(read("data.json"))

    # Les nouveaux parcours publics existent et leurs ressources sont chargées.
    for section_id in ("missions", "ewo-dashboard", "article-detail"):
        assert f'id="{section_id}"' in html, section_id
    assert "static/public-experience.css" in html
    assert "static/public-experience.js" in html
    assert '<base href="/">' in html

    # Les trois responsabilités sont explicites et distinctes.
    assert html.count('class="mission-card') == 3
    for key in ("missions.minister.title", "missions.deputy.title", "missions.project.title"):
        assert f'data-i18n="{key}"' in html

    # Le tableau de bord dérive uniquement des engagements effectivement publiés.
    axes = data["programme"]["axes"]
    assert len(axes) == 6
    assert sum(len(axis.get("points", [])) for axis in axes) == 18
    assert "Aucun pourcentage d'avancement" in html
    assert "Engagement publié" in experience
    assert 'class="progress' not in experience.lower()

    # Les actualités ont des URL stables, un partage et une provenance explicite.
    for marker in (
        '"/actualites/"',
        "navigator.share",
        "navigator.clipboard",
        "sourceUrl",
        "Note éditoriale",
        "NewsArticle",
    ):
        assert marker in experience, marker
    assert '"article"' in core and "route-page-article" in core
    assert "/actualites/" in server and "/actualites/" in public_server
    assert "_inject_public_article_metadata" in server
    assert 'article-server-jsonld' in server
    assert '"og:type", "article"' in server
    assert sum(bool(item.get("sourceUrl")) for item in data["actus"]["vedettes"] + data["actus"]["cards"]) >= 8

    # Les transitions restent fonctionnelles, progressives et accessibles.
    motion_css = read("static/public-experience.css")
    for marker in (
        "document.startViewTransition",
        "history.pushState",
        'window.addEventListener("popstate"',
        "biningaScroll",
        "is-filtering-out",
        "dashboard-card-toggle",
        "prefers-reduced-motion",
    ):
        assert marker in experience or marker in motion_css, marker
    for marker in (
        "::view-transition-group(bininga-article-image)",
        ".nlinks a.is-current",
        ".mob-nav.open a:nth-child",
        ".dashboard-card.is-collapsed",
        "transition-delay:calc(var(--motion-order,0) * 55ms)",
    ):
        assert marker in motion_css, marker

    # Accessibilité et performance des médias secondaires.
    assert 'aria-label="Image précédente"' in core
    assert 'aria-label="Image suivante"' in core
    assert 'aria-label="Afficher l\'image ${i+1}"' in core
    assert core.count('decoding="async"') >= 8
    assert 'media="(min-width:901px)" srcset="images/bininga-hero.webp"' in html
    assert 'fetchpriority="high"' in html
    assert 'sessionStorage.getItem("bininga_seen")' in html
    assert "content-visibility:auto" in motion_css
    assert "max-age=31536000, immutable" in server
    assert re.search(r'<div class="social-row"\s+hidden\s+aria-hidden="true">', html)
    assert 'id="contact-phone-item" hidden' in html
    assert 'id="contact-social-item" hidden' in html
    assert "+242 06 XXX XXXX" not in html

    # Les libellés structurants existent dans les cinq langues.
    for key in ("nav.missions", "nav.tracking", "dashboard.title", "news.filter.justice"):
        assert i18n.count(f'"{key}"') == 5, key

    # Référencement et attribution corrects.
    production = "https://projet-depute-bininga.vercel.app/"
    assert f'<link rel="canonical" href="{production}">' in html
    assert 'href="https://yaroconsulting.fr/"' in html
    assert ">YaroConsulting</a>" in html
    sitemap = ET.parse(ROOT / "sitemap.xml")
    urls = [node.text or "" for node in sitemap.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert len(urls) >= 20
    assert all(url.startswith(production) for url in urls)

    # Les erreurs typographiques françaises repérées pendant l'audit sont corrigées.
    serialized = json.dumps(data, ensure_ascii=False)
    for corrected in ("Journée internationale", "Genève", "avancées appréciables", "Législatives 2017", "conditions de détention"):
        assert corrected in serialized, corrected

    print("✅ Expérience publique — contrats valides")


if __name__ == "__main__":
    main()
