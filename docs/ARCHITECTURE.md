# Architecture BININGA

## Objectif

BININGA conserve son socle historique sans réécriture risquée, mais les nouvelles évolutions doivent respecter des frontières explicites. Le but est d'empêcher `server.py`, `static/admin.js` et `admin.html` de redevenir les endroits par défaut pour toute nouvelle fonctionnalité.

## Front public

- `static/index.js` : bootstrap léger, performance mobile et instrumentation transverse.
- `static/index-core.js` : comportement public historique.
- `static/public-experience.js` : expérience, transitions et navigation enrichie.
- `static/public-form-hardening.js` : confidentialité et intégrité des formulaires publics.
- `static/analytics-consent.js` : consentement et collecte GA4.

Règle : une nouvelle fonctionnalité publique autonome doit être ajoutée dans un module dédié et chargée depuis le bootstrap. `index-core.js` ne doit plus grossir sans nécessité de compatibilité.

## Front administration

### Noyau

- `static/admin.js` : bundle historique de compatibilité et handlers visuels existants.
- `static/admin-session-hardening.js` : propriétaire unique du bootstrap authentifié (session, premier affichage, modules critiques, `init()`, puis modules secondaires) et écran de reprise en cas d'erreur critique.
- `static/admin-core.js` : source de vérité partagée pour token, CSRF, rôle, identité, chemins API et requêtes authentifiées.
- `static/admin-production.js` : garde-fous de production, téléchargement authentifié et contrôle des actions sensibles.

### Modules métier

- `static/admin-navigation.js` : navigation et layout.
- `static/admin-dashboard-hardening.js` : dashboard et indicateurs.
- `static/admin-cases.js` : dossiers/messages citoyens.
- `static/admin-chatbot.js` : administration IA/chatbot.
- `static/admin-system-ux.js` : CRM/système et garde-fous UI.
- `static/admin-hardening.js` : synchronisation serveur-first des mutations.
- `static/admin-notification-hardening.js` : notifications.

Règles :

1. Aucun nouveau module ne doit recréer sa propre lecture de `SESSION_TOKEN`, `SESSION_CSRF` ou `SESSION_IS_MAIN_ADMIN` : utiliser `window.BiningaAdminCore`.
2. Aucun nouveau code ne doit écrire `bininga_session` dans `localStorage`. Le stockage actif est `sessionStorage`; `localStorage` ne sert qu'à supprimer/migrer les anciennes sessions.
3. Les contrôles de permissions dans l'interface ne remplacent jamais l'autorisation serveur.
4. Une fonctionnalité métier importante doit vivre dans un fichier `static/admin-*.js` dédié plutôt que dans un nouveau bloc inline de `admin.html`.
5. Aucun module secondaire ne doit envelopper `init()` ni piloter `#app`/`#login`. Il réagit aux événements du bootstrap (`bininga:admin-shell-ready`, `bininga:admin-background-starting`, `bininga:admin-ready`).
6. Un `MutationObserver` ne doit jamais surveiller un attribut ou un sous-arbre que son callback réécrit. Les rafraîchissements métier utilisent les événements de navigation ou enveloppent uniquement leur chargeur dédié.

## Backend / requêtes dynamiques

- `server.py` : moteur historique et implémentations de routes existantes.
- `passenger_wsgi.py` : adaptation WSGI/HTTP uniquement, bootstrap léger et injection des couches front de compatibilité.
- `admin_request_pipeline.py` : ordre unique des gardes serveur sur chaque requête dynamique.
- `admin_system_authz.py` : permissions système/CRM/monitoring côté serveur.
- `admin_contact_integrity.py` : intégrité des contacts et mutations.
- `editorial_publish_integrity.py` : publication éditoriale.
- `backup_download.py` : téléchargement des sauvegardes.
- `chatbot_hardening.py` : protection de la route chatbot.
- `admin_bootstrap_hardening.py` : bootstrap d'accès admin et compatibilité Vercel.

Règle : ajouter une nouvelle protection transversale dans `admin_request_pipeline.py`, pas directement dans une nouvelle chaîne `if/elif` de l'adaptateur WSGI.

## Persistance

Les mutations durables en production doivent utiliser la base configurée par `DATABASE_URL`. Les couches d'intégrité refusent les mutations serverless durables si aucune base persistante n'est disponible. `/tmp` ne doit contenir que de l'état éphémère compatible serverless.

## Tests d'architecture

`tests/test_architecture_contracts.py` protège les frontières ci-dessus : ordre du noyau admin, absence de duplication des primitives d'authentification, pipeline serveur unique et budgets de dette technique pour empêcher les gros fichiers historiques de grossir silencieusement.

## Stratégie de refactorisation

Le projet suit une stratégie "strangler" : toute nouvelle logique est extraite dans un module spécialisé, puis les fonctions historiques deviennent progressivement de simples façades de compatibilité. Une réécriture complète de `server.py` ou `admin.js` n'est pas nécessaire et serait plus risquée pour la production.
