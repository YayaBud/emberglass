using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Rain, and what it does to everything else.
///
/// Three numbers, all 0..1, all read by other systems:
/// * <see cref="Rain"/>: how hard it is raining now (eased in and out).
/// * <see cref="Damp"/>: the ground's film of water. Rises in ~15 s of full
///   rain, dries in ~60 s: wet, dark, glossy ground (`wetness` global,
///   <see cref="Terrain"/>'s ground).
/// * <see cref="Wet"/>: standing water. Rises in ~45 s of full rain,
///   evaporates in ~3.5 min: puddle size (<see cref="Water"/>). A long dry
///   spell dries them out entirely.
///
/// Default is the <see cref="Clock"/>'s shower schedule: the game starts at
/// 19:00 on day 1 just after rain (Wet 0.6, puddles at their old size, ground
/// dry), the first shower is 21:00-22:30, and every day after has 2-3
/// showers drawn from (seed, day). One real second is one game minute.
/// `--weather=rain|clear|cycle`, `--wet=0..1`, `--time=HH:MM`, `--clock=rate`.
///
/// The rain itself: GPU streaks in a box that follows the player (world-space
/// particles, so walking does not drag them), lit per pixel so lamps light
/// the drops near them. They die on a heightfield of everything below them
/// (ground, roofs) and a sub-emitter throws a splash there. The heightfield
/// moves in 4 m snaps: re-rendering it every frame would be a depth pass per
/// frame. The pond's surface is transparent, so drops over it splash on the
/// bed, under water; the water shader draws its own rain rings instead.
///
/// On the scene: sun down to 30%, shadows fainter, fog five times thicker and
/// greyer, sky darker, colour a quarter less saturated, foliage swaying three
/// times harder. Scaled from the values captured at start, so the grade that
/// was measured is exactly what plays when it is dry.
/// </summary>
public partial class Weather : Node3D
{
    public static float Rain, Damp, Wet = 0.6f;

    /// <summary>`--weather=`: "cycle" (default), "rain", "clear".</summary>
    public static string Mode = "cycle";

    /// <summary>How soaked the player is: rain and wading soak, it dries
    /// slowly. Darkens the sprite and makes it drip.</summary>
    public static float Soak;
    /// <summary>The figure's exposure cancel for this region (the player's
    /// sprite gets it on its material; the townsfolk read it here).</summary>
    public static float FigureKeep = 1f;

    /// <summary>A line of help under the clock ("E: board").</summary>
    public static string Hint = "";

    /// <summary>Hide the clock HUD (captures, benches, the lighting study).</summary>
    public static bool Quiet;
    /// <summary>The travel keys' line and the weather word (F10): off by default --
    /// on screen they read as a debug build (user, 2026-09-30).</summary>
    public static bool ShowKeys;

    private readonly List<(BaseMaterial3D M, Color A, float R)> _walls = new(), _body = new();
    private GpuParticles3D _drips = null!;
    private static Weather? _self;
    private Label? _hud;
    private Vector3 _lastP;
    private float _stepT;
    private float _shown = -1f;

    private Node3D _player = null!;
    private DirectionalLight3D _sun = null!;
    private Environment _env = null!;
    private GpuParticles3D _drops = null!;
    private GpuParticles3D _sand = null!;
    /// <summary>The Ashdunes' weight at the player (no rain there).</summary>
    public static float DunesHere;
    /// <summary>Emberglass's weight at the player: 1 inside the wall, easing
    /// to 0 over 60 m outside it. Blends in <see cref="Grade.CityL"/>.</summary>
    public static float CityHere;
    private float _soft = -1f, _sunFog = -1f, _lampGain = 1f, _windowsLit = 1f;
    private GpuParticlesCollisionHeightField3D _field = null!;
    private DirectionalLight3D? _fill;
    private ShaderMaterial? _sky;
    private float _skyC = -1f;
    private Grade.Lighting? _skyL;
    private float _t, _shadow, _bg;
    private bool _wasRaining;

    /// <summary>The global shader uniforms weather drives, set to their start
    /// values. They are declared in project.godot [shader_globals], so the editor
    /// can compile every saved material too (Add would error on a declared one).</summary>
    public static void Globals()
    {
        RenderingServer.GlobalShaderParameterSet("wetness", 0f);
        RenderingServer.GlobalShaderParameterSet("city_wet", 0f);
        RenderingServer.GlobalShaderParameterSet("wind", 1f);
        // city windows and lamp glass: 1 / the city's exposure ratio (see _Process)
        RenderingServer.GlobalShaderParameterSet("lamp_gain", 1f);
        RenderingServer.GlobalShaderParameterSet("window_lit", 1f);
        Snow.Globals();
        Prints.Globals();
        Impact.Globals();
    }

    /// <summary>Every lit material under `root` darkens and turns glossier
    /// with the ground's wetness (houses, fences, lamp posts). Emissive
    /// materials (windows, flames) are left alone. Shared resources are fine:
    /// every instance of a house should get wet together.</summary>
    public void Soakable(Node root) => Collect(root, _walls, unshaded: false);

    /// <summary>The player's sprite: darkened by <see cref="Soak"/>.</summary>
    public void Body(Node root) => Collect(root, _body, unshaded: true);

    private static void Collect(Node n, List<(BaseMaterial3D M, Color A, float R)> into, bool unshaded)
    {
        void Add(Material? m)
        {
            if (m is not BaseMaterial3D b || b.EmissionEnabled) return;
            if ((b.ShadingMode == BaseMaterial3D.ShadingModeEnum.Unshaded) != unshaded) return;
            if (b.Transparency == BaseMaterial3D.TransparencyEnum.Alpha) return;   // blob shadow, glass
            foreach (var e in into) if (e.M == b) return;
            into.Add((b, b.AlbedoColor, b.Roughness));
        }
        if (n is GeometryInstance3D g) Add(g.MaterialOverride);
        if (n is MeshInstance3D mi && mi.Mesh != null)
            for (var s = 0; s < mi.Mesh.GetSurfaceCount(); s++)
                Add(mi.GetSurfaceOverrideMaterial(s) ?? mi.Mesh.SurfaceGetMaterial(s));
        foreach (var c in n.GetChildren()) Collect(c, into, unshaded);
    }

    /// <summary>One falling drop (or splash droplet) at `at` with `vel`: the
    /// player's and the animals' dripping, footstep splashes.</summary>
    public static void Drip(Vector3 at, Vector3 vel)
    {
        if (_self == null) return;
        _self._drips.EmitParticle(new Transform3D(Basis.Identity, at), vel, Colors.White, Colors.White,
            (uint)(GpuParticles3D.EmitFlags.Position | GpuParticles3D.EmitFlags.Velocity));
    }

    public void Build(Node3D player, DirectionalLight3D sun, Environment env)
    {
        _self = this;
        _player = player;
        _sun = sun;
        _env = env;
        _shadow = sun.ShadowOpacity;
        _bg = env.BackgroundEnergyMultiplier;
        _fill = sun.GetParent().GetNodeOrNull<DirectionalLight3D>("Fill");
        _sky = env.Sky?.SkyMaterial as ShaderMaterial;
        if (Mode is "rain" or "snow") Rain = Damp = 1f;

        var drop = new StandardMaterial3D
        {
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            AlbedoColor = new Color(0.72f, 0.78f, 0.9f, 0.26f),
            BillboardMode = BaseMaterial3D.BillboardModeEnum.FixedY,
            EmissionEnabled = true,
            Emission = new Color(0.12f, 0.14f, 0.18f),
            Roughness = 0.3f,
        };
        var splash = new StandardMaterial3D
        {
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            AlbedoColor = new Color(0.8f, 0.85f, 0.95f, 0.55f),
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
            EmissionEnabled = true,
            Emission = new Color(0.1f, 0.12f, 0.15f),
        };

        var splashes = new GpuParticles3D
        {
            Name = "Splashes",
            Amount = 3000,
            Lifetime = 0.35,
            LocalCoords = false,
            ProcessMaterial = new ParticleProcessMaterial
            {
                Direction = Vector3.Up,
                Spread = 55f,
                InitialVelocityMin = 1.0f,
                InitialVelocityMax = 2.4f,
                Gravity = new Vector3(0f, -9.8f, 0f),
                ScaleMin = 0.6f,
                ScaleMax = 1.2f,
            },
            // two pixels at 52 texels/m
            DrawPass1 = new QuadMesh { Size = new Vector2(0.04f, 0.04f), Material = splash },
            VisibilityAabb = new Aabb(new Vector3(-40f, -30f, -40f), new Vector3(80f, 50f, 80f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
        AddChild(splashes);

        _drops = new GpuParticles3D
        {
            Name = "Rain",
            Amount = 6000,
            Lifetime = 1.3,
            LocalCoords = false,
            Preprocess = 1.3,
            ProcessMaterial = new ParticleProcessMaterial
            {
                EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box,
                // local X across the view, Z along it: the node is turned to
                // the locked camera yaw, and the box stops ~8 m short of the lens
                EmissionBoxExtents = new Vector3(24f, 0.5f, 14f),
                Direction = new Vector3(0.1f, -1f, 0.04f),
                Spread = 2f,
                InitialVelocityMin = 16f,
                InitialVelocityMax = 19f,
                Gravity = new Vector3(0f, -4f, 0f),
                CollisionMode = ParticleProcessMaterial.CollisionModeEnum.HideOnContact,
                SubEmitterMode = ParticleProcessMaterial.SubEmitterModeEnum.AtCollision,
                SubEmitterAmountAtCollision = 1,
            },
            // a streak one pixel wide and half a metre long: motion blur, drawn
            DrawPass1 = new QuadMesh { Size = new Vector2(0.02f, 0.5f), Material = drop },
            VisibilityAabb = new Aabb(new Vector3(-30f, -30f, -30f), new Vector3(60f, 40f, 60f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            Emitting = true,
            AmountRatio = 0f,
        };
        AddChild(_drops);
        _drops.RotationDegrees = new Vector3(0f, CameraRig.BaseYaw, 0f);
        _drops.SubEmitter = _drops.GetPathTo(splashes);

        // blowing sand in the Ashdunes: grains skimming the ground across the
        // view, thicker in the gusts. Streaks two pixels tall, drawn motion-
        // blurred like the rain.
        var grain = new StandardMaterial3D
        {
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            AlbedoColor = new Color(0.88f, 0.74f, 0.52f, 0.5f),
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
            EmissionEnabled = true,
            Emission = new Color(0.16f, 0.12f, 0.08f),
        };
        _sand = new GpuParticles3D
        {
            Name = "Sand",
            Amount = 2500,
            Lifetime = 1.6,
            LocalCoords = false,
            Preprocess = 1.6,
            ProcessMaterial = new ParticleProcessMaterial
            {
                EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box,
                EmissionBoxExtents = new Vector3(24f, 0.6f, 16f),
                Direction = new Vector3(1f, 0.06f, 0.1f),
                Spread = 8f,
                InitialVelocityMin = 5f,
                InitialVelocityMax = 9f,
                Gravity = new Vector3(0f, -0.6f, 0f),
                ScaleMin = 0.6f,
                ScaleMax = 1.4f,
            },
            DrawPass1 = new QuadMesh { Size = new Vector2(0.16f, 0.04f), Material = grain },
            VisibilityAabb = new Aabb(new Vector3(-40f, -10f, -40f), new Vector3(80f, 20f, 80f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            AmountRatio = 0f,
        };
        AddChild(_sand);
        _sand.RotationDegrees = new Vector3(0f, CameraRig.BaseYaw, 0f);

        // drips and footstep splashes: emitted one by one from code
        _drips = new GpuParticles3D
        {
            Name = "Drips",
            Amount = 600,
            Lifetime = 0.6,
            LocalCoords = false,
            // Nothing of its own, only EmitParticle. Not AmountRatio 0: that
            // caps the live particles at zero, manual ones included, and no
            // drip ever showed (2026-09-23).
            Emitting = false,
            ProcessMaterial = new ParticleProcessMaterial { Gravity = new Vector3(0f, -9.8f, 0f), Spread = 0f },
            DrawPass1 = new QuadMesh { Size = new Vector2(0.05f, 0.08f), Material = splash },
            VisibilityAabb = new Aabb(new Vector3(-60f, -30f, -60f), new Vector3(120f, 60f, 120f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
        AddChild(_drips);

        if (!Quiet)
        {
            var layer = new CanvasLayer { Name = "Hud" };
            _hud = new Label { Position = new Vector2(12f, 8f), Modulate = new Color(1f, 1f, 1f, 0.8f) };
            layer.AddChild(_hud);
            AddChild(layer);
        }

        _field = new GpuParticlesCollisionHeightField3D
        {
            Name = "RainField",
            Size = new Vector3(64f, 40f, 64f),
            Resolution = GpuParticlesCollisionHeightField3D.ResolutionEnum.Resolution256,
            UpdateMode = GpuParticlesCollisionHeightField3D.UpdateModeEnum.WhenMoved,
        };
        AddChild(_field);
    }

    public override void _Process(double delta)
    {
        var dt = (float)delta;
        _t += dt;
        Clock.Minutes += dt * Clock.Rate;
        var want = Mode switch
        {
            "rain" or "snow" => 1f,
            "clear" => 0f,
            _ => Clock.Showers(Clock.Minutes) ? 1f : 0f,
        };
        // rates are per GAME minute, so a sped-up clock (--clock) time-lapses
        // the wetting and drying with the showers
        var g = dt * Clock.Rate;
        Rain = Mathf.MoveToward(Rain, want, g / 8f);              // 8 min to build, 8 to ease off
        Damp = Mathf.Clamp(Damp + (Rain > 0.05f ? Rain / 15f : -1f / 60f) * g, 0f, 1f);
        Wet = Mathf.Clamp(Wet + (Rain > 0.05f ? Rain / 45f : -1f / 210f) * g, 0f, 1f);

        var raining = Rain > 0.05f;
        if (raining != _wasRaining)
        {
            GD.Print($"weather: rain {(raining ? "starts" : "stops")} at {_t:F0} s ({Clock.Text}), puddles {Wet:F2}");
            _wasRaining = raining;
        }

        // the rain box: centred a little toward the camera from the player, so
        // it fills the near and middle of the frame; the far field is fog
        if (_player != null)
        {
            var p = _player.GetGlobalTransformInterpolated().Origin;
            // turned with the camera, which looks down city streets
            var yr = Mathf.DegToRad(CameraRig.LiveYaw);
            var f = new Vector3(-Mathf.Sin(yr), 0f, -Mathf.Cos(yr));
            _drops.RotationDegrees = _sand.RotationDegrees = new Vector3(0f, CameraRig.LiveYaw, 0f);
            // box centre 2 m beyond the player: 12 m toward the camera, 16 away
            _drops.GlobalPosition = p + f * 2f + Vector3.Up * 14f;
            _sand.GlobalPosition = p + f * 2f + Vector3.Up * 0.7f;
            DunesHere = Biomes.WeightOf(Biome.Dunes, new Vector2(p.X, p.Z), WorldGen.Seed);
            var pp = CityPlan.ToPlan(p.X, p.Z);
            CityHere = pp.LengthSquared() > CityPlan.Outer * CityPlan.Outer ? 0f
                : CityPlan.InPoly(pp, CityPlan.Encl) ? 1f
                : 1f - Mathf.SmoothStep(0f, 60f, CityPlan.PolyDist(pp, CityPlan.Encl, true));
            var snap = new Vector3(Mathf.Round(p.X / 4f) * 4f, Mathf.Round(p.Y / 4f) * 4f, Mathf.Round(p.Z / 4f) * 4f);
            if (!_field.GlobalPosition.IsEqualApprox(snap)) _field.GlobalPosition = snap;
        }
        // in snow country the same shower falls as snow (Snow's flakes); none
        // falls on the Ashdunes, where the wind lifts sand instead (Snow.Gust
        // runs everywhere, at 0.2 of full outside the snow)
        _drops.AmountRatio = Rain * (1f - Snow.Here) * (1f - DunesHere);
        _sand.AmountRatio = DunesHere * (0.3f + 0.7f * Mathf.Clamp(Snow.Gust / 0.2f, 0f, 1f));

        // the player: soaked by rain and by wading; drips while wet, and
        // splashes at the feet walking on wet ground
        if (_player != null)
        {
            var p = _player.GetGlobalTransformInterpolated().Origin;
            var speed = dt > 0f ? new Vector2(p.X - _lastP.X, p.Z - _lastP.Z).Length() / dt : 0f;
            _lastP = p;
            var wading = Water.Wading(p);
            var soakIn = wading ? 1f / 3f : Rain / 12f;
            var dryOut = Rain < 0.05f && !wading ? 1f / 90f : 0f;
            Soak = Mathf.Clamp(Soak + (soakIn - dryOut) * dt, 0f, 1f);
            if (GD.Randf() < Soak * dt * 30f)
            {
                var yr = Mathf.DegToRad(CameraRig.LiveYaw);
                var right = new Vector3(Mathf.Cos(yr), 0f, -Mathf.Sin(yr));
                Drip(p + right * (GD.Randf() - 0.5f) * 0.5f + Vector3.Up * (0.3f + GD.Randf() * 1.2f), Vector3.Down * 0.5f);
            }
            _stepT += dt;
            if (speed > 1f && (Damp > 0.3f || wading) && _stepT > 0.3f)
            {
                _stepT = 0f;
                for (var i = 0; i < 4; i++)
                    Drip(p + Vector3.Up * 0.05f, new Vector3(GD.Randf() - 0.5f, 1.2f + GD.Randf() * 1.3f, GD.Randf() - 0.5f));
            }
        }

        // wet walls: only rewrite materials when the wetness has moved
        if (Mathf.Abs(Damp - _shown) > 0.01f)
        {
            _shown = Damp;
            foreach (var (m, a, r0) in _walls)
            {
                m.AlbedoColor = new Color(a.R * (1f - 0.35f * Damp), a.G * (1f - 0.35f * Damp), a.B * (1f - 0.32f * Damp), a.A);
                m.Roughness = Mathf.Lerp(r0, 0.3f, Damp);
            }
        }

        if (_hud != null)
            _hud.Text = !ShowKeys ? (Breakables.Coins > 0 ? $"coins {Breakables.Coins}\n" : "") + Hint : $"{Clock.Text}   {(Snow.Falling > 0.05f ? $"snow ({Snow.Level.ToString().ToLower()})" : Snow.Here > 0.3f && Rain <= 0.05f ? $"snow {Snow.Depth:F2}" : Rain > 0.05f ? "rain" : Wet > 0.05f ? "puddles" : "dry")}"
                        + $"{(Breakables.Coins > 0 ? $"   coins {Breakables.Coins}" : "")}\n{Hint}\n"
                        + "F1 village  F2 lake  F3 snow  F4 desert market  F5 temple  F6 oasis  F7 Emberglass  F8 next quarter  F9 new regions";

        // The region grade: the base (Grade.L, what the village was measured
        // under) blended toward the region's own -- the Hoarfells'
        // (Grade.SnowL) or the Ashdunes' (Grade.DesertL); they never overlap
        // -- by that region's weight at the player, so walking up out of the
        // Crags changes the light over ~80 m. At weight 0 every value below
        // is exactly the base the scene was built with.
        var (S, c) = DunesHere > Snow.Here ? (Grade.DesertL, DunesHere) : (Grade.SnowL, Snow.Here);
        if (CityHere > c) (S, c) = (Grade.CityL, CityHere);
        var B = Grade.L;
        _sun.RotationDegrees = new Vector3(-Mathf.Lerp(B.Elev, S.Elev, c),
            Mathf.RadToDeg(Mathf.LerpAngle(Mathf.DegToRad(B.Yaw), Mathf.DegToRad(S.Yaw), c)), 0f);
        if (_fill != null)
        {
            _fill.LightColor = B.Fill.Lerp(S.Fill, c);
            _fill.LightEnergy = Mathf.Lerp(B.FillEnergy, S.FillEnergy, c);
        }
        _env.AmbientLightEnergy = Mathf.Lerp(B.AmbientEnergy, S.AmbientEnergy, c);
        if (B.VFog > 0f)
        {
            _env.VolumetricFogDensity = Mathf.Lerp(B.VFog, S.VFog, c);
            _env.VolumetricFogAlbedo = B.Fog.Lerp(S.Fog, c);
        }
        Post.Live?.Mist(B.Mist.Lerp(S.Mist, c), Mathf.Lerp(B.MistDensity, S.MistDensity, c));
        Post.Live?.Black(B.Black.Lerp(S.Black, c));
        var expo = Mathf.Lerp(1f, S.Exposure / B.Exposure, c);
        _env.TonemapExposure *= expo;
        // written only when they move (priced every frame at no cost, 2026-09-24,
        // but there is no reason to touch the light 120 times a second)
        var soft = Mathf.Lerp(B.Soft, S.Soft, c);
        if (soft != _soft) _sun.LightAngularDistance = _soft = soft;
        var sunFog = Mathf.Lerp(B.SunFog, S.SunFog, c);
        if (sunFog != _sunFog) _sun.LightVolumetricFogEnergy = _sunFog = sunFog;
        // The figure is unshaded and carries the bake's own light, and
        // SpriteModulate cancels only the BASE exposure -- so a region grade's
        // exposure dimmed it (to ~0.43 in the snow, ~0.49 on the dunes, ~0.46
        // in the city). Every region cancels its own now (user, 2026-09-24:
        // "the character looks darker in snow and desert"). In sRGB terms
        // (albedo is converted to linear, ~^2.2): scaling by 1/expo blew the
        // figure out, p90 0.99 against the twilight's 0.78.
        var keep = Mathf.Pow(expo, -1f / 2.2f);
        FigureKeep = keep;
        foreach (var (m, a, _) in _body)
            m.AlbedoColor = new Color(a.R * (1f - 0.22f * Soak) * keep, a.G * (1f - 0.2f * Soak) * keep, a.B * (1f - 0.14f * Soak) * keep, a.A);
        // Lamps have their own luminance (user, 2026-09-24: "the cloud shadow
        // should not hide the lamps"). The city's afternoon runs at ~0.46 of
        // the twilight exposure, which dimmed every flame and window with it;
        // in the city they cancel it, so a lamp reads the same on screen at
        // noon, under a cloud or at dusk. The same trick as the figure below,
        // but linear: light energy and emission are both pre-exposure.
        // everywhere (user, 2026-09-24: "universally apply"): the snow's and the
        // dunes' exposure dimmed their lanterns the same way
        var lampGain = 1f / Mathf.Lerp(1f, S.Exposure / B.Exposure, c);
        Grade.LampScale = Mathf.Lerp(1f, S.Lamps / B.Lamps, c) * lampGain;
        if (lampGain != _lampGain) RenderingServer.GlobalShaderParameterSet("lamp_gain", _lampGain = lampGain);
        var lit = Mathf.Lerp(B.WindowsLit, S.WindowsLit, c);
        if (lit != _windowsLit) RenderingServer.GlobalShaderParameterSet("window_lit", _windowsLit = lit);
        // re-colour the sky when the weight moves, or when the snow grade itself
        // changed (a new look at the same spot left the old sky, tour 2)
        if (_sky != null && (Mathf.Abs(c - _skyC) > 0.02f || !ReferenceEquals(S, _skyL)))
        {
            _skyC = c;
            _skyL = S;
            foreach (var (k, a, b) in new[] { ("top", B.SkyTop, S.SkyTop), ("horizon", B.SkyHorizon, S.SkyHorizon),
                         ("ground_horizon", B.GroundHorizon, S.GroundHorizon), ("ground_bottom", B.GroundBottom, S.GroundBottom),
                         ("cloud_lit", B.CloudLit, S.CloudLit), ("cloud_dark", B.CloudDark, S.CloudDark) })
            {
                var m = a.Lerp(b, c);
                _sky.SetShaderParameter(k, new Vector3(m.R, m.G, m.B));
            }
        }

        // Then the weather on top: rain (none of it where it falls as snow),
        // snowfall, and a blizzard's whiteout.
        var r = Rain * (1f - c);
        var fall = Snow.Falling;
        var wo = Snow.Whiteout;
        _sun.LightColor = B.Sun.Lerp(S.Sun, c);
        _sun.LightEnergy = Mathf.Lerp(B.SunEnergy, S.SunEnergy, c) * (1f - 0.7f * r) * (1f - 0.35f * fall) * (1f - 0.45f * wo);
        _sun.ShadowOpacity = _shadow * (1f - 0.55f * r) * (1f - 0.4f * fall);
        _env.FogDensity = Mathf.Lerp(B.FogDen, S.FogDen, c) * (1f + 4f * r) * (1f + 2.5f * fall + 7f * wo);
        _env.FogLightColor = B.Fog.Lerp(S.Fog, c).Lerp(new Color(0.42f, 0.46f, 0.52f), 0.75f * r).Lerp(new Color(0.74f, 0.78f, 0.86f), 0.8f * wo);
        _env.BackgroundEnergyMultiplier = _bg * (1f - 0.45f * r) * (1f - 0.2f * fall);
        _env.AmbientLightColor = B.Ambient.Lerp(S.Ambient, c).Lerp(new Color(0.36f, 0.40f, 0.46f), 0.6f * r);
        // World sets saturation fresh each frame before this runs (parent first)
        _env.AdjustmentSaturation *= Mathf.Lerp(1f, S.Saturation / B.Saturation, c) * (1f - 0.25f * r);
        _env.AdjustmentContrast = Mathf.Lerp(B.Contrast, S.Contrast, c);

        // Cloud shadows need a real sun (the city, the dunes): under the twilight's weak
        // sun they only darkened the village (spawn frames mean 0.24, 56 % dark,
        // 2026-09-24) and twilight stays as it was measured. Thicker with the
        // rain: at 0.9 there are no gaps, so no shafts.
        // Wherever there is a real sun: the city's afternoon and the dunes'
        // (the snow's lantern dusk and the twilight have none to cast them).
        Clouds.Cover = Mathf.Max(CityHere, DunesHere) * Mathf.Lerp(0.35f, 0.9f, Mathf.Max(Rain, Snow.Falling));
        RenderingServer.GlobalShaderParameterSet("wetness", Damp * (1f - c));
        RenderingServer.GlobalShaderParameterSet("city_wet", Damp * CityHere);
        Terrain.Damp(Damp * (1f - c));
        RenderingServer.GlobalShaderParameterSet("wind", 1f + 2f * r + 0.6f * fall + 3f * Snow.Gust + 4f * wo);
    }
}

/// <summary>
/// Game time: minutes since 00:00 on day 1, advanced by <see cref="Weather"/>
/// at <see cref="Rate"/> game minutes per real second. Drives the showers
/// only -- the light stays the measured twilight grade.
/// </summary>
/// <summary>
/// The save (PENDING, 2026-09-23 spec): the game clock and the weather's
/// state -- rain, damp, puddles, the player's soak -- to user://save.json,
/// every 60 s and on quit, read back at start. Plain play only (no
/// command-line flags): captures, benches and studies always start fresh,
/// and `--fresh` is a flag, so it starts fresh too.
/// </summary>
public static class Save
{
    private const string Path = "user://save.json";
    private static float _t;
    public static bool On => OS.GetCmdlineUserArgs().Length == 0;

    public static void Load()
    {
        if (!On || !FileAccess.FileExists(Path)) return;
        var j = Json.ParseString(FileAccess.GetFileAsString(Path));
        if (j.VariantType != Variant.Type.Dictionary) return;
        var d = (Godot.Collections.Dictionary)j;
        float F(string k, float def) => d.ContainsKey(k) ? (float)(double)d[k] : def;
        Clock.Minutes = F("minutes", Clock.Minutes);
        Weather.Rain = F("rain", Weather.Rain);
        Weather.Damp = F("damp", Weather.Damp);
        Weather.Wet = F("wet", Weather.Wet);
        Weather.Soak = F("soak", Weather.Soak);
        GD.Print($"save: loaded {Clock.Text}, rain {Weather.Rain:F2}");
    }

    public static void Write()
    {
        if (!On) return;
        var d = new Godot.Collections.Dictionary
        {
            ["minutes"] = Clock.Minutes, ["rain"] = Weather.Rain, ["damp"] = Weather.Damp,
            ["wet"] = Weather.Wet, ["soak"] = Weather.Soak,
        };
        using var f = FileAccess.Open(Path, FileAccess.ModeFlags.Write);
        f?.StoreString(Json.Stringify(d));
    }

    /// <summary>Every frame: writes once a minute.</summary>
    public static void Tick(float dt)
    {
        if (!On || (_t += dt) < 60f) return;
        _t = 0f;
        Write();
    }
}

public static class Clock
{
    public static float Minutes = 19f * 60f;
    public static float Rate = 1f;

    public static string Text
    {
        get
        {
            var m = (int)Minutes;
            return $"Day {m / 1440 + 1}  {m / 60 % 24:00}:{m % 60:00}";
        }
    }

    /// <summary>Is a shower on at this game minute? Day 1 has one fixed
    /// shower at 21:00-22:30 (so a fresh launch sees rain in two minutes);
    /// every day has 2-3 more from (seed, day), 30-150 min long. Yesterday's
    /// are checked too, for a shower that runs past midnight.</summary>
    public static bool Showers(float minutes)
    {
        if (minutes >= 21f * 60f && minutes < 22.5f * 60f) return true;
        var day = (int)(minutes / 1440f);
        for (var d = day - 1; d <= day; d++)
        {
            if (d < 0) continue;
            var rng = new System.Random((int)(WorldGen.Seed * 7919UL % int.MaxValue) ^ (d * 104729));
            var n = 2 + rng.Next(2);
            for (var i = 0; i < n; i++)
            {
                var start = d * 1440f + (float)rng.NextDouble() * 1440f;
                var len = 30f + (float)rng.NextDouble() * 120f;
                if (minutes >= start && minutes < start + len) return true;
            }
        }
        return false;
    }
}
