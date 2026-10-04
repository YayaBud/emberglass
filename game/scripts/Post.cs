using Godot;

namespace Worldbuilder;

/// <summary>
/// The dreamy finish (user, 2026-09-28, a "with / without post-processing"
/// video, ref/video_2026-09-28: "the thing you have to do is this"): low mist
/// drifting in patches over the ground (a fog volume round the player; the
/// sun's volumetric light makes the shafts through it), shadows lifted toward
/// violet and highlights toward peach (a per-channel colour curve), a softer,
/// wider bloom, and violet corners. <see cref="Set"/> switches all of it, for
/// the harness's A/B; `--nopost` never builds it.
/// </summary>
public partial class Post : Node3D
{
    public static bool Enabled = true;
    public static Post? Live;

    private Node3D _player = null!;
    private Environment _env = null!;
    private FogVolume _mist = null!;
    private (float Bloom, float Threshold, float Intensity) _glow;
    private GradientTexture1D _curve = null!;
    private ShaderMaterial? _vignette;
    private Vector3 _vigTint;
    private float _vigStrength;

    public void Bind(Node3D player, Environment env)
    {
        _player = player;
        _env = env;
        Live = this;
        _mist = new FogVolume
        {
            Name = "Mist",
            Size = new Vector3(110f, 7f, 110f),
            Shape = RenderingServer.FogVolumeShape.Box,
            Material = new ShaderMaterial { Shader = new Shader { Code = MistCode } },
        };
        AddChild(_mist);
        // per channel, 0 -> 1: the blacks lift to violet, the whites settle
        // warm (blue held down at the top), the mids stay close to true
        var g = new Gradient();
        g.SetColor(0, new Color(0.075f, 0.035f, 0.12f));
        g.SetColor(1, new Color(1.0f, 0.95f, 0.86f));
        g.AddPoint(0.5f, new Color(0.53f, 0.49f, 0.5f));
        _curve = new GradientTexture1D { Gradient = g, Width = 256 };
        _glow = (_env.GlowBloom, _env.GlowHdrThreshold, _env.GlowIntensity);
        _vignette = (GetTree().Root.FindChild("Vignette", true, false) as ColorRect)?.Material as ShaderMaterial;
        if (_vignette != null)
        {
            _vigTint = (Vector3)_vignette.GetShaderParameter("tint");
            _vigStrength = (float)_vignette.GetShaderParameter("strength");
        }
        Set(true);
    }

    private Color _mistCol;
    private float _mistDen = -1f;
    private Color _black = new(0.075f, 0.035f, 0.12f);

    /// <summary>The curve's black point, from the region grade (Weather blends it);
    /// the vignette's tint follows it at the ratio the violet pair was set at.</summary>
    public void Black(Color c)
    {
        if (c == _black) return;
        _black = c;
        _curve.Gradient.SetColor(0, c);
        if (_vignette != null && _env.AdjustmentColorCorrection != null)
            _vignette.SetShaderParameter("tint", Tint());
    }

    private Vector3 Tint() => new(_black.R * 1.33f, _black.G * 1.14f, _black.B * 1.33f);

    /// <summary>The mist's colour and density, from the region grade (Weather blends them).</summary>
    public void Mist(Color c, float density)
    {
        var m = (ShaderMaterial)_mist.Material;
        if (c != _mistCol) m.SetShaderParameter("albedo", _mistCol = c);
        if (density != _mistDen) m.SetShaderParameter("density", _mistDen = density);
    }

    public void Set(bool on)
    {
        _mist.Visible = on;
        _env.AdjustmentColorCorrection = on ? _curve : null;
        _env.GlowBloom = on ? _glow.Bloom + 0.12f : _glow.Bloom;
        _env.GlowHdrThreshold = on ? _glow.Threshold * 0.8f : _glow.Threshold;
        _env.GlowIntensity = on ? _glow.Intensity * 1.15f : _glow.Intensity;
        if (_vignette != null)
        {
            _vignette.SetShaderParameter("tint", on ? Tint() : _vigTint);
            _vignette.SetShaderParameter("strength", on ? _vigStrength * 1.12f : _vigStrength);
        }
    }

    public override void _Process(double delta)
    {
        if (_player == null) return;
        // the mist lies from 1 m below the player's ground to 6 m above it; the
        // pattern is in world space, so moving the box moves nothing
        var p = _player.GlobalPosition;
        _mist.GlobalPosition = new Vector3(p.X, WorldGen.Height(p.X, p.Z) + 2.5f, p.Z);
        if (GetViewport().GetCamera3D() is { } cam) ((ShaderMaterial)_mist.Material).SetShaderParameter("eye", cam.GlobalPosition);
        // rain washes it out
        _mist.Visible = _env.AdjustmentColorCorrection != null && Weather.Rain < 0.3f;
    }

    private const string MistCode = @"
shader_type fog;

uniform float density = 0.22;
uniform vec3 eye;
uniform vec3 albedo : source_color = vec3(0.95, 0.86, 0.90);
uniform vec2 wind = vec2(0.55, 0.22);

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

void fog() {
    // banks ~15-25 m across, drifting downwind, with a slower churn inside
    vec2 q = WORLD_POSITION.xz * 0.05 + wind * TIME * 0.04;
    float n = noise(q) * 0.55 + noise(q * 2.3 + vec2(7.1, 3.3) - wind * TIME * 0.03) * 0.3
            + noise(q * 5.7 + 11.0) * 0.15;
    float banks = smoothstep(0.45, 0.66, n);
    // thick at the ground, gone by head height and above
    float h = UVW.y;
    float lie = exp(-h * 3.5) * smoothstep(0.0, 0.08, h);
    // soft at the box's sides, so its edge never shows
    vec2 e = abs(UVW.xz - 0.5) * 2.0;
    float side = 1.0 - smoothstep(0.7, 1.0, max(e.x, e.y));
    // clear round the lens: the mist lies in the middle distance, not on the glass
    float near = smoothstep(5.0, 16.0, length(WORLD_POSITION - eye));
    DENSITY = density * banks * lie * side * near;
    ALBEDO = albedo;
}
";
}
