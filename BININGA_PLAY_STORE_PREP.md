# Préparation fiche Google Play — Bininga Citoyen

Notes préparatoires pour la publication de l'application mobile sur le
Google Play Store. Ce document ne couvre pas le build technique (voir
`MOBILE_BININGA.md`), seulement les éléments de fiche/store/conformité.

## Nom de l'application

- **Nom complet** : Bininga Citoyen
- **Nom court** : Bininga

## Description courte (≤ 80 caractères)

> Programme, actualités, audiences et suivi de dossier avec votre député.

## Description longue (exemple, à valider/adapter)

> Bininga Citoyen est l'application officielle de proximité citoyenne.
> Suivez l'actualité et le programme, demandez une audience, signalez une
> réclamation, et suivez l'avancement de vos démarches grâce à un code de
> suivi personnel — directement depuis votre téléphone.
>
> Fonctionnalités :
> - Présentation et vision du programme
> - Actualités et contenus publics
> - Demande d'audience en ligne
> - Signalement / réclamation citoyenne
> - Suivi de dossier en temps réel via code de suivi
> - Fonctionne même en cas de connexion instable (état hors-ligne géré)

## Catégorie

- **Catégorie principale** : Actualités et magazines, ou Gouvernement /
  Affaires civiques (selon disponibilité dans la classification Play
  Console — à confirmer au moment de la création de la fiche).

## Données collectées

L'application transmet au backend existant (déjà en place, non modifié)
les données suivantes, **uniquement lorsque l'utilisateur remplit et
soumet un formulaire** :

- Demande d'audience : nom, téléphone, email (optionnel), objet, message.
- Réclamation : nom, téléphone, localité, message.
- Contact : nom, email, téléphone, message.
- Suivi de dossier : code de suivi saisi par l'utilisateur (aucune donnée
  personnelle additionnelle n'est envoyée pour cette requête).

Aucune donnée n'est collectée passivement (pas de tracking, pas
d'analytics tiers, pas de publicité) dans la version actuelle de
l'application.

## Permissions potentielles

L'application web embarquée (Capacitor WebView) ne nécessite, en l'état,
aucune permission native sensible :

- **Réseau (INTERNET)** : requis pour appeler l'API publique.
- Pas de caméra, localisation, contacts, stockage, micro ou notifications
  push dans la version actuelle.

Si des fonctionnalités futures sont ajoutées (notifications push, upload
de photo pour une réclamation, etc.), les permissions correspondantes
devront être déclarées et justifiées à ce moment-là.

## Politique de confidentialité

**Obligatoire** pour la publication sur Google Play. Doit être hébergée à
une URL publique (ex. `https://wude3801.odns.fr/confidentialite`) et
couvrir au minimum :

- Quelles données sont collectées (voir section ci-dessus) et pourquoi.
- Comment elles sont stockées et utilisées (traitement des demandes
  citoyennes, suivi de dossier).
- Durée de conservation.
- Droit d'accès, de rectification et de suppression des données.
- Contact pour exercer ces droits.

*(Ce document liste les exigences ; la rédaction et la publication de la
page elle-même restent à faire côté contenu/légal.)*

## Page de suppression des données

Google Play exige, pour toute app collectant des données via compte ou
formulaire, un lien public expliquant comment un utilisateur peut demander
la suppression de ses données (même sans compte utilisateur formel,
puisque l'app traite des demandes nominatives). À publier par exemple à
`https://wude3801.odns.fr/suppression-donnees`, avec :

- La procédure pour demander la suppression (ex. email de contact dédié).
- Le délai de traitement.
- Les éventuelles données qui ne peuvent pas être supprimées immédiatement
  (ex. obligations légales de conservation, si applicable).

## Éléments encore à produire avant soumission

- [ ] Icône d'application haute résolution (512×512) et icônes adaptatives.
- [ ] Captures d'écran (téléphone, et tablette si applicable).
- [ ] Image de présentation (feature graphic, 1024×500).
- [ ] URL de la politique de confidentialité (publiée).
- [ ] URL de la page de suppression des données (publiée).
- [ ] AAB signé (voir `MOBILE_BININGA.md`, section "Ce qu'il reste à
      faire").
- [ ] Coordonnées de contact développeur/organisation pour la fiche Play
      Console.
