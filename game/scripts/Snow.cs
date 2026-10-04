using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Snow, and what it does in the Hoarfells (<see cref="Biome.Snow"/>).
///
/// Numbers other systems read:
/// * <see cref="Here"/>: how much the player's spot is snow country (0..1).
///   <see cref="Weather"/> turns its showers into snowfall by it and blends
///   the cold light in by it.
/// * <see cref="Falling"/>: how hard it is snowing now (Weather.Rain x Here).
/// * <see cref="Depth"/>: the snow on the ground, 0..1 (global `snow_depth`).
///   Grows while it snows (25 game minutes from bare to buried), settles
///   back toward 0.3 when it stops. The ground shaders cover patchy at low
///   depth and solid at high; tree snow and prints deepen with it.
/// * <see cref="Gust"/>: a gust of wind now (0..1), added to the sway.
///
/// What lives here:
/// * Snowfall: slow flakes that drift and swirl in a box that follows the
///   player, dying on the rain's heightfield (ground, roofs).
/// * Gusts: every 6-16 s a 2.2 s gust. Trees near the player carrying
///   snow may shed it (a burst of falling snow from the canopy, and the
///   tree's load drops), then reload while it snows (~40 s at full fall).
///   A tree also sheds when the player runs into it or a blow lands near it.
/// Footprints and the grains kicked up at each step are <see cref="Prints"/>'s
/// (moved out 2026-09-28, when sand and mud began taking prints too).
///
/// Flags: `--snow=0..1` sets the depth and holds it (captures);
/// `--weather=snow` is the same as `--weather=rain` (it snows where Here is 1).
/// </summary>
public partial class Snow : Node3D
{
    public static float Depth = 0.55f, Falling, Here, Gust, Whiteout;
    /// <summary>`--snow=`: depth set by hand and held.</summary>
    public static bool Held;

    /// <summary>How hard a snowfall is. Picked when one starts (from the game
    /// clock, so a day replays the same), or `--storm=light|medium|blizzard`.</summary>
    public enum Storm { Light, Medium, Blizzard }
    public static Storm Level = Storm.Medium;
    public static bool LevelHeld;

    /// <summary>Per level: flake share, sideways drive (m/s), fall speed,
    /// turbulence, depth gained per game minute at full fall, gust gap scale.
    /// Light: sparse, slow, nearly straight down, a dusting in an hour.
    /// Blizzard: every flake, driven sideways at 6 m/s and swirling, buries
    /// the ground in ~8 game minutes, gusts three times as often, spindrift
    /// along the ground and a whiteout (Weather's fog).</summary>
    private static readonly (float Share, float Drive, float Fall, float Turb, float Accum, float GustGap)[] Levels =
    {
        (0.3f, 0.3f, 0.8f, 0.04f, 1f / 60f, 1.0f),
        (0.7f, 0.9f, 1.1f, 0.07f, 1f / 25f, 0.8f),
        (1.0f, 6.0f, 2.4f, 0.20f, 1f / 8f, 0.35f),
    };
    private Storm _applied = (Storm)(-1);
    private bool _wasFalling;
    private GpuParticles3D _drift = null!;

    public static Snow? Live;
    /// <summary>Trees shed by the player running into them (the harness).</summary>
    public static int Brushed;

    private float _gustT = 6f, _gustLeft, _reloadT;
    private Vector3 _last;

    private Node3D _player = null!;
    private GpuParticles3D _flakes = null!, _shed = null!;

    /// <summary>A tree that can carry snow: its instance in a face batch.</summary>
    private sealed class Tree
    {
        public required MultiMesh Mm;
        public required int I;
        public required Vector3 Foot;
        public required float Full;      // load at its fullest (region weight)
        public required float H, W;      // sprite size, metres
        public float Load = 1f;
    }
    private readonly List<Tree> _trees = new();
    private readonly List<(Tree T, float At)> _pending = new();

    /// <summary>The globals the ground and foliage shaders read. Registered
    /// before any of them compiles.</summary>
    public static void Globals()
    {
        RenderingServer.GlobalShaderParameterSet("snow_depth", Depth);
    }

    /// <summary>One tree that can carry snow (<see cref="Kit"/>).</summary>
    public void AddTree(MultiMesh mm, int i, Vector3 foot, float full, float h, float w)
    {
        if (full > 0.01f) _trees.Add(new Tree { Mm = mm, I = i, Foot = foot, Full = full, H = h, W = w });
    }

    public void Build(Node3D player)
    {
        Live = this;
        _player = player;
        _last = player.GlobalPosition;

        var flake = new StandardMaterial3D
        {
            Transparency = BaseMaterial3D.TransparencyEnum.AlphaScissor,
            AlbedoColor = new Color(0.95f, 0.97f, 1f),
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
            EmissionEnabled = true,
            Emission = new Color(0.16f, 0.18f, 0.22f),
            Roughness = 1f,
        };
        _flakes = new GpuParticles3D
        {
            Name = "Snowfall",
            Amount = 7000,
            Lifetime = 12.0,
            Preprocess = 12.0,
            LocalCoords = false,
            ProcessMaterial = new ParticleProcessMaterial
            {
                EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box,
                EmissionBoxExtents = new Vector3(26f, 0.5f, 16f),
                Direction = new Vector3(0.25f, -1f, 0.1f),
                Spread = 12f,
                InitialVelocityMin = 0.8f,
                InitialVelocityMax = 1.4f,
                Gravity = new Vector3(0f, -0.25f, 0f),
                TurbulenceEnabled = true,
                TurbulenceNoiseStrength = 1.2f,
                TurbulenceNoiseScale = 6f,
                TurbulenceInfluenceMin = 0.03f,
                TurbulenceInfluenceMax = 0.08f,
                ScaleMin = 0.7f,
                ScaleMax = 1.3f,
                CollisionMode = ParticleProcessMaterial.CollisionModeEnum.HideOnContact,
            },
            // two to three pixels at 52 texels/m
            DrawPass1 = new QuadMesh { Size = new Vector2(0.05f, 0.05f), Material = flake },
            VisibilityAabb = new Aabb(new Vector3(-40f, -30f, -40f), new Vector3(80f, 50f, 80f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            Emitting = true,
            AmountRatio = 0f,
        };
        AddChild(_flakes);
        _flakes.RotationDegrees = new Vector3(0f, CameraRig.BaseYaw, 0f);

        GpuParticles3D Manual(string name, int amount, double life, float grav, float damp, Vector2 size) => new()
        {
            Name = name,
            Amount = amount,
            Lifetime = life,
            LocalCoords = false,
            Emitting = false,   // EmitParticle only (see Weather's drips)
            ProcessMaterial = new ParticleProcessMaterial
            {
                Gravity = new Vector3(0f, grav, 0f), Spread = 0f,
                DampingMin = damp, DampingMax = damp * 1.5f,
                ScaleMin = 0.7f, ScaleMax = 1.6f,
                CollisionMode = ParticleProcessMaterial.CollisionModeEnum.HideOnContact,
            },
            DrawPass1 = new QuadMesh { Size = size, Material = flake },
            VisibilityAabb = new Aabb(new Vector3(-60f, -30f, -60f), new Vector3(120f, 60f, 120f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
        // blizzard spindrift: sheets of snow driven along the ground
        var sheet = (StandardMaterial3D)flake.Duplicate();
        sheet.Transparency = BaseMaterial3D.TransparencyEnum.Alpha;
        sheet.AlbedoColor = new Color(0.92f, 0.95f, 1f, 0.45f);
        _drift = new GpuParticles3D
        {
            Name = "Spindrift",
            Amount = 3000,
            Lifetime = 2.5,
            LocalCoords = false,
            ProcessMaterial = new ParticleProcessMaterial
            {
                EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box,
                EmissionBoxExtents = new Vector3(26f, 0.35f, 16f),
                Direction = new Vector3(1f, 0.08f, 0.3f),
                Spread = 8f,
                InitialVelocityMin = 5f,
                InitialVelocityMax = 8f,
                Gravity = Vector3.Zero,
                TurbulenceEnabled = true,
                TurbulenceNoiseStrength = 2f,
                TurbulenceInfluenceMin = 0.1f,
                TurbulenceInfluenceMax = 0.2f,
            },
            DrawPass1 = new QuadMesh { Size = new Vector2(0.14f, 0.05f), Material = sheet },
            VisibilityAabb = new Aabb(new Vector3(-40f, -10f, -40f), new Vector3(80f, 20f, 80f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            Emitting = true,
            AmountRatio = 0f,
        };
        AddChild(_drift);
        _drift.RotationDegrees = new Vector3(0f, CameraRig.BaseYaw, 0f);
        _shed = Manual("Shed", 2400, 2.6, -3.5f, 1.2f, new Vector2(0.07f, 0.07f));
        AddChild(_shed);
    }

    public override void _Process(double delta)
    {
        var dt = (float)delta;
        var p = _player.GetGlobalTransformInterpolated().Origin;
        var xz = new Vector2(p.X, p.Z);
        Here = Biomes.WeightOf(Biome.Snow, xz, WorldGen.Seed);
        var falling = Weather.Rain * Here > 0.05f;
        if (falling && !_wasFalling && !LevelHeld)
        {
            var roll = Biomes.Hash(Mathf.FloorToInt(Clock.Minutes), 77, WorldGen.Seed);
            Level = roll < 0.4f ? Storm.Light : roll < 0.8f ? Storm.Medium : Storm.Blizzard;
            GD.Print($"snow: a {Level.ToString().ToLower()} fall starts ({Clock.Text})");
        }
        _wasFalling = falling;
        var lv = Levels[(int)Level];
        Falling = Weather.Rain * Here * lv.Share;
        Whiteout = Level == Storm.Blizzard ? Weather.Rain * Here : 0f;
        if (_applied != Level) ApplyLevel(lv);

        // depth: grows in a fall at the storm's rate, settles back when it
        // stops (game minutes)
        var g = dt * Clock.Rate;
        if (!Held)
            Depth = falling
                ? Mathf.Min(1f, Depth + Weather.Rain * Here * lv.Accum * g)
                : Mathf.MoveToward(Depth, 0.3f, g / 240f);
        RenderingServer.GlobalShaderParameterSet("snow_depth", Depth);

        // the boxes turn with the camera (it looks down city streets)
        var yr = Mathf.DegToRad(CameraRig.LiveYaw);
        var fwd = new Vector3(-Mathf.Sin(yr), 0f, -Mathf.Cos(yr));
        _flakes.RotationDegrees = _drift.RotationDegrees = new Vector3(0f, CameraRig.LiveYaw, 0f);
        _flakes.GlobalPosition = p + fwd * 2f + Vector3.Up * 12f;
        _flakes.AmountRatio = Falling;
        _drift.GlobalPosition = new Vector3(p.X, WorldGen.Height(p.X, p.Z) + 0.5f, p.Z) + fwd * 2f;
        _drift.AmountRatio = Whiteout;

        Gusts(p, dt);
        Brush(p, dt);
    }

    private void ApplyLevel((float Share, float Drive, float Fall, float Turb, float Accum, float GustGap) lv)
    {
        _applied = Level;
        var pm = (ParticleProcessMaterial)_flakes.ProcessMaterial;
        // the node is turned to the camera yaw: local X runs across the view
        pm.Direction = new Vector3(lv.Drive, -lv.Fall, 0.3f * lv.Drive).Normalized();
        var speed = new Vector2(lv.Drive, lv.Fall).Length();
        pm.InitialVelocityMin = speed * 0.8f;
        pm.InitialVelocityMax = speed * 1.2f;
        pm.TurbulenceInfluenceMin = lv.Turb * 0.5f;
        pm.TurbulenceInfluenceMax = lv.Turb;
        // flakes must still reach the ground from 12 m up before they expire
        _flakes.Lifetime = Mathf.Clamp(14f / lv.Fall, 5f, 16f);
    }

    // ----------------------------------------------------- knocked off a tree
    /// <summary>Running into a loaded tree shakes its snow down (DQ3's conifers drop
    /// flakes when brushed): within its trunk plus a share of its crown, at more than a
    /// walk.</summary>
    private void Brush(Vector3 p, float dt)
    {
        var speed = dt > 0f ? new Vector2(p.X - _last.X, p.Z - _last.Z).Length() / dt : 0f;
        _last = p;
        if (Here < 0.05f || speed < PTune.WalkSpeed * 1.15f || speed > 40f) return;
        foreach (var t in _trees)
            if (t.Load * t.Full > 0.35f && new Vector2(t.Foot.X - p.X, t.Foot.Z - p.Z).Length() < 0.9f + t.W * 0.18f)
            {
                ShedFrom(t);
                Brushed++;
            }
    }

    /// <summary>The nearest tree still carrying snow (the harness runs into it).</summary>
    public Vector3? NearestLoaded(Vector3 p)
    {
        Vector3? best = null;
        var bd = float.MaxValue;
        foreach (var t in _trees)
        {
            if (t.Load * t.Full <= 0.35f) continue;
            var d = new Vector2(t.Foot.X - p.X, t.Foot.Z - p.Z).LengthSquared();
            if (d < bd) { bd = d; best = t.Foot; }
        }
        return best;
    }

    /// <summary>A blow landing (<see cref="Impact.Shock"/>): loaded trees within 2.5x its
    /// radius shed.</summary>
    public void Shock(Vector3 at, float r)
    {
        if (Here < 0.05f) return;
        foreach (var t in _trees)
            if (t.Load * t.Full > 0.2f && new Vector2(t.Foot.X - at.X, t.Foot.Z - at.Z).Length() < r * 2.5f)
                ShedFrom(t);
    }

    // -------------------------------------------------------------- the wind
    private void Gusts(Vector3 p, float dt)
    {
        // a gust: 2.2 s, a sine envelope
        _gustT -= dt;
        if (_gustT <= 0f && _gustLeft <= 0f)
        {
            _gustLeft = 2.2f;
            _gustT = (6f + GD.Randf() * 10f) * Levels[(int)Level].GustGap;
            if (Here > 0.05f)
                foreach (var t in _trees)
                {
                    var d = new Vector2(t.Foot.X - p.X, t.Foot.Z - p.Z).Length();
                    if (d < 40f && t.Load * t.Full > 0.35f && GD.Randf() < 0.55f)
                        _pending.Add((t, GD.Randf() * 2f));
                }
        }
        if (_gustLeft > 0f)
        {
            _gustLeft -= dt;
            // full strength in snow country and on open ground (the Meadows, the Crags);
            // a fifth of it in the woods (Surface.Exposure 0.3 .. 1)
            var open = 0.2f + 0.8f * Mathf.Clamp((Surface.Exposure(new Vector2(p.X, p.Z)) - 0.3f) / 0.7f, 0f, 1f);
            Gust = Mathf.Sin(Mathf.Pi * Mathf.Clamp(1f - _gustLeft / 2.2f, 0f, 1f)) * Mathf.Max(Here, open);
            for (var i = _pending.Count - 1; i >= 0; i--)
            {
                var (t, at) = _pending[i];
                if (2.2f - _gustLeft < at) continue;
                ShedFrom(t);
                _pending.RemoveAt(i);
            }
        }
        else Gust = 0f;

        // reload while it snows, once a second
        _reloadT += dt;
        if (_reloadT >= 1f)
        {
            if (Falling > 0.05f)
                foreach (var t in _trees)
                    if (t.Load < 1f) SetLoad(t, Mathf.Min(1f, t.Load + Falling * _reloadT / 40f));
            _reloadT = 0f;
        }
    }

    private void ShedFrom(Tree t)
    {
        var amount = t.Load * t.Full;
        SetLoad(t, 0.08f);
        var wind = new Vector3(0.9f, 0f, 0.35f);   // the snowfall's own drift
        var n = (int)(30 + 50 * amount);
        for (var i = 0; i < n; i++)
        {
            var at = t.Foot + new Vector3((GD.Randf() - 0.5f) * t.W * 0.6f, t.H * (0.35f + GD.Randf() * 0.55f),
                                          (GD.Randf() - 0.5f) * t.W * 0.3f);
            var v = wind * (0.6f + GD.Randf()) + new Vector3((GD.Randf() - 0.5f) * 0.8f, -GD.Randf() * 0.8f, (GD.Randf() - 0.5f) * 0.8f);
            _shed.EmitParticle(new Transform3D(Basis.Identity, at), v, Colors.White, Colors.White,
                (uint)(GpuParticles3D.EmitFlags.Position | GpuParticles3D.EmitFlags.Velocity));
        }
    }

    private static void SetLoad(Tree t, float load)
    {
        t.Load = load;
        t.Mm.SetInstanceCustomData(t.I, new Color(load * t.Full, 0f, 0f, 0f));
    }
}
