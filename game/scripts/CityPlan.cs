using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Emberglass as the user's EMBERGLASS MASTER CITY PLAN draws it (2026-09-23
/// rework: "not a procedural circular town"). Every outline here is TRACED
/// from the sheet: plan x = (px - 743) * 0.37, y = (378 - py) * 0.37 metres,
/// the fountain at pixel (743, 378) -- 0.37 m/px makes the walled city the
/// sheet's 420 x 300 m. +x east, +y north; north is laid along the locked
/// camera's view, so the game frames it as the sheet draws it.
///
/// Terrain hierarchy (levels over the city's base): water -1.5, Lower City 0,
/// Riverside 2.5, the city terrace 7 (Market, West Residential, Old City,
/// Craftsmen), Noble 13, Citadel 20; fields outside the east wall at 2.
/// Every change of level is a retaining block, a quay, a road ramp on an
/// embankment, or stairs -- the terrain itself stays flat per terrace, so the
/// 2 m heightfield never shows a raw slope.
///
/// Water: the river from the north-west falls runs outside the west wall to
/// the west falls and the estuary; the canal under the inner wall joins the
/// estuary; the harbour and estuary are one sea; the east tributary drops
/// from the north-east highlands, cascades by the east gate, runs through
/// the fields and falls into the estuary in the south-east.
///
/// Pure data and pure functions (the ground runs on the chunk workers);
/// <see cref="Layout"/> places the buildings and props once.
/// </summary>
public static class CityPlan
{
    public static Vector2 Centre = new(0f, -1050f);
    internal static Vector2 R = new(0.70710678f, -0.70710678f);
    internal static Vector2 F = new(-0.70710678f, -0.70710678f);

    public static Vector2 ToWorld(Vector2 p) => Centre + R * p.X + F * p.Y;
    public static Vector2 DirToWorld(Vector2 d) => R * d.X + F * d.Y;

    public static Vector2 ToPlan(float x, float z)
    {
        var d = new Vector2(x - Centre.X, z - Centre.Y);
        return new Vector2(d.Dot(R), d.Dot(F));
    }

    // ------------------------------------------------------------------ levels
    public const float Sea = -1.5f, Lower = 0f, Riverside = 2.5f, City = 7f, NobleLv = 13f, CitadelLv = 20f, Farm = 2f;
    public const float Influence = 330f, Outer = 400f;
    /// <summary>A retaining block reaches this far each side of a level
    /// change: past the heightfield's worst-case 2.83 m diagonal.</summary>
    public const float EdgeHalf = 3f;

    public enum Quarter { Market, OldCity, Craftsmen, WestRes, Noble, Citadel, Riverside, LowerCity, Farms, Strip, Isle, Outside }

    public static float Level(Quarter q) => q switch
    {
        Quarter.Noble => NobleLv,
        Quarter.Citadel => CitadelLv,
        Quarter.Riverside => Riverside,
        Quarter.LowerCity or Quarter.Strip => Lower,
        Quarter.Isle => Lower + 1.5f,
        Quarter.Farms => Farm,
        _ => City,
    };

    // ------------------------------------------------------------------ traced outlines
    /// <summary>The city's edge: curtain wall ('W') and harbour quays ('Q').</summary>
    public static Vector2[] Encl =
    {
        new(-190f, 10f), new(-188f, 29f), new(-168f, 51f), new(-142f, 74f), new(-112f, 93f), new(-79f, 106f),
        new(-45f, 115f), new(-5f, 120f), new(28f, 122f), new(60f, 127f), new(117f, 130f), new(167f, 120f),
        new(174f, 88f), new(170f, 57f), new(188f, 40f), new(206f, 16f), new(221f, -15f), new(225f, -44f),
        new(217f, -67f), new(188f, -82f), new(158f, -100f), new(139f, -119f), new(117f, -134f), new(60f, -127f),
        new(4f, -121f), new(-13f, -121f), new(-13f, -78f), new(-60f, -76f), new(-120f, -80f), new(-168f, -84f),
        new(-186f, -52f), new(-190f, -26f),
    };
    /// <summary>Edge i -> i+1 is wall (true) or quay (false).</summary>
    public static bool EdgeIsWall(int i) => i < 22 || i >= 29;

    public static Vector2[] SeaPoly =
    {
        new(-250f, -4f), new(-215f, -2f), new(-199f, -18f), new(-194f, -52f), new(-172f, -88f), new(-120f, -84f),
        new(-60f, -80f), new(-16f, -80f), new(-16f, -124f), new(4f, -125f), new(60f, -131f), new(117f, -138f),
        new(146f, -140f), new(175f, -150f), new(207f, -146f), new(250f, -168f), new(360f, -176f), new(360f, -440f),
        new(-360f, -440f), new(-360f, -150f), new(-270f, -120f), new(-255f, -60f),
    };
    /// <summary>The causeway to the water gate: land through the harbour.</summary>
    public static readonly Rect2 Strip = new(-14f, -153f, 18f, 32f);
    public static Vector2 Isle = new(-206f, -112f);
    public const float IsleR = 13f;

    public static Vector2[] Canal =
    {
        new(-205f, -41f), new(-150f, -34f), new(-100f, -38f), new(-50f, -44f), new(-4f, -50f), new(40f, -57f),
        new(90f, -64f), new(140f, -70f), new(185f, -76f),
    };
    public const float CanalHw = 8f;

    public static Vector2[] CitadelPoly =
        { new(60f, 127f), new(117f, 130f), new(167f, 120f), new(174f, 88f), new(170f, 57f), new(118f, 52f), new(62f, 54f) };
    public static Vector2[] NoblePoly =
    {
        new(-114f, 92f), new(-79f, 106f), new(-45f, 115f), new(-5f, 120f), new(28f, 122f), new(60f, 127f), new(62f, 54f),
        new(38f, 49f), new(0f, 50f), new(-40f, 50f), new(-80f, 62f),
    };
    public static Vector2[] MarketPoly =
        { new(-40f, -12f), new(-36f, 24f), new(-2f, 30f), new(30f, 24f), new(40f, -8f), new(14f, -34f), new(-28f, -32f) };
    public static Vector2[] OldCityPoly =
    {
        new(38f, 49f), new(62f, 54f), new(118f, 52f), new(170f, 57f), new(188f, 40f), new(150f, 24f), new(100f, 14f),
        new(56f, 2f), new(40f, -8f), new(30f, 24f),
    };
    public static Vector2[] FarmPoly =
    {
        new(145f, -126f), new(162f, -106f), new(190f, -90f), new(224f, -76f), new(236f, -86f), new(232f, -108f),
        new(214f, -128f), new(198f, -138f), new(175f, -146f), new(150f, -140f),
    };
    /// <summary>26 m, not 16 (user, 2026-09-24: the city "is way too
    /// together"): room round the fountain for groups of stalls, trees and
    /// open paving, as the reference towns have.</summary>
    public const float PlazaR = 26f;
    /// <summary>The small squares at the big junctions (<see cref="Squares"/>).</summary>
    public const float SquareR = 7f;

    /// <summary>Streams above the sea: (line, water level, half width).</summary>
    public static (Vector2[] Line, float Level, float Hw)[] Reaches =
    {
        (new Vector2[] { new(-128f, 112f), new(-160f, 86f), new(-190f, 58f), new(-208f, 30f), new(-213f, 6f), new(-214f, -4f) }, 5f, 6f),
        (new Vector2[] { new(204f, 64f), new(222f, 40f), new(236f, 12f), new(243f, -12f), new(246f, -26f) }, 4f, 5f),
        (new Vector2[] { new(247f, -32f), new(248f, -60f), new(238f, -95f), new(218f, -125f), new(203f, -141f) }, 0.5f, 5f),
    };

    /// <summary>Waterfalls: where, which way the water falls, from and to.</summary>
    public static (string Name, Vector2 At, Vector2 Dir, float Top, float Foot, float Width)[] Falls =
    {
        ("North-west falls", new(-124f, 116f), new(-0.78f, -0.62f), 27f, 5f, 12f),
        ("West falls", new(-214f, -6f), new(0f, -1f), 5f, Sea, 12f),
        ("East falls", new(200f, 68f), new(0.6f, -0.8f), 24f, 4f, 10f),
        ("East gate cascade", new(246.5f, -29f), new(0f, -1f), 4f, 0.5f, 10f),
        ("South-east falls", new(203f, -142f), new(0f, -1f), 0.5f, Sea, 10f),
    };

    internal static (Vector2 P, float H)[] Highland =
    {
        (new(-160f, 140f), 27f), (new(-80f, 160f), 26f), (new(0f, 165f), 25f), (new(80f, 168f), 27f), (new(170f, 150f), 28f),
        (new(232f, 80f), 24f), (new(290f, 20f), 16f), (new(300f, -80f), 4f), (new(260f, -125f), 2f), (new(-280f, 60f), 12f),
        (new(-260f, 115f), 18f), (new(-300f, -60f), 3f),
    };

    // ------------------------------------------------------------------ geometry
    public static float SegDist(Vector2 p, Vector2 a, Vector2 b)
    {
        var ab = b - a;
        var t = Mathf.Clamp((p - a).Dot(ab) / Mathf.Max(ab.LengthSquared(), 1e-6f), 0f, 1f);
        return (p - (a + ab * t)).Length();
    }

    public static float PolyDist(Vector2 p, Vector2[] line, bool closed = false)
    {
        var d = float.MaxValue;
        var n = closed ? line.Length : line.Length - 1;
        for (var i = 0; i < n; i++) d = Mathf.Min(d, SegDist(p, line[i], line[(i + 1) % line.Length]));
        return d;
    }

    public static bool InPoly(Vector2 p, Vector2[] poly)
    {
        var inside = false;
        for (int i = 0, j = poly.Length - 1; i < poly.Length; j = i++)
            if ((poly[i].Y > p.Y) != (poly[j].Y > p.Y)
                && p.X < (poly[j].X - poly[i].X) * (p.Y - poly[i].Y) / (poly[j].Y - poly[i].Y) + poly[i].X)
                inside = !inside;
        return inside;
    }

    /// <summary>The canal's centreline y at x (it runs west to east).</summary>
    public static float CanalY(float x)
    {
        if (x <= Canal[0].X) return Canal[0].Y;
        for (var i = 0; i + 1 < Canal.Length; i++)
            if (x <= Canal[i + 1].X)
                return Mathf.Lerp(Canal[i].Y, Canal[i + 1].Y, (x - Canal[i].X) / (Canal[i + 1].X - Canal[i].X));
        return Canal[^1].Y;
    }

    private static bool InStrip(Vector2 p) => Strip.HasPoint(p);

    public static Quarter QuarterAt(Vector2 p)
    {
        if (InStrip(p)) return Quarter.Strip;
        if ((p - Isle).Length() < IsleR) return Quarter.Isle;
        if (!InPoly(p, Encl)) return InPoly(p, FarmPoly) ? Quarter.Farms : Quarter.Outside;
        if (p.Y > CanalY(p.X))
        {
            if (InPoly(p, CitadelPoly)) return Quarter.Citadel;
            if (InPoly(p, NoblePoly)) return Quarter.Noble;
            if (InPoly(p, MarketPoly)) return Quarter.Market;
            if (InPoly(p, OldCityPoly)) return Quarter.OldCity;
            return p.X < -2f ? Quarter.WestRes : p.X > 44f ? Quarter.Craftsmen : Quarter.OldCity;
        }
        return p.X < -13f ? Quarter.Riverside : Quarter.LowerCity;
    }

    /// <summary>Water at p: its surface level and bed. The canal and the
    /// sea (harbour, estuary) at <see cref="Sea"/>, the streams at theirs.</summary>
    public static bool WaterAt(Vector2 p, out float level, out float bed)
    {
        level = Sea;
        bed = Sea - 1.2f;
        if (InStrip(p) || (p - Isle).Length() < IsleR) return false;
        if (PolyDist(p, Canal) < CanalHw) return true;
        if (InPoly(p, SeaPoly)) { bed = Sea - 2.5f; return true; }
        foreach (var (line, lv, hw) in Reaches)
            if (PolyDist(p, line) < hw) { level = lv; bed = lv - 1.2f; return true; }
        return false;
    }

    public static bool IsWater(Vector2 p) => WaterAt(p, out _, out _);

    private static float Hills(Vector2 p)
    {
        float s = 0f, w = 0f;
        foreach (var (c, h) in Highland)
        {
            var k = 1f / Mathf.Max((p - c).LengthSquared(), 1f);
            s += h * k;
            w += k;
        }
        return s / w + (Biomes.Fbm(p.X * 0.03f, p.Y * 0.03f, WorldGen.Seed ^ 0xC17EUL) - 0.5f) * 3f;
    }

    /// <summary>The ground over the base. Flat per terrace inside the city;
    /// outside, a 12 m flat band at the wall's level, then the highlands, the
    /// shore, the streams' banks and the fields.</summary>
    public static float Base(Vector2 p)
    {
        if (WaterAt(p, out _, out var bed)) return bed;
        var q = QuarterAt(p);
        if (q != Quarter.Outside && q != Quarter.Farms) return Level(q);
        var farm = q == Quarter.Farms;
        var h = farm ? Farm : Hills(p);
        // the wall's apron: flat at the level inside, blending out
        var best = float.MaxValue;
        var inner = City;
        for (var i = 0; i < Encl.Length; i++)
        {
            if (!EdgeIsWall(i)) continue;
            Vector2 a = Encl[i], b = Encl[(i + 1) % Encl.Length];
            var d = SegDist(p, a, b);
            if (d >= best) continue;
            best = d;
            var ab = b - a;
            var t = Mathf.Clamp((p - a).Dot(ab) / ab.LengthSquared(), 0f, 1f);
            var foot = a + ab * t;
            var q2 = QuarterAt(foot + (foot - p).Normalized() * 5f);
            inner = q2 == Quarter.Outside ? City : Level(q2);
        }
        // the fields run up to the wall's scarp; the hills ease away over 20 m; the
        // ground round the fields eases from the fields' own rule to the hills'
        var fields = Mathf.Lerp(Lower, Farm, Mathf.SmoothStep(4f, 14f, best));   // the fields meet the wall at the Lower City's level
        if (farm) h = fields;
        else
        {
            h = Mathf.Lerp(Mathf.Min(h, inner), h, Mathf.SmoothStep(14f, 34f, best));
            var fd = PolyDist(p, FarmPoly, true);
            if (fd < 24f) h = Mathf.Lerp(fields, h, Mathf.SmoothStep(0f, 24f, fd));
        }
        h = Shore(p, h);
        if (PolyDist(p, Canal) < CanalHw + 6f) h = Mathf.Min(h, City);
        return h;
    }

    /// <summary>Natural ground easing down to the sea and to a stream's banks.</summary>
    private static float Shore(Vector2 p, float h)
    {
        var sd = PolyDist(p, SeaPoly, true);
        if (sd < 22f) h = Mathf.Lerp(Sea + 0.8f, h, Mathf.SmoothStep(0f, 22f, sd));
        foreach (var (line, lv, hw) in Reaches)
        {
            var d = PolyDist(p, line);
            if (d < hw + 9f) h = Mathf.Min(h, Mathf.Lerp(lv + 0.7f, h, Mathf.SmoothStep(hw, hw + 9f, d)));
        }
        return h;
    }

    public static float RelHeight(Vector2 p) => Base(p);

    // ------------------------------------------------------------------ the ground
    private static ulong _baseFor = ulong.MaxValue;
    private static float _base;

    public static float BaseLevel()
    {
        if (System.Threading.Volatile.Read(ref _baseFor) != WorldGen.Seed)
        {
            _base = WorldGen.Raw(Centre.X, Centre.Y);
            System.Threading.Volatile.Write(ref _baseFor, WorldGen.Seed);
        }
        return _base;
    }

    /// <summary>WorldGen's last step: the city's ground inside
    /// <see cref="Influence"/>, the world's past <see cref="Outer"/>.</summary>
    public static float Apply(float x, float z, float h)
    {
        var p = ToPlan(x, z);
        var r = p.Length();
        if (r > Outer) return h;
        var lc = BaseLevel();
        var city = lc + Base(p);
        var nat = Mathf.Max(h, lc + Sea + 0.8f);
        return Mathf.Lerp(city, nat, Mathf.SmoothStep(Influence, Outer, r));
    }

    // ------------------------------------------------------------------ roads
    public sealed class Road
    {
        public string Name = "", Kind = "";
        public Vector2[] P = System.Array.Empty<Vector2>();
        public float Hw;
        public bool Loop;
        /// <summary>Surface level per point: each terrace's level where the
        /// road is on it, embankment ramps (fills) where it leaves one for a
        /// lower one, flat decks over water.</summary>
        public float[] L = System.Array.Empty<float>();
        public bool[] Wet = System.Array.Empty<bool>();
        /// <summary>Point i stands on an embankment (its level over the ground).</summary>
        public bool[] Raised = System.Array.Empty<bool>();
        public float Slope = 0.2f;
    }

    public static readonly List<Road> Roads = new();

    private static Vector2[] V(params float[] xy)
    {
        var v = new Vector2[xy.Length / 2];
        for (var i = 0; i < v.Length; i++) v[i] = new Vector2(xy[2 * i], xy[2 * i + 1]);
        return v;
    }

    /// <summary>The street network, traced from the sheet's key routes and
    /// streets: the four gate roads meet at the market, a branch climbs to
    /// the citadel, a ring road runs round the market quarters, a riverside
    /// route and waterfront streets serve the lower terraces, and district
    /// streets wind through each quarter.</summary>
    internal static (string Name, string Kind, float Hw, bool Loop, float Slope, Vector2[] P)[] Net =
    {
        // Junctions re-laid 2026-09-24 night (check 10, the city walk): the
        // North road's stair down from the Noble terrace is steeper (0.45) so
        // it lands clear of the Ring road, whose north arc moved from y 38 to
        // 30; the Citadel road starts on the Ring road, not on the North
        // road's stair; the South road's stair off the canal bridge is
        // steeper and the Riverside route and Lower street leave it where it
        // has reached the Lower City's level -- they started 5-6 m under it.
        ("North road", "main", 5.0f, false, 0.45f, V(-8, 170, -6, 140, -5, 120, -4, 100, -3, 80, -2, 64, -1, 50, 0, 36, 0, 16)),
        ("South road", "main", 5.0f, false, 0.5f, V(0, -16, -2, -30, -4, -44, -4, -58, -5, -72, -5, -90, -5, -110, -5, -130, -5, -148)),
        ("West road", "main", 5.0f, false, 0.2f, V(-16, 0, -45, 3, -80, 6, -120, 8, -160, 9, -190, 10, -199, 6, -204, -6, -210, -18, -243, -27, -280, -31, -330, -34)),
        ("East road", "main", 5.0f, false, 0.2f, V(16, -2, 45, -8, 90, -18, 140, -28, 190, -38, 225, -44, 235, -45, 247, -46, 262, -48, 300, -52, 340, -55)),
        ("Citadel road", "main", 4.5f, false, 0.36f, V(12, 30, 30, 40, 50, 46, 70, 50, 80, 55, 88, 66, 96, 82, 100, 94)),
        ("Ring road", "ring", 4.0f, true, 0.2f, V(-120, -14, -80, -20, -40, -24, 0, -26, 40, -32, 80, -36, 112, -34, 135, -20, 140, 6, 125, 20, 90, 24, 60, 30, 25, 30, -5, 30, -40, 34, -80, 42, -110, 38, -133, 24, -142, 0, -132, -12)),
        ("Riverside route", "street", 3.0f, false, 0.6f, V(-5, -78, -15, -77, -26, -69, -40, -62, -80, -61, -120, -63, -165, -62)),
        // it ran on to (160, -99), (185, -92): into the wall's corner tower
        // and out past the wall (city walk, 2026-09-24 night)
        ("Lower street", "street", 3.0f, false, 0.2f, V(-3, -83, 40, -84, 80, -89, 120, -95, 150, -96)),
        ("Waterfront", "street", 3.0f, false, 0.2f, V(-1, -100, 30, -106, 60, -112, 100, -119, 130, -117)),
        // West Residential
        ("Well lane", "street", 3.0f, false, 0.2f, V(-40, -24, -60, -8, -74, 12, -80, 30, -80, 44)),
        ("Garden lane", "street", 3.0f, false, 0.2f, V(-80, 6, -98, 20, -110, 38)),
        ("Wall lane", "street", 3.0f, false, 0.2f, V(-142, 0, -160, 18, -164, 36, -152, 55)),
        ("Hedge lane", "street", 3.0f, false, 0.2f, V(-133, 24, -122, 50, -110, 70, -96, 86)),
        ("Cottage row", "street", 3.0f, false, 0.2f, V(-120, -14, -150, -6, -178, -10)),
        // Noble Quarter
        ("Terrace walk", "street", 3.0f, false, 0.2f, V(-2, 66, -30, 72, -60, 80, -92, 90)),
        ("Chapel walk", "street", 3.0f, false, 0.2f, V(-3, 84, 22, 86, 50, 96)),
        ("Manor lane", "street", 3.0f, false, 0.2f, V(-45, 70, -42, 94, -36, 110)),
        // Old City
        ("Church street", "street", 3.0f, false, 0.2f, V(18, 3, 30, 12, 55, 14, 80, 12, 100, 6, 109, 2)),
        ("Guild street", "street", 3.0f, false, 0.2f, V(125, 24, 152, 36, 168, 42)),
        ("Old lane", "street", 2.6f, false, 0.2f, V(64, 26, 80, 22)),
        // back lanes (2026-09-24 night: "no real back lanes"): narrow alleys
        // through the Old City's blocks between the streets
        ("Tanner alley", "lane", 1.8f, false, 0.2f, V(72, 13, 74, 22, 78, 29)),
        ("Cooper alley", "lane", 1.8f, false, 0.2f, V(104, 5, 110, 16, 118, 23)),
        ("Bell alley", "lane", 1.8f, false, 0.2f, V(136, 29, 140, 40, 148, 50)),
        // Craftsmen
        ("Smithy street", "street", 3.0f, false, 0.2f, V(56, -10, 70, -28, 92, -40)),
        ("Yard street", "street", 3.0f, false, 0.2f, V(112, -34, 150, -44, 188, -58)),
        ("Stable street", "street", 3.0f, false, 0.2f, V(140, 6, 170, -8, 200, -14, 214, -22)),
        ("Mill lane", "street", 3.0f, false, 0.2f, V(100, -22, 108, -2, 114, 12)),
        // Riverside and the Lower City
        ("Quay lane", "street", 3.0f, false, 0.2f, V(-40, -60, -44, -74)),
        ("Net lane", "street", 3.0f, false, 0.2f, V(-100, -62, -102, -76)),
        ("Dyer lane", "street", 3.0f, false, 0.2f, V(-150, -63, -150, -78)),
        ("Dock lane", "street", 3.0f, false, 0.2f, V(40, -83, 44, -108)),
        ("Crane lane", "street", 3.0f, false, 0.2f, V(100, -91, 104, -117)),
        // Citadel
        ("Keep court", "street", 3.0f, false, 0.2f, V(96, 82, 130, 90, 152, 100)),
        ("Garden walk", "street", 3.0f, false, 0.2f, V(96, 82, 76, 96, 72, 112)),
        // Fields
        ("Field track", "track", 1.8f, false, 99f, V(231, -45, 226, -78, 214, -100, 196, -128)),
        ("Barn track", "track", 1.8f, false, 99f, V(160, -114, 189, -106, 193, -113, 205, -114)),
    };

    /// <summary>Stairs up onto the wall walk (plan: "ramps / stairs up onto
    /// the wall walk"): a straight flight along the inner face of four long
    /// wall edges, its foot on the terrace inside and its head at the walk
    /// (the terrace + 9.5 m, CitySite.Structures), 9 m clear of the corner
    /// towers. Plan metres: foot, head, the inward normal, levels.</summary>
    public static readonly List<(Vector2 Foot, Vector2 Head, Vector2 In, float Low, float High)> WallStairs = new();
    public const float StairHalf = 1.0f, StairOff = 2.3f, StairSlope = 0.55f;

    private static void FindWallStairs()
    {
        foreach (var i in new[] { 2, 3, 6, 18 })
        {
            Vector2 a = Encl[i], b = Encl[(i + 1) % Encl.Length];
            var dir = (b - a).Normalized();
            var n = new Vector2(dir.Y, -dir.X);
            if (!InPoly((a + b) / 2f + n * 2f, Encl)) n = -n;
            var low = Level(QuarterAt((a + b) / 2f + n * 8f));
            var run = 9.5f / StairSlope;
            var mid = (a + b) / 2f + n * StairOff;
            WallStairs.Add((mid - dir * run / 2f, mid + dir * run / 2f, n, low, low + 9.5f));
        }
    }

    /// <summary>A small paved square wherever a main or ring road meets
    /// another road, away from the plaza, the gates and the water.</summary>
    public static readonly List<Vector2> Squares = new();

    private static bool Cross(Vector2 a, Vector2 b, Vector2 c, Vector2 d, out Vector2 x)
    {
        x = Vector2.Zero;
        var r = b - a;
        var q = d - c;
        var den = r.X * q.Y - r.Y * q.X;
        if (Mathf.Abs(den) < 1e-6f) return false;
        var t = ((c - a).X * q.Y - (c - a).Y * q.X) / den;
        var u = ((c - a).X * r.Y - (c - a).Y * r.X) / den;
        if (t < 0f || t > 1f || u < 0f || u > 1f) return false;
        x = a + r * t;
        return true;
    }

    private static void FindSquares()
    {
        var found = new List<Vector2>();
        for (var i = 0; i < Net.Length; i++)
        for (var j = 0; j < Net.Length; j++)
        {
            if (i == j) continue;
            var (_, ki, _, li, _, pi) = Net[i];
            var (_, kj, hwj, _, _, pj) = Net[j];
            if (ki is not ("main" or "ring") && kj is not ("main" or "ring")) continue;
            if (ki == "track" || kj == "track") continue;
            // i's ends touching j (a T), and i crossing j (a +)
            foreach (var e in new[] { pi[0], pi[^1] })
                if (!li && PolyDist(e, pj, Net[j].Loop) < hwj + 2f) found.Add(e);
            var ni = li ? pi.Length : pi.Length - 1;
            var nj = Net[j].Loop ? pj.Length : pj.Length - 1;
            for (var a = 0; a < ni; a++)
            for (var b = 0; b < nj; b++)
                if (Cross(pi[a], pi[(a + 1) % pi.Length], pj[b], pj[(b + 1) % pj.Length], out var x)) found.Add(x);
        }
        foreach (var x in found)
        {
            if (x.Length() < PlazaR + 14f || !InPoly(x, Encl) || WallDist(x) < 16f) continue;
            if (WaterAt(x, out _, out _) || Squares.Any(s => (s - x).Length() < 22f)) continue;
            Squares.Add(x);
        }
    }

    static CityPlan() => Rebuild();

    /// <summary>Everything derived from the plan's lines: the roads (resampled, profiled,
    /// gaps closed), the squares, the wall stairs, the road grid, the base level. Run at
    /// start-up and again after <see cref="Layout.Apply"/> replaced the lines.</summary>
    public static void Rebuild()
    {
        Roads.Clear();
        Squares.Clear();
        WallStairs.Clear();
        _grid.Clear();
        System.Threading.Volatile.Write(ref _baseFor, ulong.MaxValue);
        foreach (var (name, kind, hw, loop, slope, pts) in Net)
        {
            var rd = new Road { Name = name, Kind = kind, Hw = hw, Loop = loop, P = Resample(pts, loop), Slope = slope };
            Profile(rd);
            Roads.Add(rd);
        }
        CloseGaps();
        FindSquares();
        FindWallStairs();
        for (var i = 0; i < Roads.Count; i++)
        {
            var rd = Roads[i];
            var n = rd.Loop ? rd.P.Length : rd.P.Length - 1;
            for (var s = 0; s < n; s++)
            {
                Vector2 a = rd.P[s], b = rd.P[(s + 1) % rd.P.Length];
                var grow = rd.Hw + 6f;
                for (var gx = Mathf.FloorToInt((Mathf.Min(a.X, b.X) - grow) / Cell); gx <= Mathf.FloorToInt((Mathf.Max(a.X, b.X) + grow) / Cell); gx++)
                for (var gy = Mathf.FloorToInt((Mathf.Min(a.Y, b.Y) - grow) / Cell); gy <= Mathf.FloorToInt((Mathf.Max(a.Y, b.Y) + grow) / Cell); gy++)
                {
                    var k = new Vector2I(gx, gy);
                    if (!_grid.TryGetValue(k, out var l)) _grid[k] = l = new List<(int, int)>();
                    l.Add((i, s));
                }
            }
        }
    }

    /// <summary>A road end that stops 0-4 m short of another road runs on to the
    /// nearest point of that road's centre line (user, 2026-09-29: "some end way
    /// too early"; validate 12 found five, 0.7-3.6 m short). Ends at the plaza,
    /// the wall's gates and the water are left as they are.</summary>
    private static void CloseGaps()
    {
        foreach (var rd in Roads)
        {
            if (rd.Loop || rd.Kind == "track" || rd.P.Length < 2) continue;
            var pts = rd.P.ToList();
            var changed = false;
            foreach (var first in new[] { true, false })
            {
                var e = first ? pts[0] : pts[^1];
                var prev = first ? pts[1] : pts[^2];
                if (e.Length() < PlazaR + 1f || WallDist(e) < 8f || IsWater(e + (e - prev).Normalized() * 2f)) continue;
                var best = float.MaxValue;
                var at = Vector2.Zero;
                var joined = false;
                foreach (var o in Roads)
                {
                    if (o == rd || o.Kind == "track") continue;
                    var segs = o.Loop ? o.P.Length : o.P.Length - 1;
                    for (var i = 0; i < segs; i++)
                    {
                        Vector2 a = o.P[i], b = o.P[(i + 1) % o.P.Length];
                        var d = SegDist(e, a, b);
                        if (d < o.Hw + 0.3f) joined = true;
                        if (d - o.Hw < best)
                        {
                            best = d - o.Hw;
                            var ab = b - a;
                            at = a + ab * Mathf.Clamp((e - a).Dot(ab) / Mathf.Max(ab.LengthSquared(), 1e-6f), 0f, 1f);
                        }
                    }
                }
                if (joined || best > 4f) continue;
                if (first) pts.Insert(0, at); else pts.Add(at);
                changed = true;
            }
            if (!changed) continue;
            rd.P = Resample(pts.ToArray(), false);
            Profile(rd);
        }
    }

    private static Vector2[] Resample(Vector2[] pts, bool loop)
    {
        var o = new List<Vector2>();
        var n = loop ? pts.Length : pts.Length - 1;
        for (var i = 0; i < n; i++)
        {
            Vector2 a = pts[i], b = pts[(i + 1) % pts.Length];
            var k = Mathf.Max(1, Mathf.CeilToInt((b - a).Length() / 2f));
            for (var j = 0; j < k; j++) o.Add(a.Lerp(b, j / (float)k));
        }
        if (!loop) o.Add(pts[^1]);
        return o.ToArray();
    }

    /// <summary>A road's level: its terrace where it is on one; over water a
    /// flat deck at the higher bank; then only RAISED, never cut, until no
    /// step is steeper than the road's slope -- so every ramp is an
    /// embankment on the lower terrace, walled by <see cref="CitySite"/>.</summary>
    private static void Profile(Road rd)
    {
        var n = rd.P.Length;
        var raw = new float[n];
        rd.Wet = new bool[n];
        for (var i = 0; i < n; i++)
        {
            rd.Wet[i] = WaterAt(rd.P[i], out _, out _);
            raw[i] = rd.Wet[i] ? float.NaN : Base(rd.P[i]);
        }
        // decks: each wet run at the higher of its two banks
        for (var i = 0; i < n; i++)
        {
            if (!rd.Wet[i]) continue;
            var j = i;
            while (j < n && rd.Wet[j]) j++;
            var a = i > 0 ? raw[i - 1] : float.NaN;
            var b = j < n ? raw[j] : float.NaN;
            var deck = float.IsNaN(a) ? b : float.IsNaN(b) ? a : Mathf.Max(a, b);
            for (var k = i; k < j; k++) raw[k] = float.IsNaN(deck) ? City : deck;
            i = j;
        }
        var l = (float[])raw.Clone();
        // The slope passes also tilt a wet run -- the road ran down across a
        // flat bridge (the West road's estuary deck fell 2.4 -> -0.6 m) and
        // the bridge's ends stood 0.8-1.5 m off the road (city walk,
        // 2026-09-24 night). So: slope, flatten each wet run at its highest
        // point, slope again (only ever raising), until it holds.
        for (var round = 0; round < 3; round++)
        {
            for (var pass = 0; pass < 3; pass++)
            {
                for (var i = 1; i < n; i++)
                    l[i] = Mathf.Max(l[i], l[i - 1] - rd.Slope * (rd.P[i] - rd.P[i - 1]).Length());
                for (var i = n - 2; i >= 0; i--)
                    l[i] = Mathf.Max(l[i], l[i + 1] - rd.Slope * (rd.P[i] - rd.P[i + 1]).Length());
            }
            for (var i = 0; i < n; i++)
            {
                if (!rd.Wet[i]) continue;
                var j = i;
                var top = float.MinValue;
                while (j < n && rd.Wet[j]) top = Mathf.Max(top, l[j++]);
                for (var k = i; k < j; k++) l[k] = top;
                i = j;
            }
        }
        rd.L = l;
        rd.Raised = new bool[n];
        for (var i = 0; i < n; i++) rd.Raised[i] = !rd.Wet[i] && l[i] - raw[i] > 0.3f;
    }

    private const float Cell = 16f;
    private static readonly Dictionary<Vector2I, List<(int R, int S)>> _grid = new();

    private static Vector2I Key(Vector2 p) => new(Mathf.FloorToInt(p.X / Cell), Mathf.FloorToInt(p.Y / Cell));

    /// <summary>Distance from p to the nearest road's edge (negative on it).
    /// A raised stretch counts its embankment walls as road.</summary>
    public static float RoadClear(Vector2 p)
    {
        if (!_grid.TryGetValue(Key(p), out var list)) return float.MaxValue;
        var best = float.MaxValue;
        foreach (var (ri, si) in list)
        {
            var rd = Roads[ri];
            var s1 = (si + 1) % rd.P.Length;
            var raised = rd.Raised[si] || rd.Raised[s1];
            var d = SegDist(p, rd.P[si], rd.P[s1]) - rd.Hw - (raised ? 1.4f : 0f);
            if (d < best) best = d;
        }
        return best;
    }

    /// <summary>The nearest road's direction from p (for facing), or zero.</summary>
    public static Vector2 NearestRoadDir(Vector2 p, out float dist)
    {
        dist = float.MaxValue;
        var dir = Vector2.Zero;
        if (!_grid.TryGetValue(Key(p), out var list)) return dir;
        foreach (var (ri, si) in list)
        {
            var rd = Roads[ri];
            Vector2 a = rd.P[si], ab = rd.P[(si + 1) % rd.P.Length] - a;
            var t = Mathf.Clamp((p - a).Dot(ab) / Mathf.Max(ab.LengthSquared(), 1e-6f), 0f, 1f);
            var foot = a + ab * t;
            var d = (p - foot).Length() - rd.Hw;
            if (d < dist) { dist = d; dir = (foot - p).Normalized(); }
        }
        return dir;
    }

    // ------------------------------------------------------------------ street view
    /// <summary>The street the camera looks down at world (x, z): the road the
    /// point is deepest inside, when it is inside the wall, past the market
    /// plaza and not on a field track; else -1 (the camera keeps its base yaw).</summary>
    public static int StreetAt(float x, float z)
    {
        var p = ToPlan(x, z);
        if (p.LengthSquared() > Outer * Outer || p.Length() < PlazaR || !InPoly(p, Encl)) return -1;
        if (!_grid.TryGetValue(Key(p), out var list)) return -1;
        var best = -1;
        var bd = 0f;
        foreach (var (ri, si) in list)
        {
            var rd = Roads[ri];
            if (rd.Kind == "track") continue;
            var d = SegDist(p, rd.P[si], rd.P[(si + 1) % rd.P.Length]) - rd.Hw;
            if (d < bd) { bd = d; best = ri; }
        }
        return best;
    }

    /// <summary>Road `road`'s axis nearest world (x, z): its unit tangent and
    /// the centreline point there, both world XZ.</summary>
    public static (Vector2 Dir, Vector2 Foot) StreetAxis(float x, float z, int road)
    {
        var p = ToPlan(x, z);
        var rd = Roads[road];
        var n = rd.Loop ? rd.P.Length : rd.P.Length - 1;
        var bd = float.MaxValue;
        Vector2 dir = Vector2.Right, foot = p;
        for (var s = 0; s < n; s++)
        {
            Vector2 a = rd.P[s], ab = rd.P[(s + 1) % rd.P.Length] - a;
            var t = Mathf.Clamp((p - a).Dot(ab) / Mathf.Max(ab.LengthSquared(), 1e-6f), 0f, 1f);
            var f = a + ab * t;
            var d = (p - f).LengthSquared();
            if (d < bd) { bd = d; foot = f; dir = ab; }
        }
        return (DirToWorld(dir).Normalized(), ToWorld(foot));
    }

    // ------------------------------------------------------------------ terrace edges
    public readonly record struct Edge(Vector2 A, Vector2 B, float Low, float High, Vector2 HighSide, bool Wall);

    /// <summary>Every change of level that no road crosses, as a retaining
    /// block: the terrace edges (Noble, Citadel, Riverside / Lower City), the
    /// canal's banks, the harbour quays, the causeway, and the apron of any
    /// wall stretch that stands over lower ground.</summary>
    public static List<Edge> Edges()
    {
        var lines = new List<Vector2[]>
        {
            V(-114, 92, -80, 62, -40, 50, 0, 50, 38, 49, 62, 54), V(62, 54, 60, 127), V(62, 54, 118, 52, 170, 57),
            V(-15, -50, -14, -78), OffsetLine(Canal, CanalHw), OffsetLine(Canal, -CanalHw),
            V(-168, -84, -120, -80, -60, -76, -13, -78), V(-13, -78, -13, -121), V(4, -121, 60, -127, 117, -134),
            V(-14, -121, -14, -153), V(4, -121, 4, -153), V(-14, -153, 4, -153),
        };
        for (var i = 0; i < Encl.Length; i++)
            if (EdgeIsWall(i)) lines.Add(new[] { Encl[i], Encl[(i + 1) % Encl.Length] });
        var cap = new List<Vector2>();
        for (var k = -6; k <= 6; k++) cap.Add(Canal[^1] + new Vector2(Mathf.Cos(k * 0.26f), Mathf.Sin(k * 0.26f)) * (CanalHw + 0.3f));
        lines.Add(cap.ToArray());
        var isle = new List<Vector2>();
        for (var k = 0; k <= 16; k++) isle.Add(Isle + new Vector2(Mathf.Cos(k * Mathf.Tau / 16f), Mathf.Sin(k * Mathf.Tau / 16f)) * (IsleR - 0.5f));
        lines.Add(isle.ToArray());
        var edges = new List<Edge>();
        foreach (var line in lines)
            for (var i = 0; i + 1 < line.Length; i++)
            {
                Vector2 a = line[i], b = line[i + 1];
                var segs = Mathf.Max(1, Mathf.CeilToInt((b - a).Length() / 3f));
                for (var k = 0; k < segs; k++)
                {
                    Vector2 p0 = a.Lerp(b, k / (float)segs), p1 = a.Lerp(b, (k + 1) / (float)segs), m = (p0 + p1) / 2f;
                    var nrm = new Vector2((p1 - p0).Y, -(p1 - p0).X).Normalized();
                    float s0 = Base(m + nrm * EdgeHalf * 1.1f), s1 = Base(m - nrm * EdgeHalf * 1.1f);
                    if (Mathf.Abs(s0 - s1) < 0.8f || RoadClear(m) < 0.2f) continue;
                    edges.Add(new Edge(p0, p1, Mathf.Min(s0, s1), Mathf.Max(s0, s1), s0 > s1 ? nrm : -nrm, false));
                }
            }
        return edges;
    }

    private static Vector2[] OffsetLine(Vector2[] line, float off)
    {
        var o = new Vector2[line.Length];
        for (var i = 0; i < line.Length; i++)
        {
            var t = (line[Mathf.Min(i + 1, line.Length - 1)] - line[Mathf.Max(i - 1, 0)]).Normalized();
            o[i] = line[i] + new Vector2(-t.Y, t.X) * off;
        }
        return o;
    }

    /// <summary>Is p within a retaining block's reach of a level change?</summary>
    public static bool NearEdge(Vector2 p, float lv)
    {
        const float r = EdgeHalf + 0.6f;
        foreach (var d in new[] { new Vector2(r, 0f), new Vector2(-r, 0f), new Vector2(0f, r), new Vector2(0f, -r),
                                  new Vector2(r, r) * 0.7071f, new Vector2(-r, r) * 0.7071f, new Vector2(r, -r) * 0.7071f, new Vector2(-r, -r) * 0.7071f })
            if (Mathf.Abs(Base(p + d) - lv) > 0.3f) return true;
        return false;
    }

    public static float WallDist(Vector2 p)
    {
        var d = float.MaxValue;
        for (var i = 0; i < Encl.Length; i++)
            if (EdgeIsWall(i)) d = Mathf.Min(d, SegDist(p, Encl[i], Encl[(i + 1) % Encl.Length]));
        return d;
    }

    // ------------------------------------------------------------------ buildings and props
    public readonly record struct Bldg(string Kind, Vector2 P, Vector2 Front, float W, float D, float H, float Level, Quarter Q);
    public readonly record struct Prop(string Kind, Vector2 P, Vector2 Front, float Level);

    private static readonly Dictionary<Quarter, (string Kind, int W)[]> Mix = new()
    {
        // 2026-09-30 (user: "do 1"): each district's own houses from the new kit (newkit.py)
        [Quarter.Market] = new[] { ("shop", 22), ("tavern", 10), ("townhouse_stall", 10), ("merchant_house", 8), ("apothecary", 8), ("townhouse_std", 8), ("townhouse_corner", 6), ("townhouse_arched", 6), ("city_house", 6), ("townhouse_narrow", 5) },
        [Quarter.OldCity] = new[] { ("townhouse_std", 14), ("townhouse_narrow", 10), ("tenement", 14), ("shop", 10), ("tavern", 6), ("townhouse_corner", 5), ("merchant_house", 12), ("alley_house", 14), ("townhouse_arched", 6), ("townhouse_stone", 6), ("city_house", 6), ("apothecary", 4), ("tower_house", 1), ("townhouse_damaged", 2), ("townhouse_ruin", 1) },
        [Quarter.Craftsmen] = new[] { ("blacksmith", 18), ("warehouse", 16), ("stables", 8), ("stable_yard", 6), ("shop", 10), ("tenement", 8), ("townhouse_wooden", 10), ("townhouse_narrow", 5) },
        [Quarter.WestRes] = new[] { ("cottage", 12), ("cottage_tile", 12), ("cottage_l", 8), ("cottage_thatch", 12), ("townhouse_std", 14), ("townhouse_wooden", 10), ("townhouse_stone", 6), ("townhouse_narrow", 8), ("tower_house", 1), ("shop", 4), ("tavern", 2) },
        [Quarter.Noble] = new[] { ("manor_a", 6), ("manor_b", 6), ("mansion", 7), ("city_house", 6), ("townhouse_stone", 6), ("townhouse_corner", 4), ("tower_house", 1) },
        [Quarter.Riverside] = new[] { ("tenement", 22), ("river_house", 16), ("fisher_house", 12), ("dockhouse", 8), ("townhouse_narrow", 10), ("alley_house", 6), ("tavern", 8), ("warehouse", 6), ("townhouse_std", 6), ("shop", 5), ("townhouse_damaged", 3) },
        [Quarter.LowerCity] = new[] { ("warehouse", 26), ("dockhouse", 16), ("tenement", 20), ("fisher_house", 8), ("townhouse_wooden", 8), ("alley_house", 6), ("shop", 10), ("tavern", 8), ("townhouse_narrow", 6), ("stables", 4), ("townhouse_damaged", 3) },
        [Quarter.Farms] = new[] { ("cottage", 6), ("cottage_tile", 4), ("cottage_thatch", 6), ("stables", 2), ("stable_yard", 2), ("granary", 3), ("barn", 4) },
        [Quarter.Citadel] = new[] { ("barracks", 6), ("warehouse", 5), ("stables", 4), ("tenement", 3), ("townhouse_stone", 4), ("city_house", 3), ("townhouse_corner", 3) },
    };

    /// <summary>Gap between neighbours along a street and setback from it.
    /// 2-4 m between houses (user, 2026-09-24: "everything is way too
    /// together" -- it was 0.12-0.32 m, party walls everywhere); party walls
    /// only in the Old City's core; gardens between cottages, open grounds
    /// round the manors, fields round the farms.</summary>
    private static (float Gap, float Spread, float Setback) Spacing(Quarter q) => q switch
    {
        Quarter.OldCity => (0.3f, 1.5f, 0.6f),
        // wider gaps in the market: with the hall and the inn it measured 53 % built (2026-09-30)
        Quarter.Market => (3.2f, 3f, 1.2f),
        Quarter.WestRes => (2.5f, 3f, 1.5f),
        Quarter.Noble => (4f, 4f, 4f),
        Quarter.Citadel => (2.5f, 2f, 2f),
        Quarter.Farms => (8f, 14f, 5f),
        _ => (2f, 2f, 1f),
    };

    private static Vector2 Perp(Vector2 v) => new(v.Y, -v.X);

    /// <summary>The ground sampled once at 1 m for the placer: level, quarter,
    /// water, road and wall clearance, and a mask of every cell within a
    /// retaining block's reach of a level change. Building placement asks it
    /// thousands of times; evaluating the ground each time took 27 s.</summary>
    private sealed class Grid
    {
        public const float X0 = -215f, Y0 = -172f;
        public const int Nx = 470, Ny = 320;
        public readonly float[] Lv = new float[Nx * Ny];
        public readonly byte[] Q = new byte[Nx * Ny];
        public readonly bool[] Wet = new bool[Nx * Ny];
        public readonly float[] Road = new float[Nx * Ny];
        public readonly float[] Wall = new float[Nx * Ny];
        public readonly bool[] Edge = new bool[Nx * Ny];

        public Grid()
        {
            for (var j = 0; j < Ny; j++)
            for (var i = 0; i < Nx; i++)
            {
                var p = new Vector2(X0 + i + 0.5f, Y0 + j + 0.5f);
                var k = j * Nx + i;
                Wet[k] = WaterAt(p, out _, out _);
                var q = QuarterAt(p);
                Q[k] = (byte)q;
                // outside the city nothing is placed: a marker level is enough, and it
                // puts the edge mask along the whole wall (4 m clear of it)
                Lv[k] = q == Quarter.Outside ? -50f : Base(p);
                Road[k] = RoadClear(p);
                Wall[k] = WallDist(p);
            }
            var raw = new bool[Nx * Ny];
            for (var j = 1; j < Ny - 1; j++)
            for (var i = 1; i < Nx - 1; i++)
            {
                var k = j * Nx + i;
                raw[k] = Mathf.Abs(Lv[k] - Lv[k + 1]) > 0.3f || Mathf.Abs(Lv[k] - Lv[k - 1]) > 0.3f
                      || Mathf.Abs(Lv[k] - Lv[k + Nx]) > 0.3f || Mathf.Abs(Lv[k] - Lv[k - Nx]) > 0.3f;
            }
            const int r = 4;
            var h = new bool[Nx * Ny];
            for (var j = 0; j < Ny; j++)
            for (var i = 0; i < Nx; i++)
                for (var d = -r; d <= r && !h[j * Nx + i]; d++)
                    if (i + d >= 0 && i + d < Nx && raw[j * Nx + i + d]) h[j * Nx + i] = true;
            for (var j = 0; j < Ny; j++)
            for (var i = 0; i < Nx; i++)
                for (var d = -r; d <= r && !Edge[j * Nx + i]; d++)
                    if (j + d >= 0 && j + d < Ny && h[(j + d) * Nx + i]) Edge[j * Nx + i] = true;
        }

        public int K(Vector2 p)
        {
            int i = Mathf.FloorToInt(p.X - X0), j = Mathf.FloorToInt(p.Y - Y0);
            return i < 0 || j < 0 || i >= Nx || j >= Ny ? -1 : j * Nx + i;
        }
    }

    /// <summary>Roof overhangs, jetties and signs make a kit footprint wider
    /// than its walls; neighbours share party walls under touching eaves.
    /// Tried +0.25 on 2026-09-29 (the eaves went 0.45 -> 0.60) and reverted: assets
    /// with their own overhangs (cottage thatch, chapel) never grew, so their
    /// footprints came out too small and validate 6 failed (6 on roads). The
    /// real fix is a wall footprint exported by build_city, not an allowance.</summary>
    private const float EaveW = 0.8f, EaveD = 0.6f;

    private sealed class Placer
    {
        public readonly Grid G = new();
        public readonly List<Bldg> Out = new();
        public readonly List<Prop> Props = new();
        public readonly Dictionary<string, int> Why = new() { ["quarter"] = 0, ["water"] = 0, ["level"] = 0, ["road"] = 0, ["wall"] = 0, ["edge"] = 0, ["taken"] = 0 };
        private readonly Dictionary<Vector2I, List<int>> _hash = new();
        private readonly List<(Vector2 C, float R)> _discs = new();
        private readonly IReadOnlyDictionary<string, Vector3> _size;
        public Placer(IReadOnlyDictionary<string, Vector3> size) { _size = size; }
        public bool Has(string k) => _size.ContainsKey(k);
        public Vector3 Size(string k) => _size[k];

        public static Vector2[] Corners(Vector2 c, Vector2 front, float w, float d)
        {
            var u = Perp(front) * (w / 2f);
            var f = front * (d / 2f);
            return new[] { c - u - f, c + u - f, c + u + f, c - u + f };
        }

        private static bool Separated(Vector2[] a, Vector2[] b)
        {
            foreach (var poly in new[] { a, b })
                for (var i = 0; i < 2; i++)
                {
                    var axis = Perp(poly[i + 1] - poly[i]);
                    float amin = float.MaxValue, amax = float.MinValue, bmin = float.MaxValue, bmax = float.MinValue;
                    foreach (var p in a) { var t = p.Dot(axis); amin = Mathf.Min(amin, t); amax = Mathf.Max(amax, t); }
                    foreach (var p in b) { var t = p.Dot(axis); bmin = Mathf.Min(bmin, t); bmax = Mathf.Max(bmax, t); }
                    if (amax < bmin || bmax < amin) return true;
                }
            return false;
        }

        /// <summary>Keep an open disc (the plaza, a garden, a courtyard).</summary>
        public void Reserve(Vector2 c, float r) => _discs.Add((c, r));

        public bool Free(Vector2[] corners, float pad)
        {
            var c = (corners[0] + corners[2]) / 2f;
            foreach (var (dc, dr) in _discs)
                foreach (var p in corners)
                    if ((p - dc).Length() < dr || (c - dc).Length() < dr) return false;
            var k0 = Key(c);
            for (var gx = -2; gx <= 2; gx++)
            for (var gy = -2; gy <= 2; gy++)
                if (_hash.TryGetValue(new Vector2I(k0.X + gx, k0.Y + gy), out var l))
                    foreach (var i in l)
                    {
                        var o = Out[i];
                        if (!Separated(corners, Corners(o.P, o.Front, o.W - EaveW + pad, o.D - EaveD + pad))) return false;
                    }
            return true;
        }

        /// <summary>Place `kind` at c facing `front` if its whole footprint is
        /// in quarter q, dry, on its terrace clear of any level change, clear
        /// of the roads, 2.5 m off the curtain wall, and clear of every
        /// building so far (oriented boxes; `pad` between).</summary>
        public bool Try(string kind, Vector2 c, Vector2 front, Quarter q, float pad = 0.1f, bool force = false)
        {
            if (!_size.TryGetValue(kind, out var s)) return false;
            float w = s.X, d = s.Y;
            var lv = Level(q);
            if (!force)
            {
                var u = Perp(front);
                // sampled 0.5 m inside the core: the grid's 1 m cells would otherwise read a
                // front 0.4 m off the kerb as on the road about half the time
                float cw = w - EaveW - 1f, cd = d - EaveD - 1f;
                // quarters and finer: the same points validation 6 tests, at most 1.5 m apart
                int nu = 4 * Mathf.Max(1, Mathf.CeilToInt(cw / 6f)), nv = 4 * Mathf.Max(1, Mathf.CeilToInt(cd / 6f));
                for (var i = 0; i <= nu; i++)
                for (var j = 0; j <= nv; j++)
                {
                    var p = c + u * ((i / (float)nu - 0.5f) * cw) + front * ((j / (float)nv - 0.5f) * cd);
                    var k = G.K(p);
                    if (k < 0) return false;
                    var qq = (Quarter)G.Q[k];
                    // any quarter on the same terrace: a street wall runs on across a district line
                    if (qq is Quarter.Outside or Quarter.Strip or Quarter.Isle || (qq == Quarter.Farms) != (q == Quarter.Farms)) { Why["quarter"]++; return false; }
                    if (G.Wet[k]) { Why["water"]++; return false; }
                    if (Mathf.Abs(G.Lv[k] - lv) > 0.05f) { Why["level"]++; return false; }
                    if (G.Road[k] < 1.2f && RoadClear(p) < 0.1f) { Why["road"]++; return false; }
                    if (G.Wall[k] < 3.5f && WallDist(p) < 2.5f) { Why["wall"]++; return false; }
                    if (G.Edge[k]) { Why["edge"]++; return false; }
                }
            }
            if (!Free(Corners(c, front, w - EaveW, d - EaveD), pad)) { Why["taken"]++; return false; }
            Out.Add(new Bldg(kind, c, front, w, d, s.Z, lv, q));
            var k0 = Key(c);
            if (!_hash.TryGetValue(k0, out var ll)) _hash[k0] = ll = new List<int>();
            ll.Add(Out.Count - 1);
            return true;
        }

        /// <summary>A landmark near its traced spot: the first clear place
        /// within 14 m, facing `front`.</summary>
        public bool Near(string kind, Vector2 at, Vector2 front, Quarter q)
        {
            for (var r = 0f; r <= 24f; r += 1.5f)
                for (var k = 0; k < (r == 0f ? 1 : 16); k++)
                {
                    var p = at + new Vector2(Mathf.Cos(k * Mathf.Tau / 16f), Mathf.Sin(k * Mathf.Tau / 16f)) * r;
                    if (Try(kind, p, front, q, 1f)) return true;
                }
            return false;
        }

        public void Put(string kind, Vector2 p, Vector2 front, float lv) => Props.Add(new Prop(kind, p, front, lv));
    }

    /// <summary>The kinds the user named per district (2026-09-30: "Old city: merchant
    /// and alley houses; harbour: dockhouse, fisher houses; farm edge: granary, mill,
    /// barns, stable yard; noble: mansions, library, town hall") claim a few deep plots
    /// before the frontage walk: with their street props they are deeper than the rest
    /// and the walk seldom found room (merchant 0, apothecary 0, dockhouse 1-3). Spread
    /// along each street at a 19 m stride; setback as the quarter's own.</summary>
    private static readonly (string Kind, Quarter Q, int N)[] Seeds =
    {
        ("merchant_house", Quarter.OldCity, 4), ("apothecary", Quarter.OldCity, 1), ("dockhouse", Quarter.LowerCity, 3), ("dockhouse", Quarter.Riverside, 2),
        ("river_house", Quarter.Riverside, 3), ("fisher_house", Quarter.Riverside, 2), ("granary", Quarter.Farms, 2),
        ("mansion", Quarter.Noble, 1), ("city_house", Quarter.Noble, 2),
    };

    private static void Seed(Placer pl)
    {
        var got = new List<string>();
        foreach (var (kind, want, n) in Seeds)
        {
            if (!pl.Has(kind)) continue;
            var sz = pl.Size(kind);
            var (_, _, setback) = Spacing(want);
            var placed = 0;
            foreach (var rd in Roads)
            {
                if (placed >= n) break;
                var len = 0f;
                for (var i = 1; i < rd.P.Length && placed < n; i++)
                {
                    len += (rd.P[i] - rd.P[i - 1]).Length();
                    if (len < 19f) continue;
                    len = 0f;
                    var tan = (rd.P[i] - rd.P[i - 1]).Normalized();
                    foreach (var side in new[] { 1f, -1f })
                    {
                        var nn = Perp(tan) * side;
                        if (QuarterAt(rd.P[i] + nn * (rd.Hw + 5f)) != want) continue;
                        var raised = rd.L[i] - Base(rd.P[i]) > 0.3f ? 1.4f : 0f;
                        var c = rd.P[i] + nn * (rd.Hw + raised + setback + (sz.Y - EaveD) / 2f);
                        if (pl.Try(kind, c, -nn, want, 0.02f)) { placed++; break; }
                    }
                }
            }
            // no roadside plot deep enough (the farm edge, the noble grounds): search round
            // the quarter's centre instead
            if (placed < n && Expected.TryGetValue(want, out var ctr))
                foreach (var off in new[] { new Vector2(-10f, 8f), new Vector2(10f, -8f), new Vector2(-12f, -10f), new Vector2(12f, 10f) })
                    if (placed < n && pl.Near(kind, ctr + off, new Vector2(-1f, 0f), want)) placed++;
            got.Add($"{kind}@{want} {placed}/{n}");
        }
        GD.Print("city: seeded " + string.Join(", ", got));
    }

    /// <summary>The stone flights up the terrace walls (user, 2026-09-30: "do the old
    /// city stairs"), planned before any house so their ground is kept: the Old City's
    /// own walls first, then the walls of the quarters at or below street level round
    /// it. Each runs along a straight, level-topped low face, off the roads and water,
    /// 28 m from the next; CitySite builds them. (Planned after the houses, the Old
    /// City's ~12 wall pieces were all taken.)</summary>
    public static readonly List<(Vector2 Foot, Vector2 Head, Vector2 Dir, Vector2 Out, float High)> StairSites = new();

    private static void PlanStairs(Placer pl)
    {
        StairSites.Clear();
        var edges = Edges();
        var from = new[] { Quarter.OldCity, Quarter.Market, Quarter.Craftsmen, Quarter.Riverside, Quarter.LowerCity, Quarter.WestRes };
        Quarter LowQ(Edge e) => QuarterAt((e.A + e.B) / 2f - e.HighSide * (EdgeHalf + 3f));
        int Rank(Edge e) { var i = System.Array.IndexOf(from, LowQ(e)); return i < 0 ? 99 : i; }
        foreach (var e in edges.OrderBy(Rank).ThenBy(e => e.A.X))
        {
            if (StairSites.Count >= 6) break;
            var dh = e.High - e.Low;
            if (dh < 1.2f || dh > 9f || Rank(e) == 99) continue;
            var mid = (e.A + e.B) / 2f;
            if (StairSites.Any(st => ((st.Foot + st.Head) / 2f - mid).Length() < 28f)) continue;
            var outN = -e.HighSide;
            var dir = (e.B - e.A).Normalized();
            var run = dh / StairSlope;
            var off = outN * (EdgeHalf + StairHalf + 0.05f);
            Vector2 foot = mid - dir * (run / 2f) + off, head = mid + dir * (run / 2f) + off;
            var ok = true;
            for (var t = -0.25f; t <= 1.35f && ok; t += 0.08f)
            {
                var p = foot.Lerp(head, t);
                var face = p - off;
                ok = edges.Any(o => SegDist(face, o.A, o.B) < 0.9f && Mathf.Abs(o.High - e.High) < 0.5f && Mathf.Abs(o.Low - e.Low) < 1.0f)
                     && RoadClear(p) > StairHalf + 0.3f && !IsWater(p) && pl.Free(Placer.Corners(p, dir, 0.5f, 0.5f), 0.1f);
            }
            if (!ok) continue;
            StairSites.Add((foot, head, dir, outN, e.High));
            for (var t = -0.3f; t <= 1.3f; t += 0.1f) pl.Reserve(foot.Lerp(head + dir * 1.8f, t), StairHalf + 1.3f);
            // an open apron before the flight, so it rises from a small square and the
            // street sees it (a house stood in front of the first one, 2026-09-30)
            for (var t = 0f; t <= 1f; t += 0.25f) pl.Reserve(foot.Lerp(head, t) + outN * 5f, 3.6f);
        }
    }

    private static string Pick((string Kind, int W)[] mix, System.Random rng)
    {
        var tot = 0;
        foreach (var (_, w) in mix) tot += w;
        var x = rng.Next(tot);
        foreach (var (k, w) in mix)
        {
            if (x < w) return k;
            x -= w;
        }
        return mix[0].Kind;
    }

    /// <summary>Landmarks where the sheet puts them (plan metres).</summary>
    public static readonly (string Kind, Vector2 At, Vector2 Front, Quarter Q)[] Landmarks =
    {
        ("guildhouse", new(-26f, 22f), new(0.76f, -0.65f), Quarter.Market),
        ("church", new(100f, 40f), new(-1f, 0f), Quarter.OldCity),
        ("chapel", new(44f, 30f), new(-1f, 0f), Quarter.OldCity),
        ("chapel", new(22f, 96f), new(-1f, 0f), Quarter.Noble),
        ("keep", new(118f, 108f), new(-0.5f, -0.86f), Quarter.Citadel),
        ("barracks", new(150f, 78f), new(-1f, 0f), Quarter.Citadel),
        ("stables", new(132f, 66f), new(0f, 1f), Quarter.Citadel),
        ("warehouse", new(155f, 108f), new(-1f, 0f), Quarter.Citadel),
        ("watchtower", new(80f, 110f), new(0f, -1f), Quarter.Citadel),
        ("watchtower", new(160f, 64f), new(0f, -1f), Quarter.Citadel),
        ("watchtower", new(150f, 110f), new(0f, -1f), Quarter.Citadel),
        ("windmill", new(178f, -118f), new(-1f, 0f), Quarter.Farms),
        ("barn", new(200f, -103f), new(-1f, 0f), Quarter.Farms),
        ("manor_a", new(-66f, 92f), new(0f, -1f), Quarter.Noble),
        ("manor_b", new(40f, 76f), new(0f, -1f), Quarter.Noble),
        // 2026-09-30, the new kit: the market's hall and inn across the plaza from the
        // guildhouse, the library and town hall in the Noble quarter, the farm edge's
        // granaries, stable yard and the mill by the east river
        ("market_hall", new(26f, 22f), new(-0.76f, -0.65f), Quarter.Market),
        ("inn", new(-26f, -24f), new(0.76f, 0.65f), Quarter.Market),
        ("library", new(-38f, 66f), new(0f, -1f), Quarter.Noble),
        ("town_hall", new(-18f, 100f), new(0f, -1f), Quarter.Noble),
    };
    // (the farm edge is small -- 5 buildings -- and its river runs outside the wall: the
    // granaries come from the Farms mix, the stable yard from the Craftsmen mix, and the
    // mill stands on the canal, see Layout)

    /// <summary>Each house kind's roof (the `cover` it is built with in citykit /
    /// newkit), for the neighbour rule and the far stand-ins' roof colour.</summary>
    public static readonly Dictionary<string, string> Roof = new()
    {
        ["alley_house"] = "slate", ["apothecary"] = "slate_blue", ["barn"] = "shingle", ["barracks"] = "slate", ["blacksmith"] = "shingle",
        ["city_house"] = "slate_blue", ["cottage"] = "thatch", ["cottage_l"] = "shingle", ["cottage_thatch"] = "thatch", ["cottage_tile"] = "clay_tile",
        ["dockhouse"] = "clay_tile", ["fisher_house"] = "thatch", ["granary"] = "shingle", ["guildhouse"] = "slate", ["inn"] = "clay_tile",
        ["library"] = "slate_blue", ["manor_a"] = "slate", ["manor_b"] = "slate", ["mansion"] = "slate", ["market_hall"] = "clay_tile",
        ["merchant_house"] = "clay_tile", ["mill_house"] = "shingle", ["river_house"] = "shingle", ["shop"] = "clay_tile",
        ["stable_yard"] = "shingle", ["stables"] = "thatch", ["tavern"] = "clay_tile", ["tenement"] = "clay_tile", ["tower_house"] = "slate",
        ["town_hall"] = "slate", ["townhouse_arched"] = "clay_tile", ["townhouse_corner"] = "clay_tile", ["townhouse_damaged"] = "slate",
        ["townhouse_narrow"] = "clay_tile", ["townhouse_stall"] = "shingle", ["townhouse_std"] = "slate_blue", ["townhouse_stone"] = "slate_blue",
        ["townhouse_wooden"] = "shingle", ["warehouse"] = "clay_tile",
    };

    public static string RoofOf(string kind) => Roof.TryGetValue(kind, out var r) ? r : "";

    private static readonly HashSet<string> Rare = new() { "tower_house", "inn", "apothecary", "mansion", "townhouse_ruin", "townhouse_damaged" };

    /// <summary>Where each quarter's buildings should centre, read off the
    /// sheet (validation 1).</summary>
    public static readonly Dictionary<Quarter, Vector2> Expected = new()
    {
        [Quarter.Market] = new(0f, 0f), [Quarter.WestRes] = new(-110f, 20f), [Quarter.OldCity] = new(75f, 25f),
        [Quarter.Craftsmen] = new(140f, -20f), [Quarter.Noble] = new(-20f, 85f), [Quarter.Citadel] = new(120f, 90f),
        [Quarter.Riverside] = new(-95f, -65f), [Quarter.LowerCity] = new(70f, -100f), [Quarter.Farms] = new(195f, -110f),
    };

    /// <summary>The city: gates and landmarks, then the frontage walk along
    /// every street (gaps between houses, party walls only in the Old City
    /// core, narrower kinds tried before a gap is left), then the dressing --
    /// the block interiors are yards with trees and gardens, not houses.</summary>
    public static (List<Bldg> B, List<Prop> P) Layout(IReadOnlyDictionary<string, Vector3> size)
    {
        var pl = new Placer(size);
        var rng = new System.Random(1807);
        pl.Reserve(Vector2.Zero, PlazaR);
        foreach (var sq in Squares) pl.Reserve(sq, SquareR);
        pl.Reserve(new Vector2(118f, 84f), 9f);   // the keep's courtyard
        pl.Reserve(new Vector2(0f, 72f), 13f);     // the noble chapel's formal garden
        // the gates and the canal's towers (CitySite places them after the buildings)
        foreach (var g in new[] { Encl[0], Encl[7], Encl[17] }) pl.Reserve(g, 11f);
        pl.Reserve(new Vector2(-4f, -35f), 10.5f);
        foreach (var (foot, head, _, _, _) in WallStairs)
            for (var t = 0f; t <= 1.001f; t += 0.1f) pl.Reserve(foot.Lerp(head, t), 2.4f);
        pl.Reserve(new Vector2(80f, 53.5f), 9.5f);
        PlanStairs(pl);
        for (var x = -150f; x < 180f; x += 48f) pl.Reserve(new Vector2(x, CanalY(x) + CanalHw + 3.5f), 4.2f);
        foreach (var (kind, at, front, q) in Landmarks)
        {
            var before = new Dictionary<string, int>(pl.Why);
            if (!pl.Near(kind, at, front.Normalized(), q))
                GD.Print($"city: landmark {kind} not placed: " + string.Join(", ", pl.Why.Where(kv => kv.Value > before[kv.Key]).Select(kv => $"{kv.Key} {kv.Value - before[kv.Key]}")));
        }
        // the water mill on the canal's north bank, facing east along it, its wheel (the
        // asset's -X side) toward the water (2026-09-30)
        var millAt = new Vector2(126f, CanalY(126f) + CanalHw + 5.5f);
        if (!pl.Near("mill_house", millAt, new Vector2(1f, 0f), QuarterAt(millAt))) GD.Print("city: mill_house not placed");

        Seed(pl);

        foreach (var rd in Roads)
        {
            var len = new float[rd.P.Length];
            for (var i = 1; i < rd.P.Length; i++) len[i] = len[i - 1] + (rd.P[i] - rd.P[i - 1]).Length();
            foreach (var side in new[] { 1f, -1f })
            {
                var s = 1f;
                string? prev = null;   // the last house along this side (the neighbour rule)
                while (s < len[^1] - 1f)
                {
                    var i = 1;
                    while (i < len.Length - 1 && len[i] < s) i++;
                    var at = rd.P[i - 1].Lerp(rd.P[i], (s - len[i - 1]) / Mathf.Max(len[i] - len[i - 1], 1e-3f));
                    var tan = (rd.P[i] - rd.P[i - 1]).Normalized();
                    var n = Perp(tan) * side;
                    var q = QuarterAt(at + n * (rd.Hw + 5f));
                    if (!Mix.TryGetValue(q, out var mix)) { s += 3f; continue; }
                    var (gap, spread, setback) = Spacing(q);
                    var raised = rd.L[i] - Base(rd.P[i]) > 0.3f ? 1.4f : 0f;
                    var placed = false;
                    var first = Pick(mix, rng);
                    // no two neighbours of one kind or one roof (2026-09-30): a few redraws,
                    // then at least a different kind
                    bool Same(string k) => prev != null && (k == prev || RoofOf(k) != "" && RoofOf(k) == RoofOf(prev));
                    for (var tries = 0; tries < 5 && Same(first); tries++) first = Pick(mix, rng);
                    var order = new List<string> { first };
                    // rare and tall kinds only by their own draw: as the narrowest fallback the
                    // tower house took 29 plots (first run, 2026-09-30)
                    order.AddRange(mix.Select(m => m.Kind).Where(k => k != first && k != prev && !Rare.Contains(k) && pl.Has(k))
                        .OrderBy(k => Same(k) ? 1 : 0).ThenBy(k => pl.Size(k).X).Take(3));
                    foreach (var kind in order)
                    {
                        if (!pl.Has(kind)) continue;
                        var sz = pl.Size(kind);
                        // the drawn kind gets two more tries a little further along before a
                        // narrower one stands in: the big new houses (merchant, dock, river)
                        // almost never fit first time (2026-09-30: 0 / 1 / 2 placed)
                        var shift = -1f;
                        foreach (var sh in kind == first ? new[] { 0f, 1.5f, 3f } : new[] { 0f })
                        {
                            var c = at + tan * ((sz.X - EaveW) / 2f + sh) + n * (rd.Hw + raised + setback + (sz.Y - EaveD) / 2f);
                            if (pl.Try(kind, c, -n, q, 0.02f)) { shift = sh; break; }
                        }
                        if (shift < 0f) continue;
                        s += shift + sz.X - EaveW + gap + (float)rng.NextDouble() * spread;
                        placed = true;
                        prev = kind;
                        break;
                    }
                    if (!placed) s += 1f;
                }
            }
        }

        // No back-fill (it packed every block interior with houses facing
        // nowhere): the interiors are yards now, dressed in Dress.
        GD.Print("city: rejections " + string.Join(", ", pl.Why.Select(kv => $"{kv.Key} {kv.Value}")));
        GD.Print("city: kinds " + string.Join(", ", pl.Out.GroupBy(b => b.Kind).OrderByDescending(g => g.Count()).Select(g => $"{g.Key} {g.Count()}")));
        Dress(pl, rng);
        Accents(pl);
        Density(pl);
        Consistency(pl);
        Thin(pl);
        Scenes(pl);
        return (pl.Out, pl.Props);
    }

    /// <summary>Dark side streets (2026-09-30, "city life" plan, item 3): every other street
    /// lamp on the streets and lanes outside the Market, Noble and Citadel goes (18 -> 36 m).
    /// The per-view gate measured the Old City at 7.6 % dark pixels against the sheet's
    /// 9-30. A filter after Dress, so no draw in Dress's stream moves.</summary>
    private static void Thin(Placer pl)
    {
        var drop = new HashSet<int>();
        foreach (var rd in Roads.Where(r => r.Kind is "street" or "lane"))
        {
            var near = new List<(float S, int I)>();
            for (var i = 0; i < pl.Props.Count; i++)
            {
                var p = pl.Props[i];
                // the Old City only ("narrow, tall, aged, mysterious"): thinned in every quarter
                // outside the market, Craftsmen went 17.9 -> 45 % dark pixels, West Residential 48
                if (p.Kind != "street_lamp" || (QuarterAt(p.P) != Quarter.OldCity && rd.Kind != "lane")) continue;
                float best = float.MaxValue, s = 0f, acc = 0f;
                for (var k = 1; k < rd.P.Length; k++)
                {
                    var ab = rd.P[k] - rd.P[k - 1];
                    var len = Mathf.Max(ab.Length(), 1e-3f);
                    var t = Mathf.Clamp((p.P - rd.P[k - 1]).Dot(ab) / (len * len), 0f, 1f);
                    var d = (rd.P[k - 1] + ab * t - p.P).Length();
                    if (d < best) { best = d; s = acc + t * len; }
                    acc += len;
                }
                if (best < rd.Hw + 1.2f) near.Add((s, i));
            }
            var n = 0;
            foreach (var (_, i) in near.OrderBy(x => x.S)) if (n++ % 2 == 1) drop.Add(i);
        }
        for (var i = pl.Props.Count - 1; i >= 0; i--) if (drop.Contains(i)) pl.Props.RemoveAt(i);
        GD.Print($"city: thinned {drop.Count} side-street lamps");
    }

    /// <summary>The four target scenes' foregrounds (2026-09-30, "city life" plan, items
    /// 1-2): the outside reviews and the tour agreed the frames spent 40-50 % on empty
    /// cobble, wall or field. Set pieces in front of the market, Old City, harbour and farm
    /// views, clutter at every front near them, braziers inside the gates. Its own rng,
    /// after Consistency; each piece tests the props already down.</summary>
    /// <summary>The farm view's goat pen (CitySite.Folk puts goats in it).</summary>
    public static readonly Vector2 Pen = new(176.5f, -137f);

    private static void Scenes(Placer pl)
    {
        var rng = new System.Random(3003);
        float U() => (float)rng.NextDouble();
        bool Clear(Vector2 p, float r) => !pl.Props.Any(o => (o.P - p).Length() < r);
        float R(string k, float d) => pl.Has(k) ? Mathf.Max(d, 0.5f * Mathf.Max(pl.Size(k).X, pl.Size(k).Y) + 0.3f) : d;
        var miss = new Dictionary<string, int>();
        bool Ok(Vector2 p, float r, out int g, bool road = true, bool outside = false)
        {
            g = pl.G.K(p);
            string? why = g < 0 ? "grid" : !outside && (Quarter)pl.G.Q[g] is Quarter.Outside ? "outside" : pl.G.Wet[g] ? "wet" : pl.G.Wall[g] < 1.5f ? "wall"
                : pl.G.Edge[g] ? "edge" : road && pl.G.Road[g] < r * 0.5f + 0.3f ? "road"
                : !pl.Free(Placer.Corners(p, Vector2.Up, r, r), 0.1f) ? "taken" : !Clear(p, r * 0.6f + 0.5f) ? "props" : null;
            if (why != null) miss[why] = miss.GetValueOrDefault(why) + 1;
            return why == null;
        }
        var n = new Dictionary<string, int>();
        void Put(string k, Vector2 p, Vector2 f, float lv) { if (!pl.Has(k)) return; pl.Put(k, p, f, lv); n[k] = n.GetValueOrDefault(k) + 1; }
        // in the reserved plaza Ok() always fails (Free tests reserved discs): the market's
        // pieces test props and the roads only, as Consistency's market pieces do
        void Plaza(string k, Vector2 p, Vector2 f)
        {
            var r = R(k, 1f);
            if (Clear(p, r * 0.6f + 0.4f) && RoadClear(p) > r * 0.5f + 0.3f && p.Length() < PlazaR - 1.5f) Put(k, p, f, City);
            else miss["plaza " + k] = miss.GetValueOrDefault("plaza " + k) + 1;
        }

        // the market: two stall clusters either side of the walk up from the South road,
        // in the band the market view sees (y -5..-18); a 7 m walkway stays clear
        foreach (var sx in new[] { 1f, -1f })
        {
            var inward = new Vector2(-sx, 0f);
            Plaza("stall_c", new Vector2(8.6f * sx, -12.2f), inward);
            Plaza("goods_crates", new Vector2(10.9f * sx, -15.6f), inward);
            Plaza("pots", new Vector2(5.4f * sx, -14.6f), inward);
            Plaza("sacks", new Vector2(5.2f * sx, -10.6f), inward);
            Plaza("barrel_stack", new Vector2(11.8f * sx, -9.4f), inward);
            Plaza("flower_bed", new Vector2(7.2f * sx, -17.4f), inward);
            Plaza(sx > 0 ? "table_set" : "stall_c", new Vector2(9.8f * sx, -5.2f), inward);
        }

        // around a view: both front corners of every house within 34 m get their
        // district's clutter, and every third house a small vendor's stall
        void Fronts(Vector2 at, string[] kinds)
        {
            var k = 0;
            foreach (var b in pl.Out.Where(b => (b.P - at).Length() < 34f).ToArray())
            {
                var u = Perp(b.Front);
                foreach (var s in new[] { -1f, 1f })
                {
                    var kind = kinds[k++ % kinds.Length];
                    var r = R(kind, 1.2f);
                    var c = b.P + u * s * (b.W / 2f + r * 0.5f + 0.2f) + b.Front * (b.D / 2f - r * 0.5f);
                    if (Ok(c, r, out var g)) Put(kind, c, b.Front, pl.G.Lv[g]);
                }
                if (k % 3 == 0)
                {
                    var c = b.P + b.Front * (b.D / 2f + 1.6f) + u * (U() - 0.5f) * b.W * 0.5f;
                    if (Ok(c, R("stall_c", 2f), out var g)) Put("stall_c", c, b.Front, pl.G.Lv[g]);
                }
            }
        }
        // the Old City's facades stand 0.6 m off the road (Spacing), so a front has no room;
        // the verges and gaps along the streets near the view take the clutter instead
        void Verge(Vector2 at, float rad, string[] kinds)
        {
            var k = 0;
            foreach (var rd in Roads.Where(r => r.Kind != "track"))
                for (var i = 1; i < rd.P.Length; i++)
                {
                    var ab = rd.P[i] - rd.P[i - 1];
                    var len = ab.Length();
                    var tan = ab / Mathf.Max(len, 1e-3f);
                    for (var t = 1.6f; t < len; t += 3.2f)
                    {
                        var c = rd.P[i - 1] + tan * t;
                        if ((c - at).Length() > rad || rd.Wet[i]) continue;
                        foreach (var sd in new[] { 1f, -1f })
                        {
                            var kind = kinds[k % kinds.Length];
                            var r = R(kind, 1.1f);
                            var q = c + Perp(tan) * sd * (rd.Hw + r * 0.5f + 0.35f);
                            if (Ok(q, r, out var g)) { Put(kind, q, -Perp(tan) * sd, pl.G.Lv[g]); k++; }
                        }
                    }
                }
        }
        var oldCity = new[] { "pots", "barrel_stack", "log_pile", "planter", "crate_pile", "flower_bed", "sacks", "barrels" };
        Fronts(Views.First(v => v.Name == "Old City").P, oldCity);
        Verge(Views.First(v => v.Name == "Old City").P, 36f, oldCity);
        Verge(Views.First(v => v.Name == "Old City Stairs").P, 20f, oldCity);
        var lower = new[] { "crate_pile", "barrel_stack", "sacks", "fish_barrels", "net_stack" };
        Fronts(Views.First(v => v.Name == "Lower City").P, lower);
        Verge(Views.First(v => v.Name == "Lower City").P, 30f, lower);

        // the harbour: cranes at the lower quay's edge, cargo behind them
        {
            Vector2 a = new(6f, -120f), b = new(115f, -133f);
            var inland = Perp((b - a).Normalized());
            if (inland.Y < 0f) inland = -inland;
            // the seeded harbour houses take most of the quay: search it for room
            var cranes = 0;
            for (var t = 0.05f; t < 0.75f && cranes < 3; t += 0.02f)
                foreach (var off in new[] { 3.4f, 4.6f, 5.8f })
                {
                    var at = a.Lerp(b, t) + inland * off;
                    if (!Ok(at, R("crane", 3f), out var g, road: false)) continue;
                    Put("crane", at, -inland, pl.G.Lv[g]);
                    cranes++;
                    t += 0.12f;
                    break;
                }
            var cargo = new[] { "crate_pile", "barrel_stack", "sacks", "fish_barrels", "rope_coil", "net_stack", "goods_crates" };
            for (var t = 0.1f; t < 0.7f; t += 0.035f)
            {
                var kind = cargo[rng.Next(cargo.Length)];
                var at = a.Lerp(b, t) + inland * (5.5f + U() * 3f);
                if (Ok(at, R(kind, 1.2f), out var g, road: false)) Put(kind, at, -inland, pl.G.Lv[g]);
            }
        }

        // the farm view (184, -134): crop fields either side of the walk, rail fences
        // along them, a goat pen and a hay cart, a scarecrow; the windmill stays behind
        {
            // the view stands 9 m inside the farm's south edge; the open ground is north of it
            // (the map, 2026-09-30: cottages at x 164-173 and 189-196 down to y -126 / -122, the
            // windmill's box to x 182, y -125; the farm's south edge at y ~-140 to -145)
            foreach (var (c, f) in new[] { (new Vector2(187.5f, -127.8f), Vector2.Down), (new Vector2(168f, -132f), Vector2.Down),
                                           (new Vector2(197f, -132f), Vector2.Down) })
            {
                if (!Ok(c, 8.5f, out var g, road: false)) continue;
                Put("crop_field", c, f, pl.G.Lv[g]);
                // a rail fence down the field's west side, three rails of 2.36 m
                for (var k = -1; k <= 1; k++)
                {
                    var fp = c + new Vector2(-4.6f, k * 2.4f);
                    if (Ok(fp, 0.9f, out var gf, road: false)) Put("fence", fp, Vector2.Right, pl.G.Lv[gf]);
                }
            }
            if (Ok(new Vector2(187.5f, -126.5f), 1.2f, out var gs, road: false)) Put("scarecrow", new Vector2(187.5f, -126.5f), Vector2.Down, pl.G.Lv[gs]);
            // the pen: 2 rails a side round a 4.7 m square
            var pen = Pen;
            foreach (var (d, f) in new[] { (new Vector2(0f, 2.4f), Vector2.Down), (new Vector2(0f, -2.4f), Vector2.Up), (new Vector2(2.4f, 0f), Vector2.Left), (new Vector2(-2.4f, 0f), Vector2.Right) })
                foreach (var o in new[] { -1.18f, 1.18f })
                {
                    var fp = pen + d + Perp(f) * o;
                    if (Ok(fp, 0.9f, out var gf, road: false)) Put("fence", fp, f, pl.G.Lv[gf]);
                }
            if (Ok(pen, 1.4f, out var gt, road: false)) Put("trough", pen, Vector2.Down, pl.G.Lv[gt]);
            // two shade trees in the near band (the farm view measured 3.7 % dark pixels, the
            // sheet's farm tile 8.9): the first free spot of a few along it
            var trees = 0;
            foreach (var at in new[] { new Vector2(176f, -140.5f), new Vector2(172f, -139f), new Vector2(196f, -139.5f), new Vector2(200f, -136f), new Vector2(168f, -138f) })
                if (trees < 2 && Ok(at, R("tree_broad", 2f), out var gtr, road: false, outside: true)) { Put("tree_broad", at, Vector2.Up, pl.G.Lv[gtr]); trees++; }
            // the near band the camera sees first: kitchen beds and a fence row by the walk
            foreach (var (k, at, f) in new[] { ("garden_bed", new Vector2(190f, -139.5f), Vector2.Up), ("garden_bed", new Vector2(194.2f, -139.2f), Vector2.Up),
                                              ("flower_bed", new Vector2(181f, -140.5f), Vector2.Up), ("well", new Vector2(187.2f, -141.5f), Vector2.Up),
                                              ("fence", new Vector2(190f, -142.2f), Vector2.Up), ("fence", new Vector2(192.4f, -142f), Vector2.Up), ("fence", new Vector2(194.8f, -141.8f), Vector2.Up) })
                if (Ok(at, R(k, 1f), out var gb, road: false, outside: true)) Put(k, at, f, pl.G.Lv[gb]);
            foreach (var (k, at) in new[] { ("cart", new Vector2(178.5f, -130.5f)), ("hay_stack", new Vector2(175f, -127.8f)), ("sacks", new Vector2(180.4f, -133.6f)),
                                           ("hay_stack", new Vector2(190.5f, -135.8f)), ("drying_rack", new Vector2(193.5f, -137f)) })
                if (Ok(at, R(k, 1.5f), out var g, road: false)) Put(k, at, Vector2.Left, pl.G.Lv[g]);
        }

        // the gates: a brazier either side of the road inside each gate -- the gate views
        // measured 43-52 % dark pixels, murky under the wall
        foreach (var gp in new[] { Encl[0], Encl[7], Encl[17] })
        {
            var inward = (-gp).Normalized();
            foreach (var lat in new[] { 6.4f, -6.4f })
            {
                var at = gp + inward * 12.5f + Perp(inward) * lat;   // the gate reserve is 11 m
                if (Ok(at, R("brazier", 1f), out var g)) Put("brazier", at, -Perp(inward) * Mathf.Sign(lat), pl.G.Lv[g]);
            }
        }

        GD.Print("city: scenes " + string.Join(", ", n.OrderByDescending(kv => kv.Value).Select(kv => $"{kv.Key} {kv.Value}")));
        GD.Print("city: scenes missed " + string.Join(", ", miss.OrderByDescending(kv => kv.Value).Select(kv => $"{kv.Key} {kv.Value}")));
        GD.Print("city: props within 25 m of each view: " + string.Join(", ", Views.Select(v => $"{v.Name} {pl.Props.Count(p => (p.P - v.P).Length() < 25f)}")));
    }

    /// <summary>Part 2 of the city plan (user, 2026-09-30: "make the city consistent
    /// like the reference images, all the streets, buildings and plazas"): every small
    /// square gets a centrepiece and furniture; the market a ring of tree planters,
    /// more stalls, cargo and bunting over its four road mouths; the gaps between
    /// houses the clutter of their district; the main streets tree planters; the
    /// quays cargo, nets and huts; the farms sheds and racks. Its own rng, last.</summary>
    private static void Consistency(Placer pl)
    {
        var rng = new System.Random(2002);
        float U() => (float)rng.NextDouble();
        bool Clear(Vector2 p, float r) => !pl.Props.Any(o => (o.P - p).Length() < r);
        bool Ok(Vector2 p, float r, out int g, bool road = true)
        {
            g = pl.G.K(p);
            if (g < 0 || (Quarter)pl.G.Q[g] is Quarter.Outside || pl.G.Wet[g] || pl.G.Wall[g] < 1.5f || pl.G.Edge[g]) return false;
            // validate 14's clearance; the quays test none, as Dress's quay props (they pass 14)
            if (road && pl.G.Road[g] < r * 0.5f + 0.3f) return false;
            return pl.Free(Placer.Corners(p, Vector2.Up, r, r), 0.1f) && Clear(p, r * 0.6f + 0.5f);
        }
        var n = new Dictionary<string, int>();
        void Put(string k, Vector2 p, Vector2 f, float lv) { pl.Put(k, p, f, lv); n[k] = n.GetValueOrDefault(k) + 1; }
        // a prop's real footprint from the kit manifest (a tree planter's canopy is wider
        // than its pot: at 1.4 m one stood on the East road's kerb, 2026-09-30)
        float R(string k, float d) => pl.Has(k) ? Mathf.Max(d, Mathf.Max(pl.Size(k).X, pl.Size(k).Y)) : d;

        // the small squares: a centrepiece (no collider: they stand where roads meet),
        // then planters, a stall in the busy quarters, cargo -- all off the roads
        var centre = new[] { "fountain_small", "statue_saint", "tree_planter", "monument" };
        var busy = new HashSet<Quarter> { Quarter.Market, Quarter.OldCity, Quarter.Riverside, Quarter.LowerCity, Quarter.Craftsmen };
        for (var i = 0; i < Squares.Count; i++)
        {
            var sq = Squares[i];
            var q = QuarterAt(sq);
            if (Clear(sq, 2.5f)) Put(centre[i % centre.Length], sq, Vector2.Down, Base(sq));
            var want = busy.Contains(q) ? new[] { "stall_c", "tree_planter", "crate_pile", "planter" } : new[] { "tree_planter", "planter", "bench", "tree_planter" };
            var k = 0;
            for (var a = 0; a < 12 && k < want.Length; a++)
            {
                var dir = new Vector2(Mathf.Cos(a * Mathf.Tau / 12f + 0.13f), Mathf.Sin(a * Mathf.Tau / 12f + 0.13f));
                var at = sq + dir * (SquareR - 1.6f);
                var r = want[k] is "stall_c" or "crate_pile" ? 2.4f : 1.4f;
                if (RoadClear(at) < r * 0.5f + 0.3f || !Clear(at, r * 0.6f + 0.5f)) continue;
                Put(want[k++], at, -dir, Base(at));
            }
        }

        // the market: tree planters round the fountain, stalls and cargo between the
        // stall groups, pennants over the four road mouths
        for (var k = 0; k < 8; k++)
        {
            var a = k * Mathf.Pi / 4f;
            var at = new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * 9.6f;
            if (Clear(at, 1.4f)) Put("tree_planter", at, -at.Normalized(), City);
        }
        foreach (var a in new[] { 0.785f, 2.356f, 3.927f })
        {
            var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
            var along = Perp(dir);
            foreach (var (kind, off, rad) in new[] { ("large_stall", 6.2f, 16.5f), ("crate_pile", -6.4f, 17.5f), ("barrel_stack", 0f, 20.6f) })
            {
                var at = dir * rad + along * off;
                if (Clear(at, 2.2f) && RoadClear(at) > 1.6f) Put(kind, at, -dir, City);
            }
        }
        foreach (var rd in Roads.Where(r => r.Kind == "main"))
            foreach (var end in new[] { 0, rd.P.Length - 1 })
            {
                // not over the south mouth: the market view looks in along it, and the string
                // hung across the king (tour 00, 2026-09-30)
                if (rd.P[end].Length() > PlazaR + 2f || rd.Name == "South road") continue;
                // the point on the road 23 m out from the centre, just inside the plaza's rim
                var inner = end == 0 ? 1 : rd.P.Length - 2;
                var dir = (rd.P[inner] - rd.P[end]).Normalized();
                var at = rd.P[end] + dir * (23.5f - rd.P[end].Length());
                Put(rd.Hw <= 3.2f ? "bunting_s" : "bunting_m", at, dir, City);
            }

        // between the houses: each district's own clutter at the front corners, and
        // tree planters along the main streets where the verge is too narrow for a tree
        foreach (var b in pl.Out.ToArray())
        {
            if (U() > 0.4f) continue;
            string? kind = b.Q switch
            {
                Quarter.Market => U() < 0.5f ? "sacks" : "crate_pile",
                Quarter.OldCity => U() < 0.4f ? "planter" : U() < 0.5f ? "barrel_stack" : "crate_pile",
                Quarter.Craftsmen or Quarter.LowerCity => U() < 0.5f ? "crate_pile" : "barrel_stack",
                Quarter.Riverside => U() < 0.4f ? "fishing_nets" : U() < 0.5f ? "barrel_stack" : "crate_pile",
                Quarter.WestRes => U() < 0.5f ? "planter" : "bench",
                Quarter.Noble => U() < 0.6f ? "tree_planter" : "bench",
                Quarter.Farms => U() < 0.5f ? "drying_rack" : "shed",
                _ => null,
            };
            if (kind == null) continue;
            var u = Perp(b.Front);
            var s = U() < 0.5f ? -1f : 1f;
            var r = kind is "crate_pile" or "barrel_stack" or "shed" or "drying_rack" or "fishing_nets" ? 2.2f : 1.4f;
            r = R(kind, r);
            var at = b.P + u * s * (b.W / 2f + r * 0.5f + 0.2f) + b.Front * (b.D / 2f - r * 0.5f);
            if (Ok(at, r, out var g)) Put(kind, at, b.Front, pl.G.Lv[g]);
        }
        foreach (var rd in Roads.Where(r => r.Kind == "main"))
        {
            var acc = 8f;
            var side = -1f;
            for (var i = 1; i < rd.P.Length; i++)
            {
                acc += (rd.P[i] - rd.P[i - 1]).Length();
                if (acc < 16f || rd.Wet[i] || rd.L[i] - Base(rd.P[i]) > 0.3f) continue;
                acc = 0f;
                side = -side;
                var nn = Perp((rd.P[i] - rd.P[i - 1]).Normalized()) * side;
                var at = rd.P[i] + nn * (rd.Hw + 1.3f);
                if (Ok(at, R("tree_planter", 1.4f), out var g)) Put("tree_planter", at, -nn, pl.G.Lv[g]);
            }
        }

        // the quays: cargo, nets, mooring posts, a harbour hut on each
        foreach (var (a, b) in new[] { (new Vector2(-165f, -82f), new Vector2(-16f, -78f)), (new Vector2(6f, -120f), new Vector2(115f, -133f)) })
        {
            var inland = Perp((b - a).Normalized());
            if (inland.Y < 0f) inland = -inland;
            for (var t = 0.09f; t < 1f; t += 0.07f)
            {
                var at = a.Lerp(b, t) + inland * 4.5f;
                var kind = ((int)(t * 100) % 4) switch { 0 => "crate_pile", 1 => "barrel_stack", 2 => "fishing_nets", _ => "mooring_post" };
                if (Ok(at, kind == "mooring_post" ? 0.8f : 2.2f, out var g, road: false)) Put(kind, at, -inland, pl.G.Lv[g]);
            }
            foreach (var t in new[] { 0.3f, 0.75f })
            {
                var at = a.Lerp(b, t) + inland * 9f;
                if (Ok(at, 4.4f, out var g, road: false)) Put("harbour_hut", at, -inland, pl.G.Lv[g]);
            }
        }

        // the farms: sheds and drying racks by the hay, a barrel stack at the barn
        foreach (var p0 in new[] { new Vector2(182f, -108f), new Vector2(210f, -96f), new Vector2(165f, -118f) })
            foreach (var (kind, off) in new[] { ("shed", new Vector2(0f, 5f)), ("drying_rack", new Vector2(-4f, -3f)) })
                if (Ok(p0 + off, kind == "shed" ? 3.2f : 2.6f, out var g)) Put(kind, p0 + off, Vector2.Down, pl.G.Lv[g]);

        // washing strung across the Old City's and the riverside's streets (the target
        // sheet's Old City), 26 m apart and off the bunting's 24 m rhythm, both poles on
        // level free verge
        foreach (var rd in Roads.Where(r => r.Kind == "street" && r.Hw <= 3.2f))
        {
            var acc = 6f;
            for (var i = 1; i < rd.P.Length; i++)
            {
                acc += (rd.P[i] - rd.P[i - 1]).Length();
                if (acc < 26f || rd.Wet[i] || Mathf.Abs(rd.L[i] - Base(rd.P[i])) > 0.3f) continue;
                var c = rd.P[i];
                if (QuarterAt(c) is not (Quarter.OldCity or Quarter.Riverside or Quarter.LowerCity)) continue;
                var tan = (rd.P[i] - rd.P[i - 1]).Normalized();
                Vector2 a = c + Perp(tan) * 3.8f, b = c - Perp(tan) * 3.8f;
                int ga = pl.G.K(a), gb = pl.G.K(b);
                if (ga < 0 || gb < 0 || pl.G.Road[ga] < 0.4f || pl.G.Road[gb] < 0.4f || pl.G.Wet[ga] || pl.G.Wet[gb]
                    || Mathf.Abs(pl.G.Lv[ga] - pl.G.Lv[gb]) > 0.2f || !Clear(a, 1f) || !Clear(b, 1f)
                    || !pl.Free(Placer.Corners(a, Vector2.Up, 0.3f, 0.3f), 0.1f) || !pl.Free(Placer.Corners(b, Vector2.Up, 0.3f, 0.3f), 0.1f)) continue;
                acc = 0f;
                Put("laundry_span", c, tan, pl.G.Lv[ga]);
            }
        }

        // the gate approaches: planters either side of the road just inside each gate, a
        // lamp, a wagon waiting and cargo (the overhaul sheet's "approach to gate")
        foreach (var g in new[] { Encl[0], Encl[7], Encl[17] })
        {
            var inward = (-g).Normalized();
            var side = Perp(inward);
            foreach (var (kind, fwd, lat, r) in new[] { ("tree_planter", 15f, 5.5f, 1.4f), ("tree_planter", 15f, -5.5f, 1.4f),
                         ("street_lamp", 19f, 6f, 0.6f), ("wagon", 22f, -7.5f, 2.4f), ("barrel_stack", 25f, 7.5f, 2.2f), ("crate_pile", 26f, -7f, 2.2f) })
            {
                var at = g + inward * fwd + side * lat;
                if (Ok(at, R(kind, r), out var gi)) Put(kind, at, kind == "wagon" ? inward : -side * Mathf.Sign(lat), pl.G.Lv[gi]);
            }
        }

        GD.Print("city: consistency " + string.Join(", ", n.OrderByDescending(kv => kv.Value).Select(kv => $"{kv.Key} {kv.Value}")));
    }

    /// <summary>The direction sheet's density (user, 2026-09-30: "this dense"):
    /// trees along both sides of the streets, a lantern at more doors, bunting across
    /// the streets of the busy quarters. Its own rng, after Accents, so nothing
    /// earlier moves. Props test only buildings in <see cref="Placer.Free"/>, so
    /// each piece here also keeps clear of the props already down.</summary>
    private static void Density(Placer pl)
    {
        var rng = new System.Random(930);
        float U() => (float)rng.NextDouble();
        bool Clear(Vector2 p, float r) => !pl.Props.Any(o => (o.P - p).Length() < r);
        bool Ground(Vector2 p, out int g)
        {
            g = pl.G.K(p);
            return g >= 0 && (Quarter)pl.G.Q[g] is not Quarter.Outside && !pl.G.Wet[g] && pl.G.Wall[g] >= 1.5f && !pl.G.Edge[g];
        }
        int trees = 0, lanterns = 0, bunting = 0;

        // street trees: both sides, half a step off the lamps, on free verge
        foreach (var rd in Roads)
        {
            if (rd.Kind is "track" or "lane") continue;
            var step = rd.Kind == "main" ? 16f : 19f;
            var acc = step / 2f;
            var side = 1f;
            for (var i = 1; i < rd.P.Length; i++)
            {
                acc += (rd.P[i] - rd.P[i - 1]).Length();
                if (acc < step || rd.Wet[i]) continue;
                acc = 0f;
                side = -side;
                if (rd.L[i] - Base(rd.P[i]) > 0.3f) continue;   // not on the embankments
                var n = Perp((rd.P[i] - rd.P[i - 1]).Normalized()) * side;
                var p = rd.P[i] + n * (rd.Hw + 2.2f);
                if (!Ground(p, out var g) || pl.G.Road[g] < 1.6f || !Clear(p, 2.6f)) continue;
                if (!pl.Free(Placer.Corners(p, Vector2.Up, 1.8f, 1.8f), 0.1f)) continue;
                pl.Put(U() < 0.55f ? "tree_slim" : "tree_broad", p, -n, pl.G.Lv[g]);
                trees++;
            }
        }

        // a lantern by the door of the houses (the shops and taverns have theirs)
        foreach (var b in pl.Out.ToArray())
        {
            if (b.Kind is not ("townhouse_std" or "townhouse_narrow" or "tenement" or "cottage" or "cottage_tile" or "cottage_l" or "manor_a" or "manor_b"
                    or "townhouse_arched" or "townhouse_wooden" or "townhouse_stone" or "cottage_thatch" or "alley_house" or "city_house"
                    or "river_house" or "tower_house" or "mansion")) continue;
            if (U() > 0.5f) continue;
            var u = Perp(b.Front);
            var p = b.P + b.Front * (b.D / 2f + 0.15f) + u * (b.W * 0.3f * (U() < 0.5f ? -1f : 1f));
            if (!Ground(p, out var g) || !Clear(p, 0.9f)) continue;
            pl.Put("wall_lantern", p, b.Front, pl.G.Lv[g]);
            lanterns++;
        }

        // bunting across the streets of the busy quarters, every ~24 m, where both
        // poles stand on level free verge
        foreach (var rd in Roads)
        {
            if (rd.Kind is "track" or "lane") continue;
            var (kind, half) = rd.Hw <= 3.2f ? ("bunting_s", 4.2f) : ("bunting_m", 6.3f);
            var acc = 12f;
            for (var i = 1; i < rd.P.Length; i++)
            {
                acc += (rd.P[i] - rd.P[i - 1]).Length();
                if (acc < 24f || rd.Wet[i]) continue;
                if (Mathf.Abs(rd.L[i] - Base(rd.P[i])) > 0.3f) continue;
                var c = rd.P[i];
                var gc = pl.G.K(c);
                if (gc < 0 || (Quarter)pl.G.Q[gc] is not (Quarter.Market or Quarter.OldCity or Quarter.Craftsmen
                        or Quarter.Riverside or Quarter.LowerCity or Quarter.WestRes)) continue;
                var tan = (rd.P[i] - rd.P[i - 1]).Normalized();
                Vector2 a = c + Perp(tan) * half, b = c - Perp(tan) * half;
                if (!Ground(a, out var ga) || !Ground(b, out var gb)) continue;
                if (pl.G.Road[ga] < 0.4f || pl.G.Road[gb] < 0.4f || Mathf.Abs(pl.G.Lv[ga] - pl.G.Lv[gb]) > 0.2f) continue;
                if (!Clear(a, 1f) || !Clear(b, 1f)) continue;
                if (!pl.Free(Placer.Corners(a, Vector2.Up, 0.3f, 0.3f), 0.1f) || !pl.Free(Placer.Corners(b, Vector2.Up, 0.3f, 0.3f), 0.1f)) continue;
                acc = 0f;
                pl.Put(kind, c, tan, pl.G.Lv[ga]);
                bunting++;
            }
        }
        GD.Print($"city: density: {trees} street trees, {lanterns} door lanterns, {bunting} bunting");
    }

    /// <summary>Colour at the doors (2026-09-29, "it is all grey ... dead"):
    /// planters, pots and flower beds either side of the fronts. Its own rng,
    /// after Dress, so nothing the layout or Dress placed moves; the same
    /// guards as Dress (not on roads, water, walls or edges; free ground only).</summary>
    private static void Accents(Placer pl)
    {
        var rng = new System.Random(29);
        foreach (var b in pl.Out.ToArray())
        {
            var u = Perp(b.Front);
            var front = b.P + b.Front * (b.D / 2f + 0.6f);
            foreach (var s in new[] { -1f, 1f })
            {
                var roll = rng.NextDouble();
                if (roll > 0.6) continue;
                var kind = roll < 0.3 ? "planter" : roll < 0.48 ? "pots" : "flower_bed";
                var p = front + u * s * Mathf.Max(0.8f, b.W / 2f - 0.8f);
                var g = pl.G.K(p);
                if (g < 0) continue;
                var q = (Quarter)pl.G.Q[g];
                // clear of the road by the prop's whole half-size: at 0.3 m a 1.2 m
                // planter stood 0.3 m onto the road and stopped kerb crossings (walk 2026-09-29)
                var r = kind == "flower_bed" ? 1.4f : 0.7f;
                // + 0.35, not + 0.15 (2026-09-30): the road field is sampled on a grid, and after the
                // kit rollout a pot and a planter landed within validate 14's reach of a kerb
                if (q is Quarter.Outside || pl.G.Wet[g] || pl.G.Wall[g] < 1.5f || pl.G.Edge[g] || pl.G.Road[g] < r + 0.35f) continue;
                if (pl.Free(Placer.Corners(p, Vector2.Up, r, r), 0.1f)) pl.Put(kind, p, b.Front, pl.G.Lv[g]);
            }
        }
    }

    /// <summary>The small things: lamps along the streets, lanterns and
    /// signs on the fronts, trade clutter by kind, stalls round the fountain,
    /// gardens behind the cottages, formal gardens in the Noble Quarter, the
    /// citadel's yard, the docks and fields -- each kept off the roads and the
    /// buildings, facing its street.</summary>
    private static void Dress(Placer pl, System.Random rng)
    {
        float U() => (float)rng.NextDouble();
        void Put(string k, Vector2 p, Vector2 f, float r = 0.8f, bool onRoadOk = false)
        {
            var g = pl.G.K(p);
            if (g < 0) return;
            var q = (Quarter)pl.G.Q[g];
            if (q is Quarter.Outside || pl.G.Wet[g] || pl.G.Wall[g] < 1.5f || pl.G.Edge[g]) return;
            // a big prop keeps half its size + 0.3 m off the road, validate 14's own
            // measure (a manor's knight statue stood on a kerb, 2026-09-30)
            if (!onRoadOk && pl.G.Road[g] < (r >= 1f ? r * 0.5f + 0.3f : 0.2f)) return;
            if (pl.Free(Placer.Corners(p, Vector2.Up, r, r), 0.1f)) pl.Put(k, p, f, pl.G.Lv[g]);
        }

        // the market square: fountain, stalls in three groups on the
        // diagonals (a ring of twelve read as a wall), trees on the fourth,
        // lamps and benches, and open paving between
        pl.Put("fountain", Vector2.Zero, Vector2.Down, City);
        foreach (var a in new[] { 0.785f, 2.356f, 3.927f })
        {
            var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
            var along = Perp(dir);
            for (var k = -1; k <= 1; k++)
                pl.Put(k == 0 ? "market_stall_b" : "market_stall_a", dir * 16f + along * (k * 3.4f), -dir, City);
            pl.Put("goods_crates", dir * 19f + along * 2.2f, -dir, City);
            pl.Put("sacks", dir * 19f - along * 2.4f, -dir, City);
        }
        foreach (var off in new[] { -3.5f, 3.5f })
        {
            var dir = new Vector2(Mathf.Cos(5.498f), Mathf.Sin(5.498f));
            pl.Put(off < 0f ? "tree_broad" : "tree_slim", dir * 17f + Perp(dir) * off, -dir, City);
        }
        foreach (var a in new[] { 0.785f, 2.356f, 3.927f, 5.498f })
        {
            var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
            pl.Put("street_lamp", dir * 10f, -dir, City);
            pl.Put("bench", dir * 8f + Perp(dir) * 2.4f, -dir, City);
        }
        // flags on poles round the rim, between the four roads and the stall
        // groups: the market's colours (only the guildhouse had banners)
        for (var k = 0; k < 8; k++)
        {
            var a = Mathf.Pi / 8f + k * Mathf.Pi / 4f;
            var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
            pl.Put("flag", dir * 23.6f, -dir, City);
        }
        pl.Put("notice_board", new Vector2(9f, -21f), Vector2.Up, City);
        pl.Put("planter", new Vector2(-21f, -8f), Vector2.Right, City);
        pl.Put("planter", new Vector2(21f, 8f), Vector2.Left, City);

        // the small squares: a bench or two at the rim, a lamp
        foreach (var sq in Squares)
        {
            var a0 = U() * Mathf.Tau;
            for (var k = 0; k < 3; k++)
            {
                var dir = new Vector2(Mathf.Cos(a0 + k * 2.1f), Mathf.Sin(a0 + k * 2.1f));
                // inside the square's own reserved disc, so placed directly, off the road
                var at = sq + dir * (SquareR - 1.2f);
                if (RoadClear(at) > 0.3f) pl.Put(k == 0 ? "street_lamp" : "bench", at, -dir, Base(at));
            }
        }

        // the yards: block interiors, where the back-fill used to put houses --
        // trees, beds, a hedge, a well or a washing line, and open ground
        for (var y = -150f; y < 135f; y += 7f)
        for (var x = -200f; x < 235f; x += 7f)
        {
            var p = new Vector2(x + U() * 3.5f, y + U() * 3.5f);
            var yg = pl.G.K(p);
            if (yg < 0) continue;
            var q = (Quarter)pl.G.Q[yg];
            if (q is Quarter.Outside or Quarter.Farms or Quarter.Strip or Quarter.Isle || pl.G.Road[yg] < 4f) continue;
            var f = NearestRoadDir(p, out _);
            f = f == Vector2.Zero ? Vector2.Down : -f;
            var roll = U();
            if (q == Quarter.OldCity && roll < 0.4f) continue;   // the tight core stays paved yards
            // more trees than beds (open note 2026-09-24: "49 trees is few")
            if (roll < 0.46f) Put(U() < 0.6f ? "tree_broad" : "tree_slim", p, f, 4.2f);
            else if (roll < 0.55f) Put(U() < 0.5f ? "garden_bed" : "flower_bed", p, f, 2.4f);
            else if (roll < 0.61f) Put("hedge", p, Perp(f), 1.6f);
            else if (roll < 0.645f) Put("well", p, f, 1.8f);
            else if (roll < 0.69f) Put("clothesline", p, Perp(f), 1.6f);
        }

        // along every street: lamps at the kerb, alternate sides
        foreach (var rd in Roads)
        {
            if (rd.Kind == "track") continue;
            var step = rd.Kind == "main" ? 14f : 18f;   // was 20 / 26 (2026-09-30, "this dense")
            var acc = U() * step;
            var side = 1f;
            for (var i = 1; i < rd.P.Length; i++)
            {
                acc += (rd.P[i] - rd.P[i - 1]).Length();
                if (acc < step || rd.Wet[i]) continue;
                acc = 0f;
                side = -side;
                var tan = (rd.P[i] - rd.P[i - 1]).Normalized();
                var n = Perp(tan) * side;
                var p = rd.P[i] + n * (rd.Hw + 0.5f);
                if (rd.L[i] - Base(rd.P[i]) > 0.3f) continue;   // not on the embankments
                Put("street_lamp", p, -n, 0.6f);
            }
        }

        // on and before the fronts
        foreach (var b in pl.Out.ToArray())
        {
            var u = Perp(b.Front);
            var front = b.P + b.Front * (b.D / 2f + 0.45f);
            var roll = U();
            switch (b.Kind)
            {
                case "shop" or "tavern" or "townhouse_stall" or "townhouse_corner":
                    if (roll < 0.6f) Put("wall_lantern", front - b.Front * 0.3f + u * (b.W * 0.3f), b.Front, 0.4f, true);
                    if (roll < 0.35f) Put("awning", front - b.Front * 0.35f - u * (b.W * 0.15f), b.Front, 0.6f, true);
                    Put(roll < 0.5f ? "barrels" : "goods_crates", front + u * (b.W / 2f - 0.6f), b.Front, 0.9f, true);
                    if (b.Kind == "tavern") Put("bench", front + b.Front * 0.3f - u * 1.5f, b.Front, 0.9f, true);
                    break;
                case "warehouse":
                    if (b.Q == Quarter.Craftsmen && roll > 0.6f) Put("grindstone", b.P + u * (b.W / 2f + 1.1f), b.Front, 1.0f);
                    Put(roll < 0.5f ? "sacks" : "goods_crates", front + u * (b.W / 2f - 1f), b.Front, 1.2f, true);
                    Put("barrels", front - u * (b.W / 2f - 1f), b.Front, 0.9f, true);
                    // beside the warehouse, not in the street: a wagon is solid, and in the
                    // roadway it blocked the Lower street (city walk, 2026-09-24 night)
                    if (b.Q == Quarter.LowerCity && roll < 0.3f) Put("wagon", b.P + u * (b.W / 2f + 2.6f), b.Front, 2.4f);
                    break;
                case "blacksmith":
                    Put("log_pile", b.P - b.Front * (b.D / 2f + 1.2f), u, 1.4f);
                    Put("cart", front + u * 2.5f + b.Front * 0.2f, u, 1.8f);
                    // the work spills out of the shed: an anvil and a grindstone by the flank
                    Put("anvil", b.P + u * (b.W / 2f + 1.1f) + b.Front * (b.D / 2f - 1.2f), b.Front, 0.9f);
                    Put("grindstone", b.P - u * (b.W / 2f + 1.1f) + b.Front * (b.D / 2f - 1.4f), u, 1.0f);
                    break;
                case "stables":
                    Put("hay_stack", b.P + u * (b.W / 2f + 2f), b.Front, 1.8f);
                    Put("trough", front + u * 1.5f, b.Front, 1.2f, true);
                    break;
                case "tenement":
                    if (roll < 0.5f) Put("clothesline", b.P - b.Front * (b.D / 2f + 1.6f), u, 1.6f);
                    if (roll > 0.7f) Put("wall_lantern", front - b.Front * 0.3f, b.Front, 0.4f, true);
                    break;
                case "cottage" or "cottage_tile" or "cottage_l":
                    var back = b.P - b.Front * (b.D / 2f + 2.6f);
                    Put(roll < 0.5f ? "garden_bed" : "flower_bed", back, b.Front, 2.4f);
                    if (roll < 0.25f) Put("well", back + u * 4f, b.Front, 1.8f);
                    else if (roll < 0.55f) Put("clothesline", back + u * 3.5f, u, 1.6f);
                    Put("fence", b.P + u * (b.W / 2f + 0.6f), u, 0.8f);
                    break;
                case "manor_a" or "manor_b":
                    for (var k = -1; k <= 1; k += 2)
                    {
                        Put("hedge", front + b.Front * 2f + u * k * (b.W / 2f - 1.5f), b.Front, 1.6f);
                        Put("statue_knight", front + b.Front * 2.5f + u * k * 3.5f, b.Front, 1.4f);
                    }
                    Put("gate_small", front + b.Front * 3.5f, b.Front, 1.6f);
                    // iron railings along the front yard, either side of the gate
                    for (var off = 3.2f; off <= b.W / 2f + 1.5f; off += 3f)
                        foreach (var sg in new[] { -1f, 1f })
                            Put("iron_fence", front + b.Front * 3.5f + u * sg * off, b.Front, 0.9f);
                    Put("flower_bed", b.P - b.Front * (b.D / 2f + 3f), b.Front, 2.4f);
                    break;
            }
            // ivy and moss on the quieter fronts and flanks
            if (b.Q is Quarter.OldCity or Quarter.WestRes or Quarter.Noble or Quarter.Riverside && U() < 0.22f)
                Put("ivy", b.P + u * (b.W / 2f + 0.1f), u, 0.5f);
        }

        // the noble chapel's formal garden: an axis of hedges and beds
        var g = new Vector2(0f, 72f);
        for (var k = -2; k <= 2; k++)
        {
            if (k == 0) continue;
            Put("hedge", g + new Vector2(k * 4.5f, 5f), Vector2.Down, 1.4f);
            Put("hedge", g + new Vector2(k * 4.5f, -5f), Vector2.Down, 1.4f);
            Put("flower_bed", g + new Vector2(k * 4.5f, 0f), Vector2.Down, 1.4f);
        }
        Put("fountain", g + new Vector2(0f, 0f), Vector2.Down, 3f);

        // the citadel's yard and upper gardens
        var yard = new Vector2(118f, 84f);
        Put("training_target", yard + new Vector2(-5f, 2f), Vector2.Down, 2f);
        Put("weapon_rack", yard + new Vector2(5f, 3f), Vector2.Left, 1.4f);
        Put("chest", yard + new Vector2(6f, -2f), Vector2.Left, 0.9f);
        Put("wagon", yard + new Vector2(-3f, -5f), Vector2.Right, 2.4f);
        for (var k = 0; k < 6; k++) Put("hedge", new Vector2(74f + (k % 3) * 5f, 100f + (k / 3) * 5f), Vector2.Down, 1.6f);
        Put("flower_bed", new Vector2(80f, 106f), Vector2.Down, 1.8f);

        // docks: piers are structures; cranes, bollards and fish on the quays
        foreach (var (a, b) in new[] { (new Vector2(-165f, -82f), new Vector2(-16f, -78f)), (new Vector2(6f, -120f), new Vector2(115f, -133f)) })
            for (var t = 0.05f; t < 1f; t += 0.07f)
            {
                var p = a.Lerp(b, t);
                var inland = Perp((b - a).Normalized());
                if (inland.Y < 0f) inland = -inland;
                var q = p + inland * 4.5f;
                var roll = U();
                Put(roll < 0.2f ? "crane" : roll < 0.45f ? "fish_barrels" : roll < 0.65f ? "net_stack" : roll < 0.8f ? "rope_coil" : "bollard",
                    q, -inland, 1.2f, true);
            }

        // the fields: crop patches, fences, hay, a scarecrow, carts
        for (var y = -146f; y < -80f; y += 9f)
        for (var x = 146f; x < 238f; x += 9f)
        {
            var p = new Vector2(x, y);
            var fg = pl.G.K(p);
            if (fg < 0 || (Quarter)pl.G.Q[fg] != Quarter.Farms || pl.G.Edge[fg]) continue;
            if (!pl.Free(Placer.Corners(p, Vector2.Up, 8.4f, 8.4f), 0.2f) || RoadClear(p) < 4.5f) continue;
            // flat under all four corners: at the fields' south edge the ground
            // falls to the shore and a patch hung 0.8-1.8 m in the air (check 9)
            if (Placer.Corners(p, Vector2.Up, 8f, 8f).Any(c => Mathf.Abs(Base(c) - Farm) > 0.25f)) continue;
            pl.Put("crop_field", p, Vector2.Up, Farm);
            if (U() < 0.15f) pl.Put("scarecrow", p + new Vector2(1f, 1f), Vector2.Down, Farm);
        }
        foreach (var p in new[] { new Vector2(182f, -108f), new Vector2(210f, -96f), new Vector2(165f, -118f) })
        {
            Put("hay_stack", p, Vector2.Down, 2f);
            Put("cart", p + new Vector2(4f, 0f), Vector2.Right, 1.8f);
        }
        // field fences: a rail fence down both sides of the field tracks,
        // broken where a gate or a gap would be
        foreach (var rd in Roads.Where(r => r.Kind == "track"))
        {
            var acc = 0f;
            for (var i = 1; i < rd.P.Length; i++)
            {
                acc += (rd.P[i] - rd.P[i - 1]).Length();
                if (acc < 2.4f) continue;
                acc = 0f;
                var tan = (rd.P[i] - rd.P[i - 1]).Normalized();
                foreach (var sg in new[] { -1f, 1f })
                {
                    if (U() < 0.18f) continue;
                    var n = Perp(tan) * sg;
                    Put("fence", rd.P[i] - tan * 1.2f + n * (rd.Hw + 0.9f), n, 0.7f);
                }
            }
        }
    }

    // ------------------------------------------------------------------ travel
    public static (string Name, Vector2 P)[] Views =
    {
        // 2026-09-30 (part 2): the citadel, gate and farm views stood outside or faced the
        // wall; they stand inside the city now, on the road up to what they show
        ("Market Square", new(0f, -8f)), ("Old City", new(55f, 14f)), ("Noble Quarter", new(-2f, 60f)),
        ("Citadel", new(88f, 66f)), ("Craftsmen Quarter", new(108f, -4f)), ("West Residential", new(-77f, 21f)),
        // the harbour view on the river quay, the camera out over the water: boats, piers and
        // nets in front, the river houses behind (the causeway showed none of it; on the lower
        // quay a cargo hull filled the frame); the farm view south of the windmill (2026-09-30)
        ("Riverside", new(-101f, -69f)), ("Lower City", new(42f, -96f)), ("Harbour Docks", new(-97f, -80f)),
        ("West Gate", new(-180f, 9.5f)), ("East Gate", new(212f, -40f)), ("Agricultural Edge", new(184f, -134f)),
        ("North Gate", new(-4f, 104f)),
        // set by CitySite.PlanStairs to 7 m in front of the first Old City flight
        ("Old City Stairs", new(90f, 44f)),
    };
}
