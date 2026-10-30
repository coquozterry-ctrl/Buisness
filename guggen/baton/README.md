# Bâton de la Guggen

Bâton d'environ **1,75 m**, en écorce tordue, avec en haut une main griffue qui tient des
cristaux lumineux (bougie LED orange dessous).

![Tête](apercu/tete.png)

## Principe

Un **tube alu (ou fibre de verre) Ø16 mm** sert d'âme : c'est lui qui donne la solidité.
Les pièces imprimées s'enfilent dessus comme des perles et forment l'écorce. Un bâton
100 % imprimé de 1,75 m casserait au premier choc, donc ce tube est indispensable.

| Fichier (`stl/`) | Taille (mm) | Matière conseillée |
|---|---|---|
| `fut_01.stl` à `fut_07.stl` | ~55 × 55 × 200 | PETG ou PLA+, couleur bois/noir |
| `tete_1_col.stl` | ~82 × 71 × 241 | idem |
| `tete_2_main.stl` | ~110 × 123 × 213 | idem, **supports arborescents** |
| `tete_3_cristaux.stl` | ~74 × 67 × 124 | **PETG translucide** (orange ou naturel) |

Le motif de l'écorce est continu d'une pièce à l'autre : les jointures se voient peu une fois
collées et mastiquées.

## À acheter

- Tube alu rond Ø16 mm, longueur 1,52 m (1400 mm de fût + 120 mm dans le col)
- 1 bougie LED « chauffe-plat » orange vacillante (Ø38 mm max)
- Colle époxy, mastic, sous-couche, peinture
- Embout caoutchouc Ø16 mm pour le pied (facultatif)

## Impression

- Plateau minimum : 220 × 220 × **245 mm** de haut (pour le col)
- Fût et col : 3 parois, 10-15 % de remplissage, debout, sans support
- Main : debout, supports arborescents (« tree ») pour les doigts
- Cristaux : 2 parois, 0 à 5 % de remplissage pour qu'ils restent creux et laissent passer la lumière
- Poids estimé : ~1,1 à 1,4 kg de filament, ~40 à 60 h d'impression en tout

## Montage

1. Enfiler `fut_01` (le pied) à `fut_07` sur le tube dans l'ordre, en collant chaque
   jointure à l'époxy. Les pièces se tournent pour que le motif se raccorde.
2. Emboîter `tete_1_col` sur le haut du tube (douille de 120 mm), coller.
3. Coller `tete_2_main` sur le tenon du col.
4. Poser la bougie LED dans la paume, puis emboîter les cristaux par-dessus.
   On les retire pour allumer ou changer la pile. Si ça glisse trop, un tour de ruban adhésif.

## Finition (c'est elle qui fait le rendu)

Poncer et mastiquer les jointures, sous-couche, noir mat, puis brossage à sec brun et gris
pour le bois calciné. Pour imiter la veine dorée de la photo, un trait de peinture or ou
cuivre dans un des sillons tordus.

## Modifier le bâton

Tout est généré par `generer_baton.py` (Python 3, `pip install numpy trimesh manifold3d`).
Les cotes se règlent en haut du fichier : longueur, nombre de segments, diamètre du tube,
taille de la bougie. Change `GRAINE` pour obtenir un bâton différent (noeuds, doigts, cristaux).
