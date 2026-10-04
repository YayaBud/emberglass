using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Grass with depth (user, 2026-09-27: "the ground is too flat no grass no
/// groves nothing -- look at the reference photos"): tufts of real blades on
/// every grass ground, streamed in 16 m cells round the player, one MultiMesh
/// per cell. A tuft takes the ground's own tint (dark root, light tip, in
/// four flat tones like the texture ramps), sways in the wind, parts round the
/// player, and now and then flowers.
///
/// Where it must not grow is decided by pure rules (WorldGen: water, the
/// village road; CityPlan: roads, the plaza, the squares, water) plus shapes
/// the sites register while they build, before streaming starts
/// (<see cref="ClearBox"/>, <see cref="ClearSeg"/>, <see cref="ClearNode"/>).
/// Every shape has a fringe where the grass grows thicker and taller and
/// flowers more: the weeds at a wall's foot that the reference towns all draw.
/// Generation is pure and runs on <c>Task.Run</c>, like the terrain's.
/// </summary>
public partial class Grass : Node3D
{
    public const float CellSize = 16f;
    /// <summary>Cells round the player's, as a disc: ~64 m.</summary>
    private const int Reach = 4;
    /// <summary>The jittered grid's spacing: ~7.7 tufts a square metre at full
    /// density; the city's verges and gardens 0.28 (12.8): seen from its 22 deg
    /// pitch the 0.36 grid left the ground showing between tufts, a dotted
    /// lawn (groundshots 2026-09-27).</summary>
    private const float Pitch = 0.36f, CityPitch = 0.28f;
    private const int MaxJobs = 4, MaxBuilds = 2;
    /// <summary>The blades shrink into the ground between these (camera metres).</summary>
    public const float FadeFrom = 40f, FadeTo = 58f;

    /// <summary>`--nograss` clears it before the node exists.</summary>
    public static bool Enabled = true;
    /// <summary>The harness's price toggle: hidden, still streaming.</summary>
    public static bool Shown = true;
    public static Grass? Live;

    // ------------------------------------------------------------------ cleared shapes
    private readonly record struct Shape(Vector2 A, Vector2 B, Vector2 U, Vector2 H, float R, float Fringe, bool Box);
    private static readonly List<Shape> _shapes = new();
    private static readonly Dictionary<Vector2I, List<int>> _index = new();
    private const float IndexCell = 8f;
    private static bool _frozen;

    /// <summary>No grass inside an oriented box: centre c, unit axis u along
    /// which the half-extent is h.X (h.Y across); thicker within `fringe`.</summary>
    public static void ClearBox(Vector2 c, Vector2 u, Vector2 h, float fringe = 0.9f)
    {
        var r = h.Length() + fringe;
        Add(new Shape(c, c, u.Normalized(), h, 0f, fringe, true), c - new Vector2(r, r), c + new Vector2(r, r));
    }

    /// <summary>No grass within r of the segment a-b (a disc when a == b).</summary>
    public static void ClearSeg(Vector2 a, Vector2 b, float r, float fringe = 0.9f)
    {
        var e = new Vector2(r + fringe, r + fringe);
        Add(new Shape(a, b, Vector2.Zero, Vector2.Zero, r, fringe, false),
            new Vector2(Mathf.Min(a.X, b.X), Mathf.Min(a.Y, b.Y)) - e, new Vector2(Mathf.Max(a.X, b.X), Mathf.Max(a.Y, b.Y)) + e);
    }

    public static void ClearDisc(Vector2 c, float r, float fringe = 0.6f) => ClearSeg(c, c, r, fringe);

    /// <summary>The footprint of a placed model (a house): its meshes' merged
    /// box in the root's own frame, turned with the root's yaw, less 0.3 m of
    /// eave each side.</summary>
    public static void ClearNode(Node3D root, float fringe = 0.9f)
    {
        var inv = root.GlobalTransform.AffineInverse();
        var box = new Aabb();
        var any = false;
        void Walk(Node n)
        {
            if (n is MeshInstance3D mi && !mi.Name.ToString().StartsWith("SHADOW_") && !mi.Name.ToString().StartsWith("COL_"))
            {
                var b = (inv * mi.GlobalTransform) * mi.GetAabb();
                box = any ? box.Merge(b) : b;
                any = true;
            }
            foreach (var c in n.GetChildren()) Walk(c);
        }
        Walk(root);
        if (!any) return;
        var x = root.GlobalBasis.X;
        var scale = x.Length();
        var c = root.GlobalTransform * box.GetCenter();
        var h = new Vector2(Mathf.Max(box.Size.X * 0.5f * scale - 0.3f, 0.4f), Mathf.Max(box.Size.Z * 0.5f * scale - 0.3f, 0.4f));
        ClearBox(new Vector2(c.X, c.Z), new Vector2(x.X, x.Z), h, fringe);
    }

    private static void Add(Shape s, Vector2 lo, Vector2 hi)
    {
        // the workers read the registry without a lock: it is filled while the
        // sites build, and closed when streaming begins
        if (_frozen) { GD.PushWarning("grass: a shape registered after streaming began is ignored"); return; }
        var i = _shapes.Count;
        _shapes.Add(s);
        for (var gz = Mathf.FloorToInt(lo.Y / IndexCell); gz <= Mathf.FloorToInt(hi.Y / IndexCell); gz++)
        for (var gx = Mathf.FloorToInt(lo.X / IndexCell); gx <= Mathf.FloorToInt(hi.X / IndexCell); gx++)
        {
            var k = new Vector2I(gx, gz);
            if (!_index.TryGetValue(k, out var l)) _index[k] = l = new List<int>();
            l.Add(i);
        }
    }

    /// <summary>0 clear of every shape, rising to 1 at a shape's edge; `blocked` inside one.</summary>
    private static float Fringe(Vector2 p, out bool blocked)
    {
        blocked = false;
        if (!_index.TryGetValue(new Vector2I(Mathf.FloorToInt(p.X / IndexCell), Mathf.FloorToInt(p.Y / IndexCell)), out var l)) return 0f;
        var fr = 0f;
        foreach (var i in l)
        {
            var s = _shapes[i];
            float d;
            if (s.Box)
            {
                var q = p - s.A;
                var lx = Mathf.Abs(q.Dot(s.U)) - s.H.X;
                var ly = Mathf.Abs(q.Y * s.U.X - q.X * s.U.Y) - s.H.Y;
                d = new Vector2(Mathf.Max(lx, 0f), Mathf.Max(ly, 0f)).Length() + Mathf.Min(Mathf.Max(lx, ly), 0f);
            }
            else d = CityPlan.SegDist(p, s.A, s.B) - s.R;
            if (d < 0f) { blocked = true; return 0f; }
            if (d < s.Fringe) fr = Mathf.Max(fr, 1f - d / s.Fringe);
        }
        return fr;
    }

    // ------------------------------------------------------------------ generation (pure)
    private readonly record struct Built(float[] Buf, int Count, Vector3 Origin, float Y0, float Y1);

    /// <summary>How thick each region grows, by Biome: Greenwood, Meadow,
    /// Emberwood (leaf litter), Fen, Crags, Dunes, Snow.</summary>
    private static readonly float[] Grow = { 1f, 1f, 0.35f, 0.7f, 0.25f, 0f, 0f };

    public static long GenUsec, Generated, Tufts;

    private static float Hash(int x, int z, uint k)
    {
        unchecked
        {
            var h = (uint)x * 0x8DA6B343u ^ (uint)z * 0xD8163841u ^ (k + 0x9E3779B9u) * 0xCB1AB31Fu;
            h ^= h >> 15; h *= 0x2C1B3C6Du; h ^= h >> 12; h *= 0x297A2D39u; h ^= h >> 15;
            return (h & 0xFFFFFF) / 16777216f;
        }
    }

    private static Built Generate(Vector2I key)
    {
        var t0 = System.Diagnostics.Stopwatch.GetTimestamp();
        const float g = Terrain.Cell;
        const int n = (int)(CellSize / g);
        const int m = n + 3;
        float x0 = key.X * CellSize, z0 = key.Y * CellSize;
        // the terrain's own 2 m grid over the cell, one point of margin round it
        var hg = new float[m * m];
        for (var j = 0; j < m; j++)
        for (var i = 0; i < m; i++)
            hg[j * m + i] = WorldGen.Height(x0 + (i - 1) * g, z0 + (j - 1) * g);
        float H(int i, int j) => hg[(j + 1) * m + i + 1];

        // density and tint at each grid point, bilinear between
        var dens = new float[(n + 1) * (n + 1)];
        var tint = new Vector3[(n + 1) * (n + 1)];
        var w = new float[Biomes.Count];
        var city = CityPlan.ToPlan(x0 + CellSize / 2f, z0 + CellSize / 2f).Length() < CityPlan.Outer;
        for (var j = 0; j <= n; j++)
        for (var i = 0; i <= n; i++)
        {
            float gx = x0 + i * g, gz = z0 + j * g;
            var nrm = new Vector3(-(H(i + 1, j) - H(i - 1, j)), 2f * g, -(H(i, j + 1) - H(i, j - 1))).Normalized();
            var slope = 1f - nrm.Y;
            var col = WorldGen.Albedo(gx, gz, slope, out var desert, out var fen);
            var d = 0f;
            if (city && CityPlan.ToPlan(gx, gz).Length() < CityPlan.Influence) d = 1f;   // kept land
            else
            {
                Biomes.Weights(new Vector2(gx, gz), WorldGen.Seed, w);
                for (var b = 0; b < w.Length; b++) d += w[b] * Grow[b];
                // the Fen's mud (Surface.Mud, the terrain's UV.y) is mostly bare
                d *= 1f - 0.75f * Surface.Mud(fen, H(i, j));
            }
            d *= 1f - Mathf.SmoothStep(0.16f, 0.3f, slope);
            // snow and desert country -- not the city: 1 km off the map its
            // blended weights carry ~9 % Ashdunes
            if (!city)
            {
                d *= 1f - Mathf.SmoothStep(0.02f, 0.25f, col.A);
                d *= 1f - Mathf.SmoothStep(0.02f, 0.25f, desert);
            }
            dens[j * (n + 1) + i] = TerrainEdit.GrassZone(gx, gz, d);   // the zones painted in Terrain3D
            tint[j * (n + 1) + i] = new Vector3(col.R, col.G, col.B);
        }
        float Bil(float fx, float fz, out Vector3 tn)
        {
            fx = Mathf.Clamp(fx, 0f, n - 1e-3f);
            fz = Mathf.Clamp(fz, 0f, n - 1e-3f);
            int i = (int)fx, j = (int)fz;
            float u = fx - i, v = fz - j;
            int a = j * (n + 1) + i, b = a + 1, c = a + n + 1, e = c + 1;
            tn = (tint[a] * (1 - u) + tint[b] * u) * (1 - v) + (tint[c] * (1 - u) + tint[e] * u) * v;
            return (dens[a] * (1 - u) + dens[b] * u) * (1 - v) + (dens[c] * (1 - u) + dens[e] * u) * v;
        }

        var lc = CityPlan.BaseLevel();
        var pondR2 = WorldGen.PondRadius * 2.4f * WorldGen.PondRadius * 2.4f;
        var origin = new Vector3(x0 + CellSize / 2f, H(n / 2, n / 2), z0 + CellSize / 2f);
        var buf = new List<float>(4096);
        float y0 = float.MaxValue, y1 = float.MinValue;
        var pitch = city ? CityPitch : Pitch;
        int i0 = Mathf.CeilToInt(x0 / pitch - 0.5f), i1 = Mathf.CeilToInt((x0 + CellSize) / pitch - 0.5f);
        int k0 = Mathf.CeilToInt(z0 / pitch - 0.5f), k1 = Mathf.CeilToInt((z0 + CellSize) / pitch - 0.5f);
        for (var gk = k0; gk < k1; gk++)
        for (var gi = i0; gi < i1; gi++)
        {
            var px = (gi + 0.5f + (Hash(gi, gk, 1) - 0.5f) * 0.9f) * pitch;
            var pz = (gk + 0.5f + (Hash(gi, gk, 2) - 0.5f) * 0.9f) * pitch;
            var dBase = Bil((px - x0) / g, (pz - z0) / g, out var tn);
            if (dBase < 0.02f) continue;

            // on the facet the terrain draws: the same quad split, checkerboard diagonals
            int I = Mathf.FloorToInt(px / g), J = Mathf.FloorToInt(pz / g);
            int li = I - key.X * n, lj = J - key.Y * n;
            float ha = H(li, lj), hb = H(li + 1, lj), hc = H(li + 1, lj + 1), hd = H(li, lj + 1);
            float qx = px / g - I, qz = pz / g - J;
            var y = ((I + J) & 1) == 0
                ? (qx >= qz ? ha + (hb - ha) * qx + (hc - hb) * qz : ha + (hc - hd) * qx + (hd - ha) * qz)
                : (qx + qz <= 1f ? ha + (hb - ha) * qx + (hd - ha) * qz : hc + (hd - hc) * (1f - qx) + (hb - hc) * (1f - qz));

            // water
            if (y < WorldGen.FenWaterLevel + 0.12f) continue;
            var p = new Vector2(px, pz);
            if ((p - WorldGen.PondCentre).LengthSquared() < pondR2 && y < WorldGen.PondLevel + 0.1f) continue;

            var d = dBase;
            var tall = 1f;
            var bloom = 0.022f;
            // the village road, and tufts leaning over its dirt margin
            var pd = WorldGen.PathDistance(px, pz);
            if (pd < WorldGen.PathHalfWidth + 3.2f)
            {
                var edge = WorldGen.PathHalfWidth + (Biomes.Fbm(px * 0.35f, pz * 0.35f, WorldGen.Seed ^ 0x7A7AUL) - 0.5f) * 1.2f;
                if (pd < edge + 0.3f) continue;
                if (pd < edge + 1.4f) { tall = 1.35f; bloom += 0.04f; }
            }
            if (city)
            {
                var q = CityPlan.ToPlan(px, pz);
                const float pr = CityPlan.PlazaR + 0.4f, sr = CityPlan.SquareR + 0.4f;
                if (q.LengthSquared() < pr * pr) continue;
                var onSquare = false;
                foreach (var s in CityPlan.Squares)
                    if ((q - s).LengthSquared() < sr * sr) { onSquare = true; break; }
                if (onSquare) continue;
                var rc = CityPlan.RoadClear(q);
                if (rc < 0.02f) continue;
                if (rc < 1.2f) { tall = Mathf.Max(tall, 1.3f); bloom += 0.03f; }
                if (y < lc + CityPlan.Sea + 0.2f || CityPlan.IsWater(q)) continue;
            }
            var fr = Fringe(p, out var blocked);
            if (blocked) continue;
            if (fr > 0f)
            {
                d = Mathf.Max(d, fr * Mathf.Min(1f, dBase * 3f));
                tall *= 1f + 0.5f * fr;
                bloom += 0.22f * fr;
            }
            if (Hash(gi, gk, 3) >= d) continue;

            var yaw = Hash(gi, gk, 4) * Mathf.Tau;
            float sn = Mathf.Sin(yaw), cs = Mathf.Cos(yaw);
            var sc = (0.72f + 0.56f * Hash(gi, gk, 5)) * tall;
            float ox = px - origin.X, oy = y - origin.Y, oz = pz - origin.Z;
            // MultiMesh 3D rows: (X.x Y.x Z.x o.x) (X.y Y.y Z.y o.y) (X.z Y.z Z.z o.z)
            buf.Add(cs * sc); buf.Add(0f); buf.Add(sn * sc); buf.Add(ox);
            buf.Add(0f); buf.Add(sc); buf.Add(0f); buf.Add(oy);
            buf.Add(-sn * sc); buf.Add(0f); buf.Add(cs * sc); buf.Add(oz);
            tn *= 0.86f + 0.28f * Hash(gi, gk, 6);
            if (Hash(gi, gk, 7) < 0.14f) tn *= new Vector3(1.12f, 1.04f, 0.78f);   // sun-dried
            var code = Hash(gi, gk, 8) < bloom ? 1 + (int)(Hash(gi, gk, 9) * 3.999f) : 0;
            buf.Add(tn.X); buf.Add(tn.Y); buf.Add(tn.Z); buf.Add(code + Hash(gi, gk, 10) * 0.99f);
            y0 = Mathf.Min(y0, oy);
            y1 = Mathf.Max(y1, oy);
        }

        // random order, so any prefix is an even thinning (VisibleInstanceCount)
        var count = buf.Count / 16;
        var arr = buf.ToArray();
        var rng = new System.Random(key.X * 73856093 ^ key.Y * 19349663);
        var tmp = new float[16];
        for (var a = count - 1; a > 0; a--)
        {
            var b = rng.Next(a + 1);
            System.Array.Copy(arr, a * 16, tmp, 0, 16);
            System.Array.Copy(arr, b * 16, arr, a * 16, 16);
            System.Array.Copy(tmp, 0, arr, b * 16, 16);
        }
        var us = (long)((System.Diagnostics.Stopwatch.GetTimestamp() - t0) * 1_000_000.0 / System.Diagnostics.Stopwatch.Frequency);
        System.Threading.Interlocked.Add(ref GenUsec, us);
        System.Threading.Interlocked.Increment(ref Generated);
        System.Threading.Interlocked.Add(ref Tufts, count);
        return new Built(arr, count, origin, count > 0 ? y0 : 0f, count > 0 ? y1 : 0f);
    }

    // ------------------------------------------------------------------ streaming
    private sealed class Cell
    {
        public Task<Built>? Job;
        public MultiMeshInstance3D? Node;
        public int Count, Shown = -2;
        public Vector3 Centre;
    }

    private readonly Dictionary<Vector2I, Cell> _cells = new();
    private readonly List<Vector2I> _drop = new();
    private static readonly Vector2I[] _ring = Ring();
    private Node3D _player = null!;
    private static ArrayMesh? _mesh;
    private static ShaderMaterial? _mat;

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
        _frozen = true;
        Live = this;
    }

    /// <summary>For the harness: what is built and what it cost.</summary>
    public string Stats()
    {
        var built = _cells.Values.Where(c => c.Node != null).ToList();
        var shown = built.Sum(c => c.Shown < 0 ? c.Count : c.Shown);
        return $"{_cells.Count} cells, {built.Count} with grass, {built.Sum(c => c.Count)} tufts ({shown} drawn), "
               + $"gen {(Generated > 0 ? GenUsec / 1000.0 / Generated : 0):F1} ms/cell over {Generated}, {_shapes.Count} cleared shapes";
    }

    public override void _Process(double delta)
    {
        Visible = Shown;
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
        // a job still running for a dropped cell finishes into nothing
        foreach (var k in _drop)
        {
            _cells[k].Node?.QueueFree();
            _cells.Remove(k);
        }
        var built = 0;
        foreach (var cell in _cells.Values)
        {
            if (built >= MaxBuilds) break;
            if (cell.Job is not { IsCompleted: true } job) continue;
            cell.Job = null;
            if (job.IsFaulted) { GD.PushError("grass: " + job.Exception?.GetBaseException().Message); continue; }
            Land(cell, job.Result);
            built++;
        }
        foreach (var off in _ring)
        {
            if (running >= MaxJobs) break;
            var k = c0 + off;
            if (_cells.ContainsKey(k)) continue;
            _cells[k] = new Cell { Job = Task.Run(() => Generate(k)) };
            running++;
        }
        // far cells draw a random share of their tufts: full to 22 m, 0.3 past 50
        // (the village priced +1.6 ms GPU on a GTX 1650 at full to 26 m)
        var cam = GetViewport().GetCamera3D();
        if (cam == null) return;
        var eye = cam.GlobalPosition;
        foreach (var cell in _cells.Values)
        {
            if (cell.Node == null) continue;
            var d = new Vector2(cell.Centre.X - eye.X, cell.Centre.Z - eye.Z).Length();
            var want = Mathf.CeilToInt(cell.Count * Mathf.Clamp(1f - (d - 22f) / 40f, 0.3f, 1f));
            if (Mathf.Abs(want - cell.Shown) > cell.Count / 20 || (want == cell.Count && cell.Shown != want))
            {
                cell.Node.Multimesh.VisibleInstanceCount = want;
                cell.Shown = want;
            }
        }
    }

    private void Land(Cell cell, Built b)
    {
        cell.Count = b.Count;
        cell.Centre = b.Origin;
        if (b.Count == 0) return;
        _mesh ??= Tuft();
        _mat ??= Material();
        var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseCustomData = true, Mesh = _mesh };
        mm.InstanceCount = b.Count;
        mm.Buffer = b.Buf;
        var node = new MultiMeshInstance3D
        {
            Name = "GrassCell",
            Multimesh = mm,
            MaterialOverride = _mat,
            // small things cast no shadow (memory.md: the cascades are the bill)
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            GIMode = GeometryInstance3D.GIModeEnum.Disabled,
            Position = b.Origin,
            // wind and the lean reach past the roots
            CustomAabb = new Aabb(new Vector3(-CellSize / 2f - 1f, b.Y0 - 0.5f, -CellSize / 2f - 1f),
                                  new Vector3(CellSize + 2f, b.Y1 - b.Y0 + 1.6f, CellSize + 2f)),
            // past the fade every blade is flat: measured from the cell's centre
            VisibilityRangeEnd = FadeTo + CellSize * 0.75f,
        };
        AddChild(node);
        cell.Node = node;
        cell.Shown = -2;
    }

    // ------------------------------------------------------------------ the tuft
    /// <summary>Seven tapered blades arcing out from a small root, 0.34 m at
    /// scale 1, and three flower heads on tips that stay collapsed unless the
    /// instance flowers. COLOR: r = flower head, g = height up the blade.</summary>
    private static ArrayMesh Tuft()
    {
        var rng = new System.Random(20260927);
        float R() => (float)rng.NextDouble();
        var v = new List<Vector3>();
        var uv = new List<Vector2>();
        var col = new List<Color>();
        var ix = new List<int>();
        var tips = new List<Vector3>();
        const int blades = 7;
        for (var b = 0; b < blades; b++)
        {
            var ang = (b + R() * 0.7f) / blades * Mathf.Tau;
            var dir = new Vector3(Mathf.Cos(ang), 0f, Mathf.Sin(ang));
            var root = dir * (0.015f + 0.06f * R());
            var height = 0.34f * (0.6f + 0.4f * R());
            var lean = height * (0.25f + 0.45f * R());
            var width = 0.045f + 0.02f * R();
            // the width runs across the lean, turned a little off true
            var tw = ang + Mathf.Pi / 2f + (R() - 0.5f) * 0.9f;
            var across = new Vector3(Mathf.Cos(tw), 0f, Mathf.Sin(tw));
            var first = v.Count;
            foreach (var t in new[] { 0f, 0.4f, 0.75f })
            {
                var c = root + dir * (lean * t * t) + Vector3.Up * (height * t);
                var half = width * 0.5f * Mathf.Pow(1f - t, 0.7f);
                v.Add(c - across * half); uv.Add(new Vector2(-1f, t)); col.Add(new Color(0f, t, 0f));
                v.Add(c + across * half); uv.Add(new Vector2(1f, t)); col.Add(new Color(0f, t, 0f));
            }
            var tip = root + dir * lean + Vector3.Up * height;
            v.Add(tip); uv.Add(new Vector2(0f, 1f)); col.Add(new Color(0f, 1f, 0f));
            tips.Add(tip);
            for (var s = 0; s < 2; s++)
            {
                var a = first + s * 2;
                ix.AddRange(new[] { a, a + 1, a + 3, a, a + 3, a + 2 });
            }
            ix.AddRange(new[] { first + 4, first + 5, first + 6 });
        }
        foreach (var b in new[] { 0, 2, 5 })
        {
            var first = v.Count;
            foreach (var (cx, cy) in new[] { (-1f, -1f), (1f, -1f), (1f, 1f), (-1f, 1f) })
            {
                v.Add(tips[b] + Vector3.Up * 0.015f); uv.Add(new Vector2(cx, cy)); col.Add(new Color(1f, 1f, 0f));
            }
            ix.AddRange(new[] { first, first + 1, first + 2, first, first + 2, first + 3 });
        }
        var arrays = new Godot.Collections.Array();
        arrays.Resize((int)Mesh.ArrayType.Max);
        arrays[(int)Mesh.ArrayType.Vertex] = v.ToArray();
        arrays[(int)Mesh.ArrayType.Normal] = Enumerable.Repeat(Vector3.Up, v.Count).ToArray();
        arrays[(int)Mesh.ArrayType.TexUV] = uv.ToArray();
        arrays[(int)Mesh.ArrayType.Color] = col.ToArray();
        arrays[(int)Mesh.ArrayType.Index] = ix.ToArray();
        var mesh = new ArrayMesh();
        mesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, arrays);
        return mesh;
    }

    private static ShaderMaterial Material()
    {
        // its globals exist by the first cell: `player_pos` from Foliage.Track
        // (every frame from the first), `wetness` from Weather.Build. (Listing
        // globals to check is editor-only in Godot: it errors in a game.)
        var m = new ShaderMaterial { Shader = new Shader { Code = Code } };
        m.SetShaderParameter("fade_from", FadeFrom);
        m.SetShaderParameter("fade_to", FadeTo);
        return m;
    }

    private const string Code = @"
shader_type spatial;
render_mode cull_disabled, specular_disabled;

global uniform vec3 player_pos;
global uniform float wetness;
global uniform float wind;      // Weather: 1 dry, 3 in full rain, gusts on top
global uniform vec4 shock;      // Impact: a blow's x, z, radius, age (s)
uniform float fade_from = 40.0;
uniform float fade_to = 58.0;

varying float v_t;
varying vec3 v_col;
varying vec3 v_up;
varying float v_flower;
varying float v_band;

void vertex() {
    float code = floor(INSTANCE_CUSTOM.a);
    float rnd = fract(INSTANCE_CUSTOM.a);
    float t = COLOR.g;
    bool head = COLOR.r > 0.5;
    mat3 m = mat3(MODEL_MATRIX);
    // world offsets into the instance's frame (a yaw times a uniform scale)
    mat3 to_model = transpose(m) / max(dot(m[0], m[0]), 1e-6);
    vec3 root = MODEL_MATRIX[3].xyz;
    vec3 off = vec3(0.0);
    // a flower: a square on a blade's tip, facing the camera
    if (head) off += (INV_VIEW_MATRIX[0].xyz * UV.x + INV_VIEW_MATRIX[1].xyz * UV.y) * 0.02;
    // wind: a slow gust rolling across the field, a quick flutter per tuft, and a narrow
    // band of hard gust (~10 m wide, 5.5 m/s, its front wavering) running downwind every
    // ~19 s -- the blades bow and flash pale, the wind made visible
    vec2 wd = vec2(0.87, 0.49);
    float gust = sin(TIME * 0.8 + dot(root.xz, wd) * 0.15) * 0.5 + 0.5;
    float flutter = sin(TIME * 2.6 + rnd * 6.283 + root.x * 0.9);
    float waver = sin(dot(root.xz, vec2(-wd.y, wd.x)) * 0.05) * 1.5;
    float band = pow(max(sin(dot(root.xz, wd) * 0.06 - TIME * 0.33 + waver), 0.0), 14.0) * clamp(wind * 0.5, 0.35, 1.5);
    vec2 sway = wd * (0.06 * gust + 0.02 * flutter + 0.13 * band);
    // the player wades through: it parts and bends down round the feet
    vec3 away = root - player_pos;
    float pd = length(away.xz);
    float push = (1.0 - smoothstep(0.3, 1.0, pd)) * (1.0 - smoothstep(0.8, 2.2, abs(away.y)));
    vec2 pdir = pd > 0.001 ? away.xz / pd : wd;
    // a blow (Impact: the dive): flattened out to its radius and a ring running out past
    // it, both springing back in about a second
    vec2 sd = root.xz - shock.xy;
    float sl = length(sd);
    float ring = exp(-pow((sl - min(shock.w * 9.0, shock.z * 1.8)) * 1.3, 2.0)) * exp(-shock.w * 2.5);
    float flat_ = (1.0 - smoothstep(shock.z * 0.55, shock.z * 1.1, sl)) * exp(-shock.w * 1.5);
    float sk = max(ring, flat_) * step(shock.w, 3.0);
    vec2 sdir = sl > 0.001 ? sd / sl : wd;
    off += (vec3(sway.x, 0.0, sway.y) + vec3(pdir.x * 0.3, -0.16, pdir.y * 0.3) * push
            + vec3(sdir.x * 0.34, -0.22, sdir.y * 0.34) * sk) * t * t;
    v_band = band;
    VERTEX += to_model * off;
    if (head && code < 0.5) VERTEX = vec3(0.0);
    // far off it sinks into the ground it grew from
    VERTEX *= 1.0 - smoothstep(fade_from, fade_to, length(root - CAMERA_POSITION_WORLD));
    v_t = t;
    v_col = INSTANCE_CUSTOM.rgb;
    v_up = normalize(m[1]);
    v_flower = head ? code : 0.0;
}

vec3 petal(float k) {
    if (k < 1.5) return vec3(0.78, 0.78, 0.72);
    if (k < 2.5) return vec3(0.82, 0.58, 0.08);
    if (k < 3.5) return vec3(0.36, 0.20, 0.62);
    return vec3(0.80, 0.30, 0.42);
}

void fragment() {
    // root to tip in four flat tones, as the texture ramps are painted
    float tq = min(floor(v_t * 4.0), 3.0) / 3.0;
    vec3 c = v_col * mix(0.55, 1.45, tq) + vec3(0.012, 0.009, 0.0) * tq;
    c *= 1.0 + 0.14 * v_band * tq;   // a gust turns the blades' pale side up
    if (v_flower > 0.5) c = petal(v_flower);
    ALBEDO = c * (1.0 - 0.3 * wetness);
    ROUGHNESS = mix(0.9, 0.45, wetness);
    AO = mix(0.5, 1.0, tq);
    AO_LIGHT_AFFECT = 0.3;
    BACKLIGHT = c * 0.3 * tq;
    // lit as the ground is, not as a thin card: blades seen from behind
    // would otherwise flip dark
    NORMAL = normalize((VIEW_MATRIX * vec4(v_up, 0.0)).xyz);
}
";
}
