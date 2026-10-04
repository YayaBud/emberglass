using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The Hoarfells test site: 170 m square round the region's centre
/// (-430, 430), built once like <see cref="WaterSite"/> (the world has no
/// per-chunk prop streaming yet -- implementation_plan Phase 4). After the
/// user's snow-region reference: clumped snowy pines framing the old trails
/// (<see cref="WorldGen.Trails"/>), blocky rocks under slabs of snow, a
/// split-rail fence and lamp posts along the trail, a signpost at the fork.
///
/// Snow on everything follows the live depth (<see cref="Snow.Depth"/>):
/// trees through the foliage shader (and they shed it in gusts), the rocks'
/// and the fence's tops through <see cref="PropCode"/> -- a slab of snow on
/// each rock top that thickens with the depth and is gone when it is bare.
/// </summary>
public partial class SnowSite : Node3D
{
    public static readonly Vector2 C = new(-430f, 430f);
    /// <summary>Where to stand for the reference's view: 12 m down the lamp
    /// walk (`--at=` for captures and the lighting sweep).</summary>
    public static Vector2 Vista => WalkAt(12f);
    private const int WalkFrom = 12, WalkTo = 14;
    // the sheet's other scenes: their trails' segment ranges
    private const int PassFrom = 15, PassTo = 16, VillageFrom = 17, VillageTo = 18, RuinsFrom = 19, RuinsTo = 20;
    /// <summary>The castle in the mist, beyond the lamp walk's end.</summary>
    public static readonly Vector2 Castle = new(-495f, 362f);
    /// <summary>Scene grounds the random trees and rocks keep off (centre, radius).</summary>
    private static readonly (Vector2 C, float R)[] Keep =
    {
        (new Vector2(-482f, 466f), 20f), (new Vector2(-452f, 350f), 16f), (Castle, 28f),
    };
    private const float Half = 85f;
    private static readonly Vector3 F = new(-0.7071f, 0f, -0.7071f);
    private static readonly Vector3 R = new(0.7071f, 0f, -0.7071f);

    private readonly System.Random _rng = new(4242);
    private float U() => (float)_rng.NextDouble();
    private static float Region(Vector2 p) => Biomes.WeightOf(Biome.Snow, p, WorldGen.Seed);

    private readonly Dictionary<string, List<Kit.Item>> _kit = new();

    /// <summary>Queue one kit asset at `p` (on the ground), turned `yaw`.</summary>
    private void Put(string asset, Vector2 p, float yaw, float scale)
    {
        if (!_kit.TryGetValue(asset, out var l)) _kit[asset] = l = new List<Kit.Item>();
        l.Add(new Kit.Item(WorldGen.Snap(p), yaw, scale, Region(p)));
        // things to break (Breakables): a crate and a barrel at each cabin's door, a barrel
        // beside each barrel pile, a crate by each cart. No draw from _rng: the layout keeps.
        var f = new Vector2(Mathf.Sin(yaw), Mathf.Cos(yaw));   // the asset's front (+Z)
        var r = new Vector2(f.Y, -f.X);
        if (asset == "Cabin")
        {
            var half = Kit.Box(asset).Size * 0.5f * scale;
            Breakables.Add("Crate", p + f * (half.Z + 0.9f) + r * (half.X * 0.55f), yaw);
            Breakables.Add("Barrel", p + f * (half.Z + 0.8f) - r * (half.X * 0.6f), yaw);
        }
        else if (asset == "Barrels") Breakables.Add("Barrel", p + r * 1.2f + f * 0.3f, yaw);
        else if (asset == "CartCrates") Breakables.Add("Crate", p - r * 1.6f + f * 0.9f, yaw + 0.3f);
    }

    private static Kit.Kind KindOf(string a) =>
        a.StartsWith("Pine") || a == "DeadTree" ? Kit.Kind.Tree
        : a == "Castle" ? Kit.Kind.Landmark
        : a.StartsWith("Rock") || a.StartsWith("Ruin") || a is "CliffModule" or "SnowyLedge" or "IceOverhang" or "Stairs"
            or "StoneWall" or "Cabin" or "Lantern" ? Kit.Kind.Rock
        : Kit.Kind.Prop;

    private static bool Kept(Vector2 p)
    {
        foreach (var (c, r) in Keep)
            if (p.DistanceTo(c) < r) return true;
        return false;
    }

    // the sheet's tree sizes, mixed as a wood grows: more medium and small
    // than large, a few young and sparse ones, the odd dead tree
    private static readonly string[] Trees =
        { "PineLarge", "PineMedium", "PineMedium", "PineSmall", "PineSmall", "PineYoung", "PineSparse", "DeadTree" };

    public void Build(Village village, Snow snow)
    {
        // trees in clumps, off the trails, off the steep crags, and never on
        // the camera's side of a trail (a tree there only ever shows as a
        // see-through ghost over the player)
        var trees = 0;
        for (var i = 0; i < 2600 && trees < 480; i++)
        {
            var p = C + new Vector2(U() * 2f - 1f, U() * 2f - 1f) * Half;
            var td = WorldGen.TrailDistance(p.X, p.Y);
            if (Region(p) < 0.4f || td < 3.2f || WorldGen.Slope(p.X, p.Y) > 0.4f) continue;
            if (td < 12f && CameraSide(p)) continue;
            if (Kept(p)) continue;
            var clump = Biomes.Fbm(p.X * 0.03f, p.Y * 0.03f, WorldGen.Seed ^ 0x5A0FUL);
            if (clump > 0.47f || U() < 0.06f)
            {
                Put(Trees[(int)(U() * Trees.Length)], p, U() * Mathf.Tau, 0.85f + U() * 0.3f);
                trees++;
            }
            else if (U() < 0.25f)
                Put(U() < 0.4f ? "Sapling" : U() < 0.5f ? "SnowShrub" : "FrozenGrass", p, U() * Mathf.Tau, 0.8f + U() * 0.4f);
        }
        WalkPines();

        // rocks: outcrops where the ground is steep, blocks at the bends
        for (var i = 0; i < 500 && _kit.GetValueOrDefault("RockSmall")?.Count + _kit.GetValueOrDefault("RockMedium")?.Count < 70; i++)
        {
            var p = C + new Vector2(U() * 2f - 1f, U() * 2f - 1f) * Half;
            if (Region(p) < 0.4f || WorldGen.TrailDistance(p.X, p.Y) < 3f || Kept(p)) continue;
            var slope = WorldGen.Slope(p.X, p.Y);
            if (slope < 0.12f && U() < 0.6f) continue;
            Put(slope > 0.25f ? "RockLarge" : U() < 0.5f ? "RockMedium" : "RockSmall", p, U() * Mathf.Tau, 0.8f + U() * 0.5f);
        }
        foreach (var s in new[] { 2, 3, 4 })
        {
            var seg = WorldGen.Trails[s];
            var at = new Vector2(seg.X, seg.Y);
            var dir = (new Vector2(seg.Z, seg.W) - at).Normalized();
            Put("CliffModule", at + new Vector2(-dir.Y, dir.X) * 6f, Kit.Facing(-new Vector2(-dir.Y, dir.X)), 1f);
        }

        // lanterns (real lights) and drifts from the builder; fences and a
        // signpost on the old trails from the kit
        var b = new Builder();
        var lamps = 0;
        FenceRun(2, -1f, 2.6f);
        FenceRun(3, -1f, 2.6f);
        foreach (var (s, t, side) in new[] { (2, 0.3f, 1f), (3, 0.9f, 1f), (4, 0.5f, -1f), (8, 0.2f, 1f) })
        {
            var seg = WorldGen.Trails[s];
            var a = new Vector2(seg.X, seg.Y);
            var ab = new Vector2(seg.Z, seg.W) - a;
            var at = a + ab * t + new Vector2(-ab.Y, ab.X).Normalized() * side * 2.4f;
            Lantern(at, -new Vector2(-ab.Y, ab.X).Normalized() * side);
            lamps++;
        }
        var drifts = 0;
        for (var i = 0; i < 900 && drifts < 140; i++)
        {
            var p = C + new Vector2(U() * 2f - 1f, U() * 2f - 1f) * Half;
            var w = Region(p);
            var td = WorldGen.TrailDistance(p.X, p.Y);
            if (w < 0.4f || td < 1.6f || WorldGen.Slope(p.X, p.Y) > 0.3f) continue;
            if (td > 9f && U() < 0.55f) continue;   // most by the trail, where they frame it
            Drift(b, p, 0.9f + U() * 2.2f, 0.25f + U() * 0.6f, w * (0.55f + U() * 0.45f));
            drifts++;
        }
        lamps += LampWalk(b);
        lamps += Pass(b) + Village(b) + Ruins(b);
        CliffEdge();
        var fork = WorldGen.Trails[3];
        Put("Signpost", new Vector2(fork.Z, fork.W) + new Vector2(2.2f, 2.0f), U() * Mathf.Tau, 1f);

        var placed = 0;
        foreach (var (asset, list) in _kit) placed += Kit.Place(this, asset, list, KindOf(asset), snow);
        AddChild(new MeshInstance3D
        {
            Name = "Props", Mesh = b.Mesh(),
            MaterialOverride = new ShaderMaterial { Shader = new Shader { Code = PropCode } },
        });
        GD.Print($"snowsite: {placed} kit pieces ({_kit.Count} kinds), {trees} trees, {drifts} drifts, {lamps} lamps");
    }

    /// <summary>Kit fence segments (2.3 m) down one side of a trail segment.</summary>
    private void FenceRun(int seg, float side, float off)
    {
        var s = WorldGen.Trails[seg];
        var a = new Vector2(s.X, s.Y);
        var ab = new Vector2(s.Z, s.W) - a;
        var len = ab.Length();
        var dir = ab / len;
        var nrm = new Vector2(-dir.Y, dir.X) * side * off;
        for (var d = 2.6f; d < len - 1.4f; d += 2.25f)
        {
            var p = a + dir * d + nrm;
            // a gap where another trail crosses: the old main trail's fence
            // ran straight across the lamp walk (tour, 2026-09-23)
            if (OtherTrail(p, seg) < 3.5f) continue;
            Put("Fence", p, Kit.Along(dir), 1f);
        }
    }

    /// <summary>Distance from `p` to the nearest trail segment other than `seg`.</summary>
    private static float OtherTrail(Vector2 p, int seg)
    {
        var best = float.MaxValue;
        for (var i = 0; i < WorldGen.Trails.Length; i++)
        {
            if (i == seg) continue;
            var s = WorldGen.Trails[i];
            var a = new Vector2(s.X, s.Y);
            var ab = new Vector2(s.Z, s.W) - a;
            var q = a + ab * Mathf.Clamp((p - a).Dot(ab) / ab.LengthSquared(), 0f, 1f);
            best = Mathf.Min(best, (p - q).Length());
        }
        return best;
    }

    /// <summary>Is `p` on the camera's side of its nearest trail? The locked
    /// camera looks along F, so it sits toward -F of whatever it frames.</summary>
    internal static bool CameraSide(Vector2 p)
    {
        var best = float.MaxValue;
        var near = p;
        foreach (var s in WorldGen.Trails)
        {
            var a = new Vector2(s.X, s.Y);
            var ab = new Vector2(s.Z, s.W) - a;
            var q = a + ab * Mathf.Clamp((p - a).Dot(ab) / ab.LengthSquared(), 0f, 1f);
            var d = (p - q).LengthSquared();
            if (d < best) { best = d; near = q; }
        }
        return (p - near).Dot(new Vector2(-F.X, -F.Z)) > 0f;
    }

    /// <summary>A point `d` metres down the lamp walk.</summary>
    private static Vector2 WalkAt(float d) => PathAt(WalkFrom, WalkTo, d);

    /// <summary>A point `d` metres along trail segments from..to (clamped).</summary>
    public static Vector2 PathAt(int from, int to, float d)
    {
        for (var s = from; s <= to; s++)
        {
            var seg = WorldGen.Trails[s];
            var a = new Vector2(seg.X, seg.Y);
            var ab = new Vector2(seg.Z, seg.W) - a;
            if (d <= ab.Length() || s == to) return a + ab.Normalized() * Mathf.Clamp(d, 0f, ab.Length());
            d -= ab.Length();
        }
        return C;
    }

    /// <summary>The lamp walk dressed as the sheet's forest path: lanterns
    /// alternating sides every 14 m, the kit fence down the left, rock
    /// outcrops and cliff modules set back from it, the props a traveller's
    /// road collects (bench, barrels, cart and crates, a broken cart, log
    /// piles, stumps, a stone wall, a signpost), and frozen grass, shrubs,
    /// berry bushes, saplings and snow piles along both edges. Left/right as
    /// the camera sees it (screen right = R).</summary>
    private int LampWalk(Builder b)
    {
        var r2 = new Vector2(R.X, R.Z);
        var n = 0;
        for (var d = 5f; d < 98f; d += 14f)
        {
            var side = n % 2 == 0 ? -1f : 1f;
            Lantern(WalkAt(d) + r2 * side * 2.3f, -r2 * side);
            n++;
        }
        for (var s = WalkFrom; s <= WalkTo; s++) FenceRun(s, -1f, 3.1f);
        // outcrops, not a line (a straight row read as a column of cubes);
        // the first two frame the view's near corners, as the reference's
        // dark foreground rocks do
        string[] big = { "RockLarge", "CliffModule", "RockMedium" };
        foreach (var (d, side, off) in new[] { (2f, 1f, 6.5f), (0f, -1f, 7.5f), (9f, 1f, 7f), (30f, 1f, 8.5f), (52f, -1f, 9f), (70f, 1f, 7.5f), (88f, -1f, 8f) })
        {
            var at = WalkAt(d) + r2 * side * off;
            var k = 2 + (int)(U() * 2.99f);
            for (var i = 0; i < k; i++)
                Put(big[(int)(U() * big.Length)], at + new Vector2(U() - 0.5f, U() - 0.5f) * 4f, U() * Mathf.Tau, 0.9f + U() * 0.3f);
            Put(U() < 0.5f ? "SnowyLedge" : "IceOverhang", at - r2 * side * 2.2f, Kit.Facing(-r2 * side), 1f);
        }
        // the road's things, facing the path
        foreach (var (d, side, off, asset, along) in new[]
                 {
                     (14f, 1f, 3.3f, "Bench", false), (20f, 1f, 3.6f, "Barrels", false), (24f, -1f, 4.2f, "Stump", false),
                     (33f, -1f, 5.6f, "CartCrates", true), (38f, 1f, 4.4f, "LogPile", true), (46f, -1f, 4.6f, "StoneWall", true),
                     (55f, 1f, 5.5f, "BrokenCart", true), (60f, -1f, 4.0f, "Stump", false), (72f, 1f, 4.2f, "Barrels", false),
                     (80f, -1f, 5.0f, "LogPile", true), (8f, 1f, 2.6f, "Signpost", false), (62f, 1f, 3.4f, "Stairs", false),
                 })
        {
            var p = WalkAt(d) + r2 * side * off;
            var dir = (WalkAt(d + 1f) - WalkAt(d)).Normalized();
            Put(asset, p, along ? Kit.Along(dir) : Kit.Facing(-r2 * side), 1f);
        }
        // the edges: frozen grass, shrubs, berry bushes, saplings, snow piles
        for (var d = 1f; d < 96f; d += 1.3f + U() * 1.5f)
        {
            var side = U() < 0.5f ? -1f : 1f;
            var p = WalkAt(d) + r2 * side * (1.8f + U() * 1.8f);
            var roll = U();
            Put(roll < 0.42f ? "FrozenGrass" : roll < 0.62f ? "SnowShrub" : roll < 0.74f ? "BerriesBush"
                : roll < 0.87f ? "SnowPile" : "Sapling", p, U() * Mathf.Tau, 0.8f + U() * 0.4f);
        }
        return n;
    }

    /// <summary>Pines framing the walk: rows 9-16 m out on both sides, the
    /// big ones at the frame's near edges -- the dark masses the reference
    /// frame is built on.</summary>
    private void WalkPines()
    {
        var r2 = new Vector2(R.X, R.Z);
        for (var d = -6f; d < 100f; d += 4f + U() * 4f)
            foreach (var side in new[] { -1f, 1f })
            {
                if (U() < 0.3f) continue;
                // d < 0: before the walk's start, toward the camera (-F)
                var p = WalkAt(Mathf.Max(d, 0f)) + new Vector2(F.X, F.Z) * Mathf.Min(d, 0f) + r2 * side * (9f + U() * 7f);
                Put(d < 4f ? "PineLarge" : U() < 0.5f ? "PineMedium" : "PineLarge", p, U() * Mathf.Tau, 0.9f + U() * 0.25f);
            }
    }

    /// <summary>A wooden lantern post as the reference's: a square post, an
    /// arm out over the path, a lantern of warm glass hung from it (a real
    /// light), snow on the post top and the lantern's roof.</summary>
    /// (The post is the kit's `Lantern`, so it ghosts like any occluder: the
    /// builder's version stood opaque at the lens and hid the player, tour
    /// 2026-09-23.)
    private void Lantern(Vector2 at, Vector2 toPath)
    {
        var dir = toPath.Normalized();
        Put("Lantern", at, Kit.Facing(dir), 1f);
        var lamp = WorldGen.Snap(at) + Vector3.Up * 2.35f + new Vector3(dir.X, 0f, dir.Y) * 0.78f;
        Bake.Lamp(this, new LampLight { Name = "Lantern", Position = lamp }, auto: false);
    }

    private Vector2 R2 => new(R.X, R.Z);

    /// <summary>A pick of `names`.</summary>
    private string Pick(params string[] names) => names[(int)(U() * names.Length) % names.Length];

    /// <summary>The edges of a scene's trail: frozen grass, shrubs, berry
    /// bushes, saplings, snow piles, and drifts.</summary>
    private void Edges(Builder b, int from, int to, float len)
    {
        for (var d = 1f; d < len; d += 1.4f + U() * 1.6f)
        {
            var side = U() < 0.5f ? -1f : 1f;
            var p = PathAt(from, to, d) + R2 * side * (1.8f + U() * 1.8f);
            var roll = U();
            Put(roll < 0.42f ? "FrozenGrass" : roll < 0.62f ? "SnowShrub" : roll < 0.74f ? "BerriesBush"
                : roll < 0.87f ? "SnowPile" : "Sapling", p, U() * Mathf.Tau, 0.8f + U() * 0.4f);
        }
        for (var d = 2f; d < len; d += 5f + U() * 4f)
        {
            var side = U() < 0.5f ? -1f : 1f;
            var p = PathAt(from, to, d) + R2 * side * (2.6f + U() * 2f);
            Drift(b, p, 0.9f + U() * 1.6f, 0.25f + U() * 0.5f, Region(p) * (0.6f + U() * 0.4f));
        }
    }

    /// <summary>Scene 2, the mountain pass (the sheet's "rocky terrain, snow
    /// drifts, mist"): the trail up from the Crags between walls of cliff
    /// modules, ledges and ice overhangs, lanterns every 20 m, a signpost at
    /// its foot, pines behind the walls.</summary>
    private int Pass(Builder b)
    {
        var len = 60f;
        for (var d = 0f; d < len; d += 3.6f + U() * 1.4f)
            foreach (var side in new[] { -1f, 1f })
            {
                var p = PathAt(PassFrom, PassTo, d) + R2 * side * (5.5f + U() * 2.5f);
                Put(Pick("CliffModule", "CliffModule", "RockLarge", "SnowyLedge", "IceOverhang"), p,
                    Kit.Facing(-R2 * side) + (U() - 0.5f) * 0.5f, 1.0f + U() * 0.35f);
                if (U() < 0.5f)
                    Put(Pick("PineMedium", "PineSmall", "PineLarge"), p + R2 * side * (5f + U() * 4f), U() * Mathf.Tau, 0.9f + U() * 0.2f);
            }
        var n = 0;
        for (var d = 8f; d < len; d += 20f, n++)
        {
            var side = n % 2 == 0 ? -1f : 1f;
            Lantern(PathAt(PassFrom, PassTo, d) + R2 * side * 2.3f, -R2 * side);
        }
        Put("Signpost", PathAt(PassFrom, PassTo, 3f) + R2 * 2.6f, Kit.Facing(-R2), 1f);
        Edges(b, PassFrom, PassTo, len);
        return n;
    }

    /// <summary>Scene 3, the village outskirts ("houses, fences, warm
    /// lights"): two log cabins facing the trail, fenced yards, a woodpile, a
    /// cart, barrels, a bench, a frozen pool, lanterns, pines behind.</summary>
    private int Village(Builder b)
    {
        var len = 60f;
        foreach (var (d, side, off) in new[] { (16f, -1f, 9.5f), (32f, 1f, 10f) })
            Put("Cabin", PathAt(VillageFrom, VillageTo, d) + R2 * side * off, Kit.Facing(-R2 * side), 1f);
        FenceRun(VillageFrom, 1f, 3.2f);
        FenceRun(VillageTo, -1f, 3.2f);
        foreach (var (d, side, off, asset, along) in new[]
                 {
                     (12f, -1f, 5.2f, "LogPile", true), (20f, -1f, 5.0f, "Barrels", false), (26f, 1f, 5.2f, "CartCrates", true),
                     (36f, 1f, 5.0f, "LogPile", true), (40f, -1f, 3.4f, "Bench", false), (44f, 1f, 4.8f, "StoneWall", true),
                     (8f, 1f, 2.6f, "Signpost", false), (22f, 1f, 4.4f, "Stump", false),
                 })
        {
            var p = PathAt(VillageFrom, VillageTo, d) + R2 * side * off;
            var dir = (PathAt(VillageFrom, VillageTo, d + 1f) - PathAt(VillageFrom, VillageTo, d)).Normalized();
            Put(asset, p, along ? Kit.Along(dir) : Kit.Facing(-R2 * side), 1f);
        }
        var n = 0;
        for (var d = 6f; d < len; d += 13f, n++)
        {
            var side = n % 2 == 0 ? 1f : -1f;
            Lantern(PathAt(VillageFrom, VillageTo, d) + R2 * side * 2.3f, -R2 * side);
        }
        for (var d = -4f; d < len; d += 4f + U() * 4f)
            foreach (var side in new[] { -1f, 1f })
                if (U() < 0.6f)
                    Put(Pick("PineLarge", "PineMedium", "PineMedium", "PineSmall"),
                        PathAt(VillageFrom, VillageTo, d) + R2 * side * (17f + U() * 7f), U() * Mathf.Tau, 0.9f + U() * 0.25f);
        Edges(b, VillageFrom, VillageTo, len);
        return n;
    }

    /// <summary>Scene 5, the ruins ("ancient stones, overgrown, snow"): the
    /// trail walks through two arches, broken walls and pillars either side,
    /// lanterns, dead trees and a frozen pool among them.</summary>
    private int Ruins(Builder b)
    {
        var len = 60f;
        foreach (var d in new[] { 16f, 36f })
            Put("RuinArch", PathAt(RuinsFrom, RuinsTo, d), Kit.Along(R2), 1f);
        foreach (var (d, side, off, asset) in new[]
                 {
                     (10f, -1f, 4.2f, "RuinWall"), (24f, 1f, 4.6f, "RuinWall"), (44f, -1f, 5f, "RuinWall"),
                     (8f, 1f, 3.6f, "RuinPillar"), (20f, -1f, 4f, "RuinPillar"), (30f, 1f, 3.8f, "RuinPillar"),
                     (40f, 1f, 4.2f, "RuinPillar"), (50f, -1f, 3.8f, "RuinPillar"), (27f, -1f, 6f, "DeadTree"),
                     (46f, 1f, 7f, "DeadTree"), (14f, 1f, 7f, "RockMedium"), (33f, -1f, 8f, "RockLarge"),
                 })
        {
            var p = PathAt(RuinsFrom, RuinsTo, d) + R2 * side * off;
            var dir = (PathAt(RuinsFrom, RuinsTo, d + 1f) - PathAt(RuinsFrom, RuinsTo, d)).Normalized();
            Put(asset, p, asset == "RuinWall" ? Kit.Along(dir) : U() * Mathf.Tau, 1f);
        }
        var n = 0;
        for (var d = 6f; d < len; d += 18f, n++)
        {
            var side = n % 2 == 0 ? 1f : -1f;
            Lantern(PathAt(RuinsFrom, RuinsTo, d) + R2 * side * 2.3f, -R2 * side);
        }
        for (var d = -4f; d < len; d += 5f + U() * 4f)
            foreach (var side in new[] { -1f, 1f })
                if (U() < 0.5f)
                    Put(Pick("PineMedium", "PineSmall", "PineSparse"),
                        PathAt(RuinsFrom, RuinsTo, d) + R2 * side * (11f + U() * 6f), U() * Mathf.Tau, 0.9f + U() * 0.2f);
        Edges(b, RuinsFrom, RuinsTo, len);
        return n;
    }

    /// <summary>Scene 4, the cliff edge ("snowy cliffs, depth, atmosphere"):
    /// the lamp walk ends at a rim of ledges and cliff modules, and beyond it
    /// the castle stands in the mist.</summary>
    private void CliffEdge()
    {
        var end = WalkAt(200f);
        var fwd = new Vector2(F.X, F.Z);
        for (var k = -5; k <= 5; k++)
        {
            var p = end + fwd * (3.5f + U() * 1.5f) + R2 * k * 2.8f;
            var outer = Mathf.Abs(k) > 2;
            Put(outer ? Pick("CliffModule", "RockLarge") : Pick("SnowyLedge", "RockSmall", "RockMedium"), p,
                Kit.Facing(-fwd) + (U() - 0.5f) * 0.4f, outer ? 1.1f : 0.9f);
        }
        Put("Castle", Castle, Kit.Facing(-fwd), 1f);
    }

    /// <summary>A drift: a low eight-sided mound, off-centre and flat-topped,
    /// all snow. Sinks into the ground as the depth falls (UV.y = metres).</summary>
    private void Drift(Builder b, Vector2 p, float r, float h, float grow)
    {
        var g = WorldGen.Height(p.X, p.Y) - 0.05f;
        var yaw = U() * Mathf.Tau;
        var lean = new Vector2(U() - 0.5f, U() - 0.5f) * r * 0.35f;
        var ring0 = new Vector3[8];
        var ring1 = new Vector3[8];
        for (var k = 0; k < 8; k++)
        {
            var a = yaw + k * Mathf.Tau / 8f;
            var rr = r * (0.8f + U() * 0.35f);
            var d = new Vector2(Mathf.Cos(a), Mathf.Sin(a) * 0.7f);
            var o = p + d * rr;
            ring0[k] = new Vector3(o.X, WorldGen.Height(o.X, o.Y) - 0.08f, o.Y);
            var t = p + lean + d * rr * 0.55f;
            ring1[k] = new Vector3(t.X, g + h * (0.75f + U() * 0.25f), t.Y);
        }
        var top = new Vector3(p.X + lean.X, g + h, p.Y + lean.Y);
        var col = new Color(0.84f, 0.88f, 0.94f, grow);
        var ctr = new Vector3(p.X, g, p.Y);
        for (var k = 0; k < 8; k++)
        {
            var j = (k + 1) % 8;
            b.Face(new[] { ring0[k], ring0[j], ring1[j], ring1[k] }, ctr, col, g);
            b.Face(new[] { ring1[k], ring1[j], top }, ctr, col, g);
        }
    }

    /// <summary>Flat-shaded boxes into one mesh. Colour alpha = snow-country
    /// weight; UV.x = 1 marks a snow slab (UV.y = 1 on its top face), which
    /// <see cref="PropCode"/> thins with the depth.</summary>
    private sealed class Builder
    {
        private readonly List<Vector3> _v = new(), _n = new();
        private readonly List<Color> _c = new();
        private readonly List<Vector2> _uv = new();

        public void Box(Vector3 ctr, Vector3 size, float yaw, Color col, float slab)
        {
            var bs = new Basis(Vector3.Up, yaw);
            Vector3 P(float x, float y, float z) => ctr + bs * new Vector3(x * size.X, y * size.Y, z * size.Z) * 0.5f;
            var c = new Vector3[8];
            for (var i = 0; i < 8; i++) c[i] = P((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1);
            int[][] faces = { new[] { 0, 1, 3, 2 }, new[] { 4, 6, 7, 5 }, new[] { 0, 4, 5, 1 }, new[] { 2, 3, 7, 6 }, new[] { 0, 2, 6, 4 }, new[] { 1, 5, 7, 3 } };
            foreach (var f in faces)
            {
                Vector3 a = c[f[0]], b = c[f[1]], cc = c[f[2]], d = c[f[3]];
                var n = (b - a).Cross(cc - a).Normalized();
                if (n.Dot((a + cc) * 0.5f - ctr) < 0f) { (b, d) = (d, b); n = -n; }
                Tri(a, b, cc, n, col, slab, ctr.Y, 0f);
                Tri(a, cc, d, n, col, slab, ctr.Y, 0f);
            }
        }

        // outward (b-a)x(c-a); Godot's front face winds clockwise: a, c, b
        /// <summary>A convex face of a snow mound, turned outward from
        /// `inside`; every vertex sinks by its height above `ground` when the
        /// snow is gone.</summary>
        public void Face(Vector3[] pts, Vector3 inside, Color col, float ground)
        {
            var n = (pts[1] - pts[0]).Cross(pts[2] - pts[0]).Normalized();
            var c = Vector3.Zero;
            foreach (var q in pts) c += q;
            c /= pts.Length;
            if (n.Dot(c - inside) < 0f) { System.Array.Reverse(pts); n = -n; }
            for (var i = 1; i + 1 < pts.Length; i++) Tri(pts[0], pts[i], pts[i + 1], n, col, 1f, 0f, ground);
        }

        // UV.x = 1: snow. UV.y = metres the vertex drops on bare ground: a
        // slab's whole top (side faces' top corners too, so it thins without
        // tearing) drops 0.2 m; a drift's vertices drop to the ground.
        private void Tri(Vector3 a, Vector3 b, Vector3 c, Vector3 n, Color col, float slab, float midY, float ground)
        {
            foreach (var p in new[] { a, c, b })
            {
                _v.Add(p); _n.Add(n); _c.Add(col);
                var drop = slab <= 0f ? 0f : ground != 0f ? Mathf.Max(0f, p.Y - ground) : p.Y > midY ? 0.2f : 0f;
                _uv.Add(new Vector2(slab, drop));
            }
        }

        public ArrayMesh Mesh()
        {
            var arrays = new Godot.Collections.Array();
            arrays.Resize((int)Godot.Mesh.ArrayType.Max);
            arrays[(int)Godot.Mesh.ArrayType.Vertex] = _v.ToArray();
            arrays[(int)Godot.Mesh.ArrayType.Normal] = _n.ToArray();
            arrays[(int)Godot.Mesh.ArrayType.Color] = _c.ToArray();
            arrays[(int)Godot.Mesh.ArrayType.TexUV] = _uv.ToArray();
            var m = new ArrayMesh();
            m.AddSurfaceFromArrays(Godot.Mesh.PrimitiveType.Triangles, arrays);
            return m;
        }
    }

    /// <summary>Stone and wood, texel-grained, snow on what faces up. A snow
    /// slab (UV.x = 1) lowers its top with the depth -- 0.22 m at full depth
    /// -- and is not drawn at all on bare ground.</summary>
    private const string PropCode = @"
shader_type spatial;
render_mode specular_disabled;
global uniform float snow_depth;
varying vec3 wn;
varying vec3 wp;
varying flat float slab;

float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void vertex() {
    float d = snow_depth * COLOR.a;
    slab = UV.x;
    VERTEX.y -= UV.y * (1.0 - clamp(d * 1.4, 0.0, 1.0));
    wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
    wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    float d = snow_depth * COLOR.a;
    if (slab > 0.5 && d < 0.12) discard;
    vec2 q = floor(vec2(wp.x + wp.z, wp.y) * 26.0);
    vec3 base = COLOR.rgb * (0.88 + 0.24 * h(q));
    vec3 sn = vec3(0.82, 0.86, 0.93) * (0.95 + 0.05 * h(q * 1.7));
    float up = smoothstep(0.55, 0.85, wn.y);
    float cover = slab > 0.5 ? 1.0 : up * smoothstep(0.05, 0.35, d);
    ALBEDO = mix(base, sn, cover);
    ROUGHNESS = 0.9;
}
";
}
