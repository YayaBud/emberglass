"""An ancient merchant ship for the lake: a round-bellied cargo hull, a stem
post ending in a horse's head, a sternpost that curls up and over, an open
hold of amphorae and white bales behind a fence of stakes, one mast with a
square sail set on its yard, twin steering oars at the stern.

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background --factory-startup \\
        --python D:/assests/scripts/forge/ship/ship.py

Writes game/assets/models/ship/ship_cargo.glb (and renders/ship/*.png
workbench previews, back faces culled so a flipped face shows as a hole).

Conventions shared with the kit (scripts/forge/kit/kit.py):
- surfaces the game has pixel textures for are named after them (`planks`,
  `timber`, `fieldstone`) and `TexLib` swaps its material in by that name;
  UVs are projected in world metres at 52 texels/m, `planks` boards and
  `timber` grain run along v, so v follows the hull's length and each beam.
- a `SHADOW_` mesh of a few dozen triangles casts the shadows; the detailed
  mesh casts none (memory.md: the shadow cascades are the frame's cost).
- `M_Sail` is replaced in the game by the sail shader (billow + brails).

Frame: +X is the bow, z = 0 the waterline, Blender Z up (the GLB is Y-up).
Size: 18 m over the posts, 16 m hull, 5 m beam, 1.35 m draft -- a
Kyrenia/Uluburun-class trader, about five times the rowing boat.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "game", "assets", "models", "ship")
REN = os.path.join(ROOT, "renders", "ship")
TPM = 52.0
PX = {"planks": (504, 512), "timber": (128, 512), "fieldstone": (528, 528)}

COLS = {  # base colours: the GLB carries them for the untextured surfaces
    "planks": (0.48, 0.33, 0.2), "timber": (0.33, 0.22, 0.13), "fieldstone": (0.45, 0.44, 0.42),
    "M_Sail": (0.86, 0.82, 0.7), "M_Rope": (0.52, 0.42, 0.28), "M_Terracotta": (0.66, 0.33, 0.2),
    "M_Bale": (0.84, 0.81, 0.72), "SHADOW": (0.2, 0.2, 0.2),
}

L_HULL, BEAM, KEEL, GUN = 16.0, 5.0, -1.35, 1.45
X = Vector((1, 0, 0))
Z = Vector((0, 0, 1))


class Mesh:
    """Faces with a material and a metre-projected UV each. Flat-shaded
    (no shared vertices), like the kit. `face` takes points in the winding
    that faces outward; `solid` parts flip themselves outward instead."""

    def __init__(self, name):
        self.name, self.faces = name, []

    def face(self, pts, mat, axis=None, uv=None):
        pts = [Vector(p) for p in pts]
        out = [pts[0]]
        for p in pts[1:]:
            if (p - out[-1]).length > 1e-5:
                out.append(p)
        if len(out) > 2 and (out[0] - out[-1]).length < 1e-5:
            out.pop()
        if len(out) < 3:
            return
        self.faces.append((out, mat, axis, uv))

    def solid(self, pts, mat, centre, axis=None):
        n = _normal(pts)
        if n.dot(sum((Vector(p) for p in pts), Vector()) / len(pts) - centre) < 0:
            pts = list(reversed(pts))
        self.face(pts, mat, axis)

    def box(self, m, size, mat, axis=None):
        hx, hy, hz = (s / 2 for s in size)
        c = [m @ Vector((sx * hx, sy * hy, sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        centre = m @ Vector()
        wax = None if axis is None else (m.to_3x3() @ Vector(axis)).normalized()
        for q in ((4, 6, 7, 5), (0, 1, 3, 2), (2, 3, 7, 6), (0, 4, 5, 1), (1, 5, 7, 3), (0, 2, 6, 4)):
            self.solid([c[i] for i in q], mat, centre, wax)

    def beam(self, a, b, w, h, mat, up=Z):
        """A square-section beam from a to b (grain along it)."""
        a, b = Vector(a), Vector(b)
        d = b - a
        t = d.normalized()
        s = t.cross(up)
        if s.length < 1e-4:
            s = t.cross(X)
        s.normalize()
        u = s.cross(t)
        m = Matrix((s, u, t)).transposed().to_4x4()
        m.translation = (a + b) / 2
        self.box(m, (w, h, d.length), mat, axis=(0, 0, 1))

    def prism(self, a, b, r0, r1, n, mat, caps=True):
        """An n-sided round spar or pot section from a (radius r0) to b (r1)."""
        a, b = Vector(a), Vector(b)
        t = (b - a).normalized()
        s = t.cross(Z if abs(t.z) < 0.9 else X).normalized()
        u = t.cross(s)
        ring = lambda c, r: [c + (s * math.cos(k * math.tau / n) + u * math.sin(k * math.tau / n)) * r for k in range(n)]
        ra, rb = ring(a, r0), ring(b, r1)
        centre = (a + b) / 2
        for k in range(n):
            j = (k + 1) % n
            self.solid([ra[k], ra[j], rb[j], rb[k]], mat, centre, t)
        if caps:
            self.solid(ra, mat, centre, t)
            self.solid(rb, mat, centre, t)

    def lathe(self, base, axis, prof, n, mat):
        """Revolve (radius, height) profile points about `axis` from `base`."""
        axis = Vector(axis).normalized()
        s = axis.cross(Z if abs(axis.z) < 0.9 else X).normalized()
        u = axis.cross(s)
        rings = [[base + axis * h + (s * math.cos(k * math.tau / n) + u * math.sin(k * math.tau / n)) * r
                  for k in range(n)] for r, h in prof]
        for i in range(len(prof) - 1):
            ci = base + axis * (prof[i][1] + prof[i + 1][1]) / 2
            for k in range(n):
                j = (k + 1) % n
                self.solid([rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]], mat, ci)

    def build(self):
        me = bpy.data.meshes.new(self.name)
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new("UVMap")
        mats = []
        for pts, mat, axis, uv in self.faces:
            if mat not in mats:
                mats.append(mat)
            try:
                f = bm.faces.new([bm.verts.new(p) for p in pts])
            except ValueError:
                continue
            f.material_index = mats.index(mat)
            n = _normal(pts)
            pw, ph = PX.get(mat, (512, 512))
            if uv is not None:
                for loop, (a, b) in zip(f.loops, uv):
                    loop[uvl].uv = (a * TPM / pw, b * TPM / ph)
            else:
                ua, va = _frame(n, axis)
                for loop in f.loops:
                    p = loop.vert.co
                    loop[uvl].uv = (p.dot(ua) * TPM / pw, p.dot(va) * TPM / ph)
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(_material(m))
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


def _normal(pts):
    n = Vector()
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n += Vector(((p.y - q.y) * (p.z + q.z), (p.z - q.z) * (p.x + q.x), (p.x - q.x) * (p.y + q.y)))
    return n.normalized() if n.length > 1e-12 else Z.copy()


def _frame(n, axis):
    """u across the face, v along `axis` (grain) or up the face."""
    if axis is not None and abs(Vector(axis).normalized().dot(n)) < 0.9:
        v = (Vector(axis) - n * n.dot(Vector(axis))).normalized()
    elif abs(n.z) < 0.9:
        v = (Z - n * n.z).normalized()
    else:
        v = X.copy()
    return n.cross(v).normalized(), v


def _material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    c = COLS.get(name, (0.5, 0.5, 0.5))
    bsdf.inputs["Base Color"].default_value = (*c, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    m.diffuse_color = (*c, 1)
    return m


# ---------------------------------------------------------------------- hull
def half_w(t, inset=0.0):
    return max(0.0, BEAM / 2 * (1 - abs(t) ** 2.4) ** 0.55 - inset)


def keel_z(t, inset=0.0):
    return KEEL + 1.0 * abs(t) ** 3 + inset


def gun_z(t):
    return GUN + 0.75 * t * t + (0.15 * t ** 3 if t > 0 else 0.0)


def section(t, phi, inset=0.0):
    w, k, g = half_w(t, inset), keel_z(t, inset), gun_z(t)
    return w * math.sin(phi) ** 0.75, k + (g - k) * (1 - math.cos(phi))


def inner_y_at(t, z, inset=0.12):
    """Half-width of the inner shell at height z (the deck and floor edges)."""
    k, g = keel_z(t, inset), gun_z(t)
    r = min(max((z - k) / (g - k), 0.0), 1.0)
    return half_w(t, inset) * math.sin(math.acos(1 - r)) ** 0.75


NS, NG = 32, 10


def hull(m):
    ts = [-1 + 2 * i / NS for i in range(NS + 1)]
    phis = [j / NG * math.pi / 2 for j in range(NG + 1)]
    for inset, outward in ((0.0, True), (0.12, False)):
        pts = [[section(t, p, inset) for p in phis] for t in ts]
        # girth arc length per station, for the board UV (u across boards)
        arc = []
        for row in pts:
            acc, a = [0.0], 0.0
            for j in range(1, len(row)):
                a += math.dist(row[j], row[j - 1])
                acc.append(a)
            arc.append(acc)
        for i in range(NS):
            x0, x1 = ts[i] * L_HULL / 2, ts[i + 1] * L_HULL / 2
            for j in range(NG):
                (y00, z00), (y01, z01) = pts[i][j], pts[i][j + 1]
                (y10, z10), (y11, z11) = pts[i + 1][j], pts[i + 1][j + 1]
                for sgn in (1, -1):
                    q = [(x0, sgn * y00, z00), (x0, sgn * y01, z01), (x1, sgn * y11, z11), (x1, sgn * y10, z10)]
                    uv = [(arc[i][j], x0), (arc[i][j + 1], x0), (arc[i + 1][j + 1], x1), (arc[i + 1][j], x1)]
                    # as listed, starboard faces +y; the port copy and the
                    # inner shell (seen from inside) are reversed
                    if (sgn < 0) == outward:
                        q, uv = q[::-1], uv[::-1]
                    m.face(q, "planks", uv=uv)
    # gunwale cap between the shells, a wale (rubbing strake) outside it
    for i in range(NS):
        t0, t1 = ts[i], ts[i + 1]
        x0, x1 = t0 * L_HULL / 2, t1 * L_HULL / 2
        for sgn in (1, -1):
            o0, o1 = half_w(t0), half_w(t1)
            n0, n1 = half_w(t0, 0.12), half_w(t1, 0.12)
            g0, g1 = gun_z(t0), gun_z(t1)
            q = [(x0, sgn * n0, g0), (x1, sgn * n1, g1), (x1, sgn * o1, g1), (x0, sgn * o0, g0)]
            if sgn < 0:
                q = q[::-1]
            m.face(q, "timber", axis=X)
            if abs(t0) < 0.96 and abs(t1) < 0.96:
                a = Vector((x0, sgn * (section(t0, math.pi * 0.44)[0] + 0.05), gun_z(t0) - 0.32))
                b = Vector((x1, sgn * (section(t1, math.pi * 0.44)[0] + 0.05), gun_z(t1) - 0.32))
                m.beam(a, b, 0.14, 0.2, "timber", up=Vector((0, sgn, 0)))


def decks(m):
    """The hold floor, a raised deck fore and aft, bulkheads closing them,
    and cross beams over the hold."""
    def slab(t0, t1, z, steps=6):
        for k in range(steps):
            a = t0 + (t1 - t0) * k / steps
            b = t0 + (t1 - t0) * (k + 1) / steps
            xa, xb = a * L_HULL / 2, b * L_HULL / 2
            ya, yb = inner_y_at(a, z), inner_y_at(b, z)
            m.face([(xa, -ya, z), (xb, -yb, z), (xb, yb, z), (xa, ya, z)], "planks", axis=X)

    FLOOR, FORE, AFT = 0.05, 1.25, 1.3
    slab(-0.62, 0.64, FLOOR, 16)
    slab(0.64, 0.97, gun_z(0.64) - 0.45, 6)
    slab(-0.97, -0.62, gun_z(-0.62) - 0.4, 6)
    # bulkheads from the floor up to each deck
    for t, top, face_dir in ((0.64, gun_z(0.64) - 0.45, -1), (-0.62, gun_z(-0.62) - 0.4, 1)):
        x = t * L_HULL / 2
        rows = 6
        for k in range(rows):
            za = FLOOR + (top - FLOOR) * k / rows
            zb = FLOOR + (top - FLOOR) * (k + 1) / rows
            ya, yb = inner_y_at(t, za), inner_y_at(t, zb)
            q = [(x, -ya, za), (x, ya, za), (x, yb, zb), (x, -yb, zb)]
            if face_dir < 0:   # as listed it faces +x
                q = q[::-1]
            m.face(q, "planks", axis=Z)
    for t in (-0.42, 0.12, 0.46):
        x = t * L_HULL / 2
        z = gun_z(t) - 0.2
        y = inner_y_at(t, z)
        m.beam((x, -y, z), (x, y, z), 0.22, 0.18, "timber")


# --------------------------------------------------------------- posts, head
def sweep(m, pts, w0, w1, h0, h1, mat):
    """A tapering square timber along a polyline in the XZ plane."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = Vector((0, 1, 0))
        up = t.cross(side).normalized()
        f = i / (len(pts) - 1)
        w, h = w0 + (w1 - w0) * f, h0 + (h1 - h0) * f
        rings.append([p + side * sx * w / 2 + up * sz * h / 2 for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for i in range(len(pts) - 1):
        c = (pts[i] + pts[i + 1]) / 2
        for k in range(4):
            j = (k + 1) % 4
            m.solid([rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]], mat, c,
                    (pts[i + 1] - pts[i]).normalized())
    m.solid(rings[0], mat, pts[1])
    m.solid(rings[-1], mat, pts[-2])


def posts(m):
    xe = L_HULL / 2
    bow = [(xe - 0.5, 0, -0.45), (xe, 0, 0.5), (xe + 0.4, 0, 1.6), (xe + 0.75, 0, 2.7),
           (xe + 0.95, 0, 3.6), (xe + 1.0, 0, 4.3)]
    sweep(m, bow, 0.34, 0.26, 0.42, 0.3, "timber")
    # the horse's head, big enough to read at 60 m: neck bending forward,
    # head pitched down, snout, ears, a mane down the neck
    top = Vector(bow[-1])
    neck = top + Vector((0.5, 0, 0.7))
    sweep(m, [top, neck], 0.3, 0.32, 0.34, 0.42, "timber")
    head = Matrix.Translation(neck + Vector((0.7, 0, -0.12))) @ Matrix.Rotation(math.radians(30), 4, "Y")
    m.box(head, (1.5, 0.4, 0.52), "timber", axis=(1, 0, 0))
    m.box(head @ Matrix.Translation((0.82, 0, -0.1)), (0.45, 0.34, 0.38), "timber", axis=(1, 0, 0))
    for s in (-1, 1):
        ear = Matrix.Translation(neck + Vector((0.15, s * 0.13, 0.45))) @ Matrix.Rotation(math.radians(-15), 4, "Y")
        m.box(ear, (0.14, 0.09, 0.4), "timber", axis=(0, 0, 1))
        eye = head @ Matrix.Translation((0.2, s * 0.2, 0.08))
        m.box(eye, (0.12, 0.04, 0.1), "fieldstone")
    for k in range(5):
        p = top + (neck - top) * (k / 4) + Vector((-0.26, 0, 0.12))
        m.box(Matrix.Translation(p), (0.16, 0.14, 0.22), "timber")
    stern = [(-xe + 0.5, 0, -0.45), (-xe, 0, 0.6), (-xe - 0.55, 0, 1.9), (-xe - 0.9, 0, 3.2),
             (-xe - 0.95, 0, 4.3), (-xe - 0.65, 0, 5.1), (-xe - 0.15, 0, 5.45), (-xe + 0.25, 0, 5.3)]
    sweep(m, stern, 0.36, 0.18, 0.44, 0.22, "timber")


# ------------------------------------------------------------ mast and sail
MAST_X, MAST_TOP, YARD_Z, YARD_W, FOOT_Z = 0.8, 12.2, 11.2, 13.0, 3.6


def sail_pt(u, v):
    """The set sail: hung from the yard, bellied forward by a following wind,
    its foot corners sheeted aft to the quarters."""
    y = (u - 0.5) * (YARD_W - 0.6)
    z = YARD_Z - 0.18 - (YARD_Z - 0.18 - FOOT_Z) * v
    belly = 1.5 * math.sin(math.pi * u) ** 0.8 * math.sin(math.pi / 2 * v) ** 1.1
    x = MAST_X + 0.28 + belly - 0.7 * v * abs(2 * u - 1) ** 2
    return Vector((x, y, z))


def rig(m):
    m.prism((MAST_X, 0, 0.05), (MAST_X, 0, MAST_TOP), 0.21, 0.14, 8, "timber")
    m.box(Matrix.Translation((MAST_X, 0, MAST_TOP + 0.15)), (0.36, 0.36, 0.3), "timber")
    # the yard: two tapering spars from the middle, drooping at the tips
    mid = Vector((MAST_X + 0.24, 0, YARD_Z))
    for s in (-1, 1):
        m.prism(mid, mid + Vector((0, s * YARD_W / 2, -0.3)), 0.14, 0.07, 6, "timber")
    su, sv = 14, 10
    for i in range(su):
        for j in range(sv):
            a, b = sail_pt(i / su, j / sv), sail_pt((i + 1) / su, j / sv)
            c, d = sail_pt((i + 1) / su, (j + 1) / sv), sail_pt(i / su, (j + 1) / sv)
            m.face([a, d, c, b], "M_Sail", uv=[(i / su, j / sv), (i / su, (j + 1) / sv),
                                               ((i + 1) / su, (j + 1) / sv), ((i + 1) / su, j / sv)])
    rope = lambda a, b: m.beam(a, b, 0.035, 0.035, "M_Rope")
    head = Vector((MAST_X, 0, MAST_TOP))
    rope(head, (L_HULL / 2 + 0.55, 0, 1.9))                      # forestay
    for s in (-1, 1):
        rope(head, (-L_HULL / 2 + 1.0, s * 1.3, gun_z(-0.88)))    # backstays
        for dx in (0.3, -0.9):                                    # shrouds
            t = (MAST_X + dx) / (L_HULL / 2)
            rope(head - Vector((0, 0, 1.0)), (MAST_X + dx, s * half_w(t), gun_z(t)))
        foot = sail_pt(0.0 if s < 0 else 1.0, 1.0)
        t = -0.78
        rope(foot, (t * L_HULL / 2, s * half_w(t), gun_z(t)))     # sheets
        tip = mid + Vector((0, s * YARD_W / 2, -0.3))
        t = -0.9
        rope(tip, (t * L_HULL / 2, s * half_w(t) * 0.9, gun_z(t)))   # braces
        rope(tip, head + Vector((0, 0, 0.1)))                    # lifts
    # brails: lines down the front of the sail to the deck
    for u in (0.2, 0.35, 0.5, 0.65, 0.8):
        top, bot = sail_pt(u, 0.0), sail_pt(u, 1.0)
        for j in range(4):
            a, b = sail_pt(u, j / 4), sail_pt(u, (j + 1) / 4)
            rope(a + Vector((0.05, 0, 0)), b + Vector((0.05, 0, 0)))


def steering(m):
    for s in (-1, 1):
        t = -0.84
        pivot = Vector((t * L_HULL / 2, s * (half_w(t) + 0.1), gun_z(t) + 0.15))
        blade = pivot + Vector((-1.7, s * 0.55, -2.8))
        m.prism(pivot + Vector((0.5, -s * 0.25, 0.9)), blade, 0.09, 0.08, 6, "timber")
        d = (blade - pivot).normalized()
        c = blade - d * 0.7
        side = Vector((0, 1, 0))
        up = d.cross(side).normalized()
        frame = Matrix((d.cross(up).normalized(), up, d)).transposed().to_4x4()
        frame.translation = c
        m.box(frame, (0.08, 0.5, 1.6), "timber", axis=(0, 0, 1))
        m.beam(pivot + Vector((0.5, -s * 0.25, 0.9)), pivot + Vector((1.4, -s * 1.0, 0.95)), 0.08, 0.08, "timber")


def fence(m):
    """Stakes along the gunwale over the hold, with a top rail."""
    for s in (-1, 1):
        prev = None
        n = 58
        for k in range(n + 1):
            t = -0.6 + 1.22 * k / n
            x = t * L_HULL / 2
            y = s * (half_w(t) - 0.06)
            g = gun_z(t)
            m.box(Matrix.Translation((x, y, g + 0.45)), (0.05, 0.05, 0.9), "timber", axis=(0, 0, 1))
            top = Vector((x, y, g + 0.92))
            if prev is not None:
                m.beam(prev, top, 0.07, 0.07, "timber")
            prev = top


# -------------------------------------------------------------------- cargo
AMPHORA = [(0.02, 0.0), (0.1, 0.08), (0.2, 0.3), (0.24, 0.5), (0.22, 0.66), (0.14, 0.76),
           (0.07, 0.82), (0.065, 0.96), (0.09, 0.99), (0.07, 1.02)]


def cargo(m):
    FLOOR = 0.05
    k = 0
    for x in [x * 0.52 for x in range(-9, -1)] + [x * 0.52 for x in range(5, 10)]:
        t = x / (L_HULL / 2)
        lim = inner_y_at(t, FLOOR + 0.5) - 0.3
        ny = int(lim // 0.5)
        for j in range(-ny, ny + 1):
            y = j * 0.5 + (0.25 if k % 2 else 0.0)
            if abs(y) > lim:
                continue
            base = Vector((x, y, FLOOR))
            tilt = Vector((0.04 * ((k * 7 + j * 3) % 5 - 2), 0.04 * ((k * 5 + j) % 3 - 1), 1)).normalized()
            m.lathe(base, tilt, AMPHORA, 8, "M_Terracotta")
            for s in (-1, 1):   # handles
                p = base + tilt * 0.8 + Vector((0, s * 0.13, 0))
                m.beam(p, p + tilt * 0.14 + Vector((0, s * 0.06, 0)), 0.03, 0.05, "M_Terracotta")
        k += 1
    # white bales round the mast, two high, corded
    bales = [(-0.3, -0.6, 0), (-0.3, 0.6, 0), (0.25, -1.3, 0), (0.25, 1.3, 0), (1.6, -0.6, 0), (1.6, 0.6, 0),
             (2.2, -1.2, 0), (2.2, 1.2, 0), (-0.25, 0.0, 1), (1.55, 0.0, 1), (0.5, -0.8, 1), (0.5, 0.8, 1)]
    for i, (x, y, lvl) in enumerate(bales):
        c = Vector((x, y, FLOOR + 0.33 + lvl * 0.64))
        m.box(Matrix.Translation(c) @ Matrix.Rotation(0.08 * (i % 3 - 1), 4, "Z"), (1.05, 0.72, 0.64), "M_Bale")
        for dx in (-0.3, 0.3):
            m.box(Matrix.Translation(c + Vector((dx, 0, 0))), (0.04, 0.74, 0.66), "M_Rope")
    # a stone anchor and a coil of line on the fore deck
    zf = gun_z(0.64) - 0.45
    m.box(Matrix.Translation((6.1, 0.4, zf + 0.09)) @ Matrix.Rotation(0.3, 4, "Z"), (0.7, 0.45, 0.18), "fieldstone")
    m.prism((5.8, -0.6, zf), (5.8, -0.6, zf + 0.12), 0.35, 0.35, 10, "M_Rope")


# ------------------------------------------------------------- shadow proxy
def shadow(m):
    ts = [-1, -0.6, -0.2, 0.2, 0.6, 1]
    for a, b in zip(ts, ts[1:]):
        for sgn in (1, -1):
            xa, xb = a * L_HULL / 2, b * L_HULL / 2
            q = [(xa, 0, keel_z(a)), (xb, 0, keel_z(b)), (xb, sgn * half_w(b), gun_z(b)), (xa, sgn * half_w(a), gun_z(a))]
            m.face(q if sgn < 0 else q[::-1], "SHADOW")
    m.beam((MAST_X, 0, 0), (MAST_X, 0, MAST_TOP), 0.3, 0.3, "SHADOW")
    m.beam((L_HULL / 2, 0, 0), (L_HULL / 2 + 1.3, 0, 4.8), 0.3, 0.3, "SHADOW")
    m.beam((-L_HULL / 2, 0, 0), (-L_HULL / 2 - 0.9, 0, 5.3), 0.3, 0.3, "SHADOW")
    g = [[sail_pt(i / 3, j / 2) for j in range(3)] for i in range(4)]
    for i in range(3):
        for j in range(2):
            m.face([g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j]], "SHADOW")


# ------------------------------------------------------------------- output
def preview(obs):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_backface_culling = True
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 960, 640
    obs[1].hide_render = True
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    os.makedirs(REN, exist_ok=True)
    centre = Vector((0, 0, 4.0))
    for tag, az, el in (("front", -40, 0.45), ("back", 150, 0.35), ("side", 90, 0.12), ("top", -20, 1.6)):
        d = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), el)).normalized()
        cam.location = centre + d * 30
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(REN, f"ship_{tag}.png")
        bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    vis = Mesh("Ship")
    hull(vis)
    decks(vis)
    posts(vis)
    fence(vis)
    rig(vis)
    steering(vis)
    cargo(vis)
    sh = Mesh("SHADOW_Ship")
    shadow(sh)
    obs = [vis.build(), sh.build()]
    os.makedirs(OUT, exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(o in obs)
    path = os.path.join(OUT, "ship_cargo.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True)
    tris = [sum(len(p.vertices) - 2 for p in o.data.polygons) for o in obs]
    lo = [min(v.co[i] for v in obs[0].data.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in obs[0].data.vertices) for i in range(3)]
    print(f"ship: {path}  tris {tris[0]} (shadow {tris[1]})  bounds {[round(a, 2) for a in lo]} .. {[round(a, 2) for a in hi]}")
    preview(obs)


main()
