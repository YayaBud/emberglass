using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The village outskirts at the spawn: the user's reference shot, rebuilt from
/// nanobanna's exported GLBs along the road <see cref="WorldGen"/> paints.
///
/// Layout is authored in PATH SPACE, not world space: world XZ = a*F + b*R,
/// where F runs up the road into the screen and R is screen-right. The camera's
/// yaw is locked, so every placement reads the same way every time and a table
/// of (a, b) is the whole map. a = 0 is the spawn; the camera sits near a = -20.
///
/// Composition follows the reference and the four bands of Law 7: dark near
/// occluders at the frame edges (a &lt; 0), the lit road and lamps in the play
/// band, houses on the left and trees on the right in the mid band, the keep in
/// the haze at the far end.
///
/// The GLBs lost their emission on export, but the material names survived, so
/// windows and flames are re-lit here by name.
/// </summary>
public partial class Village : Node3D
{
    private const string Dir = "res://assets/models/village/";
    private const string KitDir = "res://assets/models/kit/";

    /// <summary>The rebuilt, pixel-textured houses in place of the old
    /// ones, same spots, and 3D woods for the sprite trees. ON by default since
    /// 2026-09-23 (user: a normal launch showed none of it -- "nothing wired
    /// up"); `--nokit` brings back the old village for the lighting study.</summary>
    public static bool UseKit = true;

    /// <summary>`--noproxy`: kit meshes cast their own shadows (diagnostic).</summary>
    public static bool NoProxy;

    private static readonly Vector3 F = new(-0.7071f, 0f, -0.7071f);
    private static readonly Vector3 R = new(0.7071f, 0f, -0.7071f);

    /// <summary>How a piece is turned. Road: front toward the road and the
    /// camera. Along: long axis along the road (fences). Turn: explicit yaw.</summary>
    private enum Face { Road, Along, Turn }

    private readonly record struct Piece(string Model, float A, float B,
                                         Face Face = Face.Road, float Yaw = 0f,
                                         float Scale = 1f);

    private static readonly Piece[] Layout =
    {
        // ---- near occluders, framing the bottom corners ---------------------
        // The frame's bottom edge meets the ground near a = -12, and the frame
        // is only ~6 u either side of centre there, so an occluder has to sit
        // close in to be seen at all. The first pass put these at b = +/-12 and
        // none of them was in the picture.
        new("tree_large", -5f, -8.5f, Face.Turn, 20f, 1.1f),
        new("bush", -6f, 6.8f, Face.Turn, 0f, 1.9f),
        new("bush", -3f, -6.2f, Face.Turn, 70f, 1.5f),
        new("tree_small", -4f, 9.0f, Face.Turn, 70f),

        // ---- houses, left of the road ---------------------------------------
        new("bld_cottage", 9f, -9.5f),
        new("bld_townhouse", 22f, -10.5f),
        new("bld_cottage", 36f, -9.5f, Face.Road, 0f, 0.95f),
        new("bld_townhouse", 52f, -11f),
        new("bld_cottage", 47f, 12f),

        // ---- trees, mostly right of the road --------------------------------
        new("tree_large", 6f, 10.5f, Face.Turn, 140f),
        new("tree_small", 15f, 7.2f, Face.Turn, 10f),
        new("tree_group", 28f, 12f, Face.Turn, 200f),
        new("tree_small", 38f, 8f, Face.Turn, 95f),
        new("tree_group", 17f, -17f, Face.Turn, 30f),
        new("tree_large", 44f, -18f, Face.Turn, 300f),
        new("tree_group", 62f, 9f, Face.Turn, 120f),
        new("tree_large", 66f, -7f, Face.Turn, 250f),

        // ---- the keep, in the haze at the end of the road -------------------
        new("monument_keep", 92f, 16f, Face.Turn, 45f, 1.4f),

        // ---- undergrowth along the fences -----------------------------------
        new("bush", 4f, -4.8f, Face.Turn, 30f),
        new("flowers", 12f, -4.9f, Face.Turn, 0f),
        new("bush", 19f, 4.9f, Face.Turn, 80f),
        new("flowers", 25f, 5.0f, Face.Turn, 45f),
        new("bush", 31f, -4.9f, Face.Turn, 160f),
        new("flowers", 42f, -5.0f, Face.Turn, 90f),
        new("grass_patch", 2f, 6.5f, Face.Turn, 0f),
        new("grass_patch", 27f, -6.5f, Face.Turn, 60f),
        new("grass_patch", -3f, -6f, Face.Turn, 120f),
    };

    /// <summary>Lamp posts, alternating sides, just inside the fence line.</summary>
    private static readonly (float A, float B)[] Lamps =
    {
        (4f, -2.8f), (15f, 2.8f), (26f, -2.8f), (37f, 2.8f), (48f, -2.8f),
    };

    /// <summary>Puddles on the road, path space (a, b, size m). One 2-3 m
    /// in FRONT of every lamp (camera side, a smaller): still water mirrors a
    /// lamp only where it lies between the lamp and the eye. A few between.</summary>
    private static readonly (float A, float B, float Size)[] PuddleSpots =
    {
        (1.6f, -1.8f, 2.2f), (12.4f, 1.6f, 1.9f), (23.5f, -1.5f, 2.6f), (34.2f, 1.7f, 2.1f), (45.4f, -1.6f, 2.3f),
        (8f, 0.3f, 1.4f), (18.5f, -0.4f, 2.4f), (29.5f, 0.6f, 1.5f), (40f, -0.2f, 1.8f),
    };

    /// <summary>Pots, jars, crates, barrels and bales in the yards, path space
    /// (a, b, asset, yaw): by the house corners, behind the fences.</summary>
    private static readonly (float A, float B, string Asset, float Yaw)[] YardThings =
    {
        (2.2f, -5.4f, "Pot", 0.3f), (4.6f, -6.6f, "Barrel", 0f), (5.3f, -7.6f, "Pot", 1.2f),
        (13.6f, -6.8f, "Crate", 0.2f), (14.5f, -7.9f, "Crate", 0.9f), (17.4f, -7.0f, "Pot", 2f), (17.9f, -6.2f, "Jar", 0.4f),
        (26.6f, -7.1f, "Barrel", 0.5f), (27.4f, -6.4f, "Barrel", 1.4f), (31.2f, -6.8f, "HayBale", 0.15f),
        (40.6f, -6.9f, "Pot", 0.7f), (41.3f, -7.7f, "Pot", 2.4f), (40.0f, -7.9f, "Jar", 1f),
        (47.8f, -7.9f, "Barrel", 0.2f), (56.8f, -8.0f, "Crate", 0.6f),
        (43.0f, 8.4f, "HayBale", -0.2f), (51.2f, 8.6f, "Crate", 0.3f), (50.6f, 9.5f, "Pot", 1.1f),
    };

    /// <summary>Road puddles on (default). World clears it under `--light=`
    /// and `--off=wet`.</summary>
    public static bool Puddles = true;

    /// <summary>The fence runs, along both sides of the road, with gaps.</summary>
    private const float FenceB = 3.9f, FenceFrom = 1f, FenceTo = 46f, FenceStep = 2.95f;

    /// <summary>Shadow-casting lamps allowed at once. An omni shadow is a
    /// six-face cubemap; this is the ceiling, not a target.</summary>
    private const int ShadowBudget = 2;

    private readonly Dictionary<string, PackedScene> _scenes = new();
    private readonly Dictionary<string, Material?> _glow = new();
    private readonly List<LampLight> _lamps = new();
    /// <summary>Fence segment centres (a, b), for the animals (Folk).</summary>
    private readonly List<(float A, float B)> _fences = new();
    private Node3D _player = null!;
    private int _tick;

    public int Pieces { get; private set; }

    private static Vector3 World(float a, float b) => F * a + R * b;

    /// <summary>Villagers on the road and at the roadside, dogs and cats about
    /// them, hens in the cottage yards (user, 2026-09-26: "npcs fill the world
    /// dogs cats other animals").</summary>
    public void Folk(Node3D player, CameraRig cam)
    {
        Vector2 W(float a, float b) { var w = World(a, b); return new Vector2(w.X, w.Z); }
        var folk = new Townsfolk { Name = "VillageFolk" };
        AddChild(folk);
        folk.Bind(player, cam, 5151);
        var pts = new List<Vector2>();
        var ys = new List<float>();
        for (var a = -8f; a <= 62f; a += 2f)
        {
            var p = W(a, 0f);
            pts.Add(p);
            ys.Add(WorldGen.Height(p.X, p.Y));
        }
        var road = new Townsfolk.Route { P = pts.ToArray(), Y = ys.ToArray(), Half = 1.7f };
        foreach (var who in new[] { "farmer", "farmer", "market_woman", "child", "child", "old_man", "young_woman", "monk" })
            folk.Walker(who, road);
        foreach (var (who, a, b) in new[] { ("market_woman", 10f, -3.6f), ("farmer", 23f, -3.6f), ("old_man", 36.5f, -3.4f), ("young_woman", 47f, 3.6f), ("child", 48f, 3.2f) })
        {
            var p = W(a, b);
            folk.Stander(who, p, WorldGen.Height(p.X, p.Y), W(a, 0f));
        }
        folk.Finish();

        var pets = new Fauna
        {
            Name = "VillagePets",
            Keep = p => { var a = p.X * F.X + p.Y * F.Z; var b = p.X * R.X + p.Y * R.Z; var w = World(Mathf.Clamp(a, -6f, 60f), Mathf.Clamp(b, -9f, 9f)); return new Vector2(w.X, w.Z); },
        };
        AddChild(pets);
        pets.Bind(player, 6161);
        pets.Add(new Fauna.Kind("dog", 1.2f, 7.5f, 0f, 9f, 0.3f, 0.3f, "sit", Tame: true, Pet: true), new[] { W(6f, 1f), W(40f, -1.5f) });
        pets.Add(new Fauna.Kind("cat", 0.6f, 6f, 2.6f, 5f, 0.17f, 0.2f, "sit", Skittish: true, Pet: true), new[] { W(12f, -4f) });
        pets.Add(new Fauna.Kind("cat_black", 0.6f, 6f, 2.6f, 5f, 0.17f, 0.2f, "sit", Skittish: true, Pet: true), new[] { W(33f, 4f) });
        pets.Add(new Fauna.Kind("hen", 0.5f, 3.5f, 2.2f, 4f, 0.12f, 0.15f, "peck"), new[] { W(8f, -6.5f), W(10f, -7f), W(35f, -6.5f), W(37f, -7f) });
        pets.Add(new Fauna.Kind("hen_white", 0.5f, 3.5f, 2.2f, 4f, 0.12f, 0.15f, "peck"), new[] { W(9f, -7.5f), W(36f, -7.8f) });
        foreach (var (a, b) in Lamps) pets.Block(W(a, b), 0.35f);
        // the fences keep the hens in the yards (wood_fence.glb is 2.95 m long)
        foreach (var (a, b) in _fences) pets.BlockLine(W(a - 1.47f, b), W(a + 1.47f, b), 0.2f);
        foreach (var pc in Layout)
            if (pc.Model.StartsWith("bld_")) pets.Block(W(pc.A, pc.B), 4.2f);
            else if (pc.Model.StartsWith("tree")) pets.Block(W(pc.A, pc.B), 0.8f);
        // the yard's pots and crates are walked round too
        foreach (var (c, r) in Breakables.Footprints()) pets.Block(c, r);
        GD.Print($"village: {folk.Count} people, {pets.Count} animals");
    }

    /// <summary>The outskirts, where the camera drops to the low angle: the
    /// village stretch of the road, in path space. Entered through an inner box
    /// and left through an outer one 3 u larger, so walking along the edge
    /// cannot flip the camera back and forth.</summary>
    public static bool WantsLow(Vector3 p, bool low)
    {
        var a = p.X * F.X + p.Z * F.Z;
        var b = p.X * R.X + p.Z * R.Z;
        var m = low ? 3f : 0f;
        return a > -30f - m && a < 64f + m && Mathf.Abs(b) < 14f + m;
    }

    public void Build(Node3D player)
    {
        _player = player;

        foreach (var p in Layout)
            Place(p.Model, p.A, p.B, p.Face, p.Yaw, p.Scale);

        // Fences, one segment per step on each side, skipping every fifth so the
        // run reads as a real fence with gates and gaps rather than a wall.
        var i = 0;
        for (var a = FenceFrom; a <= FenceTo; a += FenceStep, i++)
        {
            if (i % 5 == 3) continue;
            Place("wood_fence", a, -FenceB, Face.Along, 0f, 1f);
            _fences.Add((a, -FenceB));
            if (i % 5 != 1)
            {
                Place("wood_fence", a + 1.3f, FenceB, Face.Along, 0f, 1f);
                _fences.Add((a + 1.3f, FenceB));
            }
        }

        foreach (var (a, b) in Lamps) Lamp(a, b);

        // things to break in the yards (Breakables), clear of the hens' spots, the fences
        // and each house's 4.2 m block
        foreach (var (a, b, asset, yaw) in YardThings)
        {
            var w = World(a, b);
            Breakables.Add(asset, new Vector2(w.X, w.Z), yaw);
        }

        // Standing water on the road under the lamps, so each lamp has a
        // reflection to throw (the user's test, 2026-09-23). Off under
        // --light=, which must keep reproducing the measured study frames.
        if (Puddles)
            foreach (var (a, b, size) in PuddleSpots)
                AddChild(Water.Puddle(new Vector2(World(a, b).X, World(a, b).Z), size));

        if (UseKit) Woods();
        GD.Print($"village: {Pieces} pieces, {_lamps.Count} lamps");
    }

    /// <summary>A street lamp with its flickering light, in path space; it
    /// joins the village's shadow budget. Also used by <see cref="WaterSite"/>.</summary>
    public LampLight Lamp(float a, float b)
    {
        var post = Place("street_lamp", a, b, Face.Road, 0f, 1f);
        var light = new LampLight { Name = "Flame", Position = new Vector3(0f, 3.0f, 0f) };
        post.AddChild(light);
        _lamps.Add(light);
        return light;
    }

    /// <summary>The village's trees as the references compose them (the
    /// placement study's items 1 and 4): dense groves carved by a clumping
    /// field, so there are thickets and glades rather than an even line;
    /// walls of forest behind the houses; a near band of big trees at the
    /// frame's edges, cropped and blurred; a treeline on the horizon. The road,
    /// fences, lamps and every house stay clear. Fixed seed: deterministic.</summary>
    private void Woods()
    {
        var rng = new System.Random(1337);
        var spots = new List<Foliage.Spot>();
        var houses = new List<Vector2>();
        foreach (var pc in Layout)
            if (pc.Model.StartsWith("bld_") || pc.Model == "monument_keep") houses.Add(new Vector2(pc.A, pc.B));

        bool Clear(float a, float b)
        {
            if (Mathf.Abs(b) < 5.4f && a < 58f) return false;       // road, fences, lamps
            foreach (var h in houses)
                if (new Vector2(a, b).DistanceTo(h) < (h.X > 80f ? 14f : 6.5f)) return false;
            return true;
        }

        void Add(string kind, float a, float b, float scale, bool shadow)
        {
            var at = World(a, b);
            at.Y = WorldGen.Height(at.X, at.Z);
            spots.Add(new Foliage.Spot(kind, at, scale, shadow));
        }

        string Species(double r) => r < 0.45 ? "oak" : r < 0.75 ? "pine" : "birch";

        // groves: a jittered 2.3 m grid, kept where the clumping field is high
        // -- thickets where it peaks, glades where it dips
        void Grove(float a0, float a1, float b0, float b1, float fill)
        {
            for (var a = a0; a < a1; a += 2.3f)
            for (var b = b0; b < b1; b += 2.3f)
            {
                var ja = a + (float)(rng.NextDouble() - 0.5) * 1.8f;
                var jb = b + (float)(rng.NextDouble() - 0.5) * 1.8f;
                var clump = Biomes.Fbm(ja * 0.07f, jb * 0.07f, WorldGen.Seed ^ 0x6A0FUL);
                if (rng.NextDouble() > fill * Mathf.SmoothStep(0.38f, 0.62f, clump)) continue;
                if (!Clear(ja, jb)) continue;
                Add(Species(rng.NextDouble()), ja, jb, 0.8f + (float)rng.NextDouble() * 0.45f, true);
                // undergrowth round the trunk, on the camera's side
                if (rng.NextDouble() < 0.55)
                    Add("bush", ja - 0.8f, jb + (float)(rng.NextDouble() - 0.5) * 1.6f,
                        0.8f + (float)rng.NextDouble() * 0.6f, false);
            }
        }

        Grove(-6f, 62f, -34f, -7f, 0.95f);      // behind the houses, left of the road
        Grove(4f, 70f, 6.5f, 32f, 0.85f);       // right of the road
        Grove(62f, 105f, -36f, 36f, 0.6f);      // around the keep

        // the near band: big trees and bushes close to the camera, at the edges
        Add("oak", -7.5f, -7.8f, 1.35f, true);
        Add("pine", -9.5f, 8.8f, 1.3f, true);
        Add("oak", -4.5f, 10.5f, 1.25f, true);
        Add("bush", -5.5f, -5.9f, 1.8f, false);
        Add("bush", -6.5f, 6.4f, 2.0f, false);

        // the treeline: small, no shadows, a band beyond the keep
        for (var b = -70f; b < 70f; b += 3.1f)
            for (var row = 0; row < 3; row++)
            {
                var a = 125f + row * 9f + (float)rng.NextDouble() * 6f;
                Add(Species(rng.NextDouble()), a, b + (float)rng.NextDouble() * 2f,
                    0.9f + (float)rng.NextDouble() * 0.5f, false);
            }

        spots = Bake.Plants(spots);
        spots = Bake.Plants(spots);
        var holder = new Node3D { Name = "Woods" };
        AddChild(holder);
        Foliage.Forest(holder, spots, Grade.L.Yaw);
        Pieces += spots.Count;
        GD.Print($"village: woods {spots.Count} plants");
    }

    private Node3D Place(string model, float a, float b, Face face, float yaw, float scale)
    {
        // Under --kit the Layout's lone trees and bushes are not placed:
        // Woods() plants groves, walls and bands in their stead.
        if (UseKit && Foliage.Maps(model, out _)) return new Node3D();

        var file = UseKit && model is "bld_cottage" or "bld_townhouse" ? "kit_" + model[4..] : model;
        if (!_scenes.TryGetValue(file, out var scene))
        {
            scene = GD.Load<PackedScene>((file.StartsWith("kit_") ? KitDir : Dir) + file + ".glb");
            _scenes[file] = scene;
        }

        var node = scene.Instantiate<Node3D>();
        var at = World(a, b);

        // Sit on the LOWEST ground under the footprint, not the centre: on a
        // slope a building set at its centre height floats on its downhill side.
        // Every GLB carries a 0.5 m base below its origin, which buries the rest.
        var r = 1.2f * scale;
        var y = Mathf.Min(Mathf.Min(WorldGen.Height(at.X - r, at.Z - r), WorldGen.Height(at.X + r, at.Z - r)),
                          Mathf.Min(WorldGen.Height(at.X - r, at.Z + r), WorldGen.Height(at.X + r, at.Z + r)));
        node.Position = new Vector3(at.X, y, at.Z);

        // A GLB's front is +Z (Blender's -Y). Yaw theta turns +Z to
        // (sin theta, 0, cos theta).
        var deg = face switch
        {
            // Toward the road and the camera together: the front reads as a
            // facade from the locked view, the whole point of Law 1.
            Face.Road => Facing((-F * 0.55f + R * (b < 0 ? 0.85f : -0.85f)).Normalized()),
            // Native long axis is X; turn it onto F.
            Face.Along => 135f,
            _ => yaw,
        };
        node.RotationDegrees = new Vector3(0f, deg, 0f);
        node.Scale = Vector3.One * scale;
        // a baked scene may have moved it, or deleted it (then it stays hidden, with no
        // collider, so what hangs on it -- a lamp's flame -- goes with it)
        if (Bake.VillagePiece(file, node.Transform) is not { } baked)
        {
            node.Visible = false;
            AddChild(node);
            return node;
        }
        node.Transform = baked;
        return Settle(node, model);
    }

    /// <summary>A model file at a transform: a piece added to a baked scene in the editor.</summary>
    internal Node3D PlaceAt(string file, Transform3D xf)
    {
        if (!_scenes.TryGetValue(file, out var scene))
            _scenes[file] = scene = GD.Load<PackedScene>((file.StartsWith("kit_") ? KitDir : Dir) + file + ".glb");
        var node = scene.Instantiate<Node3D>();
        node.Transform = xf;
        return Settle(node, file.StartsWith("kit_") ? "bld_" + file[4..] : file);
    }

    private Node3D Settle(Node3D node, string model)
    {
        AddChild(node);
        // no grass through the floor; weeds at the foot of the walls
        if (model.StartsWith("bld_") || model.StartsWith("monument_")) Grass.ClearNode(node);
        Relight(node);
        Solidify(node);
        Proxy(node);
        Budget(node, model);
        Pieces++;
        return node;
    }

    /// <summary>A kit model carries a `SHADOW_` mesh of a few dozen triangles:
    /// it alone casts, and the detailed mesh casts nothing. The shadow cascades
    /// are the frame's cost (memory.md), not the triangles on screen.</summary>
    internal static void Proxy(Node root)
    {
        var shadows = new List<GeometryInstance3D>();
        var visual = new List<GeometryInstance3D>();
        void Walk(Node n)
        {
            if (n is GeometryInstance3D g)
                (g.Name.ToString().StartsWith("SHADOW_") ? shadows : visual).Add(g);
            foreach (var c in n.GetChildren()) Walk(c);
        }
        Walk(root);
        if (shadows.Count == 0) return;
        if (NoProxy) { foreach (var g in shadows) g.Visible = false; return; }
        foreach (var g in shadows) g.CastShadow = GeometryInstance3D.ShadowCastingSetting.ShadowsOnly;
        foreach (var g in visual) g.CastShadow = GeometryInstance3D.ShadowCastingSetting.Off;
    }

    private static float Facing(Vector3 d) => Mathf.RadToDeg(Mathf.Atan2(d.X, d.Z));

    /// <summary>What each kind of piece is allowed to cost.
    ///
    /// Measured before this existed, standing at the spawn: 1324 draw calls and
    /// 2.39 M primitives against 50 and 216 k for the bare terrain, GPU 6.6 ms
    /// against 3.5, frame p99 8.4-8.6 ms over the 8.33 ms budget. Undergrowth is
    /// most of the piece count and none of the silhouette, so it casts no shadow
    /// and disappears past the distance where it is a few pixels anyway. The
    /// fixed rule for anything added later: small things do not cast, and
    /// everything that is not a landmark has a visibility range.</summary>
    private static void Budget(Node n, string model)
    {
        var (cast, range) = model switch
        {
            "flowers" or "grass_patch" => (false, 35f),
            "bush" => (false, 55f),
            "wood_fence" => (true, 70f),
            "street_lamp" => (true, 90f),
            "monument_keep" => (true, 0f),       // a landmark: never culled
            _ => (true, 140f),
        };
        Apply(n, cast, range);
    }

    private static void Apply(Node n, bool cast, float range)
    {
        if (n is GeometryInstance3D g)
        {
            if (!cast) g.CastShadow = GeometryInstance3D.ShadowCastingSetting.Off;
            if (range > 0f)
            {
                g.VisibilityRangeEnd = range;
                g.VisibilityRangeEndMargin = range * 0.1f;
                g.VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Self;
            }
        }
        foreach (var c in n.GetChildren()) Apply(c, cast, range);
    }

    /// <summary>Turn each GLB's `COL_*` proxy into a collider and stop drawing it.
    ///
    /// Every exported piece carries one: a coarse hull with NO material, which
    /// Godot draws in default white. That was the pale-blue box standing in every
    /// tree canopy, on every roof and along every fence in the first capture. It
    /// is exactly the shape the player should bump into, so it becomes a
    /// convex collider -- a handful of faces each, built once at spawn, nothing
    /// like the trimesh stall INVARIANTS.md warns about.</summary>
    private static void Solidify(Node root)
    {
        var proxies = new List<MeshInstance3D>();
        Collect(root, proxies);
        foreach (var mi in proxies)
        {
            if (mi.Mesh != null)
            {
                var body = new StaticBody3D { Name = mi.Name + "_Body", Transform = mi.Transform };
                body.AddChild(new CollisionShape3D { Shape = mi.Mesh.CreateConvexShape() });
                mi.GetParent().AddChild(body);
            }
            mi.QueueFree();
        }
    }

    internal static void Collect(Node n, List<MeshInstance3D> into)
    {
        if (n is MeshInstance3D mi && mi.Name.ToString().StartsWith("COL_")) into.Add(mi);
        foreach (var c in n.GetChildren()) Collect(c, into);
    }

    /// <summary>Put the emission back on by material name. One override per
    /// name, shared by every instance, so a village of forty windows is one
    /// material, not forty.</summary>
    internal void Relight(Node n)
    {
        if (n is MeshInstance3D mi && mi.Mesh != null)
        {
            // Nothing in the village moves, so its shadows are cast once per
            // frame by the sun only; the lamps' shadow budget is handled below.
            for (var s = 0; s < mi.Mesh.GetSurfaceCount(); s++)
            {
                var src = mi.Mesh.SurfaceGetMaterial(s);
                if (src == null) continue;
                var glow = Glow(src);
                if (glow != null) mi.SetSurfaceOverrideMaterial(s, glow);
                else if (TexLib.Has(src.ResourceName)) mi.SetSurfaceOverrideMaterial(s, TexLib.Get(src.ResourceName));
                else if (Grade.L.Grain && src is BaseMaterial3D b)
                    mi.SetSurfaceOverrideMaterial(s, Grained(b));
            }
        }
        foreach (var c in n.GetChildren()) Relight(c);
    }

    private readonly Dictionary<Material, Material> _grained = new();

    /// <summary>Lighting study only: the flat material with the grain proxy.</summary>
    private Material Grained(BaseMaterial3D src)
    {
        if (_grained.TryGetValue(src, out var m)) return m;
        var d = (BaseMaterial3D)src.Duplicate();
        Grade.Grain(d);
        return _grained[src] = d;
    }

    private Material? Glow(Material src)
    {
        var name = src.ResourceName;
        if (_glow.TryGetValue(name, out var cached)) return cached;

        (Color col, float energy)? spec = name switch
        {
            "M_Lantern_Flame" => (new Color(1f, 0.62f, 0.28f), 4.5f),
            "M_Window_Warm" => (new Color(1f, 0.66f, 0.34f), 2.2f),
            "M_Window_Dim" => (new Color(0.9f, 0.55f, 0.30f), 0.7f),
            _ => null,
        };

        Material? made = null;
        if (spec is { } g && src is BaseMaterial3D bm)
        {
            var m = (BaseMaterial3D)bm.Duplicate();
            m.EmissionEnabled = true;
            m.Emission = g.col;
            m.EmissionEnergyMultiplier = g.energy * Grade.L.Lamps;
            made = m;
        }
        _glow[name] = made;
        return made;
    }

    public override void _Process(double delta)
    {
        // The light budget, four times a second: shadows only on the lamps
        // nearest the player, and lamps off entirely past their range. Ranking
        // every frame buys nothing a walking player could see.
        if (++_tick % 15 != 0 || _player == null) return;

        var at = _player.GlobalPosition;
        _lamps.Sort((x, y) => x.GlobalPosition.DistanceSquaredTo(at)
                               .CompareTo(y.GlobalPosition.DistanceSquaredTo(at)));
        for (var k = 0; k < _lamps.Count; k++)
            _lamps[k].Cull(_lamps[k].GlobalPosition.DistanceTo(at), k < ShadowBudget);
    }
}
