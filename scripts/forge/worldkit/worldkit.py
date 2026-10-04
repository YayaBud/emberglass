"""The world kit (implementation_plan 2026-09-28): what the breakables and the four new
regions are built from, in the Hoarfells kit's style -- chunky, faceted, shaded per pixel by
material name -- so every region reads as one game.

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background --factory-startup \\
        --python D:/assests/scripts/forge/worldkit/worldkit.py

Writes game/assets/models/worldkit/worldkit.glb (one object per asset) and
renders/worldkit/kit_*.png. Uses snowkit's Mesh and desertkit's lathe and pot.

Breakables (Phase A): Pot, Jar, Crate, Barrel, HayBale. ONE object each, foot at the origin:
`Breakables` hides a single instance when it is hit, so a group would vanish whole.

Materials are NAMES; the game's `Kit` shades each (UVs in metres). New here: straw (stalks
in 1-texel columns). Snow caps (snowkit's `cap`) are drawn only where the instance carries
snow, i.e. in the Hoarfells.
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
sys.path.insert(0, os.path.join(HERE, "..", "desertkit"))
import snowkit as sk  # noqa: E402
import desertkit as dk  # noqa: E402  (sets sk.REN; ours is set below)
from snowkit import Mesh, X, Y, Z  # noqa: E402

OUT = os.path.join(sk.ROOT, "game", "assets", "models", "worldkit")
sk.REN = os.path.join(sk.ROOT, "renders", "worldkit")
sk.COLS.update({  # preview colours only
    "straw": (0.78, 0.64, 0.34), "thatch": (0.60, 0.48, 0.27), "earth": (0.30, 0.22, 0.15),
    "leaf": (0.25, 0.46, 0.20),
})


# -------------------------------------------------------------- breakables
def pot(rnd):
    m = Mesh("Pot")
    dk.pot(m, (0, 0, 0), 1.0, rnd)
    return m


def jar(rnd):
    """A tall storage jar: narrow foot, high shoulder, two loop handles."""
    m = Mesh("Jar")
    dk.lathe(m, [(0.0, 0.11), (0.1, 0.18), (0.42, 0.27), (0.66, 0.24), (0.8, 0.13), (0.9, 0.11), (0.93, 0.14),
                 (0.95, 0.12), (0.82, 0.08)], 10, "clay", spin=rnd.uniform(0, 1))
    for s in (-1, 1):
        m.prism((s * 0.22, 0, 0.64), (s * 0.24, 0, 0.82), 0.025, 0.025, 4, "clay")
        m.prism((s * 0.24, 0, 0.82), (s * 0.12, 0, 0.86), 0.025, 0.025, 4, "clay")
    return m


def crate(rnd):
    """A 0.7 m crate: plank sides, frame boards top and bottom, a diagonal brace on the
    two faces the camera sees."""
    m = Mesh("Crate")
    s = 0.7
    c = Vector((0, 0, s / 2))
    m.box(c, (s, s, s), "wood", 0.0, axis=X)
    for dz in (-s / 2 + 0.04, s / 2 - 0.04):
        m.box(c + Z * dz, (s + 0.02, s + 0.02, 0.06), "wood", 0.0, axis=X)
    for dx, dy, ax in ((0, -s / 2 - 0.012, X), (s / 2 + 0.012, 0, Y)):
        m.box(Vector((dx, dy, s / 2)), (0.06 if ax is Y else 0.86, 0.86 if ax is Y else 0.06, 0.07), "wood",
              0.0, axis=ax, tilt=(math.radians(45), "Y" if ax is X else "X"))
    m.cap(c + Z * (s / 2), (s, s), 0.0, 0.08, rnd)
    return m


def barrel(rnd):
    m = Mesh("Barrel")
    prof = [(0.26, 0.0), (0.31, 0.22), (0.33, 0.45), (0.31, 0.68), (0.26, 0.9)]
    for i in range(len(prof) - 1):
        (r0, z0), (r1, z1) = prof[i], prof[i + 1]
        m.prism((0, 0, z0), (0, 0, z1), r0, r1, 12, "wood", caps=False)
    for z in (0.12, 0.78):
        r = 0.335 * (0.95 if z > 0.5 else 0.97)
        m.prism((0, 0, z - 0.02), (0, 0, z + 0.03), r, r, 12, "iron", caps=False)
    m.prism((0, 0, -0.005), (0, 0, 0.005), 0.26, 0.26, 12, "logend", caps=True)
    m.prism((0, 0, 0.89), (0, 0, 0.9), 0.26, 0.26, 12, "logend", caps=True)
    m.cap(Vector((0, 0, 0.9)), (0.42, 0.42), 0.3, 0.1, rnd)
    return m


def hay_bale(rnd):
    """A square bale, 1.1 x 0.55 x 0.45 m, two bands of twine, loose straw at the foot."""
    m = Mesh("HayBale")
    m.box((0, 0, 0.225), (1.1, 0.55, 0.45), "straw", 0.0, axis=X)
    for x in (-0.28, 0.28):
        m.box((x, 0, 0.225), (0.04, 0.57, 0.47), "bark", 0.0, axis=Y)
    for _ in range(5):
        a = rnd.uniform(0, math.tau)
        p = Vector((math.cos(a) * 0.6, math.sin(a) * 0.34, 0.01))
        m.box(p, (rnd.uniform(0.15, 0.3), 0.03, 0.02), "straw", a + 1.2, axis=X)
    m.cap(Vector((0, 0, 0.45)), (1.1, 0.55), 0.0, 0.09, rnd)
    return m


# --------------------------------------------------------------- helpers
def slab_roof(m, cx, cy, ridge_z, length, run, pitch_deg, mat, t=0.2, overhang=0.35):
    """A pitched roof, ridge along X at (cx, cy, ridge_z): two slabs `run` metres down the
    slope each side, turned about X (positive raises the +Y side)."""
    a = math.radians(pitch_deg)
    for s in (-1, 1):
        c = Vector((cx, cy + s * math.cos(a) * run / 2, ridge_z - math.sin(a) * run / 2))
        m.box(c, (length + 2 * overhang, run + overhang, t), mat, 0.0, axis=Y, tilt=(-s * a, "X"))


def gable(m, x, y0, y1, z0, z1, mat):
    m.out([Vector((x, y0, z0)), Vector((x, y1, z0)), Vector((x, (y0 + y1) / 2, z1))], mat,
          Vector((0, (y0 + y1) / 2, (z0 + z1) / 2)))


# ------------------------------------------------------------- the Emberwood
def wood_shed(rnd):
    """A woodcutter's lean-to: four posts, a plank roof falling to the back, a log back
    wall, a stack of cut logs inside."""
    m = Mesh("WoodShed")
    for x in (-1.6, 1.6):
        for y, h in ((-1.0, 2.5), (1.0, 1.9)):
            m.box((x, y, h / 2), (0.18, 0.18, h), "wood", axis=Z)
    m.box((0, 0, 2.25), (3.9, 2.7, 0.1), "wood", 0.0, axis=X, tilt=(math.radians(-13), "X"))
    for i in range(6):
        z = 0.16 + i * 0.3
        m.prism((-1.65, 1.05, z), (1.65, 1.05, z), 0.15, 0.15, 7, "bark", capmat="logend", spin=rnd.uniform(0, 1))
    for z, n in ((0.15, 4), (0.43, 3), (0.71, 2)):
        for i in range(n):
            x = (i - (n - 1) / 2) * 0.32 - 0.5
            m.prism((x, -0.7, z), (x, 0.6, z), 0.15, 0.15, 7, "bark", capmat="logend", spin=rnd.uniform(0, 1))
    return m


def chopping_block(rnd):
    m = Mesh("ChoppingBlock")
    m.prism((0, 0, 0), (0, 0, 0.5), 0.32, 0.29, 8, "bark", capmat="logend")
    m.prism((0.05, 0, 0.5), (0.36, 0.1, 0.96), 0.03, 0.03, 5, "wood")
    m.box((0.03, -0.01, 0.53), (0.2, 0.04, 0.13), "iron", 0.3)
    for a in (0.5, 2.1, 3.9, 5.0):
        m.box((math.cos(a) * 0.7, math.sin(a) * 0.7, 0.08), (0.42, 0.15, 0.15), "logend", a, axis=X)
    return m


def charcoal_mound(rnd):
    """A charcoal burner's clamp: a turf-covered dome with a vent (the site hangs smoke on it)."""
    m = Mesh("CharcoalMound")
    dk.lathe(m, [(0, 1.7), (0.5, 1.5), (1.0, 1.05), (1.3, 0.55), (1.42, 0.14)], 12, "earth")
    m.prism((0, 0, 1.36), (0, 0, 1.52), 0.13, 0.1, 6, "shade")
    for a in (0.3, 1.9, 3.6, 5.1):
        m.box((math.cos(a) * 1.75, math.sin(a) * 1.75, 0.12), (0.5, 0.14, 0.14), "bark", a, axis=X)
    return m


def shrine(rnd):
    """A wayside shrine in the wood: a plinth, four pillars, a slate pyramid roof, a lantern
    burning inside -- the Emberwood's anomaly and its lit point."""
    m = Mesh("Shrine")
    m.box((0, 0, 0.2), (1.8, 1.8, 0.4), "stone", axis=X)
    for x in (-0.65, 0.65):
        for y in (-0.65, 0.65):
            m.box((x, y, 1.25), (0.22, 0.22, 1.7), "stone", axis=Z)
    top = Vector((0, 0, 3.0))
    c = [Vector((sx * 1.15, sy * 1.15, 2.1)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for i in range(4):
        m.out([c[i], c[(i + 1) % 4], top], "slate", Vector((0, 0, 2.3)))
    m.out(c, "wood", Vector((0, 0, 2.8)))
    m.box((0, 0, 0.66), (0.32, 0.32, 0.52), "iron")
    m.box((0, 0, 0.69), (0.24, 0.24, 0.38), "glass")
    return m


def trunk_arch(rnd):
    """A giant fallen trunk resting across a glade on its root plate and a broken stump."""
    m = Mesh("TrunkArch")
    m.prism((-5.5, 0, 3.0), (5.0, 0.3, 2.2), 1.1, 0.9, 10, "bark", capmat="logend")
    for i in range(11):
        a = i / 11 * math.tau
        m.prism((-5.6, 0, 3.0), (-5.7, math.cos(a) * 2.3, 3.0 + math.sin(a) * 2.3), 0.3, 0.08, 5, "bark")
    m.prism((-5.6, 0, 0), (-5.6, 0, 2.2), 0.8, 0.9, 8, "earth")
    m.prism((5.0, 0.3, 0), (5.0, 0.3, 2.0), 0.9, 0.8, 9, "bark", capmat="logend")
    return m


# ----------------------------------------------------------------- Duskfen
def boardwalk(rnd):
    """4 m of plank walk on posts; its foot is the water line, the deck 0.4 m over it, the
    posts reaching 2 m down (FenSite gives it its collider)."""
    m = Mesh("Boardwalk")
    for i in range(12):
        x = -2 + (i + 0.5) * (4 / 12)
        m.box((x, rnd.uniform(-0.04, 0.04), 0.4), (0.3, 1.4 + rnd.uniform(-0.12, 0.12), 0.07), "wood",
              rnd.uniform(-0.03, 0.03), axis=Y)
    for x in (-1.9, 1.9):
        m.box((x, 0, 0.33), (0.12, 1.5, 0.12), "wood", axis=Y)
        for y in (-0.62, 0.62):
            m.prism((x, y, -2.0), (x, y, 0.45), 0.08, 0.08, 6, "bark", capmat="logend")
    return m


def stilt_hut(rnd):
    """A fisher's hut on stilts: platform, plank walls, a lit window, a thatch roof."""
    m = Mesh("StiltHut")
    for x in (-1.6, 1.6):
        for y in (-1.4, 1.4):
            m.prism((x, y, -2.0), (x, y, 1.0), 0.1, 0.1, 6, "bark", capmat="logend")
    m.box((0, 0, 1.0), (3.8, 3.4, 0.15), "wood", axis=X)
    m.box((0, 0.3, 1.93), (3.0, 2.4, 1.7), "wood", axis=Z)
    m.box((0.6, -0.92, 1.7), (0.7, 0.04, 1.2), "shade")
    m.box((-0.8, -0.92, 2.0), (0.5, 0.04, 0.4), "glass")
    slab_roof(m, 0, 0.3, 3.55, 3.0, 1.9, 38, "thatch", t=0.18)
    for x in (-1.5, 1.5):
        gable(m, x, -0.9, 1.5, 2.78, 3.55, "wood")
    return m


def drowned_chapel(rnd):
    """The Fen's landmark ("the water remembers what stood here"): a chapel tower standing
    in the water, its crown broken, a stub of the nave running back."""
    m = Mesh("DrownedChapel")
    m.box((0, 0, 4.5), (3.2, 3.2, 9.0), "stone", axis=Z)
    for x, y in ((-1.2, -1.2), (1.2, -1.2), (1.2, 1.2), (-1.2, 1.2), (0, -1.25), (1.25, 0)):
        h = rnd.uniform(0.3, 1.5)
        m.box((x, y, 9 + h / 2), (0.8, 0.8, h), "stone", axis=Z)
    for z in (4.6, 7.3):
        m.box((0, -1.62, z), (0.7, 0.06, 1.3), "shade")
        m.box((1.62, 0, z), (0.06, 0.7, 1.3), "shade")
    m.box((-0.6, 4.6, 1.6), (0.6, 6.0, 3.2), "stone", axis=Y)
    for i in range(4):
        h = rnd.uniform(0.2, 0.9)
        m.box((-0.6, 2.4 + i * 1.4, 3.2 + h / 2), (0.6, 1.0, h), "stone")
    return m


def lily_pads(rnd):
    m = Mesh("LilyPads")
    for _ in range(8):
        c = Vector((rnd.uniform(-1.3, 1.3), rnd.uniform(-1.0, 1.0), 0.02))
        r = rnd.uniform(0.18, 0.36)
        a0 = rnd.uniform(0, math.tau)
        pts = [c + Vector((math.cos(a0 + k / 10 * math.tau) * r, math.sin(a0 + k / 10 * math.tau) * r, 0)) for k in range(10)]
        for k in range(8):   # a notch where the last slice would be
            m.out([c, pts[k], pts[k + 1]], "leaf", c - Z)
    for _ in range(3):
        c = Vector((rnd.uniform(-1.0, 1.0), rnd.uniform(-0.8, 0.8), 0.06))
        m.box(c, (0.1, 0.1, 0.08), "bloom", rnd.uniform(0, 1))
    return m


# ---------------------------------------------------------- Elder Meadows
def farmhouse(rnd):
    """A farmhouse: stone ground floor, whitewashed timber upper, a deep thatch, a chimney,
    lit windows on the camera's side."""
    m = Mesh("Farmhouse")
    m.box((0, 0, 1.2), (6.0, 4.6, 2.4), "stone", axis=X)
    m.box((0, 0, 3.2), (6.0, 4.6, 1.6), "whitewash", axis=X)
    for x in (-3.0, -1.5, 0.0, 1.5, 3.0):
        m.box((x, -2.33, 3.2), (0.16, 0.08, 1.6), "wood", axis=Z)
    for z in (2.45, 3.95):
        m.box((0, -2.33, z), (6.1, 0.08, 0.14), "wood", axis=X)
    slab_roof(m, 0, 0, 6.0, 6.0, 3.2, 40, "thatch", t=0.3)
    for x in (-3.0, 3.0):
        gable(m, x, -2.3, 2.3, 4.0, 5.9, "whitewash")
    m.box((2.2, 1.0, 5.6), (0.6, 0.6, 1.9), "stone", axis=Z)
    m.box((0.4, -2.33, 1.0), (1.0, 0.06, 2.0), "wood", axis=Z)
    for x, z in ((-1.8, 1.4), (2.0, 1.4), (-0.75, 3.25), (0.75, 3.25)):
        m.box((x, -2.33, z), (0.7, 0.06, 0.6), "glass")
    return m


def haystack(rnd):
    m = Mesh("Haystack")
    dk.lathe(m, [(0, 1.3), (0.8, 1.45), (1.7, 1.2), (2.5, 0.7), (2.9, 0.2), (3.0, 0.02)], 12, "straw",
             spin=rnd.uniform(0, 1))
    m.prism((0, 0, 2.7), (0, 0, 3.4), 0.05, 0.04, 5, "wood")
    return m


def scarecrow(rnd):
    m = Mesh("Scarecrow")
    m.prism((0, 0, -0.3), (0, 0, 1.9), 0.05, 0.05, 6, "wood")
    m.box((0, 0, 1.5), (1.4, 0.07, 0.07), "wood", axis=X)
    m.box((0, 0, 1.2), (0.5, 0.26, 0.7), "cloth2", axis=Z)
    for s in (-1, 1):
        m.box((s * 0.45, 0, 1.48), (0.45, 0.2, 0.2), "cloth2", axis=X)
        m.box((s * 0.72, 0, 1.4), (0.08, 0.12, 0.2), "straw", axis=Z)
    m.box((0, 0, 1.78), (0.28, 0.26, 0.3), "burlap", 0.1)
    m.prism((0, 0, 1.92), (0, 0, 1.96), 0.3, 0.3, 8, "straw")
    m.prism((0, 0, 1.96), (0, 0, 2.18), 0.15, 0.08, 8, "straw")
    return m


def beehives(rnd):
    """Three straw skeps on a plank bench."""
    m = Mesh("Beehives")
    m.box((0, 0, 0.45), (2.1, 0.6, 0.08), "wood", axis=X)
    for x in (-0.9, 0.9):
        m.box((x, 0, 0.22), (0.1, 0.5, 0.44), "wood", axis=Y)
    for x in (-0.65, 0.0, 0.65):
        dk.lathe(m, [(0.49, 0.26), (0.7, 0.27), (0.88, 0.2), (0.98, 0.1), (1.02, 0.02)], 10, "straw",
                 base=(x, 0, 0), spin=rnd.uniform(0, 1))
        m.box((x, -0.27, 0.53), (0.08, 0.02, 0.05), "shade")
    return m


# ---------------------------------------------------------- Greyward Crags
def watchtower(rnd):
    """The Crags' landmark on the bluff: a round stone tower, crenellated, a slate cap on a
    timber hoard, a lit window facing the camera."""
    m = Mesh("Watchtower")
    dk.lathe(m, [(0, 2.5), (0.6, 2.3), (9.0, 2.1), (9.3, 2.35)], 12, "stone", top=True)
    for k in range(10):
        a = k / 10 * math.tau
        m.box((math.cos(a) * 2.2, math.sin(a) * 2.2, 9.65), (0.6, 0.45, 0.7), "stone", a + math.pi / 2)
    for k in range(8):
        a = k / 8 * math.tau
        m.prism((math.cos(a) * 1.6, math.sin(a) * 1.6, 9.3), (math.cos(a) * 1.6, math.sin(a) * 1.6, 10.8), 0.08, 0.08, 5, "wood")
    dk.lathe(m, [(10.6, 2.0), (11.4, 1.3), (12.6, 0.1)], 10, "slate")
    for z in (4.0, 7.0):
        m.box((0, -2.16, z), (0.35, 0.1, 0.8), "glass" if z > 5 else "shade")
    m.box((0, -2.3, 1.1), (1.0, 0.08, 2.0), "wood", axis=Z)
    return m


def cairn(rnd):
    """A cairn of flat stones -- the Crags' anomaly marker."""
    m = Mesh("Cairn")
    z = 0.0
    for i in range(7):
        w = 0.9 * (1 - i * 0.11) * rnd.uniform(0.85, 1.1)
        h = rnd.uniform(0.16, 0.26)
        m.box((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), z + h / 2), (w, w * rnd.uniform(0.7, 0.95), h),
              "stone", rnd.uniform(0, math.tau), axis=X)
        z += h
    return m


def mine_mouth(rnd):
    """A mine entrance: a timber frame set into a rock face, dark within, rails running out."""
    m = Mesh("MineMouth")
    dk.blob(m, (0, 1.2, 1.5), 3.4, 1.8, 2.6, rnd, mat="stone")
    m.box((0, -0.35, 1.2), (1.9, 0.3, 2.4), "shade", axis=Z)
    for x in (-1.05, 1.05):
        m.box((x, -0.55, 1.25), (0.25, 0.25, 2.5), "wood", axis=Z)
    m.box((0, -0.55, 2.6), (2.6, 0.3, 0.3), "wood", axis=X)
    for y in [-0.9 - i * 0.6 for i in range(6)]:
        m.box((0, y, 0.04), (1.3, 0.14, 0.08), "wood", axis=X)
    for x in (-0.45, 0.45):
        m.box((x, -2.4, 0.1), (0.06, 3.4, 0.06), "iron", axis=Y)
    return m


def minecart(rnd):
    m = Mesh("Minecart")
    m.box((0, 0, 0.6), (1.2, 0.8, 0.55), "wood", axis=X)
    for z in (0.38, 0.84):
        m.box((0, 0, z), (1.24, 0.84, 0.06), "iron", axis=X)
    for x in (-0.4, 0.4):
        for y in (-0.42, 0.42):
            m.prism((x, y - 0.03, 0.2), (x, y + 0.03, 0.2), 0.18, 0.18, 8, "iron")
    for i in range(5):
        m.box((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.25, 0.25), 0.92), (0.25, 0.22, 0.18), "stone", rnd.uniform(0, 3))
    return m


# ------------------------------------------------------------------ output
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rnd = random.Random(9090)
    rows = {
        "breakables": [pot(rnd), jar(rnd), crate(rnd), barrel(rnd), hay_bale(rnd)],
        "ember": [wood_shed(rnd), chopping_block(rnd), charcoal_mound(rnd), shrine(rnd), trunk_arch(rnd)],
        "fen": [boardwalk(rnd), stilt_hut(rnd), drowned_chapel(rnd), lily_pads(rnd)],
        "meadow": [farmhouse(rnd), haystack(rnd), scarecrow(rnd), beehives(rnd)],
        "crags": [watchtower(rnd), cairn(rnd), mine_mouth(rnd), minecart(rnd)],
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
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "worldkit.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    print("worldkit: exported", len(obs))
    sk.preview(built)


if __name__ == "__main__":
    main()
