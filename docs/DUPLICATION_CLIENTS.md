# Duplication client - pack site public + espace admin

Objectif business : transformer ce projet en produit vendable a plusieurs clients
sans recoder le site a chaque fois.

## Positionnement

Le produit vendable est un "site institutionnel premium avec espace admin".
Il convient a :

- elus, deputes, maires, ministres, candidats ;
- cabinets politiques ou institutionnels ;
- associations, fondations, entreprises locales ;
- personnalites publiques qui veulent un site + CRM + formulaires + contenu.

## Ce qui est inclus dans une reproduction

- Site public complet : accueil, biographie, programme, actualites, galerie,
  contact, newsletter, chatbot et SEO.
- Espace admin prive : login, gestion de contenu, contacts, demandes
  d'audience, CRM, fichiers, sauvegardes, logs, securite.
- Donnees client separees : contenu, utilisateurs, contacts, sessions,
  uploads, logs et base de donnees.
- Deploiement possible sur o2switch, Railway, VPS ou hebergement Python.

## Architecture conseillee par client

Chaque client doit avoir sa propre copie de projet et ses propres secrets.

```text
clients/
  client-bininga/
  client-maire-x/
  client-depute-y/
```

Pour chaque client :

- un domaine public, ex. `client.cg` ;
- une URL admin secrete, ex. `/cabinet-client-2026-x9k2` ;
- une base MySQL separee ;
- un compte admin principal unique ;
- un dossier d'uploads isole ;
- une configuration email propre au client.

## Fichiers a personnaliser

Priorite haute :

- `data.json` : textes, actus, galerie, SEO, programme.
- `images/` : photos du client.
- `.env` : secrets, base de donnees, admin, domaines.
- `robots.txt` et `sitemap.xml` : domaine du client.

Priorite moyenne :

- `static/i18n.js` et `static/i18n-data.*.js` : traductions.
- `static/chat.js` : nom et posture de l'assistant.
- `admin.html`, `gestion.html`, `static/admin.js` : libelles admin marques.

## Variables d'environnement minimales

```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=cpaneluser_client
MYSQL_USER=cpaneluser_client
MYSQL_PASSWORD=mot_de_passe_mysql

BININGA_USER=admin
BININGA_PASS=mot_de_passe_admin_tres_fort
ADMIN_SECRET_PATH=espace-prive-client-long-secret
BININGA_ORIGINS=https://client.cg,https://www.client.cg

NOTIF_EMAIL_FROM=
NOTIF_EMAIL_PASS=
NOTIF_EMAIL_TO=
BININGA_FORCE_FILE_SYNC=0
```

Note : les noms `BININGA_*` existent encore dans le code. Pour aller plus
loin, on pourra les migrer vers `CLIENT_*` sans casser la prod actuelle.

## Process de vente et livraison

1. Qualification du client : nom, fonction, ville, domaine, objectif politique
   ou institutionnel, langues voulues.
2. Collecte : photos, bio, programme, contacts, comptes sociaux, couleurs,
   mentions legales.
3. Duplication avec le script `scripts/create_client_copy.py`.
4. Personnalisation du contenu dans `data.json` puis verification du site.
5. Creation de la base MySQL et du `.env`.
6. Deploiement.
7. Test complet : site public, formulaire contact, admin, sauvegarde,
   upload image, login/deconnexion, mobile.
8. Livraison : URL publique, URL admin secrete, identifiants admin, mini-guide.

## Prix suggere

Offre Starter :

- site public personnalise ;
- espace admin ;
- formulaire contact ;
- deploiement ;
- 1 langue.

Offre Pro :

- Starter ;
- CRM ;
- galerie avancee ;
- newsletter ;
- sauvegardes ;
- SEO ;
- 2 a 4 langues.

Offre Premium :

- Pro ;
- assistant IA personnalise ;
- monitoring ;
- support mensuel ;
- securite renforcee ;
- formation equipe.

## Points a industrialiser ensuite

- Renommer les constantes `BININGA_*` en constantes generiques.
- Sortir les labels "BININGA" restants dans un fichier `client.json`.
- Ajouter un mode theme couleur depuis la configuration.
- Automatiser la generation `robots.txt` et `sitemap.xml`.
- Creer un script de creation de base MySQL/o2switch si acces serveur fourni.
- Ajouter une page admin "Marque client" pour changer logo, nom, domaine,
  reseaux sociaux et couleurs sans code.

