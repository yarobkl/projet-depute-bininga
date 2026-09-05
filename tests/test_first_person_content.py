import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import first_person_content_migration as migration


def test_personal_surfaces_are_migrated_to_first_person():
    sample = {
        "hero": {
            "subtitle": "Un homme de terrain, de conviction et de résultats. Une vie au service du peuple congolais et de la Cuvette-Ouest.",
            "btn2": "Notre programme",
        },
        "about": {
            "sectionTag": "Qui est-il ?",
            "badgeLbl": "Sa circonscription",
            "title": 'Un homme forgé par <span class="r">le terrain</span>',
            "intro": "Ange Aimé Wilfrid BININGA est l'une des personnalités les plus emblématiques de la vie politique et judiciaire du Congo-Brazzaville. Docteur en droit, Inspecteur principal du Trésor, Député d'Ewo et Garde des Sceaux, son parcours est celui d'un homme d'État forgé par l'exigence, le service public et l'amour de son pays.",
            "paragraphs": list(migration.ABOUT_PARAGRAPHS_OLD),
        },
        "parcoursSection": {"tag": "Son parcours"},
        "parcours": [{"desc": old} for old in migration.PARCOURS_DESC],
        "programmeSection": {"tag": "Notre vision"},
        "programme": {
            "heroText": "Chaque engagement de ce programme est issu d'échanges directs avec les habitants d'Ewo, les chefs de village, les jeunes, les femmes entrepreneurs et les professionnels de santé et d'éducation.",
            "axes": [{
                "text": "Fort de son expérience au Ministère de la Fonction publique, il porte un plan ambitieux pour l'emploi des jeunes et la dignité des travailleurs d'Ewo."
            }],
        },
        "actus": {"cards": [{"desc": "Fort de son expérience, il agit sur le terrain."}]},
    }

    result, changed = migration.migrate_data(sample)
    assert changed is True
    assert result["hero"]["subtitle"].startswith("Je suis un homme de terrain")
    assert result["hero"]["btn2"] == "Mon programme"
    assert result["about"]["sectionTag"] == "Qui suis-je ?"
    assert result["about"]["badgeLbl"] == "Ma circonscription"
    assert result["about"]["title"].startswith("Mon parcours")
    assert result["about"]["intro"].startswith("Je suis Ange Aimé Wilfrid BININGA")
    assert all(" je " in f" {p.lower()} " or " j'" in f" {p.lower()}" for p in result["about"]["paragraphs"])
    assert result["parcoursSection"]["tag"] == "Mon parcours"
    assert result["programmeSection"]["tag"] == "Ma vision"
    assert "mes échanges directs" in result["programme"]["heroText"]
    assert result["programme"]["axes"][0]["text"].startswith("Fort de mon expérience")
    # Editorial/news copy is intentionally not rewritten.
    assert result["actus"] == sample["actus"]


def test_unknown_admin_copy_is_never_overwritten():
    sample = {
        "hero": {"subtitle": "Texte personnalisé depuis l'admin", "btn2": "Découvrir"},
        "about": {"sectionTag": "Mon histoire", "paragraphs": ["Texte personnalisé"]},
        "parcoursSection": {"tag": "Itinéraire"},
        "programmeSection": {"tag": "Projet"},
    }
    result, changed = migration.migrate_data(sample)
    assert changed is False
    assert result == sample


def test_public_runtime_never_overwrites_admin_copy_with_hardcoded_french():
    source = open(os.path.join(ROOT, "static", "index.js"), "r", encoding="utf-8").read()

    # La migration one-shot peut mettre les anciennes valeurs à la première
    # personne, mais le navigateur ne doit jamais imposer ensuite sa propre
    # copie éditoriale par-dessus les valeurs enregistrées dans l'admin.
    assert "FIRST_PERSON_FR" not in source
    assert "applyFirstPersonFrenchCopy" not in source
    assert 'heroSubtitle: "Je suis un homme de terrain' not in source
    assert 'aboutTitle: \'Mon parcours, forgé' not in source

    # Les rares corrections de rendu doivent relire la donnée réellement
    # chargée depuis data.json, jamais une constante éditoriale locale.
    assert "applyAdminContentCompatibility" in source
    assert "window._FR_DATA" in source
    assert 'document.getElementById("dyn-eng-title")' in source
    assert "editableMultilineHtml" in source


def test_public_renderer_covers_all_editable_content_sections():
    source = open(os.path.join(ROOT, "static", "index-core.js"), "r", encoding="utf-8").read()
    expected_tokens = [
        "d.hero",
        "d.about",
        "d.stats",
        "d.actus",
        "d.gallery",
        "d.programmeSection",
        "d.galerieSection",
        "d.actusSection",
        "d.engagement",
        "d.cta",
        "d.parcoursSection",
        "d.parcours",
        "d.programme",
        "d.seo",
        "d.contact",
        "d.footer",
    ]
    missing = [token for token in expected_tokens if token not in source]
    assert not missing, f"Sections admin sans rendu public détecté : {missing}"


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("OK", test.__name__)
    print(f"{len(tests)} tests voix éditoriale validés")
