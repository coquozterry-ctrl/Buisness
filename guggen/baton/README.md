# Bâton de la Guggen

Bâton d'environ **1,90 m** en bois d'arbre tordu, hérissé de branches cassées sur toute la
montée, parcouru d'une veine dorée, avec en haut une main noueuse qui enserre des cristaux
éclairés par une bougie LED orange.
Conçu pour une **Prusa XL multi-têtes** (plateau 360 × 360 × 360 mm).

| Tête | Écorce | Bâton complet |
|---|---|---|
| ![Tête](apercu/tete.png) | ![Écorce](apercu/ecorce_detail.png) | ![Bâton](apercu/baton_complet.png) |

## Principe

- Un **tube alu (ou fibre de verre) Ø16 mm** passe à l'intérieur et donne la solidité.
  Les tronçons imprimés s'enfilent dessus et se collent. Un bâton tout en plastique
  casserait au premier choc.
- Le tube est droit, mais l'extérieur ondule : la paroi est automatiquement épaissie
  là où le bois s'approche du tube (au moins 3,5 mm partout, vérifié par le script).
- La texture d'écorce (sillons verticaux et gerçures) est continue d'un tronçon à l'autre.
- **18 branches cassées** sortent de l'écorce sur toute la hauteur (4 par tronçon, 2 sur le col).
  Elles pointent vers le haut (42 à 60°) pour s'imprimer sans support. Le bout éclaté
  (bois clair et échardes) est une pièce séparée, à imprimer dans une 4e couleur.
- La **veine dorée** est une pièce séparée, logée dans le sillon de l'écorce : à imprimer
  dans une 2e couleur (PLA soie or ou cuivre).
- Les **cristaux** sont imprimés en même temps que la main, dans une 3e couleur (PLA
  translucide orange ou fumé) : les doigts les enserrent, ils ne s'enlèvent pas.
- La bougie LED se loge dans le haut du col. On retire la main pour l'allumer.

## Fichiers (`stl/`) et filaments

Chaque pièce multi-couleur = plusieurs STL à charger **ensemble** dans PrusaSlicer.

| Tête | Filament |
|---|---|
| T1 | PLA brun écorce (brun chocolat / « tree brown ») |
| T2 | PLA soie or ou cuivre (veine) |
| T3 | PLA translucide orange ou ambre (cristaux) |
| T4 | PLA beige / bois clair (bouts cassés). Un PLA chargé bois va aussi, mais avec une buse de 0,6 mm |

| Pièce | Fichiers | Taille (mm) | Outils |
|---|---|---|---|
| Fût 1 à 4 (1 = pied) | `fut_N_ecorce.stl` + `fut_N_veine.stl` + `fut_N_bois_clair.stl` | ~100 × 100 × 350 | T1, T2, T4 |
| Col | `tete_1_col_ecorce.stl` + `tete_1_col_veine.stl` + `tete_1_col_bois_clair.stl` | ~99 × 89 × 275 | T1, T2, T4 |
| Main + cristaux | `tete_2_main_ecorce.stl` + `tete_2_main_cristaux.stl` | ~137 × 114 × 212 | T1, T3 translucide |

Dans PrusaSlicer : sélectionner les 2 ou 3 fichiers d'une pièce, les glisser ensemble, répondre
**Oui** à « charger comme un seul objet à plusieurs parties », puis attribuer un extrudeur à
chaque partie. Les fichiers partagent la même origine : rien à aligner.

## À acheter

- Tube alu rond Ø16 mm, longueur **1,52 m** (1400 mm de fût + 120 mm dans le col)
- 1 bougie LED « chauffe-plat » orange vacillante (Ø38 mm max)
- 2 clous ou vis M3 × 15 mm pour goupiller la main sur le col
- Colle époxy, peinture (voir finition)
- Embout caoutchouc Ø16 mm pour le pied (facultatif)

## Impression

- Fût et col : debout, 3 parois, 10 % de remplissage gyroïde, sans support.
  Buse 0,4 mm, couches 0,2 mm (0,15 mm pour une écorce plus fine).
- Main : debout, **supports organiques** sous les doigts.
- Cristaux : réglage de pièce dans PrusaSlicer, 2 parois et 0 % de remplissage pour qu'ils
  restent bien translucides.
- Estimation : ~1,2 à 1,5 kg de filament noir, ~100 g d'or, ~60 g de translucide.
  Compter **60 à 90 h** d'impression au total. Le poids final du bâton est d'environ 1,6 à 1,9 kg.

## Montage

1. Enfiler les tronçons sur le tube du pied (`fut_1`) au haut (`fut_4`), en collant chaque
   jointure à l'époxy. Tourner chaque tronçon jusqu'à ce que la veine et l'écorce se raccordent.
2. Emboîter le col sur le haut du tube (douille de 120 mm), coller.
3. Poser la bougie dans le logement en haut du col, emboîter la main, et la goupiller avec
   les 2 clous ou vis M3 dans les trous latéraux (ne pas coller : il faut pouvoir l'ouvrir).

## Finition

Imprimée en brun, l'écorce est déjà crédible. Pour un vrai rendu d'arbre : un jus brun très
foncé dans les sillons, essuyé tout de suite, puis un brossage à sec beige-gris sur les reliefs.
Vernis mat par-dessus, en masquant la veine, les bouts cassés et les cristaux.

Les branches cassées dépassent de 2 à 4 cm : en cortège, elles peuvent accrocher un costume
ou casser sur un choc. Elles sont pleines et ancrées dans le tronc, mais si l'une casse, un
point de colle époxy suffit.

## Modifier le bâton

Tout est généré par `generer_baton.py` (Python 3, `pip install numpy scipy trimesh manifold3d`).
Les cotes sont en haut du fichier : longueur, nombre de tronçons, diamètre du tube, ondulation,
épaisseur de paroi. Change `GRAINE` pour obtenir un autre bâton (noeuds, doigts, cristaux).
