"""Génère le bâton de la Guggen en pièces imprimables (STL).

Principe : un tube alu Ø16 mm sert d'âme (solidité), les pièces imprimées s'enfilent
dessus et forment l'écorce tordue. En haut, une main griffue tient des cristaux
translucides ; sous les cristaux, une cavité accueille une bougie LED.

Usage : python3 generer_baton.py   (écrit les STL dans ./stl et des aperçus dans ./apercu)
Toutes les cotes sont en mm et se règlent dans le bloc PARAMÈTRES.
"""

import math
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh

# ---------------------------------------------------------------- PARAMÈTRES
LONGUEUR_FUT = 1400        # longueur de la partie tube (sans la tête)
NB_SEGMENTS = 7            # 7 x 200 mm : tient dans un plateau de 220 x 220 x 250
DIAM_TUBE = 16.0           # tube alu (ou fibre de verre) Ø16 mm
JEU = 0.4                  # jeu pour enfiler les pièces sur le tube
RAYON_FUT = 21.0           # rayon moyen du fût (≈ Ø42-50 mm avec les reliefs)
PROF_DOUILLE = 120         # profondeur du tube dans le col de la tête
DIAM_LED = 42.0            # cavité pour bougie LED (Ø38 mm, format chauffe-plat)
PROF_LED = 58.0
GRAINE = 7                 # change la graine pour un autre bâton "unique"

PAS_Z = 2.0                # résolution verticale
N_THETA = 96               # résolution autour
SORTIE = Path(__file__).parent

rng = np.random.default_rng(GRAINE)
# noeuds / bosses répartis sur le fût : (z, angle, hauteur, largeur_z, largeur_angle)
NOEUDS = [(rng.uniform(80, LONGUEUR_FUT + 120), rng.uniform(0, 2 * math.pi),
           rng.uniform(2.5, 5.0), rng.uniform(15, 35), rng.uniform(0.35, 0.7))
          for _ in range(18)]


# ---------------------------------------------------------------- OUTILS MAILLAGE
def vers_manifold(m: trimesh.Trimesh) -> Manifold:
    if m.volume < 0:
        m.invert()
    return Manifold(Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                         tri_verts=np.asarray(m.faces, np.uint32)))


def vers_trimesh(man: Manifold) -> trimesh.Trimesh:
    mm = man.to_mesh()
    return trimesh.Trimesh(mm.vert_properties[:, :3], mm.tri_verts, process=True)


def loft(anneaux: np.ndarray) -> trimesh.Trimesh:
    """anneaux : (n_z, n_theta, 3) -> solide fermé (bouchons en éventail au centre)."""
    nz, nt, _ = anneaux.shape
    v = anneaux.reshape(-1, 3)
    f = []
    for i in range(nz - 1):
        for j in range(nt):
            a, b = i * nt + j, i * nt + (j + 1) % nt
            c, d = a + nt, b + nt
            f += [(a, b, d), (a, d, c)]
    bas = anneaux[0].mean(0)
    haut = anneaux[-1].mean(0)
    ib, ih = len(v), len(v) + 1
    v = np.vstack([v, bas, haut])
    top = (nz - 1) * nt
    for j in range(nt):
        f.append((ib, (j + 1) % nt, j))
        f.append((ih, top + j, top + (j + 1) % nt))
    return trimesh.Trimesh(v, np.array(f), process=True)


def cylindre(r, h, z0=0.0, x=0.0, y=0.0, n=64) -> Manifold:
    return Manifold.cylinder(h, r, r, n).translate((x, y, z0))


# ---------------------------------------------------------------- ÉCORCE
def centre(z):
    """Ligne moyenne : droite le long du tube, puis le col se cambre en S."""
    z0 = LONGUEUR_FUT + PROF_DOUILLE - 20
    t = np.clip((z - z0) / 260.0, 0, 1)
    x = 38 * np.sin(math.pi * t) * t
    y = -12 * np.sin(2 * math.pi * t)
    return x, y


def rayon_base(z):
    r = RAYON_FUT + 1.5 * np.sin(z / 170.0) + 0.8 * np.sin(z / 53.0 + 1)
    r = r - 2.0 * np.exp(-z / 60.0)                              # pied un peu affiné
    h = LONGUEUR_FUT
    r = r + 9.0 * np.clip((z - h) / 220.0, 0, 1) ** 1.5           # le col s'élargit vers la main
    return r


def rayon(z, th):
    """Rayon de l'écorce : 3 brins tordus + noeuds + fissures."""
    torsion = 2 * math.pi * z / 340.0 + 0.6 * np.sin(z / 210.0)
    r = rayon_base(z)
    r = r + 4.5 * np.cos(3 * th - torsion)                        # brins enroulés
    r = r + 1.0 * np.cos(5 * th + 0.7 * torsion + 1.3)
    for (zn, an, hn, wz, wa) in NOEUDS:
        da = np.angle(np.exp(1j * (th - an)))
        r = r + hn * np.exp(-((z - zn) / wz) ** 2 - (da / wa) ** 2)
    fissure = np.abs(np.sin(11 * th - 0.25 * torsion + 0.8 * np.sin(z / 23.0)))
    r = r - 0.9 * (fissure < 0.18)                                # fissures d'écorce
    r = r + 0.35 * np.sin(29 * th + z / 7.0) * np.sin(z / 11.0)   # grain fin
    return r


def anneaux_ecorce(z0, z1):
    zs = np.arange(z0, z1 + 1e-6, PAS_Z)
    th = np.linspace(0, 2 * math.pi, N_THETA, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    R = rayon(Z, TH)
    cx, cy = centre(Z)
    return np.stack([cx + R * np.cos(TH), cy + R * np.sin(TH), Z], -1)


def ecorce(z0, z1) -> Manifold:
    return vers_manifold(loft(anneaux_ecorce(z0, z1)))


# ---------------------------------------------------------------- PIÈCES
def segment_fut(i) -> Manifold:
    h = LONGUEUR_FUT / NB_SEGMENTS
    z0, z1 = i * h, (i + 1) * h
    s = ecorce(z0, z1) - cylindre(DIAM_TUBE / 2 + JEU / 2, h + 2, z0 - 1)
    return s.translate((0, 0, -z0))


Z_COL0 = LONGUEUR_FUT
Z_COL1 = LONGUEUR_FUT + 230
TENON_R, TENON_H = 11.0, 12.0


def col() -> Manifold:
    s = ecorce(Z_COL0, Z_COL1)
    s = s - cylindre(DIAM_TUBE / 2 + JEU / 2, PROF_DOUILLE, Z_COL0 - 1)   # douille borgne
    cx, cy = centre(Z_COL1)
    s = s + cylindre(TENON_R, TENON_H, Z_COL1 - 1, cx, cy)               # tenon vers la main
    return s.translate((0, 0, -Z_COL0))


def tube_balaye(pts, rayons, n=24) -> Manifold:
    """Tube le long d'une courbe 3D (repère par transport parallèle)."""
    pts = np.asarray(pts, float)
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    nrm = np.cross(tang[0], [0, 0, 1.0] if abs(tang[0][2]) < 0.9 else [1.0, 0, 0])
    nrm /= np.linalg.norm(nrm)
    anneaux = []
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    for k, (p, t) in enumerate(zip(pts, tang)):
        nrm = nrm - np.dot(nrm, t) * t
        nrm /= np.linalg.norm(nrm)
        b = np.cross(t, nrm)
        anneaux.append(p + rayons[k] * (np.outer(np.cos(th), nrm) + np.outer(np.sin(th), b)))
    return vers_manifold(loft(np.array(anneaux)))


def main_griffue():
    """Paume creuse (cavité LED) + 5 doigts noueux qui enserrent les cristaux."""
    hp = 80.0                                            # hauteur de la paume
    zs = np.arange(0, hp + 1e-6, PAS_Z)
    th = np.linspace(0, 2 * math.pi, N_THETA, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    R = rayon(Z + Z_COL1, TH) + 10.0 * (Z / hp) ** 1.5    # l'écorce du col s'évase en paume
    paume = vers_manifold(loft(np.stack([R * np.cos(TH), R * np.sin(TH), Z], -1)))

    doigts = []
    rp = float(R[-1].mean()) - 5
    for k in range(5):
        a = 2 * math.pi * k / 5 + rng.uniform(-0.2, 0.2)
        L = rng.uniform(125, 150)
        s = np.linspace(0, 1, 70)
        ouv = rng.uniform(20, 26)                         # écartement max
        rad = rp + ouv * np.sin(math.pi * s * 0.75) - 7 * s ** 6   # bout crochu vers l'intérieur
        z = hp - 15 + L * s
        tw = a + 0.3 * s * rng.choice([-1, 1])            # doigts légèrement vrillés
        pts = np.stack([rad * np.cos(tw), rad * np.sin(tw), z], -1)
        r = 9.0 * (1 - s) ** 0.7 + 1.5
        for pos in (0.3, 0.6):                           # jointures
            r = r + 2.5 * np.exp(-((s - pos) / 0.05) ** 2) * (1 - s)
        doigts.append(tube_balaye(pts, r))

    main = paume
    for d in doigts:
        main = main + d
    main = main - cylindre(DIAM_LED / 2, PROF_LED + 200, hp - PROF_LED)  # cavité LED
    main = main - cylindre(TENON_R + JEU / 2, TENON_H + 1, -1)           # mortaise
    return main, hp


def cristaux():
    """Bouchon qui s'emboîte dans la cavité + grappe de cristaux (PETG translucide)."""
    bouchon_r = DIAM_LED / 2 - JEU
    piece = cylindre(bouchon_r, 12, 0) + cylindre(bouchon_r + 2.5, 3, 12)  # collerette d'appui

    def cristal(r, h, pointe, inclin, azim, dx, dy):
        prisme = Manifold.cylinder(h, r, r, 6)
        tete = Manifold.cylinder(pointe + 1, r, 0.0, 6).translate((0, 0, h - 1))
        c = (prisme + tete).translate((0, 0, -6))
        c = c.rotate((inclin, 0, 0)).rotate((0, 0, azim)).translate((dx, dy, 15))
        return c.trim_by_plane((0, 0, 1), 14.0)          # rien sous la collerette

    groupe = [cristal(14, 85, 30, 0, 0, 0, 0)]
    for k in range(8):
        a = 360 * k / 8 + rng.uniform(-12, 12)
        d = rng.uniform(13, 16)
        groupe.append(cristal(rng.uniform(6, 10), rng.uniform(30, 55), rng.uniform(10, 16),
                              rng.uniform(10, 25), a + 90,
                              d * math.cos(math.radians(a)), d * math.sin(math.radians(a))))
    for c in groupe:
        piece = piece + c
    return piece


# ---------------------------------------------------------------- MAIN
if __name__ == "__main__":
    (SORTIE / "stl").mkdir(exist_ok=True)
    (SORTIE / "apercu").mkdir(exist_ok=True)
    h = LONGUEUR_FUT / NB_SEGMENTS
    Zg, Tg = np.meshgrid(np.arange(0, Z_COL0 + PROF_DOUILLE, PAS_Z),
                         np.linspace(0, 2 * math.pi, N_THETA), indexing="ij")
    paroi = rayon(Zg, Tg).min() - DIAM_TUBE / 2 - JEU / 2
    print(f"Paroi minimale autour du tube : {paroi:.1f} mm")
    assert paroi >= 3.0, "paroi trop fine, augmente RAYON_FUT"
    assemble = []
    BOIS, OR = np.array([0.45, 0.33, 0.24]), np.array([0.75, 0.9, 1.0])

    for i in range(NB_SEGMENTS):
        m = vers_trimesh(segment_fut(i))
        m.export(SORTIE / "stl" / f"fut_{i + 1:02d}.stl")
        assemble.append((m.copy().apply_translation((0, 0, i * h)), BOIS))
        print(f"fut_{i + 1:02d}.stl  {m.extents.round(1)} mm  {m.volume / 1000:.0f} cm3")

    m = vers_trimesh(col())
    m.export(SORTIE / "stl" / "tete_1_col.stl")
    assemble.append((m.copy().apply_translation((0, 0, Z_COL0)), BOIS))
    print(f"tete_1_col.stl  {m.extents.round(1)} mm  {m.volume / 1000:.0f} cm3")

    main, hp = main_griffue()
    m = vers_trimesh(main)
    m.export(SORTIE / "stl" / "tete_2_main.stl")
    cx, cy = centre(Z_COL1)
    assemble.append((m.copy().apply_translation((cx, cy, Z_COL1)), BOIS))
    print(f"tete_2_main.stl  {m.extents.round(1)} mm  {m.volume / 1000:.0f} cm3")

    m = vers_trimesh(cristaux())
    m.export(SORTIE / "stl" / "tete_3_cristaux.stl")
    assemble.append((m.copy().apply_translation((cx, cy, Z_COL1 + hp - 12)), OR))
    print(f"tete_3_cristaux.stl  {m.extents.round(1)} mm  {m.volume / 1000:.0f} cm3")

    for p, _ in assemble:
        assert p.is_watertight and p.body_count == 1, "maillage défectueux"

    # assemblage complet (pour visualiser, pas pour imprimer)
    bois = trimesh.util.concatenate([m for m, c in assemble if c is BOIS])
    bois.export(SORTIE / "apercu" / "assemblage_bois.stl")
    assemble[-1][0].export(SORTIE / "apercu" / "assemblage_cristaux.stl")
    total = sum(p.volume for p, _ in assemble) / 1000
    print(f"Volume plein total : {total:.0f} cm3")
