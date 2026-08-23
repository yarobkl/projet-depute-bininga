"""Cycles de veille YARO exécutables dans le temps d'une requête serverless.

Sur Vercel, aucun agent de fond ne tourne : monitor.py (l'agent permanent)
n'existe pas, donc les cycles de veille doivent s'exécuter dans la requête
HTTP elle-même, avec un budget temps strict pour rester sous le timeout de
la fonction. Ce module réutilise les fetchers RSS réels de monitor.py
(Google News, GDELT, presse congolaise, flux juridiques internationaux)
sans les time.sleep de l'agent, et s'arrête proprement quand le budget est
épuisé — les articles récoltés jusque-là sont conservés.
"""
from __future__ import annotations

import time


def _monitor():
    import monitor
    return monitor


def _gnews_fast(m, query: str, timeout: int = 6) -> list[dict]:
    """Flux Google News direct — évite le détour GDELT (timeouts de 15s)."""
    try:
        data = m._fetch(m.google_news_url(query), timeout=timeout)
        return m.parse_rss(data, f"Google News — {query}") if data else []
    except Exception:
        return []


def run_news_quick(data: dict, custom_query: str = "", budget_s: float = 8.0) -> list[dict]:
    """Cycle de veille actualités borné dans le temps.

    Retourne les nouveaux articles (mêmes dicts que monitor.parse_rss),
    dédoublonnés contre data["items"].
    """
    m = _monitor()
    deadline = time.monotonic() + budget_s
    existing = {a.get("id") for a in data.get("items", [])}
    out: list[dict] = []

    def add(articles, category):
        for a in articles or []:
            if a.get("id") and a["id"] not in existing:
                existing.add(a["id"])
                a["category"] = category
                out.append(a)

    if custom_query.strip():
        q = custom_query.strip()
        arts = _gnews_fast(m, q)
        if not arts:  # repli complet (GDELT/Bing) si le flux direct est vide
            try:
                arts = m.fetch_google_news(q)
            except Exception:
                arts = []
        add(arts, "recherche")
        return out

    # Plan de sources par priorité — coupé net à l'épuisement du budget.
    gnews = lambda q: _gnews_fast(m, q)
    plan = (
        [(q, "bininga", gnews) for q in m.QUERIES[:3]]
        + [(q, "loi_justice", gnews) for q in m.LEGAL_QUERIES[:2]]
        + [(u, "bininga", m.fetch_extra_rss) for u in m.EXTRA_RSS[:2]]
        + [(u, "loi_justice", m.fetch_extra_rss) for u in m.LEGAL_RSS[:2]]
    )
    for arg, cat, fn in plan:
        if time.monotonic() >= deadline:
            break
        try:
            add(fn(arg), cat)
        except Exception:
            pass
    return out


def run_yaro_real(themes: list[dict], budget_s: float = 8.0, per_theme: int = 4) -> dict:
    """Bulletins juridiques RÉELS depuis les flux juridiques publics.

    Contrairement au fallback synthétique historique (URLs factices
    yaro-ref.cg), chaque bulletin pointe vers un article authentique.
    Retourne {source_du_theme: [{"titre":..., "url":...}, ...]}.
    """
    m = _monitor()
    deadline = time.monotonic() + budget_s
    pool: list[dict] = []

    # Google News direct d'abord : la source la plus fiable et la plus rapide.
    for q in ("droit justice Congo-Brazzaville OHADA",
              "loi réforme pétrole forêt contrat Congo"):
        if time.monotonic() >= deadline:
            break
        pool += _gnews_fast(m, q)
    for u in getattr(m, "LEGAL_RSS", []):
        if time.monotonic() >= deadline:
            break
        try:
            pool += m.fetch_extra_rss(u) or []
        except Exception:
            pass

    seen, uniq = set(), []
    for a in pool:
        url = (a.get("url") or "").strip()
        titre = (a.get("title") or "").strip()
        if not url or not titre or url in seen:
            continue
        seen.add(url)
        uniq.append({"titre": titre[:300], "url": url, "_text": titre.lower()})

    result: dict[str, list] = {}
    used: set[str] = set()
    for th in themes:
        kws = [k.lower() for k in th.get("keywords", [])]
        kws += [w for w in th.get("sujet", "").lower().split() if len(w) > 5][:4]
        picks = []
        for a in uniq:
            if a["url"] in used:
                continue
            if any(k in a["_text"] for k in kws):
                picks.append({"titre": a["titre"], "url": a["url"]})
                used.add(a["url"])
            if len(picks) >= per_theme:
                break
        # À défaut de correspondance thématique, au moins 2 articles réels
        if len(picks) < 2:
            for a in uniq:
                if a["url"] in used:
                    continue
                picks.append({"titre": a["titre"], "url": a["url"]})
                used.add(a["url"])
                if len(picks) >= 2:
                    break
        result[th.get("source", "?")] = picks
    return result
