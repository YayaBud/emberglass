"""
Blocks and buildings: the frontage walk.

This is the routine that decides whether the city reads as DENSE or as
scattered objects, so it is specified rather than improvised.

    parcel each district into blocks with secondary streets
    for each block, walk every street-facing edge
        place buildings shoulder to shoulder along it
        gap 0.0 m most of the time  -> party walls, a continuous terrace
        gap 0.1-0.6 m sometimes     -> a slumped joint
        gap 1.8-2.4 m rarely        -> an alley
    leave the block interior as a courtyard

The +/-3 degree yaw jitter and the irregular gaps are what keep it from
reading as extruded. Same rule as the library pass: handcrafted and lived-in,
never cleaner.

Buildings are placed as TRANSFORMS here, not geometry. `city_build.py` turns
them into collection instances so 710 placements cost 21 unique meshes.
"""

import os
import sys
import random
from math import hypot, radians, degrees, atan2, cos, sin, pi

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

import city_plan as P
import city_geom as G

# Footprints (width along frontage, depth into the block), metres.
# Taken from library_buildings.py so the walk packs against real sizes.
FOOTPRINT = {
    "bld_cottage": (4.2, 5.0),
    "bld_townhouse": (4.4, 5.4),
    "bld_tenement": (6.4, 4.6),
    "bld_tavern": (6.2, 4.4),
    "bld_shop": (5.2, 4.4),
    "bld_blacksmith": (4.4, 4.8),
    "bld_stables": (6.4, 4.6),
    "bld_warehouse": (4.8, 6.0),
    "monument_noble_manor": (7.0, 7.8),
    "monument_guildhouse": (5.8, 7.4),
    "monument_chapel": (4.6, 7.2),
    "monument_church": (5.4, 8.6),
    "monument_windmill": (4.3, 4.3),
    "monument_watchtower": (4.0, 6.4),
    "monument_gatehouse": (6.0, 5.0),
    "monument_keep": (8.6, 7.0),
    "monument_lighthouse": (6.6, 6.6),
    "variation_normal": (4.4, 5.2),
    "variation_with_stall": (4.4, 5.2),
    "variation_damaged": (4.4, 5.2),
    "variation_ruin": (4.4, 5.2),
}

# Per-district building mix, from implementation_plan.md section 8.
MIX = {
    "1": {"bld_warehouse": 55, "bld_tenement": 50, "bld_shop": 25,
          "bld_townhouse": 20, "bld_tavern": 15, "bld_stables": 12,
          "variation_damaged": 12, "variation_normal": 11},
    "2": {"bld_tenement": 45, "bld_townhouse": 35, "bld_shop": 12,
          "bld_tavern": 10, "variation_damaged": 8, "variation_normal": 5},
    "3": {"bld_shop": 30, "bld_tavern": 12, "variation_with_stall": 10,
          "bld_townhouse": 10, "bld_tenement": 7, "monument_guildhouse": 1},
    "4": {"bld_cottage": 45, "bld_townhouse": 35, "bld_shop": 6,
          "variation_normal": 6, "bld_tavern": 3},
    "5": {"bld_warehouse": 20, "bld_blacksmith": 18, "bld_stables": 12,
          "bld_shop": 12, "bld_tenement": 8},
    "6": {"bld_townhouse": 30, "bld_tenement": 28, "bld_shop": 14,
          "bld_tavern": 8, "variation_ruin": 4, "variation_damaged": 3,
          "monument_church": 1, "monument_chapel": 1,
          "monument_guildhouse": 1},
    "7": {"monument_noble_manor": 14, "bld_townhouse": 14,
          "variation_normal": 6, "bld_stables": 4, "monument_chapel": 1,
          "monument_guildhouse": 1},
    "9": {"monument_keep": 1, "monument_watchtower": 4,
          "monument_gatehouse": 1, "bld_warehouse": 2, "bld_stables": 2,
          "bld_tenement": 2},
    "10": {"bld_cottage": 10, "bld_stables": 4, "bld_warehouse": 3,
           "monument_windmill": 1},
}


def _rescale_mix():
    """Keep each district's mix summing to its target count.

    The tables were written for the grid plan's 710 buildings; the radial plan
    wants 864, distributed differently. Rescaling here means the proportions
    stay authored and the totals stay correct without maintaining both.
    """
    for key, mix in MIX.items():
        d = P.DISTRICT_BY_KEY.get(key)
        if d is None:
            continue
        have = sum(mix.values())
        if have == 0:
            continue
        k = d.buildings / float(have)
        scaled = {}
        for kind, n in mix.items():
            scaled[kind] = max(1, int(round(n * k)))
        # Settle the rounding drift on the most common type.
        drift = d.buildings - sum(scaled.values())
        if drift:
            big = max(scaled, key=lambda kk: scaled[kk])
            scaled[big] = max(1, scaled[big] + drift)
        MIX[key] = scaled


_rescale_mix()


class Placement:
    __slots__ = ("kind", "x", "y", "z", "yaw", "district", "block")

    def __init__(self, kind, x, y, z, yaw, district, block):
        self.kind = kind
        self.x, self.y, self.z = x, y, z
        self.yaw = yaw
        self.district = district
        self.block = block

    def __repr__(self):
        return "<%s @(%.1f,%.1f,%.1f) %.0fdeg d%s>" % (
            self.kind, self.x, self.y, self.z, self.yaw, self.district)


def _gap(rng):
    """Party walls most of the time; an alley about one slot in twenty."""
    r = rng.random()
    if r < 0.75:
        return 0.0
    if r < 0.95:
        return rng.uniform(0.1, 0.6)
    return rng.uniform(1.8, 2.4)


def parcel(district, rng):
    """Cut a wedge into blocks along ARCS and SPOKES, not a grid.

    A radial city's block is bounded by two ring streets and two radial lanes,
    so it is a curved trapezoid, not a rectangle. Each block is returned as a
    polygon; the frontage walk then follows its outline, which is what makes
    the fabric curve with the street instead of stepping across it.
    """
    x0, y0, x1, y1 = district.rect
    cx, cy = P.CENTRE
    # Radial extent of this district, measured from its own polygon.
    rs = [hypot(px - cx, py - cy) for px, py in district.poly]
    angs = [degrees(atan2(py - cy, px - cx)) % 360.0 for px, py in
            district.poly]
    r_lo, r_hi = min(rs), max(rs)

    # Angular extent, unwrapped so a wedge crossing 0 deg is contiguous.
    angs_sorted = sorted(angs)
    gap, gap_at = 0.0, 0.0
    for i in range(len(angs_sorted)):
        d = (angs_sorted[(i + 1) % len(angs_sorted)] - angs_sorted[i]) % 360.0
        if d > gap:
            gap, gap_at = d, angs_sorted[(i + 1) % len(angs_sorted)]
    a_lo = gap_at
    a_hi = gap_at + (360.0 - gap)
    if gap < 12.0:            # a full ring, like the market square
        a_lo, a_hi = 0.0, 360.0

    depth_lo, depth_hi = district.block
    lane = 3.2 if district.key not in ("7", "9", "10") else 6.0

    # Ring bands across the district's depth.
    bands = []
    r = r_lo
    while r < r_hi - depth_lo * 0.5:
        d = rng.uniform(depth_lo, depth_hi)
        bands.append((r, min(r + d, r_hi)))
        r += d + lane
    if not bands:
        bands = [(r_lo, r_hi)]

    blocks = []
    for br0, br1 in bands:
        mid_r = (br0 + br1) * 0.5
        if mid_r < 1.0:
            continue
        # Keep block FRONTAGE roughly constant in metres, so an outer ring
        # gets more blocks than an inner one instead of wider ones.
        target = rng.uniform(26.0, 40.0)
        span = a_hi - a_lo
        count = max(1, int(round((span / 360.0) * 2 * pi * mid_r / target)))
        step = span / count
        lane_deg = degrees(lane / max(4.0, mid_r))
        for k in range(count):
            aa0 = a_lo + k * step
            aa1 = aa0 + step - lane_deg
            if aa1 - aa0 < 2.0:
                continue
            poly = G.sector(aa0, aa1, br0, br1, P.CENTRE, steps=4)
            mx, my = G.centroid(poly)
            if not district.contains(mx, my):
                continue
            blocks.append(poly)
    return blocks


def _box_of(kind, x, y, yaw, pad=0.0):
    """Axis-aligned footprint box. Yaw is always a multiple of 90 +/- 3 deg,
    so swapping w and d is exact enough for an occupancy test."""
    w, d = FOOTPRINT[kind]
    if abs((yaw % 180.0) - 90.0) < 45.0:
        w, d = d, w
    return (x - w * 0.5 - pad, y - d * 0.5 - pad,
            x + w * 0.5 + pad, y + d * 0.5 + pad)


def _grid_add(idx, box, cell=12.0):
    for gx in range(int(box[0] // cell), int(box[2] // cell) + 1):
        for gy in range(int(box[1] // cell), int(box[3] // cell) + 1):
            idx.setdefault((gx, gy), []).append(box)


def _grid_hits(idx, box, cell=12.0):
    out = []
    for gx in range(int(box[0] // cell), int(box[2] // cell) + 1):
        for gy in range(int(box[1] // cell), int(box[3] // cell) + 1):
            out.extend(idx.get((gx, gy), ()))
    return out


def _overlaps(box, others, tol=0.30):
    """True if `box` bites more than `tol` into any box already placed.

    Needed because the four edges of a block are walked independently: at a
    corner, the run along the south edge and the run along the east edge both
    want the same ground, and opposite edges meet in the middle of a narrow
    block. Measured before this test: 127 overlapping pairs, worst 5.8 m.
    """
    ax0, ay0, ax1, ay1 = box
    for bx0, by0, bx1, by1 in others:
        ox = min(ax1, bx1) - max(ax0, bx0)
        oy = min(ay1, by1) - max(ay0, by0)
        if ox > tol and oy > tol:
            return True
    return False


def _footing(box, tol=0.6):
    """The ground a footprint stands on, or None if it straddles a step.

    Sampling the centre alone is not enough: a house whose plan crosses a
    terrace edge has half its base 11 m in the air whatever single height it
    is given. Five samples -- the four corners and the middle -- and they all
    have to agree.
    """
    x0, y0, x1, y1 = box
    zs = [P.z_at(x, y) for (x, y) in
          ((x0, y0), (x1, y0), (x1, y1), (x0, y1),
           ((x0 + x1) * 0.5, (y0 + y1) * 0.5))]
    return zs[4] if max(zs) - min(zs) <= tol else None


def _usable(x, y):
    """A building may not stand in water, on a road, or on open ground."""
    if P.in_water(x, y):
        return False
    if P.in_open_area(x, y):
        return False
    if P.road_clearance(x, y) < 1.2:
        return False
    return True


def walk_district(district, rng, budget=None, occupied=None):
    """Walk every block's outline, packing buildings shoulder to shoulder."""
    budget = dict(MIX.get(district.key, {})) if budget is None else budget
    remaining = dict(budget)
    placements = []
    blocks = parcel(district, rng)
    rng.shuffle(blocks)

    # Occupancy is DISTRICT-WIDE, not per block. Kept per block it missed
    # every collision across a lane: a building pushed in from one block's
    # outer edge lands on its neighbour's inner edge, which measured 63
    # intersecting pairs at up to 4.2 m.
    if occupied is None:
        occupied = {}
    for bi, poly in enumerate(blocks):
        bcx, bcy = G.centroid(poly)
        outline = G.resample(list(poly) + [poly[0]], 3.0)
        # Walk the outline as one continuous frontage. In a radial city a
        # block edge is an ARC, so there are no four sides to iterate -- the
        # perimeter is the street frontage, all of it.
        i = 0
        guard = 0
        while i < len(outline) - 1 and guard < 4000:
            guard += 1
            ax, ay = outline[i]
            avail = [k for k, v in remaining.items() if v > 0]
            if not avail:
                break
            weights = [remaining[k] for k in avail]
            kind = rng.choices(avail, weights=weights, k=1)[0]
            w, d = FOOTPRINT[kind]

            # Outward normal: away from the block centre.
            nx_, ny_ = ax - bcx, ay - bcy
            L = hypot(nx_, ny_) or 1.0
            nx_, ny_ = nx_ / L, ny_ / L
            back = d * 0.5 + district.setback
            bxp = ax - nx_ * back
            byp = ay - ny_ * back

            if not _usable(bxp, byp) or not district.contains(bxp, byp):
                i += 1
                continue

            # Face the street: the facade looks outward along the normal.
            yaw = degrees(atan2(ny_, nx_)) - 90.0 + rng.uniform(-3.0, 3.0)
            box = _box_of(kind, bxp, byp, yaw)
            if _overlaps(box, _grid_hits(occupied, box)):
                i += 1
                continue
            # STAND ON THE GROUND, not on the quarter's nominal level. Using
            # district.z put 179 buildings up to 27 m off their own terrain
            # wherever the two disagreed. z_at is what the terrain mesh and
            # the collision slabs are both built from, so this cannot drift.
            gz = _footing(box)
            if gz is None:
                i += 1
                continue
            _grid_add(occupied, box)
            placements.append(Placement(kind, bxp, byp, gz, yaw,
                                        district.key, bi))
            remaining[kind] -= 1
            # Advance along the outline by this building's width plus a gap.
            advance = w + _gap(rng)
            travelled = 0.0
            while i < len(outline) - 1 and travelled < advance:
                px0, py0 = outline[i]
                px1, py1 = outline[i + 1]
                travelled += hypot(px1 - px0, py1 - py0)
                i += 1
    return placements, remaining


def build_all(seed=8101):
    """Placements for every district, plus the hand-placed landmarks."""
    rng = random.Random(seed)
    out = []
    shortfall = {}
    # One occupancy index for the WHOLE city. Per district it still missed the
    # seams: adjacent wedges share an edge, and two quarters both building up
    # to it collided there.
    occupied = {}
    for d in P.DISTRICTS:
        pl, rem = walk_district(d, rng, occupied=occupied)
        out.extend(pl)
        missing = {k: v for k, v in rem.items() if v > 0}
        if missing:
            shortfall[d.key] = missing
    return out, shortfall


if __name__ == "__main__":
    pls, short = build_all()
    by_d = {}
    for p in pls:
        by_d.setdefault(p.district, []).append(p)
    print("%-4s %-26s %6s %6s" % ("dist", "name", "target", "placed"))
    total_t = total_p = 0
    for d in P.DISTRICTS:
        got = len(by_d.get(d.key, []))
        print("%-4s %-26s %6d %6d%s" % (
            d.key, d.name, d.buildings, got,
            "" if got >= d.buildings * 0.9 else "   <-- SHORT"))
        total_t += d.buildings
        total_p += got
    print("%-4s %-26s %6d %6d" % ("", "TOTAL", total_t, total_p))
    if short:
        print()
        print("unplaced by district:")
        for k, v in sorted(short.items()):
            print("  %-4s %s" % (k, v))
