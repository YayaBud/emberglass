"""
Polygon geometry for the city plan.

The first city was built entirely from axis-aligned RECTANGLES -- districts,
terraces, water, the wall. That is why it came out a grid in a box when the
blueprint is a radial city on an organic mound: a rect-based river cannot wrap
through a city, and rect districts cannot be wedges around a market square.

Everything here is the minimum needed to describe the blueprint properly:
sectors, rings, point-in-polygon, and an organic outline that is not a box.
"""

import math


def sector(a0_deg, a1_deg, r0, r1, centre=(0.0, 0.0), steps=None, wobble=0.0,
           seed=0):
    """An annular wedge: the natural shape of a district around a plaza.

    Angles are compass-free maths convention -- 0 deg is +X (east), 90 deg is
    +Y (north). `wobble` pushes the outer arc in and out so a quarter's edge
    reads as grown rather than drawn with a compass.
    """
    a0 = math.radians(a0_deg)
    a1 = math.radians(a1_deg)
    if a1 <= a0:
        a1 += 2 * math.pi
    span = a1 - a0
    if steps is None:
        steps = max(3, int(span / math.radians(9)))
    cx, cy = centre
    rng = _Rng(seed)

    pts = []
    for i in range(steps + 1):
        a = a0 + span * i / steps
        r = r1 * (1.0 + (rng.next() - 0.5) * 2.0 * wobble)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    for i in range(steps, -1, -1):
        a = a0 + span * i / steps
        r = r0 * (1.0 + (rng.next() - 0.5) * 2.0 * wobble * 0.5)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def ring(r, centre=(0.0, 0.0), steps=48, wobble=0.0, seed=0):
    """A closed ring polyline -- a concentric street, or a wall circuit."""
    cx, cy = centre
    rng = _Rng(seed)
    pts = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        rr = r * (1.0 + (rng.next() - 0.5) * 2.0 * wobble)
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pts.append(pts[0])
    return pts


def spoke(a_deg, r0, r1, centre=(0.0, 0.0), bend=0.0):
    """A radial street from the centre outward, optionally bowed."""
    a = math.radians(a_deg)
    cx, cy = centre
    pts = []
    for i in range(5):
        t = i / 4.0
        r = r0 + (r1 - r0) * t
        aa = a + math.radians(bend) * math.sin(math.pi * t)
        pts.append((cx + math.cos(aa) * r, cy + math.sin(aa) * r))
    return pts


class _Rng:
    """Tiny deterministic generator so a shape is identical every run."""

    __slots__ = ("s",)

    def __init__(self, seed):
        self.s = (seed * 1103515245 + 12345) & 0x7FFFFFFF

    def next(self):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s / 0x7FFFFFFF


def contains(poly, x, y):
    """Point in polygon, ray cast. Polygons here are small, so this is fine."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xc = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            if x < xc:
                inside = not inside
        j = i
    return inside


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs), min(ys), max(xs), max(ys))


def area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return abs(a) * 0.5


def centroid(poly):
    x0, y0, x1, y1 = bbox(poly)
    return ((x0 + x1) * 0.5, (y0 + y1) * 0.5)


def band(pts, half):
    """Thicken a polyline into a closed polygon -- a river from a course."""
    left = []
    right = []
    for i, (x, y) in enumerate(pts):
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == len(pts) - 1:
            dx, dy = x - pts[-2][0], y - pts[-2][1]
        else:
            dx = pts[i + 1][0] - pts[i - 1][0]
            dy = pts[i + 1][1] - pts[i - 1][1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        h = half[i] if isinstance(half, (list, tuple)) else half
        left.append((x + nx * h, y + ny * h))
        right.append((x - nx * h, y - ny * h))
    return left + right[::-1]


def resample(pts, step=6.0):
    """Even spacing along a polyline, for sweeping walls and roads."""
    out = [pts[0]]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if seg < 1e-6:
            continue
        d = carry
        while d + step <= seg:
            d += step
            t = d / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        carry = d - seg
    if out[-1] != pts[-1]:
        out.append(pts[-1])
    return out


def point_segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
