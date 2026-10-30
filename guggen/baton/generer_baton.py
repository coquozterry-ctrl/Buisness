"""Génère le bâton de la Guggen en pièces imprimables multi-matériaux (Prusa XL).

Principe : un tube alu Ø16 mm sert d'âme (solidité), les tronçons imprimés s'enfilent
dessus et forment l'écorce calcinée. Une veine dorée court dans un sillon de l'écorce
(2e couleur). En haut, une main noueuse enserre des cristaux translucides imprimés
dans la même pièce (3e couleur). La main s'emboîte sur le col, qui cache une bougie LED.

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
RAYON_FUT = 23.0           # rayon moyen du fût (≈ Ø46-56 mm avec les reliefs)
ONDULATION = 6.0           # amplitude des ondulations du fût
PAROI_MIN = 3.5            # paroi minimale autour du tube, sous les fissures
PROF_DOUILLE = 120         # profondeur du tube dans le col
DIAM_LED = 42.0            # bougie LED « chauffe-plat » Ø38 mm
GRAINE = 7                 # change la graine pour un autre bâton "unique"

PAS = 0.7                  # finesse du maillage (taille des fissures ≈ 2 mm)
SORTIE = Path(__file__).parent

R_ALESAGE = DIAM_TUBE / 2 + JEU / 2
Z_COL0 = LONGUEUR_FUT
Z_COL1 = LONGUEUR_FUT + 250
R_TENON, H_TENON = 24.0, 25.0      # emboîtement main / col (contient la bougie)
HP = 75.0                          # hauteur de la paume

rng = np.random.default_rng(GRAINE)
NOEUDS = [(rng.uniform(80, Z_COL1), rng.uniform(0, 2 * math.pi),
           rng.uniform(2.5, 5.0), rng.uniform(15, 35), rng.uniform(0.35, 0.7))
          for _ in range(22)]


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


def union(pieces):
    tout = pieces[0]
    for p in pieces[1:]:
        tout = tout + p
    return tout


# ---------------------------------------------------------------- TEXTURE D'ÉCORCE
class Cellules:
    """Bruit cellulaire 3D (Worley) : plaques d'écorce calcinée séparées par des fissures."""

    def __init__(self, taille, etirement, graine):
        g = np.random.default_rng(graine)
        self.S = np.array([1.0, 1.0, 1.0 / etirement])
        lo = np.array([-200, -200, -50]) * self.S
        hi = np.array([250, 250, Z_COL1 + 450]) * self.S
        axes = [np.arange(l, h, taille) for l, h in zip(lo, hi)]
        base = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
        pts = base + g.uniform(0, taille, base.shape)
        self.arbre = cKDTree(pts)
        self.h = g.uniform(-1, 1, len(pts))

    def __call__(self, p):
        d, i = self.arbre.query(p.reshape(-1, 3) * self.S, k=2, workers=-1)
        return (d[:, 1] - d[:, 0]).reshape(p.shape[:-1]), self.h[i[:, 0]].reshape(p.shape[:-1])


PLAQUES = Cellules(8.0, 4.0, GRAINE)        # plaques allongées : sillons d'écorce d'arbre
GERCURES = Cellules(3.0, 1.8, GRAINE + 1)
PROF_ECORCE = 3.4


def ecorce(p):
    """Déplacement (mm, négatif = vers l'intérieur) de l'écorce au point p."""
    e1, h1 = PLAQUES(p)
    e2, _ = GERCURES(p)
    fissure = np.clip(1 - e1 / 2.0, 0, 1) ** 1.3
    gercure = np.clip(1 - e2 / 0.7, 0, 1)
    fibres = np.sin(p[..., 2] * 0.9 + 3 * np.sin(p[..., 0] * 0.21) + 3 * np.sin(p[..., 1] * 0.19))
    return -2.6 * fissure + 0.5 * h1 * (1 - fissure) - 0.5 * gercure + 0.15 * fibres


def texturer(anneaux, echelle=1.0):
    d = ecorce(anneaux) * np.broadcast_to(echelle, anneaux.shape[:-1])
    return anneaux + normales(anneaux) * d[..., None]


# ---------------------------------------------------------------- FORME DU BOIS
def torsion(z):
    return 2 * math.pi * z / 330.0 + 0.6 * np.sin(z / 210.0)


def centre(z):
    """Ligne moyenne : ondulée le long du tube, puis le col se cambre en S."""
    x = ONDULATION * (np.sin(2 * math.pi * z / 520 + 0.4) + 0.5 * np.sin(2 * math.pi * z / 230 + 1.7))
    y = ONDULATION * (0.8 * np.sin(2 * math.pi * z / 610 + 2.1) + 0.4 * np.sin(2 * math.pi * z / 270))
    z0 = Z_COL0 + PROF_DOUILLE + 5
    t = np.clip((z - z0) / (Z_COL1 - z0), 0, 1)
    fin = np.where(z > z0, np.clip((Z_COL1 - z) / 60, 0, 1), 1)  # ondulation éteinte en haut
    return x * fin + 38 * np.sin(math.pi * t) * t, y * fin - 12 * np.sin(2 * math.pi * t)


def rayon(z, th):
    r = RAYON_FUT + 1.5 * np.sin(z / 170.0) + 0.8 * np.sin(z / 53.0 + 1)
    r = r - 2.0 * np.exp(-z / 60.0)                               # pied un peu affiné
    r = r + 9.0 * np.clip((z - Z_COL0) / (Z_COL1 - Z_COL0), 0, 1) ** 1.5      # le col s'élargit
    tw = torsion(z)
    r = r + 4.5 * np.cos(3 * th - tw)                             # 3 brins enroulés
    r = r + 1.2 * np.cos(5 * th + 0.7 * tw + 1.3)
    for (zn, an, hn, wz, wa) in NOEUDS:
        da = np.angle(np.exp(1j * (th - an)))
        r = r + hn * np.exp(-((z - zn) / wz) ** 2 - (da / wa) ** 2)
    return r


def points_bois(z, th):
    """Surface lisse du bois, repoussée pour garder la paroi autour du tube droit."""
    r = rayon(z, th)
    cx, cy = centre(z)
    x, y = cx + r * np.cos(th), cy + r * np.sin(th)
    rmin = R_ALESAGE + PAROI_MIN + PROF_ECORCE
    d = np.hypot(x, y)
    k = 2.0
    d2 = np.where(z < Z_COL0 + PROF_DOUILLE + 15, k * np.logaddexp(d / k, rmin / k), d)  # max doux
    f = d2 / np.maximum(d, 1e-9)
    return np.stack([x * f, y * f, z], -1)


def surface_bois(z0, z1):
    zs = np.linspace(z0, z1, int(round((z1 - z0) / PAS)) + 1)
    th = np.linspace(0, 2 * math.pi, 288, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    s = texturer(points_bois(Z, TH))
    s[..., 2] = np.where(np.isin(Z, (z0, z1)), Z, s[..., 2])     # tranches bien planes
    return s


def tube_balaye(pts, rayons, n=24, texture=None):
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
        anneaux.append(p + r * (np.outer(np.cos(th), nrm) + np.outer(np.sin(th), b)))
    anneaux = np.array(anneaux)
    if texture is not None:
        anneaux = texturer(anneaux, texture[:, None] * np.ones(n))
    return loft(anneaux)


# ---------------------------------------------------------------- VEINE DORÉE
def veine() -> Manifold:
    """Filon doré logé dans le creux entre deux brins, qui affleure puis replonge."""
    z = np.arange(25, Z_COL1 - 25, 1.0)
    th = (math.pi + torsion(z)) / 3 + 0.15 * np.sin(z / 47)
    surf = points_bois(z, th)
    cx, cy = centre(z)
    rv = 4.2 + 1.2 * np.sin(z / 61 + 1) + 0.6 * np.sin(z / 23)
    enfonce = rv - 0.6 + 3.0 * np.clip(np.sin(z / 150 + 0.5), 0, 1) ** 3  # affleure, replonge par endroits
    rv = rv * np.clip(np.minimum(z - 25, Z_COL1 - 25 - z) / 40, 0.15, 1)
    ax = np.stack([surf[:, 0] - cx, surf[:, 1] - cy], -1)
    ax /= np.linalg.norm(ax, axis=1)[:, None]
    p = surf.copy()
    p[:, :2] -= ax * enfonce[:, None]
    d = np.hypot(p[:, 0], p[:, 1])                                       # paroi min. autour du tube
    dmin = np.where(z < Z_COL0 + PROF_DOUILLE + 10, R_ALESAGE + 2.0 + rv, 0)
    p[:, :2] *= (np.maximum(d, dmin) / np.maximum(d, 1e-9))[:, None]
    return tube_balaye(p, rv, n=20)


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


# ---------------------------------------------------------------- BRANCHES CASSÉES
def placer(man, p, d):
    """Oriente une pièce modélisée le long de +z selon la direction d, au point p."""
    d = d / np.linalg.norm(d)
    u = np.cross(d, [0, 0, 1.0])
    u = u / np.linalg.norm(u) if np.linalg.norm(u) > 1e-6 else np.array([1.0, 0, 0])
    v = np.cross(d, u)
    return man.transform(np.column_stack([u, v, d, p]))


def chicot(g, z, th):
    """Moignon de branche écorcé, cassé net, avec le bois clair éclaté au bout."""
    surf = points_bois(np.array([z]), np.array([th]))[0]
    cx, cy = centre(z)
    rad = np.array([surf[0] - cx, surf[1] - cy, 0.0])
    rad /= np.linalg.norm(rad)
    e = math.radians(g.uniform(42, 60))                       # pointe vers le haut : imprimable
    d = math.cos(e) * rad + math.sin(e) * np.array([0, 0, 1.0])
    r0, L = g.uniform(5, 11), g.uniform(15, 45)
    ancrage = 1.6 * r0 + 4                                     # départ bien noyé dans le tronc
    t = np.linspace(0, 1, max(int((L + ancrage) / PAS), 20))
    courbe = np.outer(t ** 2, [0, 0, 1.0]) * g.uniform(0, 0.15) * L
    pts = surf - ancrage * d + np.outer(t, d * (L + ancrage)) + courbe
    tb = ancrage / (L + ancrage)                               # position de la surface du tronc
    r = r0 * (1 + 0.3 * np.exp(-np.clip(t - tb, 0, None) / 0.08)) * (1 - 0.2 * t)  # bourrelet
    ecorce_ch = tube_balaye(pts, r, n=72, texture=np.full(len(t), 0.6))

    bout, axe = pts[-1], pts[-1] - pts[-2]
    rc = r[-1] * 0.78
    coeur = [Manifold.cylinder(4, rc, rc, 48).translate((0, 0, -3.5))]
    for k in range(g.integers(5, 9)):                          # échardes
        a, rr = g.uniform(0, 2 * math.pi), g.uniform(0, rc * 0.75)
        x, y = rr * math.cos(a), rr * math.sin(a)
        w = g.uniform(1.0, 2.0)
        base = [[x + w * math.cos(b), y + w * math.sin(b), 0] for b in (0, 2.1, 4.2)]
        pointe = [[x + g.uniform(-1.5, 1.5), y + g.uniform(-1.5, 1.5), g.uniform(2, 3 + r0 * 0.6)]]
        coeur.append(Manifold.hull_points(np.array(base + pointe)))
    coeur = placer(union(coeur), bout, axe)
    return ecorce_ch - coeur, coeur


def chicots():
    """Répartit les moignons sur toute la montée, loin des jointures et de la veine."""
    g = np.random.default_rng(GRAINE + 4)
    h = LONGUEUR_FUT / NB_SEGMENTS
    coupes = [0, *(h * k for k in range(1, NB_SEGMENTS + 1)), Z_COL1]
    voulus = [4] * NB_SEGMENTS + [2]
    places = []
    for (z0, z1), n in zip(zip(coupes, coupes[1:]), voulus):
        essais = 0
        while sum(z0 <= p[0] < z1 for p in places) < n and essais < 500:
            essais += 1
            z, th = g.uniform(z0 + 25, z1 - 60), g.uniform(0, 2 * math.pi)
            th_veine = (math.pi + torsion(z)) / 3 + 0.15 * math.sin(z / 47)
            if abs(np.angle(np.exp(1j * (th - th_veine)))) < 0.9:
                continue
            if any(abs(z - pz) < 70 and abs(np.angle(np.exp(1j * (th - pt)))) < 1.2 for pz, pt in places):
                continue
            places.append((z, th))
    return [(z, *chicot(g, z, th)) for z, th in places]


# ---------------------------------------------------------------- PIÈCES
def ajouter_chicots(bois, liste, z0, z1):
    clair = [c for z, _, c in liste if z0 <= z < z1]
    bois = union([bois] + [e for z, e, _ in liste if z0 <= z < z1])
    clair = union(clair) if clair else None
    return (bois - clair if clair else bois), clair


def segment_fut(i, filon, liste):
    h = LONGUEUR_FUT / NB_SEGMENTS
    z0 = i * h
    alesage = cylindre(R_ALESAGE, h + 2, z0 - 1)
    bois, clair = ajouter_chicots(loft(surface_bois(z0, z0 + h)), liste, z0, z0 + h)
    bois = bois - alesage
    return bois - filon, (filon ^ bois.hull()) - alesage, clair


def trous_goupilles():
    """2 trous Ø3,2 pour goupiller la main sur le col (clous ou vis M3)."""
    cx, cy = centre(Z_COL1)
    trous = []
    for a in (20, 200):
        c = Manifold.cylinder(30, 1.6, 1.6, 24).rotate((0, 90, 0)).translate((R_TENON - 10, 0, 0))
        trous.append(c.rotate((0, 0, a)).translate((cx, cy, Z_COL1 + H_TENON / 2)))
    return trous[0] + trous[1]


def col(filon, liste):
    cx, cy = centre(Z_COL1)
    bois, clair = ajouter_chicots(loft(surface_bois(Z_COL0, Z_COL1)), liste, Z_COL0, Z_COL1)
    bois = bois - cylindre(R_ALESAGE, PROF_DOUILLE + 1, Z_COL0 - 1)               # douille
    bois = bois + cylindre(R_TENON, H_TENON + 1, Z_COL1 - 1, cx, cy)              # tenon
    bois = bois - cylindre(DIAM_LED / 2, 23, Z_COL1 + H_TENON - 22, cx, cy)       # logement bougie
    bois = bois - trous_goupilles()
    return bois - filon, (filon ^ bois.hull()) - cylindre(R_ALESAGE, PROF_DOUILLE + 1, Z_COL0 - 1), clair


def main_griffue():
    """Paume noueuse + 6 doigts écorcés qui enserrent la grappe de cristaux."""
    cx, cy = centre(Z_COL1)
    zs = np.linspace(Z_COL1, Z_COL1 + HP, int(HP / PAS) + 1)
    th = np.linspace(0, 2 * math.pi, 320, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    R = rayon(Z, TH) + 9.0 * ((Z - Z_COL1) / HP) ** 1.5
    paume = loft(texturer(np.stack([cx + R * np.cos(TH), cy + R * np.sin(TH), Z], -1)))

    g = np.random.default_rng(GRAINE + 3)
    doigts = []
    for k in range(6):
        a = 2 * math.pi * k / 6 + g.uniform(-0.2, 0.2)
        L = g.uniform(230, 270)
        s = np.linspace(0, 1, int(L / PAS))
        rad = 16 + g.uniform(38, 48) * np.sin(math.pi * s * 0.75) - g.uniform(16, 24) * s ** 4
        z = Z_COL1 + HP * 0.5 + L * 0.8 * (s - 0.2 * s ** 3)
        tw = a + g.uniform(0.3, 0.6) * s * g.choice([-1, 1])                       # vrillé
        pts = np.stack([cx + rad * np.cos(tw), cy + rad * np.sin(tw), z], -1)
        r = 12.0 * (1 - s) ** 0.8 + 2.2
        for pos in (0.3, 0.55, 0.78):                                               # jointures
            r = r + 3.0 * np.exp(-((s - pos) / 0.04) ** 2) * (1 - 0.6 * s)
        doigts.append(tube_balaye(pts, r, n=96, texture=np.clip(r / 10, 0.2, 1)))

    main = union([paume] + doigts)
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
    print(f"{nom:26s} {m.extents.round(0)} mm  {m.volume / 1000:5.0f} cm3  {len(m.faces):7d} tri")
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
    h = LONGUEUR_FUT / NB_SEGMENTS
    liste = chicots()
    rendu = {"bois": [], "veine": [], "cristaux": [], "clair": []}
    for i in range(NB_SEGMENTS):
        bois, v, clair = segment_fut(i, filon, liste)
        verifier_paroi(bois + v, i * h, (i + 1) * h)          # la veine compte dans la paroi
        rendu["bois"].append(exporter(bois, f"fut_{i + 1}_ecorce.stl", i * h))
        rendu["veine"].append(exporter(v, f"fut_{i + 1}_veine.stl", i * h))
        if clair:
            rendu["clair"].append(exporter(clair, f"fut_{i + 1}_bois_clair.stl", i * h))

    bois, v, clair = col(filon, liste)
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
