using Godot;

namespace Worldbuilder;

/// <summary>
/// What hangs in the light (user, 2026-09-27, option A after four reference
/// videos: "air particles: dust motes ... fireflies"). Two world-space emitters
/// that follow the player and turn with the camera, as <see cref="Snow"/>'s
/// flakes do: warm motes drifting in the city's afternoon, and fireflies
/// blinking low over the ground in the twilight regions. Each is weighted by
/// where the player is (AmountRatio) and stops in rain.
/// </summary>
public partial class Air : Node3D
{
    private Node3D _player = null!;
    private GpuParticles3D _motes = null!, _flies = null!;

    public void Bind(Node3D player)
    {
        _player = player;
        // two texels at 52/m; a slow drift that barely rises
        _motes = Emitter("Motes", 160, 7.0, new Vector3(12f, 3f, 8f), 0.035f, 0.05f, 0.2f, 0.02f,
                         new Color(1f, 0.9f, 0.7f, 0.5f), fade: false);
        // a little larger, wandering, each one glowing up and dying away once
        _flies = Emitter("Fireflies", 40, 4.0, new Vector3(14f, 0.6f, 10f), 0.05f, 0.2f, 0.5f, 0f,
                         new Color(0.85f, 1f, 0.4f), fade: true);
    }

    private GpuParticles3D Emitter(string name, int amount, double life, Vector3 box, float size,
                                   float vmin, float vmax, float rise, Color col, bool fade)
    {
        var mat = new StandardMaterial3D
        {
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            BlendMode = BaseMaterial3D.BlendModeEnum.Add,
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
            VertexColorUseAsAlbedo = true,
            AlbedoColor = col,
        };
        var pm = new ParticleProcessMaterial
        {
            EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box,
            EmissionBoxExtents = box,
            Direction = Vector3.Up,
            Spread = 180f,
            InitialVelocityMin = vmin,
            InitialVelocityMax = vmax,
            Gravity = new Vector3(0f, rise, 0f),
            TurbulenceEnabled = true,
            TurbulenceNoiseStrength = 0.6f,
            TurbulenceNoiseScale = 4f,
            TurbulenceInfluenceMin = 0.02f,
            TurbulenceInfluenceMax = 0.06f,
        };
        // in and out over each life, so nothing pops; a firefly's rise and
        // fall IS its blink
        var ramp = new Gradient();
        ramp.SetColor(0, new Color(1f, 1f, 1f, 0f));
        ramp.SetColor(1, new Color(1f, 1f, 1f, 0f));
        ramp.AddPoint(fade ? 0.5f : 0.2f, new Color(1f, 1f, 1f, 1f));
        if (!fade) ramp.AddPoint(0.8f, new Color(1f, 1f, 1f, 1f));
        pm.ColorRamp = new GradientTexture1D { Gradient = ramp };
        var e = new GpuParticles3D
        {
            Name = name, Amount = amount, Lifetime = life, Preprocess = life, LocalCoords = false,
            ProcessMaterial = pm,
            DrawPass1 = new QuadMesh { Size = new Vector2(size, size), Material = mat },
            VisibilityAabb = new Aabb(new Vector3(-30f, -10f, -30f), new Vector3(60f, 25f, 60f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            Emitting = true, AmountRatio = 0f,
        };
        AddChild(e);
        return e;
    }

    public override void _Process(double delta)
    {
        if (_player == null) return;
        var p = _player.GlobalPosition;
        var yr = Mathf.DegToRad(CameraRig.LiveYaw);
        var fwd = new Vector3(-Mathf.Sin(yr), 0f, -Mathf.Cos(yr));
        _motes.RotationDegrees = _flies.RotationDegrees = new Vector3(0f, CameraRig.LiveYaw, 0f);
        var dry = Mathf.Clamp(1f - Weather.Rain / 0.3f, 0f, 1f);
        _motes.GlobalPosition = p + fwd * 2f + Vector3.Up * 2.5f;
        _motes.AmountRatio = Weather.CityHere * dry;
        _flies.GlobalPosition = new Vector3(p.X, WorldGen.Height(p.X, p.Z) + 0.9f, p.Z) + fwd * 2f;
        _flies.AmountRatio = (1f - Weather.CityHere) * (1f - Snow.Here) * (1f - Weather.DunesHere) * dry;
    }
}
