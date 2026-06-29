# Bininga Citoyen — Application mobile (Capacitor)

Cette application mobile est une **couche séparée** qui consomme l'API publique
du backend existant (`server.py`). Elle ne modifie, n'embarque et ne remplace
**aucun** fichier du site web, de l'admin, du CRM ou de la sécurité du projet
principal.

```
mobile/
├── package.json
├── capacitor.config.json
├── vite.config.js
├── .env.example
├── index.html
├── public/
│   └── manifest.json
└── src/
    ├── main.js
    └── styles.css
```

## 1. Lancer l'application en mode développement

```bash
cd mobile
npm install
cp .env.example .env   # adapter VITE_API_BASE_URL si besoin
npm run dev
```

L'app est servie sur `http://localhost:5173`. Par défaut elle pointe vers
`https://wude3801.odns.fr` (voir `.env.example`). Pour tester contre un
backend local, changez `VITE_API_BASE_URL` dans `.env`.

## 2. Builder le bundle web

```bash
cd mobile
npm run build
```

Génère `mobile/dist/` (bundle Vite, chemins relatifs `base: "./"` — requis
pour fonctionner correctement dans la WebView Capacitor).

## 3. Builder pour Android

```bash
cd mobile
npm install
npm run build
npx cap add android       # une seule fois, scaffold le projet natif android/
npx cap sync android       # à chaque changement du bundle web
cd android
./gradlew assembleDebug   # → app/build/outputs/apk/debug/app-debug.apk
./gradlew bundleRelease   # → app/build/outputs/bundle/release/app-release.aab (non signé)
```

> **Prérequis locaux** : Android SDK + variable `ANDROID_HOME` configurée,
> JDK 17. Si vous n'avez pas l'environnement Android en local, utilisez le
> workflow GitHub Actions ci-dessous, qui tourne sur un runner avec le SDK
> Android préinstallé.

## 4. Tester l'APK debug

1. Récupérer `app-debug.apk` (build local ou artifact du workflow CI).
2. Installer sur un appareil/émulateur Android :
   ```bash
   adb install app-debug.apk
   ```
3. Vérifier : accueil, programme, actualités, démarches (demande d'audience,
   réclamation, contact), suivi de dossier par code de suivi, bandeau hors
   ligne si le serveur est inaccessible.

## 5. Workflow GitHub Actions

Fichier : `.github/workflows/bininga-android-build.yml`

Déclenché sur push/PR touchant `mobile/**`, ou manuellement
(`workflow_dispatch`). Il :
1. Installe Node 20, Java 17, le SDK Android.
2. `npm install` + `npm run build` dans `mobile/`.
3. `npx cap add android` + `npx cap sync android`.
4. `./gradlew assembleDebug` puis `./gradlew bundleRelease`.
5. Publie deux artifacts : l'APK debug et l'AAB release **non signé**.

## 6. Endpoints backend utilisés (lecture seule, aucune modification de server.py)

| Endpoint | Méthode | Usage dans l'app |
|---|---|---|
| `/api/load` | GET | Charge le contenu public (hero, à propos, programme, actualités) |
| `/api/contact` | POST | Demande d'audience, réclamation, message de contact |
| `/api/dossier?code=...` | GET | Suivi de dossier par code de suivi |

Aucun token admin, mot de passe, clé API privée ou identifiant de base de
données n'est présent dans le code de l'application mobile.

## 7. Variable d'environnement serveur à mettre à jour (config, pas de code)

Pour que le backend accepte les requêtes provenant de l'app mobile
(WebView Capacitor) en plus du site web, la variable d'environnement
`BININGA_ORIGINS` côté serveur doit inclure les origines suivantes :

```
BININGA_ORIGINS=https://wude3801.odns.fr,http://wude3801.odns.fr,https://localhost,http://localhost,capacitor://localhost,ionic://localhost
```

`server.py` lit déjà cette variable au démarrage et gère déjà les requêtes
`OPTIONS` (préflight CORS) — **aucune modification de code n'est nécessaire**,
il s'agit uniquement d'une mise à jour de configuration/déploiement.

## 8. Ce qu'il reste à faire avant publication sur Google Play

- [ ] Fournir de vraies icônes d'application (`public/icon-192.png`,
      `public/icon-512.png` référencées dans `manifest.json` — actuellement
      absentes, pas d'assets binaires générés automatiquement).
- [ ] Générer/adapter les icônes et splash screens natifs Android
      (`npx @capacitor/assets generate` ou équivalent).
- [ ] Créer un keystore de signature et builder un AAB **signé** (release
      Play Store ne peut pas être publié non signé).
- [ ] Mettre à jour `BININGA_ORIGINS` sur l'environnement serveur de
      production (voir section 7).
- [ ] Rédiger et publier une politique de confidentialité (voir
      `BININGA_PLAY_STORE_PREP.md`).
- [ ] Publier une page de suppression des données (exigée par Google Play).
- [ ] Tester sur de vrais appareils Android (pas seulement émulateur/CI).
- [ ] Remplir la fiche store complète (captures d'écran, description,
      catégorie — voir `BININGA_PLAY_STORE_PREP.md`).
