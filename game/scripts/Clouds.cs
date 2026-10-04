using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Cloud shadows and the light through their gaps.
///
/// The shadows: a sheet high over the player that is never drawn, only its
/// shadow (`ShadowsOnly`), with holes cut in a drifting noise. The sheet is
/// 12 x 12 thin box tiles in one MultiMesh, NOT a PlaneMesh: measured
/// 2026-09-24, a PlaneMesh cast no directional shadow with any material (the
/// cloud shader, a default material, with or without a cull margin), while a
/// 16 m box with the very same shader darkened the market from 0.322 to 0.233. The sun's own
/// shadow map carries them, so they take sunlight away and leave ambient alone
/// -- no double-dark under an eave -- and no material is touched; the
/// volumetric fog samples the same shadow map, so facing the sun the gaps
/// become beams in the haze. The holes are a `discard`, not ALPHA_SCISSOR:
/// Godot 4 does not cast shadows through alpha scissor (godot#58924), and
/// the first cut, written that way, cast nothing -- measured, cover 0.35 and
/// cover 1.0 gave the same frame (2026-09-24).
///
/// The shafts: fog beams only read looking toward the sun, so the god light
/// the user asked for is also drawn -- long additive cards along the sun's
/// ray, turned about that ray to face the lens, standing in the gaps. The CPU
/// samples the same noise image, so a shaft fades in where the ground is lit
/// and out when a cloud drifts over it.
///
/// Godot 4.6 directional lights have no projector (godot-proposals #8237);
/// the usual workaround is a custom light() in every material, and ours are
/// inline shader strings in five files.
/// </summary>
public partial class Clouds : MultiMeshInstance3D
{
    /// <summary>Share of the ground in cloud shadow; <see cref="Weather"/>
    /// sets it (city only, thicker with rain).</summary>
    public static float Cover = 0.35f;
    /// <summary>`--noshadowclouds`: off, for benching against.</summary>
    // TEMP (user, 2026-09-30: "remove the clouds for a while"): off by default; set back to true
    public static bool Enabled = false;
    /// <summary>`--noshafts`: the drawn god light off.</summary>
    public static bool Shafts = true;
    /// <summary>Tests: hold the cover here, whatever the weather says.</summary>
    public static float? Force;
    /// <summary>Drift, world m/s. The sky's cloud band scrolls toward
    /// -(3, 1) in world XZ (`Grade.CloudSky`), so the shadows go the same way.</summary>
    private static readonly Vector2 Wind = new Vector2(-3f, -1f).Normalized() * 3f;
    private const float Height = 45f, Tile = 16f, Period = 360f;
    private const int Tiles = 12;   // 192 m: all the sheet that can shade the 80 m shadow range (26 tiles cost 0.85 ms)
    private const int Res = 512;

    private Node3D _player = null!;
    private DirectionalLight3D _sun = null!;
    private Camera3D _eye = null!;
    private ShaderMaterial _mat = null!;
    private readonly float[] _quantile = new float[256];
    private byte[] _px = System.Array.Empty<byte>();
    private float _thr = 1f;
    private Vector2 _drift;

    public void Build(Node3D player, DirectionalLight3D sun, Camera3D eye)
    {
        _player = player;
        _sun = sun;
        _eye = eye;

        // One tile of cloud, seamless, 512 px over Period metres: blobs of
        // ~40-50 m with ragged edges. At ~88 m (frequency 0.008) a blob was
        // wider than the frame, and a 35 % cover sat the market wholly in a gap.
        var noise = new FastNoiseLite
        {
            NoiseType = FastNoiseLite.NoiseTypeEnum.SimplexSmooth,
            Frequency = 0.016f,
            FractalType = FastNoiseLite.FractalTypeEnum.Fbm,
            FractalOctaves = 4,
            Seed = 31,
        };
        var img = noise.GetSeamlessImage(Res, Res, false, false, 0.1f, true);
        img.Convert(Image.Format.L8);
        // Coverage -> threshold, from the image's own histogram, so Cover is
        // the shadowed share of the ground and not a guess at the noise's spread.
        _px = img.GetData();
        var hist = new int[256];
        foreach (var b in _px) hist[b]++;
        var acc = 0;
        for (var v = 0; v < 256; v++) { acc += hist[v]; _quantile[v] = acc / (float)_px.Length; }

        _mat = new ShaderMaterial
        {
            Shader = new Shader
            {
                Code = @"
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled;

uniform sampler2D clouds : filter_linear, repeat_enable;
uniform float threshold = 0.6;
uniform vec2 drift;
uniform float period = 360.0;
varying vec2 wxz;

void vertex() {
    wxz = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
}

void fragment() {
    if (texture(clouds, (wxz - drift) / period).r < threshold) discard;
    ALBEDO = vec3(0.0);
}",
            },
        };
        _mat.SetShaderParameter("clouds", ImageTexture.CreateFromImage(img));
        _mat.SetShaderParameter("period", Period);

        Name = "Clouds";
        var mm = new MultiMesh
        {
            TransformFormat = MultiMesh.TransformFormatEnum.Transform3D,
            Mesh = new BoxMesh { Size = new Vector3(Tile, 0.5f, Tile) },
            InstanceCount = Tiles * Tiles,
        };
        for (var i = 0; i < Tiles; i++)
        for (var j = 0; j < Tiles; j++)
            mm.SetInstanceTransform(i * Tiles + j, new Transform3D(Basis.Identity,
                new Vector3((i - (Tiles - 1) * 0.5f) * Tile, 0f, (j - (Tiles - 1) * 0.5f) * Tile)));
        Multimesh = mm;
        MaterialOverride = _mat;
        CastShadow = ShadowCastingSetting.ShadowsOnly;
        Visible = Enabled;

        BuildShafts();
    }

    /// <summary>Is world (x, z) in a gap right now -- what the shadow map says,
    /// from the same image the shader samples (bilinear, wrapped).</summary>
    public bool Lit(float x, float z)
    {
        var u = (((x - _drift.X) / Period) % 1f + 1f) % 1f * Res - 0.5f;
        var v = (((z - _drift.Y) / Period) % 1f + 1f) % 1f * Res - 0.5f;
        int x0 = Mathf.FloorToInt(u), y0 = Mathf.FloorToInt(v);
        float fx = u - x0, fy = v - y0;
        float P(int i, int j) => _px[((j % Res + Res) % Res) * Res + (i % Res + Res) % Res] / 255f;
        var n = Mathf.Lerp(Mathf.Lerp(P(x0, y0), P(x0 + 1, y0), fx), Mathf.Lerp(P(x0, y0 + 1), P(x0 + 1, y0 + 1), fx), fy);
        return n < _thr;
    }

    public override void _Process(double delta)
    {
        if (_player == null) return;
        var dt = (float)delta;
        // no cover (outside the city): no caster in the shadow pass at all
        var cover = Force ?? Cover;
        var on = Enabled && cover > 0.01f;
        if (Visible != on) Visible = on;
        Shine(dt, on ? cover : 0f);
        if (!on) return;
        _drift = (_drift + Wind * dt).PosMod(Period);
        _mat.SetShaderParameter("drift", _drift);
        // the value below which (1 - cover) of the tile lies
        var want = 1f - Mathf.Clamp(cover, 0f, 1f);
        var t = 0;
        while (t < 255 && _quantile[t] < want) t++;
        _thr = (t + 0.5f) / 255f;
        _mat.SetShaderParameter("threshold", _thr);
        // Shift the sheet toward the sun so its shadow lands round the player,
        // whatever the sun's height.
        var p = _player.GetGlobalTransformInterpolated().Origin;
        var l = -_sun.GlobalBasis.Z;   // the way the light travels
        var k = Height / Mathf.Max(-l.Y, 0.12f);
        GlobalPosition = new Vector3(p.X - l.X * k, p.Y + Height, p.Z - l.Z * k);
    }

    // ------------------------------------------------------------------ shafts
    private sealed class Shaft
    {
        public MeshInstance3D Node = null!;
        public Vector3 G;
        public float A;
    }

    private const int ShaftCount = 16;
    /// <summary>Additive strength of a shaft's core; `--shafts=0.1` dials it.</summary>
    public static float ShaftStrength = 0.12f;
    private const float ShaftLength = 38f;
    private readonly List<Shaft> _shafts = new();
    private ShaderMaterial _shaftMat = null!;
    private readonly RandomNumberGenerator _rng = new() { Seed = 5 };
    private Vector3 _last;
    private int _cluster;

    private void BuildShafts()
    {
        _shaftMat = new ShaderMaterial
        {
            Shader = new Shader
            {
                Code = @"
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, world_vertex_coords, fog_disabled;

uniform vec3 axis = vec3(0.0, 1.0, 0.0);   // ground -> sun, unit
uniform vec3 tint = vec3(1.0, 0.8, 0.55);
uniform float strength = 0.12;
uniform float length_m = 38.0;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
instance uniform float alpha = 0.0;
instance uniform float width_m = 5.0;
instance uniform float seed = 0.0;
varying float along;
varying float across;

void vertex() {
    // the card turns about the ray to face the lens, so it is never edge-on
    vec3 c = MODEL_MATRIX[3].xyz;
    vec3 side = normalize(cross(axis, normalize(CAMERA_POSITION_WORLD - c)));
    across = UV.x - 0.5;
    along = 1.0 - UV.y;
    VERTEX = c + side * across * width_m + axis * along * length_m;
}

void fragment() {
    // a flat core with soft sides, not a gaussian smear: the reference beams
    // (Octopath, DQ3 HD-2D) read as bands with edges
    float edge = 1.0 - smoothstep(0.22, 0.5, abs(across));
    float ends = smoothstep(0.0, 0.22, along) * (1.0 - smoothstep(0.55, 1.0, along));
    float streak = 0.8 + 0.2 * sin(along * 9.0 + seed * 6.28);
    // soft where the shaft meets a wall or the ground, never a hard seam
    float d = texture(depth_tex, SCREEN_UV).r;
    vec4 v = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, d, 1.0);
    float soft = clamp((-v.z / v.w + VERTEX.z) / 2.5, 0.0, 1.0);
    ALBEDO = tint * (strength * alpha * edge * ends * streak * soft);
}",
            },
        };
        _shaftMat.SetShaderParameter("length_m", ShaftLength);
        _shaftMat.SetShaderParameter("strength", ShaftStrength);
        var quad = new QuadMesh { Size = Vector2.One };
        for (var i = 0; i < ShaftCount; i++)
        {
            var n = new MeshInstance3D
            {
                Name = $"Shaft{i}",
                Mesh = quad,
                MaterialOverride = _shaftMat,
                CastShadow = ShadowCastingSetting.Off,
                TopLevel = true,
                CustomAabb = new Aabb(new Vector3(-30f, -5f, -30f), new Vector3(60f, 50f, 60f)),
                Visible = false,
            };
            n.SetInstanceShaderParameter("width_m", _rng.RandfRange(1.2f, 3.5f));
            n.SetInstanceShaderParameter("seed", _rng.Randf());
            AddChild(n);
            _shafts.Add(new Shaft { Node = n });
        }
    }

    /// <summary>Fade each shaft toward "its ground is lit", and move one that
    /// has gone out to a lit spot in view. Needs clouds to exist (no gaps
    /// without them) and not an overcast (no sun through them).</summary>
    private void Shine(float dt, float cover)
    {
        var k = Shafts ? Mathf.SmoothStep(0.08f, 0.25f, cover) * (1f - Mathf.SmoothStep(0.75f, 0.92f, cover)) : 0f;
        _shaftMat.SetShaderParameter("strength", ShaftStrength);
        var toSun = _sun.GlobalBasis.Z;
        _shaftMat.SetShaderParameter("axis", toSun);
        _shaftMat.SetShaderParameter("tint", new Vector3(_sun.LightColor.R, _sun.LightColor.G, _sun.LightColor.B));
        var eye = _eye.GlobalPosition;
        var fwd = (-_eye.GlobalBasis.Z with { Y = 0f }).Normalized();
        var right = new Vector3(-fwd.Z, 0f, fwd.X);
        var moved = false;
        foreach (var s in _shafts)
        {
            var lit = k > 0f && s.Node.Visible && Lit(s.G.X, s.G.Z);
            s.A = Mathf.MoveToward(s.A, lit ? 1f : 0f, dt / 1.6f);
            var gone = s.A <= 0f && !lit;
            if (gone && !moved && k > 0f)
            {
                // one respawn a frame: a lit ground point 8-48 m into the view,
                // or beside the last beam placed, so they come in clusters
                for (var tries = 0; tries < 6; tries++)
                {
                    var g = _cluster > 0
                        ? _last + right * _rng.RandfRange(1.6f, 3.2f) * (_rng.Randf() < 0.5f ? -1f : 1f) + fwd * _rng.RandfRange(-2f, 2f)
                        : eye + fwd * _rng.RandfRange(8f, 48f) + right * _rng.RandfRange(-18f, 18f);
                    if (!Lit(g.X, g.Z)) { _cluster = 0; continue; }
                    g.Y = WorldGen.Height(g.X, g.Z);
                    s.G = g;
                    s.Node.GlobalPosition = g;
                    s.Node.Visible = true;
                    moved = true;
                    _last = g;
                    _cluster = _cluster > 0 ? _cluster - 1 : _rng.RandiRange(1, 3);
                    break;
                }
            }
            if (s.Node.Visible && gone && !moved) s.Node.Visible = false;
            s.Node.SetInstanceShaderParameter("alpha", s.A * k);
        }
    }
}
