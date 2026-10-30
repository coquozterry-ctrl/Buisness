"""Génère le bâton de la Guggen en pièces imprimables multi-matériaux (Prusa XL).

Principe : un tube alu Ø16 mm sert d'âme (solidité). Autour, trois brins de bois
s'enroulent comme un tronc d'arbre tordu d'Halloween (nœuds creux, bosses, branches
cassées). Une veine dorée coule au fond d'un sillon (2e couleur). En haut, le col se
cambre en S et les brins s'ouvrent en griffes qui enserrent des cristaux translucides
(3e couleur). Les bouts de branches cassées sont en bois clair (4e couleur).
La main s'emboîte sur le col, qui cache une bougie LED.

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
PAROI_MIN = 3.5            # paroi minimale autour du tube, sous l'écorce
RAYON_BRIN = 11.0          # rayon moyen de chacun des 3 brins tordus
PAS_TORSION = 330.0        # hauteur d'un tour complet des brins
ONDULATION = 6.0           # amplitude des ondulations du tronc
PROF_DOUILLE = 120         # profondeur du tube dans le col
DIAM_LED = 42.0            # bougie LED « chauffe-plat » Ø38 mm
NB_NOEUDS_CREUX = 9
NB_CHICOTS = 9             # branches cassées
NB_PLAQUES = 12            # lambeaux d'écorce soulevés
GRAINE = 7                 # change la graine pour un autre bâton "unique"

PAS = 0.7                  # finesse du maillage (taille des fissures ≈ 2 mm)
SORTIE = Path(__file__).parent

R_ALESAGE = DIAM_TUBE / 2 + JEU / 2
PROF_ECORCE = 5.0
R_COEUR = R_ALESAGE + PAROI_MIN + PROF_ECORCE
Z_COL0 = LONGUEUR_FUT
Z_COL1 = LONGUEUR_FUT + 300        # col en S (pièce de 300 mm + tenon)
R_TENON, H_TENON = 24.0, 25.0      # emboîtement main / col (contient la bougie)
HP = 50.0                          # hauteur de la paume
H_SEG = LONGUEUR_FUT / NB_SEGMENTS
JOINTS = [H_SEG * k for k in range(NB_SEGMENTS + 1)] + [Z_COL1]


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
    tout = pieces[0]
    for p in pieces[1:]:
        tout = tout + p
    return tout


def placer(man, p, d):
    """Oriente une pièce modélisée le long de +z selon la direction d, au point p."""
    d = d / np.linalg.norm(d)
    u = np.cross(d, [0, 0, 1.0])
    u = u / np.linalg.norm(u) if np.linalg.norm(u) > 1e-6 else np.array([1.0, 0, 0])
    return man.transform(np.column_stack([u, np.cross(d, u), d, p]))


# ---------------------------------------------------------------- TEXTURE D'ÉCORCE
class Cellules:
    """Bruit cellulaire 3D (Worley) : plaques d'écorce séparées par des sillons."""

    def __init__(self, taille, etirement, graine):
        g = np.random.default_rng(graine)
        self.S = np.array([1.0, 1.0, 1.0 / etirement])
        lo = np.array([-250, -250, -50]) * self.S
        hi = np.array([300, 300, Z_COL1 + 450]) * self.S
        axes = [np.arange(l, h, taille) for l, h in zip(lo, hi)]
        base = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
        self.arbre = cKDTree(base + g.uniform(0, taille, base.shape))
        self.h = g.uniform(-1, 1, len(base))

    def __call__(self, p):
        d, i = self.arbre.query(p.reshape(-1, 3) * self.S, k=2, workers=-1)
        return (d[:, 1] - d[:, 0]).reshape(p.shape[:-1]), self.h[i[:, 0]].reshape(p.shape[:-1])


PLAQUES = Cellules(10.0, 3.5, GRAINE)       # plaques allongées : sillons d'écorce d'arbre
TRAVERS = Cellules(5.0, 0.5, GRAINE + 2)    # cassures en travers des plaques
GERCURES = Cellules(3.0, 1.8, GRAINE + 1)


def ecorce(p):
    """Déplacement (mm, négatif = vers l'intérieur) de l'écorce au point p."""
    e1, h1 = PLAQUES(p)
    e2, _ = GERCURES(p)
    e3, _ = TRAVERS(p)
    sillon = np.clip(1 - e1 / 3.2, 0, 1) ** 1.4                # sillons profonds entre les plaques
    plaque = (1.3 + 0.9 * h1) * (1 - sillon)                     # plaques qui ressortent
    travers = np.clip(1 - e3 / 0.9, 0, 1) * (1 - sillon)
    gercure = np.clip(1 - e2 / 0.7, 0, 1)
    fibres = np.sin(p[..., 2] * 0.9 + 3 * np.sin(p[..., 0] * 0.21) + 3 * np.sin(p[..., 1] * 0.19))
    return plaque - 3.6 * sillon - 1.1 * travers - 0.4 * gercure + 0.15 * fibres


def texturer(anneaux, echelle=1.0):
    d = ecorce(anneaux) * np.broadcast_to(echelle, anneaux.shape[:-1])
    return anneaux + normales(anneaux) * d[..., None]


def tube_balaye(pts, rayons, n=24, texture=None, aplat=1.0):
    """Tube le long d'une courbe 3D (repère par transport parallèle), section ovale si aplat < 1."""
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
        anneaux = texturer(anneaux, np.asarray(texture)[:, None] * np.ones(n))
    return loft(anneaux)


# ---------------------------------------------------------------- FORME DU TRONC
def lisse(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def torsion(z):
    return 2 * math.pi * z / PAS_TORSION + 0.8 * np.sin(z / 260.0)


T_COL = (Z_COL0 + PROF_DOUILLE + 5, Z_COL1)      # zone du col en S (au-dessus du tube)


def courbe_col(z):
    """Le col se cambre en S puis la tête penche, comme sur la photo."""
    t = np.clip((np.asarray(z, float) - T_COL[0]) / (T_COL[1] - T_COL[0]), 0, 1)
    return 55 * np.sin(math.pi * t) * t + 22 * t ** 2, -25 * np.sin(2 * math.pi * t)


def centre_coeur(z):
    return courbe_col(z)


def centre_tronc(z):
    """Ligne moyenne des brins : ondule le long du tube, suit le S du col."""
    x = ONDULATION * (np.sin(2 * math.pi * z / 520 + 0.4) + 0.5 * np.sin(2 * math.pi * z / 230 + 1.7))
    y = ONDULATION * (0.8 * np.sin(2 * math.pi * z / 610 + 2.1) + 0.4 * np.sin(2 * math.pi * z / 270))
    f = 1 - lisse((z - Z_COL0) / 150)                              # le S du col prend le relais
    cx, cy = courbe_col(z)
    return x * f + cx, y * f + cy


def rayon_coeur(z):
    return R_COEUR + 13.0 * lisse((z - Z_COL0 - PROF_DOUILLE) / (Z_COL1 - Z_COL0 - PROF_DOUILLE))


def ecart_brins(z):
    pied = 9.0 * np.exp(-z / 45.0)                                 # le pied s'évase comme des racines
    return 14.5 + 1.5 * np.sin(z / 133.0) + pied + 19.0 * lisse((z - Z_COL0 - 60) / 240)


g0 = np.random.default_rng(GRAINE)
BOSSES = [(int(g0.integers(3)), g0.uniform(60, Z_COL1 - 30), g0.uniform(3, 6), g0.uniform(15, 35))
          for _ in range(16)]


def rayon_brin(k, z):
    r = RAYON_BRIN + 2.0 * np.sin(z / 97.0 + 2.1 * k) + 1.2 * np.sin(z / 41.0 + k)
    r = r + 4.0 * np.exp(-z / 45.0)
    for kb, zb, hb, wb in BOSSES:
        if kb == k:
            r = r + hb * np.exp(-((z - zb) / wb) ** 2)
    return r


def angle_brin(k, z):
    return torsion(z) + 2 * math.pi * k / 3 + 0.25 * np.sin(z / 71.0 + 3 * k)


def axe_brin(k, z):
    cx, cy = centre_tronc(z)
    a, e = angle_brin(k, z), ecart_brins(z)
    return np.stack([cx + e * np.cos(a), cy + e * np.sin(a), z], -1)


def brin(k, z0, z1):
    z = np.arange(z0, z1 + 1e-6, 0.6)
    return tube_balaye(axe_brin(k, z), rayon_brin(k, z), n=100, texture=np.ones(len(z)))


def coeur(z0, z1):
    zs = np.linspace(z0, z1, int(round((z1 - z0) / PAS)) + 1)
    th = np.linspace(0, 2 * math.pi, 160, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    cx, cy = centre_coeur(Z)
    R = rayon_coeur(Z) + 0.8 * np.sin(3 * TH + Z / 40)
    s = texturer(np.stack([cx + R * np.cos(TH), cy + R * np.sin(TH), Z], -1))
    s[..., 2] = np.where(np.isin(Z, (z0, z1)), Z, s[..., 2])
    return loft(s)


def tronc(z0, z1):
    """Cœur + 3 brins tordus, coupés net aux jointures."""
    morceaux = [coeur(z0, z1)] + [brin(k, z0 - 20, z1 + 20) for k in range(3)]
    return union(morceaux) ^ tranche(z0, z1)


# ---------------------------------------------------------------- DÉTAILS
def point_exterieur(k, z):
    """Point de la surface d'un brin, côté extérieur, et direction sortante."""
    p = axe_brin(k, np.array([z]))[0]
    cx, cy = centre_coeur(z)
    out = np.array([p[0] - cx, p[1] - cy, 0.0])
    out /= np.linalg.norm(out)
    return p + out * rayon_brin(k, z), out


def emplacements(n, marge_bas, marge_haut, graine, deja=()):
    g = np.random.default_rng(graine)
    pris = list(deja)
    res = []
    while len(res) < n:
        z, k = g.uniform(60, Z_COL1 - 80), int(g.integers(3))
        if any(j - marge_bas < z < j + marge_haut for j in JOINTS):
            continue
        if any(abs(z - pz) < 60 and pk == k for pz, pk in pris):
            continue
        pris.append((z, k))
        res.append((z, k))
    return res


def noeuds_creux():
    """Bosse avec un trou sombre au centre, sur la face extérieure d'un brin."""
    g = np.random.default_rng(GRAINE + 5)
    plus, moins = [], []
    for z, k in emplacements(NB_NOEUDS_CREUX, 25, 25, GRAINE + 6):
        p, out = point_exterieur(k, z)
        r = g.uniform(6, 9)
        c = p - out * r * 0.7
        bosse = Manifold.sphere(r * 1.25, 48).scale((1, 1, 1.5)).translate(tuple(c))

        def ecorcer(v, c=c):                                   # même écorce que le tronc
            n = v - c
            n /= np.linalg.norm(n, axis=1, keepdims=True)
            return v + n * (0.6 * ecorce(v))[:, None]

        plus.append((z, bosse.refine_to_length(0.8).warp_batch(ecorcer)))
        trou = Manifold.sphere(r * 0.7, 48).scale((1, 1, 1.6))
        moins.append((z, placer(trou, p + out * 0.8 * r * 0.4, out)))
    return plus, moins


def chicot(g, p, out):
    """Moignon de branche écorcé, cassé net, avec le bois clair éclaté au bout."""
    e = math.radians(g.uniform(42, 60))                       # pointe vers le haut : imprimable
    d = math.cos(e) * out + math.sin(e) * np.array([0, 0, 1.0])
    r0, L = g.uniform(5, 10), g.uniform(15, 40)
    ancrage = 1.6 * r0 + 4
    t = np.linspace(0, 1, max(int((L + ancrage) / PAS), 20))
    pts = p - ancrage * d + np.outer(t, d * (L + ancrage)) + np.outer(t ** 2, [0, 0, 1.0]) * g.uniform(0, 0.15) * L
    tb = ancrage / (L + ancrage)
    r = r0 * (1 + 0.3 * np.exp(-np.clip(t - tb, 0, None) / 0.08)) * (1 - 0.2 * t)
    ecorce_ch = tube_balaye(pts, r, n=72, texture=np.full(len(t), 0.6))
    rc = r[-1] * 0.78
    coeur_ch = [Manifold.cylinder(4, rc, rc, 48).translate((0, 0, -3.5))]
    for _ in range(g.integers(5, 9)):                          # échardes
        a, rr = g.uniform(0, 2 * math.pi), g.uniform(0, rc * 0.75)
        x, y, w = rr * math.cos(a), rr * math.sin(a), g.uniform(1.0, 2.0)
        base = [[x + w * math.cos(b), y + w * math.sin(b), 0] for b in (0, 2.1, 4.2)]
        pointe = [[x + g.uniform(-1.5, 1.5), y + g.uniform(-1.5, 1.5), g.uniform(2, 3 + r0 * 0.6)]]
        coeur_ch.append(Manifold.hull_points(np.array(base + pointe)))
    coeur_ch = placer(union(coeur_ch), pts[-1], pts[-1] - pts[-2])
    return ecorce_ch - coeur_ch, coeur_ch


def chicots():
    g = np.random.default_rng(GRAINE + 4)
    res = []
    for z, k in emplacements(NB_CHICOTS, 20, 60, GRAINE + 7):
        p, out = point_exterieur(k, z)
        res.append((z, *chicot(g, p - out * 1.5, out)))
    return res


def plaque_soulevee(g, z, k):
    """Lambeau d'écorce collé en bas, décollé et déchiqueté en haut."""
    H, ouv = g.uniform(40, 75), g.uniform(0.45, 0.85)
    r_in, ep = float(rayon_brin(k, z)) - 2.5, 1.8
    axe = axe_brin(k, np.array([z - 1.0, z, z + 1.0]))
    d = axe[2] - axe[0]
    d /= np.linalg.norm(d)
    u = np.cross(d, [0, 0, 1.0]); u /= np.linalg.norm(u)
    v = np.cross(d, u)
    cx, cy = centre_coeur(z)
    out = np.array([axe[1][0] - cx, axe[1][1] - cy, 0.0])
    al = math.atan2(out @ v, out @ u)                          # direction extérieure, repère local
    coque = (Manifold.cylinder(H, r_in + ep, r_in + ep, 180)
             - Manifold.cylinder(H + 2, r_in, r_in, 180).translate((0, 0, -1)))
    coque = coque.trim_by_plane((-math.sin(al - ouv), math.cos(al - ouv), 0), 0)
    coque = coque.trim_by_plane((math.sin(al + ouv), -math.cos(al + ouv), 0), 0)
    phase = g.uniform(0, 6.3)

    def deformer(pts):
        x, y, zz = pts[:, 0], pts[:, 1], pts[:, 2]
        a, r = np.arctan2(y, x), np.hypot(x, y)
        t = np.clip(zz / H, 0, 1)
        da = np.angle(np.exp(1j * (a - al))) / ouv
        q = np.stack([r_in * np.cos(a) + 37 * k, r_in * np.sin(a), zz + z], -1)
        r = r + 4.5 * t ** 1.6 + 2.5 * t * da ** 4 + 0.5 * ecorce(q)       # se décolle, bords roulés
        zz = zz - 6 * t ** 6 * np.abs(np.sin(9 * da + phase))              # haut déchiqueté
        return np.stack([r * np.cos(a), r * np.sin(a), zz], -1)

    coque = coque.refine_to_length(1.2).warp_batch(deformer)
    return coque.transform(np.column_stack([u, v, d, axe[1]]))


def plaques_soulevees():
    g = np.random.default_rng(GRAINE + 8)
    return [(z, plaque_soulevee(g, z, k)) for z, k in emplacements(NB_PLAQUES, 10, 85, GRAINE + 9)]


def veine() -> Manifold:
    """Filon doré au fond du sillon entre deux brins."""
    z = np.arange(25, Z_COL1 - 25, 1.0)
    a = (angle_brin(0, z) + angle_brin(1, z)) / 2
    cx, cy = centre_coeur(z)
    rv = 3.4 + 1.0 * np.sin(z / 61 + 1) + 0.5 * np.sin(z / 23)
    rc = rayon_coeur(z) - 0.6 * rv                        # affleure au fond du sillon
    rv = rv * np.clip(np.minimum(z - 25, Z_COL1 - 25 - z) / 40, 0.15, 1)
    return tube_balaye(np.stack([cx + rc * np.cos(a), cy + rc * np.sin(a), z], -1), rv, n=20)


# ---------------------------------------------------------------- CRISTAUX
def cristal(g, r, h, inclin, azim, base):
    """Prisme hexagonal irrégulier à terminaison asymétrique (enveloppe convexe)."""
    a = np.arange(6) * math.pi / 3 + g.uniform(-0.12, 0.12, 6)
    rr = r * g.uniform(0.8, 1.15, 6)
    bas = np.stack([rr * np.cos(a), rr * np.sin(a), np.full(6, -8.0)], 1)
    hh = h * (1 + g.uniform(-0.12, 0.05, 6))
    haut = np.stack([rr * np.cos(a) * 0.97, rr * np.sin(a) * 0.97, hh], 1)
    pointe = [[g.uniform(-0.3, 0.3) * r, g.uniform(-0.3, 0.3) * r, h + r * g.uniform(1.3, 2.2)]]
    c = Manifold.hull_points(np.vstack([bas, haut, pointe]))
    return c.rotate((inclin, 0, 0)).rotate((0, 0, azim)).translate(tuple(base))


def grappe(o) -> Manifold:
    g = np.random.default_rng(GRAINE + 2)
    pieces = [cylindre(27, 6, o[2] - 4, o[0], o[1]),                    # socle, laisse passer la lumière
              cristal(g, 16, 125, 4, 30, o)]
    for k in range(9):
        a = 2 * math.pi * k / 9 + g.uniform(-0.25, 0.25)
        d = g.uniform(9, 17)
        pieces.append(cristal(g, g.uniform(6, 11), g.uniform(35, 90), g.uniform(12, 32),
                              math.degrees(a) + 90, o + [d * math.cos(a), d * math.sin(a), 0]))
    for k in range(40):                                                 # druse au pied
        a = g.uniform(0, 2 * math.pi)
        d = g.uniform(14, 26)
        pieces.append(cristal(g, g.uniform(1.3, 3.0), g.uniform(3, 10), g.uniform(10, 50),
                              math.degrees(a) + 90, o + [d * math.cos(a), d * math.sin(a), 1.5]))
    return union(pieces)


# ---------------------------------------------------------------- PIÈCES
def avec_details(bois, z0, z1, details):
    """Ajoute bosses et chicots, creuse les nœuds ; renvoie (bois, bois clair)."""
    plus, moins, ch, lambeaux = details
    sel = lambda lst: [m for z, m in lst if z0 <= z < z1]
    bois = union([bois] + sel(plus) + sel(lambeaux) + [e for z, e, _ in ch if z0 <= z < z1])
    for m in sel(moins):
        bois = bois - m
    clair = [c for z, _, c in ch if z0 <= z < z1]
    if not clair:
        return bois, None
    clair = union(clair)
    return bois - clair, clair


def segment_fut(i, filon, details):
    z0, z1 = i * H_SEG, (i + 1) * H_SEG
    alesage = cylindre(R_ALESAGE, H_SEG + 2, z0 - 1)
    bois, clair = avec_details(tronc(z0, z1), z0, z1, details)
    bois = (bois ^ tranche(z0, z1)) - alesage
    return bois - filon, (filon ^ tranche(z0, z1)) - alesage, clair


def trous_goupilles():
    """2 trous Ø3,2 pour goupiller la main sur le col (clous ou vis M3)."""
    cx, cy = centre_coeur(Z_COL1)
    trous = []
    for a in (20, 200):
        c = Manifold.cylinder(30, 1.6, 1.6, 24).rotate((0, 90, 0)).translate((R_TENON - 10, 0, 0))
        trous.append(c.rotate((0, 0, a)).translate((float(cx), float(cy), Z_COL1 + H_TENON / 2)))
    return trous[0] + trous[1]


def col(filon, details):
    cx, cy = (float(v) for v in centre_coeur(Z_COL1))
    bois, clair = avec_details(tronc(Z_COL0, Z_COL1), Z_COL0, Z_COL1, details)
    bois = bois ^ tranche(Z_COL0, Z_COL1)
    bois = bois - cylindre(R_ALESAGE, PROF_DOUILLE + 1, Z_COL0 - 1)               # douille
    bois = bois + cylindre(R_TENON, H_TENON + 1, Z_COL1 - 1, cx, cy)              # tenon
    bois = bois - cylindre(DIAM_LED / 2, 23, Z_COL1 + H_TENON - 22, cx, cy)       # logement bougie
    bois = bois - trous_goupilles()
    v = (filon ^ tranche(Z_COL0, Z_COL1)) - cylindre(R_ALESAGE, PROF_DOUILLE + 1, Z_COL0 - 1)
    return bois - filon, v, clair


def coudes(g, n, amp):
    """Bruit par morceaux : donne au bois des coudes au lieu de courbes trop lisses."""
    cles = np.linspace(0, 1, 7)
    s = np.linspace(0, 1, n)
    dev = np.stack([np.interp(s, cles, g.uniform(-1, 1, 7)) for _ in range(3)], -1)
    noyau = np.ones(9) / 9
    dev = np.stack([np.convolve(dev[:, i], noyau, mode="same") for i in range(3)], -1)
    return dev * amp * s[:, None]


def branche(g, pts, r0, r1, aplat=0.8):
    s = np.linspace(0, 1, len(pts))
    r = r0 * (1 - s) ** 0.75 + r1
    for pos in g.uniform(0.2, 0.85, 3):                                   # nœuds
        r = r + 0.25 * r0 * np.exp(-((s - pos) / 0.035) ** 2) * (1 - 0.6 * s)
    return tube_balaye(pts, r, n=96, texture=np.clip(r / 9, 0.15, 1), aplat=aplat), r


def griffe(g, cx, cy, a0, e0, z0, L, ecarte, crochet, vrille):
    n = int(L / PAS)
    s = np.linspace(0, 1, n)
    rad = e0 + ecarte * np.sin(math.pi * s * 0.7) - crochet * s ** 3
    z = z0 + L * 0.8 * (s - 0.25 * s ** 3)
    tw = a0 + vrille * s
    pts = np.stack([cx + rad * np.cos(tw), cy + rad * np.sin(tw), z], -1)
    return pts + coudes(g, n, 9.0)


def rameau(g, pts, r, s0):
    """Petite branche qui part d'une griffe et se recourbe."""
    i = int(s0 * len(pts))
    t = pts[min(i + 1, len(pts) - 1)] - pts[i - 1]
    t /= np.linalg.norm(t)
    lat = np.cross(t, g.normal(size=3))
    lat /= np.linalg.norm(lat)
    L = g.uniform(40, 80)
    n = int(L / PAS)
    s = np.linspace(0, 1, n)[:, None]
    d0 = 0.5 * t + 0.85 * lat
    chemin = pts[i] + L * (s * d0 + 0.6 * s ** 2 * (t - 0.4 * lat)) + coudes(g, n, 5.0)
    return branche(g, chemin, 0.5 * r[i], 1.1)[0]


def main_griffue():
    """Le bois du tronc se prolonge en 3 grosses griffes coudées, crochues à l'arrière,
    avec des rameaux ; 6 racines plus fines enveloppent la base et montent entre les cristaux."""
    cx, cy = (float(v) for v in centre_coeur(Z_COL1))
    zs = np.linspace(Z_COL1, Z_COL1 + HP, int(HP / PAS) + 1)
    th = np.linspace(0, 2 * math.pi, 240, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    R = rayon_coeur(Z_COL1) - 1 + 0 * Z
    paume = loft(texturer(np.stack([cx + R * np.cos(TH), cy + R * np.sin(TH), Z], -1)))

    g = np.random.default_rng(GRAINE + 3)
    dos = math.atan2(-cy, -cx) if abs(cx) + abs(cy) > 1 else 0.0       # côté opposé à la pente
    bois = [paume]
    e0 = float(ecart_brins(Z_COL1))
    for k in range(3):                                                  # grosses griffes
        a0 = float(angle_brin(k, Z_COL1))
        arr = max(0.0, math.cos(a0 - dos))
        pts = griffe(g, cx, cy, a0, e0, Z_COL1 - 20, 250 + 110 * arr + g.uniform(-15, 15),
                     g.uniform(22, 32), 20 + 45 * arr, g.uniform(0.4, 0.8) * (1 if k % 2 else -1))
        tube, r = branche(g, pts, RAYON_BRIN + 3, 2.0, aplat=0.75)
        bois.append(tube)
        for s0 in g.uniform(0.35, 0.65, 1 + int(arr > 0.3)):
            bois.append(rameau(g, pts, r, s0))
    for k in range(6):                                                  # racines qui enveloppent
        a0 = float(angle_brin(0, Z_COL1)) + math.pi / 3 * (k + 0.5) + g.uniform(-0.2, 0.2)
        pts = griffe(g, cx, cy, a0, float(R[0, 0]) + 1, Z_COL1 - 10, g.uniform(150, 220),
                     g.uniform(10, 20), g.uniform(5, 15), g.uniform(-0.9, 0.9))
        bois.append(branche(g, pts, g.uniform(7, 10), 1.4, aplat=0.7)[0])

    main = union(bois) ^ tranche(Z_COL1, Z_COL1 + 500)
    main = main - cylindre(R_TENON + JEU / 2, H_TENON, Z_COL1 - 1, cx, cy)        # mortaise
    main = main - cylindre(DIAM_LED / 2, HP + 1, Z_COL1, cx, cy)                  # chambre de lumière
    main = main - trous_goupilles()
    cr = grappe(np.array([cx, cy, Z_COL1 + HP]))
    return main - cr, cr


# ---------------------------------------------------------------- MAIN
def exporter(man, nom, z):
    man = Manifold.compose([c for c in man.decompose() if c.volume() > 2.0])   # sans miettes
    m = vers_trimesh(man)
    assert m.is_watertight, f"{nom} : maillage non étanche"
    m.apply_translation((0, 0, -z))
    m.export(SORTIE / "stl" / nom)
    print(f"{nom:28s} {m.extents.round(0)} mm  {m.volume / 1000:5.0f} cm3  {len(m.faces):7d} tri")
    return m.apply_translation((0, 0, z))


def verifier_paroi(bois, z0, z1):
    anneau = cylindre(R_ALESAGE + PAROI_MIN - 0.5, z1 - z0, z0) - cylindre(R_ALESAGE + 0.01, z1 - z0 + 2, z0 - 1)
    manque = (anneau - bois).volume()
    assert manque < 1.0, f"paroi trop fine entre z={z0} et {z1} ({manque:.1f} mm3 manquants)"


if __name__ == "__main__":
    (SORTIE / "stl").mkdir(exist_ok=True)
    for f in (SORTIE / "stl").glob("*.stl"):
        f.unlink()
    filon = veine()
    details = (*noeuds_creux(), chicots(), plaques_soulevees())
    rendu = {"bois": [], "veine": [], "cristaux": [], "clair": []}
    for i in range(NB_SEGMENTS):
        bois, v, clair = segment_fut(i, filon, details)
        verifier_paroi(bois + v, i * H_SEG, (i + 1) * H_SEG)       # la veine compte dans la paroi
        rendu["bois"].append(exporter(bois, f"fut_{i + 1}_ecorce.stl", i * H_SEG))
        rendu["veine"].append(exporter(v, f"fut_{i + 1}_veine.stl", i * H_SEG))
        if clair:
            rendu["clair"].append(exporter(clair, f"fut_{i + 1}_bois_clair.stl", i * H_SEG))

    bois, v, clair = col(filon, details)
    verifier_paroi(bois + v, Z_COL0, Z_COL0 + PROF_DOUILLE)
    rendu["bois"].append(exporter(bois, "tete_1_col_ecorce.stl", Z_COL0))
    rendu["veine"].append(exporter(v, "tete_1_col_veine.stl", Z_COL0))
    if clair:
        rendu["clair"].append(exporter(clair, "tete_1_col_bois_clair.stl", Z_COL0))

    main, cr = main_griffue()
    rendu["bois"].append(exporter(main, "tete_2_main_ecorce.stl", Z_COL1))
    rendu["cristaux"].append(exporter(cr, "tete_2_main_cristaux.stl", Z_COL1))

    # assemblage complet pour les aperçus (non versionné)
    (SORTIE / "apercu").mkdir(exist_ok=True)
    for cle, morceaux in rendu.items():
        trimesh.util.concatenate(morceaux).export(SORTIE / "apercu" / f"assemblage_{cle}.stl")
