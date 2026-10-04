using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Trees and bushes as pixel-art sprites, the way the references draw them.
///
/// `scripts/forge/foliage/trees.py` writes the sprites at the sprite's own
/// density (52 texels/m, Law 2) into `assets/foliage/`. A plant here is two
/// quads sharing one material: one faces the camera -- the yaw is locked, so
/// it never needs to turn -- tilted back by the camera's pitch about its foot,
/// as the character's quad is; the other is turned to face the SUN and only
/// casts. A camera-facing quad under a side sun is edge-on to the light and
/// would throw a shadow one pixel wide; the sun-facing one throws the tree.
///
/// The visible quad is lit (wrapped diffuse, so a side sun still reaches a
/// quad that faces the camera) but receives NO shadows: its own sun-facing
/// caster crosses it down the middle, and receiving would put half of every
/// canopy in that caster's shadow behind a hard vertical line (seen
/// 2026-09-23). The price: a tree does not darken inside a house's shadow.
/// </summary>
public static class Foliage
{
    private const string Dir = "res://assets/foliage/";

    /// <summary>The camera's pitch the quads lean back by: the bake angle.</summary>
    public const float TiltDeg = 8f;

    private static Godot.Collections.Dictionary? _manifest;
    private static bool _tracked;
    private static Vector3 _lastP;
    private static float _speed;

    /// <summary>Where the player stands, for the see-through fade in the
    /// shader, and how fast they move, for the brush-past rustle. Call once a
    /// frame with the interpolated position.</summary>
    public static void Track(Vector3 player, float dt)
    {
        Register();
        RenderingServer.GlobalShaderParameterSet("player_pos", player);
        var v = dt > 0f ? new Vector2(player.X - _lastP.X, player.Z - _lastP.Z).Length() / dt : 0f;
        _lastP = player;
        _speed = Mathf.Lerp(_speed, Mathf.Min(v, 20f), 0.25f);
        RenderingServer.GlobalShaderParameterSet("player_speed", _speed);
    }

    /// <summary>The shader's global uniforms (declared in project.godot
    /// [shader_globals]) at their start values.</summary>
    private static void Register()
    {
        if (_tracked) return;
        _tracked = true;
        RenderingServer.GlobalShaderParameterSet("player_pos", Vector3.Zero);
        RenderingServer.GlobalShaderParameterSet("player_speed", 0f);
    }
    private static readonly Dictionary<string, ShaderMaterial> _mats = new();
    private static Shader? _shader;

    /// <summary>What a village model slot becomes: sprite name prefixes and
    /// offsets in metres (a group is several plants).</summary>
    public static bool Maps(string model, out (string Kind, float Dx, float Dz, float Scale)[] plants)
    {
        plants = model switch
        {
            "tree_large" => new[] { ("oak", 0f, 0f, 1.0f) },
            "tree_small" => new[] { ("birch", 0f, 0f, 0.9f) },
            "tree_group" => new[] { ("oak", -1.8f, 0.6f, 0.95f), ("pine", 1.9f, -0.8f, 1.0f), ("birch", 0.3f, 2.2f, 0.85f) },
            "bush" => new[] { ("bush", 0f, 0f, 1.0f) },
            _ => System.Array.Empty<(string, float, float, float)>(),
        };
        return plants.Length > 0;
    }

    /// <summary>Plant one sprite of `kind` (a variant chosen by position) with
    /// its foot at `foot`.</summary>
    public static Node3D Plant(string kind, Vector3 foot, float scale, float sunYawDeg)
    {
        _manifest ??= (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString(Dir + "manifest.json"));
        var sprites = (Godot.Collections.Dictionary)_manifest["sprites"];
        var variants = new List<string>();
        foreach (var k in sprites.Keys)
            if (((string)k).StartsWith(kind + "_")) variants.Add((string)k);
        variants.Sort();
        var pick = variants[(int)(Mathf.Abs(Mathf.Sin(foot.X * 12.9898f + foot.Z * 78.233f)) * 43758.5453f) % variants.Count];
        var info = (Godot.Collections.Dictionary)sprites[pick];
        var m = (Godot.Collections.Array)info["metres"];
        var px = (Godot.Collections.Array)info["px"];
        var size = new Vector2((float)m[0], (float)m[1]) * scale;
        var footM = (int)info["foot_px"] / (float)(int)px[1] * size.Y;

        var root = new Node3D { Name = "Plant_" + pick, Position = foot };
        var mat = Material(pick);
        // The quad's own centre sits half its height above the foot line.
        var mesh = new QuadMesh { Size = size, CenterOffset = new Vector3(0f, size.Y / 2f - footM, 0f) };

        var face = new MeshInstance3D
        {
            Name = "Face",
            Mesh = mesh,
            MaterialOverride = mat,
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            RotationDegrees = new Vector3(-TiltDeg, CameraRig.BaseYaw, 0f),
        };
        var caster = new MeshInstance3D
        {
            Name = "Shadow",
            Mesh = mesh,
            MaterialOverride = mat,
            CastShadow = GeometryInstance3D.ShadowCastingSetting.ShadowsOnly,
            // QuadMesh faces +Z; turned by yaw+180 it faces the way the light travels.
            RotationDegrees = new Vector3(0f, sunYawDeg + 180f, 0f),
        };
        root.AddChild(face);
        root.AddChild(caster);
        return root;
    }

    /// <summary>One plant for <see cref="Forest"/>.</summary>
    /// <summary>`Snow`: how much snow this plant carries at full load (the
    /// snow country's weight at its foot; 0 = none). Live load is per
    /// instance in the MultiMesh's custom data (<see cref="Snow"/> sheds and
    /// reloads it).</summary>
    public readonly record struct Spot(string Kind, Vector3 Foot, float Scale, bool Shadow, float Snow = 0f);

    /// <summary>Many plants, batched: every sprite variant becomes ONE
    /// MultiMesh of camera-facing quads and one of sun-facing casters, so a
    /// few hundred trees cost a few dozen draw calls, not a few hundred.
    /// The variant is still chosen per plant by its position.</summary>
    public static void Forest(Node3D parent, IEnumerable<Spot> spots, float sunYawDeg,
                              List<(MultiMesh Mm, int I, Spot Sp)>? faces = null)
    {
        _manifest ??= (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString(Dir + "manifest.json"));
        var sprites = (Godot.Collections.Dictionary)_manifest["sprites"];
        var byVariant = new Dictionary<string, List<Spot>>();
        foreach (var sp in spots)
        {
            var variants = new List<string>();
            foreach (var k in sprites.Keys)
                if (((string)k).StartsWith(sp.Kind + "_")) variants.Add((string)k);
            variants.Sort();
            var pick = variants[(int)(Mathf.Abs(Mathf.Sin(sp.Foot.X * 12.9898f + sp.Foot.Z * 78.233f)) * 43758.5453f) % variants.Count];
            if (!byVariant.TryGetValue(pick, out var list)) byVariant[pick] = list = new List<Spot>();
            list.Add(sp);
        }
        var face = Basis.FromEuler(new Vector3(Mathf.DegToRad(-TiltDeg), Mathf.DegToRad(CameraRig.BaseYaw), 0f));
        var sun = Basis.FromEuler(new Vector3(0f, Mathf.DegToRad(sunYawDeg + 180f), 0f));
        foreach (var (pick, list) in byVariant)
        {
            var info = (Godot.Collections.Dictionary)sprites[pick];
            var m = (Godot.Collections.Array)info["metres"];
            var px = (Godot.Collections.Array)info["px"];
            var size = new Vector2((float)m[0], (float)m[1]);
            var footM = (int)info["foot_px"] / (float)(int)px[1] * size.Y;
            var quad = new QuadMesh { Size = size, CenterOffset = new Vector3(0f, size.Y / 2f - footM, 0f) };
            var mat = Material(pick);
            var casters = list.FindAll(sp => sp.Shadow);
            var fb = Batch(pick + "_face", quad, mat, list, face, GeometryInstance3D.ShadowCastingSetting.Off);
            parent.AddChild(fb);
            if (faces != null)
                for (var i = 0; i < list.Count; i++) faces.Add((fb.Multimesh, i, list[i]));
            if (casters.Count > 0)
                parent.AddChild(Batch(pick + "_shadow", quad, mat, casters, sun, GeometryInstance3D.ShadowCastingSetting.ShadowsOnly));
        }
    }

    private static MultiMeshInstance3D Batch(string name, Mesh quad, Material mat, List<Spot> spots,
                                             Basis turn, GeometryInstance3D.ShadowCastingSetting cast)
    {
        var mm = new MultiMesh
        {
            TransformFormat = MultiMesh.TransformFormatEnum.Transform3D,
            UseCustomData = true,
            Mesh = quad,
            InstanceCount = spots.Count,
        };
        for (var i = 0; i < spots.Count; i++)
        {
            mm.SetInstanceTransform(i, new Transform3D(turn.Scaled(Vector3.One * spots[i].Scale), spots[i].Foot));
            mm.SetInstanceCustomData(i, new Color(spots[i].Snow, 0f, 0f, 0f));
        }
        return new MultiMeshInstance3D { Name = name, Multimesh = mm, MaterialOverride = mat, CastShadow = cast };
    }

    internal static ShaderMaterial Material(string sprite)
    {
        if (_mats.TryGetValue(sprite, out var m)) return m;
        Register();
        _shader ??= new Shader { Code = Code };
        var img = Image.LoadFromFile(ProjectSettings.GlobalizePath(Dir + sprite + ".png"));
        img.GenerateMipmaps();
        m = new ShaderMaterial { Shader = _shader };
        var tex = ImageTexture.CreateFromImage(img);
        m.SetShaderParameter("tex", tex);
        m.SetShaderParameter("tex_soft", tex);
        // the sprite's box, for deciding in the shader whether it hides the player
        _manifest ??= (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString(Dir + "manifest.json"));
        var info = (Godot.Collections.Dictionary)((Godot.Collections.Dictionary)_manifest["sprites"])[sprite];
        var mt = (Godot.Collections.Array)info["metres"];
        var px = (Godot.Collections.Array)info["px"];
        m.SetShaderParameter("size_m", new Vector2((float)mt[0], (float)mt[1]));
        m.SetShaderParameter("foot_m", (int)info["foot_px"] / (float)(int)px[1] * (float)mt[1]);
        _mats[sprite] = m;
        return m;
    }

    private const string Code = @"
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_disabled, cull_disabled, shadows_disabled;

uniform sampler2D tex : source_color, filter_nearest_mipmap;
uniform sampler2D tex_soft : source_color, filter_linear_mipmap;
uniform vec2 size_m;
uniform float foot_m;
global uniform vec3 player_pos;
global uniform float player_speed; // Foliage.Track, m/s
global uniform float wind;      // Weather: 1 dry, 3 in full rain, gusts on top
global uniform float snow_depth; // Snow.Depth
const int BAYER[16] = { 0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5 };

// occ 1 = this whole plant is in the way: its sprite box covers the player
// on screen and it stands nearer the camera -- drawn blurred and thin.
// gone 1 = it is against the lens -- not drawn at all: even a thin blurred
// layer of a sprite that close veils the whole frame (seen 2026-09-23).
varying flat float occ;
varying flat float gone;
// snow this plant carries now: its load (custom data) x the live depth
varying flat float snowy;

void vertex() {
    // A slow sway, strongest at the crown, still at the foot. Phased by the
    // plant's position so a row of trees never moves in step.
    vec3 org = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
    float up = clamp(1.0 - UV.y, 0.0, 1.0);
    VERTEX.x += sin(TIME * 1.1 * sqrt(wind) + org.x * 0.37 + org.z * 0.21) * 0.05 * wind * up * up;
    // brushed past: a small plant (bush, fern, reed -- not a tree) the player walks
    // through leans away from them and rustles, harder the faster they go
    float scale = length(MODEL_MATRIX[0].xyz);
    float small = 1.0 - smoothstep(1.8, 2.8, size_m.y * scale);
    if (small > 0.0) {
        vec2 rel = org.xz - player_pos.xz;
        float near = (1.0 - smoothstep(0.35, 1.3, length(rel))) * small
                   * (1.0 - smoothstep(1.0, 1.8, abs(org.y - player_pos.y)));
        vec2 side = normalize(MODEL_MATRIX[0].xz);
        float lean = dot(rel, side) >= 0.0 ? 1.0 : -1.0;
        float rustle = sin(TIME * 21.0 + org.x * 3.1 + org.z * 1.7) * clamp(player_speed / 6.0, 0.0, 1.0);
        VERTEX.x += (lean * 0.12 + rustle * 0.05) * near * up / max(scale, 0.01);
    }
    snowy = INSTANCE_CUSTOM.r * smoothstep(0.05, 0.45, snow_depth);

    // Perspective passes only: the sun's shadow pass is orthographic, so a
    // faded tree still casts its whole shadow.
    occ = 0.0;
    gone = 0.0;
    if (PROJECTION_MATRIX[3][3] < 0.5) {
        float s = length(MODEL_MATRIX[0].xyz);
        vec3 c = (VIEW_MATRIX * MODEL_MATRIX * vec4(0.0, size_m.y * 0.5 - foot_m, 0.0, 1.0)).xyz;
        vec3 pv = (VIEW_MATRIX * vec4(player_pos + vec3(0.0, 0.9, 0.0), 1.0)).xyz;
        vec2 pp = pv.xy * (c.z / pv.z);                    // the player carried to the plant's depth
        vec2 gap = abs(pp - c.xy) - size_m * s * vec2(0.4, 0.45);
        float over = smoothstep(1.0, -0.3, max(gap.x, gap.y));
        float nearer = smoothstep(0.5, 2.0, c.z - pv.z);
        occ = over * nearer;
        gone = smoothstep(9.0, 5.0, -c.z);
    }
}

void fragment() {
    vec4 c = texture(tex, UV);
    // Snow lies where there is open air a few texels above: the crown, and
    // every pine tier's shoulder, since each tier stands out past the one
    // above it. Deeper snow, a thicker rim; a dusting speckles the rest.
    // Shaded by the sprite's own painted light, so the lit side stays lit.
    if (snowy > 0.01 && c.a > 0.5) {
        vec2 px = 1.0 / vec2(textureSize(tex, 0));
        float reach = 2.0 + floor(snowy * 5.0);
        float air = 0.0;
        for (int k = 1; k <= 7; k++) {
            float y = UV.y - px.y * float(k);
            float a = y < 0.0 ? 0.0 : textureLod(tex, vec2(UV.x, y), 0.0).a;
            if (float(k) <= reach) air = max(air, step(a, 0.5));
        }
        // a sparse dusting in 2x2-texel clumps, not a per-texel speckle
        vec2 cl = floor(UV / px * 0.5);
        float dust = step(1.0 - snowy * 0.08, fract(sin(dot(cl, vec2(12.9898, 78.233))) * 43758.5453));
        float lum = dot(c.rgb, vec3(0.3, 0.59, 0.11));
        vec3 sn = mix(vec3(0.70, 0.75, 0.86), vec3(0.94, 0.96, 1.0), clamp(lum * 3.5, 0.0, 1.0));
        c.rgb = mix(c.rgb, sn, max(air, dust) * min(1.0, snowy * 1.6));
    }
    if (occ + gone > 0.001) {
        // In the way: blurred (a far mip, linearly filtered) and thinned to a
        // ghost by an ordered dither, so the whole frame stays readable.
        c = mix(c, texture(tex_soft, UV, 3.0 * occ), occ);
        int i = (int(FRAGCOORD.y) % 4) * 4 + int(FRAGCOORD.x) % 4;
        if (c.a * (1.0 - 0.75 * occ) * (1.0 - gone) < (float(BAYER[i]) + 0.5) / 16.0) discard;
        c.a = 1.0;
    }
    ALBEDO = c.rgb;
    ALPHA = c.a;
    ALPHA_SCISSOR_THRESHOLD = 0.5;
    ROUGHNESS = 1.0;
}
";
}
