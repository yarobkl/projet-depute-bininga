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


def test_public_guard_targets_only_french_personal_surfaces():
    source = open(os.path.join(ROOT, "static", "index.js"), "r", encoding="utf-8").read()
    assert 'lang !== "fr"' in source
    assert 'aboutTag: "Qui suis-je ?"' in source
    assert 'parcoursTag: "Mon parcours"' in source
    assert 'programmeTag: "Ma vision"' in source
    assert "actualités et contenus journalistiques restent volontairement" in source


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("OK", test.__name__)
    print(f"{len(tests)} tests voix éditoriale validés")
