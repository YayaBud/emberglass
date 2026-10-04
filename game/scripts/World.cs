using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The root. Owns the sky, the sun and the streamed ground, and nothing else.
///
/// Everything in the scene is built in code rather than authored in the .tscn.
/// That is deliberate while the world is the thing being worked on: a scene
/// file turns every lighting or streaming change into a merge conflict in a
/// binary-ish format, and there is nothing here a designer needs to click.
/// Move a thing into the scene when a human needs to place it by hand.
/// </summary>
public partial class World : Node3D
{
    /// <summary>Chunks loaded either side of the camera's own chunk.</summary>
    [Export] public int ViewChunks { get; set; } = 3;

    [Export] public ulong Seed { get; set; } = 1337;

    private readonly Dictionary<Vector2I, Terrain> _live = new();
    private readonly List<Vector2I> _queue = new();
    private readonly Dictionary<Vector2I, Task<Terrain.Data>> _pending = new();
    private readonly HashSet<Vector2I> _wanted = new();
    private Vector2I _centre = new(int.MinValue, int.MinValue);
    private const int MaxPending = 4;
    /// <summary>Metres past the centre chunk's own edge before the ring
    /// recentres. See the doc comment on <see cref="Stream"/>.</summary>
    private const float Hysteresis = 8f;
    private Node3D _chunkRoot = null!;

    /// <summary>Headless capture: `-- --shot=res://x.png --frames=90`.</summary>
    private string _shot = "";
    private bool _demo;
    private bool _hybrid;
    private bool _forceTop;
    private bool _camtest;
    private Vector2 _spawn;
    private int _texlab = -1;
    private bool _lightSet;
    private DirectionalLight3D? _sun;
    private Godot.Environment? _env;
    private int _bench;
    private readonly List<double> _times = new();
    private double _chunkMs;
    private double _chunkWorst;
    private int _chunkCount;
    private int _streamScans;
    private int _shotAt = 90;
    private int _frame;
    private int _faunaCheck;
    private int _faunaFrames, _faunaWorst;
    private bool _walk, _walkAway;
    private string[] _sweepSpecs = System.Array.Empty<string>();
    private string _sweepOut = "";
    private int _sweepI = -1, _sweepF, _sweepHold = 45;
    private bool _vsync;
    private string _off = "";
    private float _scale3d = -1f;
    private string _upscale = "";
    private int _msaa = -1;
    private readonly List<double> _gpu = new();
    private readonly List<double> _chunkFrames = new();
    private readonly List<double> _jitter = new();
    private ulong _tick;
    private double _builtMs;
    private int _stale;
    private Vector3 _lastP = new(float.NaN, 0f, 0f);
    private Vector2 _lastS = new(float.NaN, 0f);
    private Player _player = null!;
    private CameraRig _rig = null!;

    /// <summary>Probe chunks used by both <c>--meshhash</c> and
    /// <c>--selftest</c>: every biome, negative coordinates, the Fen's water
    /// and the world-edge mountains.</summary>
    private static readonly Vector2I[] Probes =
    {
        new(0, 0), new(-1, -1), new(-1, 3), new(-3, 2),
        new(2, 2), new(2, -3), new(-3, -2), new(5, 5),
    };

    /// <summary>The 3D frame's own height (2026-09-30, user: "optimize for these resolutions
    /// ... at least 60 fps", laptop 1080p and a 2K monitor, GTX 1650): FSR 2 renders at about
    /// this many lines and upscales to the window -- temporal, so it also smooths edges and
    /// resolves the soft-shadow grain (it cannot run with MSAA, which is off). Measured at
    /// 1440p, market: native + MSAA 4x 26.6 ms mean; FSR 2 at 0.67 20.5 ms; with cheaper DoF,
    /// glow and Soft Low shadows, 900 lines 15.6 ms (p99 17.8), 820 lines 14.6 (p99 16.7, 60 fps
    /// at the 1 % low). `--renderh=N`.</summary>
    public static float RenderHeight = 820f;

    private void Rescale()
    {
        var vp = GetViewport();
        var h = Mathf.Max(GetWindow().Size.Y, 1);
        vp.Scaling3DMode = Viewport.Scaling3DModeEnum.Fsr2;
        vp.Scaling3DScale = Mathf.Clamp(RenderHeight / h, 0.5f, 1f);
        vp.Msaa3D = Viewport.Msaa.Disabled;
    }

    // TEMP (user, 2026-09-30: "remove it for a while"): the haze is OFF by default -- fog,
    // volumetric fog, glow, sun shafts, depth of field, Post mist/grade. F11 brings it back.
    private bool _hazeOff, _startNoHaze = false;
    /// <summary>A lighting flag is set: the look files are not applied (the study's frames must reproduce).</summary>
    private bool _looks;
    private Node3D? _edit;
    private Node3D? SiteNode(string site) => _edit?.GetNodeOrNull<Node3D>(site);
    private (bool Fog, bool VFog, bool Glow)? _hazeSaved;
    private CameraAttributes? _dofSaved;

    /// <summary>F11 / `--nohaze` (2026-09-30, user: "whatever was causing that, remove it for a
    /// while, let me see without it"): every veil over the frame off at once -- depth fog,
    /// volumetric fog, glow, the sun shafts, depth of field and the Post pass (mist, grade,
    /// vignette). F11 again puts them back. A look-at switch, not a setting.</summary>
    private void Haze(bool off)
    {
        var env = GetViewport().FindWorld3D()?.Environment;
        if (env == null) return;
        _hazeSaved ??= (env.FogEnabled, env.VolumetricFogEnabled, env.GlowEnabled);
        var (fog, vfog, glow) = _hazeSaved.Value;
        env.FogEnabled = fog && !off;
        env.VolumetricFogEnabled = vfog && !off;
        env.GlowEnabled = glow && !off;
        Clouds.Shafts = !off;
        if (Post.Live != null) Post.Live.Visible = !off;
        if (off) { _dofSaved ??= _rig.Camera.Attributes; _rig.Camera.Attributes = null; }
        else if (_dofSaved != null) _rig.Camera.Attributes = _dofSaved;
        _hazeOff = off;
        GD.Print($"world: haze {(off ? "off" : "on")} (F11)");
    }

    private void HazeOff() => Haze(true);

    public override void _Ready()
    {
        var ready0 = Time.GetTicksMsec();
        Weather.Globals();
        WorldGen.Seed = Seed;
        // world.tscn holds everything editable as instances: the layout and the sites are read
        // from their nodes here, then freed; Terrain3D is the editor's (the game draws its own
        // ground and reads the sculpting from the files: TerrainEdit)
        if (GetNodeOrNull("Terrain") is { } t3d) { RemoveChild(t3d); t3d.QueueFree(); }
        _edit = GetNodeOrNull<Node3D>("Sites");
        var layoutNode = GetNodeOrNull<Node3D>("Layout");
        // the world's lines and spots (layout.tscn), before anything reads them
        Layout.Boot(layoutNode);
        if (layoutNode != null) { RemoveChild(layoutNode); layoutNode.QueueFree(); }
        _spawn = Layout.Spawn;   // the player's start (layout `World/Spawn`); --at= and friends override
        // the start weather and clock (res://world/look/weather.tres); the command line overrides it
        Look.ApplyWeather();
        _looks = System.Array.Exists(OS.GetCmdlineUserArgs(), a => a.Contains("light=") || a.Contains("look"));

        foreach (var arg in OS.GetCmdlineUserArgs())
        {
            if (arg.StartsWith("--seed=") && ulong.TryParse(arg[7..], out var s))
                WorldGen.Seed = Seed = s;
            if (arg.StartsWith("--view=") && int.TryParse(arg[7..], out var v))
                ViewChunks = v;
            if (arg.StartsWith("--shot=")) _shot = arg[7..];
            if (arg.StartsWith("--frames=") && int.TryParse(arg[9..], out var f))
                _shotAt = f;
            if (arg == "--demo") _demo = true;
            if (arg == "--bake") Bake.On = true;
            if (arg == "--bakecheck") Bake.Check = true;
            if (arg.StartsWith("--rebake=")) { Bake.On = true; foreach (var part in arg[9..].Split(",")) Bake.Rebake.Add(part); }
            if (arg == "--demo=hybrid") { _demo = true; _hybrid = true; }
            if (arg == "--top") _forceTop = true;   // bench: top-down everywhere
            if (arg == "--noclouds") Grade.Clouds = false;
            // the kit look is the default now; `--kit` stays accepted
            if (arg == "--kit") Village.UseKit = Terrain.Textured = true;
            if (arg == "--nokit") Village.UseKit = Terrain.Textured = false;
            if (arg == "--noproxy") Village.NoProxy = true;
            if (arg == "--waterdebug") Water.Debug = true;
            if (arg.StartsWith("--weather=")) Weather.Mode = arg[10..];
            if (arg == "--boat=demo") Boat.Demo = true;
            // `--storm=light|medium|blizzard`: the snowfall's strength, held
            if (arg.StartsWith("--storm="))
            {
                Snow.Level = System.Enum.Parse<Snow.Storm>(arg[8..], true);
                Snow.LevelHeld = true;
            }
            // `--snow=0..1`: the snow depth, held (captures)
            if (arg.StartsWith("--snow="))
            {
                Snow.Depth = float.Parse(arg[7..], System.Globalization.CultureInfo.InvariantCulture);
                Snow.Held = true;
            }
            if (arg == "--boat=ram") Boat.Demo = Boat.Ram = true;
            if (arg.StartsWith("--time="))
            {
                var hm = arg[7..].Split(':');
                Clock.Minutes = int.Parse(hm[0]) * 60f + (hm.Length > 1 ? int.Parse(hm[1]) : 0);
            }
            if (arg.StartsWith("--clock=")) Clock.Rate = float.Parse(arg[8..], System.Globalization.CultureInfo.InvariantCulture);
            if (arg.StartsWith("--wet=")) Weather.Wet = float.Parse(arg[6..], System.Globalization.CultureInfo.InvariantCulture);
            // `--faunacheck=N`: after N frames, count animals inside trunks or
            // on the wrong side of the waterline; exit 1 if any (Fauna.Violations).
            if (arg.StartsWith("--faunacheck=") && int.TryParse(arg[13..], out var fc)) _faunaCheck = fc;
            // The lighting study: a preset and dials, see Grade.Tune.
            if (arg.StartsWith("--light=")) { Grade.Tune(arg[8..]); _lightSet = true; }
            // Spawn elsewhere, in world metres: `--at=x,z`. For captures.
            if (arg.StartsWith("--at="))
            {
                var xz = arg[5..].Split(',');
                var inv = System.Globalization.CultureInfo.InvariantCulture;
                _spawn = new Vector2(float.Parse(xz[0], inv), float.Parse(xz[1], inv));
            }
            // Emberglass: `--citymap` writes the plan from above; `--city=N`
            // spawns at the city's Nth view (CityPlan.Views)
            if (arg == "--citymap") CitySite.WriteMap = true;
            if (arg.StartsWith("--city=") && int.TryParse(arg[7..], out var cv)) _spawn = CitySite.View(cv);
            // `--citytour`: a capture of every quarter's view, then quit
            if (arg == "--citytour") { CitySite.Tour = true; _spawn = CitySite.View(0); }
            // `--citybuild`: build the city (layout, checks, map), print its timings, quit
            if (arg == "--citybuild") CitySite.BuildOnly = true;
            if (arg == "--noghost") CitySite.NoGhost = true;
            if (arg == "--nosmoke") CitySite.NoSmoke = true;
            if (arg == "--nofolk") CitySite.NoFolk = true;
            if (arg == "--oldstreet") { CitySite.OldStreet = true; CitySite.Setts = null; }
            if (arg.StartsWith("--setts=")) CitySite.Setts = arg[8..];
            if (arg.StartsWith("--citycuts=")) CitySite.Cuts = arg[11..] == "none" ? "" : arg[11..];
            if (arg == "--cityfade") CitySite.Fade = true;
            if (arg == "--ssaohalf") RenderingServer.EnvironmentSetSsaoQuality(RenderingServer.EnvironmentSsaoQuality.Low, true, 0.5f, 2, 50f, 300f);
            if (arg.StartsWith("--cityshadowq=") && int.TryParse(arg[14..], out var csq)) CitySite.InsideShadow = (RenderingServer.ShadowQuality)csq;
            if (arg.StartsWith("--shadowq=") && int.TryParse(arg[10..], out var sq))
                RenderingServer.DirectionalSoftShadowFilterSetQuality((RenderingServer.ShadowQuality)sq);
            if (arg.StartsWith("--citynocast=")) CitySite.NoCast = arg[13..];
            if (arg.StartsWith("--cityrange="))
            {
                var r = arg[12..].Split(',');
                var inv = System.Globalization.CultureInfo.InvariantCulture;
                CitySite.NearRange = float.Parse(r[0], inv);
                if (r.Length > 1) CitySite.PropRange = float.Parse(r[1], inv);
            }
            if (arg.StartsWith("--texlab=") && int.TryParse(arg[9..], out var tl)) _texlab = tl;
            if (arg.StartsWith("--bench=") && int.TryParse(arg[8..], out var b)) _bench = b;
            // Bench while walking a straight line, so the run streams chunks the
            // way play does. A standing bench never builds a chunk after warmup.
            if (arg == "--walk") _walk = true;
            // `--walkaway`: walk down the view (along F), back to the camera
            if (arg == "--walkaway") { _walk = true; _walkAway = true; }
            if (arg.StartsWith("--snowlight=")) Grade.TuneSnow(arg[12..]);
            if (arg.StartsWith("--desertlight=")) Grade.TuneDesert(arg[14..]);
            // `--snowlook=clear|overcast|snowfall|sunset`: the snow sheet's atmospheres
            if (arg.StartsWith("--snowlook=") && Grade.SnowLooks.TryGetValue(arg[11..], out var look))
            {
                Grade.TuneSnow(look);
                if (look.Contains("fall:1")) Weather.Mode = "snow";
            }
            // `--sweep=specs.txt,outdir`: one snow grade per line ("name|dials"),
            // each settled for 45 frames and saved -- a whole lighting sweep
            // in one launch (scripts/forge/snow_sweep.py)
            if (arg.StartsWith("--sweep="))
            {
                var parts = arg[8..].Split(',');
                _sweepSpecs = System.IO.File.ReadAllLines(parts[0]);
                _sweepOut = parts[1];
            }
            // Keep vsync on: measures pacing as played. The budget is the
            // panel's period -- 8.33 ms on this machine's 120 Hz, not 16.7.
            if (arg == "--vsync") _vsync = true;
            // `--off=shadow,ssao,dof,glow,fog,msaa,pond,ship`: price one feature at a time.
            if (arg.StartsWith("--off=")) _off = arg[6..];
            // resolution A/B (2026-09-30, native resolution): `--scale3d=0.75`, `--upscale=fsr|fsr2|bilinear`, `--msaa=0|1|2|3`
            if (arg.StartsWith("--scale3d=")) _scale3d = float.Parse(arg[10..], System.Globalization.CultureInfo.InvariantCulture);
            if (arg.StartsWith("--upscale=")) _upscale = arg[10..];
            if (arg.StartsWith("--msaa=") && int.TryParse(arg[7..], out var ms)) _msaa = ms;
            if (arg.StartsWith("--renderh=")) RenderHeight = float.Parse(arg[10..], System.Globalization.CultureInfo.InvariantCulture);
            if (arg == "--crisp") Grade.SmoothTex = false;
            if (arg == "--nohaze") _startNoHaze = true;
            if (arg == "--breathe") CameraRig.Breathe = true;
            if (arg == "--nograss") Grass.Enabled = false;
            if (arg == "--noscatter") Scatter.Enabled = false;
            if (arg == "--nopost") Post.Enabled = false;
            // `--camtest`: the camera plan's checks and captures in one launch (Demo)
            if (arg == "--camtest") _camtest = true;
            if (arg == "--noshadowclouds") Clouds.Enabled = false;
            if (arg == "--noshafts") Clouds.Shafts = false;
            if (arg.StartsWith("--shafts=")) Clouds.ShaftStrength = float.Parse(arg[9..], System.Globalization.CultureInfo.InvariantCulture);
            if (arg.StartsWith("--citylight=")) Grade.TuneCity(arg[12..]);
            // `--camcheck`: the camera's street and landmark maths, asserted
            if (arg == "--camcheck") { var cf = CameraRig.SelfCheck(); SetProcess(false); GetTree().Quit(cf == 0 ? 0 : 1); return; }
            if (arg == "--meshhash") { MeshHash(); return; }
            if (arg == "--selftest") { SelfTest(); return; }
        }

        // The proof slice brings its own light unless one was asked for.
        if (Village.UseKit && !_lightSet) Grade.L = Grade.TwilightKit();
        // the edited lightings (res://world/look/*.tres), unless a lighting flag is tuning them
        _looks |= _lightSet;
        if (Bake.On) Look.Bake(_looks);
        Look.Apply(_looks);

        if (_bench > 0 || _camtest)
        {
            // Uncap, or the bench measures the frame cap. The first pair of
            // runs came back at exactly 5.000 ms with clouds on AND off,
            // which is a 200 fps limiter reporting itself, not a result.
            Engine.MaxFps = 0;
            if (!_vsync) DisplayServer.WindowSetVsyncMode(DisplayServer.VSyncMode.Disabled);
            RenderingServer.ViewportSetMeasureRenderTime(GetViewport().GetViewportRid(), true);
        }

        _chunkRoot = new Node3D { Name = "Chunks" };
        AddChild(_chunkRoot);

        BuildSky();
        BuildSun();
        // before any site: the city's texture arrays are built on its first load
        if (Bake.On) Bake.Assets();
        // the ground into Terrain3D for the editor (res://world/terrain.tscn), if not there yet
        // (a failure here must not stop the world booting: it aborted _Ready once and every frame threw)
        if (Bake.On) try { TerrainEdit.Bake(this); } catch (System.Exception e) { GD.PushError($"terrain bake failed: {e}"); }

        _player = new Player
        {
            Name = "Player",
            // Spawned above the ground: the chunk under it is built a frame or
            // two later and it drops onto the real collider.
            Position = new Vector3(_spawn.X, WorldGen.Height(_spawn.X, _spawn.Y) + 2f, _spawn.Y),
        };
        AddChild(_player);
        // The spawn is a placement, not motion: without this the first
        // interpolated frame lerps in from wherever the interpolation state
        // defaulted to, instead of starting exactly at the spawn point.
        _player.ResetPhysicsInterpolation();

        // The camera is a sibling, not a child of the player: it follows with a
        // lag, and a child node cannot lag its own parent.
        _rig = new CameraRig { Name = "CameraRig" };
        AddChild(_rig);
        _rig.Track(_player);
        // Low (8 deg) everywhere: the user's call after trying the hybrid,
        // 2026-09-23. `--demo=hybrid` still runs the outskirts rule; `--top`
        // leaves the rule null, which is top-down everywhere.
        // 8 deg everywhere but inside Emberglass's wall, where the camera rises
        // to the town pitch -- the second bake, 22 deg (user, 2026-09-24; the
        // references' towns sit at 20-25). Enter at the wall, leave 12 m out.
        // 2026-09-28 (user: "the 8 degree ... of the village looks good ... wire
        // that up let us test it"): 8 deg in the city too, on trial; `--city22`
        // brings back the town pitch below.
        var city22 = System.Array.IndexOf(OS.GetCmdlineUserArgs(), "--city22") >= 0;
        if (!_forceTop && !_hybrid && !city22) _rig.WantsLow = static (_, _) => true;
        else if (!_forceTop) _rig.WantsLow = _hybrid ? Village.WantsLow : static (p, low) =>
        {
            var q = CityPlan.ToPlan(p.X, p.Z);
            if (q.LengthSquared() > CityPlan.Outer * CityPlan.Outer) return true;
            var inside = CityPlan.InPoly(q, CityPlan.Encl);
            return low ? !inside : !(inside || CityPlan.PolyDist(q, CityPlan.Encl, true) < 12f);
        };
        // Inside Emberglass's wall the camera looks down the street (user,
        // 2026-09-24); everywhere else it keeps CameraRig.BaseYaw.
        _rig.StreetId = static p => CityPlan.StreetAt(p.X, p.Z);
        _rig.StreetAxis = static (p, id) => CityPlan.StreetAxis(p.X, p.Z, id);
        _player.Bind(_rig);

        // The village outskirts at the spawn. Static, so it is built once and
        // never streamed: it is small, and it is always the first thing seen.
        // Road puddles: not under --light= (the study frames must reproduce)
        // and not under --off=wet.
        if (_lightSet || _off.Contains("wet")) Village.Puddles = false;
        if (_lightSet) Breakables.Enabled = false;
        var village = new Village { Name = "Village" };
        AddChild(village);
        Bake.VillageNode = village;
        Bake.Begin("village", village, SiteNode("village"));
        village.Build(_player);
        Bake.End();
        // A test forest with animals, behind the camera at the spawn (a < -40
        // in the village's path space), so the spawn frame is unchanged.
        var wood = new Wildwood { Name = "Wildwood" };
        AddChild(wood);
        Bake.Begin("wildwood", wood, SiteNode("wildwood"));
        wood.Build(_player);
        Bake.End();
        // The water test site, on its own screen-left of the village.
        var site = new WaterSite { Name = "WaterSite" };
        AddChild(site);
        Bake.Begin("watersite", site, SiteNode("watersite"));
        site.Build(_player, village);
        Bake.End();
        // Snow: the depth, prints, snowfall and gusts; then the Hoarfells site,
        // whose trees it sheds and reloads.
        var snow = new Snow { Name = "Snow" };
        AddChild(snow);
        snow.Build(_player);
        // footprints in snow, sand and mud, wet ones after water, grains kicked up
        var prints = new Prints { Name = "Prints" };
        AddChild(prints);
        prints.Build(_player);
        var fells = new SnowSite { Name = "SnowSite" };
        AddChild(fells);
        Bake.Begin("snowsite", fells, SiteNode("snowsite"));
        fells.Build(village, snow);
        Bake.End();
        // The Ashdunes site: the market street, the temple, the oasis.
        var dunes = new DesertSite { Name = "DesertSite" };
        AddChild(dunes);
        Bake.Begin("desertsite", dunes, SiteNode("desertsite"));
        dunes.Build();
        Bake.End();
        // the four regions that were bare: the Emberwood, Duskfen, the Meadows, the Crags
        var regions = new RegionSites { Name = "RegionSites" };
        AddChild(regions);
        Bake.Begin("regions", regions, SiteNode("regions"));
        regions.Build(_player);
        Bake.End();
        // Emberglass, from the master plan, past the south edge.
        CameraRig.RevealsOn = OS.GetCmdlineUserArgs().Length == 0;
        CitySite.TeleportTo = Teleport;
        CitySite.TeleportToY = (x, y, z) =>
        {
            _player.GlobalPosition = new Vector3(x, y, z);
            _player.ResetPhysicsInterpolation();
            _rig.Track(_player);
        };
        var city = new CitySite { Name = "CitySite" };
        AddChild(city);
        Bake.Begin("city", city, SiteNode("city"));
        city.Build();
        Bake.End();
        if (CitySite.BuildOnly) { GetTree().Quit(); return; }
        // people and animals everywhere, one E key for talking and petting (baked to
        // res://world/city_life.tscn and village_life.tscn: Bake.Homes / Bake.Person)
        Bake.Begin("city_life", city, SiteNode("city_life"));
        city.Birds(_player);
        city.Watch(_player);
        city.Folk(_player, _rig);
        Bake.End();
        Bake.Begin("village_life", village, SiteNode("village_life"));
        village.Folk(_player, _rig);
        Bake.End();
        _edit?.QueueFree();
        var interactor = new Interactor { Name = "Interactor" };
        AddChild(interactor);
        interactor.Bind(_player);
        // the region's name on entering it
        var banner = new Banner { Name = "Banner" };
        AddChild(banner);
        banner.Bind(_player);
        // motes in the city's sun, fireflies in the twilight
        var air = new Air { Name = "Air" };
        AddChild(air);
        air.Bind(_player);
        // the pots, crates and bales every site set down (Breakables.Add), drawn
        var breakables = new Breakables { Name = "Breakables" };
        AddChild(breakables);
        breakables.Build(_player);
        // the whole map's trees, undergrowth and rocks, streamed (not under --light=:
        // the study's frames must reproduce)
        if (Scatter.Enabled && !_lightSet)
        {
            var scatter = new Scatter { Name = "Scatter" };
            AddChild(scatter);
            scatter.Bind(_player);
        }
        // grass tufts on every grass ground; every site has registered its
        // cleared shapes by now (Grass.Bind closes the registry)
        if (Grass.Enabled)
        {
            var grass = new Grass { Name = "Grass" };
            AddChild(grass);
            grass.Bind(_player);
        }

        // Weather. The lighting study runs dry: its frames must reproduce --
        // and cloudless, for the same reason.
        if (_lightSet || _camtest) Weather.Mode = "clear";
        if (_lightSet || _sweepSpecs.Length > 0) Clouds.Enabled = false;
        Weather.Quiet = (_shot != "" || _bench > 0 || _lightSet || _faunaCheck > 0 || _sweepSpecs.Length > 0 || _camtest || CitySite.Tour)
                        && System.Array.IndexOf(OS.GetCmdlineUserArgs(), "--hud") < 0;
        var weather = new Weather { Name = "Weather" };
        AddChild(weather);
        if (_texlab >= 0) TexLib.Lab(this, _texlab);

        if (_demo)
        {
            // The demo starts once the ground under the spawn exists: it drives
            // the player, and a player still falling through an unbuilt chunk is
            // not what any of the captures are meant to show.
            var demo = new Demo { Name = "Demo" };
            AddChild(demo);
            if (_hybrid) demo.BeginHybrid(_player, _rig);
            else demo.Begin(_player);
        }

        if (_camtest)
        {
            var ct = new CamTest { Name = "CamTest" };
            AddChild(ct);
            ct.Begin(_player, _rig);
        }

        var env = GetNode<WorldEnvironment>("Env").Environment;
        _env = env;
        CitySite.Env = env;
        CitySite.Port = GetViewport();
        weather.Build(_player, _sun!, env);
        // the dreamy finish: ground mist, violet shade, peach light, soft bloom
        if (Post.Enabled)
        {
            var post = new Post { Name = "Post" };
            AddChild(post);
            post.Bind(_player, env);
        }
        Save.Load();
        // Cloud shadows (and, through the fog, the shafts): see Clouds.
        var clouds = new Clouds();
        AddChild(clouds);
        clouds.Build(_player, _sun!, _rig.Camera);
        weather.Soakable(village);
        weather.Body(_player);
        Rescale();
        GetWindow().SizeChanged += Rescale;
        // a second in, once Weather and the camera have set up their own look
        if (_startNoHaze) { Clouds.Shafts = false; CallDeferred(nameof(HazeOff)); GetTree().CreateTimer(1.0).Timeout += () => Haze(true); }
        if (_scale3d > 0f) GetViewport().Scaling3DScale = _scale3d;
        if (_upscale != "") GetViewport().Scaling3DMode = _upscale switch
        {
            "fsr" => Viewport.Scaling3DModeEnum.Fsr, "fsr2" => Viewport.Scaling3DModeEnum.Fsr2, _ => Viewport.Scaling3DModeEnum.Bilinear,
        };
        if (_msaa >= 0) GetViewport().Msaa3D = (Viewport.Msaa)_msaa;
        foreach (var o in _off.Split(',', System.StringSplitOptions.RemoveEmptyEntries))
            switch (o)
            {
                case "shadow": GetNode<DirectionalLight3D>("Sun").ShadowEnabled = false; break;
                case "ssao": env.SsaoEnabled = false; break;
                case "glow": env.GlowEnabled = false; break;
                case "fog": env.FogEnabled = false; break;
                case "vfog": env.VolumetricFogEnabled = false; break;
                case "dof": _rig.Camera.Attributes = null; break;
                case "msaa": GetViewport().Msaa3D = Viewport.Msaa.Disabled; break;
                case "wood": wood.QueueFree(); break;
                case "pond": site.QueueFree(); break;
                case "ship": Ship.Current?.QueueFree(); Ship.Current = null; break;
                case "wet": break;   // handled before the village is built
                default: GD.PushWarning($"--off: unknown feature '{o}'"); break;
            }

        GD.Print($"world: ready in {Time.GetTicksMsec() - ready0} ms");
        GD.Print($"world: seed={WorldGen.Seed} view={ViewChunks} "
                 + $"chunk={Terrain.Size}m cell={Terrain.Cell}m "
                 + $"physics={ProjectSettings.GetSetting("physics/3d/physics_engine")}");
        // every site recorded this run to res://world/<site>.tscn; what the baked ones fed
        if (Bake.On) Bake.WriteSites();
        if (Bake.Check) Bake.CheckFed();
        // a few seconds of frames, so every material compiles and its errors reach the log,
        // then the sheet it wrote, photographed
        if (Bake.On) { var tree = GetTree(); tree.CreateTimer(5.0).Timeout += () => _ = Bake.Shots(tree); }
    }

    public override void _Notification(int what)
    {
        if (what == NotificationWMCloseRequest) Save.Write();
    }

    private readonly HashSet<string> _revealed = new();
    private int _revealWait = 120;

    /// <summary>Camera plan Phase 5: the first time the player is well inside
    /// a region, open the frame on its landmark (CameraRig.Reveal). Not in the
    /// first two seconds (the spawn's own region is not "entered").</summary>
    private void Reveals()
    {
        if (!CameraRig.RevealsOn) return;
        var p = _player.GlobalPosition;
        if (_revealWait > 0)
        {
            _revealWait--;
            if (_revealWait == 0)
            {
                if (Weather.CityHere > 0.6f) _revealed.Add("city");
                if (Snow.Here > 0.6f) _revealed.Add("snow");
                if (Weather.DunesHere > 0.6f) _revealed.Add("dunes");
            }
            return;
        }
        (string Name, Vector2 At, float Up)? r =
            Weather.CityHere > 0.6f ? ("city", CityPlan.ToWorld(new Vector2(118f, 108f)), CityPlan.BaseLevel() + CityPlan.CitadelLv + 14f)
            : Snow.Here > 0.6f ? ("snow", SnowSite.Castle, float.NaN)
            : Weather.DunesHere > 0.6f ? ("dunes", DesertSite.Temple, float.NaN)
            : null;
        if (r is not { } v || !_revealed.Add(v.Name)) return;
        var y = float.IsNaN(v.Up) ? WorldGen.Height(v.At.X, v.At.Y) + 8f : v.Up;
        // a landmark far off would be a long swoop: at most 70 m from the player
        var from = new Vector3(v.At.X, y, v.At.Y);
        var d = from - p;
        if (d.Length() > 70f) from = p + d.Normalized() * 70f;
        _rig.Reveal(from, 2.8f);
        GD.Print($"camera: reveal {v.Name}");
    }

    public override void _Process(double delta)
    {
        CitySite.Region(_player.GlobalPosition);
        LampLight.Tick(_player.GlobalPosition, (float)delta);
        Reveals();
        Save.Tick((float)delta);
        if (_faunaCheck > 0)
        {
            // every frame, not just the last: a pass-through is momentary
            var bad = 0;
            foreach (var f in Fauna.All) bad += f.Violations();
            if (bad > 0) _faunaFrames++;
            if (_faunaCheck % 1200 == 0)
            {
                int near = 0, of = 0;
                foreach (var f in Fauna.All) { var (n, o) = f.Sheltered(); near += n; of += o; }
                GD.Print($"faunacheck: rain {Weather.Rain:F2} puddles {Weather.Wet:F2} ground {Weather.Damp:F2} | small animals by a trunk {near}/{of}");
            }
            _faunaWorst = Mathf.Max(_faunaWorst, bad);
            if (--_faunaCheck == 0)
            {
                foreach (var f in Fauna.All)
                {
                    var (blk, walked) = f.Stats();
                    GD.Print($"faunacheck: {f.GetParent().Name}: {f.Count} animals, {blk} blockers, walked {walked:F0} m");
                    foreach (var o in f.Offenders()) GD.Print($"faunacheck:   offender {o}");
                }
                GD.Print($"faunacheck: player at {_player.GlobalPosition}");
                GD.Print($"faunacheck: frames with a violation {_faunaFrames}, worst {_faunaWorst} -> {(_faunaFrames == 0 ? "PASS" : "FAIL")}");
                GetTree().Quit(_faunaFrames == 0 ? 0 : 1);
            }
        }
        if (_player != null)
        {
            var at = _player.GetGlobalTransformInterpolated().Origin;
            Foliage.Track(at, (float)delta);
            Water.Tick(at, (float)delta);
            Impact.Tick((float)delta);
        }
        // The sun follows the camera mode. The low outskirts view wants a
        // raking 14-degree backlight for long shadows down the road; the same
        // sun over a top-down frame turned the whole ground into shadow streaks
        // (measured 0.19 mean luminance), so top-down areas get it at 40.
        if (_sun != null && _rig != null)
        {
            // the top grade was tuned for the hybrid's 38 deg frame; the town
            // pitch lives under the city's own grade (Weather)
            var k = _hybrid || _forceTop ? _rig.Blend : 0f;
            _sun.RotationDegrees = new Vector3(Mathf.Lerp(-Grade.L.Elev, -40f, k), Grade.L.Yaw, 0f);
            // ...and so does the grade. The low grade was tuned against the low
            // frame; applied unchanged to the top-down frame, with the sun now
            // high on a ground plane that fills the picture, it measured mean
            // 0.473 and saturation 0.603 against 0.30-0.40 and 0.45-0.52.
            if (_env != null)
            {
                _env.TonemapExposure = Mathf.Lerp(Grade.L.Exposure, Grade.TopExposure, k);
                _env.AdjustmentSaturation = Mathf.Lerp(Grade.L.Saturation, Grade.TopSaturation, k);
            }
        }

        if (_walk) _player.Drive(_walkAway ? new Vector3(-0.7071f, 0f, -0.7071f) : Vector3.Right, false, false, false, false);
        Stream();
        Capture();
        Sweep();
        Bench();

        // Generation (WorldGen.Height/Albedo — ~38 ms of the old 45 ms chunk)
        // now runs on worker tasks; only node creation, mesh upload and the
        // collider stay on the main thread, at most one chunk integrated per
        // frame. That used to be a whole synchronous Build() per boundary
        // crossing — a visible hitch exactly when the camera is moving.
        while (_pending.Count < MaxPending && _queue.Count > 0)
        {
            var c = _queue[0];
            _queue.RemoveAt(0);
            _pending[c] = Task.Run(() => Terrain.Generate(c));
        }

        Vector2I? done = null;
        foreach (var (c, task) in _pending)
            if (task.IsCompleted) { done = c; break; }

        if (done is { } key)
        {
            var task = _pending[key];
            _pending.Remove(key);

            if (task.IsFaulted)
            {
                GD.PushError($"chunk {key}: {task.Exception}");
            }
            else if (!_wanted.Contains(key) || _live.ContainsKey(key))
            {
                // Left range, or already built, while it was generating.
            }
            else
            {
                var chunk = new Terrain { Coord = key, Name = $"C{key.X}_{key.Y}" };
                _chunkRoot.AddChild(chunk);
                var t0 = Time.GetTicksUsec();
                chunk.Build(task.Result);
                var ms = (Time.GetTicksUsec() - t0) / 1000.0;
                _chunkMs += ms;
                _builtMs += ms;
                _chunkWorst = Mathf.Max(_chunkWorst, ms);
                _chunkCount++;
                _live[key] = chunk;
            }
        }
    }

    /// <summary>Frame-time distribution over a run, plus what the frame is made
    /// of.
    ///
    /// The average alone was the wrong instrument: "lagging" is almost never the
    /// mean, it is the worst one percent. A run that averages 3.9 ms and spikes
    /// to 60 every time a chunk is built feels broken and measures fine.
    /// </summary>
    private void Bench()
    {
        if (_bench == 0) return;
        if (_camtest && !CamTest.BenchGo) { _tick = Time.GetTicksUsec(); return; }
        // Wall clock between frames, not `delta`: with vsync on, Godot's delta
        // smoothing snaps delta to the refresh period and hides a missed vblank.
        var now = Time.GetTicksUsec();
        var dt = (now - _tick) / 1000.0;
        _tick = now;
        var built = _builtMs;
        _builtMs = 0;
        if (_frame < 120) { _frame++; return; }

        _times.Add(dt);
        if (built > 0) _chunkFrames.Add(dt);
        _gpu.Add(RenderingServer.ViewportGetMeasuredRenderTimeGpu(GetViewport().GetViewportRid()));

        // Judder: where the player is DRAWN, frame to frame. Physics at 60 Hz
        // under a faster display leaves the drawn position unchanged for most
        // frames and then jumps it. One frame of camera skew (World processes
        // before CameraRig) cancels out at a steady walk.
        var p = _player.GetGlobalTransformInterpolated().Origin;
        var sp = _rig.Camera.UnprojectPosition(p);
        if (!float.IsNaN(_lastP.X))
        {
            if ((p - _lastP).LengthSquared() < 1e-10f) _stale++;
            _jitter.Add((sp - _lastS).Length());
        }
        _lastP = p;
        _lastS = sp;

        if (_times.Count < _bench) return;

        var s = new List<double>(_times);
        s.Sort();
        double P(double q) => s[Mathf.Clamp((int)(q * s.Count), 0, s.Count - 1)];
        var mean = 0.0;
        foreach (var v in s) mean += v;
        mean /= s.Count;

        var refresh = DisplayServer.ScreenGetRefreshRate();
        var budget = refresh > 0 ? 1000.0 / refresh : 1000.0 / 60.0;
        var missed = 0;
        foreach (var v in s) if (v > budget * 1.5) missed++;

        _gpu.Sort();
        var gpuMean = 0.0;
        foreach (var v in _gpu) gpuMean += v;
        gpuMean /= _gpu.Count;
        var chunkMean = 0.0;
        foreach (var v in _chunkFrames) chunkMean += v;
        if (_chunkFrames.Count > 0) chunkMean /= _chunkFrames.Count;
        _chunkFrames.Sort();
        _jitter.Sort();
        var jRms = 0.0;
        foreach (var v in _jitter) jRms += v * v;
        jRms = System.Math.Sqrt(jRms / Mathf.Max(_jitter.Count, 1));

        GD.Print($"bench: {s.Count} frames  mean {mean:F2}  p50 {P(0.50):F2}  "
                 + $"p95 {P(0.95):F2}  p99 {P(0.99):F2}  max {s[^1]:F2} ms  "
                 + $"(clouds={Grade.Clouds} off='{_off}' walk={_walk} vsync={_vsync})");
        GD.Print($"gpu: mean {gpuMean:F2}  p99 {_gpu[Mathf.Clamp((int)(0.99 * _gpu.Count), 0, _gpu.Count - 1)]:F2} ms  "
                 + $"|  refresh {refresh:F0} Hz, frames over 1.5x budget ({budget:F2} ms): {missed} "
                 + $"({100.0 * missed / s.Count:F1}%)");
        GD.Print($"chunk frames: {_chunkFrames.Count}  mean {chunkMean:F2}  "
                 + $"max {(_chunkFrames.Count > 0 ? _chunkFrames[^1] : 0):F2} ms");
        GD.Print($"judder: drawn position unchanged on {100.0 * _stale / Mathf.Max(_jitter.Count, 1):F1}% of frames, "
                 + $"screen step rms {jRms:F2} px, p99 {(_jitter.Count > 0 ? _jitter[(int)(0.99 * (_jitter.Count - 1))] : 0):F2} px  "
                 + $"|  physics {Engine.PhysicsTicksPerSecond} Hz, interpolation {GetTree().PhysicsInterpolation}");
        GD.Print($"scene: draw calls {Performance.GetMonitor(Performance.Monitor.RenderTotalDrawCallsInFrame):F0}  "
                 + $"prims {Performance.GetMonitor(Performance.Monitor.RenderTotalPrimitivesInFrame):F0}  "
                 + $"objects {Performance.GetMonitor(Performance.Monitor.RenderTotalObjectsInFrame):F0}  "
                 + $"vram {Performance.GetMonitor(Performance.Monitor.RenderVideoMemUsed) / 1048576.0:F1} MB  "
                 + $"chunks {_live.Count}");
        GD.Print($"chunk build: {_chunkCount} chunks, mean {(_chunkCount > 0 ? _chunkMs / _chunkCount : 0):F2} ms, "
                 + $"worst {_chunkWorst:F2} ms, worker gen {Terrain.GenUsec / 1000.0 / Mathf.Max(_chunkCount, 1):F2} ms/chunk  |  "
                 + $"stream replans {_streamScans}");
        GD.Print($"  of which: surface+mesh {Terrain.MeshUsec / 1000.0 / Mathf.Max(_chunkCount, 1):F2} ms/chunk, "
                 + $"trimesh collider {Terrain.ColliderUsec / 1000.0 / Mathf.Max(_chunkCount, 1):F2} ms/chunk");
        GetTree().Quit();
    }

    /// <summary>`--meshhash`: hash probe chunks' ground mesh as the GPU holds it,
    /// plus their collider faces, then quit. Run before and after any change to
    /// how a chunk is built: equal hashes mean the ground and its collision did
    /// not move by one bit. Probes cover every biome, negative coordinates, the
    /// Fen's water and the world-edge mountains.</summary>
    private void MeshHash()
    {
        foreach (var c in Probes)
        {
            var t = new Terrain { Coord = c };
            AddChild(t);
            t.Build(Terrain.Generate(c));

            ulong h = 14695981039346656037UL;
            void Mix(float f) => h = (h ^ (uint)System.BitConverter.SingleToInt32Bits(f)) * 1099511628211UL;
            var a = t.GetNode<MeshInstance3D>("Ground").Mesh.SurfaceGetArrays(0);
            var verts = a[(int)Mesh.ArrayType.Vertex].AsVector3Array();
            foreach (var v in verts) { Mix(v.X); Mix(v.Y); Mix(v.Z); }
            foreach (var v in a[(int)Mesh.ArrayType.Normal].AsVector3Array()) { Mix(v.X); Mix(v.Y); Mix(v.Z); }
            foreach (var v in a[(int)Mesh.ArrayType.Color].AsColorArray()) { Mix(v.R); Mix(v.G); Mix(v.B); Mix(v.A); }
            var mesh = h;

            h = 14695981039346656037UL;
            var shape = (ConcavePolygonShape3D)t.GetNode("Solid").GetChild<CollisionShape3D>(0).Shape;
            var faces = shape.GetFaces();
            foreach (var v in faces) { Mix(v.X); Mix(v.Y); Mix(v.Z); }

            GD.Print($"meshhash {c}: mesh {mesh:x16} collider {h:x16} "
                     + $"verts {verts.Length} faces {faces.Length} water {t.HasNode("Water")}");
            t.Free();
        }
        SetProcess(false);   // _Ready returned early: there is no player to stream around
        GetTree().Quit();
    }

    /// <summary>
    /// Screenshot and quit, for checking a change without sitting in
    /// front of the window. It waits a set number of frames because the
    /// streamer builds one chunk per frame — capture on frame 1 and the
    /// picture is of an empty world.
    /// </summary>
    /// <summary>`--sweep=`: after 240 frames of warm-up (chunks, shader
    /// compiles), each spec in turn: set it, hold 45 frames, save.</summary>
    private void Sweep()
    {
        if (_sweepSpecs.Length == 0) return;
        if (_sweepI < 0)
        {
            if (++_sweepF < 240) return;
            _sweepI = 0;
            _sweepF = 0;
            SweepApply();
            return;
        }
        if (++_sweepF < _sweepHold) return;
        var name = _sweepSpecs[_sweepI].Split('|')[0];
        GetViewport().GetTexture().GetImage().SavePng(System.IO.Path.Combine(_sweepOut, name + ".png"));
        GD.Print($"sweep: {name} <- {_sweepSpecs[_sweepI].Split('|')[1]}");
        _sweepF = 0;
        if (++_sweepI >= _sweepSpecs.Length) { GetTree().Quit(); return; }
        SweepApply();
    }

    /// <summary>F1-F6 in play: travel to the places built so far -- the
    /// village, the lake and its ship, the Hoarfells' lamp walk, the
    /// Ashdunes' market, temple approach and oasis. They lie 100-600 m apart
    /// with no road between, and before this only `--at=` reached them
    /// (user: "nothing is wired up", 2026-09-23). Not while rowing.</summary>
    public override void _UnhandledInput(InputEvent e)
    {
        if (e is not InputEventKey { Pressed: true, Echo: false } k || Boat.Aboard) return;
        if (k.Keycode == Key.F10) { Weather.ShowKeys = !Weather.ShowKeys; return; }
        if (k.Keycode == Key.F11) { Haze(!_hazeOff); return; }
        // Keycode, not PhysicalKeycode: F-keys don't move with layout, and a
        // key sent without a scancode (SendKeys, some Fn layers) reads phys=Pause.
        Vector2? to = k.Keycode switch
        {
            Key.F1 => _spawn,
            // on the bank behind the boat, looking over it to the ship
            Key.F2 => Boat.Current is { } b ? new Vector2(b.GlobalPosition.X, b.GlobalPosition.Z) + new Vector2(0.7071f, 0.7071f) * 4f : null,
            Key.F3 => SnowSite.Vista,
            Key.F4 => SnowSite.PathAt(21, 22, 20f),
            Key.F5 => SnowSite.PathAt(23, 24, 62f),
            Key.F6 => SnowSite.PathAt(25, 26, 30f),
            Key.F7 => CitySite.View(0),
            Key.F8 => CitySite.NextView(),
            // the four new regions in turn, at each scene's approach (the lens side)
            Key.F9 => NextRegion(),
            _ => null,
        };
        if (to is { } p) Teleport(p.X, p.Y);
    }

    private int _region = -1;
    private static readonly Biome[] RegionOrder = { Biome.Emberwood, Biome.Fen, Biome.Meadow, Biome.Crags };

    /// <summary>F9: the next of the four new regions' scenes, a few metres toward the lens.</summary>
    private Vector2? NextRegion()
    {
        _region = (_region + 1) % RegionOrder.Length;
        if (!RegionSites.Scenes.TryGetValue(RegionOrder[_region], out var s)) return null;
        return s.At + new Vector2(0.7071f, 0.7071f) * 6f;
    }

    /// <summary>Put the player at (x, z) on the ground and snap the camera
    /// there (its follow eases: after a long jump it was still travelling).</summary>
    private void Teleport(float x, float z)
    {
        _player.GlobalPosition = new Vector3(x, WorldGen.Height(x, z) + 0.6f, z);
        _player.ResetPhysicsInterpolation();
        _rig.Track(_player);
    }

    /// <summary>Set the current spec's grade; a third field `x,z` moves the
    /// player there first (several views in one launch) and holds 120
    /// frames so the camera and the chunks settle.</summary>
    private void SweepApply()
    {
        var f = _sweepSpecs[_sweepI].Split('|');
        // a look name stands for its dials; `fall:1` turns the snowfall on
        var dials = Grade.SnowLooks.TryGetValue(f[1], out var look) ? look : f[1];
        Grade.TuneSnow(dials);
        var fall = dials.Contains("fall:1");
        Weather.Mode = fall ? "snow" : "clear";
        Weather.Rain = fall ? 1f : 0f;
        _sweepHold = 45;
        if (f.Length < 3 || f[2] == "") return;
        var xz = f[2].Split(',');
        var inv = System.Globalization.CultureInfo.InvariantCulture;
        Teleport(float.Parse(xz[0], inv), float.Parse(xz[1], inv));
        _sweepHold = 120;
    }

    private void Capture()
    {
        if (_shot == "") return;
        if (++_frame < _shotAt) return;

        var img = GetViewport().GetTexture().GetImage();
        img.SavePng(_shot);
        GD.Print($"shot -> {_shot} after {_frame} frames, {_live.Count} chunks");
        GD.Print("player: " + _player.Report());
        if (_texlab >= 0) TexLib.Report(_rig.Camera);
        GD.Print($"camera: pitch {Mathf.RadToDeg(_rig.PitchRad):F1} deg, "
                 + $"outskirts {Village.WantsLow(_player.GlobalPosition, false)}");
        GetTree().Quit();
    }

    /// <summary>Replan what to load only when the player has actually left the
    /// centre chunk, by an <see cref="Hysteresis"/> margin past its edge.
    ///
    /// The spawn sits on a chunk corner (0, 0), and ordinary movement noise
    /// dithers z by ±0.0000–0.006 across z=0. Recentring on every sign flip of
    /// that dither rebuilt a whole row of 7 chunks each time — a walk that
    /// needed 63 chunks built 119.
    ///
    /// The margin is PER AXIS. Gating both axes together still re-read the
    /// dithering z whenever x crossed, and flipped a row on some crossings:
    /// 46 builds on a walk that needed 34.
    /// </summary>
    private void Stream()
    {
        var at = _player.GlobalPosition;
        var centre = new Vector2I(Axis(at.X, _centre.X), Axis(at.Z, _centre.Y));
        if (centre == _centre) return;

        var was = _centre;
        _centre = centre;
        if (_bench > 0) GD.Print($"stream: centre {was} -> {_centre} at x={at.X:F3} z={at.Z:F4}");
        _streamScans++;   // counts replans, not per-frame scans

        _wanted.Clear();
        for (var dy = -ViewChunks; dy <= ViewChunks; dy++)
        for (var dx = -ViewChunks; dx <= ViewChunks; dx++)
            _wanted.Add(new Vector2I(_centre.X + dx, _centre.Y + dy));

        _queue.RemoveAll(c => !_wanted.Contains(c));

        foreach (var c in _wanted)
            if (!_live.ContainsKey(c) && !_pending.ContainsKey(c) && !_queue.Contains(c))
                _queue.Add(c);

        // Nearest first, so the ground under the camera exists before the ring
        // at the horizon does.
        _queue.Sort((a, b) =>
            (a - _centre).LengthSquared().CompareTo((b - _centre).LengthSquared()));

        var stale = new List<Vector2I>();
        foreach (var (c, _) in _live)
            if (!_wanted.Contains(c)) stale.Add(c);
        foreach (var c in stale)
        {
            _live[c].QueueFree();
            _live.Remove(c);
        }
    }

    /// <summary>The ring's centre chunk on one axis: kept while the player is
    /// within <see cref="Hysteresis"/> metres of it, else the chunk under them.</summary>
    private static int Axis(float p, int centre) =>
        centre != int.MinValue
        && p >= centre * Terrain.Size - Hysteresis
        && p < (centre + 1) * Terrain.Size + Hysteresis
            ? centre
            : Mathf.FloorToInt(p / Terrain.Size);

    /// <summary>Pins two properties the streaming rewrite depends on. First,
    /// that <see cref="WorldGen"/>'s per-thread scratch really does make
    /// <see cref="Terrain.Generate"/> safe to run concurrently: eight
    /// concurrent generations of the same chunk must come back byte-identical
    /// to a single-threaded one. Second, that the mesh, the collider and the
    /// player's ground clamp agree on where the ground is: every vertex's Y is
    /// exactly <see cref="WorldGen.Height"/> at that vertex's (X, Z).</summary>
    private void SelfTest()
    {
        var fails = 0;
        foreach (var c in Probes)
        {
            var main = Terrain.Generate(c);
            var par = new Terrain.Data[8];
            Parallel.For(0, 8, k => par[k] = Terrain.Generate(c));

            var concurrency = 0;
            foreach (var p in par)
                if (!p.Verts.SequenceEqual(main.Verts)
                    || !p.Normals.SequenceEqual(main.Normals)
                    || !p.Colors.SequenceEqual(main.Colors)
                    || p.Lowest != main.Lowest)
                    concurrency++;

            var ground = 0;
            foreach (var v in main.Verts)
                if (v.Y != WorldGen.Height(v.X, v.Z)) ground++;

            var lengths = main.Verts.Length == 13824 && main.Normals.Length == 13824
                          && main.Colors.Length == 13824 ? 0 : 1;

            var probeFails = concurrency + ground + lengths;
            fails += probeFails;
            GD.Print($"selftest {c}: concurrency-mismatches {concurrency}  ground-mismatches {ground}  "
                     + $"length-fails {lengths}  fails {probeFails}");
        }

        GD.Print(fails == 0 ? "selftest: PASS" : $"selftest: FAIL ({fails})");
        SetProcess(false);
        GetTree().Quit(fails == 0 ? 0 : 1);
    }

    /// <summary>Sky, environment and the vignette. The numbers live in
    /// <see cref="Grade"/>, aimed at the reference set's measured targets.</summary>
    private void BuildSky()
    {
        AddChild(new WorldEnvironment { Name = "Env", Environment = Look.Environment(_looks) ?? Grade.Build() });
        AddChild(Grade.Vignette());
    }

    private void BuildSun()
    {
        var sun = _sun = new DirectionalLight3D
        {
            Name = "Sun",
            LightColor = Grade.L.Sun,
            LightEnergy = Grade.L.SunEnergy,
            LightAngularDistance = Grade.L.Soft,
            ShadowEnabled = true,
            // TWO cascades over 80 m, not four over 220. Measured with the
            // village at the spawn: the sun's cascades were ~900 of 1079 draw
            // calls, ~1.45 M of 2.0 M primitives and ~1.8 ms of GPU (6.5-6.8 ms
            // with shadows against 4.7-4.8 without). Each cascade is another
            // full pass over every house and tree inside it; past 80 m the fog
            // owns the frame and nobody can see a cascade's worth of detail.
            DirectionalShadowMode = DirectionalLight3D.ShadowMode.Parallel2Splits,
            DirectionalShadowMaxDistance = 80f,
            DirectionalShadowBlendSplits = false,
            // A long shadow from a low sun lands in bands across the ground and
            // is most of the frame's dark material at dusk.
            ShadowBias = 0.04f,
            ShadowNormalBias = 1.4f,
        };
        // BACKLIT: the sun sits beyond the far end of the road and its light
        // travels toward the camera, as in the reference frame. Every house,
        // tree and lamp post then casts its shadow down the road at the viewer,
        // which is where the frame's dark material comes from -- the dark-pixel
        // target that an empty lit plain could never reach. Yaw -148 is a
        // little off the camera axis (-135) so the shadows fall diagonally
        // across the road instead of hiding straight behind their casters.
        sun.RotationDegrees = new Vector3(-Grade.L.Elev, Grade.L.Yaw, 0f);
        AddChild(sun);

        // The cool fill. It casts no shadow and exists to keep the shadow side
        // blue rather than black: warm key against cool fill is the split every
        // reference frame uses.
        AddChild(new DirectionalLight3D
        {
            Name = "Fill",
            LightColor = Grade.L.Fill,
            LightEnergy = Grade.L.FillEnergy,
            ShadowEnabled = false,
            // From the camera side, so the faces turned toward the viewer --
            // which the backlit key leaves in shadow -- still read, in blue.
            RotationDegrees = new Vector3(-32f, 45f, 0f),
        });
    }
}
