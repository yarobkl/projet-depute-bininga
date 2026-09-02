# Sauvegarde et reprise de BININGA

## Routine recommandée

1. Dans l'administration, ouvrir **Sauvegardes**.
2. Cliquer sur **Télécharger une archive de reprise** avant toute publication importante, puis au minimum une fois par semaine.
3. Conserver le fichier ZIP dans un espace sécurisé distinct du site, avec accès limité à l'administrateur.
4. Ne jamais envoyer cette archive par messagerie non chiffrée : elle contient les données nécessaires à une reprise complète, y compris les contacts et les comptes (mots de passe hachés).

Les copies affichées « sur ce serveur » ne sont pas une sauvegarde externe. Sur Vercel, elles sont temporaires et peuvent disparaître lors d'un redéploiement. L'archive téléchargée est donc la copie de reprise de référence tant qu'aucun stockage externe durable n'est configuré. Les sessions actives et `app_config` (clés d'API) sont volontairement exclues : elles doivent être recréées ou reconfigurées après une reprise.

## Vérifier une archive

Depuis la racine du projet :

```bash
python backup_bininga.py --verify /chemin/vers/bininga-AAAAMMJJ-HHMMSSZ.zip
```

La commande contrôle le format, le nombre d'enregistrements et de photos, ainsi que l'empreinte SHA-256 de chaque fichier. Une archive qui ne termine pas par `OK vérifiée=...` ne doit pas être restaurée.

## Procédure de reprise

1. Mettre le site en maintenance et interdire les nouvelles écritures.
2. Télécharger une dernière archive de sécurité de la base actuelle si elle répond encore.
3. Vérifier l'archive choisie avec la commande ci-dessus.
4. Restaurer `bininga_store.json` et le dossier `photos/` dans une base de remplacement, jamais directement dans la seule base de production sans copie préalable.
5. Contrôler sur une préversion : accueil, actualités, formulaires, connexion admin, contacts, CRM et photos.
6. Basculer la production uniquement après validation et conserver l'ancienne base jusqu'à la fin de la période de contrôle.

La restauration destructive reste volontairement une opération d'exploitation encadrée. Elle n'est pas exposée comme bouton web afin qu'un compte administrateur compromis ne puisse pas écraser toute la base en un clic.
