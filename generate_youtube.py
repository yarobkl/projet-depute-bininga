#!/usr/bin/env python3
"""
Générateur de contenu YouTube pour la campagne BININGA.
Utilise Gemini (+ fallback Groq, puis Claude) pour créer scripts, descriptions et tags.
"""

import json
import os
import urllib.request

DATA_FILE = "data.json"
OUTPUT_FILE = "youtube_content.json"

# Thèmes de vidéos à générer
VIDEO_THEMES = [
    {
        "id": "presentation",
        "title": "Présentation — Qui est BININGA ?",
        "type": "portrait",
    },
    {
        "id": "justice",
        "title": "Réforme de la Justice au Congo — Le bilan de BININGA",
        "type": "bilan",
    },
    {
        "id": "ewo",
        "title": "Ewo, ma circonscription — Les projets pour la Cuvette-Ouest",
        "type": "terrain",
    },
    {
        "id": "diplomatie",
        "title": "Coopération Congo–France : une diplomatie judiciaire renouvelée",
        "type": "international",
    },
    {
        "id": "jeunesse",
        "title": "Emploi et avenir des jeunes de la Cuvette-Ouest",
        "type": "social",
    },
]

_GEMINI_MODEL_CACHE = None


def _ai_call(prompt: str, max_tokens: int = 4096) -> str:
    """Appelle Gemini, avec fallback automatique sur Groq puis Claude."""
    global _GEMINI_MODEL_CACHE

    # 1. Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
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
                f"{model}:generateContent?key={gemini_key}"
            )
            try:
                req = urllib.request.Request(
                    url, data=payload, headers={"content-type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=60) as r:
                    resp = json.loads(r.read())
                parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = parts[0].get("text", "").strip() if parts else ""
                if not text:
                    raise ValueError("Réponse vide")
                _GEMINI_MODEL_CACHE = (version, model)
                print(f"  [AI] Gemini {version}/{model}")
                return text
            except Exception as e:
                print(f"  [AI] Gemini {version}/{model} : {e}")
                continue

    # 2. Groq
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
            with urllib.request.urlopen(req_g, timeout=60) as r:
                resp_g = json.loads(r.read())
            text_g = resp_g["choices"][0]["message"]["content"].strip()
            print("  [AI] Groq fallback OK")
            return text_g
        except Exception as ge:
            print(f"  [AI] Groq échoué : {ge}")

    # 3. Claude (Anthropic)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        try:
            payload_c = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            req_c = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload_c,
                headers={
                    "content-type": "application/json",
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req_c, timeout=60) as r:
                resp_c = json.loads(r.read())
            text_c = resp_c["content"][0]["text"].strip()
            print("  [AI] Claude fallback OK")
            return text_c
        except Exception as ce:
            print(f"  [AI] Claude échoué : {ce}")

    raise RuntimeError("Aucune API IA disponible (GEMINI_API_KEY / GROQ_API_KEY / ANTHROPIC_API_KEY non configurés)")


def load_data() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_video_content(data: dict, theme: dict) -> dict:
    """Génère le contenu YouTube complet pour un thème donné."""

    hero = data["hero"]
    about = data["about"]

    context = f"""
Personnalité politique :
- Nom : {hero['firstName']} {hero['lastName']}
- Rôle : {hero['role']}
- Slogan : {hero['slogan'].replace('<em>', '').replace('</em>', '').replace('<br>', ' ')}
- Présentation : {about['intro']}
"""
    for p in about.get("paragraphs", []):
        context += f"- {p}\n"

    prompt = f"""Tu es un expert en communication politique et création de contenu YouTube francophone.

Contexte sur le député-ministre BININGA :
{context}

Génère le contenu YouTube complet pour la vidéo suivante :
Titre : "{theme['title']}"
Type : {theme['type']}

Fournis un objet JSON avec exactement ces champs :
{{
  "titre_youtube": "titre accrocheur optimisé SEO (max 70 caractères)",
  "description": "description YouTube complète (300-500 mots) avec paragraphes, appel à l'action et hashtags en fin",
  "script": "script de la vidéo (3-5 minutes de narration, structuré avec intro, développement, conclusion)",
  "tags": ["liste", "de", "15", "tags", "pertinents"],
  "miniature_texte": "texte court pour la miniature (max 5 mots percutants)",
  "duree_estimee": "durée estimée en minutes"
}}

Réponds UNIQUEMENT avec le JSON, sans markdown ni texte autour."""

    text = _ai_call(prompt, max_tokens=4096)

    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)


def main():
    if not any(os.environ.get(k, "").strip() for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY")):
        raise ValueError("Aucune clé IA configurée. Exportez GEMINI_API_KEY, GROQ_API_KEY ou ANTHROPIC_API_KEY.")

    data = load_data()

    print(f"Génération de contenu YouTube pour {data['hero']['firstName']} {data['hero']['lastName']}")
    print("=" * 60)

    results = []

    for theme in VIDEO_THEMES:
        print(f"\n[{theme['id']}] {theme['title']}")
        print("  Génération en cours...")

        content = generate_video_content(data, theme)
        results.append({
            "theme_id": theme["id"],
            "theme_title": theme["title"],
            "contenu": content,
        })

        print(f"  Titre YouTube : {content.get('titre_youtube', '—')}")
        print(f"  Durée estimée : {content.get('duree_estimee', '—')}")
        print(f"  Tags : {', '.join(content.get('tags', [])[:5])}...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"{len(results)} vidéos générées — résultats dans : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
