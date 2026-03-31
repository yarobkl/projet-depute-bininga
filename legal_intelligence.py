"""
legal_intelligence.py — YARO IA
Veille juridique automatique : scraping multi-sources, filtrage, traduction, stockage SQLite.
Exécution quotidienne à 02h00.
"""

import sqlite3
import time
import datetime
import logging
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("legal_intelligence.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("legal_intel")

# ── Configuration ──────────────────────────────────────────────────────────────

DB_PATH = "news.db"

KEYWORDS = ["pétrole", "forêt", "justice", "contrat"]

SOURCES = [
    {
        "name": "Légifrance",
        "url": "https://www.legifrance.gouv.fr/search/jorf?tab_selection=jorf&searchField=ALL&query=decret&page=1&pageSize=20",
        "lang": "fr",
        "item_tag": "a",
        "item_class": "result-title",
        "base_url": "https://www.legifrance.gouv.fr",
    },
    {
        "name": "JO Sénégal",
        "url": "http://www.jo.gouv.sn/",
        "lang": "fr",
        "item_tag": "a",
        "item_class": None,
        "base_url": "http://www.jo.gouv.sn",
    },
    {
        "name": "JO Côte d'Ivoire",
        "url": "https://www.gouv.ci/actualite.php",
        "lang": "fr",
        "item_tag": "a",
        "item_class": None,
        "base_url": "https://www.gouv.ci",
    },
    {
        "name": "CCJA OHADA",
        "url": "https://www.ohada.com/actualite.html",
        "lang": "fr",
        "item_tag": "a",
        "item_class": None,
        "base_url": "https://www.ohada.com",
    },
]

# ── Base de données ─────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            source    TEXT    NOT NULL,
            titre     TEXT    NOT NULL,
            titre_fr  TEXT,
            url       TEXT    UNIQUE,
            keywords  TEXT,
            lang_orig TEXT    DEFAULT 'fr',
            ts        TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts  ON articles(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_src ON articles(source)")
    conn.commit()
    conn.close()
    log.info("Base de données initialisée : %s", DB_PATH)


def save_article(source, titre, titre_fr, url, keywords_found, lang_orig="fr"):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR IGNORE INTO articles (source, titre, titre_fr, url, keywords, lang_orig) VALUES (?,?,?,?,?,?)",
            (source, titre, titre_fr, url, ",".join(keywords_found), lang_orig),
        )
        conn.commit()
        conn.close()
        log.info("[%s] Sauvegardé : %s", source, titre[:80])
    except sqlite3.Error as e:
        log.error("Erreur SQLite : %s", e)


# ── Traduction ──────────────────────────────────────────────────────────────────

def detect_lang(text):
    """Détection naïve de langue par caractères cyrilliques ou mots anglais fréquents."""
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"
    english_markers = ["the ", "of ", "and ", "for ", "law ", "act ", "decree ", "order "]
    lower = text.lower()
    if sum(1 for m in english_markers if m in lower) >= 2:
        return "en"
    return "fr"


def translate_to_french(text, src_lang):
    """Traduit via googletrans. Retourne le texte original en cas d'échec."""
    if src_lang == "fr":
        return text
    try:
        from googletrans import Translator
        translator = Translator()
        result = translator.translate(text, src=src_lang, dest="fr")
        return result.text
    except Exception as e:
        log.warning("Traduction échouée (%s→fr) : %s", src_lang, e)
        return text


# ── Scraping ────────────────────────────────────────────────────────────────────

class LinkParser(HTMLParser):
    """Extrait les balises <a> avec leurs textes et href."""
    def __init__(self, target_class=None):
        super().__init__()
        self.target_class = target_class
        self.links = []          # [(texte, href)]
        self._current_href = None
        self._current_class = None
        self._capture = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            cls  = attrs_dict.get("class", "")
            if self.target_class:
                if self.target_class in cls:
                    self._current_href = href
                    self._capture = True
                    self._buf = []
            else:
                self._current_href = href
                self._capture = True
                self._buf = []

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._capture:
            texte = " ".join("".join(self._buf).split()).strip()
            if texte and self._current_href:
                self.links.append((texte, self._current_href))
            self._capture = False
            self._buf = []


def fetch_html(url, timeout=15):
    """Télécharge le HTML d'une URL avec headers navigateur."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        log.warning("HTTP %s pour %s", e.code, url)
    except urllib.error.URLError as e:
        log.warning("URL error pour %s : %s", url, e.reason)
    except Exception as e:
        log.warning("Erreur fetch %s : %s", url, e)
    return ""


def contains_keyword(text):
    """Retourne la liste des mots-clés trouvés dans le texte (insensible à la casse)."""
    lower = text.lower()
    return [kw for kw in KEYWORDS if kw in lower]


def resolve_url(href, base_url):
    """Transforme un href relatif en URL absolue."""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base_url.rstrip("/") + href
    return base_url.rstrip("/") + "/" + href


def scrape_source(source):
    """Scrape une source et retourne les articles filtrés."""
    log.info("Scraping [%s] → %s", source["name"], source["url"])
    html = fetch_html(source["url"])
    if not html:
        log.warning("[%s] HTML vide, source ignorée.", source["name"])
        return []

    parser = LinkParser(target_class=source.get("item_class"))
    parser.feed(html)

    results = []
    seen_urls = set()

    for titre_raw, href in parser.links:
        if len(titre_raw) < 15:          # ignore liens trop courts (nav, etc.)
            continue
        if len(titre_raw) > 300:
            titre_raw = titre_raw[:300]

        url = resolve_url(href, source["base_url"])
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Filtrage par mots-clés
        kw_found = contains_keyword(titre_raw)
        if not kw_found:
            continue

        # Détection langue & traduction
        lang_orig = detect_lang(titre_raw)
        titre_fr  = translate_to_french(titre_raw, lang_orig)

        results.append({
            "source":     source["name"],
            "titre":      titre_raw,
            "titre_fr":   titre_fr,
            "url":        url,
            "keywords":   kw_found,
            "lang_orig":  lang_orig,
        })

    log.info("[%s] %d article(s) pertinent(s) trouvé(s).", source["name"], len(results))
    return results


# ── Rapport quotidien ───────────────────────────────────────────────────────────

def print_daily_report():
    conn = sqlite3.connect(DB_PATH)
    today = datetime.date.today().isoformat()
    rows = conn.execute(
        "SELECT source, titre_fr, url, keywords, ts FROM articles WHERE ts >= ? ORDER BY ts DESC",
        (today,),
    ).fetchall()
    conn.close()

    print("\n" + "=" * 70)
    print(f"  RAPPORT YARO IA — Veille juridique du {today}")
    print("=" * 70)
    if not rows:
        print("  Aucun article pertinent collecté aujourd'hui.")
    for source, titre, url, keywords, ts in rows:
        print(f"\n  [{source}]")
        print(f"  Titre  : {titre}")
        print(f"  URL    : {url}")
        print(f"  Mots-clés : {keywords}  |  {ts}")
    print("=" * 70 + "\n")


# ── Exécution principale ────────────────────────────────────────────────────────

def run_once():
    """Lance le scraping de toutes les sources une fois."""
    log.info("=== Démarrage de la veille juridique YARO IA ===")
    init_db()
    total = 0
    for source in SOURCES:
        articles = scrape_source(source)
        for art in articles:
            save_article(
                source   = art["source"],
                titre    = art["titre"],
                titre_fr = art["titre_fr"],
                url      = art["url"],
                keywords_found = art["keywords"],
                lang_orig = art["lang_orig"],
            )
        total += len(articles)
        time.sleep(2)          # pause courtoise entre sources
    log.info("=== Terminé : %d article(s) sauvegardé(s) au total ===", total)
    print_daily_report()


def run_daily():
    """Boucle infinie : attend 02h00 chaque nuit puis lance run_once()."""
    log.info("Mode run_daily activé — exécution programmée à 02h00 chaque nuit.")
    while True:
        now    = datetime.datetime.now()
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        wait_sec = (target - now).total_seconds()
        log.info("Prochaine exécution dans %.0f secondes (%s).", wait_sec, target.strftime("%Y-%m-%d %H:%M"))
        time.sleep(wait_sec)
        run_once()


# ── Point d'entrée ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        # Exécution immédiate pour test
        run_once()
    else:
        # Mode normal : attente 02h00
        run_daily()
