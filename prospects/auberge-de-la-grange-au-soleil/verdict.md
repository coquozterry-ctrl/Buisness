# Verdict : Auberge de la Grange au Soleil

Jugé le 25.10.2026 (un dimanche, à 17h43 heure du serveur). Captures 390×844 et 1440×900 dans `variantes/*/captures/` (`mobile.png`, `mobile-premier-ecran.png`, `desktop.png`).

## Notes

| Critère (poids) | A, chaleureux | B, moderne | C, conversion |
|---|---|---|---|
| Fidélité au cahier des charges et aux données (25 %) | 8 | 7 | 5 |
| Action principale évidente sur mobile (20 %) | 9 | 8 | 10 |
| Identité de CE restaurant (20 %) | 8 | 6 | 7 |
| Qualité visuelle et lisibilité mobile (15 %) | 8 | 7 | 8 |
| SEO local et accessibilité (10 %) | 8 | 7 | 9 |
| Effet « waouh » sur téléphone (10 %) | 7 | 6 | 5 |
| **Total pondéré / 10** | **8,10** | **6,90** | **7,25** |

**La variante A gagne.** Si C n'avait pas son indicateur « Fermé », elle arriverait à environ 7,9 et serait juste derrière A. C'est la variante qui pousse le plus à appeler, mais telle qu'elle est livrée, elle ne peut pas être montrée.

## Vérifications factuelles

| Contrôle | A | B | C |
|---|---|---|---|
| Prix comparés à menu.json, ligne par ligne | 94/94 justes | 94/94 justes | 94/94 justes (les 4 sauces sont regroupées sur une ligne, prix justes) |
| Écarts dans les fourchettes de prix | aucun | aucun | « Desserts 9.- à 13.- » alors que les glaces sont à 3.50 |
| « frais / fraîche » | seulement pour les pâtes et les raviolis | seulement pour les pâtes et les raviolis | seulement pour les pâtes et les raviolis |
| « poisson frais » ou « produits frais » | aucun ; « poisson surgelé » est indiqué | aucun ; surgelé indiqué | aucun ; surgelé indiqué |
| pirder.top | absent | absent | absent |
| Note Tripadvisor 3,8 | absente | absente | absente |
| Citation d'avis inventée | aucune (emplacement prévu) | aucune | aucune |
| JSON-LD | se lit sans erreur, pas d'aggregateRating | se lit sans erreur, pas d'aggregateRating | se lit sans erreur, pas d'aggregateRating, 9 MenuItem avec leurs prix |
| Défilement horizontal à 360 px (scrollWidth) | 360, aucun | 360, aucun | 360, aucun |
| Poids du fichier | 57 340 octets | 50 635 octets | 41 865 octets |
| Polices Google externes | 3 familles | 1 famille | 1 famille |
| Étoiles affichées pour 4,5 | ★★★★½ (juste) | ★★★★★ (exagéré) | ★★★★★ (exagéré) |

## Remarques par variante

### A, chaleureux (gagnante)
- **Mobile** : dès le premier écran, on voit l'adresse et le numéro cliquable dans le bandeau du haut, le nom en h1, la promesse « Toutes nos pâtes sont fraîches et faites maison » en grand, la note 4,5 Google, un gros bouton « Appeler le 024 471 15 12 » et « Itinéraire ». En bas, une barre fixe propose Appeler, Itinéraire, Carte et Horaires.
- **Identité** : terracotta et olive, nappe vichy, titres manuscrits (« Buon appetito »). On reconnaît une auberge-trattoria, pas un modèle générique. Les Pouilles sont citées dans le texte d'accroche et la puccia est expliquée.
- **Carte** : complète (94 plats) et repliable. Les pâtes et les pizzas sont ouvertes par défaut, le badge « Carte à confirmer » est en tête et la provenance est indiquée (poisson surgelé).
- **Défauts** : la page est longue (environ 15 000 px sur mobile). Les horaires n'arrivent qu'après environ 6 écrans, mais la barre fixe y mène en un geste. La galerie contient 5 emplacements photo vides et ressemble à un nuancier. 3 polices Google sont chargées.

### B, moderne
- C'est propre et la carte est bien navigable, avec des liens vers chaque rubrique. Mais on pourrait mettre n'importe quel restaurant dans ce noir et blanc façon start-up : rien ne rappelle une auberge ni les Pouilles, sauf dans le texte.
- Le h1 contient le slogan, pas le nom du restaurant : c'est moins bon pour le référencement local.
- Le premier écran mobile se termine sur un grand bloc orange vide (l'emplacement photo). Sa légende « Photo des pâtes fraîches maison » n'indique pas « à fournir ».
- Les formulations douteuses que B signale lui-même sont confirmées :
  - le badge « Pâtes maison » est collé sur « Premiers plats de terre », qui contient la parmigiana ;
  - « Pizzas, pâtes maison et puccias à emporter » : seul l'emporter en général est confirmé.
- Les animations d'apparition (`animation-timeline: view()`) laissent des zones blanches sur une capture pleine page. J'ai vérifié qu'en défilant réellement, l'opacité revient à 1. Cela reste un risque si le patron fait une capture d'écran ou imprime la page.

### C, conversion
- C'est le meilleur premier écran pour la conversion. On y trouve le numéro dans l'en-tête, deux boutons de 60 px, un bandeau de prix « 15.- / 22.- / 10.- » et un bandeau jaune qui avertit de l'heure de pointe. Le JSON-LD est le plus riche.
- **Rédhibitoire en l'état** : l'indicateur « ouvert maintenant » est calculé sur des horaires d'exemple inventés (samedi 9h00, dimanche « Fermé »). Pendant le jugement, un dimanche à 17h43, le premier écran affichait **« Fermé pour le moment »**, et la ligne « Dimanche : Fermé » était surlignée en rouge dans le tableau. Montrée au patron, cette page lui annonce une fermeture qui n'existe peut-être pas : on perd sa confiance tout de suite. Le badge « exemple » à côté ne suffit pas. **À désactiver tant que les vrais horaires ne sont pas confirmés.**
- La sous-rubrique « Pâtes fraîches maison » coiffe la parmigiana, le bouton dit « Table ou pizza à emporter », et la fourchette des desserts est fausse.
- Le rouge et vert tricolore évoque bien la pizzeria, mais il évoque moins l'auberge et l'accent des Pouilles que A.

## Corrections appliquées dans `site-final/index.html` (copie de A)
1. La rubrique de la carte « Pâtes fraîches maison », qui contenait la parmigiana, s'appelle maintenant « Premiers plats & raviolis ». Son sous-titre liste ce qu'elle contient et cite la mention de la carte entre guillemets. Le nom de la section dans le JSON-LD a été aligné.
2. « Orecchiette, tagliatelle, gnocchis, raviolis : tous faits maison » devient « Orecchiette, tagliatelle, raviolis : toutes nos pâtes sont fraîches et faites maison ». Je n'affirme plus rien sur les gnocchis.
3. Le bloc final « commander vos pizzas et vos pâtes à emporter » devient « réserver une table ou passer une commande à emporter » : seul l'emporter en général est confirmé.
4. Parking : « Places de parc à proximité, à confirmer » devient « À confirmer avec l'établissement ». Je n'affirme plus que des places existent.
5. Ajout du Plus code (7WHH+CP Collombey-Muraz) sous l'adresse.

Après correction : JSON-LD revérifié (il se lit sans erreur), toujours aucun pirder, aucun 3,8, aucun aggregateRating, pas de défilement horizontal à 360 px.

## Ce qui reste à faire (par priorité)
1. **Horaires réels** : le tableau d'exemple « Lu–Ve 8h00–22h30, Sa/Di à préciser » est balisé, mais c'est la première question du client. Il faut les obtenir du patron, puis ajouter `openingHoursSpecification` au JSON-LD. On pourra alors reprendre l'indicateur « ouvert maintenant » de C, mais seulement avec les vrais horaires.
2. **Photos réelles** : il y a 11 emplacements vides, dont 5 dans la galerie, qui alourdissent la page. Il faut réduire la galerie à 3 emplacements tant qu'on n'a pas de photos, et en priorité obtenir la façade avec la terrasse, la pizza La Grange au Soleil et les orecchiette.
3. **Reprendre de C le bandeau de prix « Pizzas dès 15.- · Pâtes dès 22.- · Menu enfant dès 10.- »** juste sous le hero, ainsi que le bandeau « Midi (11h–14h) : appelez avant de venir ». Il faut aussi remonter le bloc horaires et affluence avant la carte, ou au moins le résumer : aujourd'hui il est à environ 6 écrans.
4. **Reprendre de C les `MenuItem` avec leurs prix dans le JSON-LD**, au moins pour les plats de la sélection « À goûter ».
5. **Faire valider la carte** (noms et prix des pizzas transcrits d'une photo floue) et vérifier si les glaces sont facturées à la boule (3.50).
6. **Poids et dépendances** : 3 polices Google (Fraunces, Caveat, Nunito Sans). Il faut en héberger une seule localement, ou garder les polices système de repli, et supprimer Caveat si la vitesse compte.
7. Mineur : la burrata réutilise le dégradé « terrasse » comme emplacement photo. L'emplacement « Notre histoire » est à remplir avec le patron.
