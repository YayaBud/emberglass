using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The world's lines and spots as an editable scene, `res://world/layout.tscn`
/// (implementation_plan Phase 3). Two frames:
/// - `World` (world metres): the trails (one Path3D per polyline, in
///   <see cref="WorldGen.Trails"/> order), the village road, the dells, the oasis, the
///   pond and the ice pools (Marker3D; meta `r`, `rx`/`rz`).
/// - `City`: its transform IS the city (<see cref="CityPlan.Centre"/>, R, F). Children are
///   in plan metres, local (x, 0, -y): the wall ring, the sea, the canal, the districts,
///   the rivers (meta `level`, `hw`), the falls (meta `dir`, `top`, `foot`, `width`), the
///   highland (a marker's height IS the hill's), the isle and the roads (meta `kind`,
///   `hw`, `loop`, `slope`).
/// Loaded before anything reads WorldGen or CityPlan; <see cref="CityPlan.Rebuild"/> and
/// <see cref="WorldGen.Rebuild"/> then re-derive roads, squares, stairs and height caches.
/// ponytail: widths and levels are C# consts and stay in code. Index-bound meaning stays
/// by index: move points freely, but adding or removing a wall point shifts the gates
/// (vertices 0, 7, 17), the harbour's open edges (22-28) and the wall stairs; adding a
/// trail point shifts the later trail segments the sites refer to.
/// </summary>
public static class Layout
{
    public const string Path = "res://world/layout.tscn";

    public static bool Exists => FileAccess.FileExists(Path);

    /// <summary>Where the player starts (`World/Spawn`).</summary>
    public static Vector2 Spawn { get; private set; }

    /// <summary>Called first in World._Ready. Writes the layout from the code's constants
    /// (under --bake if there is none, or --rebake=layout) and checks it; else loads it.</summary>
    public static void Boot(Node3D? node = null)
    {
        var args = OS.GetCmdlineUserArgs();
        var rebake = args.Any(a => a.StartsWith("--rebake=") && a[9..].Split(',').Any(s => s is "layout" or "all"));
        if ((args.Contains("--bake") && !Exists) || rebake)
        {
            if (Exists) Backup();
            Write();
            Check();
        }
        else if (node != null)
        {
            var t0 = Time.GetTicksMsec();
            Apply(node);
            GD.Print($"layout: from world.tscn applied in {Time.GetTicksMsec() - t0} ms");
        }
        else if (Exists)
        {
            var t0 = Time.GetTicksMsec();
            var root = GD.Load<PackedScene>(Path).Instantiate<Node3D>();
            Upgrade(root);
            Apply(root);
            root.Free();
            GD.Print($"layout: {Path} applied in {Time.GetTicksMsec() - t0} ms");
        }
        // what was sculpted in Terrain3D, on top of the layout's ground
        TerrainEdit.Load();
    }

    // ------------------------------------------------------------------ write

    private static Vector3 Local(Vector2 p, float y = 0f) => new(p.X, y, -p.Y);
    private static Vector2 Plan(Vector3 l) => new(l.X, -l.Z);

    private static Path3D Line(string name, IEnumerable<Vector3> pts)
    {
        var c = new Curve3D();
        foreach (var p in pts) c.AddPoint(p);
        return new Path3D { Name = name, Curve = c };
    }

    private static Path3D PlanLine(string name, Vector2[] pts, bool closed = false)
    {
        var l = Line(name, pts.Select(p => Local(p)));
        if (closed) l.SetMeta("closed", true);
        return l;
    }

    private static Node3D Group(Node3D parent, string name)
    {
        var g = new Node3D { Name = name };
        parent.AddChild(g);
        return g;
    }

    private static Vector3 Ground(Vector2 p) => new(p.X, WorldGen.Height(p.X, p.Y), p.Y);

    /// <summary>The trails as polylines again: consecutive segments that join are one line.</summary>
    private static List<List<Vector2>> Chains(Vector4[] segs)
    {
        var chains = new List<List<Vector2>>();
        foreach (var s in segs)
        {
            Vector2 a = new(s.X, s.Y), b = new(s.Z, s.W);
            if (chains.Count > 0 && chains[^1][^1] == a) chains[^1].Add(b);
            else chains.Add(new List<Vector2> { a, b });
        }
        return chains;
    }

    public static void Write()
    {
        var root = new Node3D { Name = "Layout" };
        var world = Group(root, "World");
        var trails = Group(world, "Trails");
        var ci = 0;
        foreach (var ch in Chains(WorldGen.Trails))
            trails.AddChild(Line($"Trail_{ci++}", ch.Select(p => Ground(p) + Vector3.Up * 0.3f)));
        world.AddChild(Line("VillageRoad", new[] { Ground(WorldGen.PathFrom), Ground(WorldGen.PathTo) }));
        var dells = Group(world, "Dells");
        for (var i = 0; i < WorldGen.Dells.Length; i++)
            dells.AddChild(Marker($"Dell_{i}", Ground(WorldGen.Dells[i].C), ("r", WorldGen.Dells[i].R)));
        var oases = Group(world, "Oases");
        for (var i = 0; i < WorldGen.Oases.Length; i++)
            oases.AddChild(Marker($"Oasis_{i}", Ground(WorldGen.Oases[i].C), ("r", WorldGen.Oases[i].R)));
        world.AddChild(Marker("Pond", Ground(WorldGen.PondCentre)));
        AddBiomes(world);
        world.AddChild(Marker("Spawn", Ground(Spawn)));
        var ice = Group(world, "IcePools");
        for (var i = 0; i < WorldGen.IcePools.Length; i++)
        {
            var v = WorldGen.IcePools[i];
            ice.AddChild(Marker($"Ice_{i}", Ground(new Vector2(v.X, v.Y)), ("rx", v.Z), ("rz", v.W)));
        }

        var city = new Node3D
        {
            Name = "City",
            Transform = new Transform3D(new Basis(new Vector3(CityPlan.R.X, 0f, CityPlan.R.Y), Vector3.Up, new Vector3(-CityPlan.F.X, 0f, -CityPlan.F.Y)),
                                        new Vector3(CityPlan.Centre.X, CityPlan.BaseLevel(), CityPlan.Centre.Y)),
        };
        root.AddChild(city);
        city.AddChild(PlanLine("Wall", CityPlan.Encl, closed: true));
        city.AddChild(PlanLine("Sea", CityPlan.SeaPoly, closed: true));
        city.AddChild(PlanLine("Canal", CityPlan.Canal));
        var q = Group(city, "Districts");
        q.AddChild(PlanLine("Citadel", CityPlan.CitadelPoly, true));
        q.AddChild(PlanLine("Noble", CityPlan.NoblePoly, true));
        q.AddChild(PlanLine("Market", CityPlan.MarketPoly, true));
        q.AddChild(PlanLine("OldCity", CityPlan.OldCityPoly, true));
        q.AddChild(PlanLine("Farms", CityPlan.FarmPoly, true));
        var rivers = Group(city, "Rivers");
        for (var i = 0; i < CityPlan.Reaches.Length; i++)
        {
            var (line, lv, hw) = CityPlan.Reaches[i];
            var r = PlanLine($"River_{i}", line);
            r.SetMeta("level", lv);
            r.SetMeta("hw", hw);
            rivers.AddChild(r);
        }
        var falls = Group(city, "Falls");
        foreach (var (name, at, dir, top, foot, width) in CityPlan.Falls)
            falls.AddChild(Marker(name.Replace(' ', '_'), Local(at, foot), ("name", name), ("dir", dir), ("top", top), ("foot", foot), ("width", width)));
        var hills = Group(city, "Highland");
        for (var i = 0; i < CityPlan.Highland.Length; i++)
            hills.AddChild(Marker($"Hill_{i}", Local(CityPlan.Highland[i].P, CityPlan.Highland[i].H)));
        city.AddChild(Marker("Isle", Local(CityPlan.Isle)));
        var roads = Group(city, "Roads");
        for (var i = 0; i < CityPlan.Net.Length; i++)
        {
            var (name, kind, hw, loop, slope, pts) = CityPlan.Net[i];
            var r = PlanLine($"Road_{i}", pts);
            foreach (var (k, v) in new (string, Variant)[] { ("name", name), ("kind", kind), ("hw", hw), ("loop", loop), ("slope", slope) }) r.SetMeta(k, v);
            roads.AddChild(r);
        }

        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(Path.GetBaseDir()));
        Own(root, root);
        var ps = new PackedScene();
        var err = ps.Pack(root);
        if (err == Error.Ok) err = ResourceSaver.Save(ps, Path);
        GD.Print($"layout: wrote {Path} ({ci} trails, {CityPlan.Net.Length} roads, {CityPlan.Encl.Length} wall points): {err}");
        root.Free();
    }

    /// <summary>The biomes (<see cref="Biomes.All"/>): a marker per region at its centre, with its
    /// reach and landform as fields. Moving one moves where its ground, colour, plants,
    /// snow and weather are -- and re-shapes the generated hills under any sculpting.</summary>
    private static void AddBiomes(Node3D world)
    {
        var g = Group(world, "Biomes");
        foreach (var r in Biomes.All)
            g.AddChild(Marker(r.Kind.ToString(), Ground(r.Centre), ("radius", r.Radius), ("base", r.Base), ("relief", r.Relief), ("grain", r.Grain)));
    }

    private static Marker3D Marker(string name, Vector3 at, params (string K, Variant V)[] meta)
    {
        var m = new Marker3D { Name = name, Position = at };
        foreach (var (k, v) in meta) m.SetMeta(k, v);
        return m;
    }

    private static void Own(Node n, Node owner)
    {
        foreach (var c in n.GetChildren()) { c.Owner = owner; Own(c, owner); }
    }

    private static void Backup()
    {
        var dir = ProjectSettings.GlobalizePath("res://").PathJoin($"../scratch/bake_backup/{Time.GetDateStringFromSystem()}");
        DirAccess.MakeDirRecursiveAbsolute(dir);
        DirAccess.CopyAbsolute(ProjectSettings.GlobalizePath(Path), dir.PathJoin("layout.tscn"));
    }

    /// <summary>A layout written before a group existed gets it added from the code, and is
    /// saved again with everything else in it as it was (Phase 5: the biomes).</summary>
    private static void Upgrade(Node3D root)
    {
        var world = root.GetNode<Node3D>("World");
        if (world.HasNode("Biomes") && world.HasNode("Spawn")) return;
        var before = Biomes.All.ToArray();
        if (!world.HasNode("Biomes")) AddBiomes(world);
        if (!world.HasNode("Spawn")) world.AddChild(Marker("Spawn", Ground(Spawn)));
        Own(root, root);
        var ps = new PackedScene();
        var err = ps.Pack(root);
        if (err == Error.Ok) { Backup(); err = ResourceSaver.Save(ps, Path); }
        Apply(root);
        var same = before.Zip(Biomes.All).All(p => p.First == p.Second);
        GD.Print($"layout: upgraded {Path} (biomes, spawn) ({err}); biomes read back identical: {(same ? "PASS" : "FAIL")}, spawn {Spawn}");
    }

    // ------------------------------------------------------------------ read

    /// <summary>A path's points in its parent's space (a moved Path3D node moves its points).</summary>
    private static List<Vector3> Points(Path3D p)
    {
        var c = p.Curve;
        var l = new List<Vector3>();
        for (var i = 0; i < (c?.PointCount ?? 0); i++) l.Add(p.Transform * c!.GetPointPosition(i));
        return l;
    }

    private static Vector2[] PlanPts(Node3D city, string path) => Points(city.GetNode<Path3D>(path)).Select(Plan).ToArray();
    private static Vector2 Xz(Vector3 v) => new(v.X, v.Z);
    private static T M<[MustBeVariant] T>(Node n, string k, T d) => n.HasMeta(k) ? n.GetMeta(k).As<T>() : d;
    private static IEnumerable<T> Kids<T>(Node n, string group) where T : Node => n.GetNode(group).GetChildren().OfType<T>();

    /// <summary>Sets WorldGen's and CityPlan's data from a layout scene (instanced, not in the tree) and re-derives.</summary>
    public static void Apply(Node3D root)
    {
        var world = root.GetNode<Node3D>("World");
        var segs = new List<Vector4>();
        foreach (var t in Kids<Path3D>(world, "Trails"))
        {
            var pts = Points(t).Select(Xz).ToList();
            for (var i = 0; i + 1 < pts.Count; i++) segs.Add(new Vector4(pts[i].X, pts[i].Y, pts[i + 1].X, pts[i + 1].Y));
        }
        WorldGen.Trails = segs.ToArray();
        var road = Points(world.GetNode<Path3D>("VillageRoad"));
        (WorldGen.PathFrom, WorldGen.PathTo) = (Xz(road[0]), Xz(road[^1]));
        WorldGen.Dells = Kids<Marker3D>(world, "Dells").Select(m => (Xz(m.Position), M(m, "r", 40f))).ToArray();
        WorldGen.Oases = Kids<Marker3D>(world, "Oases").Select(m => (Xz(m.Position), M(m, "r", 8f))).ToArray();
        WorldGen.PondCentre = Xz(world.GetNode<Marker3D>("Pond").Position);
        if (world.HasNode("Biomes"))
            foreach (var m in Kids<Marker3D>(world, "Biomes"))
            {
                var i = System.Array.FindIndex(Biomes.All, r => r.Kind.ToString() == m.Name.ToString());
                if (i < 0) continue;
                Biomes.All[i] = Biomes.All[i] with
                {
                    Centre = Xz(m.Position), Radius = M(m, "radius", Biomes.All[i].Radius), Base = M(m, "base", Biomes.All[i].Base),
                    Relief = M(m, "relief", Biomes.All[i].Relief), Grain = M(m, "grain", Biomes.All[i].Grain),
                };
            }
        Spawn = world.HasNode("Spawn") ? Xz(world.GetNode<Marker3D>("Spawn").Position) : Vector2.Zero;
        WorldGen.IcePools = Kids<Marker3D>(world, "IcePools").Select(m => new Vector4(m.Position.X, m.Position.Z, M(m, "rx", 5f), M(m, "rz", 3f))).ToArray();

        var city = root.GetNode<Node3D>("City");
        var b = city.Transform.Basis;
        CityPlan.Centre = Xz(city.Transform.Origin);
        // exact when already unit length: normalising changed the last bit, and 13 of 57k
        // height samples lying on a district edge flipped terrace (layoutcheck, 2026-10-01)
        static Vector2 Unit(Vector2 v) => Mathf.Abs(v.Length() - 1f) < 1e-5f ? v : v.Normalized();
        CityPlan.R = Unit(Xz(b.X));
        CityPlan.F = -Unit(Xz(b.Z));
        CityPlan.Encl = PlanPts(city, "Wall");
        CityPlan.SeaPoly = PlanPts(city, "Sea");
        CityPlan.Canal = PlanPts(city, "Canal");
        CityPlan.CitadelPoly = PlanPts(city, "Districts/Citadel");
        CityPlan.NoblePoly = PlanPts(city, "Districts/Noble");
        CityPlan.MarketPoly = PlanPts(city, "Districts/Market");
        CityPlan.OldCityPoly = PlanPts(city, "Districts/OldCity");
        CityPlan.FarmPoly = PlanPts(city, "Districts/Farms");
        CityPlan.Reaches = Kids<Path3D>(city, "Rivers").Select(r => (Points(r).Select(Plan).ToArray(), M(r, "level", 2f), M(r, "hw", 5f))).ToArray();
        CityPlan.Falls = Kids<Marker3D>(city, "Falls").Select(m => (M(m, "name", m.Name.ToString()), Plan(m.Position), M(m, "dir", Vector2.Down),
                                                                   M(m, "top", 5f), M(m, "foot", 0f), M(m, "width", 10f))).ToArray();
        CityPlan.Highland = Kids<Marker3D>(city, "Highland").Select(m => (Plan(m.Position), m.Position.Y)).ToArray();
        CityPlan.Isle = Plan(city.GetNode<Marker3D>("Isle").Position);
        CityPlan.Net = Kids<Path3D>(city, "Roads").Select(r => (M(r, "name", r.Name.ToString()), M(r, "kind", "street"), M(r, "hw", 3f),
                                                                M(r, "loop", false), M(r, "slope", 0.2f), Points(r).Select(Plan).ToArray())).ToArray();
        WorldGen.Rebuild();
        CityPlan.Rebuild();
    }

    // ------------------------------------------------------------------ check

    /// <summary>What the layout decides, sampled: ground heights (the map every 8 m, the city
    /// disc every 4 m), trail and village-road distances, and every road's resampled points
    /// and levels, squares and wall stairs.</summary>
    private sealed class Sample
    {
        public readonly List<float> H = new(), D = new(), Roads = new();
        public int RoadCount, Squares, Stairs;
    }

    private static Sample Take()
    {
        var s = new Sample();
        for (var x = -512f; x <= 512f; x += 8f)
        for (var z = -512f; z <= 512f; z += 8f)
        {
            s.H.Add(WorldGen.Height(x, z));
            s.D.Add(Mathf.Min(WorldGen.TrailDistance(x, z), 50f));
            s.D.Add(Mathf.Min(WorldGen.PathDistance(x, z), 50f));
        }
        for (var u = -400f; u <= 400f; u += 4f)
        for (var v = -400f; v <= 400f; v += 4f)
        {
            var w = CityPlan.ToWorld(new Vector2(u, v));
            s.H.Add(WorldGen.Height(w.X, w.Y));
        }
        foreach (var rd in CityPlan.Roads)
        {
            foreach (var p in rd.P) { s.Roads.Add(p.X); s.Roads.Add(p.Y); }
            s.Roads.AddRange(rd.L);
        }
        (s.RoadCount, s.Squares, s.Stairs) = (CityPlan.Roads.Count, CityPlan.Squares.Count, CityPlan.WallStairs.Count);
        return s;
    }

    private static string Diff(Sample a, Sample b, out bool ok)
    {
        static (float Max, int Over) Err(List<float> x, List<float> y)
        {
            if (x.Count != y.Count) return (float.PositiveInfinity, -1);
            var max = 0f;
            var over = 0;
            for (var i = 0; i < x.Count; i++)
            {
                var e = Mathf.Abs(x[i] - y[i]);
                max = Mathf.Max(max, e);
                if (e > 1e-3f) over++;
            }
            return (max, over);
        }
        var (h, ho) = Err(a.H, b.H);
        var (d, dO) = Err(a.D, b.D);
        var (r, ro) = Err(a.Roads, b.Roads);
        ok = ho == 0 && dO == 0 && ro == 0 && a.RoadCount == b.RoadCount && a.Squares == b.Squares && a.Stairs == b.Stairs;
        return $"{a.H.Count} heights max err {h:G3} m ({ho} over 1 mm), {a.D.Count} path distances {d:G3} ({dO}), "
               + $"roads {a.RoadCount}/{b.RoadCount} points+levels {r:G3} ({ro}), squares {a.Squares}/{b.Squares}, wall stairs {a.Stairs}/{b.Stairs}";
    }

    /// <summary>Right after Write: the layout read back must decide the same world as the
    /// constants; then three edits (a canal bend, a road bend, a trail bend) must move the
    /// ground and the road with them; then the layout as written is applied again.</summary>
    public static void Check()
    {
        var t0 = Time.GetTicksMsec();
        var before = Take();
        var root = ResourceLoader.Load<PackedScene>(Path, "", ResourceLoader.CacheMode.Ignore).Instantiate<Node3D>();
        Apply(root);
        var line = Diff(before, Take(), out var ok);
        GD.Print($"layoutcheck identity: {line} -> {(ok ? "PASS" : "FAIL")}");

        // the edits, as the editor would make them: move one point of each
        var city = root.GetNode<Node3D>("City");
        var canal = city.GetNode<Path3D>("Canal");
        var c3 = canal.Curve.GetPointPosition(3);
        var oldC = Plan(c3);
        var bank = CityPlan.ToWorld(oldC + new Vector2(0f, 14f));
        var bed0 = WorldGen.Height(CityPlan.ToWorld(oldC).X, CityPlan.ToWorld(oldC).Y);
        var bank0 = WorldGen.Height(bank.X, bank.Y);
        canal.Curve.SetPointPosition(3, c3 + new Vector3(0f, 0f, -14f));   // plan y + 14

        var mill = city.GetNode("Roads").GetChildren().OfType<Path3D>().First(r => (string)r.GetMeta("name") == "Mill lane");
        var m1 = mill.Curve.GetPointPosition(1);
        var oldM = Plan(m1);
        mill.Curve.SetPointPosition(1, m1 + new Vector3(10f, 0f, 0f));   // plan x + 10
        var clear0 = CityPlan.RoadClear(oldM + new Vector2(10f, 0f));

        var trail = root.GetNode("World/Trails").GetChild<Path3D>(0);
        var t2 = trail.Curve.GetPointPosition(2);
        trail.Curve.SetPointPosition(2, t2 + new Vector3(12f, 0f, 0f));
        var trail0 = WorldGen.TrailDistance(t2.X + 12f, t2.Z);

        Apply(root);
        var bed1 = WorldGen.Height(CityPlan.ToWorld(oldC).X, CityPlan.ToWorld(oldC).Y);
        var bank1 = WorldGen.Height(bank.X, bank.Y);
        var clear1 = CityPlan.RoadClear(oldM + new Vector2(10f, 0f));
        var trail1 = WorldGen.TrailDistance(t2.X + 12f, t2.Z);
        var edits = bank1 < bank0 - 1f && bed1 > bed0 + 1f && clear1 < 0f && clear0 > 0f && trail1 < 0.01f && trail0 > 5f;
        GD.Print($"layoutcheck edits: canal point 3 moved 14 m -> ground there {bank0:F2} -> {bank1:F2} m, at the old bed {bed0:F2} -> {bed1:F2} m; "
                 + $"Mill lane point 1 moved 10 m -> road clearance there {clear0:F2} -> {clear1:F2} m; "
                 + $"trail 0 point 2 moved 12 m -> trail distance there {trail0:F2} -> {trail1:F2} m -> {(edits ? "PASS" : "FAIL")}");
        root.Free();

        root = ResourceLoader.Load<PackedScene>(Path, "", ResourceLoader.CacheMode.Ignore).Instantiate<Node3D>();
        Apply(root);
        root.Free();
        line = Diff(before, Take(), out ok);
        GD.Print($"layoutcheck restored: {line} -> {(ok ? "PASS" : "FAIL")} ({Time.GetTicksMsec() - t0} ms)");
    }
}
