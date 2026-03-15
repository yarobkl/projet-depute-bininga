#!/usr/bin/env python3
"""
Générateur de contenu YouTube pour la campagne BININGA.
Utilise l'API Claude pour créer scripts, descriptions et tags.
"""

import json
import os
import anthropic

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


def load_data() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_video_content(client: anthropic.Anthropic, data: dict, theme: dict) -> dict:
    """Génère le contenu YouTube complet pour un thème donné."""

    context = f"""
Personnalité politique :
- Nom : {data['hero']['firstName']} {data['hero']['lastName']}
- Rôle : {data['hero']['role']}
- Slogan : {data['hero']['slogan'].replace('<em>', '').replace('</em>', '').replace('<br>', ' ')}
- Présentation : {data['about']['intro']}

Actualités récentes :
- {data['actus']['featured']['title']} : {data['actus']['featured']['text']}
"""
    for item in data['actus']['items']:
        context += f"- {item['title']} : {item['desc']}\n"

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

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    # Extraire le texte de la réponse
    text = next(
        (block.text for block in response.content if block.type == "text"),
        ""
    )

    # Nettoyer les éventuels backticks markdown
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non définie. Exportez-la avant de lancer ce script.")

    client = anthropic.Anthropic(api_key=api_key)
    data = load_data()

    print(f"Génération de contenu YouTube pour {data['hero']['firstName']} {data['hero']['lastName']}")
    print("=" * 60)

    results = []

    for theme in VIDEO_THEMES:
        print(f"\n[{theme['id']}] {theme['title']}")
        print("  Génération en cours...")

        content = generate_video_content(client, data, theme)
        results.append({
            "theme_id": theme["id"],
            "theme_title": theme["title"],
            "contenu": content,
        })

        print(f"  Titre YouTube : {content.get('titre_youtube', '—')}")
        print(f"  Durée estimée : {content.get('duree_estimee', '—')}")
        print(f"  Tags : {', '.join(content.get('tags', [])[:5])}...")

    # Sauvegarder les résultats
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"{len(results)} vidéos générées — résultats dans : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
