"""The building kit: real silhouettes, pixel-textured surfaces, cheap shadows.

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background --factory-startup \\
        --python D:/assests/scripts/forge/kit/kit.py -- [cottage townhouse retaining steps]

Every piece is built from convex boxes and extruded polygons written straight
into one bmesh, so a building is ONE object with one material slot per surface
-- one draw call per surface, not per plank. Surfaces are named exactly as
`scripts/forge/tex/texgen.py` names them (`brick`, `thatch`...); the game swaps
in the shared `TexLib` material by that name. Windows use the village's glow
names (`M_Window_Warm`, `M_Window_Dim`) so `Village.Glow` lights them.

UVs are projected per face in WORLD metres at the sprite's density, 52
texels/m (hd2d audit Law 2): u runs horizontally across the face and v up it,
so brick courses stay level on a wall and shingle rows run up a roof slope. A
part built with a grain `axis` (every beam) maps v along that axis instead, so
timber grain follows the beam. One UV unit is one repeat of the texture.

Detail is modelled, not capped (user, 2026-09-23: "don't hold back"): beams
stand proud of the plaster, windows are recessed with frames, shutters and
sills, roofs are slabs with thickness, overhangs, barge boards and rafter
tails. The GPU is protected differently: each building also exports a
`SHADOW_` proxy of a few dozen triangles that casts the shadows, while the
visual mesh casts none -- the shadow cascades are the measured cost
(memory.md). `COL_` is the collision hull `Village.Solidify` already handles.

Front is -Y (the GLB's +Z after the Y-up export, which `Village.Place`
expects). Ground is z = 0; every building carries a plinth to z = -0.5 so a
slope never shows a gap under it.
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "game", "assets", "models", "kit")
TEX = json.load(open(os.path.join(ROOT, "game", "assets", "tex", "manifest.json")))
TPM = TEX["texels_per_m"]
PX = {k: v["px"] for k, v in TEX["surfaces"].items()}

# Preview colours only -- in the game every textured name is replaced by its
# TexLib material, and the glow names by Village.Glow.
FLAT = {
    "M_Window_Warm": (1.0, 0.62, 0.30), "M_Window_Dim": (0.55, 0.36, 0.22), "M_Lamp": (1.0, 0.62, 0.30),
    "iron": (0.10, 0.10, 0.11), "glass": (0.10, 0.12, 0.16), "SHADOW": (0.2, 0.2, 0.2),
}
Z = Vector((0, 0, 1))


class Mesh:
    """Accumulates convex parts into one bmesh with per-face material and UV."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.mats = []
        # applied to every point (and grain axis) as it is written: lets a
        # part be built in a convenient frame, e.g. a roof rotated 90 deg
        self.xf = Matrix.Identity(4)

    def mat(self, name):
        if name not in self.mats:
            self.mats.append(name)
        return self.mats.index(name)

    def face(self, pts, mat, centre, axis=None):
        pts = [self.xf @ Vector(p) for p in pts]
        centre = self.xf @ Vector(centre)
        if axis is not None:
            axis = (self.xf.to_3x3() @ Vector(axis)).normalized()
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            return
        n.normalize()
        fc = sum(pts, Vector()) / len(pts)
        if n.dot(fc - centre) < 0:            # convex part: outward from its centre
            pts.reverse()
            n = -n
        u, v = _frame(n, axis)
        pw, ph = PX.get(mat, (512, 512))
        f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        f.material_index = self.mat(mat)
        for loop in f.loops:
            p = loop.vert.co
            loop[self.uv].uv = (p.dot(u) * TPM / pw, p.dot(v) * TPM / ph)

    def box(self, m, size, mat, axis=None, faces=None):
        """Box of `size` under transform `m` (centre + rotation). `faces` maps
        '+z', '-y'... to a material for that face; the rest take `mat`."""
        hx, hy, hz = (s / 2 for s in size)
        c = [m @ Vector((sx * hx, sy * hy, sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        idx = {"+x": (4, 6, 7, 5), "-x": (0, 1, 3, 2), "+y": (2, 3, 7, 6),
               "-y": (0, 4, 5, 1), "+z": (1, 5, 7, 3), "-z": (0, 2, 6, 4)}
        centre = m @ Vector((0, 0, 0))
        wax = None if axis is None else (m.to_3x3() @ Vector(axis)).normalized()
        for key, q in idx.items():
            self.face([c[i] for i in q], (faces or {}).get(key, mat), centre, wax)

    def cbox(self, m, size, mat, r, axis=None, faces=None):
        """`box` with every edge chamfered by `r` (2026-09-29, "too brutalist"):
        six inset faces, twelve 45-degree strips and eight corner triangles. A
        strip catches the light as a soft line where a knife edge was. The
        strips and corners take the side faces' material. 44 triangles, not 12,
        so it is for silhouette pieces (plinths, chimneys), not every beam."""
        hx, hy, hz = (s / 2 for s in size)
        r = min(r, hx * 0.45, hy * 0.45, hz * 0.45)
        centre = m @ Vector((0, 0, 0))
        wax = None if axis is None else (m.to_3x3() @ Vector(axis)).normalized()
        F = faces or {}
        def P(x, y, z):
            return m @ Vector((x, y, z))
        def side(key):
            return F.get(key, mat)
        # the six faces, inset by r on every side
        for ax, (a, b, c) in {"x": (0, 1, 2), "y": (1, 0, 2), "z": (2, 0, 1)}.items():
            h = (hx, hy, hz)
            for s in (-1, 1):
                pts = []
                for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    p = [0.0, 0.0, 0.0]
                    p[a] = s * h[a]
                    p[b] = u * (h[b] - r)
                    p[c] = v * (h[c] - r)
                    pts.append(P(*p))
                self.face(pts, F.get(("+" if s > 0 else "-") + ax, mat), centre, wax)
        # the twelve edge strips
        for (a, b), c in (((0, 1), 2), ((0, 2), 1), ((1, 2), 0)):
            h = (hx, hy, hz)
            for sa in (-1, 1):
                for sb in (-1, 1):
                    pts = []
                    for sc in (-1, 1):
                        for which in (a, b):
                            p = [0.0, 0.0, 0.0]
                            p[a] = sa * (h[a] - (0 if which == a else r))
                            p[b] = sb * (h[b] - (0 if which == b else r))
                            p[c] = sc * (h[c] - r)
                            pts.append(p)
                    q = [pts[0], pts[1], pts[3], pts[2]]
                    key = ("+" if sa > 0 else "-") + "xyz"[a] if a != 2 else ("+" if sb > 0 else "-") + "xyz"[b]
                    self.face([P(*p) for p in q], side(key), centre, wax)
        # the eight corners
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    pts = [P(sx * hx, sy * (hy - r), sz * (hz - r)), P(sx * (hx - r), sy * hy, sz * (hz - r)),
                           P(sx * (hx - r), sy * (hy - r), sz * hz)]
                    self.face(pts, side(("+" if sx > 0 else "-") + "x"), centre, wax)

    def prism(self, o, u, v, poly, depth, mat, back=None):
        """Extrude a convex polygon given in (u, v) metres on the plane at `o`
        spanned by `u`, `v`, `depth` metres along -(u x v)."""
        n = u.cross(v).normalized()
        front = [o + u * a + v * b for a, b in poly]
        rear = [p - n * depth for p in front]
        centre = sum(front + rear, Vector()) / (2 * len(front))
        self.face(front, mat, centre)
        self.face(list(reversed(rear)), back or mat, centre)
        for i in range(len(front)):
            j = (i + 1) % len(front)
            self.face([front[i], front[j], rear[j], rear[i]], back or mat, centre)

    def build(self):
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.collection.objects.link(ob)
        for name in self.mats:
            ob.data.materials.append(_material(name))
        return ob


def _frame(n, axis):
    if axis is not None:
        v = axis - n * axis.dot(n)
        if v.length > 1e-3:
            v.normalize()
            return v.cross(n).normalized(), v
    if abs(n.z) > 0.92:
        return Vector((1, 0, 0)), Vector((0, 1 if n.z > 0 else -1, 0))
    u = Z.cross(n).normalized()
    return u, n.cross(u).normalized()


def _material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    col = FLAT.get(name, (0.5, 0.45, 0.4))
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    return m


def T(x, y, z, rz=0.0, rx=0.0, ry=0.0):
    """Translation then rotation, degrees, Blender XYZ order."""
    return (Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(rz), 4, "Z")
            @ Matrix.Rotation(math.radians(ry), 4, "Y") @ Matrix.Rotation(math.radians(rx), 4, "X"))


# ---------------------------------------------------------------------------
# parts
# ---------------------------------------------------------------------------

BEAM = 0.18      # timber section
PROUD = 0.05     # how far a beam stands out of the plaster
WALL_T = 0.30


def beam(me, a, b, width=BEAM, depth=BEAM, mat="timber", up=None):
    """A beam from point a to point b, its section `width` x `depth`. `up`
    orients the section (defaults to world Z, or X for vertical beams)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    ln = d.length
    x = d.normalized()
    up = Vector(up) if up is not None else (Vector((1, 0, 0)) if abs(x.z) > 0.95 else Z)
    y = up.cross(x).normalized()
    z = x.cross(y).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = (a + b) / 2
    me.box(m, (ln, depth, width), mat, axis=(1, 0, 0))


def wall(me, o, along, length, z0, z1, openings, infill, frame=True, braces=(), rails=(),
         thick=WALL_T):
    """A straight wall whose OUTER face starts at `o` and runs `length` along
    the horizontal unit vector `along`. Openings are (u0, u1, v0, v1, kind)
    in metres from the wall's start and from z0. The infill is tiled as
    rectangles around the openings, so each opening's reveals are real faces.
    A timber frame (corner posts, sole plate, top plate, posts at every
    opening, `rails` at given heights, diagonal `braces` in given bays) stands
    PROUD of it."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()          # outward normal
    h = z1 - z0
    cuts = sorted({0.0, length} | {o_[0] for o_ in openings} | {o_[1] for o_ in openings})

    def rect(u0, u1, v0, v1, mat, inset=0.0):
        if u1 - u0 < 1e-3 or v1 - v0 < 1e-3:
            return
        c = o + along * ((u0 + u1) / 2) + Z * (z0 + (v0 + v1) / 2) - out * (thick / 2 + inset)
        m = Matrix((along, -out, Z)).transposed().to_4x4()
        m.translation = c
        me.box(m, (u1 - u0, thick, v1 - v0), mat)

    for u0, u1 in zip(cuts, cuts[1:]):
        mid = (u0 + u1) / 2
        hole = [op for op in openings if op[0] <= mid <= op[1]]
        if not hole:
            rect(u0, u1, 0, h, infill)
            continue
        _, _, v0, v1, kind = hole[0]
        rect(u0, u1, 0, v0, infill)
        rect(u0, u1, v1, h, infill)
        opening(me, o, along, out, u0, u1, z0 + v0, z0 + v1, kind, thick)

    if not frame:
        return
    fo = o + out * PROUD
    posts = sorted({0.0 + BEAM / 2, length - BEAM / 2}
                   | {op[0] - BEAM / 2 for op in openings} | {op[1] + BEAM / 2 for op in openings})
    for p in posts:
        base = fo + along * p - out * (BEAM / 2)
        beam(me, base + Z * z0, base + Z * z1)
    for zz in (z0 + BEAM / 2, z1 - BEAM / 2) + tuple(z0 + r for r in rails):
        a = fo + along * 0.0 - out * (BEAM / 2) + Z * zz
        beam(me, a, a + along * length)
    for i, (u0, u1, up) in enumerate(braces):
        a = fo - out * (BEAM / 2) + along * u0 + Z * (z0 + (0 if up else h))
        b = fo - out * (BEAM / 2) + along * u1 + Z * (z0 + (h if up else 0))
        beam(me, a, b, up=out)


def opening(me, o, along, out, u0, u1, z0, z1, kind, thick):
    """What fills an opening: a recessed window with frame, mullions, sill
    and shutters, or a recessed plank door with a frame, hinges and a step."""
    rec = 0.12
    w = u1 - u0
    mid = o + along * ((u0 + u1) / 2)
    basis = Matrix((along, -out, Z)).transposed()
    if kind.startswith("window"):
        # Lit panes use the village's DIM glow: at the kit's pane size the
        # warm one bloomed each window into a white ball (measured: window
        # bloom was over half the light in a close shot). Unlit panes are
        # dark glass.
        # "window_bare": a lit window whose awning the caller builds (the city
        # kit's cloth awnings, 2026-09-30); every other kind is unchanged
        glass = "M_Window_Dim" if kind in ("window", "window_bare") else "glass"
        m = basis.to_4x4()
        m.translation = mid + Z * ((z0 + z1) / 2) - out * (rec + 0.02)
        me.box(m, (w, 0.04, z1 - z0), glass)
        # frame, mullion and transom, set just inside the reveal
        f = mid - out * (rec - 0.03)
        beam(me, f + along * (-w / 2 + 0.05) + Z * z0, f + along * (-w / 2 + 0.05) + Z * z1, 0.1, 0.1)
        beam(me, f + along * (w / 2 - 0.05) + Z * z0, f + along * (w / 2 - 0.05) + Z * z1, 0.1, 0.1)
        beam(me, f + Z * z0, f + Z * z1, 0.06, 0.06)
        beam(me, f + along * (-w / 2) + Z * ((z0 + z1) / 2 + 0.1), f + along * (w / 2) + Z * ((z0 + z1) / 2 + 0.1),
             0.06, 0.06)
        # leaded lattice: thin iron bars over the glass, so a lit window reads
        # as small panes rather than one glowing slab
        g = mid - out * (rec - 0.005)
        for k in range(1, 4):
            beam(me, g + along * (-w / 2 + k * w / 4) + Z * z0, g + along * (-w / 2 + k * w / 4) + Z * z1,
                 0.025, 0.02, mat="iron")
        for k in range(1, 4):
            zz = z0 + k * (z1 - z0) / 4
            beam(me, g + along * (-w / 2) + Z * zz, g + along * (w / 2) + Z * zz, 0.025, 0.02, mat="iron")
        # stone sill, proud of the wall
        m = basis.to_4x4()
        m.translation = mid + Z * (z0 - 0.05) + out * 0.06
        me.box(m, (w + 0.24, 0.26, 0.10), "fieldstone")
        if w > 1.4 and kind != "window_bare":
            # a shop window takes an awning, not shutters: shutters half its
            # width would hang past the corner of a narrow front
            m = basis.to_4x4() @ Matrix.Rotation(math.radians(-25), 4, "X")
            m.translation = mid + Z * (z1 + 0.28) + out * 0.42
            me.box(m, (w + 0.3, 0.95, 0.06), "planks", faces={"+z": "shingle"})
            for side in (-1, 1):
                beam(me, mid + along * (side * (w / 2 + 0.1)) + Z * (z1 - 0.25),
                     mid + along * (side * (w / 2 + 0.1)) + Z * (z1 + 0.18) + out * 0.85, 0.08, 0.08)
            return
        if kind == "window_bare":
            return
        # shutters, open against the wall either side
        for side in (-1, 1):
            m = basis.to_4x4()
            m.translation = mid + along * (side * (w / 2 + w / 4 + 0.04)) + Z * ((z0 + z1) / 2) + out * 0.03
            me.box(m, (w / 2, 0.05, z1 - z0 - 0.04), "planks", axis=(0, 0, 1))
    elif kind == "door":
        m = basis.to_4x4()
        m.translation = mid + Z * ((z0 + z1) / 2) - out * (rec + 0.03)
        me.box(m, (w, 0.06, z1 - z0), "planks", axis=(0, 0, 1))
        f = mid - out * (rec - 0.04)
        beam(me, f + along * (-w / 2 + 0.06) + Z * z0, f + along * (-w / 2 + 0.06) + Z * z1, 0.12, 0.12)
        beam(me, f + along * (w / 2 - 0.06) + Z * z0, f + along * (w / 2 - 0.06) + Z * z1, 0.12, 0.12)
        for hz in (z0 + 0.4, z1 - 0.4):              # iron strap hinges
            m = basis.to_4x4()
            m.translation = mid + along * (-w / 4) + Z * hz - out * (rec - 0.01)
            me.box(m, (w / 2, 0.02, 0.06), "iron")
        m = basis.to_4x4()                            # the step
        m.translation = mid + Z * (z0 - 0.12) + out * 0.35
        me.box(m, (w + 0.4, 0.7, 0.24), "fieldstone")


def gable(me, o, along, span, z_eave, rise, infill, frame=True, window=None):
    """The triangle over an end wall: plaster infill and a truss of beams
    (rakes, king post, collar). Its outer face starts at `o`."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    poly = [(0, 0), (span, 0), (span / 2, rise)]
    me.prism(o + Z * z_eave, along, Z, poly, WALL_T, infill)
    if window:
        w, h = window
        m = Matrix((along, -out, Z)).transposed().to_4x4()
        m.translation = o + along * (span / 2) + Z * (z_eave + rise * 0.38) - out * 0.14
        me.box(m, (w, 0.04, h), "M_Window_Dim")
    if not frame:
        return
    fo = o + out * PROUD - out * (BEAM / 2)
    apex = fo + along * (span / 2) + Z * (z_eave + rise)
    beam(me, fo + Z * z_eave, apex, up=out)
    beam(me, fo + along * span + Z * z_eave, apex, up=out)
    beam(me, fo + along * (span / 2) + Z * z_eave, apex - Z * 0.1)
    cz = z_eave + rise * 0.45
    half = (span / 2) * (1 - 0.45)
    beam(me, fo + along * (span / 2 - half) + Z * cz, fo + along * (span / 2 + half) + Z * cz)


# Eaves 0.60 / verges 0.45 (were 0.45 / 0.35; 2026-09-29, "too brutalist"): a
# deeper roof shades the wall under it and reads as sheltering, not boxed.
def roof(me, x0, x1, y0, y1, z_eave, pitch, cover, over_eave=0.60, over_gable=0.45,
         thick=0.18, ridge_axis="x"):
    """A gable roof over the rectangle, ridge along `ridge_axis`: two slabs
    with thickness, the covering on top and planks below, a ridge beam,
    barge boards on the gable edges and rafter tails under the eaves. A
    ridge along y is the same roof built along x under a 90 deg rotation
    (local a = world y, local b = -world x) -- never a mirror, which flips
    the winding and the slope."""
    if ridge_axis == "y":
        keep = me.xf
        me.xf = keep @ Matrix.Rotation(math.radians(90), 4, "Z")
        z = roof(me, y0, y1, -x1, -x0, z_eave, pitch, cover, over_eave, over_gable, thick, "x")
        me.xf = keep
        return z
    a0, a1, b0, b1 = x0 - over_gable, x1 + over_gable, y0, y1
    half = (b1 - b0) / 2
    tp = math.tan(math.radians(pitch))
    rise = half * tp
    slope = (half + over_eave) / math.cos(math.radians(pitch))
    mid_b = (b0 + b1) / 2
    ridge_z = z_eave + rise
    for side in (-1, 1):
        ang = math.radians(pitch) * side
        dn = Vector((0, side * math.cos(math.radians(pitch)), -math.sin(math.radians(pitch))))
        nrm = Vector((0, side * math.sin(math.radians(pitch)), math.cos(math.radians(pitch))))
        c = Vector(((a0 + a1) / 2, mid_b, ridge_z)) + dn * (slope / 2) + nrm * (thick / 2)
        me.box(Matrix.Translation(c) @ Matrix.Rotation(-ang, 4, "X"), (a1 - a0, slope, thick),
               "planks", faces={"+z": cover})
        # rafter tails: under the slab, inside the overhang, every 0.6 m
        n = int((a1 - a0) / 0.6)
        for i in range(n + 1):
            a = a0 + 0.15 + i * ((a1 - a0 - 0.3) / max(n, 1))
            p = Vector((a, mid_b + side * (half + 0.02), z_eave - 0.1))
            q = Vector((a, mid_b + side * (half + over_eave - 0.06), z_eave - 0.1 - (over_eave - 0.08) * tp))
            beam(me, p, q, 0.12, 0.10)
    # barge boards along both gable edges, and the ridge beam
    for e in (a0 + 0.035, a1 - 0.035):
        for side in (-1, 1):
            top = Vector((e, mid_b, ridge_z + thick * 0.7))
            low = Vector((e, mid_b + side * (half + over_eave), z_eave - over_eave * tp + thick * 0.7))
            beam(me, top, low, 0.26, 0.07, up=(1, 0, 0))
    beam(me, Vector((a0, mid_b, ridge_z + thick)), Vector((a1, mid_b, ridge_z + thick)), 0.22, 0.22)
    return ridge_z


def chimney(me, x, y, z_top, w=0.8, d=0.8, mat="fieldstone", top="brick"):
    me.cbox(T(x, y, (z_top - 1.2 - 0.5) / 2 + -0.5 / 2 + 0.25), (w, d, z_top - 1.2 + 0.5), mat, 0.05)
    me.cbox(T(x, y, z_top - 0.6), (w - 0.06, d - 0.06, 1.2), top, 0.05)
    me.cbox(T(x, y, z_top + 0.05), (w + 0.16, d + 0.16, 0.12), "slate", 0.03)
    for dx in (-0.18, 0.18):
        me.box(T(x + dx, y, z_top + 0.28), (0.18, 0.18, 0.34), "brick")


def plinth(me, x0, x1, y0, y1, z_top=0.5, grow=0.16, mat="fieldstone"):
    # splayed 0.16 (was 0.08) and chamfered: the house sits IN the ground on a
    # footing, not dropped onto it as a box (2026-09-29)
    me.cbox(T((x0 + x1) / 2, (y0 + y1) / 2, (z_top - 0.5) / 2),
            (x1 - x0 + 2 * grow, y1 - y0 + 2 * grow, z_top + 0.5), mat, 0.07)


def window_box(me, c, along, w, rnd):
    """A planted box under a window (2026-09-29, "it is all grey ... dead"):
    planks, a moss bed and a row of blooms in two colours -- the saturated
    pops the calm facades are allowed, where the eye rests."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    base = Matrix((along, -out, Z)).transposed().to_4x4()

    def at(p):
        m = base.copy()
        m.translation = p
        return m
    me.box(at(c), (w, 0.26, 0.2), "planks", axis=(1, 0, 0))
    me.box(at(c + Z * 0.13), (w - 0.06, 0.2, 0.08), "moss")
    cols = rnd.sample(("cloth_red", "crops", "cloth_blue", "cloth_cream", "clay_tile"), 2)
    n = max(3, min(5, int(w / 0.2)))
    for i in range(n):
        u = -w / 2 + 0.12 + i * (w - 0.24) / max(n - 1, 1)
        me.box(at(c + along * u + Z * (0.21 + rnd.uniform(0, 0.05)) + out * rnd.uniform(-0.05, 0.05)),
               (0.12, 0.12, 0.09), cols[i % 2])


def flower_box(me, x, y, z, w):
    me.box(T(x, y, z), (w, 0.26, 0.22), "planks", axis=(1, 0, 0))
    me.box(T(x, y, z + 0.14), (w - 0.06, 0.2, 0.08), "moss")


# ---------------------------------------------------------------------------
# shadow and collision proxies
# ---------------------------------------------------------------------------

def proxy_box(me, x0, x1, y0, y1, z0, z1, mat="SHADOW"):
    me.box(T((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), mat)


def proxy_roof(me, x0, x1, y0, y1, z_eave, ridge_z, ridge_axis="x", over=0.60, mat="SHADOW"):
    if ridge_axis == "x":
        o, u = Vector((x0 - 0.35, y0 - over, z_eave - 0.2)), Vector((0, 1, 0))
        span, depth = (y1 - y0) + 2 * over, (x1 - x0) + 0.7
        me.prism(o, u, Z, [(0, 0), (span, 0), (span / 2, ridge_z - z_eave + 0.3)], -depth, mat)
    else:
        o, u = Vector((x1 + over, y0 - 0.35, z_eave - 0.2)), Vector((-1, 0, 0))
        span, depth = (x1 - x0) + 2 * over, (y1 - y0) + 0.7
        me.prism(o, u, Z, [(0, 0), (span, 0), (span / 2, ridge_z - z_eave + 0.3)], -depth, mat)


# ---------------------------------------------------------------------------
# buildings
# ---------------------------------------------------------------------------

def cottage():
    """One storey and an attic, thatched, half-timbered over a fieldstone
    plinth, chimney on the east gable. 6.4 x 5.0 m."""
    W, D, z0, z1, pitch = 6.4, 5.0, 0.5, 3.0, 47
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    me = Mesh("cottage")
    plinth(me, x0, x1, y0, y1)
    h = z1 - z0
    # front (-Y): door, two windows, flower box
    wall(me, Vector((x0, y0, 0)), (1, 0, 0), W, z0, z1,
         [(1.0, 2.0, 0.9, 1.9, "window"), (2.8, 3.8, 0.0, 2.1, "door"), (4.6, 5.6, 0.9, 1.9, "window")],
         "plaster", braces=[(0.0, 1.0, True), (5.6, 6.4, False)], rails=(0.9,))
    flower_box(me, x0 + 5.1, y0 - 0.2, z0 + 0.72, 1.1)
    # back (+Y), running the other way so its outer face points +Y
    wall(me, Vector((x1, y1, 0)), (-1, 0, 0), W, z0, z1,
         [(1.4, 2.4, 0.9, 1.9, "window_dim"), (4.0, 5.0, 0.9, 1.9, "window_dim")],
         "plaster", braces=[(2.4, 4.0, True)], rails=(0.9,))
    # gable ends
    rise = (D / 2) * math.tan(math.radians(pitch))
    wall(me, Vector((x1, y0, 0)), (0, 1, 0), D, z0, z1, [(1.9, 3.1, 0.9, 1.9, "window")],
         "plaster", rails=(0.9,))
    wall(me, Vector((x0, y1, 0)), (0, -1, 0), D, z0, z1, [(1.9, 3.1, 0.9, 1.9, "window_dim")],
         "plaster", rails=(0.9,))
    gable(me, Vector((x1, y0, 0)), (0, 1, 0), D, z1, rise, "plaster")
    gable(me, Vector((x0, y1, 0)), (0, -1, 0), D, z1, rise, "plaster", window=(0.6, 0.7))
    ridge = roof(me, x0, x1, y0, y1, z1, pitch, "thatch", over_eave=0.5, thick=0.34)
    chimney(me, x1 + 0.45, 0.9, ridge + 1.0)
    vis = me.build()

    sh = Mesh("SHADOW_cottage")
    proxy_box(sh, x0, x1 + 0.9, y0, y1, -0.5, z1)
    proxy_roof(sh, x0, x1, y0, y1, z1, ridge, over=0.5)
    proxy_box(sh, x1 + 0.05, x1 + 0.85, 0.5, 1.3, z1, ridge + 1.3)
    col = Mesh("COL_cottage")
    proxy_box(col, x0, x1, y0, y1, -0.5, ridge, mat="COL")
    return vis, sh.build(), _nomat(col.build())


def townhouse():
    """Two storeys, gable to the street. Brick ground floor with a door and
    a shop window; a timber-framed upper floor jettied 0.4 m over the street;
    a steep slate roof with a framed front gable; brick chimney. 5.2 x 7 m."""
    W, D = 5.2, 7.0
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    zg0, zg1, zu1, pitch = 0.5, 3.3, 6.0, 52
    jet = 0.4
    me = Mesh("townhouse")
    plinth(me, x0, x1, y0, y1, mat="fieldstone")
    # ground floor, brick, no timber frame
    wall(me, Vector((x0, y0, 0)), (1, 0, 0), W, zg0, zg1,
         [(0.5, 1.5, 0.0, 2.2, "door"), (2.2, 4.6, 0.8, 2.2, "window")], "brick", frame=False)
    wall(me, Vector((x1, y1, 0)), (-1, 0, 0), W, zg0, zg1, [(2.0, 3.0, 0.9, 1.9, "window_dim")],
         "brick", frame=False)
    wall(me, Vector((x1, y0, 0)), (0, 1, 0), D, zg0, zg1, [(3.0, 4.0, 0.9, 1.9, "window")], "brick", frame=False)
    wall(me, Vector((x0, y1, 0)), (0, -1, 0), D, zg0, zg1, [], "brick", frame=False)
    # jetty: joist ends and brackets under the overhang
    for i in range(9):
        x = x0 + 0.2 + i * (W - 0.4) / 8
        beam(me, (x, y0 + 0.3, zg1 - 0.1), (x, y0 - jet - 0.12, zg1 - 0.1), 0.16, 0.14)
    for x in (x0 + 0.3, x1 - 0.3):
        beam(me, (x, y0 - 0.02, zg1 - 1.0), (x, y0 - jet + 0.05, zg1 - 0.15), 0.14, 0.14, up=(1, 0, 0))
    # upper floor, timber framed, front wall pushed out by the jetty
    yf = y0 - jet
    wall(me, Vector((x0, yf, 0)), (1, 0, 0), W, zg1, zu1,
         [(0.7, 1.7, 0.7, 1.9, "window"), (3.5, 4.5, 0.7, 1.9, "window")], "plaster",
         braces=[(1.9, 2.6, True), (2.6, 3.3, False)], rails=(0.6,))
    flower_box(me, x0 + 1.2, yf - 0.2, zg1 + 0.52, 1.1)
    flower_box(me, x0 + 4.0, yf - 0.2, zg1 + 0.52, 1.1)
    wall(me, Vector((x1, y1, 0)), (-1, 0, 0), W, zg1, zu1, [(2.0, 3.0, 0.7, 1.9, "window_dim")], "plaster",
         rails=(0.6,))
    wall(me, Vector((x1, yf, 0)), (0, 1, 0), D + jet, zg1, zu1,
         [(1.5, 2.5, 0.7, 1.9, "window"), (4.6, 5.6, 0.7, 1.9, "window_dim")], "plaster",
         braces=[(2.7, 4.2, True)], rails=(0.6,))
    wall(me, Vector((x0, y1, 0)), (0, -1, 0), D + jet, zg1, zu1, [(3.0, 4.0, 0.7, 1.9, "window_dim")],
         "plaster", braces=[(0.2, 1.8, False)], rails=(0.6,))
    # front and back gables (ridge runs front to back, along y)
    rise = (W / 2) * math.tan(math.radians(pitch))
    gable(me, Vector((x0, yf, 0)), (1, 0, 0), W, zu1, rise, "plaster", window=(0.7, 0.9))
    gable(me, Vector((x1, y1, 0)), (-1, 0, 0), W, zu1, rise, "plaster")
    ridge = roof(me, x0, x1, yf, y1, zu1, pitch, "slate", over_eave=0.35, over_gable=0.4, ridge_axis="y")
    chimney(me, x1 - 0.9, 1.6, ridge + 0.9, w=0.9, d=0.9, mat="brick", top="brick")
    vis = me.build()

    sh = Mesh("SHADOW_townhouse")
    proxy_box(sh, x0, x1, y0, y1, -0.5, zg1)
    proxy_box(sh, x0, x1, yf, y1, zg1, zu1)
    proxy_roof(sh, x0, x1, yf, y1, zu1, ridge, ridge_axis="y", over=0.35)
    proxy_box(sh, x1 - 1.35, x1 - 0.45, 1.15, 2.05, zu1, ridge + 1.2)
    col = Mesh("COL_townhouse")
    proxy_box(col, x0, x1, y0, y1, -0.5, ridge, mat="COL")
    return vis, sh.build(), _nomat(col.build())


def retaining():
    """A 3 m fieldstone retaining wall, 1.5 m high, with a cap: the terrace
    edge of Law 3. Tiles end to end along x."""
    me = Mesh("retaining")
    me.box(T(0, 0, 0.5), (3.0, 0.7, 2.0), "fieldstone")
    me.box(T(0, -0.04, 1.58), (3.0, 0.86, 0.16), "cobble")
    vis = me.build()
    sh = Mesh("SHADOW_retaining")
    proxy_box(sh, -1.5, 1.5, -0.35, 0.35, -0.5, 1.66)
    col = Mesh("COL_retaining")
    proxy_box(col, -1.5, 1.5, -0.35, 0.35, -0.5, 1.66, mat="COL")
    return vis, sh.build(), _nomat(col.build())


def steps():
    """Four stone treads climbing 1.5 m toward +Y, 1.6 m wide."""
    me = Mesh("steps")
    for i in range(4):
        me.box(T(0, i * 0.4, (i + 1) * 0.375 / 2 - 0.25), (1.6, 0.42, (i + 1) * 0.375 + 0.5), "fieldstone",
               faces={"+z": "cobble"})
    vis = me.build()
    sh = Mesh("SHADOW_steps")
    proxy_box(sh, -0.8, 0.8, -0.2, 1.4, -0.5, 1.5)
    col = Mesh("COL_steps")
    proxy_box(col, -0.8, 0.8, -0.2, 1.4, -0.5, 1.5, mat="COL")
    return vis, sh.build(), _nomat(col.build())


def _nomat(ob):
    ob.data.materials.clear()
    return ob


BUILDS = {"cottage": cottage, "townhouse": townhouse, "retaining": retaining, "steps": steps}


def export(name, objs):
    os.makedirs(OUT, exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    path = os.path.join(OUT, f"kit_{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_apply=True)
    return path


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = argv or list(BUILDS)
    report = {}
    for name in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        vis, sh, col = BUILDS[name]()
        tris = sum(len(p.vertices) - 2 for p in vis.data.polygons)
        stris = sum(len(p.vertices) - 2 for p in sh.data.polygons)
        lo = [min(v.co[i] for v in vis.data.vertices) for i in range(3)]
        hi = [max(v.co[i] for v in vis.data.vertices) for i in range(3)]
        path = export(name, [vis, sh, col])
        report[name] = dict(tris=tris, shadow_tris=stris, materials=list(vis.data.materials.keys()),
                            size=[round(hi[i] - lo[i], 2) for i in range(3)])
        print(f"kit: {name:<10} tris {tris:>6}  shadow {stris:>4}  size {report[name]['size']}  "
              f"mats {report[name]['materials']}  -> {path}")
    with open(os.path.join(OUT, "kit_manifest.json"), "w") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":   # citykit imports the parts
    main()
