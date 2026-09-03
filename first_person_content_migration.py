"""One-shot editorial migration: personal presentation uses first person.

The public news/editorial surfaces deliberately stay in third person. This
migration only changes canonical personal/campaign presentation copy and only
when the stored value still matches the previous known wording, so later admin
edits are never overwritten.
"""
from __future__ import annotations

import copy

MIGRATION_KEY = "editorial_voice_first_person_v1"

ABOUT_PARAGRAPHS_OLD = [
    "Né à Brazzaville, Ange Aimé Wilfrid BININGA grandit avec le sens du devoir chevillé au corps. Armé d'un Doctorat en droit, il intègre la haute fonction publique et gravit les échelons à la Direction générale du Trésor public jusqu'au rang d'Inspecteur principal, une position qui exige rigueur, intégrité et maîtrise des finances de l'État. Il apportera également sa compétence à la Direction générale de la Santé, où il occupera des fonctions stratégiques de conseiller ministeriel. C'est cette double expertise, juridique et administrative, qui fera de lui un commis de l'État hors du commun.",
    "En 2016, le Président de la République lui confie le portefeuille de Ministre de la Fonction publique et de la Réforme de l'État. Il s'attelle aussitôt à moderniser l'administration congolaise, à dynamiser l'emploi des jeunes fonctionnaires et à impulser les réformes structurelles nécessaires à la diversification économique nationale. Le 19 août 2017, les électeurs de la 1re circonscription d'Ewo lui accordent leur confiance en l'élisant Député à l'Assemblée Nationale, consécration populaire d'un engagement profond envers sa terre natale.",
    "En tant que Ministre de la Justice, il inscrit son action dans l'histoire en portant et faisant adopter en 2018 la loi instituant la Haute Autorité de lutte contre la corruption, un texte fondateur voté par 107 voix pour, 6 contre et 1 abstention, symbole d'une volonté nationale de rupture avec l'impunité. Une réforme institutionnelle qui restera comme l'une des plus importantes de la décennie.",
    "Aujourd'hui, en qualité de Garde des Sceaux, Ministre de la Justice, des Droits Humains et de la Promotion des Peuples Autochtones, il porte la voix du Congo sur la scène internationale. En février 2026, il conduit à Paris des négociations cruciales avec son homologue français Gérald Darmanin pour rénover la convention de coopération judiciaire Congo-France, un accord vieux de plus de cinquante ans qu'il entend adapter aux enjeux du monde contemporain. Juriste, réformateur, diplomate : Ange Aimé Wilfrid BININGA incarne une vision exigeante et ambitieuse du service de l'État.",
]

ABOUT_PARAGRAPHS_NEW = [
    "Né à Brazzaville, j'ai grandi avec le sens du devoir et du service public. Titulaire d'un doctorat en droit, j'ai intégré la haute fonction publique et gravi les échelons à la Direction générale du Trésor public jusqu'au rang d'Inspecteur principal, une fonction qui exige rigueur, intégrité et maîtrise des finances de l'État. J'ai également mis mon expérience au service de la Direction générale de la Santé, où j'ai exercé des fonctions stratégiques de conseiller ministériel. Ce parcours m'a permis de construire une double expertise, juridique et administrative, au service de l'État.",
    "En 2016, le Président de la République m'a confié le portefeuille de Ministre de la Fonction publique et de la Réforme de l'État. J'ai alors engagé mon action dans la modernisation de l'administration congolaise, l'emploi des jeunes fonctionnaires et les réformes structurelles nécessaires à la diversification économique nationale. Le 19 août 2017, les électeurs de la 1re circonscription d'Ewo m'ont accordé leur confiance en m'élisant Député à l'Assemblée Nationale. Cette confiance constitue pour moi une responsabilité durable envers Ewo et la Cuvette-Ouest.",
    "En tant que Ministre de la Justice, j'ai porté en 2018 la loi instituant la Haute Autorité de lutte contre la corruption. Adopté par 107 voix pour, 6 contre et 1 abstention, ce texte a marqué une étape importante dans le renforcement du cadre institutionnel de lutte contre la corruption et l'impunité. Je considère cette réforme comme l'un des engagements majeurs de mon action publique.",
    "Aujourd'hui, en qualité de Garde des Sceaux, Ministre de la Justice, des Droits Humains et de la Promotion des Peuples Autochtones, je porte la voix du Congo dans les dossiers relevant de mes responsabilités, au niveau national comme international. En février 2026, j'ai conduit à Paris des échanges avec mon homologue français Gérald Darmanin afin de moderniser la coopération judiciaire entre le Congo et la France. Juriste, réformateur et homme de terrain, je défends une vision exigeante du service de l'État, fondée sur la responsabilité, la justice et l'efficacité publique.",
]

PARCOURS_DESC = {
    "Docteur en droit, Ange Aimé Wilfrid BININGA bâtit une carrière de cadre supérieur de l'État au sein de la Direction générale du Trésor public, avant de rejoindre celle de la Santé comme conseiller stratégique du ministre.":
        "Docteur en droit, j'ai bâti une carrière de cadre supérieur de l'État au sein de la Direction générale du Trésor public, avant de rejoindre la Santé comme conseiller stratégique du ministre.",
    "Militant du Parti Congolais du Travail, il s'engage activement dans la vie politique d'Ewo et de la Cuvette-Ouest, portant les aspirations de sa communauté.":
        "Militant du Parti Congolais du Travail, je me suis engagé activement dans la vie politique d'Ewo et de la Cuvette-Ouest, avec la volonté de porter les aspirations de ma communauté.",
    "Nommé par le Président de la République au sein du premier gouvernement de la nouvelle République, il porte la modernisation de l'administration publique et l'emploi des jeunes, piliers de la diversification économique nationale.":
        "Nommé par le Président de la République au sein du premier gouvernement de la nouvelle République, j'ai porté la modernisation de l'administration publique et l'emploi des jeunes, deux enjeux essentiels de la diversification économique nationale.",
    "Il est élu Député de la 1re circonscription électorale d'Ewo (département de la Cuvette-Ouest) le 19 août 2017, représentant sa communauté à l'Assemblée Nationale de la République du Congo.":
        "Le 19 août 2017, les électeurs de la 1re circonscription d'Ewo m'ont élu Député à l'Assemblée Nationale de la République du Congo. Depuis, je représente Ewo et la Cuvette-Ouest avec la responsabilité liée à cette confiance.",
    "En tant que Ministre de la Justice, il pilote l'adoption par 107 députés de la loi créant la Haute Autorité de lutte contre la corruption (2018), institution indépendante dotée du droit de saisine directe des instances judiciaires.":
        "En tant que Ministre de la Justice, j'ai piloté l'adoption par 107 députés de la loi créant la Haute Autorité de lutte contre la corruption en 2018, institution indépendante dotée du droit de saisine directe des instances judiciaires.",
    "À ce poste clé du gouvernement, il incarne la diplomatie judiciaire du Congo, notamment avec la renégociation en février 2026 à Paris de la convention de coopération judiciaire Congo-France, accord vieux de plus de 50 ans, renouvelé sur de nouvelles bases modernes.":
        "À ce poste clé du gouvernement, je porte la diplomatie judiciaire du Congo. En février 2026 à Paris, j'ai notamment engagé la modernisation de la coopération judiciaire Congo-France, fondée sur un accord vieux de plus de cinquante ans.",
    "Plus motivé que jamais, fort de son expérience gouvernementale, il se présente aux prochaines élections législatives avec un programme ambitieux pour Ewo et le Congo.":
        "Fort de mon expérience gouvernementale et de mon engagement à Ewo, je me présente aux prochaines élections législatives avec un programme ambitieux pour Ewo et le Congo.",
}


def _replace_exact(container: dict, key: str, old, new) -> bool:
    if isinstance(container, dict) and container.get(key) == old:
        container[key] = new
        return True
    return False


def migrate_data(data: object) -> tuple[object, bool]:
    if not isinstance(data, dict):
        return data, False
    result = copy.deepcopy(data)
    changed = False

    hero = result.get("hero") if isinstance(result.get("hero"), dict) else {}
    changed |= _replace_exact(hero, "subtitle",
        "Un homme de terrain, de conviction et de résultats. Une vie au service du peuple congolais et de la Cuvette-Ouest.",
        "Je suis un homme de terrain, de conviction et de résultats. Mon engagement est au service du peuple congolais et de la Cuvette-Ouest.")
    changed |= _replace_exact(hero, "btn2", "Notre programme", "Mon programme")

    about = result.get("about") if isinstance(result.get("about"), dict) else {}
    changed |= _replace_exact(about, "sectionTag", "Qui est-il ?", "Qui suis-je ?")
    changed |= _replace_exact(about, "badgeLbl", "Sa circonscription", "Ma circonscription")
    changed |= _replace_exact(about, "title", 'Un homme forgé par <span class="r">le terrain</span>', 'Mon parcours, forgé par <span class="r">le terrain</span>')
    changed |= _replace_exact(about, "intro",
        "Ange Aimé Wilfrid BININGA est l'une des personnalités les plus emblématiques de la vie politique et judiciaire du Congo-Brazzaville. Docteur en droit, Inspecteur principal du Trésor, Député d'Ewo et Garde des Sceaux, son parcours est celui d'un homme d'État forgé par l'exigence, le service public et l'amour de son pays.",
        "Je suis Ange Aimé Wilfrid BININGA. Docteur en droit, Inspecteur principal du Trésor, Député d'Ewo et Garde des Sceaux, j'ai construit mon parcours autour d'une exigence : servir l'État et les citoyens avec rigueur, responsabilité et attachement à mon pays.")
    paragraphs = about.get("paragraphs")
    if isinstance(paragraphs, list):
        for index, old in enumerate(ABOUT_PARAGRAPHS_OLD):
            if index < len(paragraphs) and paragraphs[index] == old:
                paragraphs[index] = ABOUT_PARAGRAPHS_NEW[index]
                changed = True

    parcours_section = result.get("parcoursSection") if isinstance(result.get("parcoursSection"), dict) else {}
    changed |= _replace_exact(parcours_section, "tag", "Son parcours", "Mon parcours")
    parcours = result.get("parcours")
    if isinstance(parcours, list):
        for item in parcours:
            if not isinstance(item, dict):
                continue
            current = item.get("desc")
            if current in PARCOURS_DESC:
                item["desc"] = PARCOURS_DESC[current]
                changed = True

    programme_section = result.get("programmeSection") if isinstance(result.get("programmeSection"), dict) else {}
    changed |= _replace_exact(programme_section, "tag", "Notre vision", "Ma vision")
    programme = result.get("programme") if isinstance(result.get("programme"), dict) else {}
    changed |= _replace_exact(programme, "heroText",
        "Chaque engagement de ce programme est issu d'échanges directs avec les habitants d'Ewo, les chefs de village, les jeunes, les femmes entrepreneurs et les professionnels de santé et d'éducation.",
        "Chaque engagement de mon programme est issu de mes échanges directs avec les habitants d'Ewo, les chefs de village, les jeunes, les femmes entrepreneures et les professionnels de santé et d'éducation.")
    axes = programme.get("axes")
    if isinstance(axes, list):
        for axis in axes:
            if not isinstance(axis, dict):
                continue
            changed |= _replace_exact(axis, "text",
                "Fort de son expérience au Ministère de la Fonction publique, il porte un plan ambitieux pour l'emploi des jeunes et la dignité des travailleurs d'Ewo.",
                "Fort de mon expérience au Ministère de la Fonction publique, je porte un plan ambitieux pour l'emploi des jeunes et la dignité des travailleurs d'Ewo.")

    return result, bool(changed)


def apply(server) -> dict:
    """Apply the migration to durable site_data when possible."""
    try:
        if server._pg_load(MIGRATION_KEY):
            return {"ok": True, "changed": False, "already_applied": True}
        current = server._pg_load("site_data")
        migrated, changed = migrate_data(current)
        if changed:
            if not server._pg_save("site_data", migrated):
                return {"ok": False, "changed": False, "error": "site_data_write_failed"}
            try:
                server._DATA_CACHE = migrated
                server._DATA_CACHE_AT = 0
            except Exception:
                pass
        server._pg_save(MIGRATION_KEY, {"applied": True, "changed": bool(changed)})
        return {"ok": True, "changed": bool(changed), "already_applied": False}
    except Exception as exc:
        return {"ok": False, "changed": False, "error": type(exc).__name__}
