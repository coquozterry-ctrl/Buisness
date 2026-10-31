"""Génère le bâton de la Guggen en pièces imprimables multi-matériaux (Prusa XL 5 têtes).

Principe : un tube alu Ø16 mm sert d'âme (solidité). Autour, un fût droit en bois sombre
veiné, enlacé de lianes qui s'enroulent dans les deux sens et s'évasent en racines au pied.
Au tiers supérieur, une poignée en cuir enroulé avec un médaillon. En haut, les lianes
s'ouvrent et tiennent un bouquet de cristaux violets et verts, éclairé par une bougie LED
logée dans le col. Des petits cristaux pendants s'accrochent à la poignée.

Têtes : T1 bois sombre, T2 lianes (bronze), T3 cristaux violets, T4 cristaux verts, T5 cuir.

Usage : python3 generer_baton.py   (écrit les STL dans ./stl)
Toutes les cotes sont en mm et se règlent dans le bloc PARAMÈTRES.
"""

import math
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh
from scipy.spatial import cKDTree

# ---------------------------------------------------------------- PARAMÈTRES
LONGUEUR_FUT = 1400        # longueur de la partie tube (sans la tête)
NB_SEGMENTS = 4            # 4 x 350 mm : plateau Prusa XL 360 x 360 x 360
DIAM_TUBE = 16.0           # tube alu (ou fibre de verre) Ø16 mm
JEU = 0.4                  # jeu pour enfiler les pièces sur le tube
PAROI_MIN = 3.5            # paroi minimale autour du tube
RAYON_FUT = 15.0           # rayon du fût en bois (Ø30, ≈ Ø40-45 avec les lianes)
NB_LIANES = 14
POIGNEE = (1120.0, 1350.0) # zone de la poignée en cuir
PROF_DOUILLE = 120         # profondeur du tube dans le col
DIAM_LED = 42.0            # bougie LED « chauffe-plat » Ø38 mm
GRAINE = 11                # change la graine pour un autre bâton "unique"

PAS = 0.7                  # finesse du maillage
SORTIE = Path(__file__).parent

R_ALESAGE = DIAM_TUBE / 2 + JEU / 2
Z_COL0 = LONGUEUR_FUT
Z_COL1 = LONGUEUR_FUT + 160        # col : douille du tube + logement de la bougie
R_TENON, H_TENON = 24.0, 25.0      # emboîtement bouquet / col (contient la bougie)
R_TETE = 28.0                      # rayon du fût en haut du col
HP = 40.0                          # hauteur de la base du bouquet
H_SEG = LONGUEUR_FUT / NB_SEGMENTS


# ---------------------------------------------------------------- OUTILS MAILLAGE
def vers_manifold(m: trimesh.Trimesh) -> Manifold:
    if m.volume < 0:
        m.invert()
    return Manifold(Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                         tri_verts=np.asarray(m.faces, np.uint32)))


def vers_trimesh(man: Manifold) -> trimesh.Trimesh:
    mm = man.to_mesh()
    return trimesh.Trimesh(mm.vert_properties[:, :3], mm.tri_verts, process=False)


def loft(anneaux: np.ndarray) -> Manifold:
    """anneaux : (n_z, n_theta, 3) -> solide fermé (bouchons en éventail au centre)."""
    nz, nt, _ = anneaux.shape
    i, j = np.meshgrid(np.arange(nz - 1), np.arange(nt), indexing="ij")
    a = (i * nt + j).ravel()
    b = (i * nt + (j + 1) % nt).ravel()
    c, d = a + nt, b + nt
    f = [np.stack([a, b, d], 1), np.stack([a, d, c], 1)]
    ib, ih = nz * nt, nz * nt + 1
    j = np.arange(nt)
    top = (nz - 1) * nt
    f.append(np.stack([np.full(nt, ib), (j + 1) % nt, j], 1))
    f.append(np.stack([np.full(nt, ih), top + j, top + (j + 1) % nt], 1))
    v = np.vstack([anneaux.reshape(-1, 3), anneaux[0].mean(0), anneaux[-1].mean(0)])
    return vers_manifold(trimesh.Trimesh(v, np.vstack(f), process=False))


def normales(anneaux):
    """Normales sortantes d'une grille (n_z, n_theta, 3)."""
    dt = np.roll(anneaux, -1, 1) - np.roll(anneaux, 1, 1)
    dz = np.gradient(anneaux, axis=0)
    n = np.cross(dt, dz)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)


def cylindre(r, h, z0=0.0, x=0.0, y=0.0, n=96) -> Manifold:
    return Manifold.cylinder(h, r, r, n).translate((x, y, z0))


def tranche(z0, z1) -> Manifold:
    return Manifold.cube((800, 800, z1 - z0)).translate((-400, -400, z0))


def union(pieces):
    pieces = [p for p in pieces if p is not None]
    tout = pieces[0]
    for p in pieces[1:]:
        tout = tout + p
    return tout


def lisse(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- TEXTURES
class Cellules:
    """Bruit cellulaire 3D (Worley)."""

    def __init__(self, taille, etirement, graine):
        g = np.random.default_rng(graine)
        self.S = np.array([1.0, 1.0, 1.0 / etirement])
        lo = np.array([-150, -150, -50]) * self.S
        hi = np.array([150, 150, Z_COL1 + 400]) * self.S
        axes = [np.arange(l, h, taille) for l, h in zip(lo, hi)]
        base = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
        self.arbre = cKDTree(base + g.uniform(0, taille, base.shape))
        self.h = g.uniform(-1, 1, len(base))

    def __call__(self, p):
        d, i = self.arbre.query(p.reshape(-1, 3) * self.S, k=2, workers=-1)
        return (d[:, 1] - d[:, 0]).reshape(p.shape[:-1]), self.h[i[:, 0]].reshape(p.shape[:-1])


VEINES_BOIS = Cellules(5.0, 7.0, GRAINE)        # longues fentes du bois
ECORCE_LIANE = Cellules(3.5, 2.5, GRAINE + 1)   # petite écorce des lianes


def grain_bois(p):
    """Bois sombre veiné : longues fentes fines + fibres."""
    e, h = VEINES_BOIS(p)
    fente = np.clip(1 - e / 1.1, 0, 1)
    fibres = np.sin(np.arctan2(p[..., 1], p[..., 0]) * 40 + p[..., 2] * 0.05 + 2 * np.sin(p[..., 2] / 37))
    return -0.9 * fente + 0.15 * h + 0.12 * fibres


def ecorce_liane(p):
    e, h = ECORCE_LIANE(p)
    return -0.7 * np.clip(1 - e / 0.9, 0, 1) + 0.2 * h


def texturer(anneaux, fonction, echelle=1.0):
    d = fonction(anneaux) * np.broadcast_to(echelle, anneaux.shape[:-1])
    return anneaux + normales(anneaux) * d[..., None]


def tube_balaye(pts, rayons, n=24, texture=None, aplat=1.0):
    """Tube le long d'une courbe 3D (repère par transport parallèle)."""
    pts = np.asarray(pts, float)
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    nrm = np.cross(tang[0], [0, 0, 1.0] if abs(tang[0][2]) < 0.9 else [1.0, 0, 0])
    nrm /= np.linalg.norm(nrm)
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    anneaux = []
    for p, t, r in zip(pts, tang, rayons):
        nrm = nrm - np.dot(nrm, t) * t
        nrm /= np.linalg.norm(nrm)
        b = np.cross(t, nrm)
        anneaux.append(p + r * (np.outer(np.cos(th), nrm) + aplat * np.outer(np.sin(th), b)))
    anneaux = np.array(anneaux)
    if texture is not None:
        anneaux = texturer(anneaux, ecorce_liane, np.asarray(texture)[:, None] * np.ones(n))
    return loft(anneaux)


# ---------------------------------------------------------------- FÛT
def rayon_fut(z):
    r = RAYON_FUT + 0.6 * np.sin(z / 190.0) + 0.3 * np.sin(z / 61.0)
    return r + (R_TETE - RAYON_FUT) * lisse((z - Z_COL0 - PROF_DOUILLE + 30) / (Z_COL1 - Z_COL0 - PROF_DOUILLE + 30))


def fut(z0, z1):
    zs = np.linspace(z0, z1, int(round((z1 - z0) / PAS)) + 1)
    th = np.linspace(0, 2 * math.pi, 200, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    R = rayon_fut(Z)
    s = texturer(np.stack([R * np.cos(TH), R * np.sin(TH), Z], -1), grain_bois)
    s[..., 2] = np.where(np.isin(Z, (z0, z1)), Z, s[..., 2])
    return loft(s)


# ---------------------------------------------------------------- LIANES
g0 = np.random.default_rng(GRAINE)
LIANES = []
for i in range(NB_LIANES):
    epaisse = i < 3
    LIANES.append(dict(
        r=g0.uniform(4.2, 5.5) if epaisse else g0.uniform(2.6, 4.0),
        sens=1 if i % 2 else -1,
        pas=g0.uniform(260, 520),
        phase=g0.uniform(0, 2 * math.pi),
        decol=g0.uniform(0, 2 * math.pi),
    ))


def angle_liane(L, z):
    return L["phase"] + L["sens"] * 2 * math.pi * z / L["pas"] + 0.35 * np.sin(z / 83.0 + L["phase"])


def rayon_liane(L, z):
    r = L["r"] * (1 + 0.12 * np.sin(z / 47.0 + L["phase"]))
    return r * (1 + 0.6 * np.exp(-z / 40.0))                      # plus épaisses au pied (racines)


def orbite_liane(L, z):
    rv = rayon_liane(L, z)
    decolle = 0.45 * np.clip(np.sin(z / 70.0 + L["decol"]), 0, 1) ** 4   # par endroits elle se décolle
    racine = 16.0 * np.exp(-z / 38.0)                                     # évasement en racines
    sous_cuir = lisse((z - POIGNEE[0] + 5) / 25) * lisse((POIGNEE[1] + 5 - z) / 25)
    return rayon_fut(z) + rv * (0.45 + decolle) * (1 - sous_cuir) - rv * 1.2 * sous_cuir + racine


def axe_liane(L, z):
    a, o = angle_liane(L, z), orbite_liane(L, z)
    return np.stack([o * np.cos(a), o * np.sin(a), z], -1)


def lianes(z0, z1):
    morceaux = []
    for L in LIANES:
        z = np.arange(max(z0 - 15, 0.0), z1 + 15, 0.6)
        if z[0] == 0.0:                                                # le pied pose bien à plat
            z = np.concatenate([[-3.0], z])
        morceaux.append(tube_balaye(axe_liane(L, z), rayon_liane(L, z), n=40,
                                    texture=np.full(len(z), 0.6)))
    return union(morceaux) ^ tranche(z0, z1)


# ---------------------------------------------------------------- POIGNÉE
def cuir():
    """Lanière de cuir enroulée en hélice, chaque tour recouvrant le précédent."""
    z0, z1 = POIGNEE
    zs = np.linspace(z0, z1, int((z1 - z0) / 0.5) + 1)
    th = np.linspace(0, 2 * math.pi, 240, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    q = (Z - z0) / 15.0 + TH / (2 * math.pi)
    f = q - np.floor(q)
    bord = lisse(np.minimum(Z - z0, z1 - Z) / 4)
    R = rayon_fut(Z) + (3.0 + 1.4 * f ** 1.5) * bord              # les lianes passent dessous
    enveloppe = loft(np.stack([R * np.cos(TH), R * np.sin(TH), Z], -1))
    return enveloppe - cylindre(RAYON_FUT - 2, z1 - z0 + 2, z0 - 1)


def medaillon():
    z = POIGNEE[1] - 22
    a = angle_liane(LIANES[0], z) + 2.0
    r = float(rayon_fut(z)) + 4.0
    p = np.array([r * math.cos(a), r * math.sin(a), z])
    d = np.array([math.cos(a), math.sin(a), 0.0])
    u = np.array([-math.sin(a), math.cos(a), 0.0])
    plaque = Manifold.sphere(1.0, 48).scale((7, 9, 2.6))
    anneau = Manifold.cylinder(1.4, 8.5, 8.5, 48).scale((1, 1.25, 1)) - Manifold.cylinder(3, 7, 7, 48).scale((1, 1.25, 1)).translate((0, 0, -1))
    m = plaque + anneau.translate((0, 0, 0.6))
    return m.transform(np.column_stack([u, np.array([0, 0, 1.0]), d, p]))


# ---------------------------------------------------------------- CRISTAUX
def cristal(g, r, h, inclin, azim, base):
    """Prisme hexagonal irrégulier à terminaison asymétrique (enveloppe convexe)."""
    a = np.arange(6) * math.pi / 3 + g.uniform(-0.12, 0.12, 6)
    rr = r * g.uniform(0.8, 1.15, 6)
    bas = np.stack([rr * np.cos(a), rr * np.sin(a), np.full(6, -8.0)], 1)
    hh = h * (1 + g.uniform(-0.12, 0.05, 6))
    haut = np.stack([rr * np.cos(a) * 0.97, rr * np.sin(a) * 0.97, hh], 1)
    pointe = [[g.uniform(-0.3, 0.3) * r, g.uniform(-0.3, 0.3) * r, h + r * g.uniform(1.4, 2.4)]]
    c = Manifold.hull_points(np.vstack([bas, haut, pointe]))
    return c.rotate((inclin, 0, 0)).rotate((0, 0, azim)).translate(tuple(base))


def bouquet(o):
    """Grand bouquet de cristaux, violets en majorité, quelques verts."""
    g = np.random.default_rng(GRAINE + 2)
    violets = [cylindre(27, 6, o[2] - 4, o[0], o[1]), cristal(g, 14, 115, 4, 20, o)]
    verts = []
    couronnes = [(7, 8, 13, (8, 11), (60, 95), (8, 20), 0),
                 (10, 18, 25, (6, 9), (40, 70), (22, 34), 4),
                 (11, 24, 28, (4, 6.5), (22, 45), (35, 50), 10)]
    for n, d0, d1, rr, hh, inc, dz in couronnes:
        for k in range(n):
            a = 2 * math.pi * k / n + g.uniform(-0.2, 0.2)
            d = g.uniform(d0, d1)
            c = cristal(g, g.uniform(*rr), g.uniform(*hh), g.uniform(*inc), math.degrees(a) + 90,
                        np.array(o) + [d * math.cos(a), d * math.sin(a), dz])
            (verts if g.uniform() < 0.3 else violets).append(c)
    violets, verts = union(violets), union(verts)
    return violets - verts, verts


ECLATS = [(175, 0.4), (240, 2.6), (870, 4.4), (1475, 1.3)]


def eclats():
    """Petits cristaux violets sertis dans le fût, entre les lianes."""
    g = np.random.default_rng(GRAINE + 5)
    res = []
    for z, a in ECLATS:
        r0 = float(rayon_fut(z))
        c = cristal(g, g.uniform(5.0, 6.5), g.uniform(16, 24), g.uniform(45, 60), 0, (0, 0, 0))
        c = c.rotate((0, 0, math.degrees(a) + 90)).translate((r0 * 0.9 * math.cos(a), r0 * 0.9 * math.sin(a), z))
        res.append((z, c))
    return res


def pendentif(g, r, h):
    """Petit cristal à suspendre, percé en travers près de la base."""
    c = cristal(g, r, h, 0, 0, (0, 0, 8))
    trou = Manifold.cylinder(4 * r, 1.0, 1.0, 24).rotate((0, 90, 0)).translate((-2 * r, 0, 4))
    return c - trou


# ---------------------------------------------------------------- PIÈCES
def sertis(z0, z1, lian):
    sel = [c for z, c in ECLATS_M if z0 <= z < z1]
    return union(sel) if sel else None


def segment_fut(i, extras):
    z0, z1 = i * H_SEG, (i + 1) * H_SEG
    alesage = cylindre(R_ALESAGE, H_SEG + 2, z0 - 1)
    bois, lian = fut(z0, z1), lianes(z0, z1)
    cuir_s = None
    if POIGNEE[0] < z1 and POIGNEE[1] > z0:
        cuir_s = extras["cuir"] + extras["medaillon"]
        lian = lian - cuir_s                                       # les lianes passent sous le cuir
        cuir_s = cuir_s - extras["medaillon"]
        lian = lian + extras["medaillon"]
    cr = sertis(z0, z1, lian)
    lian = lian - cr if cr else lian                                # les éclats passent devant
    bois = bois - lian - (cuir_s if cuir_s else Manifold()) - (cr if cr else Manifold())
    return bois - alesage, lian - alesage, cuir_s, cr


def trous_vis():
    """2 trous Ø3,2 pour bloquer le bouquet sur le col (vis à bois 3,5 mm)."""
    trous = []
    for a in (20, 200):
        c = Manifold.cylinder(30, 1.6, 1.6, 24).rotate((0, 90, 0)).translate((R_TENON - 10, 0, 0))
        trous.append(c.rotate((0, 0, a)).translate((0, 0, Z_COL1 + H_TENON / 2)))
    return trous[0] + trous[1]


def col():
    bois, lian = fut(Z_COL0, Z_COL1), lianes(Z_COL0, Z_COL1)
    cr = sertis(Z_COL0, Z_COL1, lian)
    lian = lian - cr if cr else lian
    bois = bois - lian - (cr if cr else Manifold())
    bois = bois - cylindre(R_ALESAGE, PROF_DOUILLE + 1, Z_COL0 - 1)                # douille
    bois = bois + cylindre(R_TENON, H_TENON + 1, Z_COL1 - 1)                      # tenon
    bois = bois - cylindre(DIAM_LED / 2, 23, Z_COL1 + H_TENON - 22)               # logement bougie
    return bois - trous_vis(), lian, cr


def coudes(g, n, amp):
    cles = np.linspace(0, 1, 7)
    s = np.linspace(0, 1, n)
    dev = np.stack([np.interp(s, cles, g.uniform(-1, 1, 7)) for _ in range(3)], -1)
    noyau = np.ones(9) / 9
    dev = np.stack([np.convolve(dev[:, i], noyau, mode="same") for i in range(3)], -1)
    return dev * amp * s[:, None]


def tete():
    """Base en bois + les lianes qui s'ouvrent et s'entrelacent dans le bouquet."""
    zs = np.linspace(Z_COL1, Z_COL1 + HP, int(HP / PAS) + 1)
    th = np.linspace(0, 2 * math.pi, 200, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    R = R_TETE + 0 * Z
    base = loft(texturer(np.stack([R * np.cos(TH), R * np.sin(TH), Z], -1), grain_bois))

    g = np.random.default_rng(GRAINE + 3)
    branches = []
    for L in LIANES * 2:                                          # chaque liane se dédouble
        a0 = float(angle_liane(L, Z_COL1)) + g.uniform(-0.4, 0.4)
        r0 = float(orbite_liane(L, Z_COL1))
        long = g.uniform(170, 260)
        n = int(long / PAS)
        s = np.linspace(0, 1, n)
        rad = r0 + g.uniform(18, 42) * np.sin(math.pi * s * 0.8) - g.uniform(5, 25) * s ** 3
        z = Z_COL1 - 10 + long * 0.9 * s
        tw = a0 + L["sens"] * g.uniform(0.6, 1.6) * s
        pts = np.stack([rad * np.cos(tw), rad * np.sin(tw), z], -1) + coudes(g, n, 4.0)
        rv = float(rayon_liane(L, Z_COL1)) * (0.85 - 0.6 * s) + 0.7
        branches.append(tube_balaye(pts, rv, n=32, texture=np.clip(rv / 5, 0.2, 0.6)))
    lian = union(branches) ^ tranche(Z_COL1, Z_COL1 + 500)

    bois = base - cylindre(R_TENON + JEU / 2, H_TENON, Z_COL1 - 1)               # mortaise
    bois = bois - cylindre(DIAM_LED / 2, HP + 40, Z_COL1)                         # chambre de lumière
    bois = bois - trous_vis() - lian
    lian = lian - trous_vis() - cylindre(R_TENON + JEU / 2, H_TENON, Z_COL1 - 1)
    violets, verts = bouquet(np.array([0.0, 0.0, Z_COL1 + HP]))
    violets, verts = violets - lian - bois, verts - lian - bois
    return bois, lian, violets, verts


# ---------------------------------------------------------------- MAIN
def exporter(man, nom, z):
    man = Manifold.compose([c for c in man.decompose() if c.volume() > 2.0])   # sans miettes
    m = vers_trimesh(man)
    assert m.is_watertight, f"{nom} : maillage non étanche"
    m.apply_translation((0, 0, -z))
    m.export(SORTIE / "stl" / nom)
    print(f"{nom:32s} {m.extents.round(0)} mm  {m.volume / 1000:5.0f} cm3  {len(m.faces):7d} tri")
    return m.apply_translation((0, 0, z))


def verifier_paroi(solide, z0, z1):
    anneau = cylindre(R_ALESAGE + PAROI_MIN - 0.5, z1 - z0, z0) - cylindre(R_ALESAGE + 0.01, z1 - z0 + 2, z0 - 1)
    manque = (anneau - solide).volume()
    assert manque < 1.0, f"paroi trop fine entre z={z0} et {z1} ({manque:.1f} mm3 manquants)"


ECLATS_M = eclats()

if __name__ == "__main__":
    (SORTIE / "stl").mkdir(exist_ok=True)
    for f in (SORTIE / "stl").glob("*.stl"):
        f.unlink()
    extras = {"cuir": cuir(), "medaillon": medaillon()}
    rendu = {k: [] for k in ("bois", "lianes", "cuir", "violet", "vert")}
    for i in range(NB_SEGMENTS):
        bois, lian, cuir_s, cr = segment_fut(i, extras)
        verifier_paroi(union([bois, lian, cuir_s, cr]), i * H_SEG, (i + 1) * H_SEG)
        rendu["bois"].append(exporter(bois, f"fut_{i + 1}_bois.stl", i * H_SEG))
        rendu["lianes"].append(exporter(lian, f"fut_{i + 1}_lianes.stl", i * H_SEG))
        if cuir_s:
            rendu["cuir"].append(exporter(cuir_s, f"fut_{i + 1}_cuir.stl", i * H_SEG))
        if cr:
            rendu["violet"].append(exporter(cr, f"fut_{i + 1}_cristaux_violets.stl", i * H_SEG))

    bois, lian, cr = col()
    verifier_paroi(union([bois, lian, cr]), Z_COL0, Z_COL0 + PROF_DOUILLE)
    rendu["bois"].append(exporter(bois, "tete_1_col_bois.stl", Z_COL0))
    rendu["lianes"].append(exporter(lian, "tete_1_col_lianes.stl", Z_COL0))
    if cr:
        rendu["violet"].append(exporter(cr, "tete_1_col_cristaux_violets.stl", Z_COL0))

    bois, lian, violets, verts = tete()
    rendu["bois"].append(exporter(bois, "tete_2_bouquet_bois.stl", Z_COL1))
    rendu["lianes"].append(exporter(lian, "tete_2_bouquet_lianes.stl", Z_COL1))
    rendu["violet"].append(exporter(violets, "tete_2_bouquet_cristaux_violets.stl", Z_COL1))
    rendu["vert"].append(exporter(verts, "tete_2_bouquet_cristaux_verts.stl", Z_COL1))

    g = np.random.default_rng(GRAINE + 4)
    pend = [pendentif(g, 3.5, 16).translate((0, 0, 0)), pendentif(g, 3.0, 13).translate((15, 0, 0))]
    exporter(pend[0] + pend[1], "pendentifs_violets.stl", 0)
    exporter(pendentif(g, 3.2, 14), "pendentif_vert.stl", 0)

    # assemblage complet pour les aperçus (non versionné)
    (SORTIE / "apercu").mkdir(exist_ok=True)
    for cle, morceaux in rendu.items():
        if morceaux:
            trimesh.util.concatenate(morceaux).export(SORTIE / "apercu" / f"assemblage_{cle}.stl")
