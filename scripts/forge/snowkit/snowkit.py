"""The Hoarfells asset kit, after the user's snow-region asset sheet
(`ref/snow_asset_sheet.png`, 2026-09-23: "replicate it to the minute details").

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background --factory-startup \\
        --python D:/assests/scripts/forge/snowkit/snowkit.py

Writes game/assets/models/snowkit/snowkit.glb -- one object per asset, named
as the sheet labels them -- and renders/snowkit/kit_*.png, a workbench sheet
laid out like the reference's rows (back faces culled: a flipped face shows
as a hole).

Pine trees: large, medium, small, young, sapling, sparse; snowy dead tree;
snow shrub (fronds), snow bush (tiered); each on its own snow mound.
Rocks & cliffs: rock small/medium/large, cliff module, snowy ledge, ice
overhang. Props: fence, signpost, bench, cart with crates, broken cart,
barrels, frozen grass, berries bush, snow pile, log pile, stump, stone wall,
stairs.

Materials are NAMES; the game's `SnowKit` gives each a pixel shader on the
world's 52 texels/m grid, so every UV here is in METRES:
  stone (masonry: courses and blocks drawn from UV), wood (planks, grain
  along v), bark, logend (rings about UV 0), iron, ice (UV.y 0 at an
  icicle's root), berry, needles / rim (pine tiers), frond (shrub leaves),
  snow.
UV2 carries snow data:
  needles, frond: UV2.x = 0 at the top/tip .. 1 at the foot -- the snow
    patches thin out down it, scaled by the live snow amount.
  snow: UV2.y = metres the vertex sinks when there is no snow -- caps and
    mounds shrink into what they sit on as the snow goes, and are not drawn
    once it is bare.
+Z up (the game's +Y), each asset's foot at its origin, front toward -Y.
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "game", "assets", "models", "snowkit")
REN = os.path.join(ROOT, "renders", "snowkit")

COLS = {  # preview colours only; the game shades by name
    "stone": (0.24, 0.24, 0.30), "wood": (0.40, 0.25, 0.15), "bark": (0.34, 0.22, 0.14),
    "logend": (0.62, 0.46, 0.30), "iron": (0.12, 0.12, 0.13), "ice": (0.45, 0.65, 0.90),
    "berry": (0.70, 0.08, 0.10), "needles": (0.16, 0.32, 0.22), "rim": (0.10, 0.20, 0.14),
    "frond": (0.22, 0.38, 0.28), "snow": (0.88, 0.91, 0.97),
    "glass": (1.0, 0.72, 0.38), "slate": (0.20, 0.22, 0.28),
}
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


class Mesh:
    def __init__(self, name):
        self.name, self.faces = name, []

    def face(self, pts, mat, uv, uv2=None):
        pts = [Vector(p) for p in pts]
        self.faces.append((pts, mat, uv, uv2 or [(0.0, 0.0)] * len(pts)))

    def out(self, pts, mat, centre, uv=None, uv2=None, axis=None):
        """A convex polygon turned away from `centre`; UVs (metres) projected
        with v along `axis` (grain) or up the face, unless given."""
        pts = [Vector(p) for p in pts]
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            return
        n.normalize()
        c = sum(pts, Vector()) / len(pts)
        if n.dot(c - Vector(centre)) < 0:
            pts, n = pts[::-1], -n
            uv = uv[::-1] if uv else None
            uv2 = uv2[::-1] if uv2 else None
        if uv is None:
            if axis is not None and abs(Vector(axis).normalized().dot(n)) < 0.9:
                v = (Vector(axis) - n * n.dot(Vector(axis))).normalized()
            elif abs(n.z) < 0.9:
                v = (Z - n * n.z).normalized()
            else:
                v = Y.copy()
            u = n.cross(v).normalized()
            uv = [(p.dot(u), p.dot(v)) for p in pts]
        self.face(pts, mat, uv, uv2)

    def box(self, c, size, mat, yaw=0.0, uv2=None, axis=None, tilt=None):
        """Box centred at c. `uv2(p)` gives each corner's UV2; `axis` the
        grain (local), default the box's longest axis."""
        c = Vector(c)
        m = Matrix.Rotation(yaw, 3, "Z")
        if tilt:
            m = m @ Matrix.Rotation(tilt[0], 3, tilt[1])
        hx, hy, hz = (s / 2 for s in size)
        if axis is None:
            axis = [X, Y, Z][max(range(3), key=lambda i: size[i])]
        ga = m @ Vector(axis)
        k = [c + m @ Vector((sx * hx, sy * hy, sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            pts = [k[i] for i in q]
            self.out(pts, mat, c, uv2=[uv2(p) for p in pts] if uv2 else None, axis=ga)

    def prism(self, a, b, r0, r1, n, mat, caps=True, capmat=None, uv2=None, spin=0.0):
        a, b = Vector(a), Vector(b)
        t = (b - a).normalized()
        s = t.cross(Z if abs(t.z) < 0.9 else X).normalized()
        u = t.cross(s)
        ring = lambda c, r: [c + (s * math.cos(spin + k * math.tau / n) + u * math.sin(spin + k * math.tau / n)) * r
                             for k in range(n)]
        ra, rb = ring(a, r0), ring(b, r1)
        c = (a + b) / 2
        L = (b - a).length
        for k in range(n):
            j = (k + 1) % n
            q = [ra[k], ra[j], rb[j], rb[k]]
            w0, w1 = k * math.tau * r0 / n, (k + 1) * math.tau * r0 / n
            self.out(q, mat, c, uv=[(w0, 0), (w1, 0), (w1, L), (w0, L)],
                     uv2=[uv2(p) for p in q] if uv2 else None)
        if caps:
            for rr, cc, far in ((ra, a, b), (rb, b, a)):
                self.out(rr, capmat or mat, far, uv=[((p - cc).dot(s), (p - cc).dot(u)) for p in rr],
                         uv2=[uv2(p) for p in rr] if uv2 else None)

    def mound(self, c, r, h, n=8, squash=1.0, seed=0):
        """A snow lump: a flattened eight-sided dome on the ground at c.z;
        every vertex sinks to that ground when the snow is gone."""
        rnd = random.Random(seed)
        c = Vector(c)
        base, mid = [], []
        for k in range(n):
            a = k * math.tau / n
            rr = r * (0.85 + rnd.random() * 0.3)
            d = Vector((math.cos(a), math.sin(a) * squash, 0))
            base.append(c + d * rr)
            mid.append(c + d * rr * 0.62 + Z * h * (0.72 + rnd.random() * 0.2))
        top = c + Z * h
        drop = lambda p: (0.0, max(0.0, p.z - c.z))
        for k in range(n):
            j = (k + 1) % n
            self.out([base[k], base[j], mid[j], mid[k]], "snow", c, uv2=[drop(p) for p in (base[k], base[j], mid[j], mid[k])])
            self.out([mid[k], mid[j], top], "snow", c, uv2=[drop(p) for p in (mid[k], mid[j], top)])

    def cap(self, c, size, yaw, t, rnd, droop=True):
        """A snow cap on the top face (centred c, footprint size) of a block:
        a slab `t` thick overhanging a little, with lumps drooping over its
        edges. Sinks to the block's top as the snow goes."""
        c = Vector(c)
        base = c.z
        drop = lambda p: (0.0, max(0.0, p.z - base + 0.01))
        # overhang and lumps scale with what the cap sits on: on an 8 cm rail
        # a rock-sized overhang and 30 cm lumps read as blobs (user, sheet
        # comparison 2026-09-23)
        small = min(size)
        ov = min(0.1, 0.3 * small)
        sx, sy = size[0] + ov, size[1] + ov
        self.box(c + Z * (t / 2), (sx, sy, t), "snow", yaw, uv2=drop)
        if not droop or small < 0.3:
            return
        m = Matrix.Rotation(yaw, 3, "Z")
        for _ in range(int(4 + (sx + sy) * 3.0)):
            side = rnd.choice((0, 1, 2, 3))
            f = rnd.uniform(-0.45, 0.45)
            o = [Vector((f * sx, -sy / 2, 0)), Vector((f * sx, sy / 2, 0)),
                 Vector((-sx / 2, f * sy, 0)), Vector((sx / 2, f * sy, 0))][side]
            w = rnd.uniform(0.5, 0.9) * min(0.34, small * 0.8)
            hang = rnd.uniform(0.4, 1.0) * min(0.28, small * 0.8)
            p = c + m @ o + Z * (t * 0.5 - hang / 2)
            self.box(p, (w, w * 0.8, hang + t * 0.5), "snow", yaw + rnd.uniform(-0.3, 0.3),
                     uv2=lambda q: (0.0, max(0.0, q.z - (base - hang) + 0.01) + hang))

    def icicle(self, top, length, width, rnd):
        top = Vector(top)
        tip = top - Z * length + Vector((rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), 0))
        s = [top + Vector((dx, dy, 0)) * width for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for k in range(4):
            q = [s[k], s[(k + 1) % 4], tip]
            self.out(q, "ice", (top + tip) / 2 + (top - s[k]) * 0,
                     uv=[(0.0, 0.0), (width, 0.0), (width / 2, 1.0)])

    def build(self):
        me = bpy.data.meshes.new(self.name)
        bm = bmesh.new()
        l1 = bm.loops.layers.uv.new("UVMap")
        l2 = bm.loops.layers.uv.new("UV2")
        mats = []
        for pts, mat, uv, uv2 in self.faces:
            if mat not in mats:
                mats.append(mat)
            try:
                f = bm.faces.new([bm.verts.new(p) for p in pts])
            except ValueError:
                continue
            f.material_index = mats.index(mat)
            for k, loop in enumerate(f.loops):
                loop[l1].uv = uv[k]
                loop[l2].uv = uv2[k]
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            mm = bpy.data.materials.get(m) or bpy.data.materials.new(m)
            mm.use_nodes = True
            mm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*COLS[m], 1)
            mm.diffuse_color = (*COLS[m], 1)
            me.materials.append(mm)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


# ------------------------------------------------------------------- trees
def tiered(m, tiers, r0, h0, taper, sides, z0, spacing=0.56, rim=0.26, twist=0.0):
    """Stacked frustum tiers: rim band, slope (needles, UV2.x 0 top .. 1 rim),
    underside. Returns the tip height."""
    z, r, h = z0, r0, h0
    tip = z
    for t in range(tiers):
        last = t == tiers - 1
        zs = z + rim
        rt = 0.0 if last else r * 0.28
        top_z = zs + h * (1.3 if last else 1.0)
        tw = twist + t * (math.pi / sides if t % 2 else 0.0)
        ring = lambda rr, zz: [Vector((rr * math.cos(tw + k * math.tau / sides), rr * math.sin(tw + k * math.tau / sides), zz))
                               for k in range(sides)]
        bot, band, top = ring(r * 0.95, z), ring(r, zs), ring(max(rt, 1e-3), top_z)
        c = Vector((0, 0, zs))
        slope = math.hypot(r - rt, top_z - zs)
        for k in range(sides):
            j = (k + 1) % sides
            across = (band[j] - band[k]).normalized()
            if last:
                q = [top[k], band[j], band[k]]
                uv = [(top[k].dot(across), 0), (band[j].dot(across), slope), (band[k].dot(across), slope)]
                uv2 = [(0, 0), (1, 0), (1, 0)]
            else:
                q = [top[k], top[j], band[j], band[k]]
                uv = [(top[k].dot(across), 0), (top[j].dot(across), 0), (band[j].dot(across), slope), (band[k].dot(across), slope)]
                uv2 = [(0, 0), (0, 0), (1, 0), (1, 0)]
            m.out(q, "needles", c, uv=uv, uv2=uv2)
            m.out([band[k], band[j], bot[j], bot[k]], "rim", c)
        m.out([Vector((p.x, p.y, z)) for p in bot], "rim", Vector((0, 0, z + 1)))
        if not last:
            m.out(top, "needles", Vector((0, 0, top_z - 1)), uv2=[(0, 0)] * sides)
        tip = top_z
        z = zs + h * spacing
        r *= taper
        h *= 0.92
    return tip


def pine(name, tiers, r0, h0, taper, trunk_r, trunk_h, sides=6, spacing=0.56, seed=0):
    m = Mesh(name)
    tip = tiered(m, tiers, r0, h0, taper, sides, trunk_h, spacing)
    m.prism((0, 0, -0.3), (0, 0, trunk_h + 0.6), trunk_r, trunk_r * 0.8, 6, "bark", caps=False)
    m.mound((0, 0, 0), max(0.5, r0 * 0.55), 0.18 + r0 * 0.04, seed=seed)
    return m, tip


def dead_tree(name, rnd):
    m = Mesh(name)
    H = 6.2
    m.prism((0, 0, -0.3), (0, 0, H), 0.3, 0.1, 8, "bark", caps=True, capmat="bark")
    for i, z in enumerate((2.4, 2.9, 3.5, 4.0, 4.6, 5.1)):
        a = rnd.uniform(0, math.tau) if i == 0 else a + math.pi * rnd.uniform(0.7, 1.1)
        L = rnd.uniform(1.3, 1.9) * (1.15 - z / H * 0.55)
        d = Vector((math.cos(a), math.sin(a), 0.7)).normalized()
        a0 = Vector((0, 0, z))
        b0 = a0 + d * L
        m.prism(a0, b0, 0.12, 0.05, 5, "bark")
        for f, up in ((0.55, 1.2), (0.8, 0.6)):   # forked twigs, turned up
            tw = a0 + d * L * f
            m.prism(tw, tw + (d * 0.6 + Z * up).normalized() * L * 0.35, 0.05, 0.02, 4, "bark")
        # snow along the branch's top
        for f in (0.35, 0.7):
            p = a0 + d * L * f + Z * 0.07
            m.box(p, (0.16, 0.1, 0.07), "snow", math.atan2(d.y, d.x),
                  uv2=lambda q, zz=p.z: (0.0, max(0.0, q.z - zz + 0.04)))
    m.mound((0, 0, 0), 0.9, 0.22, seed=11)
    return m


def fronds(m, n, length, spread, rnd, base=Vector((0, 0, 0)), mat="frond"):
    """Leaves fanning up from a clump: long thin four-sided spikes, snow at
    their tips (frond UV2.x: 0 at the tip .. 1 at the base)."""
    for i in range(n):
        a = i * math.tau / n + rnd.uniform(-0.3, 0.3)
        lean = rnd.uniform(0.35, spread)
        d = Vector((math.cos(a) * lean, math.sin(a) * lean, 1.0)).normalized()
        L = length * rnd.uniform(0.75, 1.15)
        root = base + Vector((math.cos(a), math.sin(a), 0)) * 0.08
        tip = root + d * L
        side = d.cross(Z).normalized() * 0.07 * L
        up = side.cross(d).normalized() * 0.045 * L
        mid = root + d * L * 0.45
        ring = [mid + side, mid + up, mid - side, mid - up]
        c = root + d * L * 0.4
        for k in range(4):
            j = (k + 1) % 4
            m.out([ring[k], ring[j], tip], mat, c, uv=[(0, 0.4), (0.1, 0.4), (0.05, 1)], uv2=[(0.55, 0), (0.55, 0), (0, 0)])
            m.out([root, ring[j], ring[k]], mat, c, uv=[(0.05, 0), (0.1, 0.4), (0, 0.4)], uv2=[(1, 0), (0.55, 0), (0.55, 0)])


# ------------------------------------------------------------ rocks, cliffs
def column_stack(m, x, y, w, d, h, rnd, yaw=0.0):
    """A pile of stone blocks rising to h (courses 0.35-0.6 m, each block
    shifted a little), a snow cap on its top."""
    z = -0.2
    while z < h - 0.05:
        bh = min(rnd.uniform(0.45, 0.7), h - z)
        jx, jy = rnd.uniform(-0.1, 0.1), rnd.uniform(-0.1, 0.1)
        sw = w * rnd.uniform(0.92, 1.04)
        sd = d * rnd.uniform(0.92, 1.04)
        m.box((x + jx, y + jy, z + bh / 2), (sw, sd, bh), "stone", yaw + rnd.uniform(-0.04, 0.04))
        z += bh
    m.cap(Vector((x, y, z)), (w, d), yaw, rnd.uniform(0.16, 0.26), rnd)
    return z


def rock(name, cols, rnd, base_snow=True):
    """cols: (x, y, w, d, h) columns -- stepped stacks as the sheet's rocks."""
    m = Mesh(name)
    for c in cols:
        column_stack(m, *c, rnd)
    if base_snow:
        for _ in range(3):
            a = rnd.uniform(0, math.tau)
            r = max(max(c[2], c[3]) for c in cols) * 0.7
            m.mound((math.cos(a) * r, math.sin(a) * r, 0), rnd.uniform(0.3, 0.55), rnd.uniform(0.1, 0.2), seed=rnd.randint(0, 999))
    return m


def ice_overhang(name, rnd):
    m = Mesh(name)
    top = column_stack(m, 0, 0, 1.8, 1.4, 2.6, rnd)
    for i in range(14):
        x = -0.85 + i * 0.13 + rnd.uniform(-0.03, 0.03)
        m.icicle((x, -0.74, top - 0.02), rnd.uniform(0.4, 1.5) * (1.2 if i % 3 == 0 else 0.8), rnd.uniform(0.04, 0.08), rnd)
    for i in range(6):
        y = -0.6 + i * 0.22
        m.icicle((0.94, y, top - 0.02), rnd.uniform(0.3, 0.9), 0.05, rnd)
    return m


def ledge(name, rnd):
    m = Mesh(name)
    column_stack(m, 0, 0.3, 2.6, 1.2, 1.2, rnd)
    top = column_stack(m, 0, -0.2, 2.8, 1.0, 1.5, rnd)
    for i in range(6):
        m.icicle((-1.2 + i * 0.45 + rnd.uniform(-0.1, 0.1), -0.72, top - 0.02), rnd.uniform(0.2, 0.5), 0.04, rnd)
    return m


def stairs(name, rnd):
    m = Mesh(name)
    for i in range(5):
        z = i * 0.3
        m.box((0, i * 0.4, z / 2 + 0.05), (1.6, 0.42, z + 0.3), "stone")
        m.cap(Vector((0, i * 0.4, z + 0.2)), (1.6, 0.42), 0.0, 0.1, rnd, droop=False)
    return m


# ------------------------------------------------------------------- props
def snowed_box(m, c, size, mat, rnd, yaw=0.0, t=0.1, droop=True, axis=None):
    m.box(c, size, mat, yaw, axis=axis)
    m.cap(Vector(c) + Z * (size[2] / 2), (size[0], size[1]), yaw, t, rnd, droop)


def fence(rnd):
    m = Mesh("Fence")
    for x in (-1.1, 1.1):
        snowed_box(m, (x, 0, 0.55), (0.16, 0.16, 1.3), "wood", rnd, t=0.08, droop=False, axis=Z)
    for z in (0.45, 0.9):
        snowed_box(m, (0, 0, z), (2.3, 0.08, 0.14), "wood", rnd, t=0.06, axis=X)
    return m


def signpost(rnd):
    m = Mesh("Signpost")
    snowed_box(m, (0, 0, 1.0), (0.16, 0.16, 2.2), "wood", rnd, t=0.08, droop=False, axis=Z)
    for z, dx, yaw in ((1.75, 0.35, 0.0), (1.45, -0.3, 0.25)):
        snowed_box(m, (dx, 0, z), (0.8, 0.05, 0.22), "wood", rnd, yaw, t=0.05, droop=False, axis=X)
    m.mound((0, 0, 0), 0.45, 0.15, seed=3)
    return m


def bench(rnd):
    m = Mesh("Bench")
    for y in (-0.12, 0.0, 0.12):
        m.box((0, y, 0.45), (1.6, 0.11, 0.06), "wood", axis=X)
    m.cap(Vector((0, 0, 0.48)), (1.6, 0.35), 0.0, 0.08, rnd)
    for x in (-0.65, 0.65):
        for y in (-0.12, 0.12):
            m.box((x, y, 0.21), (0.08, 0.08, 0.45), "wood", axis=Z)
    m.box((0, 0.2, 0.75), (1.6, 0.05, 0.22), "wood", axis=X)
    m.cap(Vector((0, 0.2, 0.86)), (1.6, 0.05), 0.0, 0.05, rnd, droop=False)
    return m


def wheel(m, c, r, axis_dir):
    c = Vector(c)
    a = c - axis_dir * 0.05
    b = c + axis_dir * 0.05
    m.prism(a, b, r, r, 10, "wood", caps=True, capmat="wood")
    m.prism(a - axis_dir * 0.02, b + axis_dir * 0.02, r * 0.25, r * 0.25, 6, "iron")


def crate(m, c, s, rnd, yaw=0.0):
    c = Vector(c)
    m.box(c, (s, s, s), "wood", yaw, axis=X)
    for dz in (-s / 2 + 0.04, s / 2 - 0.04):   # frame boards
        m.box(c + Z * dz, (s + 0.02, s + 0.02, 0.06), "wood", yaw, axis=X)
    m.cap(c + Z * (s / 2), (s, s), yaw, 0.08, rnd)


def cart(rnd, broken=False):
    m = Mesh("BrokenCart" if broken else "CartCrates")
    tilt = (0.22, "Y") if broken else None
    m.box((0, 0, 0.62), (1.8, 1.0, 0.1), "wood", tilt=tilt, axis=X)
    for y in (-0.5, 0.5):
        m.box((0, y, 0.8), (1.8, 0.06, 0.3), "wood", tilt=tilt, axis=X)
    m.box((-0.9, 0, 0.8), (0.06, 1.0, 0.3), "wood", tilt=tilt, axis=Y)
    m.box((1.35, 0.3, 0.6), (1.0, 0.07, 0.07), "wood", 0.0, axis=X)
    m.box((1.35, -0.3, 0.6), (1.0, 0.07, 0.07), "wood", 0.0, axis=X)
    wheel(m, (0.2, -0.6, 0.42), 0.42, Y)
    if broken:
        m.prism((0.6, 0.95, 0.05), (0.6, 1.05, 0.05), 0.42, 0.42, 10, "wood", capmat="wood")   # a wheel off, flat
        m.box((-0.4, 0.8, 0.1), (0.9, 0.12, 0.05), "wood", 0.5, axis=X)                         # a broken board
        m.cap(Vector((0.4, 0, 0.9)), (1.2, 0.9), 0.0, 0.1, rnd)
    else:
        wheel(m, (0.2, 0.6, 0.42), 0.42, Y)
        crate(m, (-0.35, -0.15, 0.95), 0.55, rnd, 0.1)
        crate(m, (0.35, 0.18, 0.92), 0.5, rnd, -0.15)
        crate(m, (-0.2, 0.05, 1.45), 0.42, rnd, 0.35)
    m.mound((0.2, 0, 0), 0.8, 0.12, seed=21 if broken else 20)
    return m


def barrels(rnd):
    m = Mesh("Barrels")
    for x, s in ((-0.35, 1.0), (0.38, 0.92)):
        prof = [(0.26, 0.0), (0.31, 0.22), (0.33, 0.45), (0.31, 0.68), (0.26, 0.9)]
        for i in range(len(prof) - 1):
            (r0, z0), (r1, z1) = prof[i], prof[i + 1]
            m.prism((x, 0, z0 * s), (x, 0, z1 * s), r0 * s, r1 * s, 12, "wood", caps=False)
        for z in (0.12, 0.78):
            m.prism((x, 0, (z - 0.02) * s), (x, 0, (z + 0.03) * s), 0.335 * s * (0.95 if z > 0.5 else 0.97),
                    0.335 * s * (0.95 if z > 0.5 else 0.97), 12, "iron", caps=False)
        m.prism((x, 0, 0.9 * s - 0.01), (x, 0, 0.9 * s), 0.26 * s, 0.26 * s, 12, "logend", caps=True)
        m.cap(Vector((x, 0, 0.9 * s)), (0.42 * s, 0.42 * s), 0.3, 0.1, rnd)
    return m


def log_pile(rnd):
    m = Mesh("LogPile")
    rows = [(5, 0.16), (4, 0.43), (3, 0.7), (2, 0.97)]
    top = 0
    for n, z in rows:
        for i in range(n):
            x = (i - (n - 1) / 2) * 0.34
            r = 0.16 + rnd.uniform(-0.02, 0.02)
            m.prism((x, -0.7, z), (x, 0.7, z), r, r, 8, "bark", caps=True, capmat="logend", spin=rnd.uniform(0, 1))
            top = z + r
    m.cap(Vector((0, 0, top)), (0.9, 1.4), 0.0, 0.12, rnd)
    return m


def stump(rnd):
    m = Mesh("Stump")
    m.prism((0, 0, -0.2), (0, 0, 0.62), 0.42, 0.36, 8, "bark", caps=True, capmat="logend")
    for a in (0.3, 2.2, 4.1):
        m.prism((0, 0, 0.1), (math.cos(a) * 0.7, math.sin(a) * 0.7, -0.1), 0.12, 0.05, 5, "bark")
    m.cap(Vector((0, 0, 0.62)), (0.6, 0.6), 0.2, 0.14, rnd)
    m.mound((0, 0, 0), 0.7, 0.14, seed=5)
    return m


def stone_wall(rnd):
    m = Mesh("StoneWall")
    for row, z in enumerate((0.15, 0.45, 0.75)):
        x = -1.3 + (0.18 if row % 2 else 0.0)
        while x < 1.25:
            w = rnd.uniform(0.35, 0.6)
            w = min(w, 1.35 - x)
            m.box((x + w / 2, rnd.uniform(-0.03, 0.03), z), (w - 0.03, 0.55, 0.28), "stone", rnd.uniform(-0.03, 0.03))
            x += w
    m.cap(Vector((0, 0, 0.9)), (2.6, 0.55), 0.0, 0.14, rnd)
    return m


def snow_pile(rnd):
    m = Mesh("SnowPile")
    for i, (x, y, r, h) in enumerate([(0, 0, 0.7, 0.5), (0.5, 0.2, 0.45, 0.32), (-0.45, 0.25, 0.4, 0.28),
                                       (0.2, -0.45, 0.4, 0.26), (-0.3, -0.35, 0.35, 0.22)]):
        m.mound((x, y, 0), r, h, seed=i + 40)
    return m


def berries_bush(rnd):
    m = Mesh("BerriesBush")
    for i in range(7):
        a = i * math.tau / 7
        c = Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 0.32 + (i % 2) * 0.12))
        m.prism(c - Z * 0.2, c + Z * 0.2, 0.26, 0.14, 6, "frond", caps=True, spin=a,
                uv2=lambda p, cz=c.z: (max(0.0, min(1.0, (cz + 0.2 - p.z) / 0.4)), 0.0))
    m.prism((0, 0, 0.35), (0, 0, 0.72), 0.3, 0.12, 6, "frond", caps=True,
            uv2=lambda p: (max(0.0, min(1.0, (0.72 - p.z) / 0.37)), 0.0))
    for _ in range(18):
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(0.3, 0.55)
        m.box((math.cos(a) * r, math.sin(a) * r, rnd.uniform(0.2, 0.6)), (0.07, 0.07, 0.07), "berry")
    m.mound((0, 0, 0), 0.65, 0.1, seed=7)
    return m


def frozen_grass(rnd):
    m = Mesh("FrozenGrass")
    fronds(m, 13, 0.7, 0.9, rnd)
    m.mound((0, 0, 0), 0.4, 0.08, seed=9)
    return m


def shrub(rnd):
    m = Mesh("SnowShrub")
    fronds(m, 9, 1.1, 0.7, rnd)
    m.mound((0, 0, 0), 0.6, 0.12, seed=13)
    return m


def snow_bush(rnd):
    m = Mesh("SnowBush")
    for i, (x, y, s) in enumerate([(0, 0, 1.0), (0.4, 0.2, 0.7), (-0.38, 0.15, 0.65), (0.1, -0.35, 0.6)]):
        tiered(m, 3, 0.55 * s, 0.4 * s, 0.7, 6, 0.05, spacing=0.5, rim=0.1, twist=i)
        if i:
            for f in m.faces[-60:]:
                pass
    # the side clumps are offset copies: shift their faces after the fact
    m2 = Mesh("SnowBush")
    for i, (x, y, s) in enumerate([(0, 0, 1.0), (0.42, 0.22, 0.7), (-0.4, 0.18, 0.65), (0.12, -0.38, 0.6)]):
        tmp = Mesh("tmp")
        tiered(tmp, 3, 0.55 * s, 0.42 * s, 0.7, 6, 0.05, spacing=0.5, rim=0.1, twist=i)
        for pts, mat, uv, uv2 in tmp.faces:
            m2.faces.append(([p + Vector((x, y, 0)) for p in pts], mat, uv, uv2))
    m2.mound((0, 0, 0), 0.8, 0.12, seed=15)
    return m2


# --------------------------------------------------------------- buildings
def lantern(rnd):
    """The sheet's lantern (snow): a post, an arm out to the front (-Y), a
    brace, an iron-framed lantern of warm glass; snow on the post top, the arm
    and the lantern's roof. The light is the game's (at 0, -0.78, 2.45). In
    the kit so it ghosts when it stands between the camera and the player."""
    m = Mesh("Lantern")
    snowed_box(m, (0, 0, 1.55), (0.2, 0.2, 3.1), "wood", rnd, t=0.07, droop=False, axis=Z)
    snowed_box(m, (0, -0.42, 2.95), (0.12, 0.95, 0.12), "wood", rnd, t=0.05, droop=False, axis=Y)
    m.box((0, -0.2, 2.72), (0.08, 0.5, 0.08), "wood", tilt=(0.7, "X"), axis=Y)
    lamp = Vector((0, -0.78, 2.45))
    m.box(lamp + Z * 0.39, (0.03, 0.03, 0.14), "iron")
    m.box(lamp + Z * 0.26, (0.44, 0.44, 0.08), "iron")
    m.cap(lamp + Z * 0.3, (0.44, 0.44), 0.0, 0.06, rnd, droop=False)
    m.box(lamp - Z * 0.24, (0.36, 0.36, 0.06), "iron")
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        m.box(lamp + Vector((dx * 0.16, dy * 0.16, 0)), (0.04, 0.04, 0.46), "iron", axis=Z)
    m.box(lamp, (0.28, 0.28, 0.4), "glass")
    m.mound((0, 0, 0), 0.4, 0.12, seed=31)
    return m


def slab(m, pts, t, mat, centre, uv2=None):
    """A sloped slab: top face `pts` (4 points) and the same moved down t."""
    top = [Vector(p) for p in pts]
    bot = [p - Z * t for p in top]
    f = uv2 or (lambda p: (0.0, 0.0))
    m.out(top, mat, centre, uv2=[f(p) for p in top])
    m.out(bot, mat, centre + Z * 50, uv2=[f(p) for p in bot])
    for k in range(4):
        j = (k + 1) % 4
        q = [top[k], top[j], bot[j], bot[k]]
        m.out(q, mat, centre, uv2=[f(p) for p in q])


def cabin(rnd):
    """The sheet's village-outskirts cabin: log walls crossing at the corners
    on a stone plinth, a plank door, warm windows with snowy sills, a steep
    plank roof under a thick drooping snow load with icicles on the eaves, a
    stone chimney. Front (door) toward -Y."""
    m = Mesh("Cabin")
    W, D, H, r = 6.0, 5.0, 2.7, 0.17
    m.box((0, 0, -0.55), (W + 0.3, D + 0.3, 1.5), "stone")
    doors = [(-0.55, 0.55, 0.0, 2.1)]
    wins = [(-2.35, -1.25, 0.9, 1.8), (1.25, 2.35, 0.9, 1.8)]
    n = int(H / (2 * r))
    for i in range(n):
        z = 0.2 + r + i * 2 * r
        # front wall, cut round the door and windows
        cuts = sorted((a, b) for a, b, z0, z1 in doors + wins if z0 < z < z1)
        x0 = -W / 2 - 0.25
        for a, b in cuts + [(W / 2 + 0.25, W / 2 + 0.25)]:
            if a - x0 > 0.1:
                m.prism((x0, -D / 2, z), (a, -D / 2, z), r, r, 6, "bark", capmat="logend")
            x0 = b
        m.prism((-W / 2 - 0.25, D / 2, z), (W / 2 + 0.25, D / 2, z), r, r, 6, "bark", capmat="logend")
        zs = z + r
        for x in (-W / 2, W / 2):
            if zs < 0.9 + 0.1 or zs > 1.8 or True:
                m.prism((x, -D / 2 - 0.25, zs), (x, D / 2 + 0.25, zs), r, r, 6, "bark", capmat="logend")
    top = 0.2 + n * 2 * r
    # door, windows (warm glass, a cross of muntins in the shader), sills
    m.box((0, -D / 2 + 0.06, 1.05), (1.0, 0.1, 2.0), "wood", axis=Z)
    m.box((0, -D / 2 - 0.02, 2.12), (1.3, 0.14, 0.14), "wood", axis=X)
    for a, b, z0, z1 in wins:
        cx = (a + b) / 2
        m.box((cx, -D / 2 + 0.04, (z0 + z1) / 2), (b - a - 0.08, 0.06, z1 - z0 - 0.08), "glass")
        snowed_box(m, (cx, -D / 2 - 0.08, z0 - 0.05), (b - a + 0.2, 0.2, 0.08), "wood", rnd, t=0.07, axis=X)
        m.box((cx, -D / 2 - 0.03, z1 + 0.04), (b - a + 0.2, 0.12, 0.1), "wood", axis=X)
    # gable ends
    rise = D / 2 * math.tan(math.radians(40))
    for x in (-W / 2 - 0.02, W / 2 + 0.02):
        m.out([(x, -D / 2 - 0.1, top), (x, D / 2 + 0.1, top), (x, 0, top + rise)], "wood",
              (0, 0, top), axis=Z)
    # the roof: two plank slabs overhanging, a thick snow load on each
    ov, og = 0.55, 0.45
    for s in (-1, 1):
        eave = Vector((0, s * (D / 2 + ov), top - ov * math.tan(math.radians(40))))
        ridge = Vector((0, 0, top + rise + 0.05))
        q = [Vector((-W / 2 - og, eave.y, eave.z)), Vector((W / 2 + og, eave.y, eave.z)),
             Vector((W / 2 + og, 0, ridge.z)), Vector((-W / 2 - og, 0, ridge.z))]
        slab(m, [p + Z * 0.16 for p in q], 0.16, "wood", Vector((0, 0, top)))
        sn = [p + Z * 0.46 for p in q]
        slab(m, sn, 0.3, "snow", Vector((0, 0, top)), uv2=lambda p, qz=q: (0.0, 0.3 if p.z > min(v.z for v in qz) + 0.4 else 0.3))
        # the load drooping over the eave, and icicles under it
        for i in range(9):
            x = -W / 2 - og + 0.3 + i * (W + 2 * og - 0.6) / 8 + rnd.uniform(-0.15, 0.15)
            e = Vector((x, eave.y + s * 0.05, eave.z + 0.3))
            m.box(e - Z * 0.12, (rnd.uniform(0.3, 0.55), 0.28, 0.3), "snow", 0.0,
                  uv2=lambda p, zz=e.z: (0.0, 0.3))
            if rnd.random() < 0.8:
                m.icicle(e - Z * 0.28 + Vector((rnd.uniform(-0.1, 0.1), 0, 0)), rnd.uniform(0.25, 0.7), 0.045, rnd)
    # chimney
    ch = Vector((W / 2 - 1.1, 0.9, 0))
    m.box(ch + Z * (top + rise * 0.5 + 0.2), (0.75, 0.75, rise + 1.8), "stone")
    m.cap(ch + Z * (top + rise * 0.5 + 0.2 + (rise + 1.8) / 2), (0.75, 0.75), 0.0, 0.14, rnd)
    # snow banked against the walls
    for x, y in ((-W / 2, -D / 2), (W / 2, -D / 2), (-W / 2, D / 2), (W / 2, D / 2), (0, D / 2)):
        m.mound((x, y, 0.1), rnd.uniform(0.6, 1.1), rnd.uniform(0.25, 0.45), seed=rnd.randint(0, 999))
    return m


def castle(rnd):
    """The sheet's cliff-edge castle, to stand in the mist: a curtain wall
    round a 30 m court, four round towers with slate cones, a tall keep with a
    turret, merlons on everything, a few lit windows. Everything runs 6 m
    below the foot so it can stand on a slope."""
    m = Mesh("Castle")
    tau = math.tau

    def merlons(pts_dirs, z):
        for p, a in pts_dirs:
            m.box((p[0], p[1], z + 0.55), (0.9, 0.8, 1.1), "stone", a)

    def tower(x, y, r, h, n=8):
        m.prism((x, y, -6), (x, y, h), r, r * 0.92, n, "stone")
        merlons([((x + math.cos(k * tau / n) * r * 0.9, y + math.sin(k * tau / n) * r * 0.9), k * tau / n) for k in range(n)], h)
        m.prism((x, y, h + 0.3), (x, y, h + 0.3 + r * 1.9), r * 1.08, 0.06, n, "slate", caps=False)
        for z in (h * 0.45, h * 0.7):
            a = rnd.uniform(0, tau)
            m.box((x + math.cos(a) * r * 0.93, y + math.sin(a) * r * 0.93, z), (0.3, 0.3, 1.1), "glass", a)

    S = 15.0
    for x, y in ((-S, -S), (S, -S), (S, S), (-S, S)):
        tower(x, y, 3.4, 19.0)
    for (x0, y0), (x1, y1) in (((-S, -S), (S, -S)), ((S, -S), (S, S)), ((S, S), (-S, S)), ((-S, S), (-S, -S))):
        c = Vector(((x0 + x1) / 2, (y0 + y1) / 2, 0))
        along = Vector((x1 - x0, y1 - y0, 0)).normalized()
        L = 2 * S - 6.0
        yaw = math.atan2(along.y, along.x)
        m.box(c + Z * 3.0, (L, 2.4, 18.0), "stone", yaw)
        m.cap(c + Z * 12.0, (L, 2.4), yaw, 0.25, rnd)
        merlons([((c + along * (i - L / 2)).to_2d(), yaw) for i in [k * 1.8 for k in range(int(L / 1.8) + 1)]], 12.0)
    # the gate, dark, on the front wall
    m.box((0, -S - 1.25, 2.5), (4.0, 0.3, 5.0), "iron")
    # the keep and its turret
    m.box((0, 3, 7.0), (12, 12, 26), "stone")
    m.cap(Vector((0, 3, 20.0)), (12, 12), 0.0, 0.3, rnd)
    merlons([((x, 3 - 6), 0.0) for x in range(-5, 6, 2)] + [((x, 3 + 6), 0.0) for x in range(-5, 6, 2)]
            + [((-6, y), math.pi / 2) for y in range(-2, 9, 2)] + [((6, y), math.pi / 2) for y in range(-2, 9, 2)], 20.0)
    for z in (8.0, 12.0, 16.0):
        for x in (-3.0, 0.0, 3.0):
            m.box((x, -3.06, z), (0.5, 0.1, 1.4), "glass")
    tower(4.0, 7.0, 2.4, 29.0)
    return m


def ruin_arch(rnd):
    """The sheet's ruins: two block pillars and a stone arch between them,
    snow on the pillar tops and the crown, rubble at the feet."""
    m = Mesh("RuinArch")
    R, zc = 1.7, 3.3
    for x in (-R, R):
        column_stack(m, x, 0, 0.9, 0.9, zc, rnd)
    for k in range(9):
        a = math.pi * (k + 0.5) / 9
        c = Vector((-math.cos(a) * R, 0, zc + math.sin(a) * R * 0.95))
        m.box(c, (0.6, 0.9, 0.46), "stone", tilt=(-(math.pi / 2 - a), "Y"))
    m.cap(Vector((0, 0, zc + R * 0.95 + 0.23)), (0.62, 0.9), 0.0, 0.14, rnd, droop=False)
    for _ in range(5):
        m.box((rnd.uniform(-2.6, 2.6), rnd.uniform(-1.2, 1.2), 0.15), (rnd.uniform(0.3, 0.6), rnd.uniform(0.3, 0.5), 0.3),
              "stone", rnd.uniform(0, 3))
    m.mound((-R, 0.3, 0), 0.8, 0.2, seed=51)
    m.mound((R, -0.3, 0), 0.8, 0.2, seed=52)
    return m


def ruin_pillar(rnd):
    m = Mesh("RuinPillar")
    m.box((0, 0, 0.1), (1.3, 1.3, 0.5), "stone")
    z = 0.35
    for i, h in enumerate((0.75, 0.7, 0.55)):
        r = 0.45 - i * 0.02
        m.prism((0, 0, z), (0, 0, z + h), r, r, 8, "stone", spin=i * 0.3)
        z += h
    m.cap(Vector((0, 0, z)), (0.8, 0.8), 0.2, 0.14, rnd)
    m.prism((1.0, -0.6, 0.35), (2.3, -0.3, 0.35), 0.42, 0.42, 8, "stone")    # a fallen drum
    m.cap(Vector((1.65, -0.45, 0.76)), (1.2, 0.5), 0.23, 0.1, rnd, droop=False)
    m.mound((0.5, 0.4, 0), 0.9, 0.18, seed=53)
    return m


def ruin_wall(rnd):
    """A broken wall 5 m long: stone blocks in columns of ragged height, an
    arched window through it, snow on every broken top."""
    m = Mesh("RuinWall")
    x = -2.5
    while x < 2.5:
        w = min(rnd.uniform(0.45, 0.7), 2.5 - x)
        top = rnd.uniform(1.6, 3.4)
        z = -0.3
        while z < top - 0.05:
            bh = min(rnd.uniform(0.4, 0.55), top - z)
            in_window = 0.4 < x + w / 2 < 1.6 and 1.0 < z + bh / 2 < 2.3
            if not in_window:
                m.box((x + w / 2, rnd.uniform(-0.04, 0.04), z + bh / 2), (w - 0.03, 0.8, bh), "stone")
            z += bh
        m.cap(Vector((x + w / 2, 0, z)), (w - 0.03, 0.8), 0.0, 0.14, rnd)
        x += w
    m.mound((-1.8, -0.6, 0), 0.9, 0.22, seed=54)
    return m


# ------------------------------------------------------------------ output
def preview(rows):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_backface_culling = True
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 1500, 520
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    sc.collection.objects.link(cam)
    sc.camera = cam
    os.makedirs(REN, exist_ok=True)
    everything = [o for row in rows.values() for o in row]
    for tag, row in rows.items():
        for o in everything:
            o.hide_render = o not in row
        x = 0.0
        for o in row:
            w = max(o.dimensions.x, o.dimensions.y)
            o.location = (x + w / 2, 0, 0)
            x += w + 0.8
        h = max(o.dimensions.z for o in row)
        cam.data.ortho_scale = max(x, h * 3.0) * 1.02
        centre = Vector((x / 2, 0, h * 0.42))
        d = Vector((0.35, -1, 0.35)).normalized()
        cam.location = centre + d * 60
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(REN, f"kit_{tag}.png")
        bpy.ops.render.render(write_still=True)
    for o in everything:
        o.location = (0, 0, 0)
        o.hide_render = False


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rnd = random.Random(1234)
    trees = []
    # (sheet: width ~0.6 of the height, a clear trunk under the lowest tier)
    for name, args in [("PineLarge", (5, 2.25, 1.6, 0.76, 0.48, 1.45)), ("PineMedium", (4, 1.85, 1.45, 0.74, 0.40, 1.25)),
                       ("PineSmall", (3, 1.45, 1.3, 0.72, 0.33, 1.05)), ("PineYoung", (4, 0.95, 0.95, 0.76, 0.18, 0.8)),
                       ("Sapling", (3, 0.5, 0.55, 0.74, 0.08, 0.4))]:
        m, tip = pine(name, *args, seed=len(trees))
        trees.append(m)
        print(f"{name}: {tip:.2f} m")
    sparse, tip = pine("PineSparse", 5, 1.5, 1.0, 0.8, 0.24, 1.5, sides=5, spacing=0.95, seed=8)
    trees.append(sparse)
    rows = {"trees": trees + [dead_tree("DeadTree", rnd), shrub(rnd), snow_bush(rnd)],
            "rocks": [rock("RockSmall", [(0, 0, 0.8, 0.8, 1.0), (0.45, -0.1, 0.55, 0.6, 0.55)], rnd),
                      rock("RockMedium", [(0, 0, 1.0, 0.9, 1.9), (0.6, 0.1, 0.7, 0.8, 1.2), (-0.5, -0.1, 0.6, 0.7, 0.8)], rnd),
                      rock("RockLarge", [(0, 0, 1.1, 1.0, 2.9), (0.75, 0.1, 0.8, 0.9, 2.0), (-0.65, 0.0, 0.7, 0.8, 1.3), (0.2, -0.6, 0.7, 0.5, 0.8)], rnd),
                      rock("CliffModule", [(-0.6, 0, 1.3, 1.3, 3.8), (0.7, 0.1, 1.4, 1.2, 2.6), (0.2, -0.8, 1.0, 0.6, 1.2)], rnd),
                      ledge("SnowyLedge", rnd), ice_overhang("IceOverhang", rnd), stairs("Stairs", rnd)],
            "props": [fence(rnd), signpost(rnd), bench(rnd), cart(rnd), cart(rnd, broken=True), barrels(rnd),
                      frozen_grass(rnd), berries_bush(rnd), snow_pile(rnd), log_pile(rnd), stump(rnd), stone_wall(rnd)],
            "build": [lantern(rnd), cabin(rnd), ruin_arch(rnd), ruin_pillar(rnd), ruin_wall(rnd)],
            "castle": [castle(rnd)]}
    built = {k: [m.build() for m in v] for k, v in rows.items()}
    obs = [o for row in built.values() for o in row]
    for o in obs:
        print(f"  {o.name:<12} tris {sum(len(p.vertices) - 2 for p in o.data.polygons):5d}  "
              f"{o.dimensions.x:.1f} x {o.dimensions.y:.1f} x {o.dimensions.z:.1f} m")
    os.makedirs(OUT, exist_ok=True)
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "snowkit.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    print("snowkit: exported", len(obs))
    preview(built)


if __name__ == "__main__":   # desertkit imports the Mesh helpers
    main()
