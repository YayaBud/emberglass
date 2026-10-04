using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The Ashdunes test site round <see cref="WorldGen.DesertSiteCentre"/>,
/// built once like <see cref="SnowSite"/>, from the desert kit
/// (`scripts/forge/desertkit/desertkit.py`, loaded by <see cref="Kit"/>):
/// a market street of adobe houses with stalls and awnings (trail segments
/// 21-22), a temple approach lined with ruined columns up to the temple
/// (23-24), and an oasis pool ringed with date palms (25-26); cacti, dry
/// scrub, boulders, sand piles and three mesas over the dunes between. The
/// scenes stand on the dells WorldGen levels for them. Kit items carry no
/// snow.
/// </summary>
public partial class DesertSite : Node3D
{
    private static readonly Vector2 C = WorldGen.DesertSiteCentre;
    private const int MarketFrom = 21, MarketTo = 22, TempleFrom = 23, TempleTo = 24, OasisFrom = 25, OasisTo = 26;
    /// <summary>The temple, at the approach's end on the plaza dell, facing
    /// back down the approach (toward the camera).</summary>
    public static readonly Vector2 Temple = new(326f, 176f);
    private const float Half = 110f;
    // the locked camera's view direction on the ground, and screen right
    private static readonly Vector2 F = new(-0.7071f, -0.7071f);
    private static readonly Vector2 R = new(0.7071f, -0.7071f);

    private readonly System.Random _rng = new(8642);
    private float U() => (float)_rng.NextDouble();
    private string Pick(params string[] names) => names[(int)(U() * names.Length) % names.Length];
    private static float Region(Vector2 p) => Biomes.WeightOf(Biome.Dunes, p, WorldGen.Seed);

    private readonly Dictionary<string, List<Kit.Item>> _kit = new();
    /// <summary>Ground the scatter keeps off (centre, radius).</summary>
    private readonly List<(Vector2 C, float R)> _taken = new();

    private void Put(string asset, Vector2 p, float yaw, float scale = 1f)
    {
        if (!_kit.TryGetValue(asset, out var l)) _kit[asset] = l = new List<Kit.Item>();
        l.Add(new Kit.Item(WorldGen.Snap(p), yaw, scale, 0f));
    }

    private bool Taken(Vector2 p)
    {
        foreach (var (c, r) in _taken)
            if (p.DistanceTo(c) < r) return true;
        return false;
    }

    private static Kit.Kind KindOf(string a) =>
        a.StartsWith("DatePalm") || a == "ColumnCactus" ? Kit.Kind.Tree
        : a.StartsWith("Boulder") || a.StartsWith("Adobe") || a is "Mesa" or "Temple" or "SandstoneLedge" or "SandstoneArch"
            or "RuinedColumn" or "Obelisk" or "Well" or "MarketStall" ? Kit.Kind.Rock
        : Kit.Kind.Prop;

    public void Build()
    {
        Market();
        TempleWay();
        Oasis();
        Scatter();
        var placed = 0;
        foreach (var (asset, list) in _kit) placed += Kit.Place(this, asset, list, KindOf(asset));
        GD.Print($"desertsite: {placed} kit pieces ({_kit.Count} kinds)");
    }

    /// <summary>The market street, as the camera looks down it: adobe houses
    /// both sides fronting it 9.5 m out, a stall or an awning before most at
    /// 4.2 m, jars, crates and rugs between; a square at the bend with the
    /// well; palms behind the roofs; past the square the street runs out
    /// into the dunes past a fallen arch.</summary>
    private void Market()
    {
        Vector2 At(float d) => SnowSite.PathAt(MarketFrom, MarketTo, d);
        var n = 0;
        for (var d = 3f; d < 60f; d += 8.5f + U() * 2f)
        {
            if (d > 36f && d < 48f) continue;   // the square
            foreach (var side in new[] { -1f, 1f })
            {
                if (d > 48f && U() < 0.5f) continue;   // thinning out
                var face = -R * side;   // toward the street
                var p = At(d) + R * side * (9.5f + U() * 0.6f);
                Put(n++ % 3 == 1 ? "AdobeHouseTall" : "AdobeHouse", p, Kit.Facing(face));
                _taken.Add((p, 6f));
                var roll = U();
                var front = At(d + (U() - 0.5f) * 2f) + R * side * 4.2f;
                if (roll < 0.5f) Put("MarketStall", front, Kit.Facing(face));
                else if (roll < 0.75f) Put("Awning", front, Kit.Facing(face));
                Put(Pick("Pots", "Crates", "Urn", "Pots", "Rug"), At(d + 3.2f) + R * side * (5.3f + U() * 0.5f), U() * Mathf.Tau);
                // a jar or pot to break beside each stall, sometimes a crate: chosen by a
                // hash, never from _rng, so nothing else in the layout re-rolls
                var bp = At(d - 2.2f) + R * side * 5.4f;
                Breakables.Add(Biomes.Hash((int)d, (int)side, 91) < 0.55f ? "Jar" : "Pot", bp, d * 1.7f);
                if (Biomes.Hash((int)d, (int)side, 92) < 0.5f) Breakables.Add("Crate", bp + F * 1.1f, d);
            }
        }
        var square = At(42f);
        Put("Well", square - R * 4.5f, U() * Mathf.Tau);
        Put("Crates", square - R * 6.5f + F * 2.5f, U() * Mathf.Tau);
        Put("Pots", square + R * 5f - F * 1.5f, U() * Mathf.Tau);
        Breakables.Add("Barrel", square - R * 6.2f - F * 1.2f, 0.4f);
        Breakables.Add("Pot", square + R * 5.8f + F * 0.9f, 1.1f);
        Breakables.Add("Jar", square + R * 6.6f + F * 0.1f, 2.3f);
        _taken.Add((square, 9f));
        for (var d = -4f; d < 64f; d += 7f + U() * 5f)
            foreach (var side in new[] { -1f, 1f })
                if (U() < 0.6f)
                    Put(Pick("DatePalm", "DatePalmTall"), At(Mathf.Max(d, 0f)) + F * Mathf.Min(d, 0f) + R * side * (14f + U() * 5f),
                        U() * Mathf.Tau, 0.9f + U() * 0.25f);
        Put("SandstoneArch", At(66f) - R * 7.5f, Kit.Facing(R));
        Put("Bones", At(74f) + R * 3.8f, U() * Mathf.Tau);
    }

    /// <summary>The temple approach: ruined columns in pairs every 9 m (some
    /// fallen), a skeleton by the way, a broken arch off to the left, obelisks
    /// at the plaza's mouth, braziers at the stair foot, the temple.</summary>
    private void TempleWay()
    {
        Vector2 At(float d) => SnowSite.PathAt(TempleFrom, TempleTo, d);
        for (var d = 4f; d < 60f; d += 9f)
            foreach (var side in new[] { -1f, 1f })
                if (U() > 0.2f)
                    Put("RuinedColumn", At(d) + R * side * 5f, U() * Mathf.Tau);
        Put("SandstoneArch", At(30f) - R * 10f, Kit.Facing(R));
        Put("Bones", At(22f) + R * 3.4f, U() * Mathf.Tau);
        var front = Temple - F * 16.5f;   // the stair foot
        foreach (var side in new[] { -1f, 1f })
        {
            Put("Obelisk", At(66f) + R * side * 6.5f, Kit.Facing(-F));
            foreach (var at in new[] { front + R * side * 5.5f, front + R * side * 12f - F * 6f })
            {
                Put("Brazier", at, 0f);
                // the fire lights the stair foot (it was emission only)
                Bake.Lamp(this, new LampLight { Name = "Brazier", Position = WorldGen.Snap(at) + Vector3.Up * 1.3f, Fire = true, Strength = 2.2f, Reach = 8f }, auto: true);
            }
        }
        Put("Temple", Temple, Kit.Facing(-F));
        _taken.Add((Temple, 26f));
        _taken.Add((front, 10f));
    }

    /// <summary>The oasis: the pool (<see cref="Water.Pool"/>) in the basin
    /// WorldGen carved, date palms leaning over it from the far bank and the
    /// sides (the near bank stays open to the camera), scrub and boulders on
    /// the banks, a traveller's camp by the path.</summary>
    private void Oasis()
    {
        var (c, r) = WorldGen.Oases[0];
        AddChild(Water.Pool(c, r, WorldGen.OasisLevel(0)));
        _taken.Add((c, r + 1.5f));
        for (var i = 0; i < 26; i++)
        {
            var a = U() * Mathf.Tau;
            var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
            if (dir.Dot(-F) > 0.3f) continue;
            var p = c + dir * (r + 1.2f + U() * 7f);
            if (WorldGen.TrailDistance(p.X, p.Y) < 2.5f) continue;
            var lean = U() < 0.45f;
            Put(lean ? "DatePalmLean" : Pick("DatePalm", "DatePalmTall"), p, lean ? Kit.Along(-dir) : U() * Mathf.Tau, 0.85f + U() * 0.3f);
        }
        for (var i = 0; i < 40; i++)
        {
            var a = U() * Mathf.Tau;
            var p = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * (r + 0.6f + U() * 4.5f);
            if (WorldGen.TrailDistance(p.X, p.Y) < 1.8f) continue;
            var roll = U();
            Put(roll < 0.55f ? "ScrubGrass" : roll < 0.85f ? "DryShrub" : "BoulderSmall", p, U() * Mathf.Tau, 0.8f + U() * 0.5f);
        }
        Vector2 At(float d) => SnowSite.PathAt(OasisFrom, OasisTo, d);
        var camp = At(22f) - R * 5.5f;
        Put("Awning", camp, Kit.Facing(R));
        Put("Pots", camp + F * 2.8f, U() * Mathf.Tau);
        Put("Crates", camp - F * 2.6f + R * 0.5f, U() * Mathf.Tau);
        Breakables.Add("Jar", camp + F * 2.8f + R * 1.4f, 0.3f);
        Breakables.Add("Pot", camp - F * 1.2f + R * 1.8f, 1.9f);
        _taken.Add((camp, 4f));
    }

    /// <summary>The dunes between: cacti and dry scrub thin and far apart,
    /// boulders and ledges where the ground is steep, sand piles along the
    /// trails, three mesas away from the paths. Nothing tall on the camera's
    /// side of a trail.</summary>
    private void Scatter()
    {
        foreach (var off in new[] { new Vector2(-75f, -55f), new Vector2(70f, 75f), new Vector2(-20f, -100f) })
        {
            Put("Mesa", C + off, U() * Mathf.Tau, 0.9f + U() * 0.3f);
            _taken.Add((C + off, 18f));
        }
        for (var i = 0; i < 3000; i++)
        {
            var p = C + new Vector2(U() * 2f - 1f, U() * 2f - 1f) * Half;
            var td = WorldGen.TrailDistance(p.X, p.Y);
            if (Region(p) < 0.45f || td < 2.5f || Taken(p)) continue;
            var tall = td < 12f && SnowSite.CameraSide(p);
            var slope = WorldGen.Slope(p.X, p.Y);
            var roll = U();
            var yaw = U() * Mathf.Tau;
            var s = 0.8f + U() * 0.45f;
            if (slope > 0.22f && roll < 0.08f && !tall) Put(Pick("BoulderLarge", "BoulderMedium", "SandstoneLedge"), p, yaw, s);
            else if (roll < 0.012f && !tall) Put("ColumnCactus", p, yaw, s);
            else if (roll < 0.03f) Put("BarrelCactus", p, yaw, s);
            else if (roll < 0.07f) Put("DryShrub", p, yaw, s);
            else if (roll < 0.12f) Put("ScrubGrass", p, yaw, s);
            else if (roll < 0.14f) Put("BoulderSmall", p, yaw, s);
        }
        // (not down the market street itself: drifts between the stalls, tour 1)
        for (var seg = MarketFrom + 1; seg <= OasisTo; seg++)
        {
            var t = WorldGen.Trails[seg];
            var a = new Vector2(t.X, t.Y);
            var ab = new Vector2(t.Z, t.W) - a;
            for (var d = 3f; d < ab.Length(); d += 5f + U() * 6f)
            {
                var p = a + ab.Normalized() * d + R * (U() < 0.5f ? -1f : 1f) * (2.6f + U() * 1.8f);
                if (!Taken(p)) Put("SandPile", p, U() * Mathf.Tau, 0.55f + U() * 0.6f);
            }
        }
    }
}
