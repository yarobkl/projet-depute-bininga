"""Règles de traçabilité appliquées aux actualités administrables."""

from __future__ import annotations


COLLECTIONS = ("slides", "vedettes", "cards")


def news_source_report(data: dict):
    """Retourne ``(sans_url, urls_invalides)`` pour les actualités publiques."""
    unsourced = 0
    invalid = []
    actus = data.get("actus", {}) if isinstance(data, dict) else {}
    for collection in COLLECTIONS:
        rows = actus.get(collection, []) if isinstance(actus, dict) else []
        for index, article in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(article, dict):
                continue
            source_url = str(article.get("sourceUrl") or "").strip()
            if not source_url:
                unsourced += 1
            elif not source_url.startswith(("https://", "http://")):
                invalid.append(f"{collection}[{index}]")
    return unsourced, invalid


def validate_news_source_change(existing: dict, proposed: dict) -> str:
    """Empêche une URL invalide ou l'ajout d'un contenu non sourcé."""
    old_unsourced, _ = news_source_report(existing)
    new_unsourced, invalid = news_source_report(proposed)
    if invalid:
        return "Une URL source doit commencer par https:// ou http://"
    if new_unsourced > old_unsourced:
        return "Renseignez l'URL source de toute nouvelle actualité avant sauvegarde"
    return ""
