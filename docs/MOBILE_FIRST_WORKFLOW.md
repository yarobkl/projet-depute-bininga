# Workflow mobile-first — BININGA

Objectif : pouvoir modifier BININGA depuis un téléphone sans dépendre du Mac ni du cPanel pour chaque changement.

## Principe

- **GitHub = source officielle du code**
- **ChatGPT / Codex = outils de modification**
- **o2switch = production**
- **cPanel = administration serveur, base de données, variables d'environnement et dépannage**

Le code de production ne doit pas être modifié directement dans le gestionnaire de fichiers cPanel sauf urgence. Toute évolution normale doit passer par GitHub afin de conserver l'historique et d'éviter les divergences entre le serveur et le dépôt.

## Workflow depuis le téléphone

1. Demander une modification depuis ChatGPT ou Codex.
2. Travailler sur une branche Git dédiée.
3. Vérifier le diff et les fichiers modifiés.
4. Ouvrir une Pull Request vers `main`.
5. Laisser la CI exécuter les contrôles automatiques.
6. Fusionner uniquement si les contrôles sont au vert.
7. Après fusion dans `main`, le workflow CD déploie automatiquement sur o2switch si les secrets sont configurés.

## Secrets GitHub nécessaires au déploiement

Dans **GitHub → Settings → Secrets and variables → Actions**, configurer :

- `SSH_HOST` : hôte SSH o2switch
- `SSH_USER` : utilisateur SSH o2switch
- `SSH_KEY` : clé privée autorisée sur o2switch
- `SSH_PORT` : port SSH
- `DEPLOY_PATH` : chemin absolu du dossier Git du projet BININGA sur o2switch
- `RESTART_COMMAND` : commande de redémarrage de l'application Python, si disponible

Exemple de `DEPLOY_PATH` :

```text
/home/UTILISATEUR/apps/bininga
```

Ne pas copier cet exemple sans vérifier le chemin réel dans cPanel/SSH.

`RESTART_COMMAND` peut rester vide au départ. Dans ce cas, le code sera mis à jour mais le redémarrage pourra être effectué depuis **Setup Python App** dans cPanel.

## Base de données

Les données de production restent dans MySQL o2switch. Le fichier `.env` ne doit jamais être versionné dans GitHub.

Les secrets d'administration, accès MySQL et chemins privés doivent rester uniquement dans l'environnement de production.

## Règle de sécurité

Ne jamais pousser dans GitHub :

- `.env`
- mots de passe
- clés API
- clés SSH privées
- exports contenant des données personnelles réelles

## Architecture recommandée

```text
Téléphone
   ↓
ChatGPT / Codex
   ↓
Branche GitHub
   ↓
Pull Request
   ↓
CI automatique
   ↓
main
   ↓
CD GitHub Actions
   ↓
o2switch
```

Le Mac reste utile pour les développements locaux lourds et pour le futur agent Android/Samsung, mais il n'est plus obligatoire pour modifier le site BININGA.
