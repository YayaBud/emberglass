"""The Ashdunes asset kit (implementation_plan Phase 5b). No reference sheet
yet: built in the Hoarfells kit's style -- chunky, faceted, shaded per pixel
by material name -- so the two regions read as one game.

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background --factory-startup \\
        --python D:/assests/scripts/forge/desertkit/desertkit.py

Writes game/assets/models/desertkit/desertkit.glb (one object per asset) and
renders/desertkit/kit_*.png. Uses snowkit's Mesh (metre UVs, faces turned out
from a centre) and its workbench preview.

Materials are NAMES; the game's `Kit` shades each (UVs in metres):
  strata (natural sandstone: layers from WORLD height, so boulders, ledges
  and the mesa share bands), sandstone (cut blocks), glyph (blocks carved
  with rows of signs), adobe / whitewash / burlap (plaster, sacking),
  cloth / cloth2 (canvas, stripes along u), clay (terracotta, painted
  bands at 0.3 and 0.56 m), palmbark (UV.y 0 at each ring's foot),
  palm / deadfrond / dry (leaves: UV2.x 0 at the tip .. 1 at the base,
  UV2.y 0 on the midrib .. 1 at the edge -- cut into leaflets past 0.22),
  cactus, bloom, dates, bone, rug (pattern about UV 0), gold, fire, sand,
  shade (dark openings), and the snow kit's wood, logend, iron.
+Z up, each asset's foot at its origin, front toward -Y.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "snowkit"))
import snowkit as sk  # noqa: E402
from snowkit import Mesh, X, Y, Z, fronds  # noqa: E402

OUT = os.path.join(sk.ROOT, "game", "assets", "models", "desertkit")
sk.REN = os.path.join(sk.ROOT, "renders", "desertkit")
sk.COLS.update({  # preview colours only
    "strata": (0.78, 0.52, 0.32), "sandstone": (0.80, 0.62, 0.40), "glyph": (0.72, 0.54, 0.34),
    "adobe": (0.74, 0.56, 0.38), "whitewash": (0.88, 0.84, 0.76), "burlap": (0.58, 0.46, 0.30),
    "cloth": (0.70, 0.16, 0.12), "cloth2": (0.14, 0.30, 0.52), "clay": (0.72, 0.36, 0.20),
    "palmbark": (0.42, 0.30, 0.20), "palm": (0.30, 0.46, 0.18), "deadfrond": (0.52, 0.40, 0.24),
    "dry": (0.60, 0.50, 0.28), "cactus": (0.26, 0.44, 0.24), "bloom": (0.95, 0.45, 0.60),
    "dates": (0.55, 0.22, 0.08), "bone": (0.90, 0.86, 0.74), "rug": (0.60, 0.14, 0.12),
    "gold": (0.95, 0.72, 0.25), "fire": (1.0, 0.55, 0.15), "sand": (0.82, 0.68, 0.45),
    "shade": (0.08, 0.06, 0.05), "drum": (0.80, 0.62, 0.40),
})


# ----------------------------------------------------------------- helpers
def lathe(m, prof, n, mat, base=(0, 0, 0), rib=0.0, top=True, spin=0.0, capmat=None):
    """A turned solid about the vertical through `base`. `prof` is (z, r)
    from the foot up; it may turn back down inside a pot's mouth. Every other
    vertex is pulled in by `rib` (cactus ribs, flutes). UV: (arc, z)."""
    b = Vector(base)

    def ring(z, r):
        return [b + Vector((math.cos(spin + k * math.tau / n) * r * (1 - rib * (k % 2)),
                            math.sin(spin + k * math.tau / n) * r * (1 - rib * (k % 2)), z)) for k in range(n)]

    rings = [ring(z, max(r, 1e-3)) for z, r in prof]
    for i in range(len(prof) - 1):
        (z0, r0), (z1, r1) = prof[i], prof[i + 1]
        for k in range(n):
            j = (k + 1) % n
            q = [rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]]
            mid = sum(q, Vector()) / 4
            rad = mid - b
            rad.z = 0
            rad.normalize()
            # the surface's outward side, from the profile's direction: a
            # mouth turning down inside a pot faces in and up
            out = rad * (z1 - z0) - Z * (r1 - r0)
            if out.length < 1e-6:
                out = rad
            u0, u1 = k * math.tau * max(r0, r1) / n, (k + 1) * math.tau * max(r0, r1) / n
            m.out(q, mat, mid - out.normalized(), uv=[(u0, z0), (u1, z0), (u1, z1), (u0, z1)])
    if top and prof[-1][1] > 0.01:
        c = b + Z * prof[-1][0]
        for k in range(n):
            m.out([rings[-1][k], rings[-1][(k + 1) % n], c], capmat or mat, c - Z)


def blob(m, c, rx, ry, rz, rnd, mat="strata", n=8, rings=4):
    """A weathered lump, its foot sunk below c.z: rings of jittered vertices
    shared between triangles, closed by a fan at the top."""
    c = Vector(c)
    grid = []
    for i in range(rings + 1):
        ph = -0.45 + i * 1.35 / rings
        row = []
        for k in range(n):
            a = k * math.tau / n + (i % 2) * math.pi / n + rnd.uniform(-0.12, 0.12)
            j = rnd.uniform(0.86, 1.12)
            row.append(c + Vector((math.cos(a) * math.cos(ph) * rx * j, math.sin(a) * math.cos(ph) * ry * j, math.sin(ph) * rz)))
        grid.append(row)
    top = c + Vector((rnd.uniform(-0.1, 0.1) * rx, rnd.uniform(-0.1, 0.1) * ry, rz * rnd.uniform(0.95, 1.05)))
    for i in range(rings):
        for k in range(n):
            j = (k + 1) % n
            a, b, d, e = grid[i][k], grid[i][j], grid[i + 1][j], grid[i + 1][k]
            m.out([a, b, d], mat, c)
            m.out([a, d, e], mat, c)
    for k in range(n):
        m.out([grid[-1][k], grid[-1][(k + 1) % n], top], mat, c)


def outline(rx, ry, rnd, n=9, jag=0.14):
    pts = []
    for k in range(n):
        a = k * math.tau / n + rnd.uniform(-0.2, 0.2)
        j = rnd.uniform(1 - jag, 1 + jag)
        pts.append(Vector((math.cos(a) * rx * j, math.sin(a) * ry * j, 0)))
    return pts


def tier(m, c, rx, ry, z0, z1, rnd, n=9, mat="strata", jag=0.14, shrink=0.08, pts=None):
    """One layer of a butte: an irregular prism z0..z1 (outline `pts`, or a
    fresh one), its sides leaning in by `shrink`, a fan top."""
    c = Vector(c)
    pts = pts or outline(rx, ry, rnd, n, jag)
    n = len(pts)
    bot = [c + p + Z * z0 for p in pts]
    top = [c + p * (1 - shrink) + Z * z1 for p in pts]
    mid = c + Z * ((z0 + z1) / 2)
    for k in range(n):
        j = (k + 1) % n
        m.out([bot[k], bot[j], top[j], top[k]], mat, mid)
    tc = c + Z * z1
    for k in range(n):
        m.out([top[k], top[(k + 1) % n], tc], mat, tc - Z)


def frustum(m, c, s0, s1, z0, z1, mat):
    """A four-sided block battered in: footprint s0 (w, d) at z0, s1 at z1."""
    c = Vector(c)
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    b = [c + Vector((sx * s0[0] / 2, sy * s0[1] / 2, z0)) for sx, sy in corners]
    t = [c + Vector((sx * s1[0] / 2, sy * s1[1] / 2, z1)) for sx, sy in corners]
    mid = c + Z * ((z0 + z1) / 2)
    for k in range(4):
        j = (k + 1) % 4
        m.out([b[k], b[j], t[j], t[k]], mat, mid)
    m.out(t, mat, mid)


def sand(m, c, r, h, rnd, squash=1.0, n=9):
    """A drift of sand: a low dome, longer down-wind (+X), its foot sunk."""
    c = Vector(c)
    base, mid = [], []
    for k in range(n):
        a = k * math.tau / n
        rr = r * rnd.uniform(0.85, 1.15)
        d = Vector((math.cos(a) * (1.35 if math.cos(a) > 0 else 1.0), math.sin(a) * squash, 0))
        base.append(c + d * rr - Z * 0.08)
        mid.append(c + d * rr * 0.55 + Z * h * rnd.uniform(0.62, 0.8))
    top = c + Vector((-0.15 * r, 0, h))
    below = c - Z * 0.5
    for k in range(n):
        j = (k + 1) % n
        m.out([base[k], base[j], mid[j]], "sand", below)
        m.out([base[k], mid[j], mid[k]], "sand", below)
        m.out([mid[k], mid[j], top], "sand", below)


def frond(m, root, azim, elev, length, droop, width, mat="palm", segs=7):
    """A palm frond arching out from `root`: a thin gull-winged blade (a
    closed diamond section, so it shows from below), widest a fifth of the
    way out. The shader cuts its edges into leaflets."""
    hd = Vector((math.cos(azim), math.sin(azim), 0))
    side = Vector((-hd.y, hd.x, 0))
    p = Vector(root)
    path = [p.copy()]
    for i in range(segs):
        e = elev - droop * (i + 0.5) / segs
        p = p + (hd * math.cos(e) + Z * math.sin(e)) * (length / segs)
        path.append(p.copy())
    secs = []
    for i, p in enumerate(path):
        s = i / segs
        t = (path[min(i + 1, segs)] - path[max(i - 1, 0)]).normalized()
        nrm = t.cross(side).normalized()   # +Z for a level frond, outward hanging down
        w = max(0.012, width * min(1.0, s / 0.22 + 0.15) * (1 - s) ** 0.7)
        dip = w * 0.3
        secs.append((p - side * w - nrm * dip, p + nrm * 0.035, p + side * w - nrm * dip, p - nrm * 0.03, w, s, nrm))
    step = length / segs
    for i in range(segs):
        L0, T0, R0, B0, w0, s0, n0 = secs[i]
        L1, T1, R1, B1, w1, s1, n1 = secs[i + 1]
        v0, v1 = i * step, (i + 1) * step
        nm = (n0 + n1).normalized()
        mid = (path[i] + path[i + 1]) / 2
        uv = {"L": lambda w, v: (-w, v), "T": lambda w, v: (0.0, v), "R": lambda w, v: (w, v), "B": lambda w, v: (0.0, v)}
        u2 = {"L": 1.0, "T": 0.0, "R": 1.0, "B": 0.0}
        for (ka, a0, a1), (kb, b0, b1), side_ in ((("L", L0, L1), ("T", T0, T1), -1), (("T", T0, T1), ("R", R0, R1), -1),
                                                  (("R", R0, R1), ("B", B0, B1), 1), (("B", B0, B1), ("L", L0, L1), 1)):
            q = [a0, b0, b1, a1]
            m.out(q, mat, mid + nm * 0.5 * side_,
                  uv=[uv[ka](w0, v0), uv[kb](w0, v0), uv[kb](w1, v1), uv[ka](w1, v1)],
                  uv2=[(1 - s0, u2[ka]), (1 - s0, u2[kb]), (1 - s1, u2[kb]), (1 - s1, u2[ka])])


def rug_panel(m, c, w, d, hung=False, t=0.03):
    """A rug w x d: a thin slab, both faces carrying UV about its own centre
    scaled to the pattern's 2.6 x 1.7 m (the shader draws the border and the
    lattice from UV 0). Flat on the ground, or hung facing +-X."""
    c = Vector(c)
    u, v, n = (Y, Z, X) if hung else (X, Y, Z)
    k = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    corners = [c + u * (su * w / 2) + v * (sv * d / 2) for su, sv in k]
    uv = [(su * 1.3, sv * 0.85) for su, sv in k]
    for s in (1, -1):
        m.out([p + n * (s * t / 2) for p in corners], "rug", c - n * s, uv=uv)


def pot(m, base, s, rnd, mat="clay"):
    """A water jar: foot, belly, neck, a rolled lip, the mouth turning down
    inside to a floor."""
    lathe(m, [(0, 0.14 * s), (0.12 * s, 0.26 * s), (0.32 * s, 0.3 * s), (0.5 * s, 0.2 * s), (0.58 * s, 0.12 * s),
              (0.62 * s, 0.15 * s), (0.645 * s, 0.13 * s), (0.5 * s, 0.1 * s)], 10, mat, base=base, spin=rnd.uniform(0, 1))


def sack(m, base, rnd):
    b = Vector(base)
    lathe(m, [(-0.02, 0.22), (0.15, 0.28), (0.42, 0.24), (0.55, 0.12), (0.62, 0.05)], 8, "burlap", base=b,
          spin=rnd.uniform(0, 1))
    m.box(b + Z * 0.6, (0.12, 0.12, 0.08), "burlap", rnd.uniform(0, 1))


def parapet(m, cx, cy, W, D, z, mat, t=0.25, h=0.45):
    for x, y, sx, sy in ((cx, cy - D / 2 + t / 2, W, t), (cx, cy + D / 2 - t / 2, W, t),
                         (cx - W / 2 + t / 2, cy, t, D - 2 * t), (cx + W / 2 - t / 2, cy, t, D - 2 * t)):
        m.box((x, y, z + h / 2), (sx, sy, h), mat)


def vigas(m, cx, cy, W, D, z, n):
    """Roof beams whose ends poke out of the front and back walls."""
    for i in range(n):
        x = cx - W / 2 + (i + 0.5) * W / n
        for s in (-1, 1):
            y = cy + s * D / 2
            m.prism((x, y - s * 0.3, z), (x, y + s * 0.42, z), 0.085, 0.085, 6, "wood", capmat="logend")


def window(m, x, y, z, w, h, yaw_axis=X, face=-1):
    """A dark opening proud of a wall facing `face`*Y (or X), a wooden
    lintel over it and a sill, three bars."""
    if yaw_axis is X:
        m.box((x, y + face * 0.03, z), (w, 0.06, h), "shade")
        m.box((x, y + face * 0.06, z + h / 2 + 0.08), (w + 0.4, 0.14, 0.16), "wood", axis=X)
        m.box((x, y + face * 0.06, z - h / 2 - 0.05), (w + 0.2, 0.14, 0.08), "wood", axis=X)
        for k in (-1, 0, 1):
            m.box((x + k * w / 4, y + face * 0.07, z), (0.04, 0.04, h), "wood", axis=Z)
    else:
        m.box((x + face * 0.03, y, z), (0.06, w, h), "shade")
        m.box((x + face * 0.06, y, z + h / 2 + 0.08), (0.14, w + 0.4, 0.16), "wood", axis=Y)
        m.box((x + face * 0.06, y, z - h / 2 - 0.05), (0.14, w + 0.2, 0.08), "wood", axis=Y)
        for k in (-1, 0, 1):
            m.box((x + face * 0.07, y + k * w / 4, z), (0.04, 0.04, h), "wood", axis=Z)


def canopy(m, x0, x1, y_back, z_back, y_front, z_front, mat, t=0.05, flaps=True, rnd=None):
    """A sloped canvas and, along its front, a valance of hanging flaps."""
    sk.slab(m, [(x0, y_front, z_front), (x1, y_front, z_front), (x1, y_back, z_back), (x0, y_back, z_back)],
            t, mat, Vector(((x0 + x1) / 2, (y_back + y_front) / 2, (z_back + z_front) / 2 - 1.0)))
    if flaps:
        n = max(2, int((x1 - x0) / 0.45))
        for i in range(n):
            x = x0 + (i + 0.5) * (x1 - x0) / n
            m.box((x, y_front - 0.02, z_front - 0.17), ((x1 - x0) / n - 0.04, 0.03, 0.3), mat, axis=X)


# ------------------------------------------------------------------- plants
def palm(name, h, lean, n_fr, rnd, flen=3.0):
    """A date palm: a trunk of stepped rings leaning and curving, a boot of
    frond bases, a crown of arching fronds (every third one young and
    upright), dead fronds hanging under it, two bunches of dates."""
    m = Mesh(name)
    segs = max(6, int(h / 0.3))
    bend = lambda t: Vector((lean * h * t * t, 0, h * t))
    for i in range(segs):
        t0, t1 = i / segs, (i + 1) / segs
        r = 0.25 - 0.08 * t0
        m.prism(bend(t0) - Z * (0.3 if i == 0 else 0.0), bend(t1), r * 0.86, r * 1.06, 7, "palmbark", spin=i * 0.5)
    top = bend(1.0)
    lathe(m, [(-0.1, 0.2), (0.12, 0.3), (0.32, 0.14), (0.4, 0.05)], 7, "palmbark", base=top)
    root = top + Z * 0.25
    for i in range(n_fr):
        a = i * math.tau / n_fr + rnd.uniform(-0.25, 0.25)
        young = i % 3 == 0
        frond(m, root, a, rnd.uniform(0.75, 1.05) if young else rnd.uniform(0.25, 0.55),
              flen * rnd.uniform(0.85, 1.1) * (0.8 if young else 1.0),
              rnd.uniform(0.9, 1.3) if young else rnd.uniform(1.5, 2.1), 0.42 * flen / 3.0)
    for i in range(4):
        frond(m, top + Z * 0.05, i * math.tau / 4 + 0.4, -1.15, flen * 0.55, -0.15, 0.2, mat="deadfrond", segs=4)
    for s in (-1, 1):
        c = top + Vector((0.28 * s, 0.22, -0.2))
        for _ in range(14):
            m.box(c + Vector((rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), -rnd.uniform(0, 0.35))),
                  (0.07, 0.07, 0.09), "dates", rnd.uniform(0, 3))
    return m


def dry_shrub(rnd):
    m = Mesh("DryShrub")
    for _ in range(9):   # the dead twigs through it
        a = rnd.uniform(0, math.tau)
        lean = rnd.uniform(0.3, 0.9)
        m.prism((0, 0, -0.05), (math.cos(a) * lean, math.sin(a) * lean, rnd.uniform(0.5, 0.9)), 0.03, 0.012, 4, "wood", caps=False)
    fronds(m, 18, 0.55, 1.1, rnd, base=Vector((0, 0, 0.05)), mat="dry")
    fronds(m, 10, 0.4, 0.9, rnd, base=Vector((0.35, 0.1, 0)), mat="dry")
    return m


def scrub(rnd):
    m = Mesh("ScrubGrass")
    for x, y in ((0, 0), (0.45, 0.2), (-0.3, 0.35)):
        fronds(m, 12, rnd.uniform(0.35, 0.55), 0.8, rnd, base=Vector((x, y, 0)), mat="dry")
    return m


def barrel_cactus(rnd):
    m = Mesh("BarrelCactus")
    for x, y, s in ((0, 0, 1.0), (0.55, 0.25, 0.65), (-0.4, 0.35, 0.5)):
        lathe(m, [(-0.05, 0.28 * s), (0.25 * s, 0.36 * s), (0.55 * s, 0.33 * s), (0.75 * s, 0.2 * s), (0.82 * s, 0.05 * s)],
              14, "cactus", base=(x, y, 0), rib=0.16)
        for k in range(5):
            a = k * math.tau / 5 + rnd.uniform(0, 1)
            m.box((x + math.cos(a) * 0.08 * s, y + math.sin(a) * 0.08 * s, 0.84 * s), (0.07 * s, 0.07 * s, 0.06 * s), "bloom", a)
    return m


def column_cactus(rnd):
    """A saguaro: a ribbed column, two arms turning up from elbows."""
    m = Mesh("ColumnCactus")

    def column(base, h, r):
        prof = [(-0.1, r)] + [(h * t, r * (1.0 + 0.06 * math.sin(t * 5))) for t in (0.3, 0.6, 0.85)] \
            + [(h + r * 0.55, r * 0.72), (h + r * 0.95, r * 0.25)]
        lathe(m, prof, 12, "cactus", base=base, rib=0.18)

    column((0, 0, 0), 3.8, 0.3)
    for s, zb, zt in ((1, 1.5, 2.9), (-1, 2.1, 3.2)):
        elbow = Vector((0.75 * s, 0, zb + 0.12))
        m.prism((0.15 * s, 0, zb), elbow, 0.2, 0.2, 8, "cactus")
        column(elbow - Z * 0.15, zt - zb, 0.2)
    return m


# ------------------------------------------------------------------ rocks
def boulder(name, parts, rnd):
    m = Mesh(name)
    for x, y, rx, ry, rz in parts:
        blob(m, (x, y, rz * 0.1), rx, ry, rz, rnd)
    return m


def mesa(rnd):
    """A butte ~22 m across and 11 m high: five layers stepping in, talus
    boulders and sand ramps at its foot."""
    m = Mesh("Mesa")
    # one outline for every layer, each scaled in from the one below: an
    # outline of its own per layer overhung the layer under it (preview)
    # (and each vertex shrinks by its own running factor, so the outline
    # grows more ragged up the butte without ever overhanging)
    base = outline(11.0, 8.0, rnd, n=14, jag=0.22)
    f = [1.0] * len(base)
    z, k = -1.5, 1.0
    for i, hgt in enumerate((3.0, 2.6, 2.8, 2.2, 1.6)):
        sh = 0.03 + (0.06 if i % 2 else 0.0)
        f = [x * rnd.uniform(0.86, 1.0) for x in f] if i else f
        tier(m, (0, 0, 0), 0, 0, z, z + hgt, rnd, shrink=sh, pts=[p * k * x for p, x in zip(base, f)])
        z += hgt
        k *= (1 - sh) * (0.97 if i < 3 else 0.78)
    for _ in range(9):
        a = rnd.uniform(0, math.tau)
        blob(m, (math.cos(a) * 12.0, math.sin(a) * 8.8, 0.1), rnd.uniform(0.6, 1.4), rnd.uniform(0.5, 1.1), rnd.uniform(0.5, 1.2), rnd)
    for a in (0.3, 2.2, 4.0):
        sand(m, (math.cos(a) * 10.5, math.sin(a) * 7.5, 0), 3.0, 1.4, rnd)
    return m


def ledge(rnd):
    m = Mesh("SandstoneLedge")
    tier(m, (0, 0, 0), 2.8, 1.3, -0.6, 0.9, rnd, n=9, shrink=0.05)
    tier(m, (0.3, 0.15, 0), 2.1, 0.95, 0.9, 1.8, rnd, n=8, shrink=0.12)
    blob(m, (-2.4, -0.9, 0.05), 0.5, 0.45, 0.45, rnd)
    sand(m, (1.0, -1.3, 0), 1.2, 0.35, rnd)
    return m


# ---------------------------------------------------------------- buildings
def adobe_house(rnd):
    """One storey of mud brick on a stone footing: a flat roof behind a
    parapet, viga ends along the front and back, a plank door under a beam
    lintel and a striped awning on poles, barred windows, a ladder to the
    roof, a jar and a rolled rug up there, sand banked at the walls."""
    m = Mesh("AdobeHouse")
    W, D, H = 5.5, 4.5, 3.0
    m.box((0, 0, H / 2 - 0.25), (W, D, H + 0.5), "adobe")
    m.box((0, 0, 0.05), (W + 0.2, D + 0.2, 0.6), "sandstone")
    parapet(m, 0, 0, W, D, H, "adobe")
    vigas(m, 0, 0, W, D, H - 0.35, 6)
    m.box((-1.0, -D / 2 - 0.03, 1.05), (1.0, 0.08, 2.0), "wood", axis=Z)
    m.box((-1.0, -D / 2 - 0.08, 2.15), (1.5, 0.18, 0.18), "wood", axis=X)
    window(m, 1.35, -D / 2, 1.7, 0.7, 0.75)
    window(m, W / 2, 0.4, 1.7, 0.7, 0.75, yaw_axis=Y, face=1)
    canopy(m, -2.2, 0.2, -D / 2, 2.55, -D / 2 - 1.6, 2.05, "cloth", rnd=rnd)
    for x in (-2.1, 0.1):
        m.box((x, -D / 2 - 1.55, 1.0), (0.08, 0.08, 2.05), "wood", axis=Z)
    for s in (-1, 1):   # the ladder against the +X wall
        m.prism((W / 2 + 0.55, -0.9 + s * 0.25, 0), (W / 2 + 0.1, -0.9 + s * 0.25, H + 0.9), 0.04, 0.04, 4, "wood")
    for k in range(7):
        z = 0.35 + k * 0.45
        x = W / 2 + 0.55 - 0.45 * z / (H + 0.9)
        m.box((x, -0.9, z), (0.05, 0.6, 0.05), "wood", axis=Y)
    pot(m, (1.6, 1.2, H), 0.9, rnd)
    m.prism((-1.8, 1.0, H + 0.14), (-0.4, 1.3, H + 0.14), 0.14, 0.14, 8, "rug", capmat="rug")
    for x, y in ((-W / 2, -D / 2), (W / 2, D / 2), (-W / 2, D / 2 - 1.0)):
        sand(m, (x, y, 0), 1.1, 0.45, rnd)
    return m


def adobe_tall(rnd):
    """Two whitewashed storeys: the upper set back with a small dome, a
    stair up the +X side to the lower roof, a blue-striped awning, vigas,
    barred windows on both floors."""
    m = Mesh("AdobeHouseTall")
    W, D, H = 6.0, 5.0, 3.2
    m.box((0, 0, H / 2 - 0.25), (W, D, H + 0.5), "whitewash")
    m.box((0, 0, 0.05), (W + 0.2, D + 0.2, 0.6), "sandstone")
    parapet(m, 0, 0, W, D, H, "whitewash")
    vigas(m, 0, 0, W, D, H - 0.35, 7)
    uW, uD, uH = 3.4, 3.2, 2.6
    ux, uy = -1.1, 0.7
    m.box((ux, uy, H + uH / 2), (uW, uD, uH), "whitewash")
    parapet(m, ux, uy, uW, uD, H + uH, "whitewash", h=0.35)
    lathe(m, [(0, 1.0), (0.35, 0.95), (0.7, 0.75), (0.95, 0.45), (1.08, 0.12), (1.1, 0.01)], 10, "whitewash",
          base=(ux + 0.4, uy + 0.3, H + uH))
    m.box((0.6, -D / 2 - 0.03, 1.05), (1.0, 0.08, 2.0), "wood", axis=Z)
    m.box((0.6, -D / 2 - 0.08, 2.15), (1.5, 0.18, 0.18), "wood", axis=X)
    window(m, -1.6, -D / 2, 1.7, 0.8, 0.8)
    window(m, ux, uy - uD / 2, H + 1.3, 0.8, 0.7)
    canopy(m, -0.4, 1.6, -D / 2, 2.6, -D / 2 - 1.4, 2.15, "cloth2", rnd=rnd)
    # the outside stair, up the +X wall from the front to the roof
    n = 10
    for k in range(n):
        z = (k + 1) * H / n
        m.box((W / 2 + 0.45, -D / 2 + 0.4 + k * 0.42, z / 2), (0.9, 0.44, z), "whitewash")
    for x, y in ((-W / 2, -D / 2), (-W / 2, D / 2), (W / 2 + 0.5, D / 2)):
        sand(m, (x, y, 0), 1.2, 0.5, rnd)
    pot(m, (-2.3, -D / 2 - 0.5, 0), 1.0, rnd)
    return m


def market_stall(rnd):
    """A counter under a striped canopy on four posts, the front's valance of
    flaps, bowls of spice and baskets of dates on the counter, sacks before
    it, a rug hung over the side rail."""
    m = Mesh("MarketStall")
    m.box((0, 0, 0.45), (2.4, 0.9, 0.9), "wood", axis=X)
    m.box((0, -0.05, 0.93), (2.6, 1.0, 0.06), "wood", axis=X)
    for x in (-1.3, 1.3):
        m.box((x, -1.0, 1.1), (0.1, 0.1, 2.2), "wood", axis=Z)
        m.box((x, 0.6, 1.25), (0.1, 0.1, 2.5), "wood", axis=Z)
        m.box((x, -0.2, 1.3), (0.06, 1.6, 0.06), "wood", axis=Y)
    canopy(m, -1.5, 1.5, 0.75, 2.55, -1.15, 2.2, "cloth", rnd=rnd)
    for i, (x, mat) in enumerate(((-0.8, "dates"), (-0.25, "sand"), (0.3, "cactus"), (0.85, "bloom"))):
        lathe(m, [(1.04, 0.18), (1.2, 0.001)], 8, mat, base=(x, -0.1, 0), top=False)
        lathe(m, [(0.96, 0.12), (1.04, 0.2), (1.1, 0.22), (1.05, 0.18)], 8, "clay" if i % 2 else "wood", base=(x, -0.1, 0))
    for x in (-0.6, 0.2, 0.9):
        sack(m, (x, -0.85, 0), rnd)
    rug_panel(m, (1.34, -0.2, 0.95), 1.5, 0.7, hung=True)
    return m


def awning(rnd):
    """A freestanding shade: a striped canvas on four poles, the back ones
    taller, a rug and a jar under it."""
    m = Mesh("Awning")
    for x in (-1.5, 1.5):
        m.box((x, -1.9, 1.05), (0.08, 0.08, 2.1), "wood", axis=Z)
        m.box((x, 0.1, 1.3), (0.08, 0.08, 2.6), "wood", axis=Z)
    canopy(m, -1.7, 1.7, 0.2, 2.6, -2.05, 2.1, "cloth2", rnd=rnd)
    rug_panel(m, (0, -0.9, 0.07), 2.4, 1.6)
    pot(m, (1.0, -0.2, 0), 0.8, rnd)
    return m


def pots(rnd):
    m = Mesh("Pots")
    pot(m, (0, 0, 0), 1.0, rnd)
    pot(m, (0.52, 0.18, 0), 0.7, rnd)
    pot(m, (-0.48, 0.3, 0), 1.3, rnd)
    pot(m, (0.2, -0.45, 0), 0.55, rnd)
    return m


def urn(rnd):
    """A tall amphora on a stone block, two handles, painted bands."""
    m = Mesh("Urn")
    m.box((0, 0, 0.1), (0.7, 0.7, 0.3), "sandstone")
    lathe(m, [(0.25, 0.12), (0.35, 0.2), (0.75, 0.34), (1.1, 0.3), (1.3, 0.15), (1.45, 0.1), (1.53, 0.14), (1.55, 0.12),
              (1.4, 0.08)], 12, "clay")
    for s in (-1, 1):
        m.prism((s * 0.27, 0, 1.12), (s * 0.24, 0, 1.4), 0.03, 0.03, 4, "clay")
        m.prism((s * 0.24, 0, 1.4), (s * 0.12, 0, 1.44), 0.03, 0.03, 4, "clay")
    return m


def crates(rnd):
    m = Mesh("Crates")
    for c, s, yaw in (((0, 0, 0.35), 0.7, 0.1), ((0.75, 0.1, 0.3), 0.6, -0.2), ((0.1, 0.05, 1.0), 0.6, 0.4)):
        m.box(c, (s, s, s), "wood", yaw, axis=X)
        for dz in (-s / 2 + 0.04, s / 2 - 0.04):
            m.box(Vector(c) + Z * dz, (s + 0.02, s + 0.02, 0.06), "wood", yaw, axis=X)
    for x, y in ((-0.7, -0.2), (-0.6, 0.45)):
        sack(m, (x, y, 0), rnd)
    return m


def rug(rnd):
    m = Mesh("Rug")
    rug_panel(m, (0, 0, 0.07), 2.6, 1.7)
    m.prism((-1.2, 1.3, 0.12), (1.2, 1.3, 0.12), 0.12, 0.12, 8, "rug", capmat="rug")
    return m


def bones(rnd):
    """A beast's skeleton half under the sand: spine, ribs arching to the
    ground, the skull, a leg bone."""
    m = Mesh("Bones")
    for i in range(10):
        x = -1.2 + i * 0.26
        m.box((x, 0, 0.55 - abs(x) * 0.12), (0.14, 0.12, 0.12), "bone", rnd.uniform(-0.2, 0.2))
    for i in range(7):
        x = -0.7 + i * 0.22
        z0 = 0.55 - abs(x) * 0.12
        for s in (-1, 1):
            pts = [Vector((x, 0, z0))]
            for k in range(1, 5):
                a = k / 4 * 2.0
                pts.append(Vector((x + k * 0.03, s * math.sin(a) * 0.55, z0 + (math.cos(a) - 1) * 0.3)))
            for a, b in zip(pts, pts[1:]):
                m.prism(a, b, 0.035, 0.03, 4, "bone")
    m.box((1.55, 0.1, 0.25), (0.45, 0.3, 0.3), "bone", 0.3)
    m.box((1.88, 0.22, 0.18), (0.4, 0.2, 0.18), "bone", 0.3)
    for s in (-1, 1):
        m.prism((1.5, 0.1 + s * 0.14, 0.38), (1.3, 0.1 + s * 0.4, 0.62), 0.04, 0.015, 4, "bone")
    m.prism((-0.5, -0.9, 0.05), (0.4, -1.2, 0.05), 0.05, 0.05, 5, "bone")
    sand(m, (-0.5, -0.45, 0), 1.0, 0.3, rnd)
    return m


def well(rnd):
    """A ring of cut blocks round dark water, two posts and a beam, a rope
    down to a bucket."""
    m = Mesh("Well")
    n, R = 10, 0.95
    for k in range(n):
        a = k * math.tau / n
        m.box((math.cos(a) * R, math.sin(a) * R, 0.3), (0.34, 0.62, 0.9), "sandstone", a)
    for k in range(10):
        a0, a1 = k * math.tau / 10, (k + 1) * math.tau / 10
        m.out([(0, 0, 0.6), (math.cos(a0) * 0.8, math.sin(a0) * 0.8, 0.6), (math.cos(a1) * 0.8, math.sin(a1) * 0.8, 0.6)],
              "shade", (0, 0, 0))
    for x in (-1.0, 1.0):
        m.box((x, 0, 1.3), (0.14, 0.14, 2.2), "wood", axis=Z)
    m.prism((-1.15, 0, 2.35), (1.15, 0, 2.35), 0.07, 0.07, 6, "wood", capmat="logend")
    m.prism((0.1, 0, 2.3), (0.1, 0, 1.3), 0.012, 0.012, 4, "burlap", caps=False)
    lathe(m, [(0, 0.1), (0.25, 0.13), (0.2, 0.11)], 8, "wood", base=(0.1, 0, 1.05))
    sand(m, (1.3, 0.6, 0), 0.8, 0.3, rnd)
    return m


def arch(rnd):
    """A sandstone gate half fallen: block pillars, the voussoirs, a carved
    keystone, rubble and sand at the feet."""
    m = Mesh("SandstoneArch")
    R, zc = 1.9, 3.2
    for x in (-R, R):
        z = -0.3
        while z < zc - 0.05:
            bh = min(rnd.uniform(0.45, 0.6), zc - z)
            m.box((x + rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), z + bh / 2), (1.0, 1.0, bh), "sandstone",
                  rnd.uniform(-0.04, 0.04))
            z += bh
    for k in range(11):
        a = math.pi * (k + 0.5) / 11
        c = Vector((-math.cos(a) * R, 0, zc + math.sin(a) * R * 0.95))
        m.box(c, (0.62, 1.0, 0.5), "glyph" if k == 5 else "sandstone", tilt=(-(math.pi / 2 - a), "Y"))
    m.box((-0.9, 0, zc + R + 0.5), (2.6, 1.1, 0.5), "sandstone", axis=X)
    for _ in range(6):
        m.box((rnd.uniform(-3.0, 3.0), rnd.uniform(-1.3, 1.3), 0.15), (rnd.uniform(0.3, 0.7), rnd.uniform(0.3, 0.5), 0.34),
              "sandstone", rnd.uniform(0, 3))
    m.box((2.6, -0.9, 0.22), (1.3, 1.0, 0.5), "sandstone", 0.5)   # the fallen half of the lintel
    sand(m, (-R, 0.4, 0), 1.0, 0.45, rnd)
    sand(m, (R, -0.5, 0), 0.9, 0.35, rnd)
    return m


def ruined_column(rnd):
    m = Mesh("RuinedColumn")
    m.box((0, 0, 0.05), (1.3, 1.3, 0.5), "sandstone")
    m.box((0, 0, 0.38), (1.1, 1.1, 0.16), "sandstone")
    z = 0.46
    for i, h in enumerate((0.9, 0.85, 0.8, 0.55)):
        lathe(m, [(0, 0.42), (h, 0.4)], 16, "drum", base=(rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), z),
              rib=0.07, spin=i * 0.1)
        z += h
    m.prism((1.0, -0.6, 0.4), (1.85, -0.25, 0.4), 0.4, 0.4, 16, "drum")
    m.box((-1.3, 0.8, 0.2), (1.1, 1.1, 0.4), "sandstone", 0.4)
    sand(m, (0.6, 0.5, 0), 1.0, 0.3, rnd)
    return m


def obelisk(rnd):
    m = Mesh("Obelisk")
    m.box((0, 0, 0.1), (2.0, 2.0, 0.8), "sandstone")
    m.box((0, 0, 0.62), (1.6, 1.6, 0.25), "sandstone")
    frustum(m, (0, 0, 0), (1.1, 1.1), (0.72, 0.72), 0.745, 7.5, "glyph")
    t = [Vector((sx * 0.36, sy * 0.36, 7.5)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    apex = Vector((0, 0, 8.2))
    for k in range(4):
        m.out([t[k], t[(k + 1) % 4], apex], "gold", (0, 0, 7.6))
    sand(m, (0.9, 0.8, 0), 0.9, 0.35, rnd)
    return m


def brazier(rnd):
    m = Mesh("Brazier")
    m.box((0, 0, -0.05), (1.1, 1.1, 0.2), "sandstone")
    for k in range(3):
        a = k * math.tau / 3
        m.prism((math.cos(a) * 0.45, math.sin(a) * 0.45, 0.05), (math.cos(a) * 0.15, math.sin(a) * 0.15, 0.95), 0.035, 0.03, 4, "iron")
    lathe(m, [(0.85, 0.1), (0.95, 0.38), (1.12, 0.45), (1.1, 0.4), (1.0, 0.3)], 10, "iron")
    for k in range(5):
        a = k * math.tau / 5 + rnd.uniform(0, 0.5)
        r = 0.15 if k else 0.0
        h = rnd.uniform(0.35, 0.65) * (1.4 if k == 0 else 1.0)
        lathe(m, [(0, 0.14), (h * 0.4, 0.12), (h, 0.01)], 5, "fire", base=(math.cos(a) * r, math.sin(a) * r, 1.0),
              spin=rnd.uniform(0, 1))
    return m


def statue(m, x, y, z, s, rnd):
    """A seated guardian, blocky, facing -Y."""
    def b(c, size, mat="sandstone"):
        m.box((x + c[0] * s, y + c[1] * s, z + c[2] * s), tuple(v * s for v in size), mat)
    b((0, 0, 0.4), (1.6, 1.9, 0.8))
    b((0, 0.2, 1.9), (1.2, 1.2, 2.2))
    b((0, -0.55, 1.1), (1.2, 0.9, 0.6))
    b((-0.35, -0.95, 0.55), (0.35, 0.3, 1.1))
    b((0.35, -0.95, 0.55), (0.35, 0.3, 1.1))
    b((0, 0.05, 3.3), (0.62, 0.62, 0.75))
    b((0, 0.2, 3.3), (0.9, 0.7, 0.9), "glyph")
    b((0, 0.05, 3.8), (0.4, 0.4, 0.3), "gold")


def temple(rnd):
    """The Ashdunes' temple: three stepped terraces and a central stair, a
    battered pylon either side of a tall dark gate with a gold lintel, two
    seated guardians before it, a hall behind ringed with columns under an
    architrave. Everything runs 3 m below the foot so it can stand on a
    slope. ~34 x 28 x 16 m."""
    m = Mesh("Temple")
    for z0, z1, w, d in ((-3.0, 0.9, 34, 28), (0.9, 1.8, 30, 24), (1.8, 2.7, 26, 20)):
        m.box((0, 0, (z0 + z1) / 2), (w, d, z1 - z0), "sandstone")
    for i in range(3):   # the stair: a flight of three before each terrace's face
        yf, zb = -14.0 + 2.0 * i, 0.9 * i - (0.3 if i == 0 else 0.05)
        for j in range(3):
            top = 0.9 * i + 0.3 * (j + 1)
            m.box((0, yf - 1.35 + (j + 0.5) * 0.45, (top + zb) / 2), (8.0 - 0.6 * i, 0.46, top - zb), "sandstone", axis=X)
        for s in (-1, 1):   # the flight's cheek walls
            m.box((s * (4.3 - 0.3 * i), yf - 0.67, 0.9 * i + 0.5 - 0.05), (0.5, 1.4, 1.1), "sandstone")
    zt = 2.7
    for s in (-1, 1):
        frustum(m, (s * 6.4, -5.5, 0), (7.6, 5.0), (6.2, 4.0), zt, 15.0, "glyph")
        m.box((s * 6.4, -5.5, 15.4), (6.8, 4.6, 0.8), "sandstone")
    m.box((0, -5.5, zt + 4.5), (5.4, 4.6, 9.0), "sandstone")
    m.box((0, -7.85, zt + 3.2), (3.0, 0.1, 6.4), "shade")
    m.box((0, -7.9, zt + 6.9), (3.9, 0.2, 0.7), "gold", axis=X)
    m.box((0, -5.5, zt + 9.3), (5.8, 4.8, 0.6), "sandstone")
    for s in (-1, 1):
        statue(m, s * 5.2, -9.0, zt, 1.35, rnd)
    # the hall and its colonnade
    m.box((0, 4.0, zt + 4.5), (16.0, 14.0, 9.0), "sandstone")
    m.box((0, 4.0, zt + 9.3), (16.8, 14.8, 0.6), "sandstone")
    for s in (-1, 1):
        for k in range(5):
            y = -2.0 + k * 3.0
            x = s * 10.4
            m.box((x, y, zt + 0.25), (1.3, 1.3, 0.5), "sandstone")
            lathe(m, [(0, 0.5), (6.6, 0.44)], 12, "drum", base=(x, y, zt + 0.5), rib=0.08)
            m.box((x, y, zt + 7.4), (1.4, 1.4, 0.6), "sandstone")
        m.box((s * 10.4, 4.0, zt + 8.1), (1.5, 14.0, 0.8), "glyph", axis=Y)
    sand(m, (-15.5, -8.0, 0.9), 3.0, 1.2, rnd)
    sand(m, (15.0, 6.0, 0.9), 3.5, 1.4, rnd)
    sand(m, (-9.0, -14.6, 0), 2.2, 0.7, rnd)
    return m


def sand_pile(rnd):
    m = Mesh("SandPile")
    sand(m, (0, 0, 0), 1.6, 0.6, rnd)
    sand(m, (1.3, 0.8, 0), 1.0, 0.35, rnd)
    return m


# ------------------------------------------------------------------ output
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rnd = random.Random(2468)
    rows = {
        "plants": [palm("DatePalmTall", 8.5, 0.12, 16, rnd, 3.3), palm("DatePalm", 6.5, 0.06, 14, rnd, 3.0),
                   palm("DatePalmLean", 5.2, 0.35, 12, rnd, 2.7), dry_shrub(rnd), scrub(rnd), barrel_cactus(rnd),
                   column_cactus(rnd)],
        "rocks": [boulder("BoulderSmall", [(0, 0, 0.6, 0.5, 0.55)], rnd),
                  boulder("BoulderMedium", [(0, 0, 1.1, 0.9, 1.0), (0.9, 0.3, 0.6, 0.55, 0.55)], rnd),
                  boulder("BoulderLarge", [(0, 0, 1.8, 1.4, 1.7), (1.5, -0.4, 0.9, 0.8, 0.9), (-1.2, 0.6, 0.8, 0.7, 0.6)], rnd),
                  ledge(rnd), sand_pile(rnd), mesa(rnd)],
        "props": [market_stall(rnd), awning(rnd), pots(rnd), urn(rnd), crates(rnd), rug(rnd), bones(rnd), well(rnd),
                  brazier(rnd)],
        "build": [adobe_house(rnd), adobe_tall(rnd), arch(rnd), ruined_column(rnd), obelisk(rnd)],
        "temple": [temple(rnd)],
    }
    built = {k: [m.build() for m in v] for k, v in rows.items()}
    obs = [o for row in built.values() for o in row]
    for o in obs:
        print(f"  {o.name:<15} tris {sum(len(p.vertices) - 2 for p in o.data.polygons):5d}  "
              f"{o.dimensions.x:.1f} x {o.dimensions.y:.1f} x {o.dimensions.z:.1f} m")
    os.makedirs(OUT, exist_ok=True)
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "desertkit.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    print("desertkit: exported", len(obs))
    sk.preview(built)


if __name__ == "__main__":
    main()
