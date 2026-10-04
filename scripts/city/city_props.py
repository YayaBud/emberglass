"""
Clutter: what makes the layout a place rather than a correct diagram.

Two jobs:

1. **Fill the open ground.** The Noble Quarter and the Citadel are deliberately
   low-density -- forecourts and a castle ward ARE open -- but with nothing in
   them they render as dead voids, which the brief forbids. Formal beds, hedge
   runs, statues, fountains and tree rows are what make that openness read as
   designed rather than as unfinished.

2. **Dress the streets and the district interiors** with the props each quarter
   would actually have: crates and boats on the waterfront, wood piles and carts
   in the craftsmen quarter, wells and gardens in the west residential, stalls
   and lanterns at the market.

Props are placed as TRANSFORMS and instanced, same as the buildings: a well
appears 20 times and costs one mesh.
"""

import os
import sys
import random
from math import hypot, radians

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

import city_plan as P
import city_geom as G
import city_blocks as B


class Prop:
    __slots__ = ("kind", "x", "y", "z", "yaw")

    def __init__(self, kind, x, y, z, yaw):
        self.kind = kind
        self.x, self.y, self.z = x, y, z
        self.yaw = yaw

    def __repr__(self):
        return "<%s @(%.1f,%.1f)>" % (self.kind, self.x, self.y)


# Roughly how much ground a prop occupies, for the spacing test.
RADIUS = {
    "tree_large": 3.0, "tree_group": 3.4, "tree_small": 1.7, "bush": 1.0,
    "hedge": 1.4, "statue": 1.3, "fountain": 2.6, "well": 1.4,
    "market_stall_a": 2.2, "market_stall_b": 2.2, "cart": 2.0, "wagon": 2.4,
    "crates": 1.2, "barrels": 1.1, "wood_pile": 1.5, "hay_stack": 1.8,
    "crane": 2.6, "sail_boat": 3.4, "small_boat": 2.2, "fish_barrels": 1.2,
    "net_stack": 1.2, "boulder": 1.6, "rock_large": 1.4, "rock_small": 0.8,
    "planter": 0.9, "flowers": 0.7, "grass_patch": 1.0, "flower_box": 0.7,
    "bench": 1.2, "street_lamp": 0.6, "signpost": 0.6, "notice_board": 0.8,
    "clothesline": 2.0, "chest": 0.8, "sacks": 0.9, "ladder": 0.8,
    "banners": 0.6, "flags": 0.6, "spikes": 0.9, "ruins_pillar": 1.2,
    "dock_post": 0.5, "stone_fence": 1.4, "wood_fence": 1.4,
    "iron_fence": 1.4, "gate_small": 1.2, "post_chain": 0.8, "railing": 1.4,
    "ruin_wall": 1.8, "vines": 1.0, "ivy_wall": 1.0, "awning": 1.4,
    "plaza_tile": 1.4, "grassy_ground": 1.4, "monument_windmill": 3.0,
    "balcony": 1.2, "dead_tree": 2.2, "hanging_lantern": 0.5,
    "wall_lantern": 0.4,
}

# Scatter mix per district: kind -> how many.
SCATTER = {
    "1": {"crates": 26, "barrels": 24, "cart": 10, "wagon": 6, "sacks": 12,
          "fish_barrels": 12, "net_stack": 10, "crane": 3, "chest": 6,
          "clothesline": 8, "street_lamp": 14, "signpost": 5, "post_chain": 8,
          "wood_pile": 6, "ladder": 4},
    "2": {"clothesline": 16, "well": 4, "barrels": 14, "crates": 12,
          "flower_box": 12, "planter": 10, "bush": 10, "vines": 8,
          "ivy_wall": 6, "wood_fence": 10, "railing": 6, "awning": 6,
          "street_lamp": 8, "balcony": 10, "hanging_lantern": 8},
    "3": {"market_stall_a": 9, "market_stall_b": 8, "bench": 12,
          "street_lamp": 14, "planter": 12, "crates": 10, "barrels": 10,
          "cart": 5, "signpost": 5, "notice_board": 4, "awning": 6,
          "banners": 8, "flags": 6},
    "4": {"tree_small": 22, "tree_large": 9, "well": 5, "bush": 16,
          "flowers": 16, "flower_box": 12, "grass_patch": 14,
          "wood_fence": 16, "stone_fence": 10, "hedge": 14, "bench": 6,
          "clothesline": 6, "hay_stack": 4},
    "5": {"wood_pile": 16, "cart": 10, "wagon": 6, "barrels": 16,
          "crates": 16, "chest": 6, "hay_stack": 6, "ladder": 6,
          "spikes": 4, "iron_fence": 6, "sacks": 8, "street_lamp": 6},
    "6": {"ruin_wall": 6, "ruins_pillar": 5, "vines": 12, "ivy_wall": 10,
          "signpost": 6, "notice_board": 5, "awning": 8, "boulder": 5,
          "street_lamp": 10, "barrels": 10, "crates": 8, "bench": 6,
          "wall_lantern": 12, "balcony": 8, "hanging_lantern": 10},
    "7": {"hedge": 30, "statue": 7, "fountain": 3, "tree_large": 16,
          "tree_small": 12, "flowers": 20, "planter": 16, "bench": 10,
          "iron_fence": 18, "stone_fence": 10, "gate_small": 5,
          "grass_patch": 18, "banners": 6},
    "9": {"banners": 10, "flags": 8, "statue": 4, "well": 2,
          "wall_lantern": 8, "crates": 10,
          "barrels": 10, "hay_stack": 6, "spikes": 8, "post_chain": 6,
          "wood_pile": 4, "stone_fence": 8, "grass_patch": 10,
          "tree_small": 6},
    "10": {"hay_stack": 22, "wood_fence": 24, "cart": 6, "wagon": 4,
           "wood_pile": 8, "well": 3, "tree_group": 8, "tree_small": 12,
           "boulder": 6, "rock_large": 6, "rock_small": 8,
           "grass_patch": 16, "sacks": 6, "dead_tree": 7},
}

# What goes in the deliberately open areas, which otherwise read as voids.
OPEN_AREA_FILL = {
    "market_plaza": {"plaza_tile": 0, "market_stall_a": 5,
                     "market_stall_b": 4, "bench": 8, "street_lamp": 8,
                     "planter": 8, "crates": 6, "barrels": 6},
    "noble_gardens": {"hedge": 34, "flowers": 26, "tree_large": 12,
                      "tree_small": 10, "statue": 6, "fountain": 2,
                      "bench": 10, "planter": 14, "grass_patch": 20,
                      "iron_fence": 10},
    "citadel_ward": {"grass_patch": 18, "banners": 8, "statue": 3,
                     "crates": 10, "barrels": 10, "hay_stack": 8,
                     "spikes": 10, "post_chain": 8, "tree_small": 6,
                     "well": 2},
}


def _free(x, y, placed, r, buildings_idx, cell=12.0):
    """Nothing may sit in water, on a road, or on top of a building."""
    if P.in_water(x, y):
        return False
    if P.road_clearance(x, y) < r + 0.8:
        return False
    gx, gy = int(x // cell), int(y // cell)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for bx0, by0, bx1, by1 in buildings_idx.get((gx + dx, gy + dy), ()):
                if bx0 - r < x < bx1 + r and by0 - r < y < by1 + r:
                    return False
            for px, py, pr in placed.get((gx + dx, gy + dy), ()):
                if hypot(px - x, py - y) < (pr + r) * 0.85:
                    return False
    return True


def _scatter(rect, mix, rng, placed, buildings_idx, z, out, tries=60,
             poly=None):
    """Scatter inside a region. `poly` restricts to the real shape: a wedge's
    bounding box is mostly outside the wedge, so without it most of a
    district's props land in the neighbouring quarter or in the river."""
    x0, y0, x1, y1 = rect
    for kind, count in mix.items():
        if count <= 0:
            continue
        r = RADIUS.get(kind, 1.0)
        got = 0
        for _ in range(count * tries):
            if got >= count:
                break
            x = rng.uniform(x0 + r, x1 - r)
            y = rng.uniform(y0 + r, y1 - r)
            if poly is not None and not G.contains(poly, x, y):
                continue
            if not _free(x, y, placed, r, buildings_idx):
                continue
            gx, gy = int(x // 12.0), int(y // 12.0)
            placed.setdefault((gx, gy), []).append((x, y, r))
            # Ground under the prop, not the quarter's nominal level:
            # with d.z, 285 props ended up as much as 27 m off it.
            out.append(Prop(kind, x, y,
                            P.z_at(x, y) if z is None else z,
                            rng.uniform(0, 360)))
            got += 1


def _street_furniture(rng, placed, buildings_idx, out):
    """Lamps and signs along the main routes, at the kerb line."""
    n = 0
    for name, width, pts in P.MAIN_ROADS:
        for p0, p1 in zip(pts, pts[1:]):
            length = hypot(p1[0] - p0[0], p1[1] - p0[1])
            if length < 20:
                continue
            ux, uy = (p1[0] - p0[0]) / length, (p1[1] - p0[1]) / length
            px, py = -uy, ux
            step = 26.0
            d = step * 0.5
            side = 1
            while d < length - 6.0:
                o = side * (width * 0.5 + 1.5)
                x = p0[0] + ux * d + px * o
                y = p0[1] + uy * d + py * o
                kind = "street_lamp" if n % 3 else "signpost"
                r = RADIUS.get(kind, 0.6)
                if _free(x, y, placed, r, buildings_idx):
                    gx, gy = int(x // 12.0), int(y // 12.0)
                    placed.setdefault((gx, gy), []).append((x, y, r))
                    out.append(Prop(kind, x, y, P.z_at(x, y),
                                    rng.uniform(0, 360)))
                    n += 1
                d += step
                side = -side
    return n


def _harbour(rng, placed, buildings_idx, out):
    """Boats in the basin and posts along the quay."""
    basin = None
    for nm, poly in P.WATER_POLYS:
        if nm == "harbour":
            basin = poly
    if basin is None:
        return 0
    bx0, by0, bx1, by1 = G.bbox(basin)
    n = 0
    for kind, count in (("sail_boat", 5), ("small_boat", 9)):
        for _ in range(count):
            for _try in range(40):
                x = rng.uniform(bx0 + 8, bx1 - 8)
                y = rng.uniform(by0 + 8, by1 - 8)
                if G.contains(basin, x, y):
                    break
            out.append(Prop(kind, x, y, P.WATER_Z + 0.4,
                            rng.choice([0.0, 90.0, 180.0, 270.0])
                            + rng.uniform(-8, 8)))
            n += 1
    # Posts round the basin's own edge, not along a box.
    edge = G.resample(list(basin) + [basin[0]], 14.0)
    for (px, py) in edge:
        out.append(Prop("dock_post", px, py, 0.0, 0.0))
        n += 1

    # Cranes stand ON the quay, facing the water. Left to the district scatter
    # they never placed at all: a crane needs 2.6 m of clear ground and the
    # waterfront is the most tightly packed quarter in the city.
    from math import degrees, atan2
    for k in range(3):
        px, py = edge[int(len(edge) * (k + 0.5) / 3.0) % len(edge)]
        # Step inland until the ground is actually dry: 7% of the radius was
        # not always enough to clear the basin's own wobbled edge.
        ix = iy = None
        for shrink in [0.95 - 0.03 * j for j in range(12)]:
            tx, ty = px * shrink, py * shrink
            if not P.in_water(tx, ty):
                ix, iy = tx, ty
                break
        if ix is None:
            continue          # no dry quay on this stretch; skip the crane
        out.append(Prop("crane", ix, iy, P.z_at(ix, iy),
                        degrees(atan2(py - iy, px - ix))))
        n += 1
    return n


def build_all(seed=9101):
    rng = random.Random(seed)
    placements, _ = B.build_all()

    # Spatial index of building footprints so props never land on one.
    buildings_idx = {}
    for p in placements:
        box = B._box_of(p.kind, p.x, p.y, p.yaw, pad=0.6)
        for gx in range(int(box[0] // 12.0), int(box[2] // 12.0) + 1):
            for gy in range(int(box[1] // 12.0), int(box[3] // 12.0) + 1):
                buildings_idx.setdefault((gx, gy), []).append(box)

    placed = {}
    out = []

    for name, poly in P.OPEN_AREAS:
        mix = OPEN_AREA_FILL.get(name, {})
        _scatter(G.bbox(poly), mix, rng, placed, buildings_idx,
                 None, out, poly=poly)

    for d in P.DISTRICTS:
        mix = SCATTER.get(d.key, {})
        _scatter(d.rect, mix, rng, placed, buildings_idx, None, out,
                 poly=d.poly)

    _street_furniture(rng, placed, buildings_idx, out)
    _harbour(rng, placed, buildings_idx, out)
    return out


if __name__ == "__main__":
    props = build_all()
    by_kind = {}
    for p in props:
        by_kind[p.kind] = by_kind.get(p.kind, 0) + 1
    print("props placed:", len(props), "across", len(by_kind), "kinds")
    for k in sorted(by_kind, key=lambda k: -by_kind[k]):
        print("  %-18s %4d" % (k, by_kind[k]))
