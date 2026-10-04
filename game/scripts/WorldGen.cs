using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The shape and the colour of the whole world, as pure functions of (x, z).
///
/// Nothing here holds state, allocates per call in the hot path, or needs a
/// node in the tree. That is the point: the terrain mesh, its collision and
/// anything placed on the ground later all have to agree about where the
/// ground IS, and the only way to guarantee that is for every one of them to
/// call the same function rather than keep a copy.
///
/// Carried over intact from the previous project, minus the site pads and
/// road grading that used to sit in Height -- there are no sites and no
/// roads here. Add them back as a layer ON TOP of Raw, never inside it:
/// keeping "natural ground" separate is what let a site's pad level be
/// defined as the natural height at its centre without the definition
/// being circular.
/// </summary>
public static class WorldGen
{
    public static ulong Seed = 1337;

    /// <summary>Scratch for the biome weights. Not thread-safe; see the note on Sample.</summary>
    [System.ThreadStatic] private static float[]? _w;

    private static float[] W
    {
        get { _w ??= new float[Biomes.Count]; return _w; }
    }

    /// <summary>The road centreline, in world XZ. See <see cref="PathDistance"/>.
    /// a=-30 and a=+90 in the camera's path space (World XZ = a*F + b*R,
    /// F=(-0.7071,0,-0.7071)) -- computed once by <c>Village</c>'s caller and
    /// inlined here so this stays a plain data layer with no dependency on it.</summary>
    public static Vector2 PathFrom = new(21.2f, 21.2f);
    public static Vector2 PathTo = new(-63.6f, -63.6f);
    public const float PathHalfWidth = 2.1f;

    /// <summary>Distance from (x, z) to the road segment, in world units.</summary>
    public static float PathDistance(float x, float z)
    {
        var p = new Vector2(x, z);
        var ab = PathTo - PathFrom;
        var len2 = ab.LengthSquared();
        var t = len2 > 1e-6f ? Mathf.Clamp((p - PathFrom).Dot(ab) / len2, 0f, 1f) : 0f;
        return (p - (PathFrom + ab * t)).Length();
    }

    /// <summary>
    /// Natural elevation: the blended regions and nothing else.
    ///
    /// Kept separate from <see cref="Height"/> so that a site's pad level can be
    /// defined as "the natural ground at the site's centre" without the
    /// definition being circular.
    /// </summary>
    public static float Raw(float x, float z)
    {
        var p = new Vector2(x, z);
        var w = W;
        Biomes.Weights(p, Seed, w);

        var h = 0f;
        for (var i = 0; i < w.Length; i++)
        {
            if (w[i] < 0.002f) continue;
            var r = Biomes.All[i];
            var n = Biomes.Fbm(x * r.Grain, z * r.Grain, Seed + (ulong)i * 104729UL) - 0.5f;
            h += w[i] * (r.Base + n * r.Relief);
        }

        // One shared fine octave across every region. Without it each region's
        // own grain is the only detail and the seams between two smooth regions
        // read as a change of material rather than a change of country.
        h += (Biomes.Fbm(x * 0.075f, z * 0.075f, Seed ^ 0xFEEDUL) - 0.5f) * 1.35f;

        // Ridges through the Crags. Absolute-value noise gives creases rather
        // than lumps, which is the difference between mountains and hills.
        var crag = W[(int)Biome.Crags];
        if (crag > 0.01f)
        {
            var ridge = 1f - Mathf.Abs(Biomes.Fbm(x * 0.012f, z * 0.012f, Seed ^ 0xC2A6UL) * 2f - 1f);
            h += crag * ridge * ridge * 30f;
        }

        // Dune crests. A second, rotated sine rippling over the smooth base is
        // what makes sand read as sand: long parallel ridges, no small detail.
        var dune = W[(int)Biome.Dunes];
        if (dune > 0.01f)
        {
            var a = x * 0.7071f + z * 0.7071f;
            h += dune * (Mathf.Sin(a * 0.055f) * 0.5f + 0.5f)
                      * (2.6f + 3.4f * Biomes.Fbm(x * 0.006f, z * 0.006f, Seed ^ 0xD00EUL));
        }

        // The world ends in mountains rather than at the edge of a mesh.
        var r2 = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z));
        if (r2 > Biomes.HalfWorld - 110f)
        {
            // capped at 600 m (t = 2, 622 m out): past that it was thousands of
            // metres, and Emberglass stands on the plateau beyond the south edge
            // (CityPlan). Nothing inside the world is that far out.
            var t = Mathf.Min((r2 - (Biomes.HalfWorld - 110f)) / 110f, 2f);
            h += t * t * 150f;
        }
        return h;
    }

    /// <summary>
    /// Final elevation: natural ground, levelled under every site and graded
    /// along every road.
    /// </summary>
    // + what was sculpted in the editor (Terrain3D; exactly 0 where nothing was)
    public static float Height(float x, float z) => CityPlan.Apply(x, z, Pond(x, z, Oasis(x, z, Dell(x, z, Raw(x, z))))) + TerrainEdit.Offset(x, z);

    /// <summary>Oases in the Ashdunes (centre, radius): a basin carved into
    /// the dell, 1.1 m deep, its water at <see cref="OasisLevel"/>.</summary>
    public static (Vector2 C, float R)[] Oases = { (new(222f, 333f), 8f) };
    private static ulong _oasisFor = ulong.MaxValue;
    private static float[] _oasisH = new float[Oases.Length];

    /// <summary>The oasis' water surface: the levelled ground at its centre,
    /// less 0.2 m.</summary>
    public static float OasisLevel(int i)
    {
        if (System.Threading.Volatile.Read(ref _oasisFor) != Seed)
        {
            for (var k = 0; k < Oases.Length; k++)
                _oasisH[k] = Dell(Oases[k].C.X, Oases[k].C.Y, Raw(Oases[k].C.X, Oases[k].C.Y)) - 0.2f;
            System.Threading.Volatile.Write(ref _oasisFor, Seed);
        }
        return _oasisH[i];
    }

    private static float Oasis(float x, float z, float h)
    {
        for (var i = 0; i < Oases.Length; i++)
        {
            var (c, r) = Oases[i];
            var d = new Vector2(x - c.X, z - c.Y).Length();
            if (d > r * 1.6f) continue;
            var level = OasisLevel(i) + 0.2f;
            // wobbled shore, 1.1 m deep in the middle, back to the ground by 1.3 r
            var wob = (Biomes.Fbm(x * 0.4f, z * 0.4f, Seed ^ 0x0A5EUL) - 0.5f) * 0.25f * r;
            h = Mathf.Min(h, level - 1.1f + 1.1f * Mathf.SmoothStep(r * 0.2f, r * 1.3f, d + wob));
        }
        return h;
    }

    /// <summary>The lamp walk's dell in the Hoarfells: the ground eases level
    /// within ~30 m of the walk's middle (and blends back by 55 m), rising
    /// 5 cm per metre down the view with a gentle undulation, so the path
    /// recedes into fog on open ground as the snow reference frames it. On
    /// the raw hillside the camera looked into a wall of slope (snow sweep
    /// round 1, 2026-09-23). Only lowers or raises inside the dell: no
    /// `--meshhash` probe is near it.</summary>
    // Centred on the vista (14 m down the walk), not the walk's middle: the
    // camera stands ~25 m back from the player, and a bowl centred further on
    // put it behind the rim, which cut a flat wall across the lower frame.
    // The other scenes of the snow sheet got dells of their own: on the raw
    // hillside every one of them framed a slope, the camera looking into or
    // down it (tour 2 2026-09-23). Applied in order; where two overlap the
    // ground blends from one level to the next.
    public static (Vector2 C, float R)[] Dells =
    {
        (new(-406.4f, 450.6f), 70f),   // the lamp walk
        (new(-462f, 398f), 32f),       // the cliff edge at the walk's end
        (new(-470f, 478f), 48f),       // the village outskirts (centred toward the camera, like the lamp walk's)
        (new(-438f, 364f), 46f),       // the ruins (ditto: at 40 m off the view its rim crossed the frame)
        (new(-362f, 378f), 38f),       // the mountain pass
        // the Ashdunes' scenes -- all clear of the `--meshhash` probe chunk
        // (2, 2) (x, z 192..288), so the probes do not move
        (new(325f, 318f), 45f),        // the market street
        (new(365f, 227f), 45f),        // the temple approach
        (new(334f, 184f), 34f),        // the temple plaza
        (new(230f, 347f), 50f),        // the oasis
    };
    private static ulong _dellFor = ulong.MaxValue;
    private static float[] _dellH = new float[Dells.Length];

    private static float Dell(float x, float z, float h)
    {
        if (System.Threading.Volatile.Read(ref _dellFor) != Seed)
        {
            // each level is the NATURAL ground at its centre (Raw), so it does
            // not depend on the order the dells are applied in
            for (var i = 0; i < Dells.Length; i++) _dellH[i] = Raw(Dells[i].C.X, Dells[i].C.Y);
            System.Threading.Volatile.Write(ref _dellFor, Seed);
        }
        for (var i = 0; i < Dells.Length; i++)
        {
            var (c, r) = Dells[i];
            var dx = x - c.X;
            var dz = z - c.Y;
            var d2 = dx * dx + dz * dz;
            if (d2 > r * r) continue;
            var along = -(dx + dz) * 0.7071f;   // metres down the view (along F)
            var target = _dellH[i] + 0.05f * along
                       + (Biomes.Fbm(x * 0.075f, z * 0.075f, Seed ^ 0xDE11UL) - 0.5f) * 0.6f;
            h = Mathf.Lerp(h, target, Mathf.SmoothStep(r, r * 0.55f, Mathf.Sqrt(d2)));
        }
        return h;
    }

    /// <summary>The water test site's pond, world XZ: path space (a 5, b -85),
    /// screen-left of the village, in chunk (-1, 0) -- not a
    /// <c>--meshhash</c> probe, so the probes prove the carve stays local.</summary>
    public static Vector2 PondCentre = new(-63.64f, 56.57f);
    public const float PondRadius = 40f;   // 13 until the boat, 22 until the ship (2026-09-23)
    /// <summary>Water depth in the middle: room for the ship's 1.35 m draft.</summary>
    public const float PondDepth = 2.6f;

    private static ulong _pondFor = ulong.MaxValue;
    private static float _pondLevel;

    /// <summary>The pond's water surface: a little under the lowest natural
    /// ground on its rim, so the water can never spill over the bank. A pure
    /// function of the seed, cached per seed (every thread computes the same
    /// value, so the race is harmless).</summary>
    public static float PondLevel
    {
        get
        {
            if (System.Threading.Volatile.Read(ref _pondFor) == Seed) return _pondLevel;
            var lo = float.MaxValue;
            for (var i = 0; i < 64; i++)
            {
                var t = i / 64f * Mathf.Tau;
                var r = PondShore(t);
                for (var k = 0; k < 4; k++)
                {
                    var d = r * (1f + k * 0.12f);
                    lo = Mathf.Min(lo, Raw(PondCentre.X + Mathf.Cos(t) * d, PondCentre.Y + Mathf.Sin(t) * d));
                }
            }
            _pondLevel = lo - 0.25f;
            System.Threading.Volatile.Write(ref _pondFor, Seed);
            return _pondLevel;
        }
    }

    /// <summary>Shoreline radius at angle `t`: a wobbled circle, not a disc.</summary>
    public static float PondShore(float t) =>
        PondRadius * (0.7f + 0.6f * Biomes.Fbm(Mathf.Cos(t) * 1.3f + 11f, Mathf.Sin(t) * 1.3f + 5f, Seed ^ 0x90DDUL, 2));

    /// <summary>Dig the pond: <see cref="PondDepth"/> in the middle, the waterline at the
    /// wobbled shore, banks rising out of it. Only ever lowers the ground
    /// (`min`), and far outside the basin rises faster than any natural
    /// ground, so the cut-off at 2.4 R is seamless.</summary>
    private static float Pond(float x, float z, float h)
    {
        var dx = x - PondCentre.X;
        var dz = z - PondCentre.Y;
        var d = Mathf.Sqrt(dx * dx + dz * dz);
        if (d > PondRadius * 2.4f) return h;
        var r = PondShore(Mathf.Atan2(dz, dx));
        var level = PondLevel;
        var bank = Mathf.Max(0f, d - r * 1.25f);
        var basin = level - PondDepth + PondDepth * Mathf.SmoothStep(r * 0.3f, r, d)
                  + 0.5f * Mathf.SmoothStep(r, r * 1.25f, d) + bank * bank * 0.6f;
        return Mathf.Min(h, basin);
    }

    public static Vector3 Snap(Vector3 p) => new(p.X, Height(p.X, p.Z), p.Z);
    public static Vector3 Snap(Vector2 p) => new(p.X, Height(p.X, p.Y), p.Y);

    /// <summary>Surface normal by central difference.</summary>
    public static Vector3 Normal(float x, float z)
    {
        const float e = 1.0f;
        var dx = Height(x + e, z) - Height(x - e, z);
        var dz = Height(x, z + e) - Height(x, z - e);
        return new Vector3(-dx, 2f * e, -dz).Normalized();
    }

    /// <summary>Steepness, 0 flat to 1 vertical. The scatter's main filter.</summary>
    public static float Slope(float x, float z) => 1f - Normal(x, z).Y;

    /// <summary>
    /// Ground colour at a point: the blended regions, then rock on steep faces,
    /// then the road, then a per-facet value jitter.
    ///
    /// The order matters. Road last-but-one means a road stays a road when it
    /// climbs; jitter last means every surface gets the facet break-up, and
    /// without it the flat-shaded quads read as a smooth gradient and the whole
    /// point of faceting is lost.
    /// </summary>
    public static Color Albedo(float x, float z, float slope) => Albedo(x, z, slope, out _);

    /// <summary>As <see cref="Albedo(float, float, float)"/>, and how much this
    /// is desert (the Ashdunes' weight, 0 below 0.02): the terrain carries it
    /// in the vertex UV for the ground shaders' sand.</summary>
    public static Color Albedo(float x, float z, float slope, out float desert) => Albedo(x, z, slope, out desert, out _);

    /// <summary>...and the Fen's weight (0 below 0.02), from which the terrain and the
    /// walk both read the mud (<see cref="Surface.Mud"/>).</summary>
    public static Color Albedo(float x, float z, float slope, out float desert, out float fen) =>
        TerrainEdit.Paint(x, z, AlbedoGen(x, z, slope, out desert, out fen));

    /// <summary>The ground colour as generated, before any painting (<see cref="TerrainEdit.Paint"/>).</summary>
    public static Color AlbedoGen(float x, float z, float slope, out float desert, out float fen)
    {
        var p = new Vector2(x, z);
        var w = W;
        Biomes.Weights(p, Seed, w);

        var mix = Biomes.Fbm(x * 0.031f, z * 0.031f, Seed ^ 0x51E77EUL);
        float rr = 0f, gg = 0f, bb = 0f;
        for (var i = 0; i < w.Length; i++)
        {
            if (w[i] < 0.002f) continue;
            var r = Biomes.All[i];
            var c = r.Ground.Lerp(r.GroundAlt, mix);
            rr += c.R * w[i]; gg += c.G * w[i]; bb += c.B * w[i];
        }
        var col = new Color(rr, gg, bb);

        // Exposed rock. Bare stone on anything steep is what makes a landform
        // read as carved rather than as a green sheet thrown over geometry.
        var rock = new Color(0.150f, 0.140f, 0.128f);
        col = col.Lerp(rock, Mathf.Clamp((slope - 0.24f) * 2.4f, 0f, 0.92f));

        // The road: a dirt band along PathFrom-PathTo, edge wobbled by noise so
        // it doesn't read as a ruled line. Height is untouched -- the road is
        // colour only, and follows whatever the ground under it already does.
        var pathD = PathDistance(x, z);
        var edge = PathHalfWidth + (Biomes.Fbm(x * 0.35f, z * 0.35f, Seed ^ 0x7A7AUL) - 0.5f) * 1.2f;
        var onPath = 1f - Mathf.SmoothStep(edge - 0.6f, edge + 0.4f, pathD);
        if (onPath > 0f)
        {
            var dirtVar = 1f + (Biomes.Fbm(x * 0.05f, z * 0.05f, Seed ^ 0xD127UL) - 0.5f) * 0.2f;
            var dirt = new Color(0.21f * dirtVar, 0.15f * dirtVar, 0.09f * dirtVar);
            col = col.Lerp(dirt, onPath * 0.92f);
        }

        var j = 0.89f + Biomes.Hash(Mathf.FloorToInt(x), Mathf.FloorToInt(z), Seed) * 0.22f;
        // alpha = how much this is snow country: the ground shaders lay snow
        // by it (0 everywhere else, so nothing outside the fells changes)
        var snow = w[(int)Biome.Snow];
        var dune = w[(int)Biome.Dunes];
        desert = dune < 0.02f ? 0f : dune;
        var fw = w[(int)Biome.Fen];
        fen = fw < 0.02f ? 0f : fw;
        return new Color(col.R * j, col.G * j, col.B * j, snow < 0.02f ? 0f : snow);
    }

    /// <summary>The Ashdunes site's centre (the region's is (280, 270)).
    /// Declared before <see cref="Trails"/>: static initialisers run in text
    /// order, and read after it this would still be (0, 0).</summary>
    public static readonly Vector2 DesertSiteCentre = new(300f, 290f);

    /// <summary>The old trails through the Hoarfells, as segments (a.xy, b.xy)
    /// in world XZ: a main trail up from the Crags that winds through the
    /// fells, and two branches. The ground shader packs the snow along them;
    /// <see cref="SnowSite"/> keeps trees and rocks off them.</summary>
    public static Vector4[] Trails = Polylines(new Vector2(-430f, 430f),
        new[] { new Vector2(110f, -110f), new(70f, -62f), new(36f, -40f), new(10f, -8f), new(-15f, 10f), new(-30f, 45f), new(-20f, 90f), new(-52f, 122f) },
        new[] { new Vector2(10f, -8f), new(42f, 14f), new(82f, 28f), new(120f, 18f) },
        new[] { new Vector2(-15f, 10f), new(-60f, 2f), new(-104f, -22f) },
        // the lamp walk: straight down the locked view (along F), as the
        // reference frames its path -- segments 12-14 (SnowSite dresses it)
        new[] { new Vector2(34f, 30f), new(12f, 10f), new(-10f, -12f), new(-38f, -36f) },
        // the sheet's other scenes, each down the view too: the mountain pass
        // (15-16, toward the Crags), the village outskirts (17-18), the ruins
        // (19-20)
        new[] { new Vector2(90f, -30f), new(68f, -52f), new(45f, -75f) },
        new[] { new Vector2(-30f, 58f), new(-52f, 36f), new(-74f, 14f) },   // 20 m in: the camera stood past the world's edge
        new[] { new Vector2(0f, -58f), new(-22f, -80f), new(-44f, -102f) })
        // The Ashdunes' caravan trails (Phase 5), segments 21-26, all down the
        // view from the desert site's centre: the market street (21-22), the
        // temple approach (23-24), the oasis (25-26). Packed sand, not snow.
        .Concat(Polylines(DesertSiteCentre,
            new[] { new Vector2(30f, 30f), new(0f, 0f), new(-30f, -30f) },
            new[] { new Vector2(100f, -40f), new(75f, -65f), new(50f, -90f) },
            new[] { new Vector2(-60f, 75f), new(-85f, 50f), new(-110f, 25f) })).ToArray();

    /// <summary>Frozen pools in the Hoarfells, (x, z, radius x, radius z):
    /// ice on the ground shader's own terms (the sheet's ice tile), placed
    /// where the scenes frame them -- the random icy hollows were never
    /// caught in a frame (tour 2026-09-23). One beside the lamp walk, one at
    /// the cabins, one at the ruins.</summary>
    public static Vector4[] IcePools =
    {
        new(-404f, 440f, 5f, 3.2f), new(-492f, 470f, 5f, 3.5f), new(-441f, 353f, 4.5f, 3f),
    };

    private static Vector4[] Polylines(Vector2 c, params Vector2[][] lines)
    {
        var segs = new System.Collections.Generic.List<Vector4>();
        foreach (var l in lines)
            for (var i = 0; i + 1 < l.Length; i++)
                segs.Add(new Vector4(c.X + l[i].X, c.Y + l[i].Y, c.X + l[i + 1].X, c.Y + l[i + 1].Y));
        return segs.ToArray();
    }

    /// <summary>Distance from (x, z) to the nearest old snow trail.</summary>
    public static float TrailDistance(float x, float z)
    {
        var p = new Vector2(x, z);
        var best = float.MaxValue;
        foreach (var s in Trails)
        {
            var a = new Vector2(s.X, s.Y);
            var ab = new Vector2(s.Z, s.W) - a;
            var t = Mathf.Clamp((p - a).Dot(ab) / ab.LengthSquared(), 0f, 1f);
            best = Mathf.Min(best, (p - a - ab * t).Length());
        }
        return best;
    }

    /// <summary>
    /// Water level in the Fen. Everything below this is under standing water,
    /// which <see cref="World"/> draws as one large plane per chunk.
    /// </summary>
    public const float FenWaterLevel = -5.4f;

    /// <summary>After <see cref="Layout.Apply"/> replaced the data (trails, dells, oases,
    /// the pond, the ice pools): the height caches keyed on the seed are stale.</summary>
    public static void Rebuild()
    {
        _oasisH = new float[Oases.Length];
        _dellH = new float[Dells.Length];
        System.Threading.Volatile.Write(ref _oasisFor, ulong.MaxValue);
        System.Threading.Volatile.Write(ref _dellFor, ulong.MaxValue);
        System.Threading.Volatile.Write(ref _pondFor, ulong.MaxValue);
    }
}
