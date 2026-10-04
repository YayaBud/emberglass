using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// `--bake` (implementation_plan "Everything editable"): turns the code-built world into
/// scenes the Godot editor can show and edit. Phase 1: every asset as a prefab
/// (`res://prefabs/&lt;kit&gt;/&lt;kind&gt;.tscn`, a <see cref="Piece"/>) with its in-game look
/// saved beside it (`_vis/&lt;kind&gt;.scn`, built by the same code the game uses), and all
/// of them laid out in one sheet, `res://scenes/asset_sheet.tscn`. Textures and shaders
/// the visuals share are saved once under `res://prefabs/_shared/` and referenced.
/// </summary>
public static class Bake
{
    public static bool On;

    private const string Root = "res://prefabs/";
    private const string Sheet = "res://scenes/asset_sheet.tscn";
    private const float Gap = 2f, RowWidth = 160f;

    private readonly record struct Asset(string Kit, string Kind, Node3D Vis);

    private static readonly Dictionary<ulong, Resource> _shared = new();
    private static int _sharedN;

    /// <summary>Call before any site builds: the city's texture arrays are built on the
    /// first <see cref="CityKit.Load"/>, so every city kind has to be in that one.</summary>
    public static void Assets()
    {
        var t0 = Time.GetTicksMsec();
        var all = new List<Asset>();
        all.AddRange(KitAssets());
        all.AddRange(CityAssets());
        all.AddRange(VillageAssets());
        all.AddRange(FoliageAssets());
        all.AddRange(SpriteAssets());
        var ship = GD.Load<PackedScene>("res://assets/models/ship/ship_cargo.glb").Instantiate<Node3D>();
        Ship.Dress(ship);
        Village.Proxy(ship);
        all.Add(new Asset("ship", "ship_cargo", ship));

        var sheet = new Node3D { Name = "AssetSheet" };
        var z = 0f;
        foreach (var group in all.GroupBy(a => a.Kit))
        {
            var header = new Label3D { Name = "_" + group.Key, Text = group.Key.ToUpperInvariant(), FontSize = 256, PixelSize = 0.01f, OutlineSize = 24,
                                       Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, Position = new Vector3(-8f, 1.5f, z + 2f) };
            sheet.AddChild(header);
            float x = 0f, depth = 0f;
            foreach (var (a, box) in group.Select(a => (a, Box(a.Vis))).OrderBy(p => p.Item2.Size.X * p.Item2.Size.Z))
            {
                var w = Mathf.Max(box.Size.X, 1f);
                var d = Mathf.Max(box.Size.Z, 1f);
                if (x > 0f && x + w > RowWidth) { z += depth + Gap * 2f; x = 0f; depth = 0f; }
                var prefab = Prefab(a);
                var inst = GD.Load<PackedScene>(prefab).Instantiate<Node3D>();
                inst.Name = $"{a.Kit}_{a.Kind}";
                inst.Position = new Vector3(x - box.Position.X, 0f, z - box.Position.Z);
                sheet.AddChild(inst);
                inst.AddChild(new Label3D
                {
                    Name = "_label", Text = a.Kind, FontSize = 64, PixelSize = 0.01f, OutlineSize = 12,
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, Position = new Vector3(box.GetCenter().X, box.End.Y + 0.6f, box.GetCenter().Z),
                });
                x += w + Gap;
                depth = Mathf.Max(depth, d);
            }
            z += depth + Gap * 6f;
        }
        Stage(sheet, new Vector3(-12f, 0f, -12f), new Vector3(RowWidth + 12f, 0f, z));
        // the labels are owned by the sheet (a Piece's own children are its visual, unsaved)
        foreach (var n in sheet.GetChildren())
        {
            n.Owner = sheet;
            foreach (var c in n.GetChildren()) if (c.Name == "_label") c.Owner = sheet;
        }
        Save(sheet, Sheet, own: false);
        foreach (var a in all) a.Vis.Free();
        sheet.Free();
        GD.Print($"bake: {all.Count} assets in {all.Select(a => a.Kit).Distinct().Count()} kits, "
                 + $"{_sharedN} shared resources, sheet {Sheet}, {Time.GetTicksMsec() - t0} ms");
    }

    /// <summary>Opens the sheet just written and saves an overview and two close-ups to
    /// `scratch/bake_sheet_*.png` (the Phase 1 gate: every kit there, no missing material).</summary>
    public static async System.Threading.Tasks.Task Shots(SceneTree tree)
    {
        tree.ChangeSceneToFile(Sheet);
        await tree.ToSignal(tree.CreateTimer(4.0), SceneTreeTimer.SignalName.Timeout);
        var cam = tree.CurrentScene.GetNode<Camera3D>("_camera");
        var ground = (PlaneMesh)tree.CurrentScene.GetNode<MeshInstance3D>("_ground").Mesh;
        var depth = ground.Size.Y;
        var views = new[] { ("overview", cam.GlobalTransform), ("near", At(new Vector3(40f, 0f, depth * 0.12f))), ("far", At(new Vector3(60f, 0f, depth * 0.62f))) };
        Transform3D At(Vector3 look) => new(Basis.LookingAt(new Vector3(0f, -0.55f, 1f), Vector3.Up), look + new Vector3(0f, 26f, -46f));
        var dir = ProjectSettings.GlobalizePath("res://").PathJoin("../scratch");
        foreach (var (name, xf) in views)
        {
            cam.GlobalTransform = xf;
            await tree.ToSignal(tree.CreateTimer(1.5), SceneTreeTimer.SignalName.Timeout);
            var err = tree.Root.GetTexture().GetImage().SavePng(dir.PathJoin($"bake_sheet_{name}.png"));
            GD.Print($"bake: shot {name} {err}");
        }
        if (ResourceLoader.Exists(TerrainEdit.Scene))
        {
            tree.ChangeSceneToFile(TerrainEdit.Scene);
            await tree.ToSignal(tree.CreateTimer(3.0), SceneTreeTimer.SignalName.Timeout);
            var root = tree.CurrentScene;
            root.AddChild(new DirectionalLight3D { RotationDegrees = new Vector3(-55f, 160f, 0f), LightEnergy = 1.2f });
            var eye = new Camera3D { Far = 5000f };
            root.AddChild(eye);
            eye.MakeCurrent();
            root.Call("set_camera", eye);
            foreach (var (name, from, at) in new[] { ("terrain_all", new Vector3(0f, 1500f, 700f), new Vector3(0f, 0f, -500f)), ("terrain_village", new Vector3(-60f, 70f, 90f), new Vector3(0f, 0f, 0f)) })
            {
                eye.GlobalTransform = new Transform3D(Basis.LookingAt(at - from, Vector3.Up), from);
                await tree.ToSignal(tree.CreateTimer(2.0), SceneTreeTimer.SignalName.Timeout);
                var err = tree.Root.GetTexture().GetImage().SavePng(dir.PathJoin($"bake_{name}.png"));
                GD.Print($"bake: shot {name} {err}");
            }
        }
        // ponytail: a plain Quit here hung in shutdown (bake 3, killed at 400 s); every file
        // is written and closed by now, so end the process outright
        OS.Kill(OS.GetProcessId());
    }

    /// <summary>The game's light over a sheet: a ground to take the shadows, the sun and
    /// fill of the current light (<see cref="Grade.L"/>, as World.BuildSun), the game's
    /// environment without its fog (it is tuned for 80 m; the sheet is seen from further),
    /// and a <see cref="FlyCamera"/> over it, so F6 in the editor flies round the sheet.</summary>
    private static void Stage(Node3D sheet, Vector3 lo, Vector3 hi)
    {
        var size = hi - lo;
        var mid = (lo + hi) / 2f;
        sheet.AddChild(new MeshInstance3D
        {
            Name = "_ground", Position = mid + Vector3.Down * 0.01f,
            Mesh = new PlaneMesh { Size = new Vector2(size.X, size.Z) },
            MaterialOverride = new StandardMaterial3D { AlbedoColor = new Color(0.36f, 0.34f, 0.30f), Roughness = 1f },
        });
        sheet.AddChild(new DirectionalLight3D
        {
            Name = "_sun", LightColor = Grade.L.Sun, LightEnergy = Grade.L.SunEnergy, LightAngularDistance = Grade.L.Soft,
            // front-lit from behind the camera (the sheet is seen looking +Z): the game's
            // backlit key (Grade.L.Yaw) left every front a black silhouette (bake 3 shots)
            ShadowEnabled = true, DirectionalShadowMaxDistance = 250f, RotationDegrees = new Vector3(-50f, 160f, 0f),
        });
        sheet.AddChild(new DirectionalLight3D
        {
            Name = "_fill", LightColor = Grade.L.Fill, LightEnergy = Grade.L.FillEnergy, RotationDegrees = new Vector3(-32f, 45f, 0f),
        });
        var env = Grade.Build();
        env.FogEnabled = false;
        env.VolumetricFogEnabled = false;
        sheet.AddChild(new WorldEnvironment { Name = "_env", Environment = env });
        var eye = new Vector3(mid.X, size.Z * 0.45f + 20f, lo.Z - size.Z * 0.2f);
        sheet.AddChild(new FlyCamera { Name = "_camera", Transform = new Transform3D(Basis.LookingAt(mid - eye, Vector3.Up), eye), Far = 2000f });
    }

    // ------------------------------------------------------------------ the kits

    private static IEnumerable<Asset> KitAssets()
    {
        foreach (var glb in Kit.Glbs)
        {
            var kit = glb.GetBaseDir().GetFile();
            var src = GD.Load<PackedScene>(glb).Instantiate<Node3D>();
            var names = src.FindChildren("*", "MeshInstance3D", true, false).Select(n => n.Name.ToString())
                .Where(n => !n.StartsWith("COL_") && !n.StartsWith("SHADOW_")).Distinct().OrderBy(n => n).ToList();
            src.Free();
            foreach (var name in names)
                yield return new Asset(kit, name, new MeshInstance3D { Name = name, Mesh = Kit.MeshOf(name) });
        }
    }

    private static IEnumerable<Asset> CityAssets()
    {
        var kinds = DirAccess.GetFilesAt("res://assets/models/citykit").Where(f => f.StartsWith("city_") && f.EndsWith(".glb"))
            .Select(f => f[5..^4]).Append("townhouse").Append("cottage").ToList();
        CityKit.Load(kinds, new List<string>());
        foreach (var kind in kinds.Where(CityKit.Has))
        {
            var a = CityKit.Get(kind);
            var vis = new Node3D { Name = kind };
            vis.AddChild(new MeshInstance3D { Name = "Mesh", Mesh = a.Mesh, MaterialOverride = a.Mat });
            if (a.Extra != null) vis.AddChild(new MeshInstance3D { Name = "Extra", Mesh = a.Extra, MaterialOverride = a.ExtraMat ?? a.Mat });
            yield return new Asset("citykit", kind, vis);
        }
    }

    private static IEnumerable<Asset> VillageAssets()
    {
        var relight = new Village();
        foreach (var (dir, prefix) in new[] { ("res://assets/models/village", ""), ("res://assets/models/kit", "kit_") })
            foreach (var f in DirAccess.GetFilesAt(dir).Where(f => f.EndsWith(".glb") && f.StartsWith(prefix)))
            {
                var node = GD.Load<PackedScene>($"{dir}/{f}").Instantiate<Node3D>();
                var cols = new List<MeshInstance3D>();
                Village.Collect(node, cols);
                foreach (var c in cols) c.Free();
                relight.Relight(node);
                Village.Proxy(node);
                yield return new Asset("village", f[..^4], node);
            }
        relight.Free();
    }

    private static IEnumerable<Asset> FoliageAssets()
    {
        var sprites = (Godot.Collections.Dictionary)((Godot.Collections.Dictionary)Json.ParseString(
            FileAccess.GetFileAsString("res://assets/foliage/manifest.json")))["sprites"];
        var face = Basis.FromEuler(new Vector3(Mathf.DegToRad(-Foliage.TiltDeg), Mathf.DegToRad(CameraRig.BaseYaw), 0f));
        // one prefab per plant kind (what Foliage.Spot names); the game picks the variant by position
        foreach (var kind in sprites.Keys.Select(k => (string)k).Select(k => k[..k.LastIndexOf('_')]).Distinct())
        {
            var pick = kind + "_0";
            var info = (Godot.Collections.Dictionary)sprites[pick];
            var m = (Godot.Collections.Array)info["metres"];
            var px = (Godot.Collections.Array)info["px"];
            var size = new Vector2((float)m[0], (float)m[1]);
            var footM = (int)info["foot_px"] / (float)(int)px[1] * size.Y;
            yield return new Asset("foliage", kind, new MeshInstance3D
            {
                Name = kind, Basis = face, MaterialOverride = Foliage.Material(pick),
                Mesh = new QuadMesh { Size = size, CenterOffset = new Vector3(0f, size.Y / 2f - footM, 0f) },
            });
        }
    }

    /// <summary>Animals, townsfolk and the player: the first cell of each sheet, at the
    /// game's 52 texels/m, feet on the ground.</summary>
    private static IEnumerable<Asset> SpriteAssets()
    {
        Sprite3D Cell(string name, string tex, Vector2I cell, int foot) => new()
        {
            Name = name, Texture = GD.Load<Texture2D>(tex), RegionEnabled = true, RegionRect = new Rect2(0, 0, cell.X, cell.Y),
            PixelSize = 1f / 52f, Offset = new Vector2(0f, cell.Y / 2f - foot), TextureFilter = BaseMaterial3D.TextureFilterEnum.Nearest,
            AlphaCut = SpriteBase3D.AlphaCutMode.Discard, Billboard = BaseMaterial3D.BillboardModeEnum.FixedY,
        };
        Godot.Collections.Dictionary Manifest(string dir) => (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString($"res://assets/{dir}/manifest.json"));

        var fauna = (Godot.Collections.Dictionary)Manifest("fauna")["animals"];
        foreach (var k in fauna.Keys)
        {
            var a = (Godot.Collections.Dictionary)fauna[k];
            var c = (Godot.Collections.Array)a["cell_px"];
            yield return new Asset("fauna", (string)k, Cell((string)k, $"res://assets/fauna/{k}.png", new Vector2I((int)c[0], (int)c[1]), (int)a["foot_px"]));
        }
        var folk = Manifest("folk");
        var fc = (Godot.Collections.Array)folk["cell_px"];
        var foot = (int)((Godot.Collections.Dictionary)((Godot.Collections.Dictionary)folk["foot_px"])["8"])["s"];
        foreach (var k in ((Godot.Collections.Dictionary)folk["files"]).Keys)
            yield return new Asset("folk", (string)k, Cell((string)k, $"res://assets/folk/{k}_08.png", new Vector2I((int)fc[0], (int)fc[1]), foot));
        var pl = Manifest("sprites");
        var canvas = (int)pl["canvas_px"];
        yield return new Asset("player", "player", Cell("player", "res://assets/sprites/player_idle_s.png", new Vector2I(canvas, canvas), (int)pl["foot_px"]));
    }

    // ------------------------------------------------------------------ saving

    /// <summary>Writes `_vis/&lt;kind&gt;.scn` and the prefab `&lt;kind&gt;.tscn`; returns the prefab path.</summary>
    private static string Prefab(Asset a)
    {
        var dir = $"{Root}{a.Kit}/";
        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(dir + "_vis"));
        Externalize(a.Vis);
        a.Vis.Name = a.Kind;
        // a GLB instance is saved as plain nodes, not as a scene inheriting the GLB
        a.Vis.SceneFilePath = "";
        Save(a.Vis, $"{dir}_vis/{a.Kind}.scn");
        using (var f = FileAccess.Open($"{dir}_vis/{a.Kind}.scn", FileAccess.ModeFlags.Read))
            if (f.GetLength() > 16_000_000)
                throw new System.InvalidOperationException($"bake: {a.Kit}/{a.Kind} visual is {f.GetLength() / 1e6:F0} MB: a shared resource was embedded");
        var piece = new Piece { Name = a.Kind, Kit = a.Kit, Kind = a.Kind };
        Save(piece, $"{dir}{a.Kind}.tscn");
        piece.Free();
        return $"{dir}{a.Kind}.tscn";
    }

    private static void Save(Node root, string path, bool own = true)
    {
        if (own) Own(root, root);
        var ps = new PackedScene();
        var err = ps.Pack(root);
        if (err == Error.Ok) err = ResourceSaver.Save(ps, path);
        if (err != Error.Ok) GD.PushError($"bake: cannot save {path}: {err}");
    }

    private static void Own(Node n, Node owner)
    {
        foreach (var c in n.GetChildren())
        {
            c.Owner = owner;
            Own(c, owner);
        }
    }

    /// <summary>Saves each shader and texture the visuals share once, so the visuals
    /// reference it instead of embedding a copy each (a city texture array is ~40 MB).</summary>
    private static void Externalize(Node n)
    {
        if (n is GeometryInstance3D g)
        {
            ShareMat(g.MaterialOverride);
            if (g is MeshInstance3D mi && mi.Mesh != null)
                for (var s = 0; s < mi.Mesh.GetSurfaceCount(); s++)
                {
                    ShareMat(mi.GetSurfaceOverrideMaterial(s));
                    ShareMat(mi.Mesh.SurfaceGetMaterial(s));
                }
            if (g is SpriteBase3D) return;
        }
        foreach (var c in n.GetChildren()) Externalize(c);
    }

    private static void ShareMat(Material? m)
    {
        if (m == null) return;
        if (m is ShaderMaterial sm && sm.Shader != null)
        {
            Share(sm.Shader, "gdshader");
            foreach (var u in sm.Shader.GetShaderUniformList())
                if (sm.GetShaderParameter((string)((Godot.Collections.Dictionary)u)["name"]).Obj is Texture t) Share(t, "res");
        }
        else if (m is BaseMaterial3D b)
            foreach (var p in System.Enum.GetValues<BaseMaterial3D.TextureParam>())
                if (p != BaseMaterial3D.TextureParam.Max && b.GetTexture(p) is { } t) Share(t, "res");
        ShareMat(m.NextPass);
    }

    private static void Share(Resource r, string ext)
    {
        if (r.ResourcePath != "" || _shared.ContainsKey(r.GetInstanceId())) return;
        var dir = Root + "_shared/";
        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(dir));
        var path = $"{dir}{r.GetClass().ToLowerInvariant()}_{_sharedN++}.{ext}";
        var err = ResourceSaver.Save(r, path);
        if (err != Error.Ok) GD.PushError($"bake: cannot save {path}: {err}");
        // SaverFlags.ChangePath did not leave the path set (4.6.3): every visual then
        // embedded its own copy of the city's texture arrays, 148 MB each, 23 GB in all
        r.TakeOverPath(path);
        _shared[r.GetInstanceId()] = r;
    }

    /// <summary>The asset's bounds in its own space, from every mesh and sprite in it.</summary>
    private static Aabb Box(Node3D vis)
    {
        Aabb? box = null;
        void Walk(Node n, Transform3D xf)
        {
            if (n is Node3D n3) xf *= n3.Transform;
            // (a sprite has no AABB until it is drawn: its cell, feet at the origin)
            Aabb? own = n switch
            {
                Sprite3D s => new Aabb(new Vector3(-s.RegionRect.Size.X / 2f, s.Offset.Y - s.RegionRect.Size.Y / 2f, -0.1f / s.PixelSize) * s.PixelSize,
                                       new Vector3(s.RegionRect.Size.X, s.RegionRect.Size.Y, 0.2f / s.PixelSize) * s.PixelSize),
                GeometryInstance3D { CastShadow: GeometryInstance3D.ShadowCastingSetting.ShadowsOnly } => null,
                VisualInstance3D v => v.GetAabb(),
                _ => null,
            };
            if (own is { } o)
            {
                var b = xf * o;
                box = box?.Merge(b) ?? b;
            }
            foreach (var c in n.GetChildren()) Walk(c, xf);
        }
        Walk(vis, Transform3D.Identity);
        return box ?? new Aabb(Vector3.Zero, Vector3.One);
    }

    // ================================================================== sites (Phase 2)
    // Record at the funnel, replay at the funnel. Each site's generator still runs; its
    // placements pass through a few shared calls (Kit.Place, Wildwood.Tiled / Village.Woods,
    // Village.Place, Breakables.Add, Bake.Lamp, and the city's _places). With no baked scene
    // the calls are recorded (under --bake) and written to res://world/<site>.tscn. With one,
    // the n-th call of a kind takes the baked entries recorded for that n-th call instead of
    // its generated input; entries no call took (added in the editor) are placed after the
    // site's Build (Tail). ponytail: what a generator derives from its own layout (grass
    // clearings, animal blockers, smoke, Scatter keep-outs) still follows the generated
    // layout, not the edits.

    /// <summary>One placement: the funnel (kit, breakable, foliage, village, city, lamp), the
    /// prefab (Kit/Kind), where, and what the funnel needs besides (Meta).</summary>
    public sealed class Entry
    {
        public string F = "", Kit = "", Kind = "";
        public Transform3D Xf = Transform3D.Identity;
        public Godot.Collections.Dictionary Meta = new();
        /// <summary>City wall mounts: the entry (a building) this one hangs on; written as its child.</summary>
        public int Of = -1;
        public LampLight? Lamp;
        public bool Used;

        public float Num(string k, float d = 0f) => Meta.TryGetValue(k, out var v) ? v.AsSingle() : d;
        public int Int(string k, int d) => Meta.TryGetValue(k, out var v) ? v.AsInt32() : d;
        public bool Flag(string k, bool d) => Meta.TryGetValue(k, out var v) ? v.AsBool() : d;
        public string Str(string k, string d) => Meta.TryGetValue(k, out var v) ? v.AsString() : d;
    }

    private readonly record struct Fed(string F, string Kind, Vector3 P, float Yaw, float Scale);

    private const string WorldDir = "res://world/";
    public static bool Check;
    public static readonly HashSet<string> Rebake = new();
    public static Village? VillageNode;

    /// <summary>The site being built, while its placements are recorded or replayed; null otherwise.</summary>
    public static string? Site { get; private set; }
    public static bool Replaying => Site != null && _replay;
    private static bool _replay, _tail;
    private static List<Entry> _cur = new();
    private static Node3D? _siteNode, _bakedRoot;
    private static int _cityBase;
    private static readonly Dictionary<string, int> _calls = new();
    private static readonly Dictionary<string, List<Entry>> _recorded = new();
    private static readonly Dictionary<string, List<Fed>> _fed = new();
    private static readonly Dictionary<string, int> _unused = new();
    private static readonly Dictionary<string, List<Fed>> _want = new();
    // Phase 6: which funnel kinds a scene holds (root meta `funnels`; a scene from before a
    // kind existed is upgraded: that kind is recorded as generated and written back)
    private static HashSet<string> _funnels = new();
    private static readonly HashSet<string> _called = new();
    private static readonly Dictionary<string, HashSet<string>> _calledBy = new();
    private static bool _grow;
    private static Godot.Collections.Array<string>? _loadedFunnels;
    private static readonly Dictionary<Townsfolk.Route, int> _routes = new();
    private static int _folkI;
    private static readonly Dictionary<string, (Fauna F, Fauna.Kind K)> _herds = new();
    private static bool Baked(string f) => _replay && _funnels.Contains(f);

    private static string SitePath(string site) => $"{WorldDir}{site}.tscn";
    private static string Scratch(string file) => ProjectSettings.GlobalizePath("res://").PathJoin("../scratch").PathJoin(file);

    public static void Begin(string site, Node3D node, Node3D? from = null)
    {
        _siteNode = node;
        _calls.Clear();
        _called.Clear();
        _routes.Clear();
        _herds.Clear();
        (_folkI, _grow) = (0, false);
        var t0 = Time.GetTicksMsec();
        var baked = Rebake.Contains(site) || Rebake.Contains("all") ? null : from != null ? LoadFrom(from) : Load(site);
        if (baked != null)
        {
            (Site, _replay, _cur) = (site, true, baked);
            _funnels = _loadedFunnels != null ? _loadedFunnels.ToHashSet() : baked.Select(e => e.F).ToHashSet();
            _fed[site] = new List<Fed>();
            _want[site] = baked.Select(FedOf).ToList();
            GD.Print($"bake: {site} from {SitePath(site)}, {baked.Count} placements, read in {Time.GetTicksMsec() - t0} ms");
        }
        else if (On)
        {
            (Site, _replay, _cur) = (site, false, new List<Entry>());
            _recorded[site] = _cur;
        }
        else Site = null;
    }

    public static void End()
    {
        if (Site == null) return;
        var site = Site;
        if (_replay)
        {
            Tail(site);
            _unused[site] = _cur.Count(e => !e.Used);
            // kinds this scene did not hold yet were recorded as generated: write it back with them
            if (_grow && On) _recorded[site] = _cur;
        }
        _calledBy[site] = new HashSet<string>(_called.Concat(_funnels));
        _bakedRoot?.Free();
        _bakedRoot = null;
        (Site, _replay) = (null, false);
    }

    private static int Call(string key)
    {
        _calls.TryGetValue(key, out var k);
        _calls[key] = k + 1;
        return k;
    }

    /// <summary>The unused baked entries of one call, marked used and counted as fed.</summary>
    private static List<Entry> Take(string f, string? kind, int ctx)
    {
        var got = _cur.Where(e => !e.Used && e.F == f && (kind == null || e.Kind == kind) && e.Int("ctx", -1) == ctx).ToList();
        foreach (var e in got) Feed(e);
        return got;
    }

    private static void Feed(Entry e)
    {
        e.Used = true;
        _fed[Site!].Add(FedOf(e));
    }

    private static Fed FedOf(Entry e)
    {
        var p = e.F switch
        {
            "kit" or "foliage" or "village" => Foot(e),
            "breakable" => new Vector3(e.Xf.Origin.X, WorldGen.Height(e.Xf.Origin.X, e.Xf.Origin.Z), e.Xf.Origin.Z),
            _ => e.Xf.Origin,
        };
        return new Fed(e.F, e.Kind, p, Yaw(e.Xf.Basis), e.Xf.Basis.X.Length());
    }

    /// <summary>On the ground (meta `snap`, default on) at its recorded height above it
    /// (`dy`), so a piece dragged in X/Z in the editor lands on the ground in the game.</summary>
    private static Vector3 Foot(Entry e)
    {
        var o = e.Xf.Origin;
        return e.Flag("snap", true) ? new Vector3(o.X, WorldGen.Height(o.X, o.Z) + e.Num("dy"), o.Z) : o;
    }

    private static float Yaw(Basis b)
    {
        var z = b.Z.Normalized();
        return Mathf.Atan2(z.X, z.Z);
    }

    private static float Dy(Vector3 foot) => foot.Y - WorldGen.Height(foot.X, foot.Z);

    private static Entry Rec(string f, string kit, string kind, Transform3D xf, Godot.Collections.Dictionary? meta = null, int of = -1)
    {
        var e = new Entry { F = f, Kit = kit, Kind = kind, Xf = xf, Meta = meta ?? new(), Of = of };
        _cur.Add(e);
        _called.Add(f);
        // recorded during a replay (a kind this scene did not hold): the generator used it
        // already -- counted as fed, and never placed again after the site (it was: every
        // animal of the upgraded sites twice)
        if (_replay) { _grow = true; Feed(e); }
        return e;
    }

    // ------------------------------------------------------------------ the funnels

    /// <summary>Kit.Place: records the generated items, or hands back the baked ones.</summary>
    public static List<Kit.Item> KitItems(string asset, List<Kit.Item> items, Kit.Kind kind)
    {
        if (Site == null || _tail) return items;
        var ctx = Call("kit:" + asset);
        if (_replay) return Take("kit", asset, ctx).Select(KitItem).ToList();
        foreach (var it in items)
            Rec("kit", Kit.KitOf(asset), asset, new Transform3D(it.B ?? new Basis(Vector3.Up, it.Yaw).Scaled(Vector3.One * it.Scale), it.Foot),
                new() { ["kind"] = (int)kind, ["ctx"] = ctx, ["dy"] = Dy(it.Foot), ["snow"] = it.Snow });
        return items;
    }

    private static Kit.Item KitItem(Entry e) => new(Foot(e), Yaw(e.Xf.Basis), e.Xf.Basis.X.Length(), e.Num("snow"), e.Xf.Basis);

    /// <summary>Plant spots (Wildwood.Tiled, Village.Woods).</summary>
    public static List<Foliage.Spot> Plants(List<Foliage.Spot> spots)
    {
        if (Site == null || _tail) return spots;
        var ctx = Call("foliage");
        if (_replay) return Take("foliage", null, ctx).Select(Spot).ToList();
        foreach (var sp in spots)
            Rec("foliage", "foliage", sp.Kind, new Transform3D(Basis.Identity.Scaled(Vector3.One * sp.Scale), sp.Foot),
                new() { ["ctx"] = ctx, ["dy"] = Dy(sp.Foot), ["shadow"] = sp.Shadow, ["snow"] = sp.Snow });
        return spots;
    }

    private static Foliage.Spot Spot(Entry e) => new(e.Kind, Foot(e), e.Xf.Basis.X.Length(), e.Flag("shadow", true), e.Num("snow"));

    /// <summary>Village.Place: the transform to give the model, or null when it was deleted in the editor.</summary>
    public static Transform3D? VillagePiece(string file, Transform3D xf)
    {
        if (Site == null || _tail) return xf;
        var ctx = Call("village:" + file);
        if (!_replay)
        {
            Rec("village", "village", file, xf, new() { ["ctx"] = ctx, ["dy"] = Dy(xf.Origin) });
            return xf;
        }
        return Take("village", file, ctx).FirstOrDefault() is { } e ? new Transform3D(e.Xf.Basis, Foot(e)) : null;
    }

    /// <summary>Breakables.Add: true = drop the generated one (the baked ones are added in Tail).</summary>
    public static bool Breakable(string asset, Vector2 at, float yaw, float scale)
    {
        if (Site == null || _tail) return false;
        if (_replay) return true;
        Rec("breakable", Kit.KitOf(asset), asset,
            new Transform3D(new Basis(Vector3.Up, yaw).Scaled(Vector3.One * scale), new Vector3(at.X, WorldGen.Height(at.X, at.Y), at.Y)));
        return false;
    }

    /// <summary>A site's own lamp (desert braziers, region lamps, snow lanterns; the
    /// village's hang on their posts and the city's come from its lamp posts).</summary>
    public static void Lamp(Node parent, LampLight lamp, bool auto)
    {
        if (Site != null && !_tail && _replay) { lamp.Free(); return; }
        parent.AddChild(auto ? lamp.Auto() : lamp);
        if (Site != null && !_tail) Rec("lamp", "", "lamp", Transform3D.Identity, new() { ["auto"] = auto }).Lamp = lamp;
    }

    /// <summary>Fauna.Add: the homes of one herd (one animal each), recorded, or the baked ones.</summary>
    public static IReadOnlyList<Vector2> Homes(Fauna f, Fauna.Kind k, IReadOnlyList<Vector2> homes)
    {
        if (Site == null || _tail) return homes;
        var ctx = Call("herd:" + k.Sprite);
        _herds[k.Sprite] = (f, k);
        if (Baked("herd")) return Take("herd", k.Sprite, ctx).Select(e => new Vector2(e.Xf.Origin.X, e.Xf.Origin.Z)).ToList();
        _called.Add("herd");
        foreach (var h in homes)
            Rec("herd", "fauna", k.Sprite, new Transform3D(Basis.Identity, new Vector3(h.X, WorldGen.Height(h.X, h.Y), h.Y)), new() { ["ctx"] = ctx });
        return homes;
    }

    /// <summary>Townsfolk.Walker/Carrier/Holder/Stander: true = add this generated person now.
    /// With a baked scene, false: the baked people are added in <see cref="People"/> (from
    /// Townsfolk.Finish), in the recorded order, so the town's random draws are the same.</summary>
    public static bool Person(Townsfolk t, string role, string kind, Townsfolk.Route? r, Vector2 at, float y, Vector2? face, string? act)
    {
        if (Site == null || _tail) return true;
        if (Baked("folk")) return false;
        _called.Add("folk");
        var i = _folkI++;
        if (r != null)
        {
            if (!_routes.TryGetValue(r, out var ri))
            {
                ri = _cur.Count;
                _routes[r] = ri;
                var pts = new Vector3[r.P.Length];
                for (var k = 0; k < pts.Length; k++) pts[k] = new Vector3(r.P[k].X, r.Y[k], r.P[k].Y);
                Rec("route", "", "route", Transform3D.Identity, new() { ["pts"] = pts, ["half"] = r.Half });
            }
            Rec("folk", "folk", kind, new Transform3D(Basis.Identity, new Vector3(r.P[0].X, r.Y[0], r.P[0].Y)), new() { ["role"] = role, ["i"] = i }, ri);
            return true;
        }
        var dir = face is { } fc && (fc - at).LengthSquared() > 1e-4f ? (fc - at).Normalized() : (Vector2?)null;
        var dy = y - WorldGen.Height(at.X, at.Y);
        Rec("folk", "folk", kind, new Transform3D(dir is { } d ? new Basis(Vector3.Up, Mathf.Atan2(d.X, d.Y)) : Basis.Identity, new Vector3(at.X, y, at.Y)),
            new() { ["role"] = role, ["i"] = i, ["face"] = dir != null, ["act"] = act ?? "", ["snap"] = Mathf.Abs(dy) < 0.1f, ["dy"] = dy });
        return true;
    }

    /// <summary>From Townsfolk.Finish: the baked people -- walkers and carriers on their route
    /// (a Path3D; its children walk it), standers and holders where they stand, facing their
    /// node's front.</summary>
    public static void People(Townsfolk t)
    {
        if (Site == null || _tail || !Baked("folk")) return;
        _tail = true;
        var routes = new Dictionary<int, Townsfolk.Route>();
        foreach (var e in _cur.Where(e => !e.Used && e.F == "folk").OrderBy(e => e.Int("i", int.MaxValue)).ToList())
        {
            Feed(e);
            if (e.Of >= 0 && e.Of < _cur.Count && _cur[e.Of].F == "route")
            {
                if (!routes.TryGetValue(e.Of, out var r))
                {
                    var re = _cur[e.Of];
                    var pts = re.Meta["pts"].AsVector3Array();
                    routes[e.Of] = r = new Townsfolk.Route
                    {
                        P = pts.Select(p => new Vector2(p.X, p.Z)).ToArray(), Y = pts.Select(p => p.Y).ToArray(), Half = re.Num("half", 1.5f),
                    };
                }
                if (e.Str("role", "walker") == "carrier") t.AddCarrier(e.Kind, r); else t.AddWalker(e.Kind, r);
                continue;
            }
            var foot = Foot(e);
            var at = new Vector2(foot.X, foot.Z);
            var z = e.Xf.Basis.Z.Normalized();
            Vector2? face = e.Flag("face", false) ? at + new Vector2(z.X, z.Z) : null;
            var act = e.Str("act", "");
            if (e.Str("role", "stander") == "holder") t.AddHolder(e.Kind, at, foot.Y, face ?? at + Vector2.Down, act == "" ? null : act);
            else t.AddStander(e.Kind, at, foot.Y, face);
        }
        foreach (var e in _cur.Where(e => !e.Used && e.F == "route")) Feed(e);
        _tail = false;
    }

    /// <summary>Boat.Build / Ship.Build: where it lies (a baked scene may have moved it;
    /// ponytail: deleting it keeps the generated spot, the site code needs it).</summary>
    public static void Spot(string kind, ref Vector2 at, ref float yaw)
    {
        if (Site == null || _tail) return;
        var ctx = Call("spot:" + kind);
        if (Baked("spot"))
        {
            if (Take("spot", kind, ctx).FirstOrDefault() is not { } e) return;
            (at, yaw) = (new Vector2(e.Xf.Origin.X, e.Xf.Origin.Z), Yaw(e.Xf.Basis));
            return;
        }
        Rec("spot", kind == "ship_cargo" ? "ship" : "", kind, new Transform3D(new Basis(Vector3.Up, yaw), new Vector3(at.X, WorldGen.Height(at.X, at.Y), at.Y)),
            new() { ["ctx"] = ctx, ["kind"] = kind });
    }

    /// <summary>A smoke or wisp emitter (RegionSites): where it is; false = deleted in the editor.</summary>
    public static bool Emitter(string kind, ref Vector3 at)
    {
        if (Site == null || _tail) return true;
        var ctx = Call("emitter:" + kind);
        if (Baked("emitter"))
        {
            if (Take("emitter", kind, ctx).FirstOrDefault() is not { } e) return false;
            at = e.Xf.Origin;
            return true;
        }
        Rec("emitter", "", kind, new Transform3D(Basis.Identity, at), new() { ["ctx"] = ctx, ["kind"] = kind });
        return true;
    }

    /// <summary>The city's placements start here (mount indices are relative to it).</summary>
    public static void CityStart() => _cityBase = _cur.Count;

    /// <summary>One city placement: `bldg` its index in CitySite._blds, `i` its order, `of`
    /// the placement (a building) it hangs on.</summary>
    public static void RecordCity(string kind, Transform3D xf, int col, bool along, int bldg, int i, int of) =>
        Rec("city", "citykit", kind, xf, new() { ["col"] = col, ["along"] = along, ["bldg"] = bldg, ["i"] = i, ["snap"] = false },
            of >= 0 ? _cityBase + of : -1);

    /// <summary>Every baked city entry, in the recorded order (added pieces last).</summary>
    public static List<Entry> CityEntries()
    {
        var got = _cur.Where(e => !e.Used && e.F == "city").OrderBy(e => e.Int("i", int.MaxValue)).ToList();
        foreach (var e in got) Feed(e);
        return got;
    }

    /// <summary>Entries no generator call took: pieces added in the editor, or a call that
    /// no longer happens. Placed with the site's defaults.</summary>
    private static void Tail(string site)
    {
        var left = _cur.Where(e => !e.Used && e.F is not ("city" or "folk" or "route" or "spot" or "emitter")).ToList();
        if (left.Count == 0) return;
        _tail = true;
        foreach (var e in left) Feed(e);
        foreach (var g in left.Where(e => e.F == "kit").GroupBy(e => e.Kind))
            Kit.Place(_siteNode!, g.Key, g.Select(KitItem).ToList(), (Kit.Kind)g.First().Int("kind", (int)Guess(g.Key)));
        var plants = left.Where(e => e.F == "foliage").Select(Spot).ToList();
        if (plants.Count > 0) Wildwood.Tiled(_siteNode!, plants);
        foreach (var e in left.Where(e => e.F == "breakable"))
            Breakables.Add(e.Kind, new Vector2(e.Xf.Origin.X, e.Xf.Origin.Z), Yaw(e.Xf.Basis), e.Xf.Basis.X.Length());
        foreach (var e in left.Where(e => e.F == "village")) VillageNode?.PlaceAt(e.Kind, new Transform3D(e.Xf.Basis, Foot(e)));
        foreach (var g in left.Where(e => e.F == "herd").GroupBy(e => e.Kind))
            if (_herds.TryGetValue(g.Key, out var h)) h.F.Add(h.K, g.Select(e => new Vector2(e.Xf.Origin.X, e.Xf.Origin.Z)).ToList());
            else GD.PushWarning($"bake: {site}: no {g.Key} herd here to add {g.Count()} to");
        foreach (var e in left.Where(e => e.F == "lamp" && e.Lamp != null))
        {
            var l = e.Lamp!;
            l.GetParent()?.RemoveChild(l);
            l.Owner = null;   // it was the baked scene's
            l.Transform = e.Xf;
            _siteNode!.AddChild(e.Flag("auto", true) ? l.Auto() : l);
        }
        _tail = false;
        GD.Print($"bake: {site}: {left.Count} placements placed after the site (lamps, breakables, added pieces)");
    }

    /// <summary>ponytail: a kit asset dragged in from the sheet carries no `kind`; guessed by
    /// name and height. Set meta `kind` (0 tree, 1 rock, 2 prop, 3 landmark) to override.</summary>
    private static Kit.Kind Guess(string asset) =>
        asset.Contains("Pine") || asset.Contains("Tree") || asset.Contains("Palm") || asset.Contains("Cactus") ? Kit.Kind.Tree
        : Kit.Box(asset).Size.Y > 2.5f ? Kit.Kind.Rock : Kit.Kind.Prop;

    // ------------------------------------------------------------------ write, read, check

    private static List<Fed> Raw(IEnumerable<Entry> es) =>
        es.Select(e => new Fed(e.F, e.Kind, e.Xf.Origin, Yaw(e.Xf.Basis), e.Xf.Basis.X.Length())).ToList();

    /// <summary>Pairs two placement lists by funnel, kind and position (order-free): same
    /// within 1 mm; the rest paired nearest-first as moved; then missing / extra.</summary>
    private static string Compare(List<Fed> want, List<Fed> got, out bool ok)
    {
        int same = 0, moved = 0, missing = 0, extra = 0;
        float pe = 0f, ye = 0f, se = 0f;
        var notes = new List<string>();
        var pool = got.GroupBy(x => (x.F, x.Kind)).ToDictionary(g => g.Key, g => g.ToList());
        foreach (var g in want.GroupBy(r => (r.F, r.Kind)))
        {
            var mine = pool.GetValueOrDefault(g.Key) ?? new List<Fed>();
            var left = new List<Fed>();
            foreach (var r in g)
            {
                var i = mine.FindIndex(x => (x.P - r.P).LengthSquared() < 1e-6f);
                if (i < 0) { left.Add(r); continue; }
                same++;
                pe = Mathf.Max(pe, (mine[i].P - r.P).Length());
                ye = Mathf.Max(ye, Mathf.Abs(Mathf.AngleDifference(mine[i].Yaw, r.Yaw)));
                se = Mathf.Max(se, Mathf.Abs(mine[i].Scale - r.Scale));
                mine.RemoveAt(i);
            }
            foreach (var r in left)
            {
                if (mine.Count == 0) { missing++; continue; }
                var i = Enumerable.Range(0, mine.Count).OrderBy(k => (mine[k].P - r.P).LengthSquared()).First();
                moved++;
                if (notes.Count < 5) notes.Add($"{r.Kind} {(mine[i].P - r.P).Length():F2} m");
                mine.RemoveAt(i);
            }
            pool.Remove(g.Key);
            extra += mine.Count;
        }
        extra += pool.Values.Sum(l => l.Count);
        ok = moved == 0 && missing == 0 && extra == 0 && ye < 1e-3f && se < 1e-3f;
        return $"{want.Count} vs {got.Count}: {same} same (pos err {pe:G3} m, yaw err {ye:G3} rad, scale err {se:G3}), "
               + $"{moved} moved{(notes.Count > 0 ? " [" + string.Join(", ", notes) + "]" : "")}, {missing} missing, {extra} extra";
    }

    /// <summary>Writes every site recorded this run, reads each back to check the round trip,
    /// and saves what the generators gave the funnels to `scratch/bake_fed.json` (--bakecheck).</summary>
    public static void WriteSites()
    {
        if (_recorded.Count == 0) return;
        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(WorldDir));
        // merged: sites not recorded this run keep their record (a run that recorded none
        // once wrote an empty file over all seven)
        var json = FileAccess.FileExists(Scratch("bake_fed.json"))
            ? (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString(Scratch("bake_fed.json")))
            : new Godot.Collections.Dictionary();
        foreach (var (site, es) in _recorded)
        {
            foreach (var e in es) if (e.Lamp != null) e.Xf = e.Lamp.GlobalTransform;
            var path = SitePath(site);
            if (FileAccess.FileExists(path))
            {
                var dir = Scratch($"bake_backup/{Time.GetDateStringFromSystem()}");
                DirAccess.MakeDirRecursiveAbsolute(dir);
                DirAccess.CopyAbsolute(ProjectSettings.GlobalizePath(path), dir.PathJoin($"{site}.tscn"));
            }
            Write(site, es);
            var back = Load(site) ?? new List<Entry>();
            var line = Compare(Raw(es), Raw(back), out var ok);
            _bakedRoot?.Free();
            _bakedRoot = null;
            GD.Print($"bake: wrote {path}; read back {line} -> {(ok ? "PASS" : "FAIL")}");
            var rows = new Godot.Collections.Array();
            foreach (var e in es)
            {
                var p = e.F == "breakable" ? new Vector3(e.Xf.Origin.X, WorldGen.Height(e.Xf.Origin.X, e.Xf.Origin.Z), e.Xf.Origin.Z) : e.Xf.Origin;
                rows.Add(new Godot.Collections.Array { e.F, e.Kind, p.X, p.Y, p.Z, Yaw(e.Xf.Basis), e.Xf.Basis.X.Length() });
            }
            json[site] = rows;
        }
        using var f = FileAccess.Open(Scratch("bake_fed.json"), FileAccess.ModeFlags.Write);
        f.StoreString(Json.Stringify(json, "", true, true));   // full precision: the check is to 1 mm
    }

    private static void Write(string site, List<Entry> es)
    {
        var root = new Node3D { Name = site };
        var nodes = new Node3D[es.Count];
        for (var i = 0; i < es.Count; i++)
        {
            var e = es[i];
            Node3D n;
            if (e.Lamp != null)
            {
                var l = (LampLight)e.Lamp.Duplicate();
                l.Visible = true;
                n = l;
            }
            else if (e.F == "route")
            {
                var c = new Curve3D();
                foreach (var p in e.Meta["pts"].AsVector3Array()) c.AddPoint(p);
                n = new Path3D { Curve = c };
            }
            else if (e.Kit == "")
                n = new Marker3D();
            else
            {
                var prefab = $"{Root}{e.Kit}/{e.Kind}.tscn";
                n = e.Kit != "" && ResourceLoader.Exists(prefab) ? GD.Load<PackedScene>(prefab).Instantiate<Node3D>() : new Piece { Kit = e.Kit, Kind = e.Kind };
            }
            n.Name = $"{e.Kind}_{i}";
            n.Transform = e.Of >= 0 ? nodes[e.Of].Transform.AffineInverse() * e.Xf : e.Xf;
            n.SetMeta("f", e.F);
            foreach (var (k, v) in e.Meta)
                if (!(e.F == "route" && (string)k == "pts")) n.SetMeta((string)k, v);   // a route's points are its curve
            (e.Of >= 0 ? nodes[e.Of] : root).AddChild(n);
            n.Owner = root;
            nodes[i] = n;
        }
        var funnels = new Godot.Collections.Array<string>(es.Select(e => e.F).Concat(_calledBy.GetValueOrDefault(site) ?? new HashSet<string>()).Distinct().OrderBy(f => f));
        root.SetMeta("funnels", funnels);
        Save(root, SitePath(site), own: false);
        root.Free();
    }

    /// <summary>A baked site's placements, or null if it has none. The scene is instanced but
    /// never added to the tree, so no Piece loads its visual; its lamps are moved out whole.</summary>
    private static List<Entry>? Load(string site)
    {
        var path = SitePath(site);
        if (!FileAccess.FileExists(path)) return null;
        return LoadFrom(GD.Load<PackedScene>(path).Instantiate<Node3D>());
    }

    /// <summary>A baked site's placements from its root (a file's instance, or its node in
    /// world.tscn); the root is freed at <see cref="End"/>.</summary>
    private static List<Entry> LoadFrom(Node3D root)
    {
        _bakedRoot = root;
        _loadedFunnels = root.HasMeta("funnels") ? root.GetMeta("funnels").AsGodotArray<string>() : null;
        var list = new List<Entry>();
        void Walk(Node n, Transform3D xf, int parent)
        {
            foreach (var c in n.GetChildren())
            {
                if (c is not Node3D c3) continue;
                var g = xf * c3.Transform;
                var meta = new Godot.Collections.Dictionary();
                foreach (var k in c3.GetMetaList()) meta[k] = c3.GetMeta(k);
                Entry? e = null;
                if (c is Piece pc)
                {
                    var f = meta.TryGetValue("f", out var fv) ? (string)fv
                        : pc.Kit switch { "citykit" => "city", "foliage" => "foliage", "village" => "village", "fauna" => "herd", "folk" => "folk", _ => "kit" };
                    e = new Entry { F = f, Kit = pc.Kit, Kind = pc.Kind, Xf = g, Meta = meta };
                }
                else if (c is LampLight l) e = new Entry { F = "lamp", Kind = "lamp", Xf = g, Meta = meta, Lamp = l };
                else if (c is Path3D p && p.Curve != null)
                {
                    var pts = new Vector3[p.Curve.PointCount];
                    for (var k = 0; k < pts.Length; k++) pts[k] = g * p.Curve.GetPointPosition(k);
                    meta["pts"] = pts;
                    e = new Entry { F = "route", Kind = "route", Xf = g, Meta = meta };
                }
                else if (c is Marker3D)
                    e = new Entry { F = meta.TryGetValue("f", out var fv) ? (string)fv : "emitter", Kind = meta.TryGetValue("kind", out var kv) ? (string)kv : c.Name, Xf = g, Meta = meta };
                var me = parent;
                if (e != null)
                {
                    e.Of = parent;
                    me = list.Count;
                    list.Add(e);
                }
                Walk(c, g, me);
            }
        }
        Walk(root, Transform3D.Identity, -1);
        return list;
    }

    /// <summary>--bakecheck: what the funnels were given from the baked scenes against what
    /// the generators gave them when the scenes were written (scratch/bake_fed.json).</summary>
    public static void CheckFed()
    {
        var path = Scratch("bake_fed.json");
        if (!FileAccess.FileExists(path)) { GD.PushError("bakecheck: no scratch/bake_fed.json (run --bake first)"); return; }
        var json = (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString(path));
        foreach (var (site, fed) in _fed)
        {
            if (!json.TryGetValue(site, out var rv))
            {
                // no generated record to hold it to: at least every baked placement reached its funnel
                var l = Compare(_want[site], fed, out var k);
                GD.Print($"bakecheck {site} (vs its baked scene; no generated record): {l}, {_unused.GetValueOrDefault(site)} unused -> {(k && _unused.GetValueOrDefault(site) == 0 ? "PASS" : "DIFF")}");
                continue;
            }
            var rec = ((Godot.Collections.Array)rv).Select(r => (Godot.Collections.Array)r)
                .Select(r => new Fed((string)r[0], (string)r[1], new Vector3((float)r[2], (float)r[3], (float)r[4]), (float)r[5], (float)r[6])).ToList();
            var line = Compare(rec, fed, out var ok);
            var unused = _unused.GetValueOrDefault(site);
            GD.Print($"bakecheck {site}: generated {line}, {unused} unused -> {(ok && unused == 0 ? "PASS" : "DIFF")}");
        }
    }
}
