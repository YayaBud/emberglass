"""
The Emberglass master city blueprint, as data. RADIAL REWRITE.

Single source of truth for every coordinate. Terrain, walls, roads, blocks,
props and validation all read from here.

WHY THIS WAS REWRITTEN. The first version modelled everything as axis-aligned
rectangles and laid the streets on a grid, because the game camera's yaw is
locked and a diagonal street is hard to see down. Built and compared against
the blueprint, that was plainly the wrong trade: the blueprint is a RADIAL city
-- spokes running out from the market fountain through concentric ring roads,
an organic wall following the ground, and a river passing through the city
rather than around it. Making the streets axis-true did not cost "some of the
curve"; it replaced the city's entire structure with a grid in a box.

So the grid is gone. Streets are spokes and rings, districts are wedges around
the plaza, the wall is an organic polygon, and the river runs through the city
to a harbour inside the walls. The camera problem is real and is answered where
it belongs -- in the camera, with an occluder fade -- not by flattening the
city's plan into something the lens finds convenient.

Axes: +X east, +Y north, +Z up. Metres. Origin is the market square fountain.
Angles are maths convention: 0 deg = +X (east), 90 deg = +Y (north).
"""

import math
from math import hypot

import city_geom as G

# =============================================================================
# Extents and levels
# =============================================================================

TERRAIN = (-420.0, -380.0, 380.0, 330.0)

#: How far the city lays its OWN ground. Beyond this the world's terrain
#: is left alone.
#:
#: It used to cover the whole TERRAIN box, 800 x 710 m of dead flat mesh.
#: The game only holds the world level inside a site's Flat/Blend radius,
#: so past that the world went back to its natural height and the city's
#: flat plate hung over it -- ground floating in mid-air with the real
#: hillside visible underneath. A disc that fits inside the site's flat
#: pad cannot do that. It must stay <= Sites.Emberglass.Flat in the Godot
#: project, which is why the two are written down together here.
GROUND_R = 260.0

WATER_Z = -2.0
GROUND_Z = 0.0

#: The blueprint calls itself a DENSE 3-TERRACE WALLED CITY, and its ground
#: rises from the harbour in the south to the citadel in the north-east.
#: Three terraces plus the citadel's own mount.
TERRACE_Z = {
    "T0": 0.0,    # waterfront and harbour quay, south
    "T1": 11.0,   # the body of the city: market, residential, craftsmen
    "T2": 24.0,   # noble quarter, north
    "T3": 38.0,   # citadel, north-east, its own walled mount
}

CENTRE = (0.0, 0.0)

#: Concentric street radii: the plaza, then three ring roads, then the wall.
R_PLAZA = 34.0
R_RING1 = 78.0
R_RING2 = 132.0
R_RING3 = 186.0
R_WALL = 212.0

#: The built-up area: everything the masonry retaining walls serve, as
#: opposed to the rock skirts used out in open country. This was left at the
#: GRID plan's 420 x 300 m rectangle, but the radial city is 424 m across on
#: BOTH axes -- so every terrace edge north of y=150 or south of y=-150 got a
#: rock skirt where it should have had a built wall, which is a third of the
#: circuit.
BUILT = (-(R_WALL + 20.0), -(R_WALL + 20.0),
         R_WALL + 20.0, R_WALL + 20.0)

# =============================================================================
# Terraces, as polygons
# =============================================================================

#: Radius of the central plateau the market square stands on. Inside it the
#: ground is one level in every direction; outside it each quarter's wedge
#: takes its own.
R_PLATEAU = R_RING1 - 6.0

#: How far a quarter's ground runs past the wall before the outer apron takes
#: over. Small on purpose: the scarp belongs directly UNDER the curtain wall,
#: which is how a walled hill city reads from outside. Running the raised
#: ground far past the wall instead turns the whole city into a mesa floating
#: over the countryside, which is exactly what it looked like in game.
#:
#: The consequence is that a road may not leave a raised quarter — see the
#: spokes, which now terminate at their gate rather than carrying on into
#: fields 24 m below.
GROUND_OUT = 14.0

#: Degrees a quarter keeps clear of the seam with its neighbour.
#: About one building deep at the outer ring.
SEAM_INSET = 2.5


# =============================================================================
# Districts, as wedges around the plaza
# =============================================================================

class District:
    """One quarter: a wedge of the city, how high it sits, how much of it."""

    def __init__(self, key, name, a0, a1, r0, r1, terrace, buildings, fill,
                 setback=0.0, block=(30.0, 36.0), courtyard=9.0,
                 seed=0, wobble=0.05):
        # The WEDGE is kept, not just the polygon it makes. The ground level
        # is derived from these same angles, so a quarter and the terrace it
        # stands on cannot drift apart -- which is exactly what went wrong
        # when the two were authored separately.
        self.a0, self.a1, self.r0, self.r1 = a0, a1, r0, r1
        self.key = key
        self.name = name
        # The QUARTER is inset from its own angular edges; the GROUND
        # it stands on is not. The terrace wedges tile at a0/a1, so a
        # district reaching its own edge parcels blocks straight onto
        # the seam between two levels -- and a footprint across a 13 m
        # step has to be thrown away, which cost 15 to 20 buildings a
        # quarter and made the counts lurch on any change of a degree.
        seam = 0.0 if (a1 - a0) > 350.0 else SEAM_INSET
        self.poly = G.sector(a0 + seam, a1 - seam, r0, r1, CENTRE,
                             wobble=wobble, seed=seed)
        self.terrace = terrace
        self.buildings = buildings
        self.fill = fill
        self.setback = setback
        self.block = block
        self.courtyard = courtyard
        self.rect = G.bbox(self.poly)      # coarse iteration only; poly is truth

    @property
    def z(self):
        return TERRACE_Z[self.terrace]

    @property
    def area(self):
        return G.area(self.poly)

    def contains(self, x, y):
        return G.contains(self.poly, x, y)

    def __repr__(self):
        return "<District %s %s %d bldg>" % (self.key, self.name,
                                             self.buildings)


#: Bearings read off the blueprint: the citadel sits north-east above the Old
#: City, the noble quarter runs north to north-west, the harbour is due south,
#: and the riverside is south-west on the water.
#: THE ANGULAR SPANS TILE. They used to overlap -- Noble 96..174 against West
#: Residential 158..214, Riverside 214..262 against Lower City 258..320,
#: Craftsmen 316..368 against Lower City again -- and `district_at` returns
#: the FIRST match, so a building in an overlap belonged to one quarter and
#: stood on the other's ground. The Citadel is the deliberate exception: it
#: shares the Old City's bearings and sits radially ABOVE it, which is what
#: makes it a mount rather than a neighbour.
DISTRICTS = [
    District("3", "Market Square", 0, 359.9, 0.0, R_PLATEAU,
             "T1", 96, "3", setback=0.0, block=(20.0, 26.0), courtyard=7.0,
             seed=21),

    District("6", "Old City", 8, 92, R_RING1 - 4, R_RING2 + 16,
             "T1", 88, "6", setback=0.0, block=(17.0, 22.0), courtyard=5.0,
             seed=23),

    District("5", "Craftsmen Quarter", 320, 368, R_RING1 - 4, R_RING3 - 6,
             "T1", 104, "5", setback=0.0, block=(21.0, 27.0), courtyard=8.0,
             seed=27),

    District("4", "West Residential", 168, 214, R_RING1 - 4, R_RING3 - 4,
             "T1", 112, "4", setback=2.5, block=(30.0, 36.0), courtyard=12.0,
             seed=29),

    District("2", "Riverside", 214, 258, R_RING1 + 4, R_RING3 + 6,
             "T0", 110, "2", setback=0.0, block=(17.0, 22.0), courtyard=5.0,
             seed=31),

    District("1", "Lower City / Waterfront", 258, 320, R_RING1 - 2,
             R_RING3 - 2,
             "T0", 123, "1", setback=0.0, block=(18.0, 24.0), courtyard=6.0,
             seed=37),

    District("7", "Noble Quarter", 90, 168, R_RING1 + 14, R_WALL - 10,
             "T2", 86, "7", setback=3.0, block=(19.0, 24.0), courtyard=7.0,
             seed=41, wobble=0.04),

    # Rides on top of the Old City: same bearings, further out, higher. Its
    # inner radius must clear the Old City's outer one or the two quarters
    # claim the same ground at two levels.
    District("9", "Citadel / Upper", 24, 84, R_RING2 + 20, R_WALL - 2,
             "T3", 34, "9", setback=4.0, block=(30.0, 38.0), courtyard=14.0,
             seed=43, wobble=0.03),

    District("10", "Agricultural Edge", 300, 356, R_WALL + 12, R_WALL + 44,
             "T0", 22, '"', setback=6.0, block=(55.0, 80.0), courtyard=26.0,
             seed=47, wobble=0.06),
]


def _terrace_polys():
    """Ground level, DERIVED from the districts. Never declared twice.

    It used to be a separate hand-drawn set of bands, and the two disagreed:
    the T3 band reached in to r=124 while the Old City (T1) reached out to
    r=148, so 179 buildings and 285 props were placed at their quarter's level
    on ground the lookup put somewhere else -- up to 27 m out. That is what
    buried houses in the citadel mount and left props hanging in the air.

    Lowest first, though `terrace_at` no longer depends on the order:

        1. an apron over the whole map, so nothing is ever floorless
        2. the central plateau the market square stands on
        3. one wedge per quarter, from the plateau out past the wall
    """
    # NO map-wide apron. One was tried and it broke `build_ground`, which
    # draws the natural ground exactly where `terrace_at` is None: an apron
    # covering everything left it with nothing to draw and turned the whole
    # 800 x 710 m map into one flat terrace slab. Outside the terraces
    # `z_at` already falls through to GROUND_Z, which IS T0's height, so
    # nothing is floorless without it.
    out = [("T1", G.sector(0, 359.9, 0.0, R_PLATEAU + 2.0, CENTRE,
                           wobble=0.03, seed=5))]
    for d in DISTRICTS:
        if d.key in ("3", "10"):
            out.append((d.terrace, d.poly))
            continue
        # From the plateau outward, unless the quarter is itself a mount
        # standing on another quarter's ground -- which only the Citadel is,
        # and an outer radius is what marks one. Using each quarter's own r0
        # instead left an 11 m moat between the plateau edge at 74 and the
        # Noble Quarter's ground at 86, right where ring_1 runs.
        r_in = R_PLATEAU - 4.0 if d.r0 <= R_RING2 else d.r0 - 6.0
        out.append((d.terrace,
                    G.sector(d.a0, d.a1, r_in, R_WALL + GROUND_OUT, CENTRE,
                             wobble=0.028, seed=int(d.r1))))
    return out


TERRACE_POLYS = _terrace_polys()

DISTRICT_BY_KEY = {d.key: d for d in DISTRICTS}

#: Open ground: no buildings. The plaza, the noble gardens, the citadel ward.
OPEN_AREAS = [
    ("market_plaza", G.sector(0, 359.9, 0.0, R_PLAZA, CENTRE, wobble=0.04,
                              seed=51)),
    ("noble_gardens", G.sector(112, 160, R_RING2 + 12, R_WALL - 26, CENTRE,
                               wobble=0.03, seed=53)),
    ("citadel_ward", G.sector(42, 80, R_RING2 + 20, R_WALL - 30, CENTRE,
                              wobble=0.02, seed=57)),
]


# =============================================================================
# Water: THROUGH the city, not around it
# =============================================================================

#: The river comes off the north-west highland, falls, runs down the west
#: flank, and swings east across the south into the harbour -- which is INSIDE
#: the wall, at the water gate.
RIVER_COURSE = [
    (-330.0, 300.0), (-300.0, 236.0), (-278.0, 170.0), (-268.0, 96.0),
    (-260.0, 26.0), (-250.0, -44.0), (-228.0, -110.0), (-186.0, -166.0),
    (-120.0, -206.0), (-40.0, -224.0), (46.0, -228.0), (130.0, -224.0),
    (210.0, -232.0), (300.0, -258.0), (380.0, -300.0),
]
RIVER_HALF = [26, 26, 28, 30, 32, 34, 38, 44, 54, 66, 74, 70, 60, 52, 46]

#: The harbour basin, cut up into the city at the south gate.
#: The basin sits OUTSIDE the waterfront band and inside the wall's southern
#: bulge. Overlapping it with the Lower City put 368 of that district's 644
#: frontage points underwater and cost it 90 buildings.
HARBOUR = G.sector(252, 288, R_RING3 + 6, R_WALL + 44, CENTRE, wobble=0.03,
                   seed=61)

#: A second arm off the east highland, falling twice on its way down.
EAST_ARM = [
    (330.0, 250.0), (312.0, 176.0), (300.0, 106.0), (296.0, 40.0),
    (300.0, -30.0), (306.0, -104.0), (300.0, -170.0), (280.0, -226.0),
]
EAST_HALF = [16, 17, 18, 19, 20, 22, 26, 34]

WATER_POLYS = [
    ("river", G.band(RIVER_COURSE, RIVER_HALF)),
    ("harbour", HARBOUR),
    ("east_arm", G.band(EAST_ARM, EAST_HALF)),
]

# The islet stood at r=339, outside GROUND_R, so when the river was
# clipped to the city's own ground it was left as a rock alone in mid
# air with no sea around it. Moved to open water off the harbour mouth:
# found by sweeping for a point whose whole 24 m surround is wet and
# which is clear of every bridge. The lighthouse is a REQUIRED hero
# landmark and may never be substituted, so it moves rather than goes.
LIGHTHOUSE_AT = (-107.0, -201.0)
LIGHTHOUSE_ISLAND = G.sector(0, 359.9, 0.0, 22.0, LIGHTHOUSE_AT, seed=63)

# MEASURED, not chosen. These were the grid plan's map-edge cliffs at
# r=307..334, which the ground disc no longer reaches -- three falls
# pouring down dry air. Each of these is a point where the river
# actually meets a terrace scarp, found by sweeping the plan for wet
# ground with a drop of 6 m or more within 22 m.
WATERFALLS = [
    ("noble_scarp", (-230.0, 40.0), 24.0, -2.0),
    ("riverside", (-176.0, -140.0), 11.0, -2.0),
    ("harbour_mouth", (172.0, -164.0), 11.0, 0.0),
]


# =============================================================================
# Fortification: an organic circuit, plus the citadel's own enclave
# =============================================================================

def _wall_polygon():
    """Not a box. The circuit pinches at the north-west gorge and bulges south
    around the harbour mouth, the way the blueprint draws it."""
    pts = []
    steps = 72
    for i in range(steps):
        a = 2 * math.pi * i / steps
        deg = math.degrees(a) % 360
        r = R_WALL
        r -= 22.0 * math.exp(-((deg - 146.0) / 26.0) ** 2)
        r += 30.0 * math.exp(-((deg - 270.0) / 22.0) ** 2)
        r += 8.0 * math.sin(a * 3.0 + 1.1)
        pts.append((math.cos(a) * r, math.sin(a) * r))
    pts.append(pts[0])
    return pts


WALL_POLY = _wall_polygon()

#: The citadel is its own walled enclave with an inner gate, as drawn.
CITADEL_WALL = G.sector(26, 94, R_RING2 - 10, R_WALL - 6, CENTRE, wobble=0.02,
                        seed=67)

WALL_RUNS = [WALL_POLY, CITADEL_WALL + [CITADEL_WALL[0]]]

TOWER_SPACING = 52.0
BRIDGE_HALF_SPAN = 26.0


def _on_wall(deg):
    """Where the wall crosses a bearing -- gates sit on the circuit."""
    a = math.radians(deg)
    best = None
    for (x, y) in WALL_POLY:
        d = abs(((math.degrees(math.atan2(y, x)) - deg + 180) % 360) - 180)
        if best is None or d < best[0]:
            best = (d, hypot(x, y))
    return (math.cos(a) * best[1], math.sin(a) * best[1])


# =============================================================================
# Circulation: spokes and rings
# =============================================================================

def _spoke_at(bearing, r):
    a = math.radians(bearing)
    return (math.cos(a) * r, math.sin(a) * r)


MAIN_ROADS = []
for _i, _b in enumerate((90.0, 180.0, 0.0, 270.0)):
    # Terminates AT its gate. It used to run 60 m further into the fields,
    # which is 24 m below the raised quarters — the road walked off a cliff.
    MAIN_ROADS.append(("spoke_%d" % int(_b), 10.0,
                       G.spoke(_b, R_PLAZA - 6, R_WALL + 8, CENTRE,
                               bend=6.0 if _i % 2 else -6.0)))
MAIN_ROADS.append(("spoke_citadel", 9.0,
                   G.spoke(58.0, R_PLAZA, R_WALL - 26, CENTRE, bend=-9.0)))
MAIN_ROADS.append(("ring_1", 8.0, G.ring(R_RING1, CENTRE, 40, 0.02, 71)))

SECONDARY_ROADS = [
    ("ring_2", 6.5, G.ring(R_RING2, CENTRE, 48, 0.025, 73)),
    ("ring_3", 6.0, G.ring(R_RING3, CENTRE, 56, 0.03, 79)),
]
for _b in (45.0, 135.0, 225.0, 315.0):
    SECONDARY_ROADS.append(("spoke_%d" % int(_b), 6.0,
                            G.spoke(_b, R_PLAZA, R_RING3 + 10, CENTRE,
                                    bend=8.0)))
SECONDARY_ROADS.append(("south_road", 7.0,
                        [(60.0, -250.0), (150.0, -286.0), (250.0, -300.0),
                         (330.0, -290.0)]))

# Trim every road to the city's own ground. `south_road` ran from
# (60,-250) out to (330,-290), entirely outside GROUND_R, so its
# carriageway was a slab laid over the world's terrain at whatever
# height the city happened to use.
def _within_disc(pts, margin=6.0):
    return [p for p in pts if hypot(*p) <= GROUND_R - margin]


ALL_ROADS = [(n, w, _within_disc(pts))
             for (n, w, pts) in MAIN_ROADS + SECONDARY_ROADS]
ALL_ROADS = [r for r in ALL_ROADS if len(r[2]) >= 2]
MAIN_ROADS = [r for r in ALL_ROADS if r[0] in
              set(n for (n, _w, _p) in MAIN_ROADS)]
SECONDARY_ROADS = [r for r in ALL_ROADS if r not in MAIN_ROADS]


def _gate_on_spoke(bearing):
    """Where a spoke crosses the wall circuit.

    The spokes are bowed by a few degrees so the city does not read as a wheel,
    which means the road does NOT arrive on its nominal bearing: placing a gate
    at _on_wall(bearing) put it up to 22 m off its own street.
    """
    target = hypot(*_on_wall(bearing))
    want = "spoke_%d" % int(bearing)
    best = None
    for name, _w, pts in MAIN_ROADS:
        # ONLY this bearing's own spoke. Searching every main road returned
        # whichever happened to have a point nearest the wall radius, so all
        # four gates collapsed onto the same street and the compass labels
        # came out scrambled -- north at the bottom of the map.
        if name != want:
            continue
        for (x, y) in G.resample(pts, 2.0):
            d = abs(hypot(x, y) - target)
            if best is None or d < best[0]:
                best = (d, x, y)
    if best is None:
        return _on_wall(bearing)
    return (best[1], best[2])


GATES = [
    ("north", _gate_on_spoke(90.0), 90.0, 10.0),
    ("west", _gate_on_spoke(180.0), 180.0, 10.0),
    ("east", _gate_on_spoke(0.0), 0.0, 10.0),
    ("south", _gate_on_spoke(270.0), 270.0, 11.0),
    ("citadel", (math.cos(math.radians(58)) * (R_RING2 - 8),
                 math.sin(math.radians(58)) * (R_RING2 - 8)), 58.0, 8.0),
]




#: Level changes, all of them on a route.
TRANSITIONS = [
    ("grand_stair", _spoke_at(90.0, R_RING1 + 20), "T2", "T1", "stairs_large"),
    ("citadel_gate", _spoke_at(58.0, R_RING2 - 8), "T3", "T2",
     "gatehouse_ramp"),
    ("harbor_ramp", _spoke_at(270.0, R_RING1 + 16), "T1", "T0",
     "ramp_switchback"),
    ("riverside_steps", _spoke_at(232.0, R_RING1 + 14), "T1", "T0",
     "stairs_large"),
    ("west_steps", _spoke_at(196.0, R_RING1 + 10), "T1", "T0", "stairs_small"),
    ("noble_ramp", _spoke_at(135.0, R_RING1 + 18), "T2", "T1",
     "ramp_switchback"),
    ("noble_steps_e", _spoke_at(110.0, R_RING2 - 4), "T2", "T1",
     "stairs_large"),
    ("citadel_steps", _spoke_at(45.0, R_RING2 + 8), "T3", "T2",
     "stairs_large"),
    ("old_city_ramp", _spoke_at(74.0, R_RING1 + 12), "T2", "T1",
     "ramp_switchback"),
    ("quay_steps", _spoke_at(290.0, R_RING2 + 10), "T1", "T0",
     "stairs_small"),
    # The east spoke drops off the city mound onto the farm ground.
    ("east_ramp", (204.0, -16.0), "T1", "T0", "ramp_switchback"),
]

def _auto_transitions():
    """Every place a road crosses a terrace seam gets a built transition.

    A ring road circles the whole city, so it crosses every band boundary --
    twelve of them on the first pass. Hand-listing those is a maintenance trap:
    move a terrace and the list silently goes stale. Walking the roads and
    emitting one per crossing means the data can never disagree with itself.

    A main road gets a ramp because carts use it; a secondary gets stairs.
    """
    main_names = set(n for n, _w, _p in MAIN_ROADS)
    found = []
    for name, _w, pts in ALL_ROADS:
        pr = G.resample(pts, 5.0)
        for (x0, y0), (x1, y1) in zip(pr, pr[1:]):
            t0, t1 = terrace_at(x0, y0), terrace_at(x1, y1)
            if t0 is None or t1 is None or t0 == t1:
                continue
            mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
            if any(hypot(mx - px, my - py) < 30.0 for _n, (px, py), _a, _b,
                   _k in TRANSITIONS):
                continue
            if any(hypot(mx - px, my - py) < 26.0 for _n, (px, py), _a, _b,
                   _k in found):
                continue
            kind = "ramp_switchback" if name in main_names else "stairs_large"
            found.append(("auto_%s_%d" % (name, len(found)), (mx, my),
                          t0, t1, kind))
    return found




BRIDGES = [
    ("west_bridge", (-262.0, 8.0), "stone_bridge", "x"),
    ("harbour_bridge", (-150.0, -190.0), "arch_bridge", "x"),
    ("south_bridge", (40.0, -226.0), "stone_bridge", "y"),
    ("east_bridge", (298.0, 10.0), "stone_bridge", "x"),
    # The southern road out to the farms crosses the river where it
    # widens below the harbour. Found by check_transitions().
    ("farm_bridge", (213.0, -262.0), "stone_bridge", "x"),
    ("south_ford", (137.0, -281.0), "arch_bridge", "x"),
]

# Only the crossings on the city's own ground survive. The rest sat on
# the river's far reaches, which are no longer drawn -- a bridge there
# would span open air over the world's terrain.
BRIDGES = [b for b in BRIDGES if hypot(*b[1]) <= GROUND_R - 8.0]

LANDMARKS = [
    ("fountain", "fountain", (0.0, 0.0), "T1"),
    ("keep", "monument_keep", _spoke_at(62.0, R_RING3 + 6), "T3"),
    ("church", "monument_church", _spoke_at(20.0, R_RING2 - 16), "T1"),
    ("chapel", "monument_chapel", _spoke_at(134.0, R_RING2 + 20), "T2"),
    ("guildhouse", "monument_guildhouse", _spoke_at(18.0, R_RING1 + 12), "T1"),
    # Follows the fields. They were pulled in to a belt outside the
    # gates when the city stopped laying its own ground out to 372 m.
    ("windmill", "monument_windmill", _spoke_at(330.0, R_WALL + 28), "T0"),
    ("lighthouse", "monument_lighthouse", LIGHTHOUSE_AT, "T0"),
]


# =============================================================================
# Queries
# =============================================================================

def terrace_at(x, y):
    """The HIGHEST terrace covering this point.

    It used to return whichever matched last, which made the answer depend on
    the order of a list -- so a mount laid before the ground it stands on
    silently lost. Taking the highest is what "standing on" actually means.
    """
    found = None
    best = None
    for name, poly in TERRACE_POLYS:
        z = TERRACE_Z[name]
        if (best is None or z > best) and G.contains(poly, x, y):
            found, best = name, z
    return found


def in_water(x, y):
    # Outside the city's own ground there is no city water. The river
    # course runs to r=495 and the east arm to r=424, both far past
    # GROUND_R -- drawn, that is a channel of water with no banks
    # lying over the world's own terrain, and the bridges on it hang
    # in the void. Past the disc the world's water takes over.
    if hypot(x, y) > GROUND_R:
        return False
    if G.contains(LIGHTHOUSE_ISLAND, x, y):
        return False
    for _n, poly in WATER_POLYS:
        if G.contains(poly, x, y):
            return True
    return False


def z_at(x, y):
    t = terrace_at(x, y)
    if t:
        return TERRACE_Z[t]
    return WATER_Z if in_water(x, y) else GROUND_Z


def in_open_area(x, y):
    for _n, poly in OPEN_AREAS:
        if G.contains(poly, x, y):
            return True
    return False


def district_at(x, y):
    for d in DISTRICTS:
        if d.contains(x, y):
            return d
    return None


def _point_segment_distance(px, py, ax, ay, bx, by):
    return G.point_segment_distance(px, py, ax, ay, bx, by)


def road_clearance(x, y):
    best = 1e9
    for _n, width, pts in ALL_ROADS:
        for a, b in zip(pts, pts[1:]):
            d = G.point_segment_distance(x, y, a[0], a[1], b[0], b[1])
            best = min(best, d - width * 0.5)
    return best


def nearest_road(x, y):
    best = (None, 1e9, None)
    for name, _w, pts in ALL_ROADS:
        for a, b in zip(pts, pts[1:]):
            d = G.point_segment_distance(x, y, a[0], a[1], b[0], b[1])
            if d < best[1]:
                axis = "x" if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else "y"
                best = (name, d, axis)
    return best


def road_bearing(x, y):
    """Bearing of the nearest road in degrees, so a building faces its street.

    In a radial city this replaces the grid's four fixed yaws: a house on a
    ring road faces along the arc, a house on a spoke faces across it.
    """
    best = (1e9, 0.0)
    for _n, _w, pts in ALL_ROADS:
        for a, b in zip(pts, pts[1:]):
            d = G.point_segment_distance(x, y, a[0], a[1], b[0], b[1])
            if d < best[0]:
                best = (d, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))
    return best[1]


#: Generated once the terrain queries above exist: the ring roads cross
#: every band boundary, and hand-listing those goes stale the moment a
#: terrace moves.
TRANSITIONS += _auto_transitions()

# =============================================================================
# Checks
# =============================================================================

def check_water_connected():
    river = WATER_POLYS[0][1]
    bad = []
    for name, poly in WATER_POLYS[1:]:
        touch = any(G.contains(river, x, y) for x, y in poly) or \
                any(G.contains(poly, x, y) for x, y in river)
        if not touch:
            bad.append(name)
    return bad


def check_waterfalls_wet():
    return [(n, "no water at the drop") for n, (x, y), _t, _b in WATERFALLS
            if not in_water(x, y)]


def check_transitions(tol=34.0):
    bad = []
    for name, _w, pts in ALL_ROADS:
        pr = G.resample(pts, 5.0)
        for (x0, y0), (x1, y1) in zip(pr, pr[1:]):
            z0, z1 = z_at(x0, y0), z_at(x1, y1)
            if abs(z1 - z0) < 0.5:
                continue
            mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
            near = min((hypot(mx - tx, my - ty)
                        for _n, (tx, ty), _a, _b, _k in TRANSITIONS),
                       default=1e9)
            gate = min((hypot(mx - gx, my - gy)
                        for _n, (gx, gy), _f, _wd in GATES), default=1e9)
            brid = min((max(0.0, hypot(mx - bx, my - by) - BRIDGE_HALF_SPAN)
                        for _n, (bx, by), _a, _ax in BRIDGES), default=1e9)
            if min(near, gate, brid) > tol:
                bad.append((name, round(mx), round(my), round(z1 - z0, 1)))
    return bad


def total_buildings():
    return sum(d.buildings for d in DISTRICTS)


if __name__ == "__main__":
    print("districts      ", len(DISTRICTS))
    print("buildings      ", total_buildings())
    print("wall radius    ", R_WALL, " rings", R_RING1, R_RING2, R_RING3)
    print("roads          ", len(ALL_ROADS), "(%d spokes, %d rings)" % (
        sum(1 for n, _w, _p in ALL_ROADS if n.startswith("spoke")),
        sum(1 for n, _w, _p in ALL_ROADS if n.startswith("ring"))))
    dry = check_water_connected()
    print("water connected", "OK" if not dry else "DISCONNECTED %r" % (dry,))
    wf = check_waterfalls_wet()
    print("waterfalls wet ", "OK" if not wf else "DRY %r" % (wf,))
    tr = check_transitions()
    print("layer changes  ", "OK" if not tr else "UNBRIDGED %d: %r"
          % (len(tr), tr[:5]))
    print("terraces       ", " ".join("%s=%+.0f" % (k, v) for k, v in
                                      sorted(TERRACE_Z.items(),
                                             key=lambda kv: kv[1])))
    for d in DISTRICTS:
        print("  %-3s %-26s %-3s %4d bldg  %7.0f m2  %5.0f m2/bldg"
              % (d.key, d.name, d.terrace, d.buildings, d.area,
                 d.area / d.buildings))
