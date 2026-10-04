"""
City level of detail.

The library's generators are written for one asset filling a 900px sprite. At
city scale a roof tile is sub-pixel, so the same geometry costs 459k faces to
render detail nobody can see. This module coarsens the EXISTING generators
through their existing parameters -- there is no new geometry code here, and no
generator body changes.

How it works: `set_lod(level)` sets a module-level scale that
`detail_buildings.build_structure` reads through `city_lod.L`. At level 1.0
(the default, and what every library sprite renders at) every derived value is
the literal the code used before, so the 110 sheet sprites are unchanged. Proof
is in `verify_neutral()`.

    L.course_h(0.21)   ->  0.21 at lod 1.0, coarser above
    L.tile_w(0.27)     ->  0.27 at lod 1.0
    L.growth(1.0)      ->  1.0  at lod 1.0, thinned above

The knobs are chosen by what dominates the face count. Measured on the
townhouse, the roof tile field and the masonry block courses together are ~80%
of it, cobbles another ~10%, so those three carry almost all the saving.
"""


class Lod:
    """A set of coarsening factors. `scale` 1.0 is the library default."""

    __slots__ = ("scale", "name")

    def __init__(self, scale=1.0, name="full"):
        self.scale = float(scale)
        self.name = name

    # -- masonry ------------------------------------------------------------
    def course_h(self, base):
        """Course height. Taller courses -> fewer rings of blocks."""
        return base * self.scale

    def block_len(self, base):
        """(min, max) block length. Longer blocks -> fewer per ring."""
        return (base[0] * self.scale, base[1] * self.scale)

    # -- roof ---------------------------------------------------------------
    def tile_w(self, base):
        return base * self.scale

    def exposure(self, base):
        """Course exposure. Larger -> fewer courses up the slope."""
        return base * self.scale

    def tile_len(self, base):
        return base * self.scale

    # -- ground -------------------------------------------------------------
    def cobble(self, base):
        return base * self.scale

    # -- weathering ---------------------------------------------------------
    def growth(self, base):
        """Moss, lichen and weed density.

        Thinned faster than the masonry is coarsened: a moss clump is a whole
        blob rather than one face, so growth is disproportionately expensive
        and disproportionately invisible at city distance.
        """
        if self.scale <= 1.0:
            return base
        return base / (self.scale * self.scale)

    def damage(self, base):
        """Slipped/cracked/missing tiles. Kept, but thinned with the field."""
        if self.scale <= 1.0:
            return base
        return base / self.scale

    def weed_rows(self, base):
        return base if self.scale <= 1.0 else max(0, int(base / self.scale))

    def detail(self, n):
        """Count of an optional decorative run -- corbels, string courses."""
        if self.scale <= 1.0:
            return n
        return max(1, int(round(n / self.scale)))

    # -- bevel --------------------------------------------------------------
    def bevel_segments(self, segments):
        """Segments on the chamfer modifier; 0 drops the modifier entirely.

        This is the single largest lever in the library. Measured on the
        townhouse foundation, 13,330 authored faces evaluate to 69,826 through
        a 2-segment bevel -- 5.2x, and up to 9.0x on the timber cores. Nothing
        else in the LOD comes close, because every generator returns through
        `detail_primitives._end`.

        The chamfer is what gives the stonework its lit edge, so it survives at
        'near'. At city distance it is sub-pixel and buys nothing.
        """
        if self.scale <= 1.0:
            return segments
        if self.scale < 2.0:
            return 1
        return 0

    @property
    def is_full(self):
        return self.scale == 1.0

    def __repr__(self):
        return "<Lod %s x%.2f>" % (self.name, self.scale)


#: Named levels. CITY is the one the 710-building scene uses.
LEVELS = {
    "full":   Lod(1.0, "full"),    # library sprites, hero landmarks
    "near":   Lod(1.7, "near"),    # buildings the player can walk up to
    "city":   Lod(2.6, "city"),    # the general mass of the city
    "far":    Lod(4.0, "far"),     # distant silhouette only
}

#: The live level. `build_structure` reads this. Default is the library value,
#: so importing this module changes nothing until set_lod is called.
L = LEVELS["full"]


def set_lod(level):
    """Set the active level. Accepts a name, a Lod, or a float scale."""
    global L
    if isinstance(level, Lod):
        L = level
    elif isinstance(level, str):
        if level not in LEVELS:
            raise KeyError("unknown lod %r; have %s"
                           % (level, sorted(LEVELS)))
        L = LEVELS[level]
    else:
        L = Lod(float(level), "custom")
    return L


def get_lod():
    return L


def verify_neutral():
    """At lod 'full' every accessor must return its input untouched.

    This is what guarantees the 110 library sprites still render identically
    after the lod argument is threaded through the shared driver.
    """
    set_lod("full")
    checks = [
        ("course_h", L.course_h(0.21), 0.21),
        ("block_len", L.block_len((0.17, 0.52)), (0.17, 0.52)),
        ("tile_w", L.tile_w(0.27), 0.27),
        ("exposure", L.exposure(0.185), 0.185),
        ("tile_len", L.tile_len(0.31), 0.31),
        ("cobble", L.cobble(0.44), 0.44),
        ("growth", L.growth(1.0), 1.0),
        ("damage", L.damage(1.2), 1.2),
        ("weed_rows", L.weed_rows(2), 2),
        ("detail", L.detail(6), 6),
        ("bevel_segments", L.bevel_segments(2), 2),
    ]
    bad = [(n, got, want) for n, got, want in checks if got != want]
    if bad:
        raise AssertionError("lod 'full' is not neutral: %r" % (bad,))
    return True


if __name__ == "__main__":
    verify_neutral()
    print("lod 'full' is neutral - library sprites unaffected")
    for key in ("full", "near", "city", "far"):
        lod = LEVELS[key]
        set_lod(lod)
        print("  %-5s x%.2f  course_h %.3f  tile_w %.3f  exposure %.3f  "
              "cobble %.3f  growth %.3f"
              % (key, lod.scale, L.course_h(0.21), L.tile_w(0.27),
                 L.exposure(0.185), L.cobble(0.44), L.growth(1.0)))
    set_lod("full")
