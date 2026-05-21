# Base de données o2switch pour BININGA

Objectif : ne plus perdre les contenus et photos uploadés depuis l'espace admin.

## 1. Créer la base dans cPanel

Dans o2switch/cPanel :

1. Ouvrir **Bases de données MySQL**.
2. Créer une base, par exemple `cpaneluser_bininga`.
3. Créer un utilisateur MySQL, par exemple `cpaneluser_bininga`.
4. Donner à cet utilisateur **tous les privilèges** sur la base.

## 2. Configurer le projet

Sur le serveur, dans le dossier du site, copier :

```bash
cp .env.example .env
```

Puis remplir :

```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=cpaneluser_bininga
MYSQL_USER=cpaneluser_bininga
MYSQL_PASSWORD=mot_de_passe_mysql
```

Le fichier `.env` est ignoré par Git pour éviter de publier les mots de passe.

## 3. Installer les dépendances Python

Dans l'environnement Python du site :

```bash
pip install -r requirements.txt
```

## 4. Redémarrer l'application Python

Redémarrer depuis **Setup Python App** dans cPanel, ou via le terminal selon la configuration.

Au premier démarrage, le serveur crée automatiquement :

- `bininga_store` pour le contenu, les utilisateurs, contacts et CRM.
- `bininga_photos` pour les images sauvegardées en base.

## 5. Règle importante

`data.json` ne doit plus écraser la base au redémarrage.

La variable `BININGA_FORCE_FILE_SYNC=1` force volontairement une restauration depuis `data.json`; elle doit rester à `0` ou vide en production.
