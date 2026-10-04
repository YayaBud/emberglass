using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The whole map's trees, undergrowth and rocks, streamed round the player (implementation_plan
/// B0, user 2026-09-28: "the game looks dead and dry"). Until now only the sites had anything
/// on them; four of the seven regions were bare ground and grass.
///
/// 48 m cells, a disc of them ~150 m round the player. A cell's placements are a pure function
/// of its coordinates (worker threads, like the terrain and the grass): a jittered grid per
/// layer, thinned by a clumping field so there are groves and glades rather than an even
/// spread (the study's adoption #1), each point taking a region by the biome weights there and
/// a plant from that region's recipe. The main thread builds at most one cell a frame:
/// sprite plants through <see cref="Foliage.Forest"/> (a MultiMesh per variant, small enough
/// per cell -- INVARIANTS), kit assets through <see cref="Kit.Place"/> (with colliders).
///
/// Sprite casters are drawn to 85 m only (the sun's cascades end at 80); faces to 170 m, where
/// the mist has them. Kept clear of every site (the village, the wood, the pond, the Hoarfells
/// and Ashdunes sites, plus whatever <see cref="Keep"/> registers), the road, the trails, deep
/// water and steep rock.
/// </summary>
public partial class Scatter : Node3D
{
    public const float CellSize = 48f;
    private const int Reach = 3;
    private const int MaxJobs = 2;

    public static bool Enabled = true;
    public static Scatter? Live;

    // ------------------------------------------------------------------ recipes
    private readonly record struct Pick(string Name, float W, bool Kit = false, Kit.Kind K = Worldbuilder.Kit.Kind.Prop,
                                        float S0 = 0.85f, float S1 = 1.25f);

    /// <summary>Per region (Biome order): tree density in a grove, trees, undergrowth density,
    /// undergrowth.</summary>
    private static readonly (float Trees, Pick[] Tree, float Under, Pick[] Low)[] Recipe =
    {
        // Greenwood
        (0.55f, new Pick[] { new("oak", 0.35f), new("vine_oak", 0.15f), new("birch", 0.3f), new("pine", 0.2f) },
         0.22f, new Pick[] { new("bush", 0.4f), new("fern", 0.33f), new("flowers", 0.12f), new("mushroom", 0.05f), new("log", 0.1f) }),
        // Elder Meadows: lone trees, flower drifts, grain
        (0.05f, new Pick[] { new("oak", 0.6f, S0: 1f, S1: 1.35f), new("birch", 0.4f) },
         0.3f, new Pick[] { new("flowers", 0.5f, S0: 0.9f, S1: 1.4f), new("wheat", 0.2f), new("bush", 0.3f) }),
        // the Emberwood
        (0.55f, new Pick[] { new("autumn_oak", 0.5f), new("autumn_birch", 0.3f), new("oak", 0.1f), new("pine", 0.1f) },
         0.28f, new Pick[] { new("fern", 0.3f), new("mushroom", 0.2f), new("bush", 0.25f), new("log", 0.25f) }),
        // Duskfen
        (0.24f, new Pick[] { new("snag", 0.55f), new("willow", 0.45f) },
         0.32f, new Pick[] { new("reed", 0.6f), new("bush", 0.2f), new("mushroom", 0.1f), new("fern", 0.1f) }),
        // Greyward Crags
        (0.32f, new Pick[] { new("pine", 0.7f), new("birch", 0.12f), new("RockMedium", 0.1f, true, Worldbuilder.Kit.Kind.Rock),
                             new("RockLarge", 0.08f, true, Worldbuilder.Kit.Kind.Rock) },
         0.28f, new Pick[] { new("heather", 0.55f), new("fern", 0.1f), new("bush", 0.2f),
                             new("RockSmall", 0.15f, true, Worldbuilder.Kit.Kind.Rock, 0.6f, 1f) }),
        // the Ashdunes
        (0.04f, new Pick[] { new("DatePalm", 0.25f, true, Worldbuilder.Kit.Kind.Tree), new("DatePalmLean", 0.15f, true, Worldbuilder.Kit.Kind.Tree),
                             new("ColumnCactus", 0.3f, true, Worldbuilder.Kit.Kind.Tree), new("BoulderMedium", 0.3f, true, Worldbuilder.Kit.Kind.Rock) },
         0.05f, new Pick[] { new("BarrelCactus", 0.25f, true), new("DryShrub", 0.3f, true), new("ScrubGrass", 0.3f, true),
                             new("BoulderSmall", 0.15f, true, Worldbuilder.Kit.Kind.Rock) }),
        // the Hoarfells
        (0.3f, new Pick[] { new("PineMedium", 0.35f, true, Worldbuilder.Kit.Kind.Tree), new("PineSmall", 0.3f, true, Worldbuilder.Kit.Kind.Tree),
                            new("PineSparse", 0.15f, true, Worldbuilder.Kit.Kind.Tree), new("DeadTree", 0.08f, true, Worldbuilder.Kit.Kind.Tree),
                            new("RockMedium", 0.12f, true, Worldbuilder.Kit.Kind.Rock) },
         0.08f, new Pick[] { new("SnowBush", 0.4f, true), new("FrozenGrass", 0.4f, true), new("RockSmall", 0.2f, true, Worldbuilder.Kit.Kind.Rock) }),
    };

    // ------------------------------------------------------------------ where not
    private static readonly List<(Vector2 C, float R)> _keep = new();
    private static readonly Vector2 F2 = new(-0.7071f, -0.7071f), R2 = new(0.7071f, -0.7071f);

    /// <summary>Keep scatter out of a disc (a site's ground). Register before <see cref="Bind"/>.</summary>
    public static void Keep(Vector2 c, float r) => _keep.Add((c, r));

    private static bool Kept(Vector2 p)
    {
        // the village and the wood behind it, in the village's path space
        var a = p.Dot(F2);
        var b = p.Dot(R2);
        if (a > -135f && a < 105f && Mathf.Abs(b) < 55f) return true;
        if ((p - WorldGen.PondCentre).Length() < WorldGen.PondRadius * 1.6f) return true;
        if (Mathf.Abs(p.X + 430f) < 90f && Mathf.Abs(p.Y - 430f) < 90f) return true;           // SnowSite
        var d = p - WorldGen.DesertSiteCentre;
        if (Mathf.Abs(d.X) < 115f && Mathf.Abs(d.Y) < 115f) return true;                      // DesertSite
        if (Mathf.Abs(p.X) > Biomes.HalfWorld - 30f || Mathf.Abs(p.Y) > Biomes.HalfWorld - 30f) return true;
        if (WorldGen.PathDistance(p.X, p.Y) < 4.5f || WorldGen.TrailDistance(p.X, p.Y) < 3f) return true;
        foreach (var (c, r) in _keep)
            if ((p - c).LengthSquared() < r * r) return true;
        return false;
    }

    // ------------------------------------------------------------------ generation (pure)
    private sealed class Built
    {
        public readonly List<Foliage.Spot> Plants = new();
        public readonly Dictionary<string, (Kit.Kind K, List<Kit.Item> Items)> Kit = new();
    }

    [System.ThreadStatic] private static float[]? _w;

    private static int Choose(float[] w, float r)
    {
        var acc = 0f;
        for (var i = 0; i < w.Length; i++) { acc += w[i]; if (r < acc) return i; }
        return w.Length - 1;
    }

    private static Pick Of(Pick[] picks, float r)
    {
        var total = 0f;
        foreach (var p in picks) total += p.W;
        r *= total;
        foreach (var p in picks) { if (r < p.W) return p; r -= p.W; }
        return picks[^1];
    }

    private static Built Generate(Vector2I key)
    {
        _w ??= new float[Biomes.Count];
        var w = _w;
        var seed = WorldGen.Seed;
        var built = new Built();
        float x0 = key.X * CellSize, z0 = key.Y * CellSize;
        foreach (var (step, layer) in new[] { (5f, 0), (3f, 1) })
        {
            var n = (int)(CellSize / step);
            for (var j = 0; j < n; j++)
            for (var i = 0; i < n; i++)
            {
                int gi = key.X * n + i, gj = key.Y * n + j;
                ulong s = seed ^ (ulong)(0x5CA7 + layer * 977);
                var px = x0 + (i + 0.5f + (Biomes.Hash(gi, gj, s) - 0.5f) * 0.9f) * step;
                var pz = z0 + (j + 0.5f + (Biomes.Hash(gi, gj, s + 1) - 0.5f) * 0.9f) * step;
                var p = new Vector2(px, pz);
                if (Kept(p)) continue;
                Biomes.Weights(p, seed, w);
                var bi = Choose(w, Biomes.Hash(gi, gj, s + 2));
                var rec = Recipe[bi];
                // groves and glades: a low-frequency field, sharpened
                var clump = Biomes.Fbm(px * 0.018f, pz * 0.018f, seed ^ 0xC1A3UL);
                var dens = layer == 0
                    ? rec.Trees * Mathf.SmoothStep(0.38f, 0.62f, clump) + rec.Trees * 0.08f
                    : rec.Under * (0.4f + 0.9f * Mathf.SmoothStep(0.3f, 0.7f, clump));
                dens = TerrainEdit.ScatterZone(px, pz, layer, dens);   // the zones painted in Terrain3D
                if (Biomes.Hash(gi, gj, s + 3) >= dens) continue;
                var pick = Of(layer == 0 ? rec.Tree : rec.Low, Biomes.Hash(gi, gj, s + 4));
                var h = WorldGen.Height(px, pz);
                var slope = 1f - WorldGen.Normal(px, pz).Y;
                var rock = pick.K == Worldbuilder.Kit.Kind.Rock;
                if (slope > (rock ? 0.6f : 0.3f)) continue;
                // standing water: only the Fen's reeds and dead trees stand in it
                if (h < WorldGen.FenWaterLevel + 0.15f)
                {
                    if (bi != (int)Biome.Fen || h < WorldGen.FenWaterLevel - 0.9f) continue;
                    pick = layer == 0 ? new Pick("snag", 1f) : new Pick("reed", 1f);
                }
                var scale = Mathf.Lerp(pick.S0, pick.S1, Biomes.Hash(gi, gj, s + 5));
                var snow = w[(int)Biome.Snow] < 0.05f ? 0f : w[(int)Biome.Snow];
                var foot = new Vector3(px, h, pz);
                if (pick.Kit)
                {
                    if (!built.Kit.TryGetValue(pick.Name, out var e)) built.Kit[pick.Name] = e = (pick.K, new List<Kit.Item>());
                    e.Items.Add(new Kit.Item(foot, Biomes.Hash(gi, gj, s + 6) * Mathf.Tau, scale, snow));
                }
                else built.Plants.Add(new Foliage.Spot(pick.Name, foot, scale, layer == 0 || pick.Name == "log", snow));
            }
        }
        return built;
    }

    // ------------------------------------------------------------------ streaming
    private sealed class Cell
    {
        public Task<Built>? Job;
        public Node3D? Node;
    }

    private readonly Dictionary<Vector2I, Cell> _cells = new();
    private readonly List<Vector2I> _drop = new();
    private static readonly Vector2I[] _ring = Ring();
    private Node3D _player = null!;
    public static int Plants, Pieces, CellsBuilt;

    private static Vector2I[] Ring()
    {
        var l = new List<Vector2I>();
        for (var z = -Reach; z <= Reach; z++)
        for (var x = -Reach; x <= Reach; x++)
            if (x * x + z * z <= (Reach + 0.5f) * (Reach + 0.5f)) l.Add(new Vector2I(x, z));
        return l.OrderBy(v => v.X * v.X + v.Y * v.Y).ToArray();
    }

    public void Bind(Node3D player)
    {
        _player = player;
        Live = this;
    }

    public override void _Process(double delta)
    {
        if (_player == null) return;
        var p = _player.GlobalPosition;
        var c0 = new Vector2I(Mathf.FloorToInt(p.X / CellSize), Mathf.FloorToInt(p.Z / CellSize));
        _drop.Clear();
        var running = 0;
        foreach (var (k, cell) in _cells)
        {
            if (Mathf.Max(Mathf.Abs(k.X - c0.X), Mathf.Abs(k.Y - c0.Y)) > Reach + 1) _drop.Add(k);
            else if (cell.Job is { IsCompleted: false }) running++;
        }
        foreach (var k in _drop)
        {
            _cells[k].Node?.QueueFree();
            _cells.Remove(k);
        }
        // at most one cell built a frame (INVARIANTS: the main thread's budget)
        foreach (var (k, cell) in _cells)
        {
            if (cell.Job is not { IsCompleted: true } job) continue;
            cell.Job = null;
            if (job.IsFaulted) { GD.PushError("scatter: " + job.Exception?.GetBaseException().Message); break; }
            cell.Node = Land(k, job.Result);
            break;
        }
        foreach (var off in _ring)
        {
            if (running >= MaxJobs) break;
            var k = c0 + off;
            if (_cells.ContainsKey(k)) continue;
            _cells[k] = new Cell { Job = Task.Run(() => Generate(k)) };
            running++;
        }
    }

    private Node3D Land(Vector2I key, Built b)
    {
        var node = new Node3D { Name = $"Scatter_{key.X}_{key.Y}" };
        AddChild(node);
        if (b.Plants.Count > 0)
        {
            Foliage.Forest(node, b.Plants, Grade.L.Yaw);
            foreach (var c in node.GetChildren())
                if (c is MultiMeshInstance3D mm)
                    mm.VisibilityRangeEnd = mm.CastShadow == GeometryInstance3D.ShadowCastingSetting.ShadowsOnly ? 85f : 170f;
        }
        foreach (var (asset, (kind, items)) in b.Kit) Kit.Place(node, asset, items, kind);
        Plants += b.Plants.Count;
        foreach (var e in b.Kit.Values) Pieces += e.Items.Count;
        CellsBuilt++;
        return node;
    }
}
