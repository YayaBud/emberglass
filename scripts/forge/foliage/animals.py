"""Pixel-art animals, generated: doe, stag, fox, rabbit, robin, duck, koi, and the city's pigeon and gull.

    python D:/assests/scripts/forge/foliage/animals.py

Writes `game/assets/fauna/<name>.png` and `manifest.json`, and a sheet at
`renders/foliage/animals.png`. One PNG per animal: a cell per frame, row 0
facing screen-right, row 1 facing left. The left row is DRAWN, not mirrored,
so the key stays on the upper left both ways (a mirrored sprite is lit from
the wrong side).

Same method as `trees.py`: 52 texels/m, every part shaded as a lit volume
under the upper-left key, CIELAB ramps only, selective outline. The small
animals are drawn about 1.5x life size, or a rabbit is 15 px and a robin 8
(detail is sized against the sprite, not the metre -- memory.md).
"""
import json
import math
import os
import zlib

import numpy as np
from PIL import Image

from trees import Canvas, render, outline, ramp, TPM, LIGHT, ROOT, SHEETS

OUT = os.path.join(ROOT, "game", "assets", "fauna")
WALK = ["walk0", "walk1", "walk2", "walk3"]


class Pose:
    """Draws in metres on one cell: x forward along the animal, y up from
    its feet. `face` +1 draws it facing screen-right, -1 left."""

    def __init__(self, cv, face):
        self.cv, self.face, self.base = cv, face, cv.h - 2
        self.yy, self.xx = np.mgrid[0:cv.h, 0:cv.w].astype(np.float64)

    def p(self, x, y):
        return self.cv.w / 2 + x * TPM * self.face, self.base - y * TPM

    def blob(self, x, y, rx, ry, rid, bias=0.0, rot=0.0):
        """An ellipse lit as a volume. `rot` radians, positive = front end down."""
        cx, cy = self.p(x, y)
        rx, ry = max(rx * TPM, 0.7), max(ry * TPM, 0.7)
        dx, dy = self.xx - cx, self.yy - cy
        c, s = math.cos(rot * self.face), math.sin(rot * self.face)
        u, v = (dx * c + dy * s) / rx, (-dx * s + dy * c) / ry
        d2 = u * u + v * v
        gz = np.sqrt(np.clip(1 - d2, 0.05, 1))
        lam = (dx / rx) * LIGHT[0] + (dy / ry) * LIGHT[1] + gz * LIGHT[2]
        self.cv.put(d2 <= 1, rid, np.clip(np.round(1.3 + lam * 3.4 + bias), 0, 6).astype(np.int16))

    def limb(self, x0, y0, x1, y1, w0, w1, rid, bias=0.0):
        """A tapered capsule from (x0, y0) to (x1, y1), lit as a cylinder."""
        ax, ay = self.p(x0, y0)
        bx, by = self.p(x1, y1)
        vx, vy = bx - ax, by - ay
        t = np.clip(((self.xx - ax) * vx + (self.yy - ay) * vy) / (vx * vx + vy * vy + 1e-9), 0, 1)
        ox, oy = self.xx - (ax + t * vx), self.yy - (ay + t * vy)
        half = np.maximum((w0 + (w1 - w0) * t) * TPM / 2, 0.6)
        d = np.hypot(ox, oy) / half
        gz = np.sqrt(np.clip(1 - d * d, 0.05, 1))
        lam = (ox / half) * LIGHT[0] + (oy / half) * LIGHT[1] + gz * LIGHT[2]
        self.cv.put(d <= 1, rid, np.clip(np.round(1.3 + lam * 3.4 + bias), 0, 6).astype(np.int16))


def gait(frame, stride, lift, offs=(0.0, math.pi / 2, math.pi, 1.5 * math.pi)):
    """Foot (dx, dy) per leg for a walk frame; all zero standing."""
    if frame not in WALK:
        return [(0.0, 0.0)] * len(offs)
    ph = WALK.index(frame) * math.pi / 2
    return [(stride * math.sin(ph + o), max(0.0, math.cos(ph + o)) * lift) for o in offs]


def _rot(ox, oy, a):
    """Turn a y-up offset by `a` radians clockwise (the way a head dips)."""
    return ox * math.cos(a) + oy * math.sin(a), -ox * math.sin(a) + oy * math.cos(a)


# ---------------------------------------------------------------------------

FUR, PALE, DARK, HORN = 0, 1, 2, 3
DEER = [("#8c5a34", 7), ("#e0d2b4", 7), ("#2e241c", 7), ("#cbb68c", 7)]
FOX = [("#c4692c", 7), ("#e8dcc8", 7), ("#2a2020", 7)]
RABBIT = [("#8a7660", 7), ("#e6ddd0", 7), ("#2a2020", 7)]
ROBIN = [("#6a5242", 7), ("#c8582e", 7), ("#2a2020", 7)]


def deer(P, frame, stag):
    feet = gait(frame, 0.17, 0.07)
    far = [(-0.34, feet[0]), (0.34, feet[1])]
    near = [(-0.42, feet[2]), (0.42, feet[3])]
    for hx, (fx, fy) in far:
        P.limb(hx, 0.95, hx + fx, fy + 0.03, 0.11, 0.05, FUR, bias=-1.3)
        P.blob(hx + fx, fy + 0.03, 0.035, 0.03, DARK)
    P.blob(-0.36, 1.02, 0.27, 0.25, FUR)
    P.blob(0.0, 1.04, 0.52, 0.22, FUR)
    P.blob(0.33, 1.0, 0.25, 0.26, FUR)
    P.blob(0.02, 0.87, 0.34, 0.07, PALE, bias=-0.8)
    P.blob(-0.6, 1.12, 0.07, 0.09, PALE, bias=0.5)
    for hx, (fx, fy) in near:
        P.limb(hx, 0.95, hx + fx, fy + 0.03, 0.12, 0.055, FUR)
        P.blob(hx + fx, fy + 0.03, 0.035, 0.03, DARK)
    graze = frame == "graze"
    hx, hy, rot = (0.8, 0.32, 1.25) if graze else (0.74, 1.55, 0.35)
    P.limb(0.42, 1.1, hx - 0.06, hy + (0.08 if graze else -0.02), 0.24, 0.13, FUR)
    dip = rot - 0.35
    if stag:
        for (ax, ay), (bx, by), w in (((-0.04, 0.07), (-0.26, 0.58), 0.065),
                                      ((-0.1, 0.24), (0.06, 0.44), 0.05),
                                      ((-0.18, 0.42), (-0.06, 0.62), 0.05)):
            a, b = _rot(ax, ay, dip), _rot(bx, by, dip)
            P.limb(hx + a[0], hy + a[1], hx + b[0], hy + b[1], w, w * 0.6, HORN)
    ex, ey = _rot(-0.09, 0.07, dip)
    P.blob(hx + ex, hy + ey, 0.08, 0.035, FUR, bias=-0.3, rot=-0.7 + dip)
    P.blob(hx, hy, 0.17, 0.085, FUR, rot=rot)
    nx, ny = _rot(0.15, -0.02, dip)
    P.blob(hx + nx, hy + ny, 0.03, 0.025, DARK)
    ix, iy = _rot(0.0, 0.025, dip)
    P.blob(hx + ix, hy + iy, 0.014, 0.014, DARK, bias=-3)


def doe(P, frame):
    deer(P, frame, False)


def stag(P, frame):
    deer(P, frame, True)


def fox(P, frame):
    feet = gait(frame, 0.11, 0.05)
    sway = 0.03 * math.sin(WALK.index(frame) * math.pi / 2) if frame in WALK else 0.0
    for hx, (fx, fy) in ((-0.2, feet[0]), (0.2, feet[1])):
        P.limb(hx, 0.3, hx + fx, fy + 0.02, 0.06, 0.035, DARK, bias=-0.8)
    P.limb(-0.28, 0.36, -0.7, 0.27 + sway, 0.17, 0.13, FUR)
    P.blob(-0.74, 0.27 + sway, 0.08, 0.065, PALE)
    P.blob(0.0, 0.33, 0.32, 0.115, FUR)
    P.blob(0.22, 0.32, 0.14, 0.13, FUR)
    P.blob(0.06, 0.25, 0.2, 0.04, PALE, bias=-0.5)
    for hx, (fx, fy) in ((-0.25, feet[2]), (0.25, feet[3])):
        P.limb(hx, 0.3, hx + fx, fy + 0.02, 0.065, 0.04, DARK)
    sniff = frame == "sniff"
    hx, hy = (0.5, 0.2) if sniff else (0.44, 0.47)
    P.limb(0.26, 0.37, hx - 0.03, hy - 0.01, 0.14, 0.11, FUR)
    P.limb(hx - 0.04, hy + 0.05, hx - 0.08, hy + 0.18, 0.07, 0.015, FUR, bias=-0.8)
    P.limb(hx + 0.02, hy + 0.05, hx + 0.0, hy + 0.18, 0.07, 0.015, FUR)
    P.blob(hx, hy, 0.1, 0.075, FUR)
    P.limb(hx + 0.05, hy - 0.02, hx + 0.16, hy - 0.05, 0.07, 0.03, FUR)
    P.blob(hx + 0.05, hy - 0.04, 0.06, 0.03, PALE)
    P.blob(hx + 0.165, hy - 0.05, 0.018, 0.016, DARK)
    P.blob(hx + 0.03, hy + 0.015, 0.013, 0.013, DARK, bias=-3)


def rabbit(P, frame):
    k = 1.5
    if frame == "sit":
        P.blob(-0.02 * k, 0.1 * k, 0.1 * k, 0.1 * k, FUR)
        P.blob(0.0, 0.2 * k, 0.1 * k, 0.14 * k, FUR)
        P.blob(-0.12 * k, 0.1 * k, 0.04 * k, 0.04 * k, PALE)
        hx, hy = 0.05 * k, 0.36 * k
        P.limb(hx - 0.02 * k, hy + 0.03 * k, hx - 0.05 * k, hy + 0.22 * k, 0.045 * k, 0.025 * k, FUR, bias=-0.8)
        P.limb(hx, hy + 0.03 * k, hx - 0.01 * k, hy + 0.23 * k, 0.045 * k, 0.025 * k, FUR)
    else:
        s = math.sin(WALK.index(frame) * math.pi / 2) if frame in WALK else -1.0
        air, st = max(0.0, s) * 0.08 * k, 1 + 0.25 * max(0.0, s)
        P.limb(-0.08 * k, 0.06 * k + air, -0.2 * k * st, 0.015 * k + air, 0.06 * k, 0.04 * k, FUR, bias=-0.4)
        P.blob(-0.08 * k, 0.12 * k + air, 0.1 * k, 0.1 * k, FUR)
        P.blob(0.0, 0.14 * k + air, 0.16 * k * st, 0.1 * k / math.sqrt(st), FUR)
        P.limb(0.08 * k, 0.1 * k + air, (0.12 + 0.12 * (st - 1)) * k, 0.015 * k + air, 0.04 * k, 0.03 * k, FUR)
        P.blob(-0.16 * k * st, 0.16 * k + air, 0.045 * k, 0.045 * k, PALE)
        hx, hy = 0.15 * k * st, 0.23 * k + air
        P.limb(hx - 0.02 * k, hy + 0.04 * k, hx - 0.1 * k, hy + 0.2 * k, 0.045 * k, 0.025 * k, FUR, bias=-0.8)
        P.limb(hx, hy + 0.04 * k, hx - 0.07 * k, hy + 0.21 * k, 0.045 * k, 0.025 * k, FUR)
    P.blob(hx, hy, 0.085 * k, 0.07 * k, FUR)
    P.blob(hx + 0.035 * k, hy + 0.015 * k, 0.014 * k, 0.014 * k, DARK, bias=-3)


def robin(P, frame, k=2.0):
    fly = frame.startswith("fly")
    s = math.sin(WALK.index(frame) * math.pi / 2) if frame in WALK else -1.0
    air = (0.08 if fly else max(0.0, s) * 0.035) * k
    peck = frame == "peck"
    if not fly:
        P.limb(0.0, 0.05 * k + air, 0.0, 0.0 + air, 0.012 * k, 0.012 * k, DARK)
    P.limb(-0.05 * k, 0.1 * k + air, -0.14 * k, (0.1 if fly else 0.14) * k + air, 0.045 * k, 0.035 * k, FUR, bias=-0.5)
    P.blob(0.0, 0.1 * k + air, 0.075 * k, 0.055 * k, FUR, rot=0.0 if fly else -0.25)
    P.blob(0.035 * k, 0.085 * k + air, 0.045 * k, 0.042 * k, PALE)
    hx, hy = (0.1 * k, 0.06 * k + air) if peck else (0.07 * k, 0.15 * k + air)
    P.blob(hx, hy, 0.04 * k, 0.038 * k, FUR)
    P.limb(hx + 0.03 * k, hy - 0.005 * k, hx + 0.065 * k, hy - (0.03 if peck else 0.01) * k, 0.016 * k, 0.008 * k, DARK)
    P.blob(hx + 0.012 * k, hy + 0.01 * k, 0.009 * k, 0.009 * k, DARK, bias=-3)
    if fly:
        tip = (-0.05 * k, 0.3 * k) if frame == "fly0" else (-0.04 * k, 0.12 * k)
        P.limb(-0.005 * k, 0.12 * k + air, tip[0], tip[1] + air - (0.0 if frame == "fly0" else 0.12 * k),
               0.07 * k, 0.03 * k, FUR, bias=0.3)
    else:
        P.blob(-0.02 * k, 0.11 * k + air, 0.05 * k, 0.03 * k, FUR, bias=-0.7, rot=-0.2)


GREY, BROWN, GREEN, BILL, DK = 0, 1, 2, 3, 4
DUCK = [("#8c8a80", 7), ("#6e4430", 7), ("#2c6040", 7), ("#d8b040", 7), ("#262420", 7)]
KOI = [("#d8742c", 7), ("#efe6da", 7), ("#262420", 7)]


def duck(P, frame):
    """A mallard sitting ON the water: the foot line is the waterline and
    nothing is drawn below it, except in flight."""
    k = 1.5
    fly = frame.startswith("fly")
    s = math.sin(WALK.index(frame) * math.pi / 2) if frame in WALK else 0.0
    bob = 0.008 * k * s
    if frame == "dabble":
        # tail up, head under
        P.limb(-0.1 * k, 0.06 * k, -0.2 * k, 0.24 * k, 0.07 * k, 0.03 * k, GREY, bias=-0.6)
        P.blob(-0.02 * k, 0.07 * k, 0.15 * k, 0.1 * k, GREY, rot=0.7)
        P.blob(-0.06 * k, 0.1 * k, 0.09 * k, 0.05 * k, GREY, bias=-0.8, rot=0.7)
        P.cv.ramp[P.base + 1:] = -1
        return
    air = 0.12 * k if fly else 0.0
    if fly:
        P.limb(0.02 * k, 0.02 * k + air, -0.06 * k, -0.04 * k + air, 0.02 * k, 0.02 * k, BILL)
    P.limb(-0.14 * k, 0.07 * k + air + bob, -0.25 * k, 0.12 * k + air, 0.06 * k, 0.025 * k, GREY, bias=-1.0)
    P.blob(0.0, 0.055 * k + air + bob, 0.19 * k, 0.085 * k, GREY)
    P.blob(0.11 * k, 0.07 * k + air + bob, 0.075 * k, 0.07 * k, BROWN)
    P.limb(0.13 * k, 0.1 * k + air + bob, 0.16 * k, 0.16 * k + air + bob * 2, 0.05 * k, 0.045 * k, GREEN)
    hx, hy = 0.165 * k, 0.175 * k + air + bob * 2
    P.blob(hx, hy, 0.055 * k, 0.05 * k, GREEN)
    P.limb(hx + 0.035 * k, hy - 0.01 * k, hx + 0.09 * k, hy - 0.025 * k, 0.03 * k, 0.018 * k, BILL)
    P.blob(hx + 0.012 * k, hy + 0.012 * k, 0.01 * k, 0.01 * k, DK, bias=-3)
    if fly:
        up = frame == "fly0"
        P.limb(-0.01 * k, 0.09 * k + air, -0.08 * k, (0.34 if up else -0.1) * k + air, 0.08 * k, 0.035 * k, GREY, bias=0.4)
    else:
        P.blob(-0.03 * k, 0.08 * k + bob, 0.12 * k, 0.045 * k, GREY, bias=-0.8)
        P.cv.ramp[P.base + 1:] = -1


def koi(P, frame):
    """A koi, side on. Swim frames flick the tail; jump frames turn the
    whole fish about its middle, nose up, level, nose down."""
    a = {"jump0": 0.6, "jump1": 0.0, "jump2": -0.6}.get(frame, 0.0)
    cy = 0.3
    flick = 0.05 * math.sin(WALK.index(frame) * math.pi / 2) if frame in WALK else 0.0

    def at(x, y):
        ox, oy = _rot(x, y - cy, -a)
        return ox, oy + cy
    tx, ty = at(-0.36, cy + flick)
    bx, by = at(-0.2, cy)
    P.limb(bx, by, tx, ty, 0.1, 0.13, FUR, bias=-0.4)
    x, y = at(0.0, cy)
    P.blob(x, y, 0.24, 0.075, FUR, rot=-a)
    x, y = at(0.06, cy + 0.02)
    P.blob(x, y, 0.08, 0.035, PALE, rot=-a)
    x, y = at(-0.08, cy - 0.03)
    P.blob(x, y, 0.07, 0.03, PALE, rot=-a, bias=-0.5)
    fx, fy = at(0.02, cy + 0.06)
    gx, gy = at(-0.06, cy + 0.11)
    P.limb(fx, fy, gx, gy, 0.05, 0.02, FUR, bias=-0.5)
    x, y = at(0.18, cy + 0.015)
    P.blob(x, y, 0.012, 0.012, DARK, bias=-3)


# The city's birds: the robin's body at other sizes and colours. Pigeons
# peck round the squares; gulls stand on the quays; both fly when the
# player comes close.
PIGEON = [("#7c8494", 7), ("#a8acb6", 7), ("#2a2828", 7)]
GULL = [("#e2e2da", 7), ("#f2f0e8", 7), ("#3a3a3c", 7)]


def pigeon(P, frame):
    robin(P, frame, k=2.3)


def gull(P, frame):
    robin(P, frame, k=3.4)


# The town's animals (user, 2026-09-26: "dogs cats other animals ... fill
# the city"): dogs and cats in the streets, hens in the yards, a goat, sheep
# and pigs at the farms. Same drawing as the wild ones; the small ones are
# drawn larger than life for the same reason (detail sized against the
# sprite). Ramps: FUR, PALE, DARK, then a fourth for eyes / comb / bill.
DOG_TAN = [("#9a6a3c", 7), ("#e6d4b0", 7), ("#2a2020", 7), ("#6e4628", 7)]
DOG_BLACK = [("#34302e", 7), ("#ece6dc", 7), ("#161414", 7), ("#24201e", 7)]
CAT_GINGER = [("#d0803a", 7), ("#f0dcc0", 7), ("#2a2020", 7), ("#8cb040", 7)]
CAT_GREY = [("#8a8a92", 7), ("#dcdce0", 7), ("#262428", 7), ("#d0b040", 7)]
CAT_BLACK = [("#2e2c32", 7), ("#4a4650", 7), ("#141216", 7), ("#e0c040", 7)]
HEN_BROWN = [("#9a5a2a", 7), ("#d8a060", 7), ("#2a2020", 7), ("#c83828", 7), ("#e0b040", 7)]
HEN_WHITE = [("#ece8dc", 7), ("#f6f2ea", 7), ("#2a2020", 7), ("#c83828", 7), ("#e0b040", 7)]
GOAT = [("#b8a88c", 7), ("#ece4d4", 7), ("#2a2420", 7), ("#8a7c66", 7)]
SHEEP = [("#e4ddcc", 7), ("#f4f0e6", 7), ("#2c2826", 7), ("#3e3834", 7)]
PIG = [("#e0a08c", 7), ("#f0c4b4", 7), ("#2a2020", 7), ("#c47c6c", 7)]
EAR, EYE, COMB, BEAK = 3, 3, 3, 4


def _phase(frame):
    return math.sin(WALK.index(frame) * math.pi / 2) if frame in WALK else 0.0


def dog(P, frame):
    """A medium street dog, 0.5 m at the shoulder. `sit` sits with the tail
    thumping (the petting frame); `idle` stands with the tail up."""
    if frame == "sit":
        P.limb(0.14, 0.36, 0.15, 0.03, 0.07, 0.05, FUR, bias=-0.9)
        P.limb(-0.3, 0.05, -0.5, 0.1, 0.06, 0.03, FUR, bias=-0.3)
        P.blob(-0.13, 0.16, 0.2, 0.16, FUR)
        P.blob(-0.2, 0.05, 0.12, 0.05, FUR, bias=-0.6)
        P.limb(-0.06, 0.2, 0.14, 0.44, 0.22, 0.19, FUR)
        P.blob(0.17, 0.4, 0.09, 0.12, PALE, bias=-0.3)
        P.limb(0.17, 0.36, 0.19, 0.03, 0.075, 0.055, FUR)
        P.blob(0.2, 0.03, 0.045, 0.03, PALE)
        hx, hy = 0.24, 0.66
    else:
        feet = gait(frame, 0.13, 0.06)
        bob = 0.015 * _phase(frame)
        for hx0, (fx, fy) in ((-0.24, feet[0]), (0.24, feet[1])):
            P.limb(hx0, 0.42, hx0 + fx, fy + 0.03, 0.075, 0.045, FUR, bias=-1.0)
        up = frame == "idle"
        P.limb(-0.3, 0.5 + bob, -0.5, 0.72 if up else 0.58, 0.07, 0.035, FUR, bias=-0.3)
        P.blob(-0.26, 0.46 + bob, 0.14, 0.14, FUR)
        P.blob(0.0, 0.47 + bob, 0.3, 0.13, FUR)
        P.blob(0.22, 0.47 + bob, 0.14, 0.15, FUR)
        P.blob(0.24, 0.42 + bob, 0.08, 0.1, PALE, bias=-0.3)
        P.blob(0.02, 0.38 + bob, 0.2, 0.04, PALE, bias=-0.6)
        for hx0, (fx, fy) in ((-0.28, feet[2]), (0.28, feet[3])):
            P.limb(hx0, 0.42, hx0 + fx, fy + 0.03, 0.08, 0.05, FUR)
            P.blob(hx0 + fx + 0.02, fy + 0.03, 0.045, 0.03, PALE)
        hx, hy = 0.4, 0.68 + bob
        P.limb(0.26, 0.52 + bob, hx - 0.03, hy - 0.04, 0.16, 0.12, FUR)
    P.blob(hx, hy, 0.11, 0.095, FUR)
    P.limb(hx + 0.04, hy - 0.02, hx + 0.17, hy - 0.05, 0.1, 0.07, FUR)
    P.blob(hx + 0.1, hy - 0.06, 0.07, 0.035, PALE)
    P.blob(hx + 0.175, hy - 0.045, 0.025, 0.022, DARK)
    P.limb(hx - 0.04, hy + 0.06, hx - 0.09, hy - 0.08, 0.07, 0.04, EAR, bias=-0.4)
    P.blob(hx + 0.04, hy + 0.025, 0.016, 0.016, DARK, bias=-3)


def dog_black(P, frame):
    dog(P, frame)


def cat(P, frame, k=1.5):
    """A cat, 0.25 m at the shoulder drawn at 1.5x. `sit` is the loaf it
    keeps on a doorstep (and when it is stroked)."""
    if frame == "sit":
        P.limb(-0.1 * k, 0.02 * k, 0.09 * k, 0.015 * k, 0.035 * k, 0.03 * k, FUR, bias=-0.4)
        P.blob(-0.04 * k, 0.08 * k, 0.1 * k, 0.085 * k, FUR)
        P.limb(-0.02 * k, 0.1 * k, 0.05 * k, 0.22 * k, 0.13 * k, 0.09 * k, FUR)
        P.blob(0.06 * k, 0.17 * k, 0.04 * k, 0.06 * k, PALE, bias=-0.3)
        P.limb(0.06 * k, 0.16 * k, 0.075 * k, 0.015 * k, 0.035 * k, 0.03 * k, FUR)
        hx, hy = 0.07 * k, 0.3 * k
    else:
        feet = gait(frame, 0.05 * k, 0.03 * k)
        for hx0, (fx, fy) in ((-0.11 * k, feet[0]), (0.11 * k, feet[1])):
            P.limb(hx0, 0.16 * k, hx0 + fx, fy + 0.012 * k, 0.035 * k, 0.025 * k, FUR, bias=-1.0)
        P.limb(-0.15 * k, 0.19 * k, -0.24 * k, 0.3 * k, 0.035 * k, 0.03 * k, FUR, bias=-0.3)
        P.limb(-0.24 * k, 0.3 * k, -0.2 * k, 0.4 * k, 0.03 * k, 0.025 * k, FUR, bias=-0.3)
        P.blob(0.0, 0.18 * k, 0.16 * k, 0.065 * k, FUR)
        P.blob(0.02 * k, 0.14 * k, 0.11 * k, 0.025 * k, PALE, bias=-0.6)
        for hx0, (fx, fy) in ((-0.13 * k, feet[2]), (0.13 * k, feet[3])):
            P.limb(hx0, 0.16 * k, hx0 + fx, fy + 0.012 * k, 0.04 * k, 0.028 * k, FUR)
        hx, hy = 0.19 * k, 0.25 * k
        P.limb(0.12 * k, 0.2 * k, hx - 0.02 * k, hy - 0.01 * k, 0.08 * k, 0.065 * k, FUR)
    P.blob(hx, hy, 0.065 * k, 0.058 * k, FUR)
    for ex, bias in ((-0.03, -0.8), (0.02, 0.0)):
        P.limb(hx + ex * k, hy + 0.04 * k, hx + (ex - 0.005) * k, hy + 0.095 * k, 0.04 * k, 0.006 * k, FUR, bias=bias)
    P.blob(hx + 0.04 * k, hy - 0.02 * k, 0.03 * k, 0.022 * k, PALE)
    P.blob(hx + 0.068 * k, hy - 0.005 * k, 0.01 * k, 0.009 * k, DARK)
    P.blob(hx + 0.028 * k, hy + 0.012 * k, 0.012 * k, 0.011 * k, EYE, bias=1)


def cat_grey(P, frame):
    cat(P, frame)


def cat_black(P, frame):
    cat(P, frame)


def hen(P, frame, k=1.7):
    """A hen, drawn at 1.7x. Pecks; flaps up when she bolts."""
    fly = frame.startswith("fly")
    s = _phase(frame)
    air = (0.06 if fly else max(0.0, s) * 0.02) * k
    peck = frame == "peck"
    if not fly:
        for dx, ph in ((-0.01, 0.0), (0.02, math.pi)):
            fx = 0.03 * k * math.sin(WALK.index(frame) * math.pi / 2 + ph) if frame in WALK else 0.0
            P.limb(dx * k, 0.08 * k + air, dx * k + fx, 0.0 + air, 0.014 * k, 0.012 * k, BEAK)
    P.limb(-0.07 * k, 0.15 * k + air, -0.14 * k, 0.26 * k + air, 0.08 * k, 0.04 * k, FUR, bias=-0.4)
    P.blob(0.0, 0.14 * k + air, 0.11 * k, 0.08 * k, FUR, rot=-0.15)
    P.blob(0.03 * k, 0.11 * k + air, 0.07 * k, 0.05 * k, PALE, bias=-0.3)
    hx, hy = (0.12 * k, 0.07 * k + air) if peck else (0.08 * k, 0.26 * k + air)
    P.limb(0.05 * k, 0.17 * k + air, hx - 0.01 * k, hy - 0.01 * k, 0.06 * k, 0.045 * k, FUR)
    P.blob(hx, hy, 0.042 * k, 0.04 * k, FUR)
    P.limb(hx - 0.02 * k, hy + 0.035 * k, hx + 0.02 * k, hy + 0.045 * k, 0.025 * k, 0.015 * k, COMB)
    P.limb(hx + 0.03 * k, hy - 0.005 * k, hx + 0.065 * k, hy - 0.015 * k, 0.018 * k, 0.008 * k, BEAK)
    P.blob(hx + 0.025 * k, hy - 0.035 * k, 0.012 * k, 0.018 * k, COMB)
    P.blob(hx + 0.012 * k, hy + 0.01 * k, 0.009 * k, 0.009 * k, DARK, bias=-3)
    if fly:
        up = frame == "fly0"
        P.limb(-0.01 * k, 0.17 * k + air, -0.08 * k, (0.34 if up else 0.02) * k + air, 0.08 * k, 0.035 * k, FUR, bias=0.4)
    else:
        P.blob(-0.02 * k, 0.15 * k + air, 0.07 * k, 0.04 * k, FUR, bias=-0.7, rot=-0.2)


def hen_white(P, frame):
    hen(P, frame)


def goat(P, frame):
    """A goat, 0.65 m at the shoulder: swept-back horns and a beard."""
    feet = gait(frame, 0.12, 0.05)
    for hx0, (fx, fy) in ((-0.22, feet[0]), (0.22, feet[1])):
        P.limb(hx0, 0.52, hx0 + fx, fy + 0.03, 0.07, 0.04, FUR, bias=-1.2)
        P.blob(hx0 + fx, fy + 0.02, 0.03, 0.025, DARK)
    P.limb(-0.32, 0.64, -0.38, 0.75, 0.06, 0.03, FUR, bias=-0.2)
    P.blob(-0.2, 0.6, 0.17, 0.16, FUR)
    P.blob(0.02, 0.62, 0.3, 0.14, FUR)
    P.blob(0.2, 0.6, 0.15, 0.16, FUR)
    P.blob(0.02, 0.5, 0.22, 0.05, PALE, bias=-0.7)
    for hx0, (fx, fy) in ((-0.26, feet[2]), (0.26, feet[3])):
        P.limb(hx0, 0.52, hx0 + fx, fy + 0.03, 0.075, 0.045, FUR)
        P.blob(hx0 + fx, fy + 0.02, 0.03, 0.025, DARK)
    graze = frame == "graze"
    hx, hy = (0.52, 0.18) if graze else (0.46, 0.9)
    P.limb(0.26, 0.66, hx - 0.04, hy - 0.02, 0.15, 0.1, FUR)
    dip = 0.9 if graze else 0.0
    for (ax, ay), (bx, by) in (((-0.02, 0.06), (-0.14, 0.2)), ((-0.14, 0.2), (-0.22, 0.16))):
        a, b = _rot(ax, ay, dip), _rot(bx, by, dip)
        P.limb(hx + a[0], hy + a[1], hx + b[0], hy + b[1], 0.04, 0.025, EAR)
    P.blob(hx, hy, 0.11, 0.075, FUR, rot=0.4 + dip)
    mx, my = _rot(0.1, -0.04, dip)
    P.blob(hx + mx, hy + my, 0.05, 0.035, PALE, rot=0.4 + dip)
    bx, by = _rot(0.08, -0.1, dip)
    P.limb(hx + bx - 0.01, hy + by + 0.04, hx + bx, hy + by - 0.03, 0.035, 0.015, PALE, bias=-0.5)
    ex, ey = _rot(-0.02, 0.03, dip)
    P.blob(hx + ex, hy + ey, 0.014, 0.014, DARK, bias=-3)
    kx, ky = _rot(-0.07, 0.01, dip)
    P.limb(hx + kx, hy + ky, hx + kx - 0.1, hy + ky - 0.03, 0.05, 0.02, FUR, bias=-0.4)


def sheep(P, frame):
    """A sheep: a cloud of wool on dark legs, a dark face."""
    feet = gait(frame, 0.1, 0.04)
    for hx0, (fx, fy) in ((-0.2, feet[0]), (0.2, feet[1])):
        P.limb(hx0, 0.4, hx0 + fx, fy + 0.03, 0.06, 0.045, DARK, bias=-0.8)
    for x, y, rx, ry, b in ((-0.22, 0.56, 0.2, 0.19, -0.2), (0.0, 0.62, 0.26, 0.2, 0.2), (0.2, 0.57, 0.19, 0.18, 0.0),
                            (-0.08, 0.48, 0.28, 0.12, -0.6), (0.1, 0.7, 0.16, 0.1, 0.5)):
        P.blob(x, y, rx, ry, FUR, bias=b)
    for x, y in ((-0.3, 0.64), (-0.1, 0.76), (0.12, 0.76), (0.28, 0.62), (-0.18, 0.44), (0.12, 0.45)):
        P.blob(x, y, 0.07, 0.065, PALE, bias=0.4)
    for hx0, (fx, fy) in ((-0.24, feet[2]), (0.24, feet[3])):
        P.limb(hx0, 0.4, hx0 + fx, fy + 0.03, 0.065, 0.05, DARK)
    graze = frame == "graze"
    hx, hy = (0.46, 0.14) if graze else (0.42, 0.66)
    P.limb(0.3, 0.6, hx - 0.03, hy + 0.01, 0.12, 0.1, EAR)
    P.blob(0.3, 0.64, 0.1, 0.1, FUR, bias=0.3)
    P.blob(hx, hy, 0.1, 0.075, EAR, rot=0.5 + (0.9 if graze else 0.0))
    P.limb(hx - 0.04, hy + 0.05, hx - 0.12, hy + 0.02, 0.05, 0.02, EAR, bias=-0.3)
    P.blob(hx + 0.01, hy + 0.025, 0.013, 0.013, PALE, bias=2)


def pig(P, frame):
    """A pig: a round pink barrel on short legs; roots with its snout."""
    feet = gait(frame, 0.08, 0.035)
    for hx0, (fx, fy) in ((-0.2, feet[0]), (0.2, feet[1])):
        P.limb(hx0, 0.24, hx0 + fx, fy + 0.03, 0.08, 0.055, EAR, bias=-0.8)
    tail = [(-0.36, 0.42), (-0.43, 0.46), (-0.42, 0.52), (-0.37, 0.5)]
    for (ax, ay), (bx, by) in zip(tail, tail[1:]):
        P.limb(ax, ay, bx, by, 0.025, 0.02, FUR, bias=-0.3)
    P.blob(-0.02, 0.38, 0.36, 0.2, FUR)
    P.blob(0.0, 0.29, 0.3, 0.08, PALE, bias=-0.6)
    for hx0, (fx, fy) in ((-0.24, feet[2]), (0.24, feet[3])):
        P.limb(hx0, 0.24, hx0 + fx, fy + 0.03, 0.085, 0.06, FUR)
    root = frame == "sniff"
    hx, hy = (0.4, 0.16) if root else (0.38, 0.42)
    P.blob(hx, hy, 0.13, 0.12, FUR)
    P.limb(hx - 0.02, hy + 0.08, hx + 0.06, hy + 0.15, 0.08, 0.03, EAR, bias=0.2)
    P.blob(hx + 0.12, hy - 0.03, 0.045, 0.05, PALE)
    P.blob(hx + 0.15, hy - 0.03, 0.012, 0.012, DARK)
    P.blob(hx + 0.05, hy + 0.03, 0.014, 0.014, DARK, bias=-3)


# name: (draw, ramps, cell metres (w, h), frames)
# The four new regions (implementation_plan B1, 2026-09-28): crows over the Meadows and
# the Crags, hares in the grass, squirrels and boar in the Emberwood, herons and frogs in
# the Fen. Where a drawing already fits, a palette is all that changes.
CROW = [("#2a2a30", 7), ("#3c3c48", 7), ("#101014", 7)]
SQUIRREL = [("#a8562a", 7), ("#e8d8c0", 7), ("#2a2020", 7)]
HARE = [("#9a7a50", 7), ("#e6ddd0", 7), ("#2a2020", 7)]
BOAR = [("#4a3a2c", 7), ("#6e5a46", 7), ("#1e1814", 7), ("#e8e0cc", 7)]
HERON = [("#8a9098", 7), ("#e4e4e0", 7), ("#2a2a2c", 7), ("#d8b040", 7)]
FROG = [("#4a7a30", 7), ("#c8c888", 7), ("#1e2418", 7)]


def crow(P, frame):
    robin(P, frame, k=2.6)


def heron(P, frame):
    """A grey heron: long legs, an S neck, a dagger bill; `fish` strikes down."""
    fly = frame.startswith("fly")
    fish = frame == "fish"
    by = 0.72 + (0.5 if fly else 0.0)
    if fly:
        P.limb(-0.1, by, -0.45, by - 0.05, 0.02, 0.02, DARK)
    else:
        for off in (0.0, math.pi):
            dx = 0.08 * math.sin(WALK.index(frame) * math.pi / 2 + off) if frame in WALK else 0.0
            P.limb(0.0, by - 0.05, dx, 0.0, 0.025, 0.018, DARK)
    P.limb(-0.12, by + 0.02, -0.28, by - 0.06, 0.08, 0.03, FUR, bias=-0.5)
    P.blob(0.0, by, 0.2, 0.1, FUR, rot=-0.3)
    mx, my = (0.22, by - 0.05) if fish else (0.1, by + 0.22)
    nx, ny = (0.3, by - 0.25) if fish else (0.14, by + 0.42)
    P.limb(0.12, by + 0.05, mx, my, 0.05, 0.04, PALE)
    P.limb(mx, my, nx, ny, 0.04, 0.035, PALE)
    P.blob(nx, ny, 0.045, 0.04, PALE)
    P.limb(nx + 0.03, ny, nx + 0.17, ny - (0.08 if fish else 0.02), 0.025, 0.01, HORN)
    P.blob(nx + 0.012, ny + 0.012, 0.01, 0.01, DARK, bias=-3)
    if fly:
        up = frame == "fly0"
        P.limb(-0.02, by + 0.05, -0.12, by + (0.45 if up else -0.3), 0.14, 0.05, FUR, bias=0.3)
    else:
        P.blob(-0.03, by + 0.02, 0.15, 0.06, FUR, bias=-0.6, rot=-0.3)


def frog(P, frame):
    """A frog, side on; the walk is a hop."""
    k = 1.8
    s = math.sin(WALK.index(frame) * math.pi / 2) if frame in WALK else -1.0
    air = max(0.0, s) * 0.08 * k
    P.limb(-0.05 * k, 0.03 * k + air, -0.1 * k * (1 + max(0.0, s)), air * 0.2, 0.035 * k, 0.02 * k, FUR, bias=-0.4)
    P.blob(0.0, 0.05 * k + air, 0.08 * k, 0.05 * k, FUR, rot=-0.3)
    P.blob(0.02 * k, 0.035 * k + air, 0.05 * k, 0.025 * k, PALE)
    P.limb(0.05 * k, 0.03 * k + air, 0.07 * k, air, 0.02 * k, 0.015 * k, FUR)
    P.blob(0.05 * k, 0.09 * k + air, 0.022 * k, 0.022 * k, FUR)
    P.blob(0.055 * k, 0.095 * k + air, 0.009 * k, 0.009 * k, DARK, bias=-3)


ANIMALS = {
    "crow": (crow, CROW, (1.1, 1.3), ["idle"] + WALK + ["peck", "fly0", "fly1"]),
    "squirrel": (rabbit, SQUIRREL, (0.9, 1.0), ["idle"] + WALK + ["sit"]),
    "hare": (rabbit, HARE, (0.9, 1.0), ["idle"] + WALK + ["sit"]),
    "boar": (pig, BOAR, (1.3, 0.8), ["idle"] + WALK + ["sniff"]),
    "heron": (heron, HERON, (1.3, 1.95), ["idle"] + WALK + ["fish", "fly0", "fly1"]),
    "frog": (frog, FROG, (0.9, 0.5), ["idle"] + WALK + ["sit"]),
    "doe": (doe, DEER, (2.1, 1.9), ["idle"] + WALK + ["graze"]),
    "stag": (stag, DEER, (2.8, 2.4), ["idle"] + WALK + ["graze"]),
    "fox": (fox, FOX, (1.9, 0.9), ["idle"] + WALK + ["sniff"]),
    "rabbit": (rabbit, RABBIT, (0.9, 1.0), ["idle"] + WALK + ["sit"]),
    "robin": (robin, ROBIN, (0.8, 1.0), ["idle"] + WALK + ["peck", "fly0", "fly1"]),
    "duck": (duck, DUCK, (1.0, 0.9), ["idle"] + WALK + ["dabble", "fly0", "fly1"]),
    "koi": (koi, KOI, (1.0, 0.7), ["idle"] + WALK + ["jump0", "jump1", "jump2"]),
    "pigeon": (pigeon, PIGEON, (0.95, 1.2), ["idle"] + WALK + ["peck", "fly0", "fly1"]),
    "gull": (gull, GULL, (1.4, 1.75), ["idle"] + WALK + ["peck", "fly0", "fly1"]),
    "dog": (dog, DOG_TAN, (1.5, 1.0), ["idle"] + WALK + ["sit"]),
    "dog_black": (dog_black, DOG_BLACK, (1.5, 1.0), ["idle"] + WALK + ["sit"]),
    "cat": (cat, CAT_GINGER, (1.0, 0.8), ["idle"] + WALK + ["sit"]),
    "cat_grey": (cat_grey, CAT_GREY, (1.0, 0.8), ["idle"] + WALK + ["sit"]),
    "cat_black": (cat_black, CAT_BLACK, (1.0, 0.8), ["idle"] + WALK + ["sit"]),
    "hen": (hen, HEN_BROWN, (0.8, 0.85), ["idle"] + WALK + ["peck", "fly0", "fly1"]),
    "hen_white": (hen_white, HEN_WHITE, (0.8, 0.85), ["idle"] + WALK + ["peck", "fly0", "fly1"]),
    "goat": (goat, GOAT, (1.4, 1.3), ["idle"] + WALK + ["graze"]),
    "sheep": (sheep, SHEEP, (1.3, 1.0), ["idle"] + WALK + ["graze"]),
    "pig": (pig, PIG, (1.3, 0.8), ["idle"] + WALK + ["sniff"]),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SHEETS, exist_ok=True)
    manifest, sheets = {}, []
    for name, (draw, ramp_defs, (wm, hm), frames) in ANIMALS.items():
        ramps = [ramp(b, n) for b, n in ramp_defs]
        allowed = {tuple(c) for r in ramps for c in r}
        cw, ch = int(wm * TPM), int(hm * TPM)
        atlas = np.zeros((ch * 2, cw * len(frames), 4), dtype=np.uint8)
        for row, face in enumerate((1, -1)):
            for col, fr in enumerate(frames):
                cv = Canvas(cw, ch)
                draw(Pose(cv, face), fr)
                outline(cv, None)
                rgba = render(cv, ramps)
                op = rgba[..., 3] == 255
                assert op.any(), f"{name}/{fr}: empty"
                assert not ({tuple(c) for c in rgba[op][:, :3]} - allowed), f"{name}/{fr}: off-palette"
                # a clear 1 px border, so a neighbouring frame never bleeds in
                assert not op[0].any() and not op[:, 0].any() and not op[:, -1].any(), f"{name}/{fr}: touches the cell edge"
                atlas[row * ch:(row + 1) * ch, col * cw:(col + 1) * cw] = rgba
        Image.fromarray(atlas).save(os.path.join(OUT, name + ".png"))
        manifest[name] = dict(cell_px=[cw, ch], metres=[round(cw / TPM, 3), round(ch / TPM, 3)],
                              foot_px=1, frames=frames)
        sheets.append(atlas)
        print(f"fauna: {name:<7} {len(frames)} frames x 2 facings, cell {cw}x{ch} px")
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(dict(texels_per_m=TPM, animals=manifest), f, indent=1)
    W = max(a.shape[1] for a in sheets) + 20
    H = sum(a.shape[0] for a in sheets) + 10 * (len(sheets) + 1)
    sheet = Image.new("RGB", (W, H), (96, 104, 88))
    y = 10
    for a in sheets:
        im = Image.fromarray(a)
        sheet.paste(im, (10, y), im)
        y += a.shape[0] + 10
    sheet = sheet.resize((W * 2, H * 2), Image.NEAREST)
    sheet.save(os.path.join(SHEETS, "animals.png"))
    print("fauna: sheet", os.path.join(SHEETS, "animals.png"))


if __name__ == "__main__":
    main()
