# Renaissance 66

App perso (sans abonnement) pour ancrer de nouvelles habitudes en 66 jours, façon jeu de rôle :
quêtes quotidiennes, XP, niveaux, 4 attributs, série de jours, mode difficile avec pénalités,
minuteur focus, calendrier des 66 jours, export/import de sauvegarde.

Inspirée des *mécaniques* des apps « life reset » (pas de leur nom, design ni contenu).

## L'utiliser sur ton téléphone

C'est un simple site (HTML/JS, aucun serveur, aucune dépendance). Il faut juste l'héberger :

1. Sur GitHub : **Settings → Pages → Deploy from a branch**, choisir la branche et le dossier racine.
2. Ouvrir `https://<ton-pseudo>.github.io/<repo>/apps/renaissance-66/` sur le téléphone.
3. iPhone : Safari → Partager → **Sur l'écran d'accueil**. Android : Chrome → menu → **Installer l'application**.

⚠️ Les données restent **uniquement dans le navigateur du téléphone**. Si tu effaces les données
de Safari/Chrome, tu perds ton historique : utilise **Réglages → Exporter** régulièrement.

## Tester en local

```bash
cd apps/renaissance-66 && python3 -m http.server 8000
# puis http://localhost:8000
```
