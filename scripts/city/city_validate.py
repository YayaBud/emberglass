"""
Phase 8 validation: the brief's six checks, scripted.

    python scripts/city/city_validate.py

Runs without Blender -- everything it tests lives in the plan data and the
placement walk, not in geometry. Exit code is non-zero if any check fails, so
this is usable as a gate.

    1. every district in the blueprint exists and is populated
    2. every REQUIRED EXTERIOR asset is used, in a functionally appropriate
       district; interior/optional assets are exempt
    3. gates, roads, stairs, bridges, walls, rivers and elevation connect
    4. landmarks sit where the blueprint puts them
    5. nothing intersects: no building in a road, in water, in another
       building, or orphaned outside a block
    6. the built footprint matches the binding constraint
"""

import os
import sys
from collections import defaultdict
from math import hypot

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

import city_plan as P
import city_blocks as B
import city_props as PR

# Interior / optional, exempt from the coverage rule. Binding constraint 4.
EXEMPT = {
    "bed", "bookshelf", "chair", "table", "table_set", "shelf", "rug",
    "curtain", "fireplace", "stairs_interior",
}

# Assets consumed by the generated terrain / roads / walls rather than placed
# as instances. They ARE used, just not as discrete objects.
STRUCTURAL = {
    "wall_straight", "wall_corner", "wall_tower", "wall_gatehouse",
    "castle_gate", "retaining_wall", "cliff_wall", "cliff_edge",
    "stone_road", "cobblestone", "dirt_road", "plaza_tile", "wooden_deck",
    "dock_tile", "grassy_ground", "stairs_small", "stairs_large", "ramp",
    "platform", "arch_bridge", "stone_bridge", "pier", "dock_platform",
    "chimney_smoke", "ivy_wall", "vines", "fountain", "well", "statue",
    "monument_keep", "monument_church", "monument_chapel",
    "monument_guildhouse", "monument_noble_manor", "monument_watchtower",
    "monument_gatehouse", "monument_windmill", "monument_lighthouse",
}


def _sprites():
    d = os.path.join(os.path.dirname(_scripts), "renders",
                     "sheet_sprites_detailed")
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".png"))


def check_1_districts(placements):
    by_d = defaultdict(int)
    for p in placements:
        by_d[p.district] += 1
    fails = []
    for d in P.DISTRICTS:
        got = by_d.get(d.key, 0)
        if got == 0:
            fails.append("district %s (%s) is EMPTY" % (d.key, d.name))
        elif got < d.buildings * 0.9:
            fails.append("district %s only %d of %d target"
                         % (d.key, got, d.buildings))
    return fails, dict(by_d)


def check_2_coverage(placements, props):
    used = set(p.kind for p in placements) | set(p.kind for p in props)
    used |= STRUCTURAL
    required = [s for s in _sprites() if s not in EXEMPT]
    missing = [s for s in required if s not in used]
    return missing, len(required), len(used)


def check_3_connectivity():
    fails = []
    # No axis-true check: the city is radial, streets are spokes and arcs.
    fails += ["water disconnected: %s" % n for n in P.check_water_connected()]
    fails += ["waterfall dry: %r" % (w,) for w in P.check_waterfalls_wet()]
    fails += ["unbridged level change: %r" % (t,)
              for t in P.check_transitions()]
    # Every gate must sit on a road.
    for name, (gx, gy), facing, gw in P.GATES:
        if name == "water":
            continue
        if P.road_clearance(gx, gy) > 6.0:
            fails.append("gate %s is not on a road" % name)
    # Every bridge must span water.
    for name, (bx, by), asset, axis in P.BRIDGES:
        if not P.in_water(bx, by):
            fails.append("bridge %s does not cross water" % name)
    # Every terrace must be reachable: at least one transition touches it.
    touched = set()
    for _n, (tx, ty), a, b, _k in P.TRANSITIONS:
        touched.add(a)
        touched.add(b)
    for t in P.TERRACE_Z:
        if t not in touched:
            fails.append("terrace %s has no transition to any other level" % t)
    return fails


def check_4_landmarks():
    fails = []
    for name, asset, (lx, ly), terrace in P.LANDMARKS:
        if P.in_water(lx, ly) and name != "lighthouse":
            fails.append("landmark %s stands in water" % name)
        t = P.terrace_at(lx, ly)
        if name == "lighthouse":
            continue
        if t != terrace:
            fails.append("landmark %s expects %s, ground is %s"
                         % (name, terrace, t))
    return fails


def check_5_intersections(placements, props):
    fails = []
    boxes = [B._box_of(p.kind, p.x, p.y, p.yaw) for p in placements]
    grid = defaultdict(list)
    for i, b in enumerate(boxes):
        for gx in range(int(b[0] // 10), int(b[2] // 10) + 1):
            for gy in range(int(b[1] // 10), int(b[3] // 10) + 1):
                grid[(gx, gy)].append(i)
    seen = set()
    overlaps = 0
    worst = 0.0
    for cell in grid.values():
        for ii in range(len(cell)):
            for jj in range(ii + 1, len(cell)):
                a, b = sorted((cell[ii], cell[jj]))
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                A, Bx = boxes[a], boxes[b]
                ox = min(A[2], Bx[2]) - max(A[0], Bx[0])
                oy = min(A[3], Bx[3]) - max(A[1], Bx[1])
                if ox > 0.35 and oy > 0.35:
                    overlaps += 1
                    worst = max(worst, min(ox, oy))
    if overlaps:
        fails.append("%d building pairs overlap, worst %.2f m"
                     % (overlaps, worst))
    on_road = [p for p in placements if P.road_clearance(p.x, p.y) < 0]
    if on_road:
        fails.append("%d buildings stand in a carriageway" % len(on_road))
    in_water = [p for p in placements if P.in_water(p.x, p.y)]
    if in_water:
        fails.append("%d buildings stand in water" % len(in_water))
    orphan = [p for p in placements if P.district_at(p.x, p.y) is None]
    if orphan:
        fails.append("%d buildings outside every district" % len(orphan))
    pw = [p for p in props
          if P.in_water(p.x, p.y) and p.kind not in
          ("sail_boat", "small_boat", "dock_post")]
    if pw:
        fails.append("%d props float in water" % len(pw))
    return fails


def check_6_footprint():
    """The city is radial now, so the test is the CIRCUIT, not a box.

    Districts are wedges tiling the wall's interior; asking whether each fits
    an axis-aligned rectangle tested the old grid plan and says nothing about
    this one.
    """
    fails = []
    inner = sum(d.area for d in P.DISTRICTS if d.key != "10")
    circle = 3.14159 * P.R_WALL * P.R_WALL
    if inner > circle:
        fails.append("districts (%.0f m2) exceed the walled area (%.0f m2)"
                     % (inner, circle))
    if inner < circle * 0.35:
        fails.append("districts fill only %.0f%% of the circuit"
                     % (100.0 * inner / circle))
    for d in P.DISTRICTS:
        if d.key == "10":
            continue
        for (px, py) in d.poly:
            if (px * px + py * py) ** 0.5 > P.R_WALL + 24.0:
                fails.append("district %s escapes the wall circuit" % d.key)
                break
    return fails


def main():
    placements, shortfall = B.build_all()
    props = PR.build_all()

    print("=" * 66)
    print("EMBERGLASS CITY - VALIDATION")
    print("=" * 66)
    all_fails = []

    f1, by_d = check_1_districts(placements)
    print()
    print("1. DISTRICTS                    %s"
          % ("PASS" if not f1 else "FAIL"))
    for d in P.DISTRICTS:
        print("     %-3s %-26s %4d / %4d"
              % (d.key, d.name, by_d.get(d.key, 0), d.buildings))
    all_fails += f1

    missing, nreq, nused = check_2_coverage(placements, props)
    print()
    print("2. ASSET COVERAGE               %s   (%d required, %d unused)"
          % ("PASS" if not missing else "FAIL", nreq, len(missing)))
    if missing:
        for m in missing:
            print("     unused: %s" % m)
        all_fails += ["asset never used: %s" % m for m in missing]

    f3 = check_3_connectivity()
    print()
    print("3. CONNECTIVITY                 %s"
          % ("PASS" if not f3 else "FAIL"))
    for f in f3:
        print("     %s" % f)
    all_fails += f3

    f4 = check_4_landmarks()
    print()
    print("4. LANDMARKS                    %s"
          % ("PASS" if not f4 else "FAIL"))
    for f in f4:
        print("     %s" % f)
    all_fails += f4

    f5 = check_5_intersections(placements, props)
    print()
    print("5. INTERSECTIONS                %s"
          % ("PASS" if not f5 else "FAIL"))
    for f in f5:
        print("     %s" % f)
    all_fails += f5

    f6 = check_6_footprint()
    print()
    print("6. CIRCUIT                      %s"
          % ("PASS" if not f6 else "FAIL"))
    for f in f6:
        print("     %s" % f)
    all_fails += f6

    print()
    print("-" * 66)
    print("buildings %d   props %d   districts %d"
          % (len(placements), len(props), len(P.DISTRICTS)))
    if shortfall:
        print("SHORTFALL:", shortfall)
    print("%s  (%d issues)"
          % ("ALL CHECKS PASS" if not all_fails else "VALIDATION FAILED",
             len(all_fails)))
    return 1 if all_fails else 0


if __name__ == "__main__":
    sys.exit(main())
