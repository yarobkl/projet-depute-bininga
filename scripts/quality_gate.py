#!/usr/bin/env python3
"""Contrôle qualité public BININGA, exécutable localement et en CI."""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MAX_LEGACY_UNSOURCED = 18


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.assets = []
        self.dialogs = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta":
            key = values.get("property") or values.get("name")
            if key:
                self.meta[key] = values.get("content", "")
        if tag == "script" and values.get("src"):
            self.assets.append(values["src"])
        if tag == "link" and values.get("href", "").startswith("static/"):
            self.assets.append(values["href"])
        if values.get("role") == "dialog" and values.get("aria-modal") == "true":
            self.dialogs += 1


def local_path(value: str) -> Path | None:
    parsed = urlparse(value)
    if parsed.scheme in ("http", "https"):
        if parsed.netloc != "projet-depute-bininga.vercel.app":
            return None
        value = parsed.path
    value = value.split("?", 1)[0].lstrip("/")
    if not value or ".." in Path(value).parts:
        return None
    return ROOT / value


def main() -> int:
    errors = []
    warnings = []
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(html)

    required_meta = ("description", "og:title", "og:description", "og:image", "twitter:image")
    for key in required_meta:
        if not parser.meta.get(key, "").strip():
            errors.append(f"Métadonnée absente : {key}")
    social_image = local_path(parser.meta.get("og:image", ""))
    if social_image is None or not social_image.is_file():
        errors.append("L'image Open Graph n'existe pas dans le dépôt")
    if parser.meta.get("og:image") != parser.meta.get("twitter:image"):
        errors.append("Les images Open Graph et Twitter divergent")

    for asset in parser.assets:
        path = local_path(asset)
        if path is not None and not path.is_file():
            errors.append(f"Ressource HTML introuvable : {asset}")

    if "https://yaroconsulting.fr/" not in html or ">YaroConsulting</a>" not in html:
        errors.append("Crédit développeur YaroConsulting incomplet")
    if parser.dialogs < 4:
        errors.append("Les modales publiques ne déclarent pas toutes leur rôle accessible")

    bootstrap = (ROOT / "static" / "index.js").read_text(encoding="utf-8")
    if "XMLHttpRequest" in bootstrap or re.search(r"\.open\([^\n]+,\s*false\s*\)", bootstrap):
        errors.append("Le bootstrap public contient encore un chargement XHR synchrone")

    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    articles = []
    for collection in ("slides", "vedettes", "cards"):
        for article in data.get("actus", {}).get(collection, []) or []:
            if not isinstance(article, dict):
                errors.append(f"Actualité invalide dans {collection}")
                continue
            articles.append(article)
            image = str(article.get("image") or "").strip()
            if image:
                path = local_path(image)
                if path is not None and not path.is_file():
                    errors.append(f"Image d'actualité introuvable : {image}")
            source_url = str(article.get("sourceUrl") or "").strip()
            if source_url and not source_url.startswith(("https://", "http://")):
                errors.append(f"URL de source invalide : {source_url}")
            if article.get("publication_source") == "editorial_ia" and not (
                source_url or str(article.get("sourceLabel") or "").strip()
            ):
                errors.append("Une publication éditoriale publiée est dépourvue de source")

    unsourced = sum(not str(article.get("sourceUrl") or "").strip() for article in articles)
    if unsourced > MAX_LEGACY_UNSOURCED:
        errors.append(
            f"Le nombre d'actualités historiques sans URL source augmente ({unsourced} > {MAX_LEGACY_UNSOURCED})"
        )
    elif unsourced:
        warnings.append(
            f"{unsourced} actualités historiques restent sans URL source ; aucune source n'a été inventée"
        )

    for warning in warnings:
        print(f"AVERTISSEMENT: {warning}")
    if errors:
        for error in errors:
            print(f"ERREUR: {error}", file=sys.stderr)
        return 1
    print(
        f"OK qualité institutionnelle — {len(articles)} actualités, "
        f"{len(articles) - unsourced} sourcées, métadonnées et ressources valides"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
