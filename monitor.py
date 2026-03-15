#!/usr/bin/env python3
"""
Veille IA — Agent de surveillance des actualités concernant BININGA
====================================================================
Surveille automatiquement Google News et d'autres sources RSS toutes
les 15 minutes pour détecter toute nouvelle information concernant
le Député/Ministre Ange Aimé Wilfrid BININGA.

Démarrage : python3 monitor.py
Arrêt     : Ctrl+C  ou  kill <pid>

Variables d'environnement :
  ANTHROPIC_API_KEY  — optionnel, pour résumés IA des articles
  SMTP_HOST          — serveur SMTP (ex: smtp.gmail.com)
  SMTP_PORT          — port SMTP (défaut: 587)
  SMTP_USER          — email expéditeur
  SMTP_PASS          — mot de passe SMTP
  NOTIF_EMAIL        — email destinataire admin
  MONITOR_INTERVAL   — intervalle en secondes (défaut: 900 = 15 min)
"""

from __future__ import annotations
import os, json, time, hashlib, signal, sys, smtplib, re
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import quote_plus, urlencode
from urllib.error import URLError, HTTPError
from xml.etree import ElementTree as ET
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
NEWS_FILE  = BASE_DIR / "news_monitor.json"
PID_FILE   = BASE_DIR / "monitor.pid"
LOG_PREFIX = "[VEILLE IA]"
INTERVAL   = int(os.environ.get("MONITOR_INTERVAL", 900))   # 15 min par défaut

# ── Fichier de déclenchement manuel ──────────────────────────────────────────
TRIGGER_FILE = BASE_DIR / "monitor.trigger"

# Requêtes de recherche — Actualités Bininga
QUERIES = [
    '"Ange Aimé Bininga"',
    '"Aimé Bininga" Congo',
    '"Bininga" "Garde des Sceaux" Congo',
    '"Bininga" député "Brazzaville"',
    '"Bininga" ministre justice Congo 2026',
    '"BININGA" Congo Brazzaville',
]

# Requêtes de veille juridique mondiale — Lois & Justice
LEGAL_QUERIES = [
    "nouvelles lois justice droits humains 2026",
    "réforme judiciaire Afrique 2026",
    "droits des peuples autochtones nouvelles lois 2026",
    "loi justice réparation populations autochtones",
    "réforme pénitentiaire Afrique subsaharienne",
    "coopération judiciaire internationale Afrique 2026",
    "nouvelles lois droits humains ONU 2026",
    "justice transitionnelle Afrique centrale",
    "réforme code pénal Afrique francophone 2026",
    "OHADA réforme juridique 2026",
    "Cour pénale internationale Afrique actualité 2026",
    "accès à la justice populations vulnérables Afrique",
]

# Sources RSS — presse congolaise
EXTRA_RSS = [
    # Les Dépêches de Brazzaville
    "https://www.lesdepechesdebrazzaville.fr/rss.xml",
    # Adiac-Congo
    "https://www.adiac-congo.com/rss.xml",
]

# Sources RSS — juridiques internationales
LEGAL_RSS = [
    # RFI Afrique (droit, justice, société)
    "https://www.rfi.fr/fr/rss/afrique/",
    # ONU actualités droits de l'homme
    "https://news.un.org/feed/subscribe/fr/news/topic/human-rights/feed/rss.xml",
    # Jeune Afrique
    "https://www.jeuneafrique.com/feed/",
    # Le Monde Afrique
    "https://www.lemonde.fr/afrique/rss_full.xml",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BiningaVeille/1.0; "
        "+https://bininga.cg) Python/3"
    ),
    "Accept": "application/rss+xml,application/xml,text/xml,*/*",
}

MAX_ITEMS = 300   # nombre max d'articles gardés en mémoire
MAX_AGE_DAYS = 30

# ── Signaux ───────────────────────────────────────────────────────────────────

running = True

def _stop(sig, frame):
    global running
    running = False
    _log("Signal reçu — arrêt propre en cours…")

signal.signal(signal.SIGINT,  _stop)
signal.signal(signal.SIGTERM, _stop)

# ── Utilitaires ───────────────────────────────────────────────────────────────

def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{LOG_PREFIX} [{ts}] {msg}", flush=True)


def _item_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def _parse_date(s: str) -> str:
    """Retourne ISO 8601 ou l'original si parsing échoue."""
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            return datetime.strptime(s.strip(), fmt).astimezone(timezone.utc).isoformat()
        except Exception:
            pass
    return s.strip() if s else ""

# ── Persistance ───────────────────────────────────────────────────────────────

def load_news() -> dict:
    try:
        if NEWS_FILE.exists():
            return json.loads(NEWS_FILE.read_text("utf-8"))
    except Exception as e:
        _log(f"Erreur lecture news_monitor.json : {e}")
    return {"items": [], "last_run": None, "stats": {"total_found": 0, "runs": 0}}


def save_news(data: dict):
    try:
        NEWS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    except Exception as e:
        _log(f"Erreur écriture news_monitor.json : {e}")

# ── Fetching ──────────────────────────────────────────────────────────────────

def _fetch(url: str, timeout: int = 15) -> bytes | None:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=timeout) as r:
            return r.read()
    except HTTPError as e:
        _log(f"HTTP {e.code} pour {url}")
    except URLError as e:
        _log(f"URL error {e.reason} pour {url}")
    except Exception as e:
        _log(f"Erreur fetch {url}: {e}")
    return None


def google_news_url(query: str) -> str:
    params = urlencode({"q": query, "hl": "fr", "gl": "CG", "ceid": "CG:fr"})
    return f"https://news.google.com/rss/search?{params}"


def parse_rss(xml_bytes: bytes, source_label: str) -> list[dict]:
    articles = []
    try:
        root = ET.fromstring(xml_bytes)
        # Support atom + rss
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for item in items:
            def _t(tag):
                n = item.find(tag)
                return n.text.strip() if n is not None and n.text else ""
            title   = _strip_tags(_t("title"))
            url     = _t("link") or _t("guid")
            # atom <link> a href= attribute
            if not url:
                lk = item.find("atom:link", ns)
                url = lk.get("href", "") if lk is not None else ""
            summary = _strip_tags(_t("description") or _t("summary") or _t("content"))
            pub     = _parse_date(_t("pubDate") or _t("published") or _t("updated"))
            if not title or not url:
                continue
            articles.append({
                "id":         _item_id(url),
                "title":      title,
                "url":        url,
                "source":     source_label,
                "published":  pub,
                "summary":    summary[:500] if summary else "",
                "ai_summary": "",
                "read":       False,
                "found_at":   datetime.now(timezone.utc).isoformat(),
            })
    except ET.ParseError as e:
        _log(f"ParseError RSS ({source_label}): {e}")
    return articles


def fetch_google_news(query: str) -> list[dict]:
    url = google_news_url(query)
    data = _fetch(url)
    if not data:
        return []
    label = f"Google News — {query}"
    return parse_rss(data, label)


def fetch_extra_rss(rss_url: str) -> list[dict]:
    data = _fetch(rss_url)
    if not data:
        return []
    label = rss_url.split("//")[-1].split("/")[0]
    articles = parse_rss(data, label)
    # Filtrer seulement ceux qui concernent Bininga
    keywords = ["bininga", "ange aimé", "garde des sceaux"]
    filtered = [
        a for a in articles
        if any(k in (a["title"] + a["summary"]).lower() for k in keywords)
    ]
    return filtered

# ── IA — Résumé Claude ─────────────────────────────────────────────────────────

def ai_summarize(article: dict) -> str:
    """Appelle l'API Claude pour résumer un article en français."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return ""
    try:
        import urllib.request as ur
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{
                "role": "user",
                "content": (
                    f"Résume cet article en 2-3 phrases en français, "
                    f"en te concentrant sur ce qui concerne Ange Aimé Wilfrid BININGA.\n\n"
                    f"Titre : {article['title']}\n"
                    f"Résumé brut : {article['summary']}\n"
                    f"Source : {article['source']}\n"
                    f"Date : {article['published']}"
                ),
            }],
        }).encode()
        req = ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with ur.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
            return resp["content"][0]["text"].strip()
    except Exception as e:
        _log(f"Erreur Claude API: {e}")
        return ""

# ── Notifications email ────────────────────────────────────────────────────────

def send_email_notification(new_articles: list[dict]):
    smtp_host  = os.environ.get("SMTP_HOST", "")
    smtp_port  = int(os.environ.get("SMTP_PORT", 587))
    smtp_user  = os.environ.get("SMTP_USER", "")
    smtp_pass  = os.environ.get("SMTP_PASS", "")
    notif_mail = os.environ.get("NOTIF_EMAIL", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass or not notif_mail:
        return   # Email non configuré

    count = len(new_articles)
    subject = f"[Veille BININGA] {count} nouvelle(s) info(s) détectée(s)"

    body_parts = [
        f"<h2>🤖 Veille IA — {count} article(s) détecté(s)</h2>",
        f"<p>Rapport du {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>",
        "<hr>",
    ]
    for a in new_articles[:10]:
        ai = f"<p><em>{a['ai_summary']}</em></p>" if a.get("ai_summary") else ""
        body_parts.append(
            f"<h3><a href='{a['url']}'>{a['title']}</a></h3>"
            f"<p><small>{a['source']} — {a['published']}</small></p>"
            f"<p>{a['summary']}</p>{ai}<hr>"
        )
    if count > 10:
        body_parts.append(f"<p>… et {count - 10} autre(s) article(s). Voir le panneau Veille IA.</p>")

    body_parts.append('<p><a href="https://bininga.cg/admin.html">→ Ouvrir l\'espace admin</a></p>')
    html_body = "\n".join(body_parts)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = notif_mail
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, notif_mail, msg.as_string())
        _log(f"📧 Email envoyé à {notif_mail} ({count} articles)")
    except Exception as e:
        _log(f"Erreur envoi email: {e}")

# ── Cycle principal ────────────────────────────────────────────────────────────

def run_cycle(data: dict, custom_query: str = "") -> list[dict]:
    """Exécute un cycle de veille et retourne les nouveaux articles."""
    existing_ids = {a["id"] for a in data.get("items", [])}
    new_articles: list[dict] = []

    def _add(articles, category):
        for a in articles:
            if a["id"] not in existing_ids:
                existing_ids.add(a["id"])
                a["category"] = category
                new_articles.append(a)

    # Requête personnalisée (déclenchement manuel)
    if custom_query:
        _log(f"Recherche manuelle : {custom_query}")
        _add(fetch_google_news(custom_query), "recherche")
        time.sleep(2)
        return new_articles

    # Google News — Actualités Bininga
    for query in QUERIES:
        _log(f"[Bininga] {query}")
        _add(fetch_google_news(query), "bininga")
        time.sleep(2)

    # Google News — Lois & Justice mondiale
    for query in LEGAL_QUERIES:
        _log(f"[Juridique] {query}")
        _add(fetch_google_news(query), "loi_justice")
        time.sleep(2)

    # Sources RSS — presse congolaise
    for rss_url in EXTRA_RSS:
        _log(f"[RSS Congo] {rss_url}")
        _add(fetch_extra_rss(rss_url), "bininga")
        time.sleep(1)

    # Sources RSS — juridiques internationales
    for rss_url in LEGAL_RSS:
        _log(f"[RSS Juridique] {rss_url}")
        _add(fetch_extra_rss(rss_url), "loi_justice")
        time.sleep(1)

    # Résumés IA (si configuré)
    if os.environ.get("ANTHROPIC_API_KEY") and new_articles:
        _log(f"Résumés IA pour {len(new_articles)} article(s)…")
        for a in new_articles[:8]:
            a["ai_summary"] = ai_summarize(a)
            time.sleep(0.5)

    _log(f"Cycle terminé : {len(new_articles)} nouveau(x) article(s)")
    return new_articles


def main():
    _log("=== Agent de veille BININGA démarré ===")
    _log(f"Intervalle : {INTERVAL // 60} min | Requêtes : {len(QUERIES)}")
    _log(f"Email notifications : {'✅' if os.environ.get('SMTP_HOST') else '⚠️  non configuré'}")
    _log(f"Résumés IA (Claude) : {'✅' if os.environ.get('ANTHROPIC_API_KEY') else '⚠️  non configuré'}")

    # Écrire PID pour gestion externe
    PID_FILE.write_text(str(os.getpid()))

    data = load_news()
    data.setdefault("items", [])
    data.setdefault("stats", {"total_found": 0, "runs": 0})

    while running:
        try:
            # Vérifier si un déclenchement manuel est demandé
            custom_query = ""
            if TRIGGER_FILE.exists():
                try:
                    custom_query = TRIGGER_FILE.read_text(encoding="utf-8").strip()
                    TRIGGER_FILE.unlink(missing_ok=True)
                    _log(f"Déclenchement manuel {'— requête : ' + custom_query if custom_query else '(cycle complet)'}")
                except Exception:
                    pass

            new_articles = run_cycle(data, custom_query=custom_query)

            if new_articles:
                # Insérer en tête (plus récent d'abord)
                data["items"] = new_articles + data["items"]
                # Purger les anciens (> MAX_AGE_DAYS)
                cutoff = (datetime.now(timezone.utc).timestamp() - MAX_AGE_DAYS * 86400)
                def _keep(a):
                    try:
                        from datetime import datetime as _dt
                        ts = _dt.fromisoformat(a.get("found_at", "")).timestamp()
                        return ts > cutoff
                    except Exception:
                        return True
                data["items"] = [a for a in data["items"] if _keep(a)]
                # Garder max MAX_ITEMS
                data["items"] = data["items"][:MAX_ITEMS]

                # Notification email
                send_email_notification(new_articles)

            data["last_run"] = datetime.now(timezone.utc).isoformat()
            data["stats"]["runs"] += 1
            data["stats"]["total_found"] = data["stats"].get("total_found", 0) + len(new_articles)
            save_news(data)

        except Exception as e:
            _log(f"❌ Erreur cycle : {e}")

        if not running:
            break

        _log(f"Prochaine veille dans {INTERVAL // 60} min…")
        # Attendre par tranches de 5 s pour réagir au signal d'arrêt ou au trigger
        waited = 0
        while running and waited < INTERVAL:
            time.sleep(5)
            waited += 5
            if TRIGGER_FILE.exists():
                _log("Trigger détecté — lancement immédiat du cycle")
                break

    PID_FILE.unlink(missing_ok=True)
    _log("Agent arrêté.")


if __name__ == "__main__":
    main()
