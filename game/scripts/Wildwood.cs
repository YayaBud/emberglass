using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// A test forest behind the spawn: mixed wood, ivy-hung oaks, ferns and
/// fallen logs around a path and four glades, with deer, foxes, rabbits and
/// robins that wander their glade, walk round trunks and logs, and bolt when
/// the player comes close.
///
/// Placed in the same path space as <see cref="Village"/> (a along the road,
/// b screen-right), at a = -125..-40: behind the camera at the spawn, so the
/// spawn frame and every light study measured from it are untouched. Walk
/// back down the road ~25 m to reach it.
///
/// Plants go through <see cref="Foliage.Forest"/>, batched per 20 m tile;
/// animals through <see cref="Fauna"/>.
/// </summary>
public partial class Wildwood : Node3D
{
    private static readonly Vector3 F = new(-0.7071f, 0f, -0.7071f);
    private static readonly Vector3 R = new(0.7071f, 0f, -0.7071f);
    private const float A0 = -125f, A1 = -40f, B0 = -42f, B1 = 42f;

    /// <summary>Clearings, path space (a, b, radius). Animals live in them.</summary>
    private static readonly (float A, float B, float R)[] Glades =
    {
        (-62f, -16f, 8f), (-88f, 12f, 10f), (-108f, -10f, 8f), (-55f, 20f, 6f),
    };

    /// <summary>Species, how many, and where: a glade index, -1 = scattered
    /// along the path, -2 = one per glade in turn.</summary>
    private static readonly (Fauna.Kind Kind, int Count, int Glade)[] Kinds =
    {
        (new("doe", 1.1f, 7.5f, 11f, 8f, 0.34f, 0.45f, "graze"), 4, 1),
        (new("stag", 1.0f, 7.5f, 12f, 8f, 0.36f, 0.5f, "graze"), 1, 1),
        (new("fox", 1.7f, 6.5f, 8f, 16f, 0.22f, 0.3f, "sniff"), 2, 0),
        (new("rabbit", 1.3f, 5.5f, 5f, 6f, 0.3f, 0.2f, "sit"), 8, -2),
        (new("robin", 0.6f, 5f, 4f, 4f, 0.08f, 0.1f, "peck", Flies: true), 8, -1),
    };

    private static readonly HashSet<string> Trunked = new()
    {
        "oak", "vine_oak", "pine", "birch", "autumn_oak", "autumn_birch", "snag", "willow",
    };

    private readonly System.Random _rng = new(4242);

    private static Vector3 World(float a, float b) => F * a + R * b;
    private static Vector2 Flat(Vector3 v) => new(v.X, v.Z);
    private static float PathB(float a) => 3f * Mathf.Sin(a * 0.04f);

    /// <summary>0 on the path and in the glades, 1 in the thick of it.</summary>
    private static float Thicket(float a, float b)
    {
        var c = Mathf.SmoothStep(2.8f, 4.8f, Mathf.Abs(b - PathB(a)));
        foreach (var g in Glades)
            c = Mathf.Min(c, Mathf.SmoothStep(g.R, g.R + 3f, new Vector2(a - g.A, b - g.B).Length()));
        return c;
    }

    /// <summary>Keep a point inside the wood (path space box, 4 m in).</summary>
    private static Vector2 Inside(Vector2 p)
    {
        var a = Mathf.Clamp(p.X * F.X + p.Y * F.Z, A0 + 4f, A1 - 4f);
        var b = Mathf.Clamp(p.X * R.X + p.Y * R.Z, B0 + 4f, B1 - 4f);
        return Flat(World(a, b));
    }

    public void Build(Node3D player)
    {
        var spots = Plants();
        var fauna = new Fauna { Name = "Fauna", Keep = Inside };
        AddChild(fauna);
        fauna.Bind(player, 4242);
        Blockers(fauna, spots);
        foreach (var (kind, count, glade) in Kinds)
        {
            var homes = new List<Vector2>();
            for (var i = 0; i < count; i++)
            {
                if (glade != -1)
                {
                    var g = Glades[glade == -2 ? i % Glades.Length : glade];
                    var r = g.R * 0.6f * Mathf.Sqrt((float)_rng.NextDouble());
                    var t = (float)_rng.NextDouble() * Mathf.Tau;
                    homes.Add(Flat(World(g.A + Mathf.Cos(t) * r, g.B + Mathf.Sin(t) * r)));
                }
                else
                {
                    var a = A1 - 8f - (float)_rng.NextDouble() * (A1 - A0 - 16f);
                    homes.Add(Flat(World(a, PathB(a) + ((float)_rng.NextDouble() - 0.5f) * 5f)));
                }
            }
            fauna.Add(kind, homes);
        }
        GD.Print($"wildwood: {spots.Count} plants, {fauna.Count} animals");
    }

    /// <summary>What animals walk round: a circle per trunk (its base is
    /// ~0.6 m wide on the sprite, plus the root flare) and a chain of circles
    /// along each log, which lies across the view, along R. Bushes, ferns
    /// and reeds they walk through.</summary>
    public static void Blockers(Fauna fauna, IEnumerable<Foliage.Spot> spots)
    {
        var r = new Vector2(R.X, R.Z);
        foreach (var sp in spots)
        {
            var at = Flat(sp.Foot);
            if (Trunked.Contains(sp.Kind)) fauna.Block(at, 0.4f * sp.Scale);
            else if (sp.Kind == "log")
                for (var i = -2; i <= 2; i++) fauna.Block(at + r * (i * 0.6f * sp.Scale), 0.4f * sp.Scale);
        }
    }

    private List<Foliage.Spot> Plants()
    {
        var rng = new System.Random(1717);
        float U() => (float)rng.NextDouble();
        var spots = new List<Foliage.Spot>();
        void Add(string kind, float a, float b, float scale, bool shadow)
        {
            var at = World(a, b);
            at.Y = WorldGen.Height(at.X, at.Z);
            spots.Add(new Foliage.Spot(kind, at, scale, shadow));
        }
        string Tree(float r) => r < 0.3f ? "vine_oak" : r < 0.55f ? "oak" : r < 0.8f ? "pine" : "birch";

        // trees: jittered grid, thinned by a clumping field, feathered at the
        // region's edge so it does not stop on a straight line
        for (var a = A0; a < A1; a += 2.6f)
        for (var b = B0; b < B1; b += 2.6f)
        {
            var ja = a + (U() - 0.5f) * 2.2f;
            var jb = b + (U() - 0.5f) * 2.2f;
            var edge = Mathf.Min(Mathf.Min(ja - A0, A1 - ja), Mathf.Min(jb - B0, B1 - jb));
            var clump = Biomes.Fbm(ja * 0.06f, jb * 0.06f, WorldGen.Seed ^ 0x3A11UL);
            var fill = Mathf.SmoothStep(0f, 8f, edge) * Mathf.SmoothStep(0.3f, 0.55f, clump) * Thicket(ja, jb);
            if (U() > 0.9f * fill) continue;
            Add(Tree(U()), ja, jb, 0.85f + U() * 0.45f, true);
            if (U() < 0.6f)
                Add(U() < 0.5f ? "bush" : "fern", ja - 0.9f, jb + (U() - 0.5f) * 1.8f, 0.8f + U() * 0.6f, false);
        }

        // ground cover: ferns and bushes everywhere but the path, thinner in the glades
        for (var a = A0 + 3f; a < A1 - 3f; a += 1.9f)
        for (var b = B0 + 3f; b < B1 - 3f; b += 1.9f)
        {
            var ja = a + (U() - 0.5f) * 1.6f;
            var jb = b + (U() - 0.5f) * 1.6f;
            if (Mathf.Abs(jb - PathB(ja)) < 2.2f) continue;
            if (U() > 0.12f + 0.3f * Thicket(ja, jb)) continue;
            Add(U() < 0.65f ? "fern" : "bush", ja, jb, 0.7f + U() * 0.5f, false);
        }

        // fallen logs at the glades' rims and a few in the wood
        foreach (var g in Glades)
        {
            var t = U() * Mathf.Tau;
            Add("log", g.A + Mathf.Cos(t) * g.R * 0.8f, g.B + Mathf.Sin(t) * g.R * 0.8f, 0.9f + U() * 0.3f, false);
        }
        for (var i = 0; i < 14; i++)
        {
            float a = A0 + 6f + U() * (A1 - A0 - 12f), b = B0 + 6f + U() * (B1 - B0 - 12f);
            if (Mathf.Abs(b - PathB(a)) > 4f) Add("log", a, b, 0.8f + U() * 0.4f, false);
        }

        Tiled(this, spots);
        return spots;
    }

    /// <summary>Plants batched per 20 m tile, not once per site: one
    /// MultiMesh spanning 85 m put every caster in the sun's cascades
    /// whenever any corner of it was near the view -- +1.2 ms GPU at the spawn
    /// with the wood behind the camera, ~0.15 ms with shadows off
    /// (2026-09-23).</summary>
    public static void Tiled(Node3D parent, List<Foliage.Spot> spots,
                             List<(MultiMesh Mm, int I, Foliage.Spot Sp)>? faces = null)
    {
        spots = Bake.Plants(spots);
        var tiles = new Dictionary<Vector2I, List<Foliage.Spot>>();
        foreach (var sp in spots)
        {
            var key = new Vector2I(Mathf.FloorToInt(sp.Foot.X / 20f), Mathf.FloorToInt(sp.Foot.Z / 20f));
            if (!tiles.TryGetValue(key, out var list)) tiles[key] = list = new List<Foliage.Spot>();
            list.Add(sp);
        }
        foreach (var (key, list) in tiles)
        {
            var holder = new Node3D { Name = $"Plants_{key.X}_{key.Y}" };
            parent.AddChild(holder);
            Foliage.Forest(holder, list, Grade.L.Yaw, faces);
        }
    }
}
