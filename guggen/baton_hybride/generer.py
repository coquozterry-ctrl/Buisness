"""Bâton hybride de la Guggen : un vrai manche en bois au milieu (entouré de ruban à la main),
une tête et un pied imprimés en lianes tressées, et un petit logo à fixer sur le ruban.

- Tête : les lianes montent le long du manche, se resserrent, puis s'ouvrent et s'enroulent
  dans un bouquet de cristaux violets et verts. Une bougie LED se pose sur le bout du manche,
  sous les cristaux.
- Pied : les lianes s'écartent en racines qui s'appuient au sol, et grimpent sur le manche.
- Logo : médaillon ovale, dos incurvé au diamètre du manche + ruban.

Têtes Prusa XL : T1 bois sombre (fourreaux), T2 lianes, T3 cristaux violets,
T4 cristaux verts, T5 or (motif du logo).

Usage : python3 generer.py   (écrit les STL dans ./stl)
"""

import math
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh
from scipy.spatial import cKDTree

# ---------------------------------------------------------------- PARAMÈTRES
DIAM_MANCHE = 28.0         # manche en bois dur (rond de hêtre / frêne) Ø28 mm
JEU = 0.5                  # jeu pour enfiler les pièces sur le manche
EP_RUBAN = 1.5             # épaisseur du ruban / cuir enroulé (pour le dos du logo)
PROF_SOCLE_TETE = 90       # profondeur du manche dans la tête
DIAM_LED = 42.0            # bougie LED chauffe-plat Ø38 mm, posée sur le bout du manche
GRAINE = 21

PAS = 0.5                  # finesse du maillage : plus petit = plus de détails
SORTIE = Path(__file__).parent

R_M = DIAM_MANCHE / 2 + JEU / 2


# ---------------------------------------------------------------- OUTILS
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
    dt = np.roll(anneaux, -1, 1) - np.roll(anneaux, 1, 1)
    dz = np.gradient(anneaux, axis=0)
    n = np.cross(dt, dz)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)


def cylindre(r, h, z0=0.0, x=0.0, y=0.0, n=128) -> Manifold:
    return Manifold.cylinder(h, r, r, n).translate((x, y, z0))


def dessus(z) -> Manifold:
    return Manifold.cube((1000, 1000, 1000)).translate((-500, -500, z))


def union(pieces):
    pieces = [p for p in pieces if p is not None]
    tout = pieces[0]
    for p in pieces[1:]:
        tout = tout + p
    return tout


def lisse(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def coudes(g, n, amp, cles=7):
    """Bruit par morceaux adouci : des coudes naturels plutôt que des courbes parfaites."""
    c = np.linspace(0, 1, cles)
    s = np.linspace(0, 1, n)
    dev = np.stack([np.interp(s, c, g.uniform(-1, 1, cles)) for _ in range(3)], -1)
    k = max(3, n // 40)
    noyau = np.ones(k) / k
    return np.stack([np.convolve(dev[:, i], noyau, mode="same") for i in range(3)], -1) * amp


# ---------------------------------------------------------------- TEXTURES
class Cellules:
    def __init__(self, taille, etirement, graine, lo=(-150, -150, -50), hi=(150, 150, 450)):
        g = np.random.default_rng(graine)
        self.S = np.array([1.0, 1.0, 1.0 / etirement])
        lo, hi = np.array(lo) * self.S, np.array(hi) * self.S
        axes = [np.arange(l, h, taille) for l, h in zip(lo, hi)]
        base = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
        self.arbre = cKDTree(base + g.uniform(0, taille, base.shape))
        self.h = g.uniform(-1, 1, len(base))

    def __call__(self, p):
        d, i = self.arbre.query(p.reshape(-1, 3) * self.S, k=2, workers=-1)
        return (d[:, 1] - d[:, 0]).reshape(p.shape[:-1]), self.h[i[:, 0]].reshape(p.shape[:-1])


GERCES = Cellules(3.0, 1.5, GRAINE)
FENTES = Cellules(4.0, 6.0, GRAINE + 1)


def grain_bois(p):
    e, h = FENTES(p)
    return -0.7 * np.clip(1 - e / 1.0, 0, 1) + 0.12 * h


def texturer(anneaux, fonction, echelle=1.0):
    d = fonction(anneaux) * np.broadcast_to(echelle, anneaux.shape[:-1])
    return anneaux + normales(anneaux) * d[..., None]


def liane(pts, rayons, n=None, graine=0, stries=True):
    """Tube organique : section légèrement ovale qui tourne, fibres dans le sens de la liane,
    petites gerçures d'écorce."""
    pts = np.asarray(pts, float)
    rayons = np.asarray(rayons, float)
    n = n or int(np.clip(2 * math.pi * rayons.max() / PAS, 24, 64))
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    nrm = np.cross(tang[0], [0, 0, 1.0] if abs(tang[0][2]) < 0.9 else [1.0, 0, 0])
    nrm /= np.linalg.norm(nrm)
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    abscisse = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    g = np.random.default_rng(graine)
    nb_fibres = int(g.integers(6, 10))
    vrille, ph = g.uniform(0.02, 0.05) * g.choice([-1, 1]), g.uniform(0, 6.3)
    anneaux = []
    for p, t, r, s in zip(pts, tang, rayons, abscisse):
        nrm = nrm - np.dot(nrm, t) * t
        nrm /= np.linalg.norm(nrm)
        b = np.cross(t, nrm)
        ov = 1 + 0.12 * np.cos(2 * (th + 0.01 * s + ph))                     # section ovale
        rr = r * ov
        if stries:
            f = np.sin(nb_fibres * th + vrille * s + ph)
            rr = rr + np.clip(r / 4, 0.15, 1) * (0.35 * f - 0.45 * np.clip(f, 0.75, 1) * 4 + 1.35)
        anneaux.append(p + rr[:, None] * (np.outer(np.cos(th), nrm) + np.outer(np.sin(th), b)))
    anneaux = np.array(anneaux)
    e, h = GERCES(anneaux)
    ech = np.clip(rayons / 4, 0.1, 1)[:, None]
    anneaux = anneaux + normales(anneaux) * ((-0.45 * np.clip(1 - e / 0.6, 0, 1) + 0.12 * h) * ech)[..., None]
    return loft(anneaux)


def vrille(g, p, out, haut=1.0):
    """Petite vrille enroulée en spirale qui part d'une liane."""
    tours, R0 = g.uniform(1.5, 2.6), g.uniform(4, 7)
    s = np.linspace(0, 1, int(60 * tours))
    a = 2 * math.pi * tours * s
    rr = R0 * (1 - 0.65 * s)
    u = out / np.linalg.norm(out)
    w = np.cross(u, [0, 0, 1.0])
    w /= np.linalg.norm(w)
    centre = p + u * (R0 + 1)
    pts = centre + np.outer(-rr * np.cos(a), u) + np.outer(rr * np.sin(a), w) + np.outer(s * 8 * haut, [0, 0, 1.0])
    r = 1.3 * (1 - 0.5 * s) + 0.4
    return liane(pts, r, n=16, graine=int(g.integers(1e6)), stries=False)


def appui(rv):
    """Rayon d'orbite d'une liane posée contre le manche (sans le toucher)."""
    return R_M + rv + 0.3


# ---------------------------------------------------------------- CRISTAUX
def cristal(g, r, h, inclin, azim, base):
    """Quartz : prisme hexagonal irrégulier, faces striées, pointe décentrée."""
    a = np.arange(6) * math.pi / 3 + g.uniform(-0.12, 0.12, 6)
    rr = r * g.uniform(0.75, 1.2, 6)
    bas = np.stack([rr * np.cos(a), rr * np.sin(a), np.full(6, -10.0)], 1)
    hh = h * (1 + g.uniform(-0.15, 0.05, 6))
    haut = np.stack([rr * np.cos(a) * 0.97, rr * np.sin(a) * 0.97, hh], 1)
    pointe = [[g.uniform(-0.35, 0.35) * r, g.uniform(-0.35, 0.35) * r, h + r * g.uniform(1.4, 2.3)]]
    c = Manifold.hull_points(np.vstack([bas, haut, pointe]))
    if r > 3:
        pas_s = g.uniform(1.6, 2.4)

        def strier(v):                                         # stries horizontales du quartz
            z = v[:, 2]
            ok = (z > -9) & (z < hh.min() - 1)
            rad = np.hypot(v[:, 0], v[:, 1])
            k = np.where(ok, 0.22 * (np.sin(z * 2 * math.pi / pas_s) > 0.55), 0) / np.maximum(rad, 1e-6)
            return np.stack([v[:, 0] * (1 - k), v[:, 1] * (1 - k), z], -1)

        c = c.refine_to_length(0.8).warp_batch(strier)
    return c.rotate((inclin, 0, 0)).rotate((0, 0, azim)).translate(tuple(base))


# ---------------------------------------------------------------- TÊTE
Z_FOURREAU = 55.0                          # début du fourreau (sous : seulement les lianes)
Z_BOUT = Z_FOURREAU + PROF_SOCLE_TETE      # bout du manche (la bougie se pose dessus)
Z_BOUQUET = Z_BOUT + 52.0                  # base des cristaux
R_COU = 25.0                               # rayon du cou sous le bouquet


def rayon_fourreau_tete(z):
    r = R_M + 2.4 + (R_COU - R_M - 2.4) * lisse((z - Z_BOUT + 40) / 80)
    return r * lisse((z - Z_FOURREAU) / 6) + (R_M + 0.6) * (1 - lisse((z - Z_FOURREAU) / 6))


def enveloppe(z):
    """Contour du bouquet de cristaux en fonction de la hauteur."""
    t = np.clip((z - Z_BOUQUET) / 150.0, 0, 1)
    return R_COU + 20 * np.sin(math.pi * t * 0.85) ** 0.8 - 14 * t ** 2       # bouquet effilé


def bouquet():
    g = np.random.default_rng(GRAINE + 2)
    o = np.array([0.0, 0.0, Z_BOUQUET])
    violets = [cylindre(R_COU - 1, 6, Z_BOUQUET - 4), cristal(g, 14, 128, 3, 20, o)]
    verts = []
    couronnes = [(6, 8, 13, (8, 11), (85, 112), (5, 12), 0),
                 (9, 13, 20, (6, 9), (60, 90), (12, 22), 2),
                 (12, 18, 24, (4, 7), (35, 62), (22, 34), 5),
                 (14, 21, 26, (2.5, 4.5), (16, 34), (34, 50), 8)]
    for n, d0, d1, rr, hh, inc, dz in couronnes:
        for k in range(n):
            a = 2 * math.pi * k / n + g.uniform(-0.2, 0.2)
            d = g.uniform(d0, d1)
            c = cristal(g, g.uniform(*rr), g.uniform(*hh), g.uniform(*inc), math.degrees(a) + 90,
                        o + [d * math.cos(a), d * math.sin(a), dz])
            (verts if g.uniform() < 0.3 else violets).append(c)
    violets, verts = union(violets), union(verts)
    return violets - verts, verts


def lianes_tete():
    g = np.random.default_rng(GRAINE + 3)
    tubes, bouts = [], []
    n = 16
    for i in range(n):
        rv = g.uniform(3.2, 5.5) if i < 8 else g.uniform(2.0, 3.4)
        sens = 1 if i % 2 else -1
        pas = g.uniform(170, 300)
        ph = 2 * math.pi * i / n + g.uniform(-0.2, 0.2)
        z0 = g.uniform(0, 35)
        z1 = Z_BOUQUET + (g.uniform(25, 70) if i % 3 == 0 else g.uniform(80, 140))
        z = np.arange(z0 - 4, z1, PAS * 0.8)
        u = np.clip((z - (z1 - 35)) / 35, 0, 1)                    # dernière portion : la pointe
        tresse = 0.35 * np.sin(2 * math.pi * z / 55 + i)           # les paires se tressent
        a = ph + sens * 2 * math.pi * z / pas * (1 - 0.7 * lisse((z - Z_BOUQUET + 20) / 40)) + tresse
        orb_bas = np.maximum(appui(rv), rayon_fourreau_tete(z) + rv * 0.35)
        orb_haut = enveloppe(z) - rv * 0.4 - 10 * u ** 2          # entre les cristaux, pointe crochue
        m = lisse((z - Z_BOUQUET + 15) / 30)
        orb = orb_bas * (1 - m) + orb_haut * m
        pts = np.stack([orb * np.cos(a), orb * np.sin(a), z], -1)
        pts = pts + coudes(g, len(z), 1.2) * lisse((z - Z_BOUT) / 60)[:, None]
        r = rv * (1 - 0.85 * u ** 1.3) * lisse((z - z0 + 4) / 10) * 0.85 + rv * 0.15
        tubes.append(liane(pts, r, graine=int(g.integers(1e6))))
        bouts.append((pts, r))
    for k in range(10):                                           # vrilles
        pts, r = bouts[int(g.integers(len(bouts)))]
        j = int(g.uniform(0.55, 0.85) * len(pts))
        out = np.array([pts[j][0], pts[j][1], 0.0])
        tubes.append(vrille(g, pts[j], out))
    return union(tubes)


def tete():
    zs = np.arange(Z_FOURREAU, Z_BOUQUET + 2, PAS)
    th = np.linspace(0, 2 * math.pi, 200, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    R = rayon_fourreau_tete(Z)
    fourreau = loft(texturer(np.stack([R * np.cos(TH), R * np.sin(TH), Z], -1), grain_bois))
    lian = lianes_tete() ^ dessus(0)
    creux = cylindre(R_M, Z_BOUT + 1, -1) + cylindre(DIAM_LED / 2, Z_BOUQUET - Z_BOUT + 2, Z_BOUT - 0.5)
    vis = Manifold.cylinder(40, 1.6, 1.6, 24).rotate((0, 90, 0)).translate((0, 0, Z_FOURREAU + 30))
    bois = fourreau - creux - vis - lian
    lian = lian - creux - vis
    violets, verts = bouquet()
    violets, verts = violets - lian - bois, verts - lian - bois
    return bois, lian, violets, verts


# ---------------------------------------------------------------- PIED
Z_SOL = 12.0                     # épaisseur sous le manche
H_FOURREAU_PIED = 200.0


def rayon_fourreau_pied(z):
    r = R_M + 2.4 + 9 * np.exp(-z / 22)
    fin = 1 - lisse((z - H_FOURREAU_PIED + 8) / 8)
    return r * fin + (R_M + 0.6) * (1 - fin)


def pied():
    g = np.random.default_rng(GRAINE + 5)
    zs = np.arange(0, H_FOURREAU_PIED + PAS, PAS)
    th = np.linspace(0, 2 * math.pi, 200, endpoint=False)
    Z, TH = np.meshgrid(zs, th, indexing="ij")
    R = rayon_fourreau_pied(Z)
    s = texturer(np.stack([R * np.cos(TH), R * np.sin(TH), Z], -1), grain_bois)
    s[0, :, 2] = 0
    fourreau = loft(s)

    tubes = []
    n = 14
    for i in range(n):                                            # lianes qui grimpent
        rv = g.uniform(3.4, 5.8) if i < 7 else g.uniform(2.2, 3.6)
        sens = 1 if i % 2 else -1
        pas = g.uniform(170, 300)
        ph = 2 * math.pi * i / n + g.uniform(-0.2, 0.2)
        z1 = g.uniform(220, 320)
        z = np.arange(-6, z1, PAS * 0.8)
        u = np.clip((z - (z1 - 30)) / 30, 0, 1)
        a = ph + sens * 2 * math.pi * z / pas + 0.35 * np.sin(2 * math.pi * z / 55 + i)
        orb = np.maximum(appui(rv), rayon_fourreau_pied(z) + rv * 0.35)
        orb = orb + g.uniform(18, 34) * np.exp(-np.clip(z, 0, None) / g.uniform(20, 35))   # s'écarte en racine
        pts = np.stack([orb * np.cos(a), orb * np.sin(a), z], -1) + coudes(g, len(z), 1.0)
        r = rv * (1 + 0.5 * np.exp(-np.clip(z, 0, None) / 25)) * (1 - 0.85 * u ** 1.3)
        tubes.append(liane(pts, r, graine=int(g.integers(1e6))))
        if i < 6:                                                 # grosses racines au sol
            a0 = ph + g.uniform(-0.3, 0.3)
            L = g.uniform(45, 70)
            s_ = np.linspace(0, 1, int(L / PAS))
            rad = orb[10] * 0.8 + L * s_
            zz = 25 * (1 - s_) ** 1.6 - 3
            pts = np.stack([rad * np.cos(a0 + 0.3 * s_), rad * np.sin(a0 + 0.3 * s_), zz], -1) + coudes(g, len(s_), 2.0)
            tubes.append(liane(pts, rv * 1.5 * (1 - 0.55 * s_), graine=int(g.integers(1e6))))
    for k in range(6):
        i = int(g.integers(n))
        z = g.uniform(90, 200)
        a = g.uniform(0, 2 * math.pi)
        p = np.array([(R_M + 4) * math.cos(a), (R_M + 4) * math.sin(a), z])
        tubes.append(vrille(g, p, np.array([math.cos(a), math.sin(a), 0.0])))
    lian = union(tubes) ^ dessus(0)
    creux = cylindre(R_M, 1000, Z_SOL)
    vis = Manifold.cylinder(40, 1.6, 1.6, 24).rotate((0, 90, 0)).translate((0, 0, 100))
    bois = fourreau - creux - vis - lian
    return bois, lian - creux - vis


# ---------------------------------------------------------------- LOGO
def logo():
    """Médaillon ovale : bord perlé, cristal en relief entouré de deux lianes, dos incurvé."""
    rc = DIAM_MANCHE / 2 + EP_RUBAN                       # rayon du manche + ruban
    L, W, E = 34.0, 24.0, 3.2
    plaque = Manifold.sphere(1.0, 96).scale((W / 2, L / 2, E)).trim_by_plane((0, 0, 1), 0)
    plaque = plaque + Manifold.cylinder(1.2, 1, 1, 96).scale((W / 2, L / 2, 1)).translate((0, 0, -1.2))
    perles = []
    for k in range(28):
        a = 2 * math.pi * k / 28
        perles.append(Manifold.sphere(1.05, 16).translate((0.43 * W * math.cos(a), 0.43 * L * math.sin(a), 1.6)))
    dome = lambda x, y: E * np.sqrt(np.clip(1 - (x / (W / 2)) ** 2 - (y / (L / 2)) ** 2, 0, 1))
    hexa = [(3.6 * math.cos(k * math.pi / 3), 3.6 * math.sin(k * math.pi / 3) * 0.45) for k in range(6)]
    pts_c = [(x, y0, z) for y0 in (-9.0, 4.0) for x, z in hexa] + [(0.6, 11.0, 0.3)]
    motif = Manifold.hull_points(np.array(pts_c)).translate((0, 0, E + 0.4))     # cristal en relief
    for s in (-1, 1):                                                          # deux lianes autour
        t = np.linspace(0, 1, 90)
        x = s * (4.6 + 2.6 * np.sin(math.pi * t))
        y = -12 + 23 * t
        pts = np.stack([x, y, dome(x, y) + 0.3 + 0.35 * np.sin(4 * math.pi * t)], -1)
        motif = motif + liane(pts, 0.95 * (1 - 0.45 * t), n=14, stries=False)
    fond = plaque - union(perles) - motif
    or_ = (union(perles) + motif) ^ Manifold.cube((100, 100, 100)).translate((-50, -50, -1.2))

    def courber(v):                                       # dos incurvé pour épouser le manche
        x, y, z = v[:, 0], v[:, 1], v[:, 2]
        a = x / rc
        r = rc + 1.2 + z
        return np.stack([r * np.sin(a), y, r * np.cos(a) - rc], -1)

    fond = fond.refine_to_length(0.6).warp_batch(courber)
    or_ = or_.refine_to_length(0.6).warp_batch(courber)
    return fond, or_ - fond


# ---------------------------------------------------------------- MAIN
def exporter(man, nom):
    man = Manifold.compose([c for c in man.decompose() if c.volume() > 1.0])
    m = vers_trimesh(man)
    assert m.is_watertight, f"{nom} : maillage non étanche"
    m.export(SORTIE / "stl" / nom)
    print(f"{nom:30s} {m.extents.round(0)} mm  {m.volume / 1000:6.1f} cm3  {len(m.faces):7d} tri")
    return m


if __name__ == "__main__":
    (SORTIE / "stl").mkdir(exist_ok=True)
    (SORTIE / "apercu").mkdir(exist_ok=True)
    for f in (SORTIE / "stl").glob("*.stl"):
        f.unlink()
    pb, pl = pied()
    pied_b = exporter(pb, "pied_bois.stl")
    pied_l = exporter(pl, "pied_lianes.stl")
    tb, tl, tv, tg = tete()
    tete_b = exporter(tb, "tete_bois.stl")
    tete_l = exporter(tl, "tete_lianes.stl")
    tete_v = exporter(tv, "tete_cristaux_violets.stl")
    tete_g = exporter(tg, "tete_cristaux_verts.stl")
    exporter(cylindre(R_M + 3, 15) - cylindre(R_M, 17, -1), "test_manche.stl")   # bague d'essai
    lf, lo = logo()
    logo_f = exporter(lf, "logo_fond.stl")
    logo_o = exporter(lo, "logo_motif_or.stl")

    # aperçu monté (non versionné) : manche + ruban + pièces, bâton de 1,80 m
    H = 1800.0
    z_tete = H - (Z_BOUQUET + 140)
    manche = trimesh.creation.cylinder(radius=DIAM_MANCHE / 2, height=z_tete + Z_BOUT - Z_SOL, sections=96)
    manche.apply_translation((0, 0, (z_tete + Z_BOUT + Z_SOL) / 2))
    ruban = trimesh.creation.cylinder(radius=DIAM_MANCHE / 2 + EP_RUBAN, height=420, sections=96)
    ruban.apply_translation((0, 0, z_tete - 330))
    medaillon = trimesh.util.concatenate([logo_f, logo_o]).copy()
    medaillon.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
    medaillon.apply_translation((0, 0, z_tete - 200))
    medaillon.apply_translation((0, -(DIAM_MANCHE / 2 + EP_RUBAN), 0))
    decal = lambda m, dz: m.copy().apply_translation((0, 0, dz))
    sorties = {
        "bois": [pied_b, decal(tete_b, z_tete), manche],
        "lianes": [pied_l, decal(tete_l, z_tete)],
        "cuir": [ruban, medaillon],
        "violet": [decal(tete_v, z_tete)],
        "vert": [decal(tete_g, z_tete)],
    }
    for cle, morceaux in sorties.items():
        trimesh.util.concatenate(morceaux).export(SORTIE / "apercu" / f"assemblage_{cle}.stl")
    print(f"Manche à couper : {z_tete + Z_BOUT - Z_SOL:.0f} mm")
