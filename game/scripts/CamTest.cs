using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// `-- --camtest [--bench=N]`: the camera and sky checks in one launch.
///
/// A list of timed steps, each printing `check:` lines, then a pricing pass
/// in the market that toggles the city's sky features one at a time and
/// times each (`price:` lines). Every 0.1 s a `camlog:` line; captures are
/// `shot_cam_*.png`. It drives the player through <see cref="Player.DriveKeys"/>
/// where the test is about input (the latch), so the camera-relative mapping
/// is the one exercised, not bypassed.
/// </summary>
public partial class CamTest : Node
{
    /// <summary>With `--bench=N`, World's bench waits for this and then times
    /// the market standing still.</summary>
    public static bool BenchGo;

    private sealed record Step(string Name, float Hold, System.Action? Enter, System.Action<float>? Tick, System.Action? Exit);

    private static readonly Vector3 Right = new(0.7071f, 0f, -0.7071f);
    private Player _p = null!;
    private CameraRig _cam = null!;
    private readonly List<Step> _steps = new();
    private int _i = -1;
    private float _t, _logT;
    private int _drawn;
    private bool _held;
    private readonly List<string> _shots = new();
    private readonly Dictionary<string, float> _v = new();

    public void Begin(Player player, CameraRig cam)
    {
        _p = player;
        _cam = cam;
        Prices();
        // `--contentshots` (the overnight content, framed: each target placed
        // ahead of the player along the base view, so it sits in the frame),
        // `--citywalk` and `--camsweep` chain in that order in one launch (the
        // sweep last: it holds the clouds off) -- the user caps a request at
        // 1-2 launches
        var args = OS.GetCmdlineUserArgs();
        // `--folkprice`: what the townsfolk and the town animals cost, priced
        // by hiding them -- A B A B in the market, then A B in the village, in
        // one launch (INVARIANTS: the price table drifts even inside one)
        if (args.Contains("--folkprice"))
        {
            void Folk(bool on)
            {
                foreach (var n in new[] { "CityFolk", "VillageFolk", "CityPets", "FarmAnimals", "VillagePets" })
                    if (GetTree().CurrentScene.FindChild(n, true, false) is Node3D x)
                    {
                        x.Visible = on;
                        x.ProcessMode = on ? ProcessModeEnum.Inherit : ProcessModeEnum.Disabled;
                    }
            }
            _price = new (string, System.Action, System.Action)[]
            {
                ("m_folk", () => { Tp(0f, -8f); Folk(true); }, () => { }),
                ("m_nofolk", () => Folk(false), () => Folk(true)),
                ("m_folk2", () => { }, () => { }),
                ("m_nofolk2", () => Folk(false), () => Folk(true)),
                ("v_folk", () => CitySite.TeleportTo?.Invoke(-12f, -12f), () => { }),
                ("v_nofolk", () => Folk(false), () => Folk(true)),
            };
            if (args.Contains("--looksweep")) LookSweep();
            FolkShots();
            _steps.Add(new("fp_settle", 4f, () => Tp(0f, -8f), _ => Stop(), null));
            return;
        }
        // `--groundshots` (2026-09-27, "the ground is too flat"): the ground in
        // every region that has grass, then the grass priced by hiding it --
        // A B A B in a city street with verges, A B in the village
        if (args.Contains("--groundshots"))
        {
            // (grass priced 2026-09-27; now the post stack: each pair also
            // leaves a with / without frame, shot_price_*)
            static void On(bool on) => Post.Live?.Set(on);
            _price = new (string, System.Action, System.Action)[]
            {
                ("v_post", () => { CitySite.TeleportTo?.Invoke(-12f, -12f); On(true); }, () => { }),
                ("v_nopost", () => On(false), () => On(true)),
                ("s_post", () => Tp(55f, 12f), () => { }),
                ("s_nopost", () => On(false), () => On(true)),
                ("m_post", () => CitySite.TeleportTo?.Invoke(-31.8f, 88.4f), () => { }),
                ("m_nopost", () => On(false), () => On(true)),
            };
            GroundShots();
            return;
        }
        var chained = false;
        if (args.Contains("--contentshots")) { ContentShots(); chained = true; }
        if (args.Contains("--gradesweep")) { GradeSweep(); chained = true; }
        if (args.Contains("--looksweep")) { LookSweep(); chained = true; }
        if (args.Contains("--noiseshots")) { NoiseShots(); chained = true; }
        if (args.Contains("--ghostshot")) { GhostShot(); chained = true; }
        if (args.Contains("--folkshots")) { FolkShots(); chained = true; }
        if (args.Contains("--physshots")) { PhysShots(); chained = true; _physWatch = true; }
        if (args.Contains("--bioshots")) { BioShots(); chained = true; }
        if (args.Contains("--citywalk")) { _walking = true; Walk(); chained = true; }
        if (args.Contains("--camsweep")) { Sweep(); chained = true; }
        if (chained) { _pi = _price.Length; return; }
        // `--priceonly`: straight to the pricing pass in the market
        if (OS.GetCmdlineUserArgs().Contains("--priceonly")) { _steps.Add(new("settle", 4f, () => Tp(0f, -8f), _ => Stop(), null)); return; }
        CameraRig.SelfCheck();
        Build();
    }

    // ------------------------------------------------------------------ helpers
    private Vector3 At => _p.GetGlobalTransformInterpolated().Origin;
    private void Stop() => _p.Drive(Vector3.Zero, false, false, false, false);

    private static void Tp(float x, float y)
    {
        var w = CityPlan.ToWorld(new Vector2(x, y));
        CitySite.TeleportTo?.Invoke(w.X, w.Y);
    }

    /// <summary>Onto road `rd`'s point k, at the road's own level (Tp lands on
    /// the ground, which under an embankment is below the road).</summary>
    private static void TpRoad(CityPlan.Road rd, int k)
    {
        var w = CityPlan.ToWorld(rd.P[k]);
        CitySite.TeleportToY?.Invoke(w.X, CityPlan.BaseLevel() + rd.L[k] + 0.6f, w.Y);
    }

    private Vector2 Screen()
    {
        var size = GetViewport().GetVisibleRect().Size;
        var sp = _cam.Camera.UnprojectPosition(At + Vector3.Up * 0.9f);
        return new Vector2((sp.X - size.X / 2f) / size.X, (sp.Y - size.Y / 2f) / size.Y);
    }

    private void Shoot(string name)
    {
        GetViewport().GetTexture().GetImage().SavePng($"res://shot_{name}.png");
        _shots.Add(name);
    }

    private static void Check(string name, bool ok, string detail) =>
        GD.Print($"check: {name,-22} {(ok ? "PASS" : "FAIL")}  {detail}");

    private static float Ang(Vector3 a, Vector3 b) => Mathf.RadToDeg(a.SignedAngleTo(b, Vector3.Up));

    // ------------------------------------------------------------------ physics
    /// <summary>`--physshots` (implementation_plan A8): every Phase A mechanic once, in one
    /// launch -- a swing at a yard crate, a dive among pots, sand prints, mud and its sink,
    /// wet prints off a puddle, a run into a loaded pine, a slide on ice -- each a `check:`
    /// line with its numbers and a `shot_phys_*` frame. Run with `--wet=0.9` so the road
    /// puddles hold water.</summary>
    private void PhysShots()
    {
        var fwd = new Vector3(-0.7071f, 0f, -0.7071f);   // the locked view, along the ground
        static Vector3 V(float a, float b) => new Vector3(-0.7071f, 0f, -0.7071f) * a + Right * b;
        static void To(float x, float z) => CitySite.TeleportTo?.Invoke(x, z);
        int broken = 0, stamps = 0, wets = 0, brushed = 0;
        bool s1 = false, s2 = false, s3 = false;
        // Presses are timed from a step's FIRST tick, not from t = 0: the Shoot() that ends
        // the step before stalls a frame ~150 ms, so a "t < 0.05" press never happened
        // (the first run's swing).
        float t0 = -1f;
        float Rel(float t) { if (t0 < 0f) t0 = t; return t - t0; }
        Vector3 released = default;
        float slide = 0f;
        Vector3? pine = null;

        // 1. one swing at the yard crate (Village.YardThings (13.6, -6.8))
        _steps.Add(new("ph_yard", 3f, () => { var p = V(13.6f, -5.3f); To(p.X, p.Z); }, _ => Stop(),
            () => { Shoot("phys_yard"); broken = Breakables.Broken; }));
        _steps.Add(new("ph_swing", 1.2f, () => t0 = -1f, t =>
        {
            var r = Rel(t);
            var toCrate = (V(13.6f, -6.8f) - V(13.6f, -5.3f)).Normalized();
            _p.Drive(r < 0.05f ? toCrate : Vector3.Zero, false, false, r < 0.05f, false);
            if (!s1 && r >= 0.22f) { s1 = true; Shoot("phys_swing"); }
        }, () => Check("swing breaks", Breakables.Broken > broken, $"{Breakables.Broken - broken} broken by one swing; coins {Breakables.Coins}")));

        // 2. a dive among the pots at (40.6, -6.9), (41.3, -7.7), (40.0, -7.9)
        _steps.Add(new("ph_pots", 2.5f, () => { var p = V(40.6f, -5.6f); To(p.X, p.Z); }, _ => Stop(),
            () => { Shoot("phys_pots"); broken = Breakables.Broken; }));
        _steps.Add(new("ph_dive", 1.8f, () => t0 = -1f, t =>
        {
            var r = Rel(t);
            _p.Drive(Vector3.Zero, r < 0.3f, false, r >= 0.22f && r < 0.26f, r >= 0.2f);
            if (!s2 && Impact.ShockAge > 0.12f && Impact.ShockAge < 0.6f) { s2 = true; Shoot("phys_dive"); }
        }, () => Check("dive smashes", Breakables.Broken - broken >= 2, $"{Breakables.Broken - broken} broken by one dive (3 pots within 2.4 m); shock age {Impact.ShockAge:F2}")));

        // 3. sand: walk toward the camera 2 m off the market's packed trail
        _steps.Add(new("ph_sand", 2.5f, () =>
        {
            var p = SnowSite.PathAt(21, 22, 30f) + new Vector2(Right.X, Right.Z) * 2.0f;
            To(p.X, p.Y);
        }, _ => Stop(), () => stamps = Prints.Stamps));
        _steps.Add(new("ph_sandwalk", 2.4f, null, t => _p.Drive(t < 2.0f ? -fwd : Vector3.Zero, false, false, false, false),
            () => { Shoot("phys_sand"); Check("sand prints", Prints.Stamps - stamps >= 6, $"{Prints.Stamps - stamps} prints pressed in 2 s"); }));

        // 4. mud: the softest mud near the Fen's middle; stand (sink), then walk
        _steps.Add(new("ph_mud", 3f, () =>
        {
            Vector2? mud = null;
            var best = 0f;
            for (var x = -170f; x <= -10f; x += 3f)
            for (var z = 200f; z <= 400f; z += 3f)
            {
                var g = Surface.At(new Vector3(x, WorldGen.Height(x, z), z));
                if (g.K == Surface.Kind.Mud && g.Soft > best) { best = g.Soft; mud = new Vector2(x, z); }
            }
            GD.Print($"physshots: mud at {mud} soft {best:F2}");
            if (mud is { } m) To(m.X, m.Y);
        }, _ => Stop(), () =>
        {
            var g = Surface.At(At);
            Check("mud sinks", _p.Sink > 0.05f, $"settled {_p.Sink:F3} m after 3 s standing on {g.K} soft {g.Soft:F2} speed x{g.Speed:F2}");
            stamps = Prints.Stamps;
        }));
        _steps.Add(new("ph_mudwalk", 2.3f, null, t => _p.Drive(t < 1.8f ? -fwd : Vector3.Zero, false, false, false, false),
            () => { Shoot("phys_mud"); Check("mud prints", Prints.Stamps - stamps >= 4, $"{Prints.Stamps - stamps} prints pressed in 1.8 s"); }));

        // 5. wet prints: out of a road puddle (Village.PuddleSpots (18.5, -0.4)) toward the camera
        _steps.Add(new("ph_puddle", 2.5f, () => { var p = V(18.5f, -0.4f); To(p.X, p.Z); }, _ => Stop(), () => wets = Prints.WetStamps));
        _steps.Add(new("ph_wetwalk", 2.2f, null, t => _p.Drive(t < 1.6f ? -fwd : Vector3.Zero, false, false, false, false),
            () => { Shoot("phys_wet"); Check("wet prints", Prints.WetStamps - wets >= 3, $"{Prints.WetStamps - wets} wet prints after the puddle (Weather.Wet {Weather.Wet:F2})"); }));

        // 6. snow: run into the nearest pine still carrying snow
        _steps.Add(new("ph_snow", 3f, () =>
        {
            var v = SnowSite.PathAt(12, 14, 6f);
            To(v.X, v.Y);
            pine = Snow.Live?.NearestLoaded(new Vector3(v.X, 0f, v.Y));
            if (pine is { } q) To(q.X + 4f, q.Z + 4f);   // 5.7 m off it, on the camera's side
            brushed = Snow.Brushed;
        }, _ => Stop(), null));
        _steps.Add(new("ph_snowrun", 2.2f, null, t =>
        {
            if (pine is not { } q) return;
            var d = new Vector3(q.X - At.X, 0f, q.Z - At.Z);
            _p.Drive(t < 1.4f && d.Length() > 0.3f ? d.Normalized() : Vector3.Zero, false, t < 1.4f, false, false);
            if (!s3 && t >= 1.0f) { s3 = true; Shoot("phys_snowrun"); }
        }, () => Check("pine sheds", Snow.Brushed > brushed, $"{Snow.Brushed - brushed} shed running into the pine at {pine}")));

        // 7. ice: walk 1 s onto the first frozen pool, let go, measure the slide
        _steps.Add(new("ph_ice", 2.5f, () => To(WorldGen.IcePools[0].X - 4.5f, WorldGen.IcePools[0].Y), _ => Stop(), null));
        _steps.Add(new("ph_slide", 3f, null, t =>
        {
            if (t < 1.0f) { _p.Drive(Vector3.Right, false, false, false, false); released = At; }
            else { Stop(); slide = new Vector2(At.X - released.X, At.Z - released.Z).Length(); }
        }, () => Check("ice slides", slide > 1.2f, $"{slide:F2} m slid after letting go ({Surface.At(At).K} underfoot; firm ground stops in ~0.1 m)")));
        _steps.Add(new("ph_end", 0.5f, null, _ => Stop(), () =>
        {
            GD.Print($"physshots: breakables {Breakables.Count}, broken {Breakables.Broken}, coins {Breakables.Coins}, prints {Prints.Stamps}, wet {Prints.WetStamps}, pines brushed {Snow.Brushed}");
            var walked = 0f;
            foreach (var f in Fauna.All) walked += f.Stats().Walked;
            Check("animals stay legal", _physViol == 0, $"{_physViol} of {_physFrames} frames had an animal inside a blocker or off its medium (faunacheck's rule); animals walked {walked:F0} m");
        }));
    }

    /// <summary>`--bioshots` (implementation_plan B6): every biome's streamed scatter and the
    /// four new scenes, each settled 5 s, then 3 s timed (GPU and frame, mean and p99) and a
    /// `shot_bio_*` frame. Run once as built and once with `--noscatter` for the price.</summary>
    private void BioShots()
    {
        var stops = new List<(string Name, System.Func<Vector2?> At)>
        {
            ("greenwood", () => new Vector2(150f, 60f)),
            ("meadows", () => new Vector2(-300f, -60f)),
            ("emberwood", () => new Vector2(260f, -150f)),
            ("fen", () => new Vector2(-40f, 330f)),
            ("crags", () => new Vector2(-200f, 300f)),
            ("dunes", () => new Vector2(200f, 380f)),
            ("snow", () => new Vector2(-330f, 440f)),
        };
        foreach (var b in new[] { Biome.Emberwood, Biome.Fen, Biome.Meadow, Biome.Crags })
        {
            var k = b;
            stops.Add(("site_" + k.ToString().ToLower(), () => RegionSites.Scenes.TryGetValue(k, out var s) ? s.At + new Vector2(0.7071f, 0.7071f) * 6f : null));
        }
        foreach (var (name, at) in stops)
        {
            var gpu = new List<double>();
            var wall = new List<double>();
            ulong last = 0;
            _steps.Add(new("bio_" + name, 8f, () =>
            {
                if (at() is { } p) CitySite.TeleportTo?.Invoke(p.X, p.Y);
                gpu.Clear(); wall.Clear(); last = 0;
            }, t =>
            {
                Stop();
                var now = Time.GetTicksUsec();
                if (t > 5f && last > 0)
                {
                    gpu.Add(RenderingServer.ViewportGetMeasuredRenderTimeGpu(GetViewport().GetViewportRid()));
                    wall.Add((now - last) / 1000.0);
                }
                last = now;
            }, () =>
            {
                Shoot("bio_" + name);
                double P(List<double> l, double q) { var s = l.OrderBy(v => v).ToList(); return s.Count == 0 ? 0 : s[Mathf.Clamp((int)(q * s.Count), 0, s.Count - 1)]; }
                GD.Print($"bio: {name,-16} gpu mean {(gpu.Count > 0 ? gpu.Average() : 0):F2} p99 {P(gpu, 0.99):F2} | frame mean {(wall.Count > 0 ? wall.Average() : 0):F2} p99 {P(wall, 0.99):F2} ms"
                         + $" | scatter cells {Scatter.CellsBuilt} plants {Scatter.Plants} kit {Scatter.Pieces} | at {At.X:F0},{At.Z:F0} ground {Surface.At(At).K}");
            }));
        }
    }

    /// <summary>`--physshots` also keeps `--faunacheck`'s count, every frame, in the same
    /// launch (the fliers now circle home; the test cap is 1-2 launches).</summary>
    private bool _physWatch;
    private int _physViol, _physFrames;

    // ------------------------------------------------------------------ steps
    private void Build()
    {
        var ring = CityPlan.Roads.FindIndex(r => r.Name == "Ring road");
        var east = CityPlan.DirToWorld(Vector2.Right);
        var east3 = new Vector3(east.X, 0f, east.Y);
        Vector3 wish0 = Vector3.Zero;
        var drift = 0f;
        var roads = new List<int>();
        var rollMax = 0f;

        _steps.Add(new("settle", 2.5f, null, _ => Stop(), null));

        // Lead: run screen-right at the spawn.
        _steps.Add(new("lead", 1.8f, null, _ => _p.Drive(Right, false, true, false, false),
            () => { var x = Screen().X; Check("lead", x <= -0.08f, $"player {-x:P1} of width behind centre (>= 8 %)"); }));

        // Latch: on Church street at the base yaw, hold D (east, along the
        // street). The camera turns 90 deg under the held key; the wish must not.
        _steps.Add(new("latch", 3.0f, () => { Tp(36f, 12.8f); wish0 = Vector3.Zero; drift = 0f; },
            _ =>
            {
                _p.DriveKeys(new Vector2(1f, 0f));
                var w = _p.WishDir;
                if (wish0 == Vector3.Zero) wish0 = w;
                else drift = Mathf.Max(drift, Mathf.Abs(Ang(wish0, w)));
            },
            () => Check("latch", drift < 5f, $"wish drifted {drift:F1} deg while the camera turned to {Mathf.RadToDeg(_cam.YawRad):F1} (< 5)")));

        // Re-press: after a release the key takes the camera's yaw again.
        _steps.Add(new("relatch", 1.0f, null,
            t =>
            {
                // the latch takes the camera's yaw AT the press; compare against
                // that, not the still-easing camera at the end of the step
                if (t >= 0.3f && !_v.ContainsKey("press_yaw")) _v["press_yaw"] = _cam.YawRad;
                _p.DriveKeys(t < 0.3f ? Vector2.Zero : new Vector2(1f, 0f));
            },
            () =>
            {
                var y = _v["press_yaw"];
                var camRight = new Vector3(Mathf.Cos(y), 0f, -Mathf.Sin(y));
                var d = Mathf.Abs(Ang(camRight, _p.WishDir));
                Check("relatch", d < 2f, $"new press is {d:F1} deg off the camera's right (< 2)");
            }));

        // Centreline: the same street spot on its centreline and 1.8 m off it.
        _steps.Add(new("centre_on", 2.5f, () => Tp(50f, 13.6f), _ => Stop(), () => _v["x0"] = Screen().X));
        _steps.Add(new("centre_off", 2.5f, () => Tp(50f, 15.4f), _ => Stop(),
            () =>
            {
                var dx = Mathf.Abs(Screen().X - _v["x0"]);
                Check("centreline", dx > 0.04f, $"player moved {dx:P1} of width off centre for 1.8 m off the line (0.85 x 1.8 m = {0.85f * 1.8f / 24.6f:P1} expected)");
            }));

        // Junctions: walk the ring road east through Well lane and the South road.
        _steps.Add(new("junction", 9f, () => { Tp(-68f, -21.2f); roads.Clear(); },
            _ =>
            {
                var (d, _) = CityPlan.StreetAxis(At.X, At.Z, ring);
                var d3 = new Vector3(d.X, 0f, d.Y);
                _p.Drive(d3.Dot(east3) >= 0f ? d3 : -d3, false, false, false, false);
                if (roads.Count == 0 || roads[^1] != _cam.Road) roads.Add(_cam.Road);
            },
            () =>
            {
                var after = roads.SkipWhile(r => r != ring).ToList();   // entries before the first ring commit are the step's start
                var others = after.Count(r => r >= 0 && r != ring);
                Check("junction", others == 0, $"committed roads in order: {string.Join(" > ", roads)} (ring = {ring}; plan x now {CityPlan.ToPlan(At.X, At.Z).X:F0})");
            }));

        // Peek: a right-drag of 150 px, then hands off.
        _steps.Add(new("peek_settle", 2.5f, () => Tp(-12f, 0f), _ => Stop(), null));
        _steps.Add(new("peek", 3.6f, () =>
            {
                _v["pk0"] = Screen().X;
                Input.ParseInputEvent(new InputEventMouseMotion { Relative = new Vector2(150f, 0f), ButtonMask = MouseButtonMask.Right });
            },
            t => { Stop(); if (t > 0.6f && !_v.ContainsKey("pk1")) _v["pk1"] = Screen().X; },
            () =>
            {
                var out1 = _v["pk1"] - _v["pk0"];
                var back = Screen().X - _v["pk0"];
                // the drag is in window pixels and reaches the viewport scaled
                // by its stretch: 150 px x 0.02 m x (1280 / window width)
                var scale = GetViewport().GetVisibleRect().Size.X / DisplayServer.WindowGetSize().X;
                var want = 150f * 0.02f * scale / 24.6f * 0.8f;
                Check("peek", out1 < -want && Mathf.Abs(back) < Mathf.Abs(out1) * 0.35f,
                      $"drag moved the player {out1:+0.0%;-0.0%} (>= {want:P1} after scale {scale:F2}), 3.6 s later {back:+0.0%;-0.0%} (within 35 %)");
            }));

        // Landmark pull: 12 m screen-left of the fountain, with and without it.
        _steps.Add(new("pull_on", 2.5f, () => Tp(-12f, 0f), _ => Stop(), () => _v["pull"] = Screen().X));
        _steps.Add(new("pull_off", 2.0f, () =>
            {
                _saved.AddRange(CameraRig.Interests);
                CameraRig.Interests.Clear();
            }, _ => Stop(),
            () =>
            {
                var d = _v["pull"] - Screen().X;
                CameraRig.Interests.AddRange(_saved);
                Check("landmark pull", d < -0.03f, $"the fountain moved the player {d:+0.0%;-0.0%} of width (toward screen-left = frame leaning right, at <= 3 m)");
            }));

        // Shake: trauma 0.8.
        _steps.Add(new("shake", 1.0f, () => { rollMax = 0f; _cam.AddTrauma(0.8f); },
            _ => { Stop(); rollMax = Mathf.Max(rollMax, Mathf.Abs(Mathf.RadToDeg(_cam.Camera.Rotation.Z))); },
            () => Check("shake", rollMax is > 0.2f and < 1.3f, $"roll peaked {rollMax:F2} deg (0.2-1.3)")));

        // Rain on a turned street: the box must turn with the camera.
        _steps.Add(new("rain_street", 2.6f, () => { Tp(50f, 13.6f); Weather.Mode = "rain"; Weather.Rain = 1f; }, _ => Stop(),
            () =>
            {
                var rain = GetTree().CurrentScene.GetNodeOrNull<Node3D>("Weather/Rain");
                var dy = rain == null ? 999f : Mathf.Abs(Mathf.Wrap(rain.RotationDegrees.Y - CameraRig.LiveYaw, -180f, 180f));
                Check("rain turns", dy < 0.5f, $"rain box yaw {rain?.RotationDegrees.Y:F1} vs camera {CameraRig.LiveYaw:F1}");
                Shoot("cam_rain_street");
                Weather.Mode = "clear";
                Weather.Rain = 0f;
            }));

        // Reveal (camera plan Phase 5): open on the keep, ease back to the
        // player in 2.8 s; mid-way it is away from the player, at the end the
        // rig is back on its aim and input is released.
        _steps.Add(new("reveal", 3.4f, () =>
            {
                Tp(0f, -8f);
                var k = CityPlan.ToWorld(new Vector2(118f, 108f));
                var from = new Vector3(k.X, CityPlan.BaseLevel() + CityPlan.CitadelLv + 14f, k.Y);
                var d = from - At;
                _cam.Reveal(d.Length() > 70f ? At + d.Normalized() * 70f : from, 2.8f);
                _v["rv_mid"] = -1f;
            },
            t =>
            {
                Stop();
                if (t > 1.3f && _v["rv_mid"] < 0f) { _v["rv_mid"] = _cam.GlobalPosition.DistanceTo(At); Shoot("cam_reveal_mid"); }
            },
            () =>
            {
                var end = _cam.GlobalPosition.DistanceTo(At);
                Check("reveal", _v["rv_mid"] > 15f && end < 5f && !CameraRig.Revealing,
                      $"mid-way the aim was {_v["rv_mid"]:F1} m from the player (> 15), at the end {end:F1} m (< 5: aim height + framing), input released {!CameraRig.Revealing}");
            }));

        // Zoom x2 in the market.
        _steps.Add(new("zoom2", 1.4f, () => Tp(0f, -8f), t => { Stop(); if (t > 0.6f) _cam.Zoom = 2; },
            () => { Shoot("cam_zoom2"); _cam.Zoom = 1; }));

        // Cloud shadows: the market at cover 0 and 1, then at 0.35 three
        // times 4 s apart, each against the same moment with the clouds held
        // off -- the pair's darker share is what the clouds did.
        _steps.Add(new("cloud_0", 1.2f, () => { Clouds.Force = 0f; Clouds.Shafts = false; }, _ => Stop(), () => Shoot("cam_cloud_0")));
        _steps.Add(new("cloud_100", 1.2f, () => Clouds.Force = 1f, _ => Stop(), () => Shoot("cam_cloud_100")));
        foreach (var m in new[] { "a", "b", "c" })
        {
            var tag = m;
            _steps.Add(new("cloud_35" + tag, 4f, () => Clouds.Force = 0.35f, _ => Stop(), () => Shoot("cam_cloud_35" + tag)));
            _steps.Add(new("cloud_35" + tag + "_off", 0.25f, () => Clouds.Force = 0f, _ => Stop(), () => Shoot("cam_cloud_35" + tag + "_off")));
        }
        _steps.Add(new("cloud_end", 0.2f, () => { Clouds.Force = null; Clouds.Shafts = true; }, _ => Stop(), null));

        // God light: the default side sun and the sun swung in front of the
        // lens; clouds off, clouds with shafts, clouds without shafts.
        foreach (var (yaw, tag) in new[] { (-45f, "side"), (-135f, "back") })
        {
            _steps.Add(new($"sun_{tag}_clear", 1.6f, () => { Grade.CityL.Yaw = yaw; Clouds.Force = 0f; }, _ => Stop(), () => Shoot($"cam_sun_{tag}_clear")));
            _steps.Add(new($"sun_{tag}_shafts", 5.0f, () => { Clouds.Force = 0.45f; Clouds.Shafts = true; }, _ => Stop(), () => Shoot($"cam_sun_{tag}_shafts")));
            _steps.Add(new($"sun_{tag}_noshafts", 1.2f, () => Clouds.Shafts = false, _ => Stop(),
                () => { Shoot($"cam_sun_{tag}_noshafts"); Clouds.Shafts = true; }));
        }
        _steps.Add(new("sun_reset", 0.5f, () => { Grade.CityL.Yaw = -45f; Clouds.Force = null; }, _ => Stop(), null));

        // The tour: the de-cluttered city at the town pitch, and every region
        // under its own light (lamps, figure, clouds where the sun is real).
        foreach (var (name, x, y) in new[] { ("market", 0f, -8f), ("oldcity", 55f, 14f), ("westres", -77f, 21f), ("riverside", -101f, -69f), ("lower", 42f, -96f) })
            _steps.Add(new("tour_" + name, 3.2f, () => Tp(x, y), _ => Stop(), () => Shoot("tour_city_" + name)));
        if (CityPlan.Squares.Count > 0)
        {
            var sq = CityPlan.Squares[0];
            _steps.Add(new("tour_square", 3.2f, () => Tp(sq.X, sq.Y - 6f), _ => Stop(), () => Shoot("tour_city_square")));
        }
        foreach (var (name, at) in new[] { ("village", Vector2.Zero), ("snow", SnowSite.Vista), ("desert", SnowSite.PathAt(21, 22, 20f)) })
            _steps.Add(new("tour_" + name, 4f, () => CitySite.TeleportTo?.Invoke(at.X, at.Y), _ => Stop(), () => Shoot("tour_" + name)));
        // overnight content: a forge's smoke, and the windmill's sails turning
        // (two captures 1 s apart must differ round the hub)
        var forge = CitySite.Buildings.FirstOrDefault(b => b.Kind == "blacksmith");
        if (forge.Kind != null)
            _steps.Add(new("smoke_forge", 4f, () => { var at = forge.P + forge.Front * (forge.D / 2f + 9f); Tp(at.X, at.Y); }, _ => Stop(), () => Shoot("cam_smoke_forge")));
        WindmillShots("cam_windmill");
        // carried-over checks (asset-rebuild plan 5d, 6j): a blizzard on the
        // lamp walk, and blowing sand on the dunes, each held 5 s then captured
        _steps.Add(new("snow_blizzard", 5f, () =>
            {
                CitySite.TeleportTo?.Invoke(SnowSite.Vista.X, SnowSite.Vista.Y);
                Snow.Level = Snow.Storm.Blizzard; Snow.LevelHeld = true; Weather.Mode = "snow"; Weather.Rain = 1f;
            }, _ => Stop(), () => { Shoot("tour_snow_blizzard"); Weather.Mode = "clear"; Weather.Rain = 0f; Snow.LevelHeld = false; }));
        _steps.Add(new("desert_sand", 5f, () => { var d = SnowSite.PathAt(21, 22, 20f); CitySite.TeleportTo?.Invoke(d.X, d.Y); }, _ => Stop(),
            () => Shoot("tour_desert_sand")));
        // back to the market: the pricing and the bench time it standing there
        _steps.Add(new("back_market", 3f, () => Tp(0f, -8f), _ => Stop(), null));
    }

    /// <summary>Stand so plan point `target` is `ahead` metres in front along
    /// the base view (the camera looks along -(sin 45, cos 45) in world XZ).</summary>
    private static void TpFacing(Vector2 target, float ahead)
    {
        var t = CityPlan.ToWorld(target);
        var y = Mathf.DegToRad(CameraRig.BaseYaw);
        var at = t + new Vector2(Mathf.Sin(y), Mathf.Cos(y)) * ahead;
        var p = CityPlan.ToPlan(at.X, at.Y);
        Tp(p.X, p.Y);
    }

    /// <summary>The windmill's sails turning: two frames 1.2 s apart (they
    /// turn at 0.55 rad/s, ~38 deg between them), from a lens 30 m out along
    /// the mill's front (its sails face it) and 16 m over its foot -- west of
    /// the mill that is just outside the wall, which stays behind the lens.
    /// Not the rig: the rig looks plan +y, and the sails face -x, so from the
    /// rig they are edge-on everywhere. The player waits at the lens's feet,
    /// out of shot.</summary>
    private void WindmillShots(string name)
    {
        var mill = CityPlan.Landmarks.First(l => l.Kind == "windmill");
        var foot = CityPlan.BaseLevel() + CityPlan.Level(mill.Q);
        var eye = mill.At + mill.Front * 30f;
        Vector2 at = CityPlan.ToWorld(mill.At), from = CityPlan.ToWorld(eye);
        Camera3D? lens = null;
        _steps.Add(new(name + "_a", 3f, () =>
        {
            Tp(eye.X, eye.Y);
            lens = new Camera3D { Fov = CameraRig.Fov, Far = 1400f };
            AddChild(lens);
            lens.LookAtFromPosition(new Vector3(from.X, foot + 16f, from.Y), new Vector3(at.X, foot + 9f, at.Y), Vector3.Up);
            lens.MakeCurrent();
        }, _ => Stop(), () => Shoot(name + "_a")));
        _steps.Add(new(name + "_b", 1.2f, null, _ => Stop(), () =>
        {
            Shoot(name + "_b");
            _cam.Camera.MakeCurrent();
            lens?.QueueFree();
        }));
    }

    private void ContentShots()
    {
        _steps.Add(new("settle", 3f, () => Tp(0f, -8f), _ => Stop(), null));
        var smiths = CitySite.Buildings.Where(b => b.Kind == "blacksmith").Take(2).ToList();
        for (var k = 0; k < smiths.Count; k++)
        {
            var b = smiths[k];
            var n = k;
            _steps.Add(new($"smoke_{n}", 5f, () => TpFacing(b.P, 30f), _ => Stop(), () => Shoot($"content_smoke_{n}")));
        }
        // smoke diagnosis: the first emitter's live state, then its first
        // emission point framed 25 m ahead
        _steps.Add(new("smoke_diag", 5f, () =>
            {
                var sm = GetTree().CurrentScene.FindChildren("Smoke*", "", true, false).OfType<GpuParticles3D>().FirstOrDefault();
                if (sm == null) { GD.Print("smoke: no emitter"); return; }
                var pm = (ParticleProcessMaterial)sm.ProcessMaterial;
                var img = pm.EmissionPointTexture.GetImage();
                var c = img.GetPixel(0, 0);
                var wp = sm.GlobalPosition + new Vector3(c.R, c.G, c.B);
                GD.Print($"smoke: node {sm.GlobalPosition} emitting {sm.Emitting} amount {sm.Amount} visible {sm.IsVisibleInTree()} points {pm.EmissionPointCount} fmt {img.GetFormat()} first point {wp} range {sm.VisibilityRangeEnd}");
                var pl = CityPlan.ToPlan(wp.X, wp.Z);
                TpFacing(pl, 25f);
            }, _ => Stop(), () => Shoot("content_smoke_diag")));
        // the spray's and the smoke's process material and draw pass, each on
        // one emission point in front of the player (spray left, smoke right),
        // made once the teleport has settled: separates "not rendering" from
        // "off screen"
        var made = false;
        _steps.Add(new("smoke_near", 5f, () => { Tp(0f, -8f); made = false; },
            t =>
            {
                Stop();
                if (made || t < 0.8f) return;
                made = true;
                var y = Mathf.DegToRad(CameraRig.BaseYaw);
                var fwd = -new Vector3(Mathf.Sin(y), 0f, Mathf.Cos(y));
                var right = new Vector3(Mathf.Cos(y), 0f, -Mathf.Sin(y));
                foreach (var (pat, side) in new[] { ("Spray*", -2.5f), ("Smoke*", 2.5f) })
                {
                    var src = GetTree().CurrentScene.FindChildren(pat, "", true, false).OfType<GpuParticles3D>().FirstOrDefault();
                    if (src == null) { GD.Print($"near: no {pat}"); continue; }
                    var pm = (ParticleProcessMaterial)src.ProcessMaterial.Duplicate();
                    pm.EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box;
                    pm.EmissionBoxExtents = new Vector3(0.2f, 0.2f, 0.2f);
                    var near = new GpuParticles3D
                    {
                        Name = "Near" + pat.TrimEnd('*'), Amount = 20, Lifetime = src.Lifetime, Preprocess = src.Lifetime,
                        ProcessMaterial = pm, DrawPass1 = src.DrawPass1,
                        VisibilityAabb = new Aabb(new Vector3(-20f, -5f, -20f), new Vector3(40f, 30f, 40f)),
                    };
                    GetTree().CurrentScene.AddChild(near);
                    near.GlobalPosition = At + fwd * 4f + right * side + Vector3.Up * 1.5f;
                    GD.Print($"near: {pat} at {near.GlobalPosition}, player {At}");
                }
            }, () => Shoot("content_smoke_near")));
        foreach (var vi in new[] { 1, 4, 5, 7 })
        {
            var (vn, vp) = CityPlan.Views[vi];
            _steps.Add(new("view_" + vi, 4f, () => Tp(vp.X, vp.Y), _ => Stop(), () => Shoot("content_view_" + vn.Replace(' ', '_'))));
        }
        WindmillShots("content_windmill");
        // a rowboat at its quay: the player on the quay's block top 2.4 m
        // inland of it (inside the parapet), so the boat lies between the lens
        // (out over the water) and the player. At the quay's level, not Tp:
        // the ground there is the block's buried step (see the walk's grid)
        if (CitySite.Boats.Count > 0)
        {
            var (boat, inland, level) = CitySite.Boats[0];
            var w = CityPlan.ToWorld(boat + inland * 2.4f);
            _steps.Add(new("rowboat", 3f, () => CitySite.TeleportToY?.Invoke(w.X, CityPlan.BaseLevel() + level + 0.65f, w.Y), _ => Stop(),
                () => Shoot("content_rowboat")));
        }
        foreach (var (name, at, dir, _, _, _) in CityPlan.Falls.Take(3))
        {
            var nm = name.Replace(' ', '_').Replace("-", "").ToLowerInvariant();
            var spot = at + dir * 12f;
            _steps.Add(new("falls_" + nm, 3f, () => TpFacing(at, 18f), _ => Stop(), () => Shoot("content_falls_" + nm)));
        }
        _steps.Add(new("stream", 3f, () => TpFacing(CityPlan.Reaches[0].Line[2], 12f), _ => Stop(), () => Shoot("content_stream")));
        _steps.Add(new("sand", 7f, () => { var d = SnowSite.PathAt(21, 22, 30f); CitySite.TeleportTo?.Invoke(d.X, d.Y); }, _ => Stop(), () => Shoot("content_sand")));
    }

    private bool _talked, _petted;

    /// <summary>`--folkshots`: the townsfolk and the animals (user, 2026-09-26:
    /// "npcs fill the world dogs cats"): the market crowd, a street, someone
    /// answering E, a dog petted, the farm, the village (the LOW bake).</summary>
    private void GroundShots()
    {
        void Shot(string name, float hold, System.Action go) =>
            _steps.Add(new("ground_" + name, hold, go, _ => Stop(), () =>
            {
                Shoot("ground_" + name);
                GD.Print($"grass: {name}: {Grass.Live?.Stats() ?? "off"}");
            }));
        static void W(float x, float z) => CitySite.TeleportTo?.Invoke(x, z);
        Shot("village", 5f, () => W(-12f, -12f));          // the spawn frame, on the road
        Shot("meadow", 3f, () => W(-7.07f, -16.97f));      // 7 m right of the road, past the fence
        Shot("wood", 3f, () => W(42.4f, 42.4f));           // the Wildwood, path space a -60
        Shot("pond", 3f, () => W(-31.8f, 88.4f));          // the pond's near bank, looking over it
        Shot("street", 3f, () => Tp(55f, 12f));
        Shot("market", 3f, () => Tp(0f, -12f));
        Shot("farm", 3f, () => Tp(192f, -116f));
        Shot("westres", 3f, () => Tp(-77f, 21f));
        Shot("noble", 3f, () => Tp(-2f, 60f));
    }

    private void FolkShots()
    {
        _steps.Add(new("folk_settle", 3f, () => { Tp(0f, -8f); _folkWatch = true; }, _ => Stop(), null));
        _steps.Add(new("folk_market", 2f, () => Tp(0f, -12f), _ => Stop(), () => { Shoot("folk_market"); AirLog("market"); }));
        _steps.Add(new("folk_street", 3f, () => Tp(55f, 12f), _ => Stop(), () => Shoot("folk_street")));
        _steps.Add(new("folk_talk", 2.6f, () =>
            {
                var town = Townsfolk.All.FirstOrDefault(t => t.Name == "CityFolk");
                var who = town?.Positions.Where(p => CityPlan.ToPlan(p.X, p.Z).Length() is > 6f and < 22f)
                    .OrderBy(p => CityPlan.ToPlan(p.X, p.Z).Y).FirstOrDefault() ?? Vector3.Zero;
                var pl = CityPlan.ToPlan(who.X, who.Z);
                Tp(pl.X, pl.Y - 1.3f);
                _talked = false;
            }, t =>
            {
                Stop();
                if (t > 1.2f && !_talked)
                {
                    _talked = true;
                    Interact.Best(new Vector2(At.X, At.Z))?.Act();
                    var town = Townsfolk.All.First(x => x.Name == "CityFolk");
                    _talker = town.Positions.OrderBy(v => Horiz(v - At)).First();
                }
            }, () => Shoot("folk_talk")));
        _steps.Add(new("folk_bump", 2.5f, null, t =>
            {
                // walk straight at the nearest person, found live each frame (a point
                // recorded once went stale when that person walked on, 2026-09-27):
                // people are solid, so the player stops at 0.65 m or slides round
                var town = Townsfolk.All.First(x => x.Name == "CityFolk");
                var who = town.Positions.OrderBy(v => Horiz(v - At)).First();
                var d = who - At;
                d.Y = 0f;
                _p.Drive(d.Length() > 0.05f ? d.Normalized() * 0.5f : Vector3.Zero, false, false, false, false);
                _bumpMin = Mathf.Min(_bumpMin, d.Length());
            }, () => Check("player vs person", _bumpMin > 0.6f, $"closest {_bumpMin:F2} m to the nearest person (bodies touch at 0.65)")));
        _steps.Add(new("folk_pet", 4.4f, () =>
            {
                // a dog with nobody within 4 m: a person nearer than the dog wins the
                // E key (the closest offer), and stood between them blocks the dog
                var town = Townsfolk.All.First(x => x.Name == "CityFolk");
                var dog = Pets.Where("dog").FirstOrDefault(d => town.Nearest(new Vector2(d.X, d.Z)) > 4f);
                if (dog == default) dog = Pets.Where("dog").First();
                var pl = CityPlan.ToPlan(dog.X, dog.Z) + new Vector2(0f, -2.5f);
                var w = CityPlan.ToWorld(pl);
                CitySite.TeleportToY?.Invoke(w.X, dog.Y + 0.6f, w.Y);
                _petted = false;
                _logCat = 0f;
            }, t =>
            {
                Stop();
                if (t > 3.6f && !_petted)
                {
                    // the dog's own offer: the E key gives the closest thing, and a
                    // person who wanders nearer than the dog rightly wins it
                    _petted = true;
                    _dogIx = NearestIx("dog");
                    var me = new Vector2(At.X, At.Z);
                    GD.Print($"petdog: E would offer '{Interact.Best(me)?.Hint ?? "none"}'");
                    var o = Pets.OfferFor(me);
                    _hint = o?.Hint ?? "none";
                    _hearts0 = Townsfolk.Hearts;
                    o?.Act();
                }
                if (t >= _logCat)
                {
                    _logCat = t + 0.5f;
                    var ix = NearestIx("dog");
                    GD.Print($"petdog: t {t:F1} gap {Horiz(Pets.Where("dog").ElementAt(ix) - At):F2} {Pets.Doing("dog").ElementAt(ix)}");
                }
            }, () =>
            {
                Shoot("folk_pet");
                Check("pet the dog", _hint.StartsWith("E: pet the dog") && Townsfolk.Hearts > _hearts0, $"hint '{_hint}', hearts {Townsfolk.Hearts - _hearts0}");
            }));
        // the petted dog follows for 25 s: walk a street at 3 m/s for 20 s
        _steps.Add(new("folk_follow", 20f, () => { Route(); _dogMax = 0f; _walked = 0f; _lastAt = At; },
            t =>
            {
                Follow(0.5f);
                if (t > 4f) _dogMax = Mathf.Max(_dogMax, DogGap());
            }, () =>
            {
                Shoot("folk_follow");
                Check("dog follows", _dogMax < 8f && _walked > 25f, $"walked {_walked:F0} m, dog at most {_dogMax:F1} m off, now {DogGap():F1}");
            }));
        // ...and not after: 25.8 s after the pet its follow timer has run out.
        // Read directly: a tame dog comes to anyone within 7 m anyway, so
        // distance tests measured the street, not the follow (a walk-off that
        // turned back at a road's end, then a 20 m jump that landed 5 m away,
        // both failed with a dog that had stopped following, 2026-09-27).
        _steps.Add(new("folk_unfollow", 5f, () => _followWas = Pets.Following("dog", _dogIx), _ => Stop(),
            () => Check("dog stops following", _followWas && !Pets.Following("dog", _dogIx),
                        $"following at 20.8 s {_followWas}, at 25.8 s {Pets.Following("dog", _dogIx)}")));
        // a cat: walked up to, it stays and can be petted; sprinted at, it bolts
        _steps.Add(new("folk_cat_pet", 6f, () =>
            {
                _catIx = 0;
                OnRoadNear(Cat(), 6f);
                _petted = false;
            }, t =>
            {
                var d = Cat() - At;
                d.Y = 0f;
                _p.Drive(d.Length() > 1.3f && t < 4.8f ? d.Normalized() * 0.5f : Vector3.Zero, false, false, false, false);
                if (t > 5.2f && !_petted) { _petted = true; PetNow(); }
            }, () =>
            {
                Shoot("folk_cat_pet");
                Check("pet a cat (walked up)", _hint.StartsWith("E: pet the cat") && Townsfolk.Hearts > _hearts0, $"hint '{_hint}', cat {Horiz(Cat() - At):F1} m off");
            }));
        _steps.Add(new("folk_cat_bolt", 5f, () =>
            {
                OnRoadNear(Cat(), 9f);
                _cat0 = Cat();
                _catMoved = 0f;
                _logCat = 0f;
            }, t =>
            {
                var d = Cat() - At;
                d.Y = 0f;
                if (t < 0.5f) Stop();
                else _p.Drive(d.Length() > 0.5f ? d.Normalized() : Vector3.Zero, false, true, false, false);
                _catMoved = Mathf.Max(_catMoved, Horiz(Cat() - _cat0));
                if (t >= _logCat)
                {
                    _logCat += 0.25f;
                    GD.Print($"catbolt: t {t:F2} gap {d.Length():F2} cat moved {Horiz(Cat() - _cat0):F2} {Pets.Doing("cat").ElementAt(_catIx)} player {At.X:F1},{At.Z:F1}");
                }
            }, () =>
            {
                Shoot("folk_cat_bolt");
                Check("cat bolts from a sprint", _catMoved > 3f, $"cat got {_catMoved:F1} m from its start in 5 s (walks 0.6 m/s, runs 6)");
            }));
        _steps.Add(new("folk_farm", 3f, () => Tp(192f, -116f), _ => Stop(), () => Shoot("folk_farm")));
        _steps.Add(new("folk_village", 4f, () => CitySite.TeleportTo?.Invoke(-12f, -12f), _ => Stop(), () =>
            {
                Shoot("folk_village");
                AirLog("village");
                _folkWatch = false;
                var farm = Fauna.All.First(f => f.Name == "FarmAnimals");
                Check("animals in fences", _fenceBad == 0, $"{_fenceBad} animal-frames inside a blocker over {_watchFrames} frames; farm blockers {farm.Stats().Blockers}");
                Check("city pets on streets", _petBad == 0, $"{_petBad} pet-frames off the streets or inside a blocker");
                Check("people apart", _overlapMax <= 2, $"most city pairs closer than 0.45 m in one frame: {_overlapMax}");
                Check("player never in a person", _gapMin > 0.55f, $"closest person {_gapMin:F2} m (after each teleport settles)");
            }));
    }

    /// <summary>The air's emitters where the player stands (motes in the city,
    /// fireflies in the twilight).</summary>
    private void AirLog(string where)
    {
        float R(string n) => GetTree().CurrentScene.FindChild(n, true, false) is GpuParticles3D g && g.Emitting ? g.AmountRatio : -1f;
        GD.Print($"air: {where} motes {R("Motes"):F2} fireflies {R("Fireflies"):F2}");
    }

    // ---- folk harness helpers
    private bool _folkWatch, _followWas;
    private int _fenceBad, _petBad, _watchFrames, _overlapMax, _dogIx, _catIx, _hearts0, _wi;
    private float _gapMin = float.MaxValue, _bumpMin = float.MaxValue, _dogMax, _walked, _catMoved, _logCat;
    private string _hint = "";
    private Vector3 _talker, _cat0, _lastAt;
    private List<Vector2> _way = new();

    private static Fauna Pets => Fauna.All.First(f => f.Name == "CityPets");
    private Vector3 Dog() => Pets.Where("dog").ElementAt(_dogIx);
    private Vector3 Cat() => Pets.Where("cat").ElementAt(_catIx);
    private static float Horiz(Vector3 v) => new Vector2(v.X, v.Z).Length();
    private float DogGap() => Horiz(Dog() - At);

    private int NearestIx(string sprite)
    {
        var l = Pets.Where(sprite).ToList();
        return l.IndexOf(l.OrderBy(v => Horiz(v - At)).First());
    }

    private void PetNow()
    {
        var o = Interact.Best(new Vector2(At.X, At.Z));
        _hint = o?.Hint ?? "none";
        _hearts0 = Townsfolk.Hearts;
        o?.Act();
    }

    private static (CityPlan.Road Rd, int K) NearestRoad(Vector2 plan)
    {
        CityPlan.Road? best = null;
        int bk = 0;
        var bd = float.MaxValue;
        foreach (var rd in CityPlan.Roads)
        {
            if (rd.Kind == "track") continue;
            for (var k = 0; k < rd.P.Length; k++)
            {
                var d = (rd.P[k] - plan).LengthSquared();
                if (d < bd) { bd = d; best = rd; bk = k; }
            }
        }
        return (best!, bk);
    }

    /// <summary>Onto the road nearest `at`, about `dist` along it, so a
    /// straight walk back to `at` is down the street, not into a house.</summary>
    private static void OnRoadNear(Vector3 at, float dist)
    {
        var (rd, k) = NearestRoad(CityPlan.ToPlan(at.X, at.Z));
        var dir = k + 1 < rd.P.Length ? 1 : -1;
        var i = k;
        var acc = 0f;
        while (acc < dist && i + dir >= 0 && i + dir < rd.P.Length)
        {
            acc += (rd.P[i + dir] - rd.P[i]).Length();
            i += dir;
        }
        TpRoad(rd, i);
    }

    /// <summary>The street under the player, the longer way from here.</summary>
    private void Route()
    {
        var (rd, k) = NearestRoad(CityPlan.ToPlan(At.X, At.Z));
        var fwd = rd.P.Skip(k + 1).ToList();
        var back = rd.P.Take(k).Reverse().ToList();
        _way = (fwd.Count >= back.Count ? fwd : back).Select(CityPlan.ToWorld).ToList();
        _wi = 0;
    }

    /// <summary>Walk the route at `speed` x walking pace, back again at its end.</summary>
    private void Follow(float speed)
    {
        _walked += Horiz(At - _lastAt);
        _lastAt = At;
        if (_way.Count == 0) { Stop(); return; }
        var d = _way[_wi] - new Vector2(At.X, At.Z);
        if (d.Length() < 1.5f && ++_wi >= _way.Count) { _way.Reverse(); _wi = 0; }
        d = _way[_wi] - new Vector2(At.X, At.Z);
        _p.Drive(new Vector3(d.X, 0f, d.Y).Normalized() * speed, false, false, false, false);
    }

    /// <summary>Every frame of the folk steps: animals inside a blocker (a
    /// fence crossed), people on top of each other, the player inside one.</summary>
    private void FolkWatch()
    {
        _watchFrames++;
        foreach (var f in Fauna.All)
            if (f.Name == "FarmAnimals" || f.Name == "VillagePets") _fenceBad += f.Violations();
            else if (f.Name == "CityPets") _petBad += f.Violations();
        if (Townsfolk.All.FirstOrDefault(t => t.Name == "CityFolk") is { } town)
            _overlapMax = Mathf.Max(_overlapMax, town.Overlaps(0.45f, new Vector2(At.X, At.Z)));
        if (_t > 0.6f)
            foreach (var t in Townsfolk.All) _gapMin = Mathf.Min(_gapMin, t.Nearest(new Vector2(At.X, At.Z)));
    }

    /// <summary>`--gradesweep` (2026-09-27, the calm-and-palette pass):
    /// candidate city grades at three city spots in one launch, clouds held
    /// off so every candidate sees the same light. Scored by
    /// `scripts/forge/compare_refs.py "game/shot_grade_c1_*.png"` against the
    /// four reference videos. c0 is the shipped grade.</summary>
    private void GradeSweep()
    {
        static Grade.Lighting Cand(Color amb, Color fog, float sat, Color sky, Color ground)
        {
            var l = Grade.CityLight();
            l.Ambient = amb;
            l.Fog = fog;
            l.Saturation = sat;
            l.SkyHorizon = sky;
            l.GroundHorizon = ground;
            return l;
        }
        Color a1 = new(0.36f, 0.42f, 0.58f), f1 = new(0.74f, 0.76f, 0.80f), s1 = new(0.82f, 0.76f, 0.66f), g1 = new(0.46f, 0.44f, 0.40f);
        var cands = new System.Func<Grade.Lighting>[]
        {
            Grade.CityLight,
            () => Cand(a1, f1, 0.74f, s1, g1),
            () => Cand(a1, f1, 0.66f, s1, g1),
            () => Cand(new(0.30f, 0.37f, 0.62f), f1, 0.70f, s1, g1),
            () => Cand(a1, new(0.64f, 0.70f, 0.82f), 0.70f, new(0.74f, 0.74f, 0.76f), new(0.44f, 0.44f, 0.44f)),
        };
        // spot-major: one teleport per spot, then the candidates in place
        foreach (var (spot, x, y) in new[] { ("market", 0f, -12f), ("street", 55f, 12f), ("craft", 108f, -4f) })
            for (var i = 0; i < cands.Length; i++)
            {
                var (ci, sx, sy, first) = (i, x, y, i == 0);
                _steps.Add(new($"grade_c{ci}_{spot}", first ? 3f : 1.2f, () =>
                {
                    Clouds.Force = 0f;
                    Grade.CityL = cands[ci]();   // a new object, so Weather re-colours the sky too
                    if (first) Tp(sx, sy);
                }, _ => Stop(), () => Shoot($"grade_c{ci}_{spot}")));
            }
        _steps.Add(new("grade_reset", 0.5f, () => { Grade.CityL = Grade.CityLight(); Clouds.Force = null; }, _ => Stop(), null));
    }

    /// <summary>`--looksweep` (2026-09-27, "do warm colours first then fix
    /// ground noise"): one lever at a time against the shipped city frame at
    /// three spots, clouds held off. The sun's temperature for the warm share,
    /// then the ground-noise suspects: the soft-shadow filter, the shadow
    /// atlas, volumetric fog and the grade's contrast. Scored per variant by
    /// `compare_refs.py "game/shot_look_<variant>_*.png"`.</summary>
    private void LookSweep()
    {
        // third pass (2026-09-29, "it is all grey ... dead"): warm candidates over the
        // retoned honey stone. The earlier passes (sun, filter, atlas, fog, contrast;
        // then combinations) are in findings 2026-09-27. Contrast stays 1.00.
        // pass 1 (all warm: peach ambient, fog and mist) turned the frame one sepia
        // and warmed the shade to b* +3..+16; pass 2 keeps the shade cool-lavender
        // (warm light over neutral shade, as pp_with) and thins the haze so the
        // town's colour reaches the distance
        // pass 3: AgX won pass 2 (closest to pp_with on every column); the milky
        // distance is the Post mist, so its density is the lever now
        static Grade.Lighting Warm(float k, float sat, float haze, float mist = 0.22f)
        {
            var l = Grade.CityLight();
            l.Sun = Grade.Kelvin(k);
            l.Saturation = sat;
            l.Ambient = new Color(0.38f, 0.42f, 0.64f);        // cool lavender shade
            l.Fill = new Color(0.52f, 0.56f, 0.84f);
            l.MistDensity = mist;
            l.Fog = new Color(0.84f, 0.78f, 0.74f);            // light warm haze
            l.FogDen *= haze;
            l.VFog *= haze;
            l.Mist = new Color(0.96f, 0.92f, 0.90f);           // cream, not peach
            l.SkyTop = new Color(0.28f, 0.44f, 0.76f);         // a clear blue over a warm town
            l.SkyHorizon = new Color(0.92f, 0.84f, 0.74f);
            l.GroundHorizon = new Color(0.60f, 0.52f, 0.46f);
            return l;
        }
        var env = GetViewport().FindWorld3D().Environment;
        var tone0 = env.TonemapMode;
        (string, System.Action, System.Action) V(string name, float k, float sat, float haze, Godot.Environment.ToneMapper tone, float mist = 0.22f) =>
            (name, () => { Grade.CityL = Warm(k, sat, haze, mist); env.TonemapMode = tone; },
                   () => { Grade.CityL = Grade.CityLight(); env.TonemapMode = tone0; });
        const Godot.Environment.ToneMapper Film = Godot.Environment.ToneMapper.Filmic, Agx = Godot.Environment.ToneMapper.Agx;
        // pass 4 (2026-09-30, the user's city direction sheet: "this dense and this orangish
        // and dark"): a sunset over the city -- a low orange sun, a purple-to-orange sky, every
        // window and lamp lit, deep near-neutral blacks (Post), less shade fill. The sheet
        // measures mean 0.321, dark 17.7 %, sat 0.423, lit sat 0.401, warm 75 %, shade b* +3.5.
        // Pass 3's variants are in findings 2026-09-29.
        static Grade.Lighting Dusk(float k, float elev, float exp, float sat, float warmShade)
        {
            var l = Grade.CityLight();
            l.Sun = Grade.Kelvin(k);
            l.Elev = elev;
            l.SunEnergy = 3.2f;
            l.Ambient = new Color(0.38f, 0.42f, 0.64f).Lerp(new Color(0.56f, 0.42f, 0.36f), warmShade);
            l.Fill = new Color(0.52f, 0.56f, 0.84f).Lerp(new Color(0.70f, 0.54f, 0.48f), warmShade);
            l.AmbientEnergy = 0.30f;
            l.FillEnergy = 0.22f;
            l.Exposure = exp;
            l.Saturation = sat;
            l.Black = new Color(0.022f, 0.016f, 0.024f);
            l.WindowsLit = 1f;
            l.Lamps = 4.5f;
            l.Bloom = 0.8f;
            l.Fog = new Color(0.88f, 0.58f, 0.44f);
            l.FogDen *= 2f;
            l.SkyTop = new Color(0.20f, 0.15f, 0.36f);
            l.SkyHorizon = new Color(0.98f, 0.58f, 0.30f);
            l.GroundHorizon = new Color(0.46f, 0.30f, 0.26f);
            l.GroundBottom = new Color(0.08f, 0.06f, 0.07f);
            l.CloudLit = new Color(1.0f, 0.64f, 0.40f);
            l.CloudDark = new Color(0.32f, 0.22f, 0.32f);
            return l;
        }
        (string, System.Action, System.Action) D(string name, float k, float elev, float exp, float sat, float warm, Godot.Environment.ToneMapper tone) =>
            (name, () => { Grade.CityL = Dusk(k, elev, exp, sat, warm); env.TonemapMode = tone; },
                   () => { Grade.CityL = Grade.CityLight(); env.TonemapMode = tone0; });
        const Godot.Environment.ToneMapper Aces = Godot.Environment.ToneMapper.Aces;
        // pass 5 (2026-09-30, "city life" plan, item 3): light in pools. The per-view gate
        // measured market 0.422 / old city 0.435 mean luma (sheet 0.243-0.395) and the old
        // city 7.6 % dark, the gates 43-52 %; the shade b* +7.3 against the sheet's +3.5.
        // Pass 4's variants (d1-d5) are in findings 2026-09-30.
        static Grade.Lighting Pool(float bloom, float lift, float lamps, float cool)
        {
            var l = Grade.CityLight();
            l.Bloom = bloom;
            l.AmbientEnergy *= lift;
            l.FillEnergy *= lift;
            l.Lamps = lamps;
            l.Ambient = l.Ambient.Lerp(new Color(0.38f, 0.42f, 0.64f), cool);
            l.Fill = l.Fill.Lerp(new Color(0.52f, 0.56f, 0.84f), cool);
            return l;
        }
        (string, System.Action, System.Action) P(string name, float bloom, float lift, float lamps, float cool) =>
            (name, () => Grade.CityL = Pool(bloom, lift, lamps, cool), () => Grade.CityL = Grade.CityLight());
        var variants = new (string Name, System.Action On, System.Action Off)[]
        {
            ("base", () => { }, () => { }),
            P("p1", 0.5f, 1f, 4.5f, 0f),
            P("p2", 0.5f, 0.8f, 4.5f, 0f),
            P("p3", 0.5f, 0.8f, 3.5f, 0f),
            P("p4", 0.5f, 0.8f, 4.5f, 0.4f),
        };
        foreach (var (spot, x, y) in new[] { ("market", 0f, -8f), ("oldcity", 55f, 14f), ("lower", 42f, -96f), ("wgate", -180f, 9.5f), ("harbour", 30.1f, -130.4f) })
            for (var i = 0; i < variants.Length; i++)
            {
                var (v, sx, sy, first) = (variants[i], x, y, i == 0);
                _steps.Add(new($"look_{v.Name}_{spot}", first ? 3f : 1.2f, () =>
                {
                    Clouds.Force = 0f;
                    if (first) Tp(sx, sy);
                    v.On();
                }, _ => Stop(), () => { Shoot($"look_{v.Name}_{spot}"); v.Off(); }));
            }
        _steps.Add(new("look_reset", 0.5f, () => Clouds.Force = null, _ => Stop(), null));
    }

    /// <summary>`--noiseshots` (2026-09-30, user: "the whole city is hazy ... the graphics are
    /// fucked up"): per-pixel noise on every lit surface, none in the sky. One suspect off at a
    /// time at two spots: SSAO, volumetric fog, the sun's soft shadows (PCSS), the cloud shadow
    /// casters; then all off. Frames `game/shot_noise_<variant>_<spot>.png`.</summary>
    private void NoiseShots()
    {
        var env = GetViewport().FindWorld3D().Environment;
        static Grade.Lighting Hard() { var l = Grade.CityLight(); l.Soft = 0f; return l; }
        var variants = new (string Name, System.Action On, System.Action Off)[]
        {
            ("base", () => { }, () => { }),
            ("noclouds", () => Clouds.Force = 0f, () => Clouds.Force = null),
            ("nossao", () => env.SsaoEnabled = false, () => env.SsaoEnabled = true),
            ("novfog", () => env.VolumetricFogEnabled = false, () => env.VolumetricFogEnabled = true),
            ("hard", () => Grade.CityL = Hard(), () => Grade.CityL = Grade.CityLight()),
            ("alloff", () => { Clouds.Force = 0f; env.SsaoEnabled = false; env.VolumetricFogEnabled = false; Grade.CityL = Hard(); },
                       () => { Clouds.Force = null; env.SsaoEnabled = true; env.VolumetricFogEnabled = true; Grade.CityL = Grade.CityLight(); }),
            // the city forces Soft Very Low (CitySite.Region): the filter's own quality levels
            Q("qlow", RenderingServer.ShadowQuality.SoftLow), Q("qmed", RenderingServer.ShadowQuality.SoftMedium),
            Q("qhigh", RenderingServer.ShadowQuality.SoftHigh),
            ("soft025", () => { var l = Grade.CityLight(); l.Soft = 0.25f; Grade.CityL = l; }, () => Grade.CityL = Grade.CityLight()),
        };
        static (string, System.Action, System.Action) Q(string n, RenderingServer.ShadowQuality q) =>
            (n, () => RenderingServer.DirectionalSoftShadowFilterSetQuality(q),
                () => RenderingServer.DirectionalSoftShadowFilterSetQuality(RenderingServer.ShadowQuality.SoftVeryLow));
        foreach (var (spot, x, y) in new[] { ("oldcity", 55f, 14f), ("market", 0f, -8f) })
            for (var i = 0; i < variants.Length; i++)
            {
                var (v, sx, sy, first) = (variants[i], x, y, i == 0);
                _steps.Add(new($"noise_{v.Name}_{spot}", first ? 3f : 1.5f, () =>
                {
                    if (first) Tp(sx, sy);
                    v.On();
                }, _ => Stop(), () => { Shoot($"noise_{v.Name}_{spot}"); v.Off(); }));
            }
    }

    /// <summary>`--ghostshot` (2026-09-30): the player just north (plan +Y) of three Old City
    /// houses, the camera south of them, so each house stands between: the occluder must be
    /// drawn see-through and whole (CitySite.Ghosts). Checks a ghost is shown; frames
    /// `game/shot_ghost_<n>.png`.</summary>
    private void GhostShot()
    {
        // houses facing south (the camera's side, plan -Y), the player in the yard behind them,
        // clear of any street (on a street the camera turns to look along it)
        static Vector2 Behind(CityPlan.Bldg b) => b.P + new Vector2(0f, Mathf.Max(b.W, b.D) / 2f + 2.5f);
        var houses = CitySite.Buildings.Where(b => b.Front.Y < -0.8f && CityPlan.RoadClear(Behind(b)) > 3f && CityPlan.StreetAt(CityPlan.ToWorld(Behind(b)).X, CityPlan.ToWorld(Behind(b)).Y) < 0)
            .OrderBy(b => (b.P - new Vector2(55f, 14f)).Length()).Take(3).ToArray();
        for (var k = 0; k < houses.Length; k++)
        {
            var b = houses[k];
            var at = Behind(b);
            var n = k;
            _steps.Add(new($"ghost_{n}", 3f, () => Tp(at.X, at.Y), _ => Stop(), () =>
            {
                Shoot($"ghost_{n}");
                Check($"ghost {n} ({b.Kind})", CitySite.GhostsShown > 0, $"{CitySite.GhostsShown} ghost(s) shown");
            }));
        }
    }

    private readonly List<CameraRig.Interest> _saved = new();

    /// <summary>`--camtest --camsweep`: the market at pitch 5-30 deg (5 deg
    /// steps) x standoff 20-40 m (5 m steps), clouds held off so every frame
    /// has the same light. Frames to renders/camera_sweep/, composed into one
    /// sheet by scripts/forge/camera_sweep_sheet.py.</summary>
    private void Sweep()
    {
        const string dir = "D:/assests/renders/camera_sweep";
        DirAccess.MakeDirRecursiveAbsolute(dir);
        _steps.Add(new("sweep_settle", 3f, () => { Tp(0f, -8f); Clouds.Force = 0f; Clouds.Shafts = false; }, _ => Stop(), null));
        foreach (var pitch in new[] { 5, 10, 15, 20, 25, 30 })
        foreach (var dist in new[] { 20, 25, 30, 35, 40 })
        {
            var p = pitch;
            var d = dist;
            _steps.Add(new($"p{p}_d{d}", 0.7f, () => { _cam.PitchOverride = p; _cam.StandoffOverride = d; }, _ => Stop(),
                () => GetViewport().GetTexture().GetImage().SavePng($"{dir}/p{p:00}_d{d}.png")));
        }
        _steps.Add(new("sweep_end", 0.2f, () => { _cam.PitchOverride = null; _cam.StandoffOverride = null; }, _ => Stop(), null));
    }

    // ------------------------------------------------------------------ city walk
    // `--camtest --citywalk` (user, 2026-09-24: "walk in every part and fix
    // the city"): every street walked end to end at walking pace, then a
    // stand on a 20 m grid over the whole city. Logged as `walk:` lines --
    // stuck (< 0.6 m in 1.5 s: a collider across the way), off level (the
    // feet > 0.8 m off the road's own level: a hole, a step, a buried road),
    // fell (below the ground), pushed (a grid point inside a collider) --
    // and captured every 35 m of street and at every grid point into
    // renders/citywalk/. Frame and GPU time are bucketed by quarter.
    private bool _skip;
    private bool _walking;
    private readonly Dictionary<string, List<(double Gpu, double Frame)>> _byQ = new();
    private ulong _walkTick;
    private int _quiet;
    private int _issues;

    private void Issue(string what, Vector3 at, string detail)
    {
        var p = CityPlan.ToPlan(at.X, at.Z);
        GD.Print($"walk: ISSUE {what,-9} plan ({p.X:F0},{p.Y:F0}) {CityPlan.QuarterAt(p)}  {detail}");
        _issues++;
    }

    private void Walk()
    {
        const string dir = "D:/assests/renders/citywalk";
        DirAccess.MakeDirRecursiveAbsolute(dir);
        foreach (var f in DirAccess.GetFilesAt(dir)) DirAccess.RemoveAbsolute($"{dir}/{f}");
        var lc = CityPlan.BaseLevel();
        _steps.Add(new("walk_settle", 3f, () => Tp(0f, -8f), _ => Stop(), null));
        // `--walkroads=1,2,3`: only those roads (and no stairs, falls or grid;
        // `--walkstairs` / `--walkgrid` add those back)
        var only = OS.GetCmdlineUserArgs().FirstOrDefault(a => a.StartsWith("--walkroads="))?[12..]
            .Split(',').Select(int.Parse).ToHashSet();
        var stairs = only == null || OS.GetCmdlineUserArgs().Contains("--walkstairs");
        var gridOn = only == null || OS.GetCmdlineUserArgs().Contains("--walkgrid");
        for (var ri = 0; ri < CityPlan.Roads.Count; ri++)
        {
            if (only != null && !only.Contains(ri)) continue;
            var r = ri;
            var rd = CityPlan.Roads[ri];
            var len = 0f;
            for (var i = 1; i < rd.P.Length; i++) len += (rd.P[i] - rd.P[i - 1]).Length();
            int wp = 0, shot = 0;
            float travel = 0f, nextShot = 0f, stuckT = 0f, offT = 0f;
            Vector3 last = default, stuckAt = default;
            _steps.Add(new($"walk_{r:00}", len / 6f * 1.8f + 8f,
                () =>
                {
                    wp = 1; travel = 0f; nextShot = 0f; shot = 0; stuckT = 0f; offT = 0f;
                    TpRoad(rd, 0);
                    GD.Print($"walk: road {r:00} {rd.Name} ({rd.Kind}, {len:F0} m)");
                },
                t =>
                {
                    var here = At;
                    if (t < 0.8f) { Stop(); last = stuckAt = here; return; }   // settle after the teleport
                    var plan = CityPlan.ToPlan(here.X, here.Z);
                    while (wp < rd.P.Length - 1 && (rd.P[wp] - plan).Length() < 1.8f) wp++;
                    if (wp >= rd.P.Length - 1 && (rd.P[^1] - plan).Length() < 1.8f) { Stop(); _skip = true; return; }
                    var tgt = CityPlan.ToWorld(rd.P[wp]);
                    var d = new Vector3(tgt.X - here.X, 0f, tgt.Y - here.Z);
                    _p.Drive(d.Normalized(), false, false, false, false);
                    travel += new Vector2(here.X - last.X, here.Z - last.Z).Length();
                    last = here;
                    // the road's own surface at the nearest point
                    var k = Mathf.Clamp(wp - 1, 0, rd.P.Length - 1);
                    if ((rd.P[wp] - plan).Length() < (rd.P[k] - plan).Length()) k = wp;
                    var want = lc + rd.L[k] + (rd.Wet[k] ? 0f : 0.06f);
                    var dy = here.Y - want;
                    if (!rd.Wet[k] && Mathf.Abs(dy) > 0.8f)
                    {
                        if ((offT += 1f / 120f) > 0.4f) { Issue("off-level", here, $"road {r} {rd.Name}: feet {dy:+0.0;-0.0} m from the road's level"); offT = -3f; }
                    }
                    else if (offT > 0f) offT = 0f;
                    if (here.Y < WorldGen.Height(here.X, here.Z) - 1.2f) { Issue("fell", here, $"road {r} {rd.Name}: {WorldGen.Height(here.X, here.Z) - here.Y:F1} m under the ground"); TpRoad(rd, Mathf.Min(wp + 3, rd.P.Length - 1)); }
                    if ((stuckT += (float)GetProcessDeltaTime()) > 1.5f)
                    {
                        if (new Vector2(here.X - stuckAt.X, here.Z - stuckAt.Z).Length() < 0.6f)
                        {
                            Issue("stuck", here, $"road {r} {rd.Name} at point {wp}/{rd.P.Length}");
                            var j = Mathf.Min(wp + 3, rd.P.Length - 1);
                            wp = j;
                            TpRoad(rd, j);
                        }
                        stuckT = 0f;
                        stuckAt = here;
                    }
                    if (travel >= nextShot)
                    {
                        nextShot += 35f;
                        GetViewport().GetTexture().GetImage().SavePng($"{dir}/r{r:00}_{shot++:00}.png");
                        _quiet = 4;
                    }
                },
                () =>
                {
                    GD.Print($"walk: road {r:00} done: {travel:F0} of {len:F0} m, reached point {wp}/{rd.P.Length}, player hidden {100f * _occHit / Mathf.Max(_occN, 1):F1} % of frames");
                    _occAll += _occHit; _occAllN += _occN; _occHit = _occN = 0;
                }));
        }

        // the kerbs (2026-09-29): straight across one piece of ~60 kerb runs and
        // back. The player has no step-up, so a kerb is a ridge to ride over.
        // Stopping short of the kerb's outer edge is the kerb; stopping past it is
        // something on the verge (a house front), counted but not an issue.
        var probes = only == null || OS.GetCmdlineUserArgs().Contains("--walkkerbs")
            ? CitySite.KerbProbes : new List<(Vector2 Edge, Vector2 N, float Level)>();
        int kN = 0, kOut = 0, kBack = 0, kVerge = 0;
        for (var pi = 0; pi < probes.Count; pi += Mathf.Max(1, probes.Count / 60))
        {
            var (edge, n, level) = probes[pi];
            var e3 = CityPlan.ToWorld(edge);
            var o3 = CityPlan.ToWorld(edge + n);
            var wn = new Vector3(o3.X - e3.X, 0f, o3.Y - e3.Y).Normalized();
            float maxOut = -9f, minIn = 9f;
            var back = false;
            _steps.Add(new($"kerb_{pi}", 4.2f,
                () =>
                {
                    maxOut = -9f; minIn = 9f; back = false;
                    var s0 = CityPlan.ToWorld(edge - n * 1.2f);
                    CitySite.TeleportToY?.Invoke(s0.X, CityPlan.BaseLevel() + level + 0.6f, s0.Y);
                },
                t =>
                {
                    if (t < 0.8f) { Stop(); return; }
                    var here = At;
                    var off = (CityPlan.ToPlan(here.X, here.Z) - edge).Dot(n);
                    if (!back)
                    {
                        maxOut = Mathf.Max(maxOut, off);
                        if (off > 1.2f || t > 2.5f) back = true;
                        _p.Drive(wn, false, false, false, false);
                    }
                    else
                    {
                        minIn = Mathf.Min(minIn, off);
                        if (off < -1f) Stop(); else _p.Drive(-wn, false, false, false, false);
                    }
                },
                () =>
                {
                    kN++;
                    var at = new Vector3(e3.X, 0f, e3.Y);
                    if (maxOut < 0.05f) Issue("kerb", at, $"stopped going out {maxOut:+0.00;-0.00} m from the kerb's outer edge");
                    else if (maxOut < 0.6f) kVerge++;
                    else if (minIn <= -0.6f) { kOut++; kBack++; }
                    else { kOut++; Issue("kerb", at, $"stopped coming back {minIn:+0.00;-0.00} m from the kerb's outer edge"); }
                }));
        }
        if (probes.Count > 0)
            _steps.Add(new("kerb_sum", 0.1f, () => { }, _ => Stop(),
                () => GD.Print($"walk: kerbs {kN} of {probes.Count} runs tried: over and back {kBack}, out only {kOut - kBack}, verge-blocked {kVerge}")));

        // the wall stairs: from the foot up the flight and onto the wall walk
        for (var si = 0; si < (stairs ? CityPlan.WallStairs.Count : 0); si++)
        {
            var (foot, head, inn, low, high) = CityPlan.WallStairs[si];
            var k = si;
            var top = 0f;
            _steps.Add(new($"wallstair_{k}", 9f,
                () =>
                {
                    var w = CityPlan.ToWorld(foot - (head - foot).Normalized() * 3f);
                    CitySite.TeleportToY?.Invoke(w.X, lc + low + 0.6f, w.Y);
                    top = -999f;
                },
                t =>
                {
                    if (t < 0.8f) { Stop(); return; }
                    var plan = CityPlan.ToPlan(At.X, At.Z);
                    // up the flight, then a step out onto the walk
                    var goal = (plan - head).Length() > 1.2f && t < 6.5f ? head : head - inn * 2.6f;
                    var g = CityPlan.ToWorld(goal);
                    _p.Drive(new Vector3(g.X - At.X, 0f, g.Y - At.Z).Normalized(), false, false, false, false);
                    top = Mathf.Max(top, At.Y - lc);
                    if (t > 4f && t < 4.1f) { GetViewport().GetTexture().GetImage().SavePng($"{dir}/s{k}_climb.png"); _quiet = 4; }
                },
                () =>
                {
                    GetViewport().GetTexture().GetImage().SavePng($"{dir}/s{k}_top.png");
                    if (top < high - 0.6f) Issue("stairs", At, $"wall stair {k}: reached {top:F1} of the walk's {high:F1}");
                    else GD.Print($"walk: wall stair {k} climbed to {top:F1} (walk {high:F1})");
                }));
        }

        // the falls, from 14 m downstream
        foreach (var (name, at, fdir, ftop, ffoot, _) in CityPlan.Falls)
        {
            if (only != null) break;
            var nm = name.Replace(' ', '_').Replace("-", "").ToLowerInvariant();
            var spot = at + fdir * 16f;
            _steps.Add(new("falls_" + nm, 2.2f, () => Tp(spot.X, spot.Y), _ => Stop(),
                () => { GetViewport().GetTexture().GetImage().SavePng($"{dir}/f_{nm}.png"); _quiet = 4; }));
        }

        // the grid: every 20 m inside the wall and over the fields, not in
        // the water, not inside a building, not inside a retaining block (6 m
        // of solid masonry across every level change: a point within
        // EdgeHalf of one spawns inside it and is shoved out of its face --
        // both "pushed" of the 2026-09-25 walk, WestRes 3.2 m, Noble 1.8 m)
        var grid = new List<Vector2>();
        for (var y = -150f; y <= 135f; y += 20f)
        for (var x = -200f; x <= 240f; x += 20f)
        {
            var p = new Vector2(x, y);
            var q = CityPlan.QuarterAt(p);
            if (!gridOn || q == CityPlan.Quarter.Outside || CityPlan.IsWater(p)) continue;
            if (CitySite.Buildings.Any(b => Mathf.Abs((p - b.P).Dot(new Vector2(b.Front.Y, -b.Front.X))) < b.W / 2f + 1f
                                          && Mathf.Abs((p - b.P).Dot(b.Front)) < b.D / 2f + 1f)) continue;
            if (CitySite.Edges.Any(e => CityPlan.SegDist(p, e.A, e.B) < CityPlan.EdgeHalf + 0.5f)) continue;
            grid.Add(p);
        }
        foreach (var gp in grid)
        {
            var p = gp;
            _steps.Add(new($"grid_{p.X:F0}_{p.Y:F0}", 1.0f, () => Tp(p.X, p.Y), _ => Stop(),
                () =>
                {
                    var here = At;
                    var w = CityPlan.ToWorld(p);
                    var g = WorldGen.Height(here.X, here.Z);
                    if (here.Y < g - 0.8f) Issue("fell", here, $"grid point: {g - here.Y:F1} m under the ground");
                    var moved = new Vector2(here.X - w.X, here.Z - w.Y).Length();
                    if (moved > 1.5f) Issue("pushed", here, $"grid point: pushed {moved:F1} m (inside a collider?)");
                    if (here.Y > g + 1.5f) Issue("high", here, $"grid point: standing {here.Y - g:F1} m over the ground (on something)");
                    GetViewport().GetTexture().GetImage().SavePng($"{dir}/g_{p.X:+000;-000}_{p.Y:+000;-000}.png");
                    _quiet = 4;
                }));
        }
        _steps.Add(new("walk_end", 0.2f, null, _ => Stop(), () =>
        {
            GD.Print($"walk: {_issues} issues, {grid.Count} grid points, lamps lit {CitySite.Lit}, check-9 offenders {CitySite.Floating.Count}, player hidden {100f * _occAll / Mathf.Max(_occAllN, 1):F1} % of street frames");
            foreach (var f in CitySite.Floating.Take(40)) GD.Print($"walk: feet {f}");
            double P(List<double> l, double q) { var s = l.OrderBy(v => v).ToList(); return s[Mathf.Clamp((int)(q * s.Count), 0, s.Count - 1)]; }
            foreach (var (q, l) in _byQ.OrderBy(kv => kv.Key))
            {
                if (l.Count < 30) continue;
                var g = l.Select(v => v.Gpu).ToList();
                var fr = l.Select(v => v.Frame).ToList();
                GD.Print($"walk: time {q,-10} n {l.Count,5}  gpu mean {g.Average():F2} p99 {P(g, 0.99):F2}  frame mean {fr.Average():F2} p99 {P(fr, 0.99):F2} ms  (over 12.5 ms: {100.0 * fr.Count(v => v > 12.5) / fr.Count:F1} %)");
            }
        }));
    }

    // street occlusion (camera plan Phase 2's gate, re-measured at the town
    // pitch): the share of walking frames where a ray from the lens to the
    // player's chest hits something solid (a building's box, a wall)
    private int _occN, _occHit, _occAll, _occAllN;

    private void Occlusion()
    {
        var space = GetViewport().World3D.DirectSpaceState;
        var q = PhysicsRayQueryParameters3D.Create(_cam.Camera.GlobalPosition, At + Vector3.Up * 1.0f);
        q.Exclude = new Godot.Collections.Array<Rid> { _p.GetRid() };
        _occN++;
        if (space.IntersectRay(q).Count > 0) _occHit++;
    }

    /// <summary>Walk timing: every frame's GPU and wall time into its quarter,
    /// except the few after a capture (SavePng stalls the frame).</summary>
    private void WalkTime()
    {
        if (_i >= 0 && _i < _steps.Count && _steps[_i].Name.StartsWith("walk_") && _t > 0.8f) Occlusion();
        var now = Time.GetTicksUsec();
        var dt = (now - _walkTick) / 1000.0;
        _walkTick = now;
        if (_quiet > 0) { _quiet--; return; }
        if (_i < 1 || dt <= 0.0 || dt > 250.0) return;
        var p = CityPlan.ToPlan(At.X, At.Z);
        var q = CityPlan.QuarterAt(p).ToString();
        if (!_byQ.TryGetValue(q, out var l)) _byQ[q] = l = new();
        l.Add((RenderingServer.ViewportGetMeasuredRenderTimeGpu(GetViewport().GetViewportRid()), dt));
    }

    // ------------------------------------------------------------------ pricing
    // Each config: applied, 90 frames to settle, 300 timed, reverted. The
    // market first (2026-09-24 night: the budget candidates, one at a time,
    // with the new lamps and smoke), then standing in every quarter.
    private (string Name, System.Action On, System.Action Off)[] _price = null!;

    private Godot.Environment Env => GetTree().CurrentScene.GetNode<WorldEnvironment>("Env").Environment;

    private void Prices()
    {
        var list = new List<(string, System.Action, System.Action)>
        {
            ("all", () => { }, () => { }),
            ("noshafts", () => Clouds.Shafts = false, () => Clouds.Shafts = true),
            ("noclouds", () => Clouds.Force = 0f, () => Clouds.Force = null),
            ("novfog", () => Env.VolumetricFogEnabled = false, () => Env.VolumetricFogEnabled = true),
            ("ssao_low", () => RenderingServer.EnvironmentSetSsaoQuality(RenderingServer.EnvironmentSsaoQuality.Low, true, 0.5f, 2, 50f, 300f),
                         () => RenderingServer.EnvironmentSetSsaoQuality(RenderingServer.EnvironmentSsaoQuality.Medium, true, 0.5f, 2, 50f, 300f)),
            ("nossao", () => Env.SsaoEnabled = false, () => Env.SsaoEnabled = true),
            ("nomsaa", () => GetViewport().Msaa3D = Viewport.Msaa.Disabled, () => GetViewport().Msaa3D = Viewport.Msaa.Msaa2X),
            ("noglow", () => Env.GlowEnabled = false, () => Env.GlowEnabled = true),
            ("nolamps", () => LampLight.AutoOff = true, () => LampLight.AutoOff = false),
            ("nosmoke", () => Smoke(false), () => Smoke(true)),
            ("soft0", () => Grade.CityL.Soft = 0f, () => Grade.CityL.Soft = 0.5f),
            ("shadow2k", () => RenderingServer.DirectionalShadowAtlasSetSize(2048, true), () => RenderingServer.DirectionalShadowAtlasSetSize(4096, true)),
            ("ssao+2k", () => { Env.SsaoEnabled = false; RenderingServer.DirectionalShadowAtlasSetSize(2048, true); },
                        () => { Env.SsaoEnabled = true; RenderingServer.DirectionalShadowAtlasSetSize(4096, true); }),
            ("ssao+2k+vfog", () => { Env.SsaoEnabled = false; Env.VolumetricFogEnabled = false; RenderingServer.DirectionalShadowAtlasSetSize(2048, true); },
                             () => { Env.SsaoEnabled = true; Env.VolumetricFogEnabled = true; RenderingServer.DirectionalShadowAtlasSetSize(4096, true); }),
            ("all_again", () => { }, () => { }),
        };
        // `--standsonly`: just the per-view benches, under the shipped cuts
        if (OS.GetCmdlineUserArgs().Contains("--standsonly")) list.Clear();
        foreach (var (name, at) in CityPlan.Views)
        {
            var a = at;
            list.Add(("stand_" + name.Replace(' ', '_'), () => { Tp(a.X, a.Y); CitySite.Reapply(); }, () => { }));
        }
        list.Add(("back_market", () => Tp(0f, -8f), () => { }));
        _price = list.ToArray();
    }

    private void Smoke(bool on)
    {
        foreach (var n in GetTree().CurrentScene.FindChildren("Smoke*", "", true, false))
            if (n is GpuParticles3D g) g.Visible = on;
    }
    private int _pi = -1, _pf;
    private readonly List<double> _gpu = new(), _wall = new();
    private ulong _tick;

    private void Price()
    {
        Stop();
        var now = Time.GetTicksUsec();
        var dt = (now - _tick) / 1000.0;
        _tick = now;
        if (_pi < 0) { _pi = 0; _pf = 0; _price[0].On(); return; }
        if (_pi >= _price.Length) return;
        _pf++;
        if (_pf <= 90) return;
        _gpu.Add(RenderingServer.ViewportGetMeasuredRenderTimeGpu(GetViewport().GetViewportRid()));
        _wall.Add(dt);
        if (_pf < 390) return;
        double P(List<double> l, double q) { var s = l.OrderBy(v => v).ToList(); return s[Mathf.Clamp((int)(q * s.Count), 0, s.Count - 1)]; }
        GD.Print($"price: {_price[_pi].Name,-10} gpu mean {_gpu.Average():F2} p50 {P(_gpu, 0.5):F2} p99 {P(_gpu, 0.99):F2}  |  frame mean {_wall.Average():F2} p99 {P(_wall, 0.99):F2} ms  (over 12.5 ms: {100.0 * _wall.Count(v => v > 12.5) / _wall.Count:F1} %)");
        _gpu.Clear();
        _wall.Clear();
        // the frame each config priced, for judging a cut by eye too
        GetViewport().GetTexture().GetImage().SavePng($"res://shot_price_{_price[_pi].Name}.png");
        _price[_pi].Off();
        _pi++;
        _pf = 0;
        if (_pi < _price.Length) _price[_pi].On();
    }

    public override void _Process(double delta)
    {
        if (_p == null) return;
        var dt = (float)delta;
        if (_i >= _steps.Count)
        {
            if (_pi < _price.Length) { Price(); return; }
            if (!BenchGo) GD.Print("camtest: wrote " + string.Join(", ", _shots));
            BenchGo = true;
            Stop();
            if (!OS.GetCmdlineUserArgs().Any(a => a.StartsWith("--bench="))) GetTree().Quit();
            return;
        }
        if (_walking) WalkTime();
        // a step ends only once 3 frames have been drawn since it began: a
        // window that cannot draw (minimised, a locked screen) keeps running
        // the steps while GetImage() hands back one stale frame (2026-09-25:
        // 29 of 30 sweep frames, and windmill a = b, byte-identical)
        var drawn = Engine.GetFramesDrawn() >= _drawn + 3;
        if (_i >= 0 && !_skip && _t >= _steps[_i].Hold && !drawn && !_held)
        {
            _held = true;
            GD.Print($"camtest: window not drawing, holding {_steps[_i].Name}");
        }
        if (_i < 0 || (_t >= _steps[_i].Hold && drawn) || _skip)
        {
            _skip = false;
            _held = false;
            if (_i >= 0) _steps[_i].Exit?.Invoke();
            _i++;
            _t = 0f;
            _drawn = Engine.GetFramesDrawn();
            if (_i < _steps.Count) _steps[_i].Enter?.Invoke();
            else _tick = Time.GetTicksUsec();
            return;
        }
        _t += dt;
        _steps[_i].Tick?.Invoke(_t);
        if (_folkWatch) FolkWatch();
        if (_physWatch)
        {
            _physFrames++;
            var bad = 0;
            foreach (var f in Fauna.All) bad += f.Violations();
            if (bad > 0) _physViol++;
        }
        _logT += dt;
        if (_logT >= 0.1f)
        {
            _logT = 0f;
            var s = Screen();
            GD.Print($"camlog: {_steps[_i].Name} t {_t:F2} yaw {Mathf.RadToDeg(_cam.YawRad):F1} road {_cam.Road} "
                     + $"x {s.X:+0.000;-0.000} y {s.Y:+0.000;-0.000} "
                     + $"depth {(At + Vector3.Up * 1.2f - _cam.Camera.GlobalPosition).Dot(-_cam.Camera.GlobalBasis.Z):F2}");
        }
    }
}
