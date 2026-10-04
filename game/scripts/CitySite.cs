using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Emberglass in the game, from <see cref="CityPlan"/>: the city kit placed
/// building by building (<see cref="CityKit"/>, MultiMeshes per asset per
/// 60 m tile, a grey-box stand-in past 140 m), the curtain wall with its
/// towers and gates, bridges, docks, ships and falls, retaining blocks on
/// every level change, embankment ramps and stairs where streets change
/// level, the water, the dressing. Then the plan's eight checks and a map
/// laid beside the master plan sheet (`--citymap`), and a capture tour of
/// the quarters (`--citytour`).
/// </summary>
public partial class CitySite : Node3D
{
    public static bool WriteMap;
    public static bool Tour;
    public static bool BuildOnly;
    /// <summary>Kit draw range (buildings, structures) and props', metres; the
    /// grey-box stand-in takes over at the first. `--cityrange=near,props`.</summary>
    public static float NearRange = 95f, PropRange = 55f;

    private static bool _inCity;

    /// <summary>The sun's soft-shadow filter inside the city (`--cityshadowq=N`). Soft High, not
    /// Very Low (2026-09-30, user: "the whole city is hazy ... the graphics are fucked up"):
    /// Very Low's few taps drew per-pixel noise on every lit wall and stone, `--noiseshots`
    /// measured 6.18 (Very Low), 4.56 (Low), 3.54 (Medium), 2.91 (High), 2.57 (hard shadows).</summary>
    // Soft Low under FSR 2 (2026-09-30, later): its temporal pass resolves the taps' grain that
    // Very Low left at 720p without it; High cost 4.5 ms of GPU at 1440p
    public static RenderingServer.ShadowQuality InsideShadow = RenderingServer.ShadowQuality.SoftLow;

    /// <summary>Called every frame with the player's position. Inside the city
    /// the sun's soft-shadow filter drops to Very Low: the city frame is lit
    /// wall and roof edge to edge, and filtering every pixel cost 1.3 ms of GPU
    /// at the market (bench 2026-09-24: 9.38 -> 8.05). Outside, the project's
    /// default (Soft Low) comes back, so the village keeps its look.</summary>
    public static void Region(Vector3 p)
    {
        var inside = CityPlan.ToPlan(p.X, p.Z).Length() < CityPlan.Outer;
        if (inside == _inCity) return;
        _inCity = inside;
        RenderingServer.DirectionalSoftShadowFilterSetQuality(inside ? InsideShadow : RenderingServer.ShadowQuality.SoftLow);
        // the tone mapper is not blended (Weather blends the rest): the city's
        // AgX (2026-09-29) switches at the wall, where the city is its own plateau
        if (Env != null) Env.TonemapMode = Grade.Tonemapper(inside ? Grade.CityL.Tone : Grade.L.Tone);
        Cut(inside);
    }

    /// <summary>The frame-budget cuts applied only inside the city (the
    /// village's look was measured and stays): a comma list of `vfog`
    /// (volumetric fog off), `ssaolow`, `ssao` (off), `msaa` (off), `glow`
    /// (off). `--citycuts=...` overrides; `--citycuts=none` prices raw.</summary>
    // 2026-09-24 night (the user's parked "SSAO off or MSAA off" call, made
    // alone): SSAO off + a 2048 sun atlas, priced in one launch: market GPU
    // 7.52 -> 5.70 ms, frame p99 9.61 -> 8.17. MSAA stays: without it the
    // window mullions broke into dashes. Full frames looked the same; the
    // 2048 atlas shows some shadow noise on the fountain's basin up close.
    public static string Cuts = "ssao,shadow2k";
    public static Godot.Environment? Env;
    public static Viewport? Port;

    /// <summary>Re-apply the cuts for where the player is (after a bench
    /// switch undid one).</summary>
    public static void Reapply() => Cut(_inCity);

    private static void Cut(bool inside)
    {
        if (Env == null) return;
        var set = new HashSet<string>(Cuts.Split(',', System.StringSplitOptions.RemoveEmptyEntries));
        if (set.Contains("vfog")) Env.VolumetricFogEnabled = !inside && Grade.L.VFog > 0f;
        if (set.Contains("ssaolow"))
            RenderingServer.EnvironmentSetSsaoQuality(inside ? RenderingServer.EnvironmentSsaoQuality.Low : RenderingServer.EnvironmentSsaoQuality.Medium, true, 0.5f, 2, 50f, 300f);
        if (set.Contains("ssao")) Env.SsaoEnabled = !inside;
        if (set.Contains("glow")) Env.GlowEnabled = !inside;
        if (set.Contains("msaa") && Port != null) Port.Msaa3D = inside ? Viewport.Msaa.Disabled : Viewport.Msaa.Msaa2X;
        // the sun's shadow atlas at 2048 in the city (4096 default): the cloud
        // caster covers the whole map in both cascades, and its discard defeats
        // early-z -- the fill is the cloud cost. 2048 over the near cascade is
        // still ~2x the kit's 52 texels/m.
        if (set.Contains("shadow2k")) RenderingServer.DirectionalShadowAtlasSetSize(inside ? 2048 : 4096, true);
    }
    /// <summary>`--nosmoke`: no chimney smoke (a bench switch).</summary>
    public static bool NoSmoke;
    /// <summary>`--oldstreet`: the Voronoi cobbles and no kerbs, the street
    /// before 2026-09-29.</summary>
    public static bool OldStreet;
    /// <summary>`--nofolk`: no townsfolk or town animals (a harness switch:
    /// the solid people stop walk probes that have nothing to do with geometry).</summary>
    public static bool NoFolk;
    /// <summary>The streets' running-bond setts, laid along each road
    /// (`--setts=surface` to try another; null = the triplanar Voronoi cobbles).
    /// 0.60 x 0.30 m by the user's pick: the guide's 0.30 x 0.15 measured
    /// noisier than the cobbles, these calmer (findings 2026-09-29).</summary>
    public static string? Setts = "setts_lg";
    /// <summary>One point per kerb run, for the city walk's crossing test: the
    /// kerb's outer edge (plan), the outward normal, the road's floor level.</summary>
    public static readonly List<(Vector2 Edge, Vector2 N, float Level)> KerbProbes = new();
    /// <summary>`--noghost`: no occluder test at all (a bench switch).</summary>
    public static bool NoGhost;
    /// <summary>`--cityfade`: fade the kit out over a 15 m band instead of a hard switch (A/B).</summary>
    public static bool Fade;
    /// <summary>`--citynocast=blocks,proxies`: which casters to drop (A/B).</summary>
    public static string NoCast = "";
    public static System.Action<float, float>? TeleportTo;
    /// <summary>Teleport to an exact (x, y, z) -- onto a raised road.</summary>
    public static System.Action<float, float, float>? TeleportToY;
    private static int _view;

    public static Vector2 View(int i)
    {
        _view = (i % CityPlan.Views.Length + CityPlan.Views.Length) % CityPlan.Views.Length;
        GD.Print($"city: travel -> {CityPlan.Views[_view].Name}");
        return CityPlan.ToWorld(CityPlan.Views[_view].P);
    }

    public static Vector2 NextView() => View(_view + 1);

    private static readonly string[] Manifests =
        { "res://assets/models/citykit/city_manifest.json", "res://assets/models/kit/kit_manifest.json" };

    /// <summary>Per asset, from the kit build (build_city.py): its lamp
    /// points (every M_Lamp cluster) and chimney tops, in its own space.</summary>
    private static readonly Dictionary<string, Vector3[]> LampPts = new(), SmokePts = new();
    /// <summary>Per building kind, the front wall of each storey house()
    /// built: (storey, floor height, front wall z, x0, x1), asset space.</summary>
    private static readonly Dictionary<string, (int F, float Z, float Zf, float X0, float X1)[]> FrontPts = new();

    private static Dictionary<string, Vector3> Sizes()
    {
        var d = new Dictionary<string, Vector3>();
        foreach (var path in Manifests)
        {
            var j = (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString(path));
            foreach (var (k, v) in j)
            {
                var e = (Godot.Collections.Dictionary)v;
                var s = (Godot.Collections.Array)e["size"];
                d[(string)k] = new Vector3((float)s[0], (float)s[1], (float)s[2]);
                LampPts[(string)k] = Pts(e, "lamps");
                SmokePts[(string)k] = Pts(e, "smoke");
                if (e.ContainsKey("front"))
                {
                    var fa = (Godot.Collections.Array)e["front"];
                    var fr = new (int, float, float, float, float)[fa.Count];
                    for (var i = 0; i < fa.Count; i++)
                    {
                        var q = (Godot.Collections.Array)fa[i];
                        fr[i] = ((int)q[0], (float)q[1], (float)q[2], (float)q[3], (float)q[4]);
                    }
                    FrontPts[(string)k] = fr;
                }
            }
        }
        return d;
    }

    private static Vector3[] Pts(Godot.Collections.Dictionary e, string key)
    {
        if (!e.ContainsKey(key)) return System.Array.Empty<Vector3>();
        var a = (Godot.Collections.Array)e[key];
        var o = new Vector3[a.Count];
        for (var i = 0; i < a.Count; i++)
        {
            var p = (Godot.Collections.Array)a[i];
            o[i] = new Vector3((float)p[0], (float)p[1], (float)p[2]);
        }
        return o;
    }

    /// <summary>One placed asset: plan position, the way its front (+Z)
    /// faces -- or, `Along`, the way its length (+X) runs -- the level its
    /// foot stands at, a scale, and what it collides as.</summary>
    private readonly record struct Place(string Kind, Vector2 P, Vector2 Dir, float Y, Vector3 Scale, Col Col, bool Along = false, int Of = -1);

    private enum Col { None, Box, Wall, Tower, Gate, WaterGate, Bridge, Prop, Deck, Arm }

    private static readonly HashSet<string> Landmark = new()
        { "keep", "church", "gatehouse", "water_gate", "lighthouse", "windmill", "tower_round", "tower_square", "wall_run", "watchtower", "waterfall" };

    /// <summary>Top of a pier's or dock platform's deck (placed at Sea + 0.3, the deck 1.28 up).</summary>
    private const float DeckTop = CityPlan.Sea + 0.3f + 1.28f;
    /// <summary>Props standing on a deck (validate 9 exempts them: the ground under is the sea bed).</summary>
    private readonly List<Vector2> Decks = new();
    /// <summary>Each pier's end and its seaward direction (a fisher stands there).</summary>
    private readonly List<(Vector2 P, Vector2 Sea)> PierEnds = new();
    private float _lc;
    private readonly List<Place> _places = new();
    private List<CityPlan.Bldg> _blds = new();
    private List<CityPlan.Prop> _props = new();
    private Dictionary<string, Vector3> _sizes = new();
    private readonly List<CityPlan.Edge> _edges = new();

    public void Build()
    {
        var t0 = Time.GetTicksMsec();
        var lap = t0;
        void Lap(string what) { var now = Time.GetTicksMsec(); GD.Print($"city: {what} {now - lap} ms"); lap = now; }
        var sizes = _sizes = Sizes();
        (_blds, _props) = CityPlan.Layout(sizes);
        Buildings = _blds;
        Lap("layout");
        _lc = CityPlan.BaseLevel();
        // What the camera leans toward (CameraRig.Pull): the fountain, the
        // true landmarks, the falls -- not every barracks and watchtower, or
        // the pull would never let go.
        var poi = new Dictionary<string, float> { ["guildhouse"] = 0.3f, ["church"] = 0.35f, ["chapel"] = 0.25f, ["keep"] = 0.35f, ["windmill"] = 0.25f, ["manor_a"] = 0.25f, ["manor_b"] = 0.25f };
        void Interest(Vector2 plan, float level, float weight)
        {
            var w = CityPlan.ToWorld(plan);
            CameraRig.Interests.Add(new CameraRig.Interest(new Vector3(w.X, _lc + level + 2f, w.Y), 6f, 28f, weight));
        }
        Interest(Vector2.Zero, CityPlan.Level(CityPlan.Quarter.Market), 0.35f);
        foreach (var (kind, at, _, q) in CityPlan.Landmarks)
            if (poi.TryGetValue(kind, out var wt)) Interest(at, CityPlan.Level(q), wt);
        foreach (var f in CityPlan.Falls) Interest(f.At, f.Foot + 1f, 0.3f);
        var bigProp = new HashSet<string> { "fountain", "market_stall_a", "market_stall_b", "wagon", "crane", "statue_knight", "well", "hay_stack", "cart" };
        foreach (var b in _blds) _places.Add(new Place(b.Kind, b.P, b.Front, b.Level, Vector3.One, Col.Box));
        foreach (var p in _props) _places.Add(new Place(p.Kind, p.P, p.Front, p.Level, Vector3.One, bigProp.Contains(p.Kind) ? Col.Prop : Col.None));
        Mounts();
        Structures();
        Waystones();
        if (Bake.Site != null) BakeCity();
        var ghosted = new HashSet<string>(_blds.Select(b => b.Kind)) { "wall_run", "tower_round", "tower_square", "gatehouse", "water_gate", "lighthouse", "crane", "market_stall_a", "market_stall_b", "tree_broad", "tree_slim",
            "wall_corner", "watchtower", "stall_c", "large_stall", "harbour_hut", "shed" };
        _ghostKinds = NoGhost ? new HashSet<string>() : ghosted;
        if (NoGhost) ghosted.Clear();
        CityKit.Load(_places.Select(p => p.Kind).Distinct(), ghosted);
        Lap("kit load");

        var body = new StaticBody3D { Name = "City_Solid" };
        AddChild(body);
        Instances(body);
        Lap("instances");
        FarLod();
        Roads(body);
        Lap("roads");
        _edges.AddRange(CityPlan.Edges());
        PlanStairs();
        Edges = _edges;
        Blocks(body);
        OldStairs(body);
        Lap("edges + blocks");
        GrassClear();
        Water();
        Spray();
        Lamps();
        if (!NoSmoke) Smoke();
        GD.Print($"city: {_blds.Count} buildings, {_props.Count} props, {_places.Count} placed, {CityKit.LayerCount} surfaces, "
                 + $"{_edges.Count} retaining blocks, built in {Time.GetTicksMsec() - t0} ms");
        Validate();
        Lap("validate");
        if (WriteMap) Map();
        Lap("map");
    }

    /// <summary>Records the placements for a baked scene, or replaces them (and the buildings
    /// they carry) with the baked ones. Everything after -- kit load, instances, colliders,
    /// ghosts, lamps, grass, validate, <see cref="Buildings"/> -- reads the replaced lists.
    /// Roads, retaining blocks and water stay from CityPlan.</summary>
    private void BakeCity()
    {
        if (!Bake.Replaying)
        {
            Bake.CityStart();
            for (var i = 0; i < _places.Count; i++)
            {
                var p = _places[i];
                Bake.RecordCity(p.Kind, Xf(p), (int)p.Col, p.Along, i < _blds.Count ? i : -1, i, p.Of);
            }
            return;
        }
        var kinds = _blds.Select(b => b.Kind).ToHashSet();
        var blds = new List<CityPlan.Bldg>();
        _places.Clear();
        foreach (var e in Bake.CityEntries())
        {
            var o = e.Xf.Origin;
            var bs = e.Xf.Basis;
            var scale = new Vector3(bs.X.Length(), bs.Y.Length(), bs.Z.Length());
            var along = e.Flag("along", false);
            // the world direction Xf turned toward: front (+Z) or, along, length (+X)
            var d = along ? bs.X / scale.X : bs.Z / scale.Z;
            var at = CityPlan.ToPlan(o.X, o.Z);
            var dir = CityPlan.ToPlan(o.X + d.X, o.Z + d.Z) - at;
            var y = o.Y - _lc;
            var col = (Col)e.Int("col", (int)(kinds.Contains(e.Kind) ? Col.Box : Col.None));
            _places.Add(new Place(e.Kind, at, dir, y, scale, col, along));
            var b = e.Int("bldg", -1);
            if (b >= 0 && b < _blds.Count) blds.Add(_blds[b] with { P = at, Front = dir, Level = y });
        }
        _blds = blds;
        Buildings = _blds;
    }

    // ------------------------------------------------------------------ on the walls
    /// <summary>What hangs ON a front, placed on the wall itself (the kit
    /// records each storey's front plane, jetties included -- the eave box
    /// would float them 0.5 m off): hanging signs over the shops, taverns
    /// and smithies; timber balconies on the town houses' first floors;
    /// banners on the market's fronts; ladders against warehouses, stables
    /// and ruins. User plan items, 2026-09-24.</summary>
    private void Mounts()
    {
        var rng = new System.Random(606);
        int signs = 0, balconies = 0, banners = 0, ladders = 0;
        var bi = -1;   // the building's placement (buildings are the first entries of _places)
        foreach (var b in _blds)
        {
            bi++;
            if (!FrontPts.TryGetValue(b.Kind, out var fr) || fr.Length == 0) continue;
            var xf = Xf(new Place(b.Kind, b.P, b.Front, b.Level, Vector3.One, Col.None));
            var roll = rng.NextDouble();
            var ground = fr[0];
            var upper = fr.FirstOrDefault(f => f.F == 1);
            void Hang(string kind, float x, float y, float z)
            {
                var w = xf * new Vector3(x, y, z);
                _places.Add(new Place(kind, CityPlan.ToPlan(w.X, w.Z), b.Front, w.Y - _lc, Vector3.One, Col.None, Of: bi));
            }
            switch (b.Kind)
            {
                case "shop" or "tavern" or "townhouse_stall" or "townhouse_corner" or "blacksmith" or "merchant_house" when roll < 0.75:
                    // the prop's arm is 3.1 m up its own post: hung from the ground line
                    Hang("hanging_sign", ground.X1 - 0.7f, 0f, ground.Zf);
                    signs++;
                    break;
                case "warehouse" or "stables" or "barn" or "townhouse_damaged" when roll < 0.35:
                    Hang("ladder", ground.X0 + 1.1f, 0f, ground.Zf);
                    ladders++;
                    break;
            }
            if (upper.F == 1 && b.Kind is "tenement" or "townhouse_std" or "townhouse_narrow" or "townhouse_corner" or "alley_house"
                    or "city_house" or "townhouse_stone" or "townhouse_arched"
                && b.Q is CityPlan.Quarter.OldCity or CityPlan.Quarter.Riverside or CityPlan.Quarter.Market or CityPlan.Quarter.WestRes or CityPlan.Quarter.LowerCity
                && rng.NextDouble() < 0.35)
            {
                Hang("balcony", (upper.X0 + upper.X1) / 2f, upper.Z, upper.Zf);
                balconies++;
            }
            // blue banners beyond the market too (2026-09-30, the direction sheet), by a
            // hash of the site, so the rng above -- signs, ladders, balconies -- is unchanged
            var h = Mathf.PosMod(Mathf.Sin(b.P.X * 12.9898f + b.P.Y * 78.233f) * 43758.5453f, 1f);
            if (upper.F == 1 && b.Q is CityPlan.Quarter.OldCity or CityPlan.Quarter.Noble or CityPlan.Quarter.Craftsmen or CityPlan.Quarter.Citadel && h < 0.25f)
            {
                Hang("banner", upper.X0 + 0.5f, 0f, upper.Zf);
                banners++;
            }
            else if (upper.F == 1 && b.Q == CityPlan.Quarter.Market && rng.NextDouble() < 0.5)
            {
                // the banner's rod is 5.0 m up its own frame: hung from the ground line, at the corner pier
                Hang("banner", upper.X0 + 0.5f, 0f, upper.Zf);
                banners++;
            }
        }
        GD.Print($"city: on the walls: {signs} signs, {balconies} balconies, {banners} banners, {ladders} ladders");
    }

    // ------------------------------------------------------------------ structures
    private static Vector2 Out(int i)
    {
        var e = CityPlan.Encl;
        var ab = e[(i + 1) % e.Length] - e[i];
        var n = new Vector2(ab.Y, -ab.X).Normalized();
        var m = (e[i] + e[(i + 1) % e.Length]) / 2f;
        return CityPlan.InPoly(m + n * 2f, e) ? -n : n;
    }

    private void Structures()
    {
        var e = CityPlan.Encl;
        // gates on the wall: west (vertex 0), north (7), east (17) -- each at
        // the level of the road through it (the north gate stood at the
        // market's 7 m while its road ran through at the Noble terrace's 13)
        var gates = new[] { 0, 7, 17 };
        foreach (var g in gates)
        {
            var o = (Out((g - 1 + e.Length) % e.Length) + Out(g)).Normalized();
            var (_, _, lv) = OnRoad(e[g]);
            _places.Add(new Place("gatehouse", e[g], o, lv, Vector3.One, Col.Gate));
        }
        // the curtain wall: 8 m runs between the towers, clear of the gates and the water
        for (var i = 0; i < e.Length; i++)
        {
            if (!CityPlan.EdgeIsWall(i)) continue;
            Vector2 a = e[i], b = e[(i + 1) % e.Length];
            var o = Out(i);
            var len = (b - a).Length();
            var n = Mathf.Max(1, Mathf.RoundToInt(len / 8f));
            var piece = len / n;
            for (var k = 0; k < n; k++)
            {
                var m = a.Lerp(b, (k + 0.5f) / n);
                var nearGate = gates.Any(g => (m - e[g]).Length() < 10.5f);
                if (nearGate || CityPlan.IsWater(m) || CityPlan.IsWater(m - o * 3f)) continue;
                var lv = CityPlan.Level(CityPlan.QuarterAt(m - o * 5f));
                var foot = Mathf.Min(lv, CityPlan.Base(m + o * 5f));
                var sy = Mathf.Clamp((lv + 9.5f - foot) / 9.5f, 1f, 1.8f);
                _places.Add(new Place("wall_run", m, o, foot, new Vector3(piece / 8f * 1.02f, sy, 1f), Col.Wall));
                // a lantern post on the walk every other run, its lamp over the city side
                if (k % 2 == 1) _places.Add(new Place("lantern_post", m - o * 0.3f, -o, foot + 9.5f * sy, Vector3.One, Col.None));
            }
            // towers at the corners and every ~45 m
            var towers = Mathf.Max(1, Mathf.RoundToInt(len / 45f));
            for (var k = 0; k < towers; k++)
            {
                var p = a.Lerp(b, k / (float)towers);
                if (gates.Any(g => (p - e[g]).Length() < 12f) || CityPlan.IsWater(p)) continue;
                var lv = Mathf.Max(CityPlan.Level(CityPlan.QuarterAt(p - o * 5f)), CityPlan.Level(CityPlan.QuarterAt(p - o * 5f + (b - a).Normalized() * 6f)));
                var citadel = i >= 9 && i <= 13;
                _places.Add(new Place(citadel ? "tower_square" : "tower_round", p, o, lv, Vector3.One, Col.Tower));
            }
        }
        // the inner gates: the canal gate on the south road, the citadel gate
        // -- ON their road's centreline, turned along it, at its level. Set
        // square to the plan's axes they stood across their roads: the city
        // walk stuck at both (the citadel gate's side walls lay across the
        // Citadel road, 2026-09-24 night).
        foreach (var at in new[] { new Vector2(-4f, -35f), new Vector2(80f, 53.5f) })
        {
            var (c, d, lv) = OnRoad(at);
            _places.Add(new Place("gatehouse", c, d, lv, Vector3.One, Col.Gate));
        }
        // the canal's inner fortification: round towers along its north bank
        for (var x = -150f; x < 180f; x += 48f)
        {
            if (Mathf.Abs(x + 4f) < 14f) continue;
            _places.Add(new Place("tower_round", new Vector2(x, CityPlan.CanalY(x) + CityPlan.CanalHw + 3.5f), Vector2.Down, CityPlan.City, new Vector3(0.8f, 0.8f, 0.8f), Col.Tower));
        }
        // the water gate at the causeway's end
        _places.Add(new Place("water_gate", new Vector2(-5f, -149f), Vector2.Down, CityPlan.Lower, Vector3.One, Col.WaterGate));
        _places.Add(new Place("lighthouse", CityPlan.Isle, new Vector2(1f, 0.3f).Normalized(), CityPlan.Level(CityPlan.Quarter.Isle), Vector3.One, Col.Tower));
        // bridges where a road crosses water
        foreach (var rd in CityPlan.Roads)
        {
            if (rd.Kind is "track") continue;
            for (var i = 0; i < rd.P.Length; i++)
            {
                if (!rd.Wet[i]) continue;
                var j = i;
                while (j < rd.P.Length && rd.Wet[j]) j++;
                // sized to the wet run (first to last point over water) plus 1.5 m
                // of bearing each side; the half-wet segments either side are
                // road (Roads). Sized dry-to-dry, the flat deck ran on past the
                // point where a steep road had already started down off the bank
                // (South road: the walker stood 2.3 m over its stair).
                Vector2 a = rd.P[i], b = rd.P[Mathf.Min(j - 1, rd.P.Length - 1)];
                if ((b - a).Length() < 0.5f) { a = rd.P[Mathf.Max(i - 1, 0)]; b = rd.P[Mathf.Min(j, rd.P.Length - 1)]; }
                var span = (b - a).Length();
                var deck = rd.L[(i + j) / 2];   // flat across the run (CityPlan.Profile)
                var longOne = span > 26f;
                var (len, deckH, below) = longOne ? (37.4f, 4.6f, 3f) : (20f, 5.2f, 3f);
                var bed = CityPlan.Sea - 2.2f;
                CityPlan.WaterAt((a + b) / 2f, out var wl, out var wb);
                bed = wb - 0.5f;
                var sy = (deck - bed) / (deckH + below);
                var sx = (span + 3f) / len;
                var sz = rd.Hw * 2f / (longOne ? 5f : 4.5f);
                _places.Add(new Place(longOne ? "bridge_long" : "bridge_arch", (a + b) / 2f, (b - a).Normalized(),
                    deck - deckH * sy, new Vector3(sx, sy, sz), Col.Bridge, Along: true));
                if (OS.GetCmdlineUserArgs().Contains("--bridgedump"))
                {
                    GD.Print($"bridge: {rd.Name} wet {i}..{j - 1} span {span:F1} deck {deck:F2} len {len} sx {sx:F2} sy {sy:F2} centre ({((a + b) / 2f).X:F1},{((a + b) / 2f).Y:F1})");
                    for (var k = Mathf.Max(0, i - 4); k <= Mathf.Min(rd.P.Length - 1, j + 4); k++)
                        GD.Print($"bridge:   {k} ({rd.P[k].X:F1},{rd.P[k].Y:F1}) L {rd.L[k]:F2} base {CityPlan.Base(rd.P[k]):F2} wet {rd.Wet[k]} raised {rd.Raised[k]}");
                }
                i = j;
            }
        }
        // piers off the quays, ships alongside
        var rng = new System.Random(77);
        var quays = new[] { (new Vector2(-160f, -83.5f), new Vector2(-24f, -78.5f), CityPlan.Riverside), (new Vector2(10f, -121.5f), new Vector2(110f, -133f), CityPlan.Lower) };
        var q = 0;
        foreach (var (a, b, lv) in quays)
        {
            var dir = (b - a).Normalized();
            var sea = new Vector2(dir.Y, -dir.X);
            if (!CityPlan.IsWater((a + b) / 2f + sea * 8f)) sea = -sea;
            for (var t = 0f; t <= (b - a).Length(); t += 21f)
            {
                var root = a + dir * t + sea * CityPlan.EdgeHalf;
                _places.Add(new Place("pier", root, sea, CityPlan.Sea + 0.3f, Vector3.One, Col.Deck));
                // cargo on the deck (2026-09-30, "city life" plan: the harbour view looks down a
                // pier with nothing on it); a position hash picks, so the rng above stays
                var deck = new[] { "fish_barrels", "rope_coil", "net_stack", "barrels" };
                for (var k = 0; k < 3; k++)
                {
                    var h = Mathf.PosMod(Mathf.Sin(root.X * 7.13f + root.Y * 3.71f + k * 1.7f) * 43758.547f, 1f);
                    if (h < 0.3f) continue;
                    var at = root + sea * (3.2f + k * 3.1f) + dir * ((k % 2 == 0 ? 0.8f : -0.8f));
                    _places.Add(new Place(deck[(int)(h * 40f) % deck.Length], at, -dir * (k % 2 == 0 ? 1f : -1f), DeckTop, Vector3.One, Col.None));
                    Decks.Add(at);
                }
                PierEnds.Add((root + sea * 10.5f, sea));
                // a rowboat moored at the quay between each pair of piers
                var boat = a + dir * (t + 10.5f) + sea * (CityPlan.EdgeHalf + 1.3f);
                // 2026-09-30: every other gap on the lower quay is a dock platform with cargo
                if (lv == CityPlan.Lower && q % 2 == 1 && t + 10.5f < (b - a).Length() && CityPlan.IsWater(boat))
                    _places.Add(new Place("dock_platform", a + dir * (t + 10.5f) + sea * CityPlan.EdgeHalf, sea, CityPlan.Sea + 0.3f, Vector3.One, Col.Deck));
                else if (t + 10.5f < (b - a).Length() && CityPlan.IsWater(boat))
                {
                    _places.Add(new Place("rowboat", boat, dir.Rotated((q % 2 == 0 ? 1f : -1f) * 0.12f), CityPlan.Sea + 0.05f, Vector3.One, Col.None, Along: true));
                    Boats.Add((boat, -sea, lv));
                }
                // the fleet (2026-09-30): merchantmen and cargo cogs on the lower quay, fishing
                // boats, sailboats and barges on the river quay
                var k3 = q++ % 3;
                var ship = lv == CityPlan.Lower ? (k3 == 0 ? "ship_merchant" : k3 == 1 ? "ship_cargo" : "ship_fishing")
                                                : (k3 == 0 ? "sailboat" : k3 == 1 ? "ship_fishing" : "dock_barge");
                var (off, outd) = ship switch
                {
                    "ship_merchant" => (7.5f, 14f), "ship_cargo" => (6f, 11f), "sailboat" => (3f, 5f), "dock_barge" => (5f, 5.5f), _ => (4f, 7f),
                };
                _places.Add(new Place(ship, root + sea * outd + dir * off, sea, CityPlan.Sea + (ship == "dock_barge" ? 0.35f : 0.2f), Vector3.One, Col.None, Along: true));
            }
        }
        _places.Add(new Place("ship_merchant", new Vector2(-150f, -150f), new Vector2(0.9f, 0.4f).Normalized(), CityPlan.Sea + 0.2f, Vector3.One, Col.None, Along: true));
        _places.Add(new Place("ship_merchant", new Vector2(60f, -165f), new Vector2(-1f, 0.1f).Normalized(), CityPlan.Sea + 0.2f, Vector3.One, Col.None, Along: true));
        // harbour arms and the chain across the mouth
        foreach (var (a, b) in new[] { (new Vector2(118f, -140f), new Vector2(18f, -158f)), (new Vector2(-24f, -158f), new Vector2(-84f, -162f)) })
        {
            var dir = (b - a).Normalized();
            var n = Mathf.Max(1, Mathf.RoundToInt((b - a).Length() / 12f));
            for (var k = 0; k < n; k++)
                _places.Add(new Place("harbour_arm", a.Lerp(b, (k + 0.5f) / n), dir, CityPlan.Sea, new Vector3((b - a).Length() / n / 12f, 1f, 1f), Col.Arm, Along: true));
        }
        _places.Add(new Place("chain_boom", new Vector2(-96f, -161f), new Vector2(-1f, 0.2f).Normalized(), CityPlan.Sea, Vector3.One, Col.None, Along: true));
        // the falls
        foreach (var (_, at, dir, top, foot, width) in CityPlan.Falls)
            _places.Add(new Place("waterfall", at, dir, foot, new Vector3(width / 6f, (top - foot) / 10f, 1f), Col.None));
    }

    /// <summary>The road centreline point nearest `at` (plan), the road's
    /// direction there and its surface level.</summary>
    private static (Vector2 P, Vector2 Dir, float Level) OnRoad(Vector2 at)
    {
        var best = float.MaxValue;
        (Vector2, Vector2, float) r = (at, Vector2.Down, CityPlan.City);
        foreach (var rd in CityPlan.Roads)
        {
            if (rd.Kind == "track") continue;
            for (var i = 0; i + 1 < rd.P.Length; i++)
            {
                Vector2 a = rd.P[i], ab = rd.P[i + 1] - a;
                var t = Mathf.Clamp((at - a).Dot(ab) / Mathf.Max(ab.LengthSquared(), 1e-6f), 0f, 1f);
                var f = a + ab * t;
                var d = (f - at).Length();
                if (d < best) { best = d; r = (f, ab.Normalized(), Mathf.Lerp(rd.L[i], rd.L[i + 1], t)); }
            }
        }
        return r;
    }

    // ------------------------------------------------------------------ instancing
    private Transform3D Xf(Place p)
    {
        var w = CityPlan.ToWorld(p.P);
        var d = CityPlan.DirToWorld(p.Dir);
        var yaw = p.Along ? Mathf.Atan2(-d.Y, d.X) : Mathf.Atan2(d.X, d.Y);
        return new Transform3D(new Basis(Vector3.Up, yaw) * Basis.FromScale(p.Scale), new Vector3(w.X, _lc + p.Y, w.Y));
    }

    /// <summary>Each quarter's share of lit windows against the grade's
    /// `window_lit` (15 % in the city's afternoon, all at twilight): the
    /// market's shops and the manors burn more, the workshops and the
    /// warehouses less (user: "window lights varying by district").</summary>
    private static float LitShare(CityPlan.Quarter q) => q switch
    {
        CityPlan.Quarter.Market => 1.7f,
        CityPlan.Quarter.Noble => 1.9f,
        CityPlan.Quarter.Citadel => 1.4f,
        CityPlan.Quarter.Riverside => 1.3f,
        CityPlan.Quarter.OldCity => 1.1f,
        CityPlan.Quarter.WestRes => 1.0f,
        CityPlan.Quarter.LowerCity => 0.8f,
        CityPlan.Quarter.Farms => 0.7f,
        CityPlan.Quarter.Craftsmen => 0.5f,
        _ => 1f,
    };

    /// <summary>A dark house (2026-09-30, "city life" plan, item 3): 30 % of the Old City's
    /// side-street houses and 60 % of the alleys' keep one window in eight lit and
    /// their front lantern out (the shader's lamp glass steps off below 0.2, Lamps skips its
    /// light). The per-view gate measured the Old City at 7.6 % dark pixels, the sheet 9-30.
    /// A position hash, so no rng stream moves.</summary>
    private bool Dim(Place p)
    {
        if (!_houseKinds.Contains(p.Kind) || Landmark.Contains(p.Kind)) return false;
        // the Old City's side streets (30 %) and every alley (60 %); across all side streets
        // the Craftsmen view went 17.9 -> 45 % dark pixels, West Residential 36 -> 48
        var old = CityPlan.QuarterAt(p.P) == CityPlan.Quarter.OldCity;
        var h = Mathf.PosMod(Mathf.Sin(p.P.X * 12.9898f + p.P.Y * 78.233f) * 43758.547f, 1f);
        if (h >= 0.6f) return false;
        var bd = float.MaxValue;
        var kind = "";
        foreach (var rd in CityPlan.Roads)
            for (var i = 1; i < rd.P.Length; i++)
            {
                var d = CityPlan.SegDist(p.P, rd.P[i - 1], rd.P[i]) - rd.Hw;
                if (d < bd) { bd = d; kind = rd.Kind; }
            }
        return kind == "lane" || (old && kind == "street" && h < 0.3f);
    }

    private const float DimLit = 0.12f;
    private HashSet<string> _houseKinds = new();

    private void Instances(StaticBody3D body)
    {
        var rng = new System.Random(4242);
        _houseKinds = _blds.Select(b => b.Kind).ToHashSet();
        var pend = new List<(string Kind, Vector2I Tile, int I, Transform3D Xf)>();
        var groups = new Dictionary<(string, Vector2I), List<Transform3D>>();
        var lit = new Dictionary<(string, Vector2I), List<float>>();
        foreach (var p in _places)
        {
            if (!CityKit.Has(p.Kind)) continue;
            var xf = Xf(p);
            var tile = new Vector2I(Mathf.FloorToInt(xf.Origin.X / 60f), Mathf.FloorToInt(xf.Origin.Z / 60f));
            if (!groups.TryGetValue((p.Kind, tile), out var l)) { groups[(p.Kind, tile)] = l = new List<Transform3D>(); lit[(p.Kind, tile)] = new List<float>(); }
            if (_ghostKinds.Contains(p.Kind)) pend.Add((p.Kind, tile, l.Count, xf));
            l.Add(xf);
            lit[(p.Kind, tile)].Add(Dim(p) ? DimLit : LitShare(CityPlan.QuarterAt(p.P)));
            Collide(body, p, xf);
        }
        var mmis = new Dictionary<(string, Vector2I), (MultiMesh Main, MultiMesh? Ex)>();
        foreach (var ((kind, tile), list) in groups)
        {
            var a = CityKit.Get(kind);
            var centre = new Vector3((tile.X + 0.5f) * 60f, _lc, (tile.Y + 0.5f) * 60f);
            var isBig = _blds.Any(b => b.Kind == kind) || Landmark.Contains(kind) || kind.StartsWith("bridge") || kind.StartsWith("ship") || kind == "pier" || kind == "harbour_arm";
            var range = Landmark.Contains(kind) ? 0f : isBig ? NearRange : PropRange;
            var lk = lit[(kind, tile)];
            var main = Multi(kind, a.Mesh, a.Mat, list, centre, range, rng, GeometryInstance3D.ShadowCastingSetting.Off, lk);
            AddChild(main);
            MultiMeshInstance3D? ex = null;
            if (a.Extra != null) AddChild(ex = Multi(kind + "_extra", a.Extra, a.ExtraMat ?? a.Mat, list, centre, range, rng, GeometryInstance3D.ShadowCastingSetting.On, lk));
            mmis[(kind, tile)] = (main.Multimesh, ex?.Multimesh);
            // trees cast through their two-box proxies too: without a shadow a
            // yard tree read as pasted on (2026-09-24 night)
            if (a.Shadow != null && (isBig || kind.StartsWith("tree_")) && !NoCast.Contains("proxies"))
                AddChild(Multi(kind + "_shadow", a.Shadow, CityKit.ShadowMaterial, list, centre, range, rng, GeometryInstance3D.ShadowCastingSetting.ShadowsOnly));
        }
        foreach (var (kind, tile, i, xf) in pend)
        {
            var (mm, ex) = mmis[(kind, tile)];
            var g = new Gh(kind, xf, mm, ex, i, mm.GetInstanceTransform(i), mm.GetInstanceCustomData(i));
            var cell = new Vector2I(Mathf.FloorToInt(xf.Origin.X / GhCell), Mathf.FloorToInt(xf.Origin.Z / GhCell));
            if (!_ghGrid.TryGetValue(cell, out var gl)) _ghGrid[cell] = gl = new List<int>();
            gl.Add(_gh.Count);
            _gh.Add(g);
        }
    }

    // ------------------------------------------------------------------ occluders
    /// <summary>An instance that can stand between the camera and the player: its MultiMesh,
    /// its slot and its own transform and custom data (to restore it, and to draw its ghost).</summary>
    private sealed record Gh(string Kind, Transform3D Xf, MultiMesh Mm, MultiMesh? Ex, int I, Transform3D Local, Color Custom);
    private const float GhCell = 24f;
    private readonly List<Gh> _gh = new();
    private readonly Dictionary<Vector2I, List<int>> _ghGrid = new();
    /// <summary>Hidden instances: a ghost MeshInstance3D, or null when the camera is inside.</summary>
    private readonly Dictionary<int, MeshInstance3D?> _ghState = new();
    private readonly HashSet<int> _ghNow = new(), _ghGone = new();
    private HashSet<string> _ghostKinds = new();
    private static readonly Transform3D Zero = new(new Basis(Vector3.Zero, Vector3.Zero, Vector3.Zero), Vector3.Zero);

    /// <summary>The user's occluder rule (2026-09-23: blur and thin the whole object, never
    /// a hole), drawn see-through at last (2026-09-30, user: "clean this haze"): the kit
    /// shader used to discard 72 % of an occluder's pixels in a 4x4 screen-door, which at
    /// 720p upscaled read as a grid of dots. Each frame, the camera-to-player segment is
    /// tested against the boxes of the instances near it (the shader's own slab test); an
    /// occluder is hidden in its MultiMesh and drawn once, whole, at 30 % in the GHOST
    /// variant; the camera inside or within 4 m of a box hides it outright. Its shadow
    /// proxy keeps casting.</summary>
    private void Ghosts()
    {
        var cam = GetViewport().GetCamera3D();
        if (cam == null || _player == null) return;
        Vector3 a = cam.GlobalPosition, b = _player.GlobalPosition + Vector3.Up * 0.9f;
        _ghNow.Clear();
        _ghGone.Clear();
        var lo = new Vector2(Mathf.Min(a.X, b.X), Mathf.Min(a.Z, b.Z)) - Vector2.One * 18f;
        var hi = new Vector2(Mathf.Max(a.X, b.X), Mathf.Max(a.Z, b.Z)) + Vector2.One * 18f;
        for (var gx = Mathf.FloorToInt(lo.X / GhCell); gx <= Mathf.FloorToInt(hi.X / GhCell); gx++)
        for (var gz = Mathf.FloorToInt(lo.Y / GhCell); gz <= Mathf.FloorToInt(hi.Y / GhCell); gz++)
        {
            if (!_ghGrid.TryGetValue(new Vector2I(gx, gz), out var list)) continue;
            foreach (var i in list)
            {
                var g = _gh[i];
                var box = CityKit.Get(g.Kind).Box;
                var inv = g.Xf.AffineInverse();
                Vector3 la = inv * a, d = inv * b - la;
                var s = g.Xf.Basis.Scale;
                var m = new Vector3(4f / Mathf.Max(s.X, 1e-3f), 4f / Mathf.Max(s.Y, 1e-3f), 4f / Mathf.Max(s.Z, 1e-3f));
                if (new Aabb(box.Position - m, box.Size + 2f * m).HasPoint(la)) { _ghGone.Add(i); continue; }
                float enter = float.MinValue, leave = float.MaxValue;
                for (var k = 0; k < 3; k++)
                {
                    var dk = Mathf.Abs(d[k]) < 1e-5f ? 1e-5f : d[k];
                    float t0 = (box.Position[k] - la[k]) / dk, t1 = (box.End[k] - la[k]) / dk;
                    enter = Mathf.Max(enter, Mathf.Min(t0, t1));
                    leave = Mathf.Min(leave, Mathf.Max(t0, t1));
                }
                if (enter < leave && leave > 0f && enter < 0.97f) _ghNow.Add(i);
            }
        }
        foreach (var i in _ghState.Keys.ToArray())
            if (!_ghNow.Contains(i) && !_ghGone.Contains(i)) Restore(i);
        foreach (var i in _ghGone)
        {
            if (_ghState.TryGetValue(i, out var mi) && mi == null) continue;
            if (mi != null) { mi.QueueFree(); _ghState[i] = null; continue; }
            Hide(i);
            _ghState[i] = null;
        }
        foreach (var i in _ghNow)
        {
            if (_ghState.TryGetValue(i, out var mi) && mi != null) continue;
            if (!_ghState.ContainsKey(i)) Hide(i);
            var g = _gh[i];
            var ghost = new MeshInstance3D
            {
                Name = "Ghost", Mesh = CityKit.Get(g.Kind).Mesh, MaterialOverride = CityKit.GhostMat(g.Kind),
                CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            };
            AddChild(ghost);
            ghost.GlobalTransform = g.Xf;
            ghost.SetInstanceShaderParameter("ghost_custom", g.Custom);
            _ghState[i] = ghost;
        }
        GhostsShown = _ghState.Values.Count(v => v != null);
    }

    /// <summary>Ghosts drawn this frame (see-through occluders), for the capture harness.</summary>
    public static int GhostsShown;

    private void Hide(int i)
    {
        var g = _gh[i];
        g.Mm.SetInstanceTransform(g.I, Zero);
        g.Ex?.SetInstanceTransform(g.I, Zero);
    }

    private void Restore(int i)
    {
        var g = _gh[i];
        g.Mm.SetInstanceTransform(g.I, g.Local);
        g.Ex?.SetInstanceTransform(g.I, g.Local);
        _ghState[i]?.QueueFree();
        _ghState.Remove(i);
    }

    private static MultiMeshInstance3D Multi(string name, Mesh mesh, Material mat, List<Transform3D> list, Vector3 centre, float range,
        System.Random rng, GeometryInstance3D.ShadowCastingSetting cast, List<float>? lit = null)
    {
        var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseCustomData = true, Mesh = mesh, InstanceCount = list.Count };
        for (var i = 0; i < list.Count; i++)
        {
            var t = list[i];
            mm.SetInstanceTransform(i, new Transform3D(t.Basis, t.Origin - centre));
            var v = 0.93f + (float)rng.NextDouble() * 0.12f;
            mm.SetInstanceCustomData(i, new Color(v, v * (0.97f + (float)rng.NextDouble() * 0.05f), v * (0.95f + (float)rng.NextDouble() * 0.06f), lit?[i] ?? 1f));
        }
        var mi = new MultiMeshInstance3D { Name = name, Multimesh = mm, MaterialOverride = mat, Position = centre, CastShadow = cast };
        if (range > 0f)
        {
            mi.VisibilityRangeEnd = range;
            // a hard hand-over: a fading instance is drawn in the transparent pass,
            // which cost 1.2-1.6 ms of GPU at the market (bench 2026-09-24)
            mi.VisibilityRangeEndMargin = Fade ? 15f : 0f;
            mi.VisibilityRangeFadeMode = Fade ? GeometryInstance3D.VisibilityRangeFadeModeEnum.Self : GeometryInstance3D.VisibilityRangeFadeModeEnum.Disabled;
        }
        return mi;
    }

    private void Collide(StaticBody3D body, Place p, Transform3D xf)
    {
        CollisionShape3D Box(Vector3 size, Vector3 local) => new()
        {
            Shape = new BoxShape3D { Size = size },
            Transform = new Transform3D(xf.Basis.Orthonormalized(), xf * local),
        };
        var s = p.Scale;
        switch (p.Col)
        {
            case Col.Box:
            {
                var b = CityKit.Get(p.Kind).Box;
                body.AddChild(Box(new Vector3(Mathf.Max(b.Size.X - 1.2f, 1f), b.Size.Y * 0.75f, Mathf.Max(b.Size.Z - 1.2f, 1f)),
                    new Vector3(b.GetCenter().X, b.Size.Y * 0.375f, b.GetCenter().Z)));
                break;
            }
            case Col.Deck:
            {
                // a pier's or dock platform's plank deck (1.2 m up the asset, top at 1.28):
                // walkable, level with the lower quay (city life plan: the harbour view stands
                // out on a pier, the camera over the basin)
                var b = CityKit.Get(p.Kind).Box;
                body.AddChild(Box(new Vector3(Mathf.Max(b.Size.X - 0.3f, 1f), 0.3f, Mathf.Max(b.Size.Z - 0.2f, 1f)),
                    new Vector3(b.GetCenter().X, 1.13f, b.GetCenter().Z)));
                break;
            }
            case Col.Arm:
                // the breakwater's flagstone walk (top 2.2 m up the asset, 4.2 wide, the parapet
                // on the sea side, asset -Y = local +Z): walkable, a harbour view stands on it
                body.AddChild(Box(new Vector3(12f * s.X, 0.3f, 3.7f), new Vector3(0f, 2.05f, -0.2f)));
                body.AddChild(Box(new Vector3(12f * s.X, 1.6f, 0.5f), new Vector3(0f, 2.9f, 1.9f)));
                break;
            case Col.Prop:
            {
                var b = CityKit.Get(p.Kind).Box;
                body.AddChild(Box(b.Size * new Vector3(0.7f, 0.9f, 0.7f), b.GetCenter()));
                break;
            }
            case Col.Wall:
                // the wall walk is at 9.5 m x the run's height scale (the old box
                // stood 1 m proud of it at scale 1 and 7 m under it at 1.8);
                // and the crenellated outer parapet stops a walker stepping off
                body.AddChild(Box(new Vector3(8f * s.X, 10f * s.Y, 2.6f), new Vector3(0f, 4.5f, 0f)));
                body.AddChild(Box(new Vector3(8f * s.X, 1.8f, 0.4f), new Vector3(0f, 9.5f + 0.9f / s.Y, 1.1f)));
                break;
            case Col.Tower:
                body.AddChild(new CollisionShape3D { Shape = new CylinderShape3D { Radius = 3.2f * s.X, Height = 20f }, Position = xf.Origin + Vector3.Up * 9f });
                break;
            case Col.Gate:
                foreach (var x in new[] { -5.6f, 5.6f })
                    body.AddChild(new CollisionShape3D { Shape = new CylinderShape3D { Radius = 3.1f * s.X, Height = 20f }, Position = xf * new Vector3(x, 9f, 0.3f) });
                foreach (var x in new[] { -2.55f, 2.55f }) body.AddChild(Box(new Vector3(1.5f, 10f, 6.4f), new Vector3(x, 5f, 0f)));
                break;
            case Col.WaterGate:
                foreach (var x in new[] { -7.1f, 7.1f }) body.AddChild(Box(new Vector3(3.2f, 12f, 6f), new Vector3(x, 4f, 0f)));
                break;
            case Col.Bridge:
            {
                var b = CityKit.Get(p.Kind).Box;
                // the deck's own height in the asset (Structures: deckH), so the top is
                // deck + 0.02 m -- the road colliders' convention; from the asset's
                // parapet box it came out ~7 cm low, a lip at the South road's stair
                var deckH = p.Kind == "bridge_long" ? 4.6f : 5.2f;
                // exactly the wet run (the visual adds 1.5 m of bearing each side,
                // where the half-wet road segments already carry the walk from
                // the deck down): a flat box over a road already going down was
                // a ledge. The asset's raw length left 8 m gaps before that.
                body.AddChild(Box(new Vector3(Mathf.Max(b.Size.X * s.X - 3f, 1f), 0.4f, b.Size.Z * 0.8f * s.Z), new Vector3(b.GetCenter().X, deckH - 0.18f / s.Y, b.GetCenter().Z)));
                break;
            }
        }
    }

    /// <summary>Past 140 m every building is a box of its own size, walls and
    /// roof in the mean colours of its own surfaces (2026-09-29: they were
    /// grey boxes on the skyline) -- one draw for the whole city.</summary>
    /// <summary>Per 60 m tile, like the kit: a visibility range is measured
    /// from the node, so one city-wide stand-in switched on over the real
    /// houses anywhere 140 m from the fountain.</summary>
    private void FarLod()
    {
        var mesh = HouseMesh();
        var mat = new ShaderMaterial { Shader = new Shader { Code = FarCode } };
        static Color Mean(string s) { var m = TexLib.MeanLinear(s); return new Color(m.X, m.Y, m.Z); }
        var walls = new[] { "plaster", "ashlar", "brick", "fieldstone" }.Select(Mean).ToArray();
        mat.SetShaderParameter("walls", walls.Select(c => new Vector3(c.R, c.G, c.B)).ToArray());
        Color slate = Mean("slate"), clay = Mean("clay_tile"), thatch = Mean("thatch"), shingle = Mean("shingle"), slateBlue = Mean("slate_blue");
        var wrng = new System.Random(7);
        var tiles = new Dictionary<Vector2I, List<(Transform3D Xf, Color Roof)>>();
        foreach (var b in _blds)
        {
            var box = CityKit.Has(b.Kind) ? CityKit.Get(b.Kind).Box : new Aabb(new Vector3(-b.W / 2f, 0f, -b.D / 2f), new Vector3(b.W, b.H, b.D));
            var xf = Xf(new Place(b.Kind, b.P, b.Front, b.Level, Vector3.One, Col.None));
            xf = new Transform3D(xf.Basis * Basis.FromScale(new Vector3(box.Size.X * 0.9f, box.Size.Y, box.Size.Z * 0.9f)), xf.Origin);
            var roof = CityPlan.RoofOf(b.Kind) switch
            {
                "clay_tile" => clay, "shingle" => shingle, "thatch" => thatch, "slate_blue" => slateBlue, _ => slate,
            };
            // alpha: which wall colour (plaster most, then ashlar, brick, fieldstone)
            var w = wrng.NextDouble();
            roof.A = w < 0.45 ? 0.1f : w < 0.75 ? 0.35f : w < 0.92 ? 0.6f : 0.85f;
            var tile = new Vector2I(Mathf.FloorToInt(xf.Origin.X / 60f), Mathf.FloorToInt(xf.Origin.Z / 60f));
            if (!tiles.TryGetValue(tile, out var l)) tiles[tile] = l = new List<(Transform3D, Color)>();
            l.Add((xf, roof));
        }
        foreach (var (tile, list) in tiles)
        {
            var centre = new Vector3((tile.X + 0.5f) * 60f, _lc, (tile.Y + 0.5f) * 60f);
            var mm = new MultiMesh { TransformFormat = MultiMesh.TransformFormatEnum.Transform3D, UseCustomData = true, Mesh = mesh, InstanceCount = list.Count };
            for (var i = 0; i < list.Count; i++)
            {
                mm.SetInstanceTransform(i, new Transform3D(list[i].Xf.Basis, list[i].Xf.Origin - centre));
                mm.SetInstanceCustomData(i, list[i].Roof);
            }
            AddChild(new MultiMeshInstance3D
            {
                Name = "FarCity", Multimesh = mm, Position = centre, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
                MaterialOverride = mat, VisibilityRangeBegin = NearRange,
                VisibilityRangeFadeMode = GeometryInstance3D.VisibilityRangeFadeModeEnum.Disabled,
            });
        }
    }

    // ------------------------------------------------------------------ ground work
    private Vector3 W3(Vector2 plan, float rel)
    {
        var w = CityPlan.ToWorld(plan);
        return new Vector3(w.X, _lc + rel, w.Y);
    }

    private static void Tri(List<Vector3> v, Vector3 a, Vector3 b, Vector3 c, Vector3 outward)
    {
        if ((b - a).Cross(c - a).Dot(outward) < 0f) (b, c) = (c, b);
        v.Add(a); v.Add(c); v.Add(b);
    }

    private static void Quad(List<Vector3> v, Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 outward)
    {
        Tri(v, a, b, c, outward);
        Tri(v, a, c, d, outward);
    }

    /// <summary><see cref="Tri"/> carrying a UV per corner through its winding swap.</summary>
    private static void UvTri(List<Vector3> v, List<Vector2> uv, Vector3 a, Vector3 b, Vector3 c,
        Vector2 ta, Vector2 tb, Vector2 tc, Vector3 outward)
    {
        if ((b - a).Cross(c - a).Dot(outward) < 0f) { (b, c) = (c, b); (tb, tc) = (tc, tb); }
        v.Add(a); v.Add(c); v.Add(b);
        uv.Add(ta); uv.Add(tc); uv.Add(tb);
    }

    /// <summary>An upward-facing quad with a UV per corner.</summary>
    private static void UvQuad(List<Vector3> v, List<Vector2> uv, Vector3 a, Vector3 b, Vector3 c, Vector3 d,
        Vector2 ta, Vector2 tb, Vector2 tc, Vector2 td)
    {
        UvTri(v, uv, a, b, c, ta, tb, tc, Vector3.Up);
        UvTri(v, uv, a, c, d, ta, tc, td, Vector3.Up);
    }

    /// <summary>A coping along plan a-b on a wall of `half` width whose top is at
    /// `top` (2026-09-29, "too brutalist"): proud of both faces by 6 cm, its long
    /// top edges chamfered 5 cm, so the wall ends in a soft lit line and a thin
    /// shadow under the lip -- not a knife edge. Stone faces, a flagstone top.</summary>
    private void Coping(List<Vector3> sides, List<Vector3> caps, Vector2 a, Vector2 b, float half, float top)
    {
        const float Out = 0.06f, Ch = 0.05f, H = 0.16f;
        var along = (b - a).Normalized();
        var n = new Vector2(along.Y, -along.X);
        a -= along * Out; b += along * Out;
        float w = half + Out, lo = top - H + 0.02f, hi = top + 0.02f;
        var c = W3((a + b) / 2f, top);
        foreach (var sg in new[] { -1f, 1f })
        {
            var o = n * w * sg;
            var i = n * (w - Ch) * sg;
            var outw = W3(a + o * 2f, top) - W3(a, top);
            Quad(sides, W3(a + o, lo), W3(b + o, lo), W3(b + o, hi - Ch), W3(a + o, hi - Ch), outw);
            Quad(caps, W3(a + o, hi - Ch), W3(b + o, hi - Ch), W3(b + i, hi), W3(a + i, hi), outw + Vector3.Up * outw.Length());
        }
        var ti = n * (w - Ch);
        Quad(caps, W3(a - ti, hi), W3(b - ti, hi), W3(b + ti, hi), W3(a + ti, hi), Vector3.Up);
        foreach (var (e, d) in new[] { (a, -along), (b, along) })
        {
            var ow = W3(e + d, top) - W3(e, top);
            Quad(sides, W3(e - n * w, lo), W3(e + n * w, lo), W3(e + n * w, hi - Ch), W3(e - n * w, hi - Ch), ow);
            Quad(sides, W3(e - n * w, hi - Ch), W3(e + n * w, hi - Ch), W3(e + n * (w - Ch), hi), W3(e - n * (w - Ch), hi), ow);
        }
        _ = c;
    }

    /// <summary>Raised kerbs on a street segment's two edges (guide 2.1: 0.25 m
    /// wide, 0.14 m above the road), inside the road's width so the verge's
    /// grass, which grows to 2 cm off the road, leans against them. Cut in 2 m
    /// pieces: a joining road, a square, the plaza or water leaves a gap. The
    /// collider is a low ridge, not the kerb's box: the player has no step-up,
    /// and a 0.14 m face would stop them dead.</summary>
    private void Kerbs(CityPlan.Road rd, Vector2 a, Vector2 b, float la, float lb, float lift,
        List<Vector3> sides, List<Vector3> caps, List<Vector3> solid)
    {
        const float W = 0.25f, H = 0.14f, Piece = 2f;
        var len = (b - a).Length();
        var along = (b - a) / len;
        var pieces = Mathf.CeilToInt(len / Piece);
        foreach (var sgn in new[] { -1f, 1f })
        {
            var n = new Vector2(along.Y, -along.X) * sgn;
            for (var k = 0; k < pieces; k++)
            {
                float t0 = k / (float)pieces, t1 = (k + 1) / (float)pieces;
                Vector2 p0 = a.Lerp(b, t0), p1 = a.Lerp(b, t1);
                var edge = (p0 + p1) / 2f + n * rd.Hw;
                if (Joins(rd, edge) || CityPlan.IsWater(edge + n * 0.3f)) continue;
                // kerbs end at the gates: the roads out are country roads (and the
                // only two failed crossings of the 2026-09-29 walk were out there)
                if (CityPlan.QuarterAt(edge) == CityPlan.Quarter.Outside) continue;
                if (edge.Length() < CityPlan.PlazaR + 0.5f) continue;
                if (CityPlan.Squares.Any(q => (edge - q).Length() < CityPlan.SquareR + 0.5f)) continue;
                float h0 = Mathf.Lerp(la, lb, t0), h1 = Mathf.Lerp(la, lb, t1);
                Vector2 i0 = p0 + n * (rd.Hw - W), i1 = p1 + n * (rd.Hw - W), o0 = p0 + n * rd.Hw, o1 = p1 + n * rd.Hw;
                // every corner clear of every other road, not just the midpoint: at an
                // angled junction a piece whose middle cleared still lay across the
                // side road (user, 2026-09-29: "some tiles are glitchy")
                if (new[] { i0, i1, o0, o1 }.Any(c => OnRoad(rd, c, 0.1f))) continue;
                if (_courts.Any(c => (edge - c.P).Length() < c.R + 0.2f)) continue;
                // break round the street's furniture: validate 14 found 67 barrels,
                // crates, awnings and troughs standing on kerbs (and blocking the
                // walk's crossings)
                if (_props.Any(pr => !Overhead(pr.Kind) && _sizes.TryGetValue(pr.Kind, out var sz)
                                     && CityPlan.SegDist(pr.P, o0, o1) < 0.5f * Mathf.Max(sz.X, sz.Y) + 0.15f)) continue;
                if (k == pieces / 2) KerbProbes.Add((edge, n, (h0 + h1) / 2f - lift));
                _kerbPieces.Add((o0, o1, n, rd));
                // the outer face runs down into the verge, however far below the road it lies
                float g0 = CityPlan.Base(o0 + n * 0.3f), g1 = CityPlan.Base(o1 + n * 0.3f);
                float d0 = Mathf.Min(h0, g0) - 0.15f, d1 = Mathf.Min(h1, g1) - 0.15f;
                var outw = W3(o0 + n, h0) - W3(o0, h0);
                var fwd = W3(p1, h0) - W3(p0, h0);
                Quad(caps, W3(i0, h0 + H), W3(o0, h0 + H), W3(o1, h1 + H), W3(i1, h1 + H), Vector3.Up);
                Quad(sides, W3(i0, h0 - 0.05f), W3(i1, h1 - 0.05f), W3(i1, h1 + H), W3(i0, h0 + H), -outw);
                Quad(sides, W3(o0, d0), W3(o1, d1), W3(o1, h1 + H), W3(o0, h0 + H), outw);
                Quad(sides, W3(i0, h0 - 0.05f), W3(o0, d0), W3(o0, h0 + H), W3(i0, h0 + H), -fwd);
                Quad(sides, W3(i1, h1 - 0.05f), W3(o1, d1), W3(o1, h1 + H), W3(i1, h1 + H), fwd);
                // the ridge: up at ~22 deg from BELOW the road's floor (the plan level;
                // the drawn road floats `lift` above it, and a ramp starting above the
                // floor is the ledge that stopped the city walk at every ramp on
                // 2026-09-24; buried 0.1 m, it cannot be a ledge where the ground sits
                // a little under the plan level either) to the kerb's top, down to the
                // verge at no more than ~30 deg
                Vector2 r0 = p0 + n * (rd.Hw - W - 0.6f), r1 = p1 + n * (rd.Hw - W - 0.6f);
                Vector2 c0 = p0 + n * (rd.Hw - 0.05f), c1 = p1 + n * (rd.Hw - 0.05f);
                float run0 = Mathf.Max(0.35f, (h0 + H - g0) * 1.7f), run1 = Mathf.Max(0.35f, (h1 + H - g1) * 1.7f);
                Vector2 e0 = o0 + n * run0, e1 = o1 + n * run1;
                Quad(solid, W3(r0, h0 - lift - 0.1f), W3(r1, h1 - lift - 0.1f), W3(c1, h1 + H + 0.01f), W3(c0, h0 + H + 0.01f), Vector3.Up);
                Quad(solid, W3(c0, h0 + H + 0.01f), W3(c1, h1 + H + 0.01f), W3(e1, g1 + 0.02f), W3(e0, g0 + 0.02f), Vector3.Up);
            }
        }
    }

    /// <summary>A solid block from plan a to b, `half` each side, bottom to
    /// top; stone faces, a cap of `capMat` on top.</summary>
    private void Slab(List<Vector3> sides, List<Vector3> caps, Vector2 a, Vector2 b, float half, float bottom, float top, float batter = 0f)
    {
        var n = new Vector2((b - a).Y, -(b - a).X).Normalized() * half;
        Vector2[] q = { a - n, b - n, b + n, a + n };
        var c3 = W3((a + b) / 2f, (top + bottom) / 2f);
        // a batter leans the long faces back: the foot stands out by `batter` x the height
        var foot = n.Normalized() * batter * (top - bottom);
        Vector2[] qf = { a - n - foot, b - n - foot, b + n + foot, a + n + foot };
        var lo = qf.Select(p => W3(p, bottom)).ToArray();
        var hi = q.Select(p => W3(p, top)).ToArray();
        for (var k = 0; k < 4; k++)
        {
            var j = (k + 1) % 4;
            var mid = (lo[k] + lo[j] + hi[k] + hi[j]) / 4f;
            Quad(sides, lo[k], lo[j], hi[j], hi[k], mid - c3);
        }
        Quad(caps, hi[0], hi[1], hi[2], hi[3], Vector3.Up);
    }

    /// <summary>The streets: cobbled ribbons at each road's level; stairs
    /// where the road climbs steeper than a ramp; walled embankments where
    /// it runs above the ground; collision for everything raised.</summary>
    private void Roads(StaticBody3D body)
    {
        var cob = new List<Vector3>();
        var cobUv = new List<Vector2>();
        // streets and lanes are cobbled like the reference sheets (2026-09-30, part 2);
        // the main roads keep the large setts the user picked on 2026-09-29
        var lanes = new List<Vector3>();
        var dirt = new List<Vector3>();
        var stone = new List<Vector3>();
        var caps = new List<Vector3>();
        var kerb = new List<Vector3>();
        var kerbCap = new List<Vector3>();
        var solid = new List<Vector3>();
        // a dead end ends in a small paved court, not a square cut across the road
        // (user, 2026-09-29: "some end and are visible ending"; validate 12 listed 14)
        var courts = new List<Vector3>();
        foreach (var rd in CityPlan.Roads)
        {
            if (rd.Loop || rd.Kind == "track" || rd.P.Length < 2) continue;
            foreach (var (e, prev, lv) in new[] { (rd.P[0], rd.P[1], rd.L[0]), (rd.P[^1], rd.P[^2], rd.L[^1]) })
            {
                if (OnRoad(rd, e, 0.3f) || e.Length() < CityPlan.PlazaR + 1f || CityPlan.Squares.Any(q => (e - q).Length() < CityPlan.SquareR + 1f)) continue;
                if (CityPlan.QuarterAt(e) == CityPlan.Quarter.Outside || CityPlan.WallDist(e) < 8f || CityPlan.IsWater(e + (e - prev).Normalized() * 2f)) continue;
                var r = rd.Hw + 0.8f;
                _courts.Add((e, r));
                const int courtN = 24;
                for (var k = 0; k < courtN; k++)
                {
                    var d0 = new Vector2(Mathf.Cos(k * Mathf.Tau / courtN), Mathf.Sin(k * Mathf.Tau / courtN)) * r;
                    var d1 = new Vector2(Mathf.Cos((k + 1) * Mathf.Tau / courtN), Mathf.Sin((k + 1) * Mathf.Tau / courtN)) * r;
                    Tri(courts, W3(e, lv + 0.05f), W3(e + d0, lv + 0.05f), W3(e + d1, lv + 0.05f), Vector3.Up);
                }
            }
        }
        // The setts run along each road, so two roads crossing show two patterns
        // and would z-fight: each road lies at its own height, 1 mm apart, the
        // wider on top (a lane butts into the main road, not across it).
        var rank = CityPlan.Roads.OrderBy(r => r.Hw).Select((r, k) => (r, k)).ToDictionary(t => t.r, t => t.k);
        foreach (var rd in CityPlan.Roads)
        {
            var into = rd.Kind == "track" ? dirt : rd.Kind == "main" ? cob : lanes;
            var setts = into == cob && Setts != null;
            var n = rd.P.Length;
            var segs = rd.Loop ? n : n - 1;
            var s = 0f;   // metres along the road, for the setts' u
            for (var i = 0; i < segs; i++)
            {
                int j = (i + 1) % n;
                Vector2 a = rd.P[i], b = rd.P[j];
                var len = (b - a).Length();
                var u0 = s;
                s += len;
                if (len < 0.01f) continue;
                var side = new Vector2((b - a).Y, -(b - a).X).Normalized() * rd.Hw;
                // a track follows the ground, whose facets it must clear
                var lift = rd.Kind == "track" ? 0.15f : 0.06f + (setts || into == lanes ? 0.001f * rank[rd] : 0f);
                float la = rd.L[i] + lift, lb = rd.L[j] + lift;
                if (rd.Wet[i] && rd.Wet[j]) continue;   // the bridge carries it (a half-wet segment is road, from the deck down)
                var raised = rd.L[i] - CityPlan.Base(a) > 0.3f || rd.L[j] - CityPlan.Base(b) > 0.3f;
                if (rd.Kind != "track" && Mathf.Abs(lb - la) / len > 0.22f)
                {
                    // stairs: treads of <= 0.3 m risers. 2026-09-29 ("too brutalist"; the
                    // flight read as dark and light stripes): flagstone treads over ashlar
                    // risers with a 5 cm chamfered nosing between, a mid-tone step from the
                    // lit tread to the riser in shade; and each riser faces DOWN the flight
                    // (its outward pointed up it, into the step)
                    var steps = Mathf.CeilToInt(Mathf.Abs(lb - la) / 0.3f);
                    var up = (lb > la ? b - a : a - b).Normalized();
                    for (var k = 0; k < steps; k++)
                    {
                        Vector2 p0 = a.Lerp(b, k / (float)steps), p1 = a.Lerp(b, (k + 1) / (float)steps);
                        var h = Mathf.Lerp(la, lb, (k + (lb > la ? 1f : 0f)) / steps);
                        var hp = Mathf.Lerp(la, lb, (k + (lb > la ? 0f : 1f)) / steps);
                        var riser = lb > la ? p0 : p1;
                        var far = lb > la ? p1 : p0;
                        var back = riser + up * 0.05f;
                        var down = W3(riser - up, h) - W3(riser, h);
                        Quad(caps, W3(back - side, h), W3(back + side, h), W3(far + side, h), W3(far - side, h), Vector3.Up);
                        Quad(caps, W3(riser - side, h - 0.05f), W3(riser + side, h - 0.05f), W3(back + side, h), W3(back - side, h),
                            down + Vector3.Up * down.Length());
                        Quad(stone, W3(riser - side, hp), W3(riser + side, hp), W3(riser + side, h - 0.05f), W3(riser - side, h - 0.05f), down);
                    }
                }
                else
                {
                    if (setts)
                        UvQuad(cob, cobUv, W3(a - side, la), W3(a + side, la), W3(b + side, lb), W3(b - side, lb),
                            new Vector2(u0, -rd.Hw), new Vector2(u0, rd.Hw), new Vector2(u0 + len, rd.Hw), new Vector2(u0 + len, -rd.Hw));
                    else Quad(into, W3(a - side, la), W3(a + side, la), W3(b + side, lb), W3(b - side, lb), Vector3.Up);
                    if ((into == cob || into == lanes) && !raised && !OldStreet) Kerbs(rd, a, b, la, lb, lift, kerb, kerbCap, solid);
                }
                // Collision wherever the road stands at all above the ground, not
                // only on the embankment proper (> 0.3 m): the ramp's collider used
                // to start 0.3-0.36 m up, a ledge the player cannot step onto --
                // the city walk stuck at the foot of every ramp (2026-09-24 night).
                var lifted = rd.L[i] - CityPlan.Base(a) > 0.02f || rd.L[j] - CityPlan.Base(b) > 0.02f;
                if (lifted && rd.Kind != "track")
                    Quad(solid, W3(a - side, rd.L[i] + 0.02f), W3(a + side, rd.L[i] + 0.02f), W3(b + side, rd.L[j] + 0.02f), W3(b - side, rd.L[j] + 0.02f), Vector3.Up);
                if (!raised) continue;
                // the embankment's walls, with a parapet -- solid too: the ramp
                // was walkable off its side, a fall of up to 13 m
                foreach (var sgn in new[] { -1f, 1f })
                {
                    var off = side.Normalized() * (rd.Hw + 0.45f) * sgn;
                    // open where another road comes in on this side (a solid wall
                    // across a junction would close it)
                    if (Joins(rd, (a + b) / 2f + off)) continue;
                    var ground = Mathf.Min(CityPlan.Base(a + off), CityPlan.Base(b + off));
                    var top = Mathf.Max(la, lb) + 0.8f;
                    var n0 = stone.Count;
                    Slab(stone, caps, a + off, b + off, 0.45f, ground - 0.8f, top);
                    Coping(stone, caps, a + off, b + off, 0.45f, top);
                    for (var q = n0; q < stone.Count; q++) solid.Add(stone[q]);
                }
            }
        }
        // the market plaza
        var plaza = new List<Vector3>();
        const int kN = 40;
        for (var k = 0; k < kN; k++)
        {
            var p0 = new Vector2(Mathf.Cos(k * Mathf.Tau / kN), Mathf.Sin(k * Mathf.Tau / kN)) * CityPlan.PlazaR;
            var p1 = new Vector2(Mathf.Cos((k + 1) * Mathf.Tau / kN), Mathf.Sin((k + 1) * Mathf.Tau / kN)) * CityPlan.PlazaR;
            Tri(plaza, W3(Vector2.Zero, CityPlan.City + 0.04f), W3(p0, CityPlan.City + 0.04f), W3(p1, CityPlan.City + 0.04f), Vector3.Up);
        }
        // the small squares at the big junctions, paved like the plaza, just
        // under the road surface (the road draws over its own crossing)
        foreach (var sq in CityPlan.Squares)
        {
            var lv = CityPlan.Base(sq) + 0.03f;
            for (var k = 0; k < 24; k++)
            {
                var p0 = sq + new Vector2(Mathf.Cos(k * Mathf.Tau / 24), Mathf.Sin(k * Mathf.Tau / 24)) * CityPlan.SquareR;
                var p1 = sq + new Vector2(Mathf.Cos((k + 1) * Mathf.Tau / 24), Mathf.Sin((k + 1) * Mathf.Tau / 24)) * CityPlan.SquareR;
                Tri(plaza, W3(sq, lv), W3(p0, lv), W3(p1, lv), Vector3.Up);
            }
        }
        // the plaza's pattern: brick rings round the fountain, mid-way and at
        // the rim, and four diagonal spokes between them (it was one plain
        // flagstone disc); the four roads are the other spokes. Brick, not the
        // cobble it was built in: cobble is the same irregular stone as the
        // flagstone, a shade darker (mean luminance 91 vs 119), and the rings
        // did not read in the game frame (2026-09-25 tour_city_market)
        var pattern = new List<Vector3>();
        foreach (var (r0, r1) in new[] { (8.6f, 9.8f), (17f, 18f), (24.6f, 26f) })
            for (var k = 0; k < 64; k++)
            {
                float a0 = k * Mathf.Tau / 64f, a1 = (k + 1) * Mathf.Tau / 64f;
                Vector2 d0 = new(Mathf.Cos(a0), Mathf.Sin(a0)), d1 = new(Mathf.Cos(a1), Mathf.Sin(a1));
                Quad(pattern, W3(d0 * r0, CityPlan.City + 0.05f), W3(d1 * r0, CityPlan.City + 0.05f), W3(d1 * r1, CityPlan.City + 0.05f), W3(d0 * r1, CityPlan.City + 0.05f), Vector3.Up);
            }
        foreach (var a in new[] { 0.785f, 2.356f, 3.927f, 5.498f })
        {
            var d = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
            var w = new Vector2(-d.Y, d.X) * 0.45f;
            foreach (var (r0, r1) in new[] { (9.8f, 17f), (18f, 24.6f) })
                Quad(pattern, W3(d * r0 - w, CityPlan.City + 0.05f), W3(d * r0 + w, CityPlan.City + 0.05f), W3(d * r1 + w, CityPlan.City + 0.05f), W3(d * r1 - w, CityPlan.City + 0.05f), Vector3.Up);
        }
        // stairs up onto the wall walk: a stepped masonry flight against the
        // wall's inner face; a smooth ramp is its collider
        foreach (var (foot, head, inn, low, high) in CityPlan.WallStairs)
        {
            const int n = 32;
            var dir = (head - foot).Normalized();
            var side = inn * CityPlan.StairHalf;
            for (var k = 0; k < n; k++)
            {
                Vector2 p0 = foot.Lerp(head, k / (float)n), p1 = foot.Lerp(head, (k + 1) / (float)n);
                var h = Mathf.Lerp(low, high, (k + 1) / (float)n);
                Slab(stone, caps, p0, p1, CityPlan.StairHalf, low - 0.6f, h);
            }
            // a landing block at the head, against the wall
            Slab(stone, caps, head, head + dir * 1.6f, CityPlan.StairHalf, low - 0.6f, high);
            Quad(solid, W3(foot - side, low + 0.02f), W3(foot + side, low + 0.02f), W3(head + side, high), W3(head - side, high), Vector3.Up);
            Quad(solid, W3(head - side, high), W3(head + side, high), W3(head + side + dir * 1.6f, high), W3(head - side + dir * 1.6f, high), Vector3.Up);
        }
        AddChild(Setts == null ? Surface("CityRoads", cob, TexLib.Triplanar("cobble"))
                               : Surface("CityRoads", cob, cobUv, TexLib.Metres(Setts)));
        // cobble_hd, not cobble: the same stones at twice the texels, half the gradient per
        // texel -- cobble took the ground gate from 0.0268 to 0.0337 (2026-09-30)
        if (lanes.Count > 0) AddChild(Surface("CityLanes", lanes, TexLib.Triplanar("cobble_hd")));
        if (courts.Count > 0) AddChild(Surface("CityCourts", courts, TexLib.Triplanar("flagstone")));
        if (kerb.Count > 0)
        {
            AddChild(Surface("CityKerbs", kerb, TexLib.Triplanar("ashlar")));
            AddChild(Surface("CityKerbCaps", kerbCap, TexLib.Triplanar("flagstone")));
        }
        GD.Print($"CitySite: {CityPlan.Roads.Count} roads, kerbs {kerb.Count / 3} tris");
        AddChild(Surface("CityTracks", dirt, TexLib.Triplanar("dirt")));
        AddChild(Surface("CityStairs", stone, TexLib.Triplanar("ashlar")));
        AddChild(Surface("CityCaps", caps, TexLib.Triplanar("flagstone")));
        AddChild(Surface("CityPlaza", plaza, TexLib.Triplanar("flagstone")));
        AddChild(Surface("CityPlazaPattern", pattern, TexLib.Triplanar("paving_brick")));
        if (solid.Count > 0) body.AddChild(new CollisionShape3D { Shape = new ConcavePolygonShape3D { Data = solid.ToArray() } });
    }

    /// <summary>Does a road other than `rd` reach point p (within its half
    /// width + 1 m)?</summary>
    /// <summary>Is p on a road other than `rd` (inside its half width + margin)?</summary>
    private static bool OnRoad(CityPlan.Road rd, Vector2 p, float margin)
    {
        foreach (var o in CityPlan.Roads)
        {
            if (o == rd || o.Kind == "track") continue;
            var segs = o.Loop ? o.P.Length : o.P.Length - 1;
            for (var i = 0; i < segs; i++)
                if (CityPlan.SegDist(p, o.P[i], o.P[(i + 1) % o.P.Length]) < o.Hw + margin) return true;
        }
        return false;
    }

    /// <summary>The outer edge of every kerb piece built (plan), for validate 13-14.</summary>
    private readonly List<(Vector2 A, Vector2 B, Vector2 N, CityPlan.Road Rd)> _kerbPieces = new();
    /// <summary>The small paved courts at the roads' dead ends (plan centre, radius).</summary>
    private readonly List<(Vector2 P, float R)> _courts = new();

    private static bool Joins(CityPlan.Road rd, Vector2 p)
    {
        foreach (var o in CityPlan.Roads)
        {
            if (o == rd) continue;
            for (var i = 0; i + 1 < o.P.Length; i++)
                if (CityPlan.SegDist(p, o.P[i], o.P[i + 1]) < o.Hw + 1f) return true;
        }
        return false;
    }

    // ------------------------------------------------------------------ the Old City's stairs
    /// <summary>Stone flights from the Old City up its terrace walls to the Noble and
    /// Citadel terraces (user, 2026-09-30: "do the old city stairs"; the target sheet's
    /// Old City climbs in stairs between the houses). Each runs along the wall's low
    /// face like the city-wall stairs: ~20 cm risers, an outer wall, a landing at the
    /// top where the parapet opens, walkable collision. At most five, 28 m apart, on a
    /// straight level-topped face, clear of roads, houses and water.</summary>
    private readonly List<(Vector2 Foot, Vector2 Head, Vector2 Dir, Vector2 Out, float High)> _stairs = new();

    /// <summary>Spans strung across a road on two poles: their box is the road's, so the
    /// kerb break, validate 9 and validate 14 skip them.</summary>
    public static bool Overhead(string kind) => kind.StartsWith("bunting") || kind == "laundry_span";

    /// <summary>A wall from plan a to b, `half` each side, its top sloping from topA to
    /// topB (the stairs' parapet: per-step slabs read as a comb).</summary>
    private void SlopedWall(List<Vector3> sides, List<Vector3> caps, Vector2 a, Vector2 b, float half, float bottom, float topA, float topB)
    {
        var dir = (b - a).Normalized();
        var n = new Vector2(dir.Y, -dir.X) * half;
        Vector3 a0 = W3(a - n, bottom), a1 = W3(a + n, bottom), b0 = W3(b - n, bottom), b1 = W3(b + n, bottom);
        Vector3 a0t = W3(a - n, topA), a1t = W3(a + n, topA), b0t = W3(b - n, topB), b1t = W3(b + n, topB);
        var nw = W3(n, 0f) - W3(Vector2.Zero, 0f);
        var dw = W3(dir, 0f) - W3(Vector2.Zero, 0f);
        Quad(sides, a0, b0, b0t, a0t, -nw);
        Quad(sides, a1, a1t, b1t, b1, nw);
        Quad(sides, a0, a0t, a1t, a1, -dw);
        Quad(sides, b0, b1, b1t, b0t, dw);
        Quad(caps, a0t, a1t, b1t, b0t, Vector3.Up);
    }

    private static bool Inside(CityPlan.Bldg b, Vector2 p, float pad)
    {
        var d = p - b.P;
        return Mathf.Abs(d.Dot(new Vector2(b.Front.Y, -b.Front.X))) < b.W / 2f + pad && Mathf.Abs(d.Dot(b.Front)) < b.D / 2f + pad;
    }

    private void PlanStairs()
    {
        // CityPlan chose and reserved them before the houses; a site a house still
        // reached (a landmark's search) is dropped
        foreach (var st in CityPlan.StairSites)
            if (!_blds.Any(b => Inside(b, st.Foot, CityPlan.StairHalf) || Inside(b, st.Head, CityPlan.StairHalf)))
                _stairs.Add(st);
        // what stood on the flights' ground goes (props, not structures)
        foreach (var st in _stairs)
            _places.RemoveAll(pl => pl.Col is Col.None or Col.Prop && CityPlan.SegDist(pl.P, st.Foot - st.Dir * 0.6f, st.Head + st.Dir * 1.8f) < CityPlan.StairHalf + 0.9f);
        if (_stairs.Count > 0)
        {
            var s0 = _stairs[0];
            CityPlan.Views[^1] = ("Old City Stairs", (s0.Foot + s0.Head) / 2f + s0.Out * 7f);
        }
        GD.Print("city: old city stairs " + string.Join(", ", _stairs.Select(st => $"{CityPlan.QuarterAt(st.Foot)} ({st.Foot.X:F0},{st.Foot.Y:F0})->({st.Head.X:F0},{st.Head.Y:F0}) to {st.High:F1}")));
    }

    private void OldStairs(StaticBody3D body)
    {
        if (_stairs.Count == 0) return;
        var stone = new List<Vector3>();
        var caps = new List<Vector3>();
        var solid = new List<Vector3>();
        foreach (var (foot, head, dir, outN, high) in _stairs)
        {
            var low = CityPlan.Base(foot);
            var n = Mathf.Max(8, Mathf.RoundToInt((high - low) / 0.2f));
            var side = outN * CityPlan.StairHalf;
            var wallOff = outN * (CityPlan.StairHalf + 0.15f);
            for (var k = 0; k < n; k++)
            {
                Vector2 p0 = foot.Lerp(head, k / (float)n), p1 = foot.Lerp(head, (k + 1) / (float)n);
                var h = Mathf.Lerp(low, high, (k + 1) / (float)n);
                Slab(stone, caps, p0, p1, CityPlan.StairHalf, low - 0.6f, h);
            }
            SlopedWall(stone, caps, foot + wallOff, head + wallOff, 0.15f, low - 0.6f, low + 0.85f, high + 0.85f);
            var land = head + dir * 1.8f;
            Slab(stone, caps, head, land, CityPlan.StairHalf, low - 0.6f, high);
            Slab(stone, caps, head + wallOff, land + wallOff, 0.15f, low - 0.6f, high + 0.85f);
            Quad(solid, W3(foot - side, low + 0.02f), W3(foot + side, low + 0.02f), W3(head + side, high), W3(head - side, high), Vector3.Up);
            Quad(solid, W3(head - side, high), W3(head + side, high), W3(land + side, high), W3(land - side, high), Vector3.Up);
            var ow = W3(outN, 0f) - W3(Vector2.Zero, 0f);
            Quad(solid, W3(foot + wallOff, low), W3(land + wallOff, high), W3(land + wallOff, high + 0.9f), W3(foot + wallOff, low + 0.9f), ow);
            // a lamp at the foot, pots at the landing, the grass kept off the treads
            _places.Add(new Place("street_lamp", foot - dir * 0.9f + outN * 1.2f, -outN, low, Vector3.One, Col.None));
            // on the ground by the first step (on the landing, validate 9 measured them 6 m
            // above the street below)
            _places.Add(new Place("pots", foot - dir * 1.5f - outN * 0.2f, -outN, low, Vector3.One, Col.None));
            Grass.ClearSeg(CityPlan.ToWorld(foot - dir * 0.5f), CityPlan.ToWorld(land), CityPlan.StairHalf + 0.5f);
        }
        AddChild(Surface("CityOldStairs", stone, TexLib.Triplanar("ashlar")));
        AddChild(Surface("CityOldStairCaps", caps, TexLib.Triplanar("flagstone")));
        body.AddChild(new CollisionShape3D { Shape = new ConcavePolygonShape3D { Data = solid.ToArray() } });
    }

    /// <summary>Retaining blocks on every level change no road crosses: 6 m
    /// thick, so the terrain's step is always inside one; a flagstone cap,
    /// a parapet over drops of more than 2 m, a moss band at the foot.</summary>
    private void Blocks(StaticBody3D body)
    {
        var stone = new List<Vector3>();
        var caps = new List<Vector3>();
        var moss = new List<Vector3>();
        foreach (var e in _edges)
        {
            var dir = (e.B - e.A).Normalized();
            Vector2 a = e.A - dir * 0.15f, b = e.B + dir * 0.15f;
            // 2026-09-29 ("too brutalist"): a 2 % batter, a proud chamfered coping
            // on the low face, and a pilaster every ~7 m of a tall face -- the long
            // flat ashlar planes were the city's hardest shapes
            Slab(stone, caps, a, b, CityPlan.EdgeHalf, e.Low - 0.8f, e.High + 0.05f, 0.02f);
            var lowFace = -e.HighSide * CityPlan.EdgeHalf;
            Coping(stone, caps, a + lowFace, b + lowFace, 0.12f, e.High + 0.05f);
            var low = -e.HighSide * (CityPlan.EdgeHalf - 0.25f);
            var mid = (e.A + e.B) / 2f;
            var landing = _stairs.Any(st => CityPlan.SegDist(mid, st.Head - st.Dir * 0.5f, st.Head + st.Dir * 2.3f) < 4.6f);
            if (e.High - e.Low > 2f && !landing)
            {
                Slab(stone, caps, a + low, b + low, 0.25f, e.High, e.High + 0.9f);
                Coping(stone, caps, a + low, b + low, 0.25f, e.High + 0.9f);
            }
            var run = (e.B - e.A).Length();
            if (e.High - e.Low > 1.6f && run > 5f)
            {
                var count = Mathf.FloorToInt(run / 7f);
                for (var k = 1; k <= count; k++)
                {
                    var at = e.A.Lerp(e.B, k / (count + 1f));
                    var pc = at + lowFace * (1f + 0.14f / CityPlan.EdgeHalf);
                    if (_stairs.Any(st => CityPlan.SegDist(pc, st.Foot, st.Head + st.Dir * 1.8f) < CityPlan.StairHalf + 0.6f)) continue;
                    Slab(stone, caps, pc - dir * 0.35f, pc + dir * 0.35f, 0.16f, e.Low - 0.1f, e.High - 0.3f, 0.02f);
                    Coping(stone, caps, pc - dir * 0.35f, pc + dir * 0.35f, 0.16f, e.High - 0.3f);
                    var pw = W3(pc, (e.Low + e.High) / 2f - 0.2f);
                    var dw = CityPlan.DirToWorld(dir);
                    body.AddChild(new CollisionShape3D
                    {
                        Shape = new BoxShape3D { Size = new Vector3(0.7f, e.High - e.Low - 0.2f, 0.32f) },
                        Transform = new Transform3D(new Basis(Vector3.Up, Mathf.Atan2(-dw.Y, dw.X)), pw),
                    });
                }
            }
            if (e.Low > CityPlan.Sea + 0.5f)
            {
                // out with the batter: the foot stands 2 % of the height proud
                var face = -e.HighSide * (CityPlan.EdgeHalf + 0.03f + 0.02f * (e.High - e.Low + 0.2f));
                Slab(moss, moss, a + face, b + face, 0.04f, e.Low - 0.1f, e.Low + 0.6f);
            }
            var c = W3((e.A + e.B) / 2f, (e.Low + e.High) / 2f - 0.4f);
            var w = CityPlan.DirToWorld(dir);
            body.AddChild(new CollisionShape3D
            {
                Shape = new BoxShape3D { Size = new Vector3((e.B - e.A).Length() + 0.3f, e.High - e.Low + 0.8f, CityPlan.EdgeHalf * 2f) },
                Transform = new Transform3D(new Basis(Vector3.Up, Mathf.Atan2(-w.Y, w.X)), c),
            });
        }
        // the sheet's big blocks (2026-09-30, "city life" plan, item 6); ashlar read as brick
        AddChild(Surface("CityRetaining", stone, TexLib.Triplanar("ashlar_big")));
        AddChild(Surface("CityRetainingCaps", caps, TexLib.Triplanar("flagstone")));
        AddChild(Surface("CityMoss", moss, TexLib.Triplanar("moss")));
    }

    /// <summary>Where the grass must not grow: house floors, retaining blocks,
    /// the wall and its stairs, crop fields, big props. Its fringe thickens
    /// round each (weeds at the wall's foot). Roads, the plaza, the squares and
    /// water are Grass's own pure rules.</summary>
    private void GrassClear()
    {
        static Vector2 W(Vector2 p) => CityPlan.ToWorld(p);
        static Vector2 Across(Vector2 f) => CityPlan.DirToWorld(new Vector2(f.Y, -f.X));
        foreach (var b in _blds) Grass.ClearBox(W(b.P), Across(b.Front), new Vector2((b.W - 0.8f) / 2f - 0.25f, (b.D - 0.6f) / 2f - 0.25f));
        // to the wall's face, not 0.25 m short of it: a bare strip at every wall
        // foot was one of the hard seams (2026-09-29, "the continuation")
        foreach (var e in _edges) Grass.ClearSeg(W(e.A), W(e.B), CityPlan.EdgeHalf + 0.02f);
        foreach (var c in _courts) Grass.ClearDisc(W(c.P), c.R, 0.4f);
        foreach (var (foot, head, _, _, _) in CityPlan.WallStairs)
            Grass.ClearSeg(W(foot), W(head + (head - foot).Normalized() * 1.6f), CityPlan.StairHalf + 0.3f);
        var wall = _sizes.TryGetValue("wall_run", out var ws) ? ws.Y / 2f : 1.5f;
        for (var i = 0; i < CityPlan.Encl.Length; i++)
            if (CityPlan.EdgeIsWall(i)) Grass.ClearSeg(W(CityPlan.Encl[i]), W(CityPlan.Encl[(i + 1) % CityPlan.Encl.Length]), wall);
        foreach (var p in _props)
        {
            if (!_sizes.TryGetValue(p.Kind, out var s)) continue;
            if (p.Kind == "crop_field") Grass.ClearBox(W(p.P), Across(p.Front), new Vector2(s.X, s.Y) / 2f, 0.6f);
            else if (p.Kind is "fountain" or "market_stall_a" or "market_stall_b" or "wagon" or "well" or "hay_stack" or "cart" or "statue_knight")
                Grass.ClearDisc(W(p.P), Mathf.Max(s.X, s.Y) * 0.45f, 0.5f);
        }
    }

    /// <summary>A flat-lying surface with its own UVs (the setts): tangents for
    /// the normal map, which a triplanar surface does without. Casts nothing.</summary>
    /// <summary>Wear on the paving (2026-09-30, "city life" plan, item 7; the outside reviews:
    /// "thousands of people have been walking here"): broad lighter and darker patches (~12 m)
    /// and darker grime (~20 m blotches) as vertex colour over the texture. Low frequency only:
    /// the look gate's ground metric is fine detail, and the user chose calm ground (2026-09-27).</summary>
    private static readonly FastNoiseLite WearA = new() { NoiseType = FastNoiseLite.NoiseTypeEnum.SimplexSmooth, Frequency = 0.085f, Seed = 11 };
    private static readonly FastNoiseLite WearB = new() { NoiseType = FastNoiseLite.NoiseTypeEnum.SimplexSmooth, Frequency = 0.05f, Seed = 23 };
    private static readonly HashSet<string> Worn = new() { "CityRoads", "CityLanes", "CityPlaza", "CityCourts" };

    private static Color Wear(Vector3 p)
    {
        // +-10 % / -20 % was all but invisible in the Old City view (tour r2a); +-14 / -28
        var a = 1f + 0.14f * WearA.GetNoise2D(p.X, p.Z);
        var g = Mathf.SmoothStep(0.3f, 0.7f, WearB.GetNoise2D(p.X, p.Z));
        var k = a * (1f - 0.28f * g);
        return new Color(k, k * (1f - 0.02f * g), k * (1f - 0.05f * g));
    }

    private static Material Worn_(string name, Material m)
    {
        if (!Worn.Contains(name) || m is not BaseMaterial3D b) return m;
        var w = (BaseMaterial3D)b.Duplicate();
        w.VertexColorUseAsAlbedo = true;
        return w;
    }

    private static MeshInstance3D Surface(string name, List<Vector3> v, List<Vector2> uv, Material m)
    {
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        var worn = Worn.Contains(name);
        for (var i = 0; i < v.Count; i++) { st.SetUV(uv[i]); if (worn) st.SetColor(Wear(v[i])); st.AddVertex(v[i]); }
        m = Worn_(name, m);
        st.GenerateNormals();
        st.GenerateTangents();
        return new MeshInstance3D { Name = name, Mesh = st.Commit(), MaterialOverride = m,
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off };
    }

    private static MeshInstance3D Surface(string name, List<Vector3> v, Material m)
    {
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        var worn = Worn.Contains(name);
        foreach (var p in v) { if (worn) st.SetColor(Wear(p)); st.AddVertex(p); }
        m = Worn_(name, m);
        st.GenerateNormals();
        // only the masonry casts: roads, caps and moss lie flat on what already casts
        var cast = (name is "CityRetaining" or "CityStairs") && !NoCast.Contains("blocks");
        return new MeshInstance3D { Name = name, Mesh = st.Commit(), MaterialOverride = m,
            CastShadow = cast ? GeometryInstance3D.ShadowCastingSetting.On : GeometryInstance3D.ShadowCastingSetting.Off };
    }

    /// <summary>Spray at the foot of each fall: soft white puffs thrown up
    /// and drifting off, so the landing reads as water hitting water and
    /// not a panel meeting a plane.</summary>
    private void Spray()
    {
        var puff = new Gradient();
        puff.SetColor(0, new Color(1f, 1f, 1f, 1f));
        puff.SetColor(1, new Color(1f, 1f, 1f, 0f));
        var mat = new StandardMaterial3D
        {
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Particles,
            VertexColorUseAsAlbedo = true,
            AlbedoTexture = new GradientTexture2D { Gradient = puff, Fill = GradientTexture2D.FillEnum.Radial, FillFrom = new Vector2(0.5f, 0.5f), FillTo = new Vector2(0.5f, 0f), Width = 32, Height = 32 },
            AlbedoColor = new Color(0.92f, 0.95f, 0.97f),
        };
        var ramp = new Gradient();
        ramp.SetColor(0, new Color(1f, 1f, 1f, 0.5f));
        ramp.SetColor(1, new Color(1f, 1f, 1f, 0f));
        var grow = new Curve();
        grow.AddPoint(new Vector2(0f, 0.5f));
        grow.AddPoint(new Vector2(1f, 1.8f));
        foreach (var (_, at, dir, _, foot, width) in CityPlan.Falls)
        {
            var w = W3(at + dir * 2.5f, foot + 0.3f);
            var d = CityPlan.DirToWorld(dir);
            AddChild(new GpuParticles3D
            {
                Name = "Spray", Position = w, Amount = 70, Lifetime = 2.2, Preprocess = 2.2,
                ProcessMaterial = new ParticleProcessMaterial
                {
                    EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box,
                    EmissionBoxExtents = new Vector3(width * 0.4f, 0.3f, width * 0.4f),
                    Direction = new Vector3(d.X, 1.6f, d.Y).Normalized(), Spread = 35f,
                    InitialVelocityMin = 1.2f, InitialVelocityMax = 2.6f,
                    Gravity = new Vector3(0f, -0.9f, 0f), DampingMin = 0.4f, DampingMax = 0.8f,
                    ScaleMin = 1.2f, ScaleMax = 2.2f, ScaleCurve = new CurveTexture { Curve = grow },
                    ColorRamp = new GradientTexture1D { Gradient = ramp },
                },
                DrawPass1 = new QuadMesh { Size = new Vector2(1.4f, 1.4f), Material = mat },
                VisibilityAabb = new Aabb(new Vector3(-12f, -2f, -12f), new Vector3(24f, 12f, 24f)),
                VisibilityRangeEnd = NearRange + 20f, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            });
        }
    }

    /// <summary>The sea (harbour, estuary, canal) as one sheet the ground
    /// hides; each stream as a ribbon at its own level.</summary>
    private void Water()
    {
        AddChild(global::Worldbuilder.Water.Pool(CityPlan.ToWorld(Vector2.Zero), CityPlan.Outer / 1.3f, _lc + CityPlan.Sea));
        // each reach runs from its first point to its last (falls -> falls
        // -> sea), and its sheet carries that direction per vertex so the
        // water visibly runs (it read as a still pond)
        foreach (var (line, lv, hw) in CityPlan.Reaches)
        {
            var v = new List<Vector3>();
            var flow = new List<Vector2>();
            for (var i = 0; i + 1 < line.Length; i++)
            {
                Vector2 a = line[i], b = line[i + 1];
                var dir = (b - a).Normalized();
                var s = new Vector2(dir.Y, -dir.X) * (hw + 2f);
                a -= dir * 2f;
                b += dir * 2f;
                Quad(v, W3(a - s, lv), W3(a + s, lv), W3(b + s, lv), W3(b - s, lv), Vector3.Up);
                var wd = CityPlan.DirToWorld(dir).Normalized();
                for (var k = 0; k < 6; k++) flow.Add(wd);
            }
            AddChild(global::Worldbuilder.Water.Sheet("Stream", v, flow));
        }
    }

    /// <summary>Every lamp the kit draws is a real light (user, 2026-09-24:
    /// "most of lights dont light up, they are prop"; before this only the
    /// fountain's four were): a <see cref="LampLight"/> on each lamp point of
    /// every placed asset -- street lamps, wall and hanging lanterns, the
    /// lanterns built into taverns, gates, piers, the watchtowers' braziers,
    /// the forges, the lighthouse -- merged within 1.5 m, under LampLight's
    /// distance cull (on within 50 m of the player). Windows stay emission.</summary>
    private void Lamps()
    {
        var lamps = new List<(Vector3 P, string Kind)>();
        var grid = new Dictionary<Vector2I, List<int>>();
        foreach (var p in _places)
        {
            if (!LampPts.TryGetValue(p.Kind, out var pts) || pts.Length == 0 || Dim(p)) continue;
            var xf = Xf(p);
            foreach (var lp in pts)
            {
                var w = xf * lp;
                var key = new Vector2I(Mathf.FloorToInt(w.X / 3f), Mathf.FloorToInt(w.Z / 3f));
                var dup = false;
                for (var gx = -1; gx <= 1 && !dup; gx++)
                for (var gz = -1; gz <= 1 && !dup; gz++)
                    if (grid.TryGetValue(key + new Vector2I(gx, gz), out var l))
                        dup = l.Any(i => lamps[i].P.DistanceSquaredTo(w) < 2.25f);
                if (dup) continue;
                if (!grid.TryGetValue(key, out var cell)) grid[key] = cell = new List<int>();
                cell.Add(lamps.Count);
                lamps.Add((w, p.Kind));
            }
        }
        foreach (var (w, kind) in lamps)
        {
            var (strength, reach, fire) = kind switch
            {
                "street_lamp" or "lantern_post" or "pier" => (2.4f, 9f, false),
                "lighthouse" => (3.5f, 14f, false),
                "brazier" or "watchtower" => (2.2f, 8f, true),
                "blacksmith" => (1.8f, 6f, true),
                // wall and hanging lanterns, and the lanterns built into fronts
                _ => (1.5f, 6.5f, false),
            };
            AddChild(new LampLight { Name = "Lamp", Position = w, Strength = strength, Reach = reach, Fire = fire, CullRange = 50f }.Auto());
        }
        Lit = lamps.Count;
        GD.Print($"city: {lamps.Count} lamps lit (real lights, culled to 50 m)");
    }

    /// <summary>Check 9's offenders, for the walk's report.</summary>
    public static readonly List<string> Floating = new();
    /// <summary>The placed buildings (the walk keeps its grid points out of them).</summary>
    public static IReadOnlyList<CityPlan.Bldg> Buildings = System.Array.Empty<CityPlan.Bldg>();
    /// <summary>The retaining blocks' lines (the walk keeps its grid points out of them too).</summary>
    public static IReadOnlyList<CityPlan.Edge> Edges = System.Array.Empty<CityPlan.Edge>();
    /// <summary>Each rowboat's mooring (plan metres), the way inland off it,
    /// and its quay's level (camtest frames one).</summary>
    public static readonly List<(Vector2 P, Vector2 Inland, float Level)> Boats = new();

    /// <summary>The city's birds (user, 2026-09-24 plan: "gulls / pigeons"):
    /// pigeons pecking round the fountain and in the small squares, gulls on
    /// the quays. Both flutter up and away when the player comes close, and
    /// stay up while over water (Fauna).</summary>
    public void Birds(Node3D player)
    {
        var pigeon = new Fauna.Kind("pigeon", 0.45f, 5.5f, 3.2f, 5f, 0.1f, 0.15f, "peck", Flies: true);
        var gull = new Fauna.Kind("gull", 0.6f, 6.5f, 5f, 6f, 0.16f, 0.25f, "peck", Flies: true);
        var fauna = new Fauna
        {
            Name = "CityBirds",
            Dry = p => !CityPlan.IsWater(CityPlan.ToPlan(p.X, p.Y)),
        };
        AddChild(fauna);
        fauna.Bind(player, 3131);
        var rng = new System.Random(88);
        float U() => (float)rng.NextDouble();
        Vector2 W(Vector2 plan) => CityPlan.ToWorld(plan);
        // round the fountain, between the stall groups, off the basin
        var pigeons = new List<Vector2>();
        for (var i = 0; i < 26; i++)
        {
            var a = U() * Mathf.Tau;
            pigeons.Add(W(new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * (5.5f + U() * 16f)));
        }
        foreach (var sq in CityPlan.Squares)
            for (var i = 0; i < 4; i++)
                pigeons.Add(W(sq + new Vector2(U() - 0.5f, U() - 0.5f) * 8f));
        fauna.Add(pigeon, pigeons);
        // gulls on the quay edges and the causeway
        var gulls = new List<Vector2>();
        foreach (var (a, b) in new[] { (new Vector2(-160f, -80f), new Vector2(-24f, -76f)), (new Vector2(10f, -118f), new Vector2(110f, -130f)), (new Vector2(-12f, -125f), new Vector2(-12f, -150f)) })
            for (var t = 0.03f; t < 1f; t += 0.09f)
            {
                var p = a.Lerp(b, t + (U() - 0.5f) * 0.04f);
                if (!CityPlan.IsWater(p)) gulls.Add(W(p));
            }
        fauna.Add(gull, gulls);
        // the fountain's basin and the stalls: walked round, not through
        fauna.Block(W(Vector2.Zero), 3.8f);
        foreach (var p in _props.Where(pp => pp.Kind is "market_stall_a" or "market_stall_b" or "bench" or "street_lamp" or "well" or "tree_broad" or "tree_slim"))
            fauna.Block(W(p.P), p.Kind.StartsWith("market") ? 1.4f : 0.5f);
        GD.Print($"city: {pigeons.Count} pigeons, {gulls.Count} gulls");
    }

    // ------------------------------------------------------------------ folk
    /// <summary>The streets' walking height, a 1 m grid over the plan: every
    /// road's ribbon at its own level (ramps, stairs, bridge decks), the
    /// plaza and the squares; NaN is not a street. The dogs and cats keep to
    /// it (on the ground's height they would sink into a raised road).</summary>
    private float[] _street = System.Array.Empty<float>();
    private const float StX = -215f, StY = -165f;
    private const int StW = 470, StH = 310;

    private void Streets()
    {
        _street = new float[StW * StH];
        System.Array.Fill(_street, float.NaN);
        void Mark(int i, int j, float lv)
        {
            if (i < 0 || j < 0 || i >= StW || j >= StH) return;
            var k = j * StW + i;
            if (float.IsNaN(_street[k]) || lv > _street[k]) _street[k] = lv;
        }
        foreach (var rd in CityPlan.Roads)
        {
            if (rd.Kind == "track") continue;
            var half = rd.Hw - 0.5f;
            var n = rd.Loop ? rd.P.Length : rd.P.Length - 1;
            for (var s0 = 0; s0 < n; s0++)
            {
                var s1 = (s0 + 1) % rd.P.Length;
                Vector2 a = rd.P[s0], b = rd.P[s1];
                var ab = b - a;
                var l2 = Mathf.Max(ab.LengthSquared(), 1e-6f);
                int i0 = Mathf.FloorToInt(Mathf.Min(a.X, b.X) - half - StX), i1 = Mathf.CeilToInt(Mathf.Max(a.X, b.X) + half - StX);
                int j0 = Mathf.FloorToInt(Mathf.Min(a.Y, b.Y) - half - StY), j1 = Mathf.CeilToInt(Mathf.Max(a.Y, b.Y) + half - StY);
                var wet = rd.Wet[s0] && rd.Wet[s1];
                for (var j = j0; j <= j1; j++)
                for (var i = i0; i <= i1; i++)
                {
                    var c = new Vector2(StX + i + 0.5f, StY + j + 0.5f);
                    var t = Mathf.Clamp((c - a).Dot(ab) / l2, 0f, 1f);
                    if ((c - (a + ab * t)).Length() > half) continue;
                    Mark(i, j, Mathf.Lerp(rd.L[s0], rd.L[s1], t) + (wet ? 0.02f : 0.06f));
                }
            }
        }
        for (var j = 0; j < StH; j++)
        for (var i = 0; i < StW; i++)
        {
            var c = new Vector2(StX + i + 0.5f, StY + j + 0.5f);
            var r = c.Length();
            if (r < CityPlan.PlazaR - 0.5f && r > 4.2f) Mark(i, j, CityPlan.City + 0.04f);
            foreach (var sq in CityPlan.Squares)
                if ((c - sq).Length() < CityPlan.SquareR - 0.5f) Mark(i, j, CityPlan.Base(sq) + 0.03f);
        }
    }

    /// <summary>The street's height at a world point, or NaN off the streets.</summary>
    public float StreetY(Vector2 world)
    {
        var p = CityPlan.ToPlan(world.X, world.Y);
        int i = Mathf.FloorToInt(p.X - StX), j = Mathf.FloorToInt(p.Y - StY);
        if (i < 0 || j < 0 || i >= StW || j >= StH) return float.NaN;
        var lv = _street[j * StW + i];
        return float.IsNaN(lv) ? lv : _lc + lv;
    }

    /// <summary>Who walks where, by quarter (user, 2026-09-26: "different
    /// characters npcs fill the world").</summary>
    private static readonly Dictionary<CityPlan.Quarter, string[]> Who = new()
    {
        [CityPlan.Quarter.Market] = new[] { "merchant", "market_woman", "young_woman", "noble_lady", "child", "guard", "farmer", "old_man" },
        [CityPlan.Quarter.OldCity] = new[] { "merchant", "market_woman", "young_woman", "old_man", "child", "monk", "blacksmith" },
        [CityPlan.Quarter.Craftsmen] = new[] { "blacksmith", "blacksmith", "farmer", "merchant", "child", "young_woman" },
        [CityPlan.Quarter.WestRes] = new[] { "young_woman", "child", "old_man", "market_woman", "farmer", "merchant" },
        [CityPlan.Quarter.Noble] = new[] { "noble_lady", "noble_lady", "guard", "monk", "merchant" },
        [CityPlan.Quarter.Citadel] = new[] { "guard", "guard", "guard", "monk", "noble_lady" },
        // the harbour's own people (2026-09-30, "city life" plan): fishers and dock hands
        [CityPlan.Quarter.Riverside] = new[] { "fisher", "fisher", "dockhand", "market_woman", "old_man", "child", "young_woman" },
        [CityPlan.Quarter.LowerCity] = new[] { "dockhand", "dockhand", "fisher", "market_woman", "old_man", "child", "young_woman", "blacksmith" },
        [CityPlan.Quarter.Farms] = new[] { "farmer", "farmer", "child" },
    };

    /// <summary>People and animals (user, 2026-09-26: "make the game more
    /// livable ... dogs cats other animals ... fill the city"): walkers on
    /// every street, loiterers at the stalls and in the squares, guards at the
    /// gates; dogs and cats in the streets; hens, goats, sheep and pigs at the
    /// farms.</summary>
    public void Folk(Node3D player, CameraRig cam)
    {
        Streets();
        if (NoFolk) return;
        var rng = new System.Random(2626);
        float U() => (float)rng.NextDouble();
        string Pick(Vector2 plan)
        {
            var l = Who.TryGetValue(CityPlan.QuarterAt(plan), out var w) ? w : Who[CityPlan.Quarter.OldCity];
            return l[rng.Next(l.Length)];
        }
        Vector2 W(Vector2 plan) => CityPlan.ToWorld(plan);
        var folk = new Townsfolk { Name = "CityFolk" };
        AddChild(folk);
        folk.Bind(player, cam, 7272);
        foreach (var rd in CityPlan.Roads)
        {
            var route = new Townsfolk.Route
            {
                P = rd.P.Select(W).ToArray(),
                Y = rd.P.Select((_, i) => _lc + rd.L[i] + (rd.Kind == "track" ? 0.15f : rd.Wet[i] ? 0.02f : 0.06f)).ToArray(),
                Half = Mathf.Max(rd.Hw - 0.9f, 0.4f),
            };
            var len = 0f;
            for (var i = 1; i < rd.P.Length; i++) len += (rd.P[i] - rd.P[i - 1]).Length();
            var n = Mathf.Max(1, Mathf.RoundToInt(len / (rd.Kind == "main" ? 12f : 16f)));
            for (var k = 0; k < n; k++) folk.Walker(Pick(rd.P[rng.Next(rd.P.Length)]), route);
        }
        // the plaza: shoppers at the stalls, idlers round the fountain
        foreach (var st in _props.Where(p => p.Kind is "market_stall_a" or "market_stall_b"))
        {
            var at = st.P + st.Front * 2.2f + new Vector2(U() - 0.5f, U() - 0.5f) * 1.5f;
            folk.Stander(U() < 0.5f ? "market_woman" : "merchant", W(at), _lc + CityPlan.City + 0.04f, W(st.P));
        }
        for (var i = 0; i < 12; i++)
        {
            var a = U() * Mathf.Tau;
            var at = new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * (5.5f + U() * 15f);
            folk.Stander(Pick(Vector2.Zero), W(at), _lc + CityPlan.City + 0.04f, W(Vector2.Zero));
        }
        // a pair talking in each square
        foreach (var sq in CityPlan.Squares)
        {
            var a = U() * Mathf.Tau;
            var d = new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * 0.8f;
            folk.Stander(Pick(sq), W(sq + d), _lc + CityPlan.Base(sq) + 0.03f, W(sq - d));
            folk.Stander(Pick(sq), W(sq - d), _lc + CityPlan.Base(sq) + 0.03f, W(sq + d));
        }
        // two guards just inside each gate
        foreach (var rd in CityPlan.Roads.Where(r => r.Kind == "main"))
            for (var i = 1; i < rd.P.Length; i++)
            {
                bool inA = CityPlan.InPoly(rd.P[i - 1], CityPlan.Encl), inB = CityPlan.InPoly(rd.P[i], CityPlan.Encl);
                if (inA == inB) continue;
                var inner = inA ? i - 1 : i;
                var dir = (rd.P[i] - rd.P[i - 1]).Normalized();
                var side = new Vector2(-dir.Y, dir.X) * (rd.Hw - 0.6f);
                var back = (inA ? -dir : dir) * 4f;
                foreach (var sg in new[] { 1f, -1f })
                {
                    var at = rd.P[inner] + back + side * sg;
                    folk.Stander("guard", W(at), _lc + rd.L[inner] + 0.06f, W(at + back));
                }
                break;
            }
        // busy people (2026-09-30, "city life" plan, Phase 5a; own rng, so every draw above
        // stays): a vendor behind every stall, a cluster of customers in front of the small
        // stalls, groups of three round the fountain, dock hands at the lower quay's cargo,
        // farmers in the crop rows
        var r5 = new System.Random(2727);
        float V() => (float)r5.NextDouble();
        foreach (var st in _props.Where(p => p.Kind is "market_stall_a" or "market_stall_b" or "stall_c" or "large_stall"))
        {
            var lv = _lc + st.Level + 0.04f;
            var side = new Vector2(-st.Front.Y, st.Front.X);
            var seller = CityPlan.QuarterAt(st.P) == CityPlan.Quarter.Market ? (V() < 0.5f ? "merchant" : "market_woman") : Pick(st.P);
            folk.Holder(seller, W(st.P - st.Front * 0.55f), lv, W(st.P + st.Front * 3f));
            if (st.Kind is "stall_c" or "large_stall")
                foreach (var sd in new[] { -0.8f, 0.8f })
                {
                    var at = st.P + st.Front * (st.Kind == "large_stall" ? 2.8f : 2.1f) + side * (sd + (V() - 0.5f) * 0.4f);
                    folk.Holder(Pick(at), W(at), lv, W(st.P));
                }
        }
        for (var g = 0; g < 3; g++)
        {
            var a = 0.6f + g * 2.1f;
            var c = new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * 13.5f;
            for (var k = 0; k < 3; k++)
            {
                var o = new Vector2(Mathf.Cos(k * 2.09f + a), Mathf.Sin(k * 2.09f + a)) * 0.85f;
                folk.Holder(Pick(Vector2.Zero), W(c + o), _lc + CityPlan.City + 0.04f, W(c));
            }
        }
        var cargo = _props.Where(p => (p.P.Y < -112f && p.P.X > 0f || p.P.Y < -74f && p.P.X < -20f && p.P.X > -170f)
                                      && p.Kind is "crate_pile" or "barrel_stack" or "sacks" or "fish_barrels" or "goods_crates" or "net_stack").ToList();
        foreach (var cg in cargo)
        {
            if (V() > 0.55f) continue;
            var at = cg.P + cg.Front * 1.6f + new Vector2(V() - 0.5f, V() - 0.5f);
            folk.Holder(V() < 0.6f ? "dockhand" : "fisher", W(at), _lc + cg.Level + 0.04f, W(cg.P), V() < 0.5f ? "work" : null);
        }
        // dock hands carrying crates between cargo piles 6-16 m apart on one level
        var carriers = 0;
        for (var i = 0; i < cargo.Count && carriers < 8; i++)
            for (var j = i + 1; j < cargo.Count; j++)
            {
                var (a, b) = (cargo[i], cargo[j]);
                var d = (a.P - b.P).Length();
                if (d < 6f || d > 16f || Mathf.Abs(a.Level - b.Level) > 0.1f) continue;
                Vector2 pa = a.P + a.Front * 1.4f, pb = b.P + b.Front * 1.4f;
                folk.Carrier("dockhand", new Townsfolk.Route { P = new[] { W(pa), W(pb) }, Y = new[] { _lc + a.Level + 0.04f, _lc + b.Level + 0.04f }, Half = 0.3f });
                carriers++;
                break;
            }
        // a fisher at the end of every other pier, facing the water
        for (var i = 0; i < PierEnds.Count; i += 2)
        {
            var (pe, sea) = PierEnds[i];
            folk.Holder("fisher", W(pe), _lc + DeckTop + 0.04f, W(pe + sea * 4f));
        }
        foreach (var f in _props.Where(p => p.Kind == "crop_field"))
            foreach (var k in new[] { -1.6f, 2.2f })
            {
                var at = f.P + new Vector2(k, (V() - 0.5f) * 4f);
                folk.Holder(V() < 0.75f ? "farmer" : "child", W(at), _lc + f.Level + 0.04f, W(at + f.Front * 3f + new Vector2(V() - 0.5f, 0f)), "work");
            }
        // sitters (2026-09-30, Phase 5b): on four benches in ten, one or two, facing out
        foreach (var bn in _props.Where(p => p.Kind == "bench"))
        {
            if (V() > 0.4f) continue;
            var side = new Vector2(-bn.Front.Y, bn.Front.X);
            var who = CityPlan.QuarterAt(bn.P) is CityPlan.Quarter.Noble ? "noble_lady" : V() < 0.45f ? "old_man" : Pick(bn.P);
            var two = V() < 0.5f;
            foreach (var sd in two ? new[] { -0.38f, 0.38f } : new[] { (V() - 0.5f) * 0.5f })
            {
                var at = bn.P + side * sd - bn.Front * 0.05f;
                folk.Holder(sd > 0f && two ? Pick(bn.P) : who, W(at), _lc + bn.Level + 0.04f, W(at + bn.Front * 3f), "sit");
            }
        }
        folk.Finish();

        // dogs and cats: the streets are theirs
        var pets = new Fauna
        {
            Name = "CityPets",
            Dry = p => !float.IsNaN(StreetY(p)),
            Ground = p => { var y = StreetY(p); return float.IsNaN(y) ? WorldGen.Height(p.X, p.Y) : y; },
        };
        AddChild(pets);
        pets.Bind(player, 4242);
        List<Vector2> OnStreets(int n)
        {
            var l = new List<Vector2>();
            for (var t = 0; t < n * 40 && l.Count < n; t++)
            {
                var rd = CityPlan.Roads[rng.Next(CityPlan.Roads.Count)];
                if (rd.Kind == "track") continue;
                var p = W(rd.P[rng.Next(rd.P.Length)]);
                if (!float.IsNaN(StreetY(p))) l.Add(p);
            }
            return l;
        }
        pets.Add(new Fauna.Kind("dog", 1.2f, 7.5f, 0f, 10f, 0.3f, 0.3f, "sit", Tame: true, Pet: true), OnStreets(7));
        pets.Add(new Fauna.Kind("dog_black", 1.2f, 7.5f, 0f, 10f, 0.3f, 0.3f, "sit", Tame: true, Pet: true), OnStreets(5));
        pets.Add(new Fauna.Kind("cat", 0.6f, 6f, 2.6f, 6f, 0.17f, 0.2f, "sit", Skittish: true, Pet: true), OnStreets(6));
        pets.Add(new Fauna.Kind("cat_grey", 0.6f, 6f, 2.6f, 6f, 0.17f, 0.2f, "sit", Skittish: true, Pet: true), OnStreets(5));
        pets.Add(new Fauna.Kind("cat_black", 0.6f, 6f, 2.6f, 6f, 0.17f, 0.2f, "sit", Skittish: true, Pet: true), OnStreets(4));
        pets.Block(W(Vector2.Zero), 3.8f);
        foreach (var p in _props.Where(pp => pp.Kind is "market_stall_a" or "market_stall_b" or "bench" or "street_lamp" or "well" or "tree_broad" or "tree_slim"))
            pets.Block(W(p.P), p.Kind.StartsWith("market") ? 1.4f : 0.5f);

        // the farms: hens round the barn, goats, sheep and pigs in the fields
        var farm = new Fauna
        {
            Name = "FarmAnimals",
            Dry = p => { var q = CityPlan.ToPlan(p.X, p.Y); return CityPlan.QuarterAt(q) == CityPlan.Quarter.Farms && !CityPlan.IsWater(q); },
        };
        AddChild(farm);
        farm.Bind(player, 5353);
        List<Vector2> InFarm(Vector2 near, float r, int n)
        {
            var l = new List<Vector2>();
            for (var t = 0; t < n * 60 && l.Count < n; t++)
            {
                var p = near + new Vector2(U() - 0.5f, U() - 0.5f) * 2f * r;
                if (CityPlan.QuarterAt(p) == CityPlan.Quarter.Farms && !CityPlan.IsWater(p)) l.Add(W(p));
            }
            return l;
        }
        var barn = CityPlan.Landmarks.First(l => l.Kind == "barn").At;
        var mill = CityPlan.Landmarks.First(l => l.Kind == "windmill").At;
        farm.Add(new Fauna.Kind("hen", 0.5f, 3.5f, 2.2f, 5f, 0.12f, 0.15f, "peck"), InFarm(barn + new Vector2(-9f, -4f), 7f, 7));
        farm.Add(new Fauna.Kind("hen_white", 0.5f, 3.5f, 2.2f, 5f, 0.12f, 0.15f, "peck"), InFarm(barn + new Vector2(-9f, -4f), 7f, 5));
        farm.Add(new Fauna.Kind("goat", 0.6f, 4f, 1.2f, 8f, 0.3f, 0.35f, "graze", Pet: true), InFarm(new Vector2(214f, -95f), 10f, 3));
        farm.Add(new Fauna.Kind("sheep", 0.5f, 3.5f, 1.2f, 9f, 0.28f, 0.4f, "graze", Pet: true), InFarm(new Vector2(205f, -125f), 12f, 7));
        farm.Add(new Fauna.Kind("pig", 0.45f, 3f, 1.2f, 6f, 0.24f, 0.4f, "sniff", Pet: true), InFarm(barn + new Vector2(6f, -8f), 5f, 3));
        // the farm view's pen (CityPlan.Scenes, 2026-09-30): last, so no earlier draw moves
        farm.Add(new Fauna.Kind("goat", 0.6f, 4f, 1.2f, 8f, 0.3f, 0.35f, "graze", Pet: true), InFarm(CityPlan.Pen, 1.4f, 3));
        farm.Block(W(barn), 6.5f);
        // the rail fences (field tracks, cottage yards) are walls to them; the
        // kit fence runs across its front, size.X long
        var half = _sizes["fence"].X / 2f;
        foreach (var f in _props.Where(pp => pp.Kind == "fence"))
        {
            var along = new Vector2(-f.Front.Y, f.Front.X) * half;
            farm.BlockLine(W(f.P - along), W(f.P + along), 0.2f);
        }
        farm.Block(W(mill), 4f);
        GD.Print($"city: {folk.Count} people, {pets.Count} dogs and cats, {farm.Count} farm animals");
    }

    /// <summary>How many lamp lights the city placed.</summary>
    public static int Lit;

    /// <summary>Smoke from the chimneys: about half of the houses' and every
    /// forge's, from the chimney tops the kit build records. One
    /// GPUParticles3D per 60 m tile, emitting from a point list, so the whole
    /// city is ~30 small draws and only the tiles round the frame are drawn.</summary>
    private void Smoke()
    {
        var rng = new System.Random(515);
        var tiles = new Dictionary<Vector2I, List<Vector3>>();
        foreach (var b in _blds)
        {
            if (!SmokePts.TryGetValue(b.Kind, out var pts) || pts.Length == 0) continue;
            if (b.Kind != "blacksmith" && rng.NextDouble() > 0.5) continue;
            var xf = Xf(new Place(b.Kind, b.P, b.Front, b.Level, Vector3.One, Col.None));
            foreach (var sp in pts)
            {
                var w = xf * sp;
                var t = new Vector2I(Mathf.FloorToInt(w.X / 60f), Mathf.FloorToInt(w.Z / 60f));
                if (!tiles.TryGetValue(t, out var l)) tiles[t] = l = new List<Vector3>();
                l.Add(w);
            }
        }
        var puff = new Gradient();
        puff.SetColor(0, new Color(1f, 1f, 1f, 1f));
        puff.SetColor(1, new Color(1f, 1f, 1f, 0f));
        var tex = new GradientTexture2D { Gradient = puff, Fill = GradientTexture2D.FillEnum.Radial, FillFrom = new Vector2(0.5f, 0.5f), FillTo = new Vector2(0.5f, 0f), Width = 32, Height = 32 };
        var mat = new StandardMaterial3D
        {
            ShadingMode = BaseMaterial3D.ShadingModeEnum.PerVertex,
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Particles,
            VertexColorUseAsAlbedo = true,
            AlbedoTexture = tex,
            AlbedoColor = new Color(0.58f, 0.57f, 0.56f),
        };
        // `--smokedebug`: solid red, unshaded -- proves the particles are there
        if (OS.GetCmdlineUserArgs().Contains("--smokedebug")) { mat.ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded; mat.AlbedoColor = new Color(1f, 0f, 0f); }
        var ramp = new Gradient();
        ramp.SetColor(0, new Color(1f, 1f, 1f, 0f));
        ramp.SetColor(1, new Color(0.9f, 0.9f, 0.9f, 0f));
        ramp.AddPoint(0.15f, new Color(1f, 1f, 1f, 0.55f));
        var grow = new Curve();
        grow.AddPoint(new Vector2(0f, 0.35f));
        grow.AddPoint(new Vector2(1f, 1.6f));
        var n = 0;
        foreach (var (tile, list) in tiles)
        {
            var centre = new Vector3((tile.X + 0.5f) * 60f, _lc, (tile.Y + 0.5f) * 60f);
            var img = Image.CreateEmpty(list.Count, 1, false, Image.Format.Rgbaf);
            for (var i = 0; i < list.Count; i++)
            {
                var d = list[i] - centre;
                img.SetPixel(i, 0, new Color(d.X, d.Y, d.Z, 1f));
            }
            var pm = new ParticleProcessMaterial
            {
                EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Points,
                EmissionPointTexture = ImageTexture.CreateFromImage(img),
                EmissionPointCount = list.Count,
                Direction = Vector3.Up, Spread = 8f,
                InitialVelocityMin = 0.5f, InitialVelocityMax = 0.8f,
                // drifting with the clouds' wind (Clouds.Wind: world -x, a little -z)
                Gravity = new Vector3(-0.28f, 0.12f, -0.09f),
                DampingMin = 0.05f, DampingMax = 0.1f,
                ScaleMin = 0.8f, ScaleMax = 1.2f,
                ScaleCurve = new CurveTexture { Curve = grow },
                ColorRamp = new GradientTexture1D { Gradient = ramp },
            };
            var ps = new GpuParticles3D
            {
                Name = "Smoke", Position = centre, Amount = list.Count * 9, Lifetime = 6.0, Preprocess = 6.0,
                ProcessMaterial = pm, DrawPass1 = new QuadMesh { Size = new Vector2(1.3f, 1.3f), Material = mat },
                VisibilityAabb = new Aabb(new Vector3(-40f, -10f, -40f), new Vector3(80f, 50f, 80f)),
                VisibilityRangeEnd = NearRange, CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            };
            AddChild(ps);
            n += list.Count;
        }
        GD.Print($"city: smoke from {n} chimneys in {tiles.Count} tiles");
    }

    // ------------------------------------------------------------------ the eight checks
    private void Validate()
    {
        var lines = new List<string>();
        void Check(int n, string what, bool ok, string detail) => lines.Add($"validate {n} {what}: {(ok ? "PASS" : "FAIL")}  {detail}");

        // 1 districts where the sheet puts them
        var worst = 0f;
        var d1 = new System.Text.StringBuilder();
        foreach (var (q, want) in CityPlan.Expected)
        {
            var mine = _blds.Where(b => b.Q == q).ToList();
            if (mine.Count == 0) { worst = 999f; d1.Append($"{q} none; "); continue; }
            var c = mine.Aggregate(Vector2.Zero, (s, b) => s + b.P) / mine.Count;
            var off = (c - want).Length();
            worst = Mathf.Max(worst, off);
            d1.Append($"{q} {mine.Count} @{off:F0}m; ");
        }
        Check(1, "district arrangement", worst < 40f, d1.ToString());

        // 2 landmarks in their districts
        var missing = new List<string>();
        foreach (var (kind, at, _, q) in CityPlan.Landmarks)
            if (!_blds.Any(b => b.Kind == kind && (b.P - at).Length() < 16f && CityPlan.QuarterAt(b.P) == q)) missing.Add($"{kind}@{q}");
        if (!_places.Any(p => p.Kind == "lighthouse")) missing.Add("lighthouse");
        foreach (var k in new[] { "fountain" }) if (!_props.Any(p => p.Kind == k)) missing.Add(k);
        Check(2, "landmarks in their districts", missing.Count == 0, missing.Count == 0 ? $"{CityPlan.Landmarks.Length + 2} placed" : string.Join(", ", missing));

        // 3 roads join every gate to the market and the citadel
        var roads = CityPlan.Roads;
        var adj = new List<int>[roads.Count];
        for (var i = 0; i < roads.Count; i++) adj[i] = new List<int>();
        for (var i = 0; i < roads.Count; i++)
        for (var j = i + 1; j < roads.Count; j++)
            if (roads[i].P.Any(p => roads[j].P.Any(q2 => (p - q2).Length() < roads[i].Hw + roads[j].Hw + 1f)))
            { adj[i].Add(j); adj[j].Add(i); }
        int RoadAt(Vector2 p) => roads.FindIndex(r => r.P.Any(q2 => (q2 - p).Length() < r.Hw + 3f));
        var seen = new HashSet<int>();
        var queue = new Queue<int>();
        var start = RoadAt(new Vector2(0f, 18f));
        if (start >= 0) { queue.Enqueue(start); seen.Add(start); }
        while (queue.Count > 0) foreach (var j in adj[queue.Dequeue()]) if (seen.Add(j)) queue.Enqueue(j);
        var ends = new (string, Vector2)[] { ("north gate", CityPlan.Encl[7]), ("west gate", CityPlan.Encl[0]), ("east gate", CityPlan.Encl[17]), ("water gate", new(-5f, -147f)), ("citadel", new(100f, 94f)) };
        var cut = ends.Where(e => { var r = RoadAt(e.Item2); return r < 0 || !seen.Contains(r); }).Select(e => e.Item1).ToList();
        var loose = string.Join(", ", Enumerable.Range(0, roads.Count).Where(i => !seen.Contains(i)).Select(i => roads[i].Name));
        Check(3, "roads connect gates, market, citadel", cut.Count == 0, (cut.Count == 0 ? $"{seen.Count}/{roads.Count} roads in one network" : "cut off: " + string.Join(", ", cut))
            + (loose.Length > 0 ? $" (not joined: {loose})" : ""));

        // 4 water continuous: falls -> reach -> falls -> sea
        var breaks = new List<string>();
        var f = CityPlan.Falls;
        var r = CityPlan.Reaches;
        void Near(string what, Vector2 a, Vector2 b, float tol) { if ((a - b).Length() > tol) breaks.Add($"{what} {(a - b).Length():F1}m"); }
        Near("NW falls -> river", f[0].At, r[0].Line[0], 8f);
        Near("river -> W falls", r[0].Line[^1], f[1].At, 4f);
        if (!CityPlan.IsWater(f[1].At + f[1].Dir * 6f)) breaks.Add("W falls foot not in the estuary");
        Near("E falls -> tributary", f[2].At, r[1].Line[0], 8f);
        Near("tributary -> cascade", r[1].Line[^1], f[3].At, 4f);
        Near("cascade -> lower reach", f[3].At, r[2].Line[0], 4f);
        Near("lower reach -> SE falls", r[2].Line[^1], f[4].At, 4f);
        if (!CityPlan.IsWater(f[4].At + f[4].Dir * 7f)) breaks.Add("SE falls foot not in the estuary");
        if (!CityPlan.IsWater(CityPlan.Canal[0]) || !CityPlan.IsWater(new Vector2(-199f, -45f))) breaks.Add("canal not joined to the estuary");
        if (!CityPlan.IsWater(new Vector2(-40f, -110f)) || !CityPlan.IsWater(new Vector2(-60f, -200f))) breaks.Add("harbour not joined to the estuary");
        Check(4, "water continuous", breaks.Count == 0, breaks.Count == 0 ? "NW falls-river-W falls-estuary; E falls-tributary-cascade-fields-SE falls-estuary; canal, harbour" : string.Join("; ", breaks));

        // 5 every level change has a block, a ramp, stairs or a wall on it
        var raw = 0;
        var tested = 0;
        var bareAt = new List<string>();
        for (var y = -165f; y < 140f; y += 2f)
        for (var x = -210f; x < 250f; x += 2f)
        {
            var p = new Vector2(x, y);
            foreach (var d in new[] { new Vector2(2f, 0f), new Vector2(0f, 2f) })
            {
                var q2 = p + d;
                if (CityPlan.QuarterAt(p) == CityPlan.Quarter.Outside && CityPlan.QuarterAt(q2) == CityPlan.Quarter.Outside) continue;
                float h0 = CityPlan.WaterAt(p, out var w0, out _) ? w0 : CityPlan.Base(p);
                float h1 = CityPlan.WaterAt(q2, out var w1, out _) ? w1 : CityPlan.Base(q2);
                if (Mathf.Abs(h0 - h1) < 1f) continue;
                if (CityPlan.IsWater(p) && CityPlan.IsWater(q2)) continue;
                tested++;
                var m = (p + q2) / 2f;
                var covered = _edges.Any(e => CityPlan.SegDist(m, e.A, e.B) < CityPlan.EdgeHalf + 0.5f) || CityPlan.RoadClear(m) < 1.5f
                              || CityPlan.WallDist(m) < 4f;
                if (!covered) { raw++; if (bareAt.Count < 30) bareAt.Add($"({m.X:F0},{m.Y:F0} {h0:F1}/{h1:F1})"); }
            }
        }
        Check(5, "terrace transitions walled / ramped", raw == 0, $"{tested} level changes sampled, {raw} bare {string.Join(" ", bareAt)}");

        // 6 no building on a road, a wall, water, a level change or another building
        var bad = new List<string>();
        foreach (var b in _blds)
        {
            var u = new Vector2(b.Front.Y, -b.Front.X);
            for (var i = 0; i <= 4; i++)
            for (var j = 0; j <= 4; j++)
            {
                // the walls' core, as the placer tests it: eaves and jetties may hang over a street
                var p = b.P + u * ((i / 4f - 0.5f) * (b.W - 1.8f)) + b.Front * ((j / 4f - 0.5f) * (b.D - 1.6f));
                if (CityPlan.RoadClear(p) < 0.05f) { bad.Add($"{b.Kind} on a road"); goto next; }
                if (CityPlan.IsWater(p)) { bad.Add($"{b.Kind} in water"); goto next; }
                if (CityPlan.WallDist(p) < 2.4f) { bad.Add($"{b.Kind} in the wall"); goto next; }
            }
            next:;
        }
        var overlaps = 0;
        for (var i = 0; i < _blds.Count; i++)
        for (var j = i + 1; j < _blds.Count; j++)
        {
            if ((_blds[i].P - _blds[j].P).Length() > 30f) continue;
            if (Overlap(_blds[i], _blds[j])) overlaps++;
        }
        Check(6, "no intersections", bad.Count == 0 && overlaps == 0, $"{bad.Count} on road/wall/water, {overlaps} overlapping pairs"
            + (bad.Count > 0 ? " (" + string.Join(", ", bad.Take(4)) + ")" : ""));

        // 7 open: built share down to the reference towns' (user, 2026-09-24:
        // "way too together"), and little DEAD ground -- open ground that is
        // neither street, nor near a house, nor a dressed yard (trees, beds,
        // hedges, wells). It was "dense", 57-66 % built, before.
        var sb = new System.Text.StringBuilder();
        var openOk = true;
        var yardKinds = new HashSet<string> { "tree_broad", "tree_slim", "garden_bed", "flower_bed", "hedge", "well", "clothesline", "bench", "street_lamp" };
        var yards = _props.Where(pp => yardKinds.Contains(pp.Kind)).Select(pp => pp.P).ToList();
        var yardCells = new HashSet<Vector2I>();   // 3 m cells within ~4.5 m of a yard piece
        foreach (var yp in yards)
            for (var dx = -1; dx <= 1; dx++)
            for (var dy = -1; dy <= 1; dy++)
                yardCells.Add(new Vector2I(Mathf.FloorToInt(yp.X / 3f) + dx, Mathf.FloorToInt(yp.Y / 3f) + dy));
        foreach (var q in new[] { CityPlan.Quarter.Market, CityPlan.Quarter.OldCity, CityPlan.Quarter.Craftsmen, CityPlan.Quarter.Riverside, CityPlan.Quarter.LowerCity, CityPlan.Quarter.WestRes })
        {
            int built = 0, near = 0, dead = 0;
            for (var y = -140f; y < 130f; y += 3f)
            for (var x = -195f; x < 230f; x += 3f)
            {
                var p = new Vector2(x, y);
                if (CityPlan.QuarterAt(p) != q || CityPlan.RoadClear(p) < 0f || p.Length() < CityPlan.PlazaR || CityPlan.NearEdge(p, CityPlan.Level(q))) continue;
                var dmin = float.MaxValue;
                foreach (var b in _blds)
                {
                    if ((b.P - p).LengthSquared() > 900f) continue;
                    var dd = b.P - p;
                    var ax = Mathf.Abs(dd.Dot(new Vector2(b.Front.Y, -b.Front.X))) - b.W / 2f;
                    var ay = Mathf.Abs(dd.Dot(b.Front)) - b.D / 2f;
                    dmin = Mathf.Min(dmin, Mathf.Max(ax, ay));
                }
                if (dmin <= 0f) built++;
                else if (dmin < 4f || CityPlan.RoadClear(p) < 3f || yardCells.Contains(new Vector2I(Mathf.FloorToInt(x / 3f), Mathf.FloorToInt(y / 3f)))) near++;
                else dead++;
            }
            var tot = Mathf.Max(built + near + dead, 1);
            var builtPct = 100f * built / tot;
            var deadPct = 100f * dead / tot;
            var maxBuilt = q == CityPlan.Quarter.OldCity ? 60f : 50f;
            openOk &= builtPct <= maxBuilt && deadPct < (q == CityPlan.Quarter.WestRes ? 35f : 25f);
            sb.Append($"{q} built {builtPct:F0}% dead {deadPct:F0}%; ");
        }
        Check(7, "open, not empty", openOk, sb.ToString() + $"{CityPlan.Squares.Count} squares, {yards.Count} yard pieces ({_props.Count(pp => pp.Kind.StartsWith("tree_"))} trees)");
        Check(8, "top-down vs master plan", true, WriteMap ? "see renders/citykit/plan_vs_sheet.png (visual)" : "run with --citymap");

        // 9 feet on the ground (2026-09-24, user: "the city is broken most of
        // the part"): every building's corners and every prop's foot against
        // the ground WorldGen gives there, which is what the player walks on.
        // A building floats where the ground falls > 0.6 m under a corner
        // (its plinth reaches 0.5 m down) and is buried where it rises
        // > 0.35 m; a prop either way > 0.3 m. Structures (wall, towers,
        // gates, bridges, docks, ships, falls) carry their own footings.
        var floating = new List<string>();
        var buried = new List<string>();
        foreach (var p in _places)
        {
            if (!CityKit.Has(p.Kind) || p.Col is Col.Wall or Col.Tower or Col.Gate or Col.WaterGate or Col.Bridge) continue;
            if (p.Kind is "pier" or "harbour_arm" or "chain_boom" or "waterfall" or "rowboat" or "sailboat" or "dock_barge" or "dock_platform"
                || p.Kind.StartsWith("ship")) continue;
            if (p.Kind is "balcony" or "hanging_sign" or "banner" or "wall_lantern" or "ivy" or "lantern_post" or "ladder") continue;   // hung on walls, or up on the wall walk
            // on a pier's deck (within 10 cm: a baked scene round-trips positions to ~0.1 mm,
            // and the exact match failed 27 deck props after the bake)
            if (Decks.Any(d => d.DistanceSquaredTo(p.P) < 0.01f)) continue;
            if (Overhead(p.Kind)) continue;   // overhead: its box centre is over the road, its poles on the verge
            var box = CityKit.Get(p.Kind).Box;
            var xf = Xf(p);
            var foot = _lc + p.Y;
            var bldg = p.Col == Col.Box;
            var probe = new List<Vector3> { new(box.GetCenter().X, 0f, box.GetCenter().Z) };
            if (bldg)
            {
                float x0 = box.Position.X + 0.9f, x1 = box.End.X - 0.9f, z0 = box.Position.Z + 0.7f, z1 = box.End.Z - 0.7f;
                probe.AddRange(new[] { new Vector3(x0, 0f, z0), new Vector3(x1, 0f, z0), new Vector3(x1, 0f, z1), new Vector3(x0, 0f, z1) });
            }
            float lo = float.MaxValue, hi = float.MinValue;
            foreach (var q in probe)
            {
                var w = xf * q;
                var g = WorldGen.Height(w.X, w.Z) - foot;
                // a road or the plaza is the ground where one runs
                var pp = CityPlan.ToPlan(w.X, w.Z);
                if (CityPlan.RoadClear(pp) < 0f || pp.Length() < CityPlan.PlazaR) g = Mathf.Max(g, CityPlan.Base(pp) - p.Y);
                lo = Mathf.Min(lo, g);
                hi = Mathf.Max(hi, g);
            }
            var tag = $"{p.Kind}@({p.P.X:F0},{p.P.Y:F0})";
            if (bldg ? lo < -0.6f : lo < -0.3f) floating.Add($"{tag} {lo:+0.0;-0.0}");
            else if (bldg ? hi > 0.35f : hi > 0.3f) buried.Add($"{tag} {hi:+0.0;-0.0}");
        }
        Check(9, "feet on the ground", floating.Count == 0 && buried.Count == 0,
            $"{floating.Count} floating ({string.Join(", ", floating.Take(8))}), {buried.Count} buried ({string.Join(", ", buried.Take(8))})");
        Floating.Clear();
        Floating.AddRange(floating.Concat(buried));

        // 10 grade crossings (2026-09-24 night): a stretch of road on an
        // embankment that another road meets at a different level -- the
        // lower road runs into the embankment's wall (the walk stuck on the
        // Ring road where it met the North road's ramp).
        // Geometric: the other road's edge must reach the raised stretch's
        // side wall band (beside the segment, not past its ends -- a street
        // leaving from the foot of a ramp is a proper junction).
        var clash = new Dictionary<string, string>();
        for (var i = 0; i < roads.Count; i++)
        for (var k = 0; k + 1 < roads[i].P.Length; k++)
        {
            var ri = roads[i];
            if (!ri.Raised[k] && !ri.Raised[k + 1]) continue;
            Vector2 a = ri.P[k], ab = ri.P[k + 1] - a;
            var len2 = Mathf.Max(ab.LengthSquared(), 1e-6f);
            for (var j = 0; j < roads.Count; j++)
            {
                if (j == i) continue;
                var rj = roads[j];
                for (var m = 0; m < rj.P.Length; m++)
                {
                    if (rj.Wet[m]) continue;
                    // across the other road's own width (its sides lie along its normal)
                    var tj = (rj.P[Mathf.Min(m + 1, rj.P.Length - 1)] - rj.P[Mathf.Max(m - 1, 0)]).Normalized();
                    var nj = new Vector2(-tj.Y, tj.X);
                    var hit = false;
                    var t = 0f;
                    foreach (var fw in new[] { -1f, -0.5f, 0f, 0.5f, 1f })
                    {
                        var q = rj.P[m] + nj * rj.Hw * fw;
                        var tq = (q - a).Dot(ab) / len2;
                        if (tq < 0f || tq > 1f || (q - (a + ab * tq)).Length() > ri.Hw + 0.9f) continue;
                        hit = true;
                        t = tq;
                        break;
                    }
                    if (!hit) continue;
                    var li = Mathf.Lerp(ri.L[k], ri.L[k + 1], t);
                    // 1 m: a ramp rising out of its own junction differs by up to ~0.9 m
                    // beside the road it leaves (Riverside route off the South road)
                    if (Mathf.Abs(li - rj.L[m]) <= 1.0f) continue;
                    var key = $"{Mathf.Min(i, j)}-{Mathf.Max(i, j)}@{Mathf.RoundToInt(a.X / 12f)},{Mathf.RoundToInt(a.Y / 12f)}";
                    clash.TryAdd(key, $"{ri.Name} {li:F1} / {rj.Name} {rj.L[m]:F1} at ({rj.P[m].X:F0},{rj.P[m].Y:F0})");
                    break;
                }
            }
        }
        Check(10, "no grade crossings", clash.Count == 0, $"{clash.Count}: " + string.Join("; ", clash.Values.Take(12)));

        // 11 roads clear of the curtain wall (2026-09-24 night: the Lower
        // street ran into a corner tower): no road's edge within 2 m of a wall
        // stretch, except through the three gates.
        var gatesAt = new[] { CityPlan.Encl[0], CityPlan.Encl[7], CityPlan.Encl[17] };
        var hitWall = new List<string>();
        foreach (var rd in roads)
        {
            if (rd.Kind == "track") continue;
            foreach (var p in rd.P)
            {
                if (gatesAt.Any(g => (g - p).Length() < 14f) || CityPlan.WallDist(p) >= rd.Hw + 2f) continue;
                hitWall.Add($"{rd.Name}@({p.X:F0},{p.Y:F0})");
                break;
            }
        }
        Check(11, "roads clear of the wall", hitWall.Count == 0, hitWall.Count == 0 ? "gates only" : string.Join(", ", hitWall));

        // 12-14 (user, 2026-09-29: "road tiles are not consistent ... some end and are
        // visible ending ... some end way too early"; "add more tests")
        // 12 every road end meets something: another road, a square, the plaza, a
        // gate, the water -- a dead end is listed, and an end within 4 m of another
        // road that stops short of it (a gap) fails
        float EdgeDist(CityPlan.Road rd, Vector2 p)
        {
            var near = float.MaxValue;
            foreach (var o in CityPlan.Roads)
            {
                if (o == rd || o.Kind == "track") continue;
                var segs = o.Loop ? o.P.Length : o.P.Length - 1;
                for (var i = 0; i < segs; i++) near = Mathf.Min(near, CityPlan.SegDist(p, o.P[i], o.P[(i + 1) % o.P.Length]) - o.Hw);
            }
            return near;
        }
        int joined = 0, onSquare = 0, atGate = 0, deadEnds = 0, gaps = 0;
        var endList = new List<string>();
        foreach (var rd in CityPlan.Roads)
        {
            if (rd.Loop || rd.Kind == "track" || rd.P.Length < 2) continue;
            foreach (var (e, prev) in new[] { (rd.P[0], rd.P[1]), (rd.P[^1], rd.P[^2]) })
            {
                if (OnRoad(rd, e, 0.3f)) { joined++; continue; }
                if (e.Length() < CityPlan.PlazaR + 1f || CityPlan.Squares.Any(q => (e - q).Length() < CityPlan.SquareR + 1f)) { onSquare++; continue; }
                var ahead = e + (e - prev).Normalized() * 2f;
                if (CityPlan.QuarterAt(e) == CityPlan.Quarter.Outside || CityPlan.WallDist(e) < 8f || CityPlan.IsWater(ahead)) { atGate++; continue; }
                var near = EdgeDist(rd, e);
                if (near < 4f) { gaps++; endList.Add($"{rd.Name} ({e.X:F0},{e.Y:F0}) {near:F1} m short"); }
                else { deadEnds++; endList.Add($"{rd.Name} dead end ({e.X:F0},{e.Y:F0})"); }
            }
        }
        Check(12, "road ends meet something", gaps == 0,
            $"joined {joined}, squares/plaza {onSquare}, gates/water {atGate}, dead ends {deadEnds}, short {gaps}" + (endList.Count > 0 ? ": " + string.Join("; ", endList) : ""));

        // 13 no kerb piece lies on another road (the angled-junction glitch)
        var onOther = _kerbPieces.Count(k => OnRoad(k.Rd, (k.A + k.B) / 2f - k.N * 0.125f, 0f));
        Check(13, "kerbs clear of other roads", onOther == 0, $"{_kerbPieces.Count} pieces, {onOther} on another road");

        // 14 no prop stands on a kerb or the road strip just inside it (the walk's
        // kerb crossings stopped at -0.63..-0.68 m: something there)
        var blocking = new Dictionary<string, int>();
        var blockAt = new List<string>();
        foreach (var pr in _props)
        {
            if (Overhead(pr.Kind) || !_sizes.TryGetValue(pr.Kind, out var sz)) continue;   // bunting / washing lines are overhead
            var pr0 = 0.5f * Mathf.Min(sz.X, sz.Y);
            foreach (var k in _kerbPieces)
            {
                var toward = (pr.P - (k.A + k.B) / 2f).Dot(k.N);   // + on the verge, - on the road
                if (CityPlan.SegDist(pr.P, k.A, k.B) < pr0 + 0.3f && toward < pr0 + 0.1f)
                {
                    blocking[pr.Kind] = blocking.GetValueOrDefault(pr.Kind) + 1;
                    if (blockAt.Count < 6) blockAt.Add($"{pr.Kind} ({pr.P.X:F0},{pr.P.Y:F0}) on {k.Rd.Name}");
                    break;
                }
            }
        }
        Check(14, "props clear of the kerbs", blocking.Count == 0,
            blocking.Count == 0 ? $"{_props.Count} props" : string.Join(", ", blocking.OrderByDescending(kv => kv.Value).Select(kv => $"{kv.Key} {kv.Value}"))
                + " -- " + string.Join("; ", blockAt));
        foreach (var l in lines) GD.Print(l);
    }

    private static bool Overlap(CityPlan.Bldg a, CityPlan.Bldg b)
    {
        Vector2[] C(CityPlan.Bldg x)
        {
            var u = new Vector2(x.Front.Y, -x.Front.X) * ((x.W - 0.8f) / 2f - 0.05f);
            var f = x.Front * ((x.D - 0.6f) / 2f - 0.05f);
            return new[] { x.P - u - f, x.P + u - f, x.P + u + f, x.P - u + f };
        }
        var pa = C(a);
        var pb = C(b);
        foreach (var poly in new[] { pa, pb })
            for (var i = 0; i < 2; i++)
            {
                var e = poly[i + 1] - poly[i];
                var axis = new Vector2(e.Y, -e.X);
                float amin = pa.Min(p => p.Dot(axis)), amax = pa.Max(p => p.Dot(axis)), bmin = pb.Min(p => p.Dot(axis)), bmax = pb.Max(p => p.Dot(axis));
                if (amax < bmin || bmax < amin) return false;
            }
        return true;
    }

    // ------------------------------------------------------------------ map and tour
    /// <summary>The plan from above at the sheet's own scale (0.37 m/px, the
    /// fountain at pixel 743, 378), stacked under the sheet.</summary>
    private void Map()
    {
        const int w = 1536, h = 830;
        var img = Image.CreateEmpty(w, h, false, Image.Format.Rgb8);
        Vector2 P(int i, int j) => new((i - 743f) * 0.37f, (378f - j) * 0.37f);
        Vector2I Px(Vector2 p) => new(Mathf.RoundToInt(p.X / 0.37f + 743f), Mathf.RoundToInt(378f - p.Y / 0.37f));
        for (var j = 0; j < h; j++)
        for (var i = 0; i < w; i++)
        {
            var p = P(i, j);
            Color c;
            if (CityPlan.WaterAt(p, out var wl, out _)) c = new Color(0.14f, 0.30f, 0.46f).Lightened(Mathf.Clamp(wl * 0.03f, 0f, 0.3f));
            else
            {
                var q = CityPlan.QuarterAt(p);
                var lv = CityPlan.Base(p);
                c = q == CityPlan.Quarter.Outside ? new Color(0.20f, 0.30f, 0.16f).Lightened(Mathf.Clamp(lv / 60f, 0f, 0.4f))
                  : q == CityPlan.Quarter.Farms ? new Color(0.46f, 0.44f, 0.24f)
                  : new Color(0.40f, 0.37f, 0.31f).Lightened(lv / 40f);
                if (CityPlan.RoadClear(p) < 0f) c = new Color(0.62f, 0.55f, 0.44f);
            }
            img.SetPixel(i, j, c);
        }
        void Fill(Vector2 c, Vector2 front, float bw, float bd, Color col)
        {
            var u = new Vector2(front.Y, -front.X);
            var ext = Mathf.Max(bw, bd);
            var lo = Px(c + new Vector2(-ext, ext));
            var hi = Px(c + new Vector2(ext, -ext));
            for (var j = Mathf.Max(lo.Y, 0); j <= Mathf.Min(hi.Y, h - 1); j++)
            for (var i = Mathf.Max(lo.X, 0); i <= Mathf.Min(hi.X, w - 1); i++)
            {
                var d = P(i, j) - c;
                if (Mathf.Abs(d.Dot(u)) <= bw / 2f && Mathf.Abs(d.Dot(front)) <= bd / 2f) img.SetPixel(i, j, col);
            }
        }
        foreach (var e in _edges) Fill((e.A + e.B) / 2f, e.HighSide, (e.B - e.A).Length() + 0.3f, 2f * CityPlan.EdgeHalf, new Color(0.30f, 0.29f, 0.27f));
        foreach (var p in _props.Where(p => p.Kind == "crop_field")) Fill(p.P, p.Front, 8f, 8f, new Color(0.70f, 0.60f, 0.25f));
        foreach (var b in _blds)
        {
            var col = b.Kind is "tavern" or "shop" or "cottage_tile" or "townhouse_corner" or "warehouse" or "townhouse_stall" ? new Color(0.66f, 0.30f, 0.20f)
                    : b.Kind is "cottage" or "barn" or "stables" ? new Color(0.62f, 0.50f, 0.30f)
                    : b.Kind is "keep" or "church" or "chapel" or "barracks" or "watchtower" ? new Color(0.55f, 0.55f, 0.58f)
                    : new Color(0.26f, 0.32f, 0.44f);
            Fill(b.P, b.Front, b.W - 0.6f, b.D - 0.6f, col);
        }
        foreach (var p in _places)
        {
            if (p.Kind == "wall_run") Fill(p.P, p.Dir, 8f * p.Scale.X, 2.6f, new Color(0.12f, 0.11f, 0.10f));
            else if (p.Kind is "tower_round" or "tower_square" or "gatehouse" or "water_gate" or "lighthouse") Fill(p.P, p.Dir, 6f, 6f, new Color(0.08f, 0.08f, 0.08f));
            else if (p.Kind == "pier") Fill(p.P + p.Dir * 6f, p.Dir, 3f, 12f, new Color(0.45f, 0.32f, 0.20f));
            else if (p.Kind.StartsWith("ship")) Fill(p.P, new Vector2(-p.Dir.Y, p.Dir.X), p.Kind == "ship_merchant" ? 20f : 9f, p.Kind == "ship_merchant" ? 6f : 3f, new Color(0.35f, 0.24f, 0.15f));
        }
        var dir = ProjectSettings.GlobalizePath("res://") + "../renders/citykit/";
        img.SavePng(dir + "citymap.png");
        var sheet = Image.LoadFromFile(ProjectSettings.GlobalizePath("res://") + "../ref/emberglass_master_plan.webp");
        if (sheet != null && sheet.GetWidth() == w)
        {
            sheet.Convert(Image.Format.Rgb8);
            var both = Image.CreateEmpty(w, h * 2, false, Image.Format.Rgb8);
            both.BlitRect(sheet, new Rect2I(0, 0, w, h), Vector2I.Zero);
            both.BlitRect(img, new Rect2I(0, 0, w, h), new Vector2I(0, h));
            both.SavePng(dir + "plan_vs_sheet.png");
        }
        GD.Print($"city: map -> {dir}citymap.png, plan_vs_sheet.png");
    }

    private int _tourFrame;
    private int _tourShot;

    // ------------------------------------------------------------------ roads out
    // The city stands on a plateau ~600 m above the world past its south
    // edge (the edge mountains, WorldGen.Raw): no road can climb that inside
    // the ~280 m between them, so the three roads out end at waystones.
    // Stepping onto one carries the player along the road: the city's West,
    // North and East road ends go to the village's road end, and a stone
    // there goes back to the West road. (It was F7 only.) Plain play only --
    // the walks and tours pass the road ends.
    private readonly List<(Vector3 At, Vector2 To)> _stones = new();
    private float _stoneWait;
    private Node3D? _player;

    private void Waystones()
    {
        var ends = new[] { ("West road", false), ("North road", true), ("East road", false) };
        var village = WorldGen.PathTo + (WorldGen.PathTo - WorldGen.PathFrom).Normalized() * 4f;
        foreach (var (name, first) in ends)
        {
            var rd = CityPlan.Roads.First(r => r.Name == name);
            var k = first ? 0 : rd.P.Length - 1;
            var inward = (rd.P[first ? 2 : k - 2] - rd.P[k]).Normalized();
            var p = rd.P[k] + inward * 1.5f;
            var side = new Vector2(inward.Y, -inward.X) * (rd.Hw + 1f);
            // on the ground beside the road's end (it may end on a low embankment)
            // (past 330 m the ground blends to the world's: take the real height)
            float Ground(Vector2 q) { var w = CityPlan.ToWorld(q); return WorldGen.Height(w.X, w.Y) - _lc; }
            _places.Add(new Place("signpost", p + side, inward, Ground(p + side), Vector3.One, Col.None));
            _places.Add(new Place("lantern_post", p - side, -side.Normalized(), Ground(p - side), Vector3.One, Col.None));
            _stones.Add((W3(rd.P[k], rd.L[k]), village));
        }
        // the village's stone, back to the West road's end
        var west = CityPlan.Roads.First(r => r.Name == "West road");
        var back = CityPlan.ToWorld(west.P[^1] + (west.P[^3] - west.P[^1]).Normalized() * 5f);
        var vy = WorldGen.Height(village.X, village.Y);
        var vp = CityPlan.ToPlan(village.X, village.Y);
        var vd = CityPlan.ToPlan(village.X + 1f, village.Y + 1f) - vp;
        _places.Add(new Place("signpost", vp, vd.Normalized(), vy - _lc, Vector3.One, Col.None));
        _stones.Add((new Vector3(village.X, vy, village.Y), back));
    }

    /// <summary>World calls this once with the player (waystones watch it).</summary>
    public void Watch(Node3D player) => _player = player;

    public override void _Process(double delta)
    {
        if (_gh.Count > 0) Ghosts();
        if (_player != null && _stones.Count > 0 && CameraRig.RevealsOn)
        {
            _stoneWait -= (float)delta;
            var p = _player.GlobalPosition;
            foreach (var (at, to) in _stones)
                if (_stoneWait <= 0f && new Vector2(p.X - at.X, p.Z - at.Z).Length() < 2f && Mathf.Abs(p.Y - at.Y) < 3f)
                {
                    GD.Print("city: waystone -> " + to);
                    TeleportTo?.Invoke(to.X, to.Y);
                    _stoneWait = 3f;   // not straight back from the stone you land by
                    break;
                }
        }
        if (!Tour) return;
        if (++_tourFrame < 240) return;
        _tourFrame = 0;
        var dir = ProjectSettings.GlobalizePath("res://") + "../renders/citykit/tour/";
        DirAccess.MakeDirRecursiveAbsolute(dir);
        var name = CityPlan.Views[_view].Name.Replace(' ', '_').ToLowerInvariant();
        GetViewport().GetTexture().GetImage().SavePng($"{dir}{_tourShot:D2}_{name}.png");
        GD.Print($"city: tour shot {_tourShot} {name}");
        if (++_tourShot >= CityPlan.Views.Length) { GetTree().Quit(); return; }
        var next = NextView();
        TeleportTo?.Invoke(next.X, next.Y);
    }

    // ------------------------------------------------------------------ far stand-in
    private static ArrayMesh HouseMesh()
    {
        var v = new List<Vector3>();
        void Box(Vector3 lo, Vector3 hi)
        {
            var c = (lo + hi) / 2f;
            Vector3 P(int x, int y, int z) => new(x == 0 ? lo.X : hi.X, y == 0 ? lo.Y : hi.Y, z == 0 ? lo.Z : hi.Z);
            foreach (var (a, b, cc, d) in new[] {
                (P(0,0,0), P(0,1,0), P(0,1,1), P(0,0,1)), (P(1,0,0), P(1,0,1), P(1,1,1), P(1,1,0)),
                (P(0,0,0), P(1,0,0), P(1,1,0), P(0,1,0)), (P(0,0,1), P(0,1,1), P(1,1,1), P(1,0,1)),
                (P(0,1,0), P(1,1,0), P(1,1,1), P(0,1,1)) })
                Quad(v, a, b, cc, d, (a + b + cc + d) / 4f - c);
        }
        Box(new Vector3(-0.5f, 0f, -0.5f), new Vector3(0.5f, 0.62f, 0.5f));
        Vector3 e0 = new(-0.5f, 0.62f, -0.5f), e1 = new(0.5f, 0.62f, -0.5f), e2 = new(0.5f, 0.62f, 0.5f), e3 = new(-0.5f, 0.62f, 0.5f);
        Vector3 k0 = new(-0.5f, 1f, 0f), k1 = new(0.5f, 1f, 0f);
        var ctr = new Vector3(0f, 0.7f, 0f);
        Quad(v, e0, e1, k1, k0, (e0 + k1) / 2f - ctr);
        Quad(v, e3, k0, k1, e2, (e3 + k1) / 2f - ctr);
        Tri(v, e0, k0, e3, Vector3.Left);
        Tri(v, e1, e2, k1, Vector3.Right);
        var st = new SurfaceTool();
        st.Begin(Mesh.PrimitiveType.Triangles);
        foreach (var p in v) { st.SetColor(new Color(p.Y > 0.63f ? 1f : 0f, 0f, 0f)); st.AddVertex(p); }
        st.GenerateNormals();
        return st.Commit();
    }

    // 2026-09-30 (part 2): the stand-ins read as orange blobs through the far blur; the
    // sheet's distant town is violet silhouettes with lit windows
    private const string FarCode = @"
shader_type spatial;
uniform vec3 walls[4];
varying vec3 roof;
varying flat float wall;
varying vec3 wpos;
void vertex() { roof = INSTANCE_CUSTOM.rgb; wall = INSTANCE_CUSTOM.a; wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
    vec3 base = COLOR.r > 0.5 ? roof : walls[clamp(int(wall * 4.0), 0, 3)];
    ALBEDO = mix(base, vec3(0.24, 0.19, 0.30), 0.45);
    ROUGHNESS = 0.9;
    if (COLOR.r < 0.5) {
        vec2 g = vec2((wpos.x + wpos.z) * 0.55, wpos.y * 0.42);
        vec2 f = fract(g);
        float win = step(0.3, f.x) * step(f.x, 0.62) * step(0.3, f.y) * step(f.y, 0.7);
        float lit = step(0.5, fract(sin(dot(floor(g), vec2(12.9898, 78.233))) * 43758.5453));
        EMISSION = vec3(1.0, 0.55, 0.22) * win * lit * 1.4;
    }
}
";
}
