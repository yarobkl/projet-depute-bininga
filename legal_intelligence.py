"""
legal_intelligence.py — YARO IA Veille Juridique
Génération de bulletins de veille juridique via l'API Gemini (+ fallback Groq).
Exécution quotidienne à 02h00 (ou manuellement via --now).
"""

from __future__ import annotations
import sqlite3, time, datetime, logging, json, os, secrets
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("legal_intelligence.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("legal_intel")

# ── Configuration ───────────────────────────────────────────────────────────────

DB_PATH = "news.db"

# Thèmes de veille — adaptés au Député-Ministre BININGA (Justice, Congo-Brazzaville)
THEMES = [
    {
        "source":   "OHADA Info",
        "sujet":    "droit OHADA et droit des affaires en Afrique centrale",
        "keywords": ["contrat", "OHADA"],
    },
    {
        "source":   "JO Congo",
        "sujet":    "Journal Officiel du Congo-Brazzaville — textes législatifs et réglementaires récents",
        "keywords": ["loi", "décret", "réforme"],
    },
    {
        "source":   "Justice Congo",
        "sujet":    "réforme judiciaire et système de justice au Congo-Brazzaville",
        "keywords": ["justice", "tribunal", "réforme"],
    },
    {
        "source":   "Énergie Congo",
        "sujet":    "réglementation pétrolière, minière et énergétique au Congo-Brazzaville",
        "keywords": ["pétrole", "contrat"],
    },
    {
        "source":   "Environnement Congo",
        "sujet":    "droit forestier, environnemental et foncier au Congo-Brazzaville",
        "keywords": ["forêt", "contrat"],
    },
    {
        "source":   "Diplomatie Congo",
        "sujet":    "coopération judiciaire internationale et accords bilatéraux du Congo-Brazzaville",
        "keywords": ["diplomatie", "contrat"],
    },
]

_GEMINI_MODEL_CACHE = None


# ── IA : Gemini + fallback Groq ─────────────────────────────────────────────────

def _gemini_call(prompt: str, max_tokens: int = 800) -> str:
    """
    Appelle l'API Gemini via le proxy système (hérité du processus parent).
    Fallback automatique sur Groq si Gemini indisponible.
    """
    global _GEMINI_MODEL_CACHE
    key = os.environ.get("GEMINI_API_KEY", "").strip()

    if key:
        candidates = [
            ("v1beta", "gemini-2.0-flash-lite"),
            ("v1beta", "gemini-2.0-flash-lite-001"),
            ("v1beta", "gemini-2.0-flash"),
            ("v1beta", "gemini-2.5-flash"),
        ]
        if _GEMINI_MODEL_CACHE:
            candidates = [_GEMINI_MODEL_CACHE] + [c for c in candidates if c != _GEMINI_MODEL_CACHE]

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.6},
        }).encode()

        for (version, model) in candidates:
            url = (
                f"https://generativelanguage.googleapis.com/{version}/models/"
                f"{model}:generateContent?key={key}"
            )
            try:
                req = urllib.request.Request(
                    url, data=payload, headers={"content-type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.loads(r.read())
                parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text  = parts[0].get("text", "").strip() if parts else ""
                if not text:
                    raise ValueError("Réponse vide")
                _GEMINI_MODEL_CACHE = (version, model)
                log.info("[AI] Gemini %s/%s", version, model)
                return text
            except Exception as e:
                log.warning("[AI] Gemini %s/%s : %s", version, model, e)
                continue

    # Fallback Groq
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            payload_g = json.dumps({
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.6,
            }).encode()
            req_g = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload_g,
                headers={
                    "content-type": "application/json",
                    "authorization": f"Bearer {groq_key}",
                },
            )
            with urllib.request.urlopen(req_g, timeout=30) as r:
                resp_g = json.loads(r.read())
            text_g = resp_g["choices"][0]["message"]["content"].strip()
            log.info("[AI] Groq fallback OK")
            return text_g
        except Exception as ge:
            log.error("[AI] Groq aussi échoué : %s", ge)

    raise RuntimeError("Aucune API IA disponible (GEMINI_API_KEY / GROQ_API_KEY non configurés)")


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


def save_article(source, titre, url, keywords_found):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR IGNORE INTO articles (source, titre, titre_fr, url, keywords, lang_orig) "
            "VALUES (?,?,?,?,?,?)",
            (source, titre[:300], titre[:300], url, ",".join(keywords_found), "fr"),
        )
        conn.commit()
        conn.close()
        log.info("[%s] Sauvegardé : %s", source, titre[:80])
    except sqlite3.Error as e:
        log.error("Erreur SQLite : %s", e)


# ── Génération des bulletins ─────────────────────────────────────────────────────

def generate_bulletins(theme: dict) -> list:
    today = datetime.date.today().strftime("%d %B %Y")
    prompt = f"""Tu es un expert en veille juridique spécialisé dans le droit africain.

Génère 4 bulletins de veille juridique portant sur : {theme['sujet']}
Date de référence : {today}

Chaque bulletin doit couvrir un aspect différent (actualité législative, jurisprudence,
accord international, analyse de texte, initiative gouvernementale, etc.).

Réponds UNIQUEMENT avec ce tableau JSON (sans markdown ni texte autour) :
[
  {{
    "titre": "titre du bulletin (factuel, informatif, max 120 caractères)",
    "url": "https://yaro-ref.cg/{secrets.token_hex(6)}"
  }}
]"""

    try:
        raw = _gemini_call(prompt, max_tokens=600)
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])
        items = json.loads(raw.strip())
        return items if isinstance(items, list) else []
    except json.JSONDecodeError as e:
        log.error("[%s] JSON invalide : %s", theme["source"], e)
        return []
    except Exception as e:
        log.error("[%s] Erreur génération : %s", theme["source"], e)
        return []


# ── Rapport ─────────────────────────────────────────────────────────────────────

def print_daily_report():
    conn  = sqlite3.connect(DB_PATH)
    today = datetime.date.today().isoformat()
    rows  = conn.execute(
        "SELECT source, titre_fr, url, keywords, ts FROM articles WHERE ts >= ? ORDER BY ts DESC",
        (today,),
    ).fetchall()
    conn.close()
    print("\n" + "=" * 70)
    print(f"  RAPPORT YARO IA — Veille juridique du {today}")
    print("=" * 70)
    if not rows:
        print("  Aucun bulletin généré aujourd'hui.")
    for source, titre, url, keywords, ts in rows:
        print(f"\n  [{source}]")
        print(f"  Titre  : {titre}")
        print(f"  URL    : {url}")
        print(f"  Mots-clés : {keywords}  |  {ts}")
    print("=" * 70 + "\n")


# ── Exécution principale ────────────────────────────────────────────────────────

def run_once():
    log.info("=== Démarrage de la veille juridique YARO IA (via Gemini IA) ===")
    init_db()
    total = 0

    for theme in THEMES:
        log.info("Génération [%s] …", theme["source"])
        bulletins = generate_bulletins(theme)
        for b in bulletins:
            titre = (b.get("titre") or "").strip()
            url   = (b.get("url")   or f"https://yaro-ref.cg/{secrets.token_hex(8)}").strip()
            if titre:
                save_article(
                    source        = theme["source"],
                    titre         = titre,
                    url           = url,
                    keywords_found= theme["keywords"],
                )
                total += 1
        time.sleep(1)

    log.info("=== Terminé : %d bulletin(s) sauvegardé(s) ===", total)
    print_daily_report()
    return total


def run_daily():
    log.info("Mode run_daily activé — exécution à 02h00 chaque nuit.")
    while True:
        now    = datetime.datetime.now()
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        wait_sec = (target - now).total_seconds()
        log.info("Prochaine exécution dans %.0f s (%s).",
                 wait_sec, target.strftime("%Y-%m-%d %H:%M"))
        time.sleep(wait_sec)
        run_once()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        run_once()
    else:
        run_daily()
