# Signalements BININGA — livraison en cours

## Contrat validé
- Audience et réclamation conservées ; ajouter Signaler un sinistre.
- Description, coordonnées et localisation volontaire ; caméra et import photo/vidéo natifs.
- Dossier et référence dans la base métier actuelle ; médias dans CloudKit.
- Admin : lecture et téléchargement explicite ; aucun téléchargement automatique.
- Expiration vidéo = minimum(réception UTC + 7 jours, première ouverture UTC + 48 heures).
- La première ouverture doit être enregistrée une seule fois atomiquement côté serveur.
- Bloquer toute lecture après expiration même si la purge physique doit être réessayée.
- Conserver dossier, référence, dates et état de suppression ; ne pas conserver les octets des médias dans la base métier.
- Purge effective CloudKit par worker planifié avec reprise sur erreur, contrôlée et testée avant activation.

## Contraintes vérifiées
CloudKit server-to-server accède à la base publique d’un conteneur ; le type de record des sinistres doit retirer les droits de lecture aux rôles publics. Toutes les lectures sont médiées par le serveur après contrôle de session et des droits du dossier.
Source : https://developer.apple.com/library/archive/documentation/DataManagement/Conceptual/CloudKitWebServicesReference/SettingUpWebServices.html

## État réel
Les règles temporelles et leur tests sont écrits. La frise SwiftUI et le bandeau texte sont préparés.
Le formulaire, les routes de transfert, le stockage CloudKit et la purge ne sont PAS activés.
Il faut vérifier/créer le conteneur BININGA, les rôles, une clé server-to-server propre au conteneur, le stockage serveur de la clé et le déclencheur de purge.
Le badge PCT est textuel ; il ne constitue pas le logo officiel demandé.
Aucune clé n’est incorporée à l’application. Aucun média réel n’est envoyé tant que les contrôles CloudKit et les tests bout en bout ne sont pas terminés.
