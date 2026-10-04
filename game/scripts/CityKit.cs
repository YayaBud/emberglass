using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The Emberglass city kit in the game (`scripts/forge/citykit/` ->
/// `assets/models/citykit/city_*.glb`, plus the kit's cottage and townhouse).
///
/// Each asset's surfaces are merged into ONE surface whose vertex colour
/// carries the surface's layer in a texture array holding every texgen map
/// the kit uses (albedo, normal, ORM; flat colours for iron, glass, windows,
/// water). One draw per asset per tile instead of one per surface: a kit
/// building has ~10 surfaces, and draw calls are what sank the old city
/// (C20: 4,898 calls, ~10 FPS).
///
/// The shader ghosts an instance whole -- dithered, never a hole -- when it
/// stands between the camera and the player (the user's occluder rule), and
/// tints each instance a little so repeats of one asset do not read as
/// copies. GLBs load at runtime (GltfDocument), so no Godot import is needed.
/// </summary>
public static class CityKit
{
    public sealed class Asset
    {
        public ArrayMesh Mesh = null!;
        public ArrayMesh? Shadow;
        public ArrayMesh? Extra;
        public ShaderMaterial Mat = null!;
        /// <summary>The extra's own material when it moves (the windmill's
        /// sails turn about their hub); else null and it draws with Mat.</summary>
        public ShaderMaterial? ExtraMat;
        public Aabb Box;
    }

    private static readonly Dictionary<string, Asset> _assets = new();
    private static readonly List<string> _layers = new();
    private static readonly Dictionary<string, ArrayMesh> _pending = new();
    private static Shader? _shader;
    private static Texture2DArray? _alb, _nrm, _orm;
    private static ShaderMaterial? _shadowMat;
    private static Shader? _ghostShader;
    private static readonly Dictionary<string, ShaderMaterial> _ghostMats = new();

    /// <summary>The see-through twin of an asset's material (the shader's GHOST variant,
    /// alpha-blended, no shadow), with every parameter copied from the opaque one.</summary>
    public static ShaderMaterial GhostMat(string kind)
    {
        if (_ghostMats.TryGetValue(kind, out var g)) return g;
        _ghostShader ??= new Shader { Code = Grade.Filter(Code).Replace("shader_type spatial;", "shader_type spatial;\n#define GHOST") };
        var src = Get(kind).Mat;
        g = new ShaderMaterial { Shader = _ghostShader };
        foreach (var u in src.Shader.GetShaderUniformList())
        {
            var name = (string)((Godot.Collections.Dictionary)u)["name"];
            g.SetShaderParameter(name, src.GetShaderParameter(name));
        }
        g.SetShaderParameter("ghost", false);
        // a depth-only pass first, so only the ghost's nearest surface is drawn see-through:
        // without it every inner wall and floor showed through at once, stacked like glass
        _ghostDepth ??= new Shader { Code = @"shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_always, cull_back, shadows_disabled;
void fragment() { ALBEDO = vec3(0.0); ALPHA = 0.0; }
" };
        var depth = new ShaderMaterial { Shader = _ghostDepth, NextPass = g, RenderPriority = -1 };
        _ghostMats[kind] = depth;
        return depth;
    }

    private static Shader? _ghostDepth;

    private static readonly Dictionary<string, (Color Albedo, float Rough, float Metal)> Flat = new()
    {
        ["iron"] = (new Color(0.13f, 0.13f, 0.14f), 0.45f, 0.6f),
        ["glass"] = (new Color(0.10f, 0.12f, 0.16f), 0.15f, 0f),
        ["M_Window_Dim"] = (new Color(0.95f, 0.62f, 0.32f), 0.4f, 0f),
        ["M_Window_Warm"] = (new Color(1.0f, 0.70f, 0.38f), 0.4f, 0f),
        ["M_Lamp"] = (new Color(1.0f, 0.70f, 0.38f), 0.4f, 0f),
        ["water"] = (new Color(0.46f, 0.62f, 0.70f), 0.08f, 0f),
        ["foam"] = (new Color(0.85f, 0.90f, 0.92f), 0.6f, 0f),
        ["royal"] = (new Color(0.10f, 0.17f, 0.42f), 0.75f, 0f),   // the market king's cape and shield (2026-09-30)
        // painted shutters, doors and the small stalls' canopies (2026-09-30, "city life" plan)
        ["paint_teal"] = (new Color(0.24f, 0.47f, 0.50f), 0.8f, 0f),
        ["paint_green"] = (new Color(0.30f, 0.44f, 0.27f), 0.8f, 0f),
        ["paint_blue"] = (new Color(0.25f, 0.35f, 0.58f), 0.8f, 0f),
        ["paint_oxblood"] = (new Color(0.50f, 0.18f, 0.15f), 0.8f, 0f),
    };

    private static string Path(string kind) => kind is "townhouse" or "cottage"
        ? $"res://assets/models/kit/kit_{kind}.glb" : $"res://assets/models/citykit/city_{kind}.glb";

    private static int Layer(string name)
    {
        if (!TexLib.Has(name) && !Flat.ContainsKey(name)) name = "planks";
        var i = _layers.IndexOf(name);
        if (i >= 0) return i;
        _layers.Add(name);
        return _layers.Count - 1;
    }

    /// <summary>Load every asset named, then build the texture arrays and
    /// one material per asset. Call once, before <see cref="Get"/>.</summary>
    public static void Load(IEnumerable<string> kinds, ICollection<string> ghosted)
    {
        var loaded = new List<(string Kind, ArrayMesh Mesh, ArrayMesh? Shadow, ArrayMesh? Extra)>();
        foreach (var kind in kinds)
        {
            if (_assets.ContainsKey(kind)) continue;
            var doc = new GltfDocument();
            var st = new GltfState();
            if (doc.AppendFromFile(ProjectSettings.GlobalizePath(Path(kind)), st) != Error.Ok)
            {
                GD.PrintErr($"citykit: cannot load {kind}");
                continue;
            }
            var root = doc.GenerateScene(st);
            Mesh? vis = null, sh = null, extra = null;
            foreach (var n in root.FindChildren("*", "MeshInstance3D", true, false))
            {
                var mi = (MeshInstance3D)n;
                var nm = mi.Name.ToString();
                if (nm == kind) vis = mi.Mesh;
                else if (nm == "SHADOW_" + kind) sh = mi.Mesh;
                else if (nm.StartsWith("SAILS_")) extra = mi.Mesh;
            }
            root.QueueFree();
            if (vis == null)
            {
                GD.PrintErr($"citykit: {kind} has no mesh named {kind}");
                continue;
            }
            loaded.Add((kind, Merge(vis, true), sh == null ? null : Merge(sh, false), extra == null ? null : Merge(extra, true)));
        }
        _alb ??= Array("albedo");
        _nrm ??= Array("normal");
        _orm ??= Array("orm");
        _shader ??= new Shader { Code = Grade.Filter(Code) };
        _shadowMat ??= new ShaderMaterial { Shader = new Shader { Code = "shader_type spatial;\nrender_mode unshaded;\nvoid fragment() { ALBEDO = vec3(0.3); }\n" } };
        foreach (var (kind, mesh, sh, extra) in loaded)
        {
            var m = new ShaderMaterial { Shader = _shader };
            m.SetShaderParameter("alb", _alb);
            m.SetShaderParameter("nrm", _nrm);
            m.SetShaderParameter("orm", _orm);
            var box = mesh.GetAabb();
            m.SetShaderParameter("box_lo", box.Position);
            m.SetShaderParameter("box_hi", box.End);
            m.SetShaderParameter("glow_dim", (float)_layers.IndexOf("M_Window_Dim"));
            m.SetShaderParameter("glow_warm", (float)_layers.IndexOf("M_Window_Warm"));
            m.SetShaderParameter("glow_lamp", (float)_layers.IndexOf("M_Lamp"));
            m.SetShaderParameter("water_layer", (float)_layers.IndexOf("water"));
            m.SetShaderParameter("plaster_layer", (float)_layers.IndexOf("plaster"));
            // the broad trees only: tree_slim is a conifer since 2026-09-30 and read as a yellow larch
            if (kind is "tree_broad") m.SetShaderParameter("autumn_layer", (float)_layers.IndexOf("moss"));
            m.SetShaderParameter("lamps", Grade.L.Lamps);
            // (2026-09-30) the shader's own dither ghost -- a 4x4 screen-door that read as
            // "haze" at 720p upscaled -- is off; CitySite.Ghosts draws occluders see-through
            m.SetShaderParameter("ghost", false);
            // cloth in the wind: a banner hangs from its rod (5.0 m), laundry
            // from its line (2.3 m), a flag streams from its pole
            var (sway, top) = kind switch { "banner" => (1, 5.0f), "clothesline" => (1, 2.3f), "flag" => (2, 0f), _ => (0, 0f) };
            if (sway > 0)
            {
                m.SetShaderParameter("sway_mode", sway);
                m.SetShaderParameter("sway_top", top);
                m.SetShaderParameter("cloth_layers", new Vector3(_layers.IndexOf("cloth_red"), _layers.IndexOf("cloth_blue"), _layers.IndexOf("cloth_cream")));
            }
            if (kind == "waterfall") m.SetShaderParameter("falls", 1f);
            ShaderMaterial? em = null;
            if (kind == "windmill" && extra != null)
            {
                // the sails' hub: Blender (0, -3.7, 11.1) -> (0, 11.1, 3.7); they turn about +Z
                em = (ShaderMaterial)m.Duplicate();
                em.SetShaderParameter("spin_hub", new Vector3(0f, 11.1f, 3.7f));
                em.SetShaderParameter("spin_rate", 0.55f);
            }
            _assets[kind] = new Asset { Mesh = mesh, Shadow = sh, Extra = extra, ExtraMat = em, Mat = m, Box = box };
        }
    }

    public static bool Has(string kind) => _assets.ContainsKey(kind);
    public static Asset Get(string kind) => _assets[kind];
    public static Material ShadowMaterial => _shadowMat!;
    public static int LayerCount => _layers.Count;

    /// <summary>All surfaces into one, each vertex's colour.r = its layer.</summary>
    private static ArrayMesh Merge(Mesh src, bool layered)
    {
        var verts = new List<Vector3>();
        var norms = new List<Vector3>();
        var uvs = new List<Vector2>();
        var cols = new List<Color>();
        var idx = new List<int>();
        for (var s = 0; s < src.GetSurfaceCount(); s++)
        {
            var arr = src.SurfaceGetArrays(s);
            var v = arr[(int)Mesh.ArrayType.Vertex].AsVector3Array();
            var n = arr[(int)Mesh.ArrayType.Normal].VariantType == Variant.Type.Nil ? null : arr[(int)Mesh.ArrayType.Normal].AsVector3Array();
            var uv = arr[(int)Mesh.ArrayType.TexUV].VariantType == Variant.Type.Nil ? null : arr[(int)Mesh.ArrayType.TexUV].AsVector2Array();
            var ind = arr[(int)Mesh.ArrayType.Index].VariantType == Variant.Type.Nil ? null : arr[(int)Mesh.ArrayType.Index].AsInt32Array();
            var name = src.SurfaceGetMaterial(s)?.ResourceName ?? "planks";
            var layer = layered ? Layer(name) : 0;
            var b = verts.Count;
            for (var i = 0; i < v.Length; i++)
            {
                verts.Add(v[i]);
                norms.Add(n != null && i < n.Length ? n[i] : Vector3.Up);
                uvs.Add(uv != null && i < uv.Length ? uv[i] : Vector2.Zero);
                cols.Add(new Color(layer / 255f, 0f, 0f));
            }
            if (ind != null) foreach (var k in ind) idx.Add(b + k);
            else for (var k = 0; k < v.Length; k++) idx.Add(b + k);
        }
        var a = new Godot.Collections.Array();
        a.Resize((int)Mesh.ArrayType.Max);
        a[(int)Mesh.ArrayType.Vertex] = verts.ToArray();
        a[(int)Mesh.ArrayType.Normal] = norms.ToArray();
        a[(int)Mesh.ArrayType.TexUV] = uvs.ToArray();
        a[(int)Mesh.ArrayType.Color] = cols.ToArray();
        a[(int)Mesh.ArrayType.Index] = idx.ToArray();
        var mesh = new ArrayMesh();
        mesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, a);
        return mesh;
    }

    /// <summary>One map of every layer, 512 px square (the texgen tiles are
    /// 504-528; UVs count repeats, so the resize does not move the mapping).</summary>
    private static Texture2DArray Array(string map)
    {
        var imgs = new Godot.Collections.Array<Image>();
        foreach (var name in _layers)
        {
            Image img;
            if (TexLib.Has(name))
            {
                img = Image.LoadFromFile(ProjectSettings.GlobalizePath($"res://assets/tex/{name}_{map}.png"));
                img.Convert(Image.Format.Rgba8);
                img.Resize(512, 512, Image.Interpolation.Nearest);
            }
            else
            {
                var (c, r, m) = Flat[name];
                img = Image.CreateEmpty(512, 512, false, Image.Format.Rgba8);
                img.Fill(map switch { "albedo" => c, "normal" => new Color(0.5f, 0.5f, 1f), _ => new Color(1f, r, m) });
            }
            img.GenerateMipmaps(map == "normal");
            imgs.Add(img);
        }
        var t = new Texture2DArray();
        t.CreateFromImages(imgs);
        return t;
    }

    private const string Code = @"
shader_type spatial;
#ifdef GHOST
render_mode cull_back, blend_mix, depth_draw_never, shadows_disabled;
#else
render_mode cull_back;
#endif
uniform sampler2DArray alb : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray nrm : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray orm : filter_nearest_mipmap_anisotropic, repeat_enable;
uniform vec3 box_lo;
uniform vec3 box_hi;
uniform float glow_dim = -1.0;
uniform float glow_warm = -1.0;
uniform float glow_lamp = -1.0;
// share of windows lit (Weather: all at twilight, ~15 % in the city's afternoon)
global uniform float window_lit;
uniform float water_layer = -1.0;
uniform float plaster_layer = -1.0;
uniform float autumn_layer = -1.0;
uniform float lamps = 1.0;
global uniform float lamp_gain;
// rain in the city (Weather: Damp x CityHere). The region-weighted `wetness`
// is zero inside any region grade, so the kit has its own.
global uniform float city_wet;
uniform bool ghost = true;
global uniform vec3 player_pos;
// cloth in the wind (CityKit.Load): 1 hangs from sway_top, 2 streams from x = 0
uniform int sway_mode = 0;
uniform float sway_top = 0.0;
uniform vec3 cloth_layers = vec3(-1.0);
// a turning part (the windmill's sails): about +Z through spin_hub
uniform vec3 spin_hub = vec3(0.0);
uniform float spin_rate = 0.0;
// the waterfall asset: its water falls in its own space (CityKit.Load)
uniform float falls = 0.0;
varying vec3 lpos;
varying flat float layer;
// the instance's share of lit windows, x window_lit (its quarter's, CitySite)
varying flat float litk;
varying flat float occ;
varying flat float gone;
varying flat vec3 tint;
varying flat float seed;
#ifdef GHOST
// a ghosted occluder (CitySite.Ghosts): see-through and whole, in its own MeshInstance3D,
// so its tint and lit share come from an instance uniform, not INSTANCE_CUSTOM
instance uniform vec4 ghost_custom = vec4(1.0);
uniform float ghost_alpha = 0.3;
#endif
const float BAYER[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

void vertex() {
    layer = floor(COLOR.r * 255.0 + 0.5);
#ifdef GHOST
    tint = ghost_custom.rgb;
#else
    tint = INSTANCE_CUSTOM.rgb;
#endif
    seed = fract(sin(dot(MODEL_MATRIX[3].xz, vec2(12.9898, 78.233))) * 43758.5453);
    lpos = VERTEX;
#ifdef GHOST
    litk = ghost_custom.a;
#else
    litk = INSTANCE_CUSTOM.a;
#endif
    if (sway_mode > 0 && any(lessThan(abs(vec3(layer) - cloth_layers), vec3(0.5)))) {
        float ph = dot(MODEL_MATRIX[3].xz, vec2(0.37, 0.61));
        float reach = sway_mode == 1 ? max(sway_top - VERTEX.y, 0.0) : abs(VERTEX.x);
        float w = sin(TIME * 2.3 + ph + reach * 1.7) * 0.6 + sin(TIME * 3.7 + ph * 1.3 + reach * 2.9) * 0.4;
        VERTEX.z += w * reach * (sway_mode == 1 ? 0.07 : 0.12);
        if (sway_mode == 2) VERTEX.y += w * reach * 0.03;
    }
    if (spin_rate != 0.0) {
        float a = TIME * spin_rate + dot(MODEL_MATRIX[3].xz, vec2(0.13, 0.07));
        float c = cos(a), s = sin(a);
        vec2 d = VERTEX.xy - spin_hub.xy;
        VERTEX.xy = spin_hub.xy + vec2(c * d.x - s * d.y, s * d.x + c * d.y);
        NORMAL.xy = vec2(c * NORMAL.x - s * NORMAL.y, s * NORMAL.x + c * NORMAL.y);
    }
    occ = 0.0;
    gone = 0.0;
    // only instances near the player can stand between it and the camera (26 m back)
    if (ghost && distance(MODEL_MATRIX[3].xyz, player_pos) < 60.0) {
        // into the instance's own space without a matrix inverse: its basis is a
        // rotation times a scale, so each axis is a dot product over its length squared
        vec3 c0 = MODEL_MATRIX[0].xyz, c1 = MODEL_MATRIX[1].xyz, c2 = MODEL_MATRIX[2].xyz;
        vec3 inv_s = 1.0 / vec3(dot(c0, c0), dot(c1, c1), dot(c2, c2));
        vec3 ca = CAMERA_POSITION_WORLD - MODEL_MATRIX[3].xyz;
        vec3 cb = player_pos + vec3(0.0, 0.9, 0.0) - MODEL_MATRIX[3].xyz;
        vec3 a = vec3(dot(ca, c0), dot(ca, c1), dot(ca, c2)) * inv_s;
        vec3 b = vec3(dot(cb, c0), dot(cb, c1), dot(cb, c2)) * inv_s;
        vec3 d = b - a;
        vec3 dd = mix(vec3(1e-5), d, step(vec3(1e-5), abs(d)));
        vec3 t0 = (box_lo - a) / dd;
        vec3 t1 = (box_hi - a) / dd;
        vec3 lo = min(t0, t1);
        vec3 hi = max(t0, t1);
        float enter = max(max(lo.x, lo.y), lo.z);
        float leave = min(min(hi.x, hi.y), hi.z);
        occ = (enter < leave && leave > 0.0 && enter < 0.97) ? 1.0 : 0.0;
        // against the lens: the camera inside or within 4 m of this box -- not drawn at all
        vec3 m = vec3(4.0) * sqrt(inv_s);
        if (all(greaterThan(a, box_lo - m)) && all(lessThan(a, box_hi + m))) gone = 1.0;
    }
}

void fragment() {
    vec3 uvw = vec3(UV, layer);
    vec3 c = texture(alb, uvw).rgb;
    ALBEDO = c * tint;
    // a limewash per house (2026-09-29, 'it is all grey'): cream, rose, ochre,
    // sage, peach -- pastel, so the street reads as lived-in, not poured
    if (abs(layer - plaster_layer) < 0.5)
        ALBEDO *= seed < 0.3 ? vec3(1.0) : seed < 0.48 ? vec3(1.05, 0.92, 0.90)
                : seed < 0.66 ? vec3(1.06, 0.97, 0.80) : seed < 0.82 ? vec3(0.94, 1.01, 0.88) : vec3(1.06, 0.93, 0.84);
    // autumn in the city's trees (2026-09-29; the user's newest references are
    // red and gold): each tree keeps its leaves' shading, recoloured
    // 2026-09-30 (the direction sheet: dark green trees against the orange dusk): 28 %
    if (abs(layer - autumn_layer) < 0.5 && seed > 0.72) {
        float l = dot(c, vec3(0.3, 0.59, 0.11)) / 0.12;
        vec3 leaf = seed < 0.82 ? vec3(0.55, 0.34, 0.06) : seed < 0.92 ? vec3(0.56, 0.19, 0.05) : vec3(0.42, 0.08, 0.05);
        ALBEDO = leaf * l * tint;
    }
    // a damp foot on buildings (not props): darker and greener up the first
    // half metre, so a house stands IN the street, not on it
    if (box_hi.y > 3.0) {
        float foot = 1.0 - smoothstep(-0.1, 0.55, lpos.y);
        ALBEDO *= mix(vec3(1.0), vec3(0.72, 0.77, 0.64), foot * 0.7);
    }
    NORMAL_MAP = texture(nrm, uvw).rgb;
    vec3 o = texture(orm, uvw).rgb;
    AO = o.r;
    AO_LIGHT_AFFECT = 0.5;
    ROUGHNESS = o.g;
    METALLIC = o.b;
    if (abs(layer - glow_dim) < 0.5 || abs(layer - glow_warm) < 0.5) {
        // one lit / unlit draw per window, from its place in the world
        vec3 w = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
        float pick = fract(sin(dot(floor(w * 0.7), vec3(12.9898, 78.233, 37.719))) * 43758.5453);
        float on = step(pick, window_lit * litk);
        // 0.8 / 2.6 -> 0.55 / 1.8 (2026-09-30): under the dusk grade's ACES the windows burned
        // white; the reference sheets' windows are orange
        float k = abs(layer - glow_dim) < 0.5 ? 0.55 : 1.8;
        EMISSION = c * k * lamps * lamp_gain * on;
        ALBEDO = mix(c * vec3(0.16, 0.17, 0.2), ALBEDO, on);
    }
    // lamp glass, lanterns, braziers, the forge: always burning
    // a dark house (CitySite.Dim, litk 0.12) has its lantern out
    if (abs(layer - glow_lamp) < 0.5) EMISSION = c * 2.6 * lamps * lamp_gain * step(0.2, litk);
    // how many screen pixels one rope / streak column spans, for the falls' fade
    float rope_px = fwidth(lpos.x * 9.0);
    float uv_px = fwidth(UV.x * 90.0);
    if (abs(layer - water_layer) < 0.5 && falls > 0.5) {
        // a waterfall (2026-09-24 night: 'falls read as flat panels'): ropes
        // of water of their own width and speed falling in the asset's own
        // height, white churn where it lands and a bright lip where it tips
        float h = clamp((lpos.y - box_lo.y) / max(box_hi.y - box_lo.y, 0.01), 0.0, 1.0);
        // thin ropes (9 per metre) with their own brightness and speed. 2026-09-30
        // (the gate views: 'blocky blue/white stripes'): each rope's value blends into
        // its neighbour's, the dash is a smooth wave (the sawtooth's reset was the hard
        // edge), and the pattern fades to its mean where a rope is under ~2 px
        float fx = lpos.x * 9.0;
        float c0 = floor(fx);
        float r = mix(fract(sin(c0 * 12.9898) * 43758.5453), fract(sin((c0 + 1.0) * 12.9898) * 43758.5453),
                      smoothstep(0.0, 1.0, fract(fx)));
        float wave = 0.5 + 0.5 * sin(6.2832 * (lpos.y * (0.7 + 0.5 * r) + TIME * (1.0 + 0.9 * r) + r * 7.0));
        float rope = pow(wave, 3.0) * (0.25 + 0.55 * r);
        rope = mix(0.12, rope, clamp(1.5 - rope_px, 0.0, 1.0));
        float churn = smoothstep(0.28, 0.0, h) * (0.6 + 0.4 * sin(TIME * 7.0 + lpos.x * 3.0 + lpos.z * 2.0));
        float lip = smoothstep(0.88, 0.98, h);
        vec3 deep = c * vec3(0.55, 0.7, 0.8);
        ALBEDO = mix(deep, vec3(0.94, 0.97, 1.0), clamp(rope * 0.8 + churn + lip * 0.7, 0.0, 1.0));
        ROUGHNESS = 0.2;
        EMISSION = ALBEDO * 0.3;
    }
    else if (abs(layer - water_layer) < 0.5) {
        // falling and running water: streaks sliding down the sheet, foam flecks
        // thin columns, each with its own speed and phase, dashes sliding down v
        float ux = UV.x * 90.0;
        float c0 = floor(ux);
        float r = mix(fract(sin(c0 * 12.9898) * 43758.5453), fract(sin((c0 + 1.0) * 12.9898) * 43758.5453),
                      smoothstep(0.0, 1.0, fract(ux)));
        float s = 0.5 + 0.5 * sin(6.2832 * (UV.y * 5.0 + TIME * (1.8 + 1.4 * r) + r * 7.0));
        float streak = pow(s, 3.0) * (0.35 + 0.65 * r);
        streak = mix(0.12, streak, clamp(1.5 - uv_px, 0.0, 1.0));
        ALBEDO = mix(c * 0.85, vec3(0.93, 0.97, 1.0), streak * 0.75);
        ROUGHNESS = 0.15;
        EMISSION = ALBEDO * 0.22;
    }
    // Wet by exposure (PENDING 'wet walls under eaves', done in the kit's one
    // shader): what faces the sky (roofs, sills, caps, paving on props) soaks
    // fully; walls only in the splash band near their foot, so the wall under
    // an eave stays dry. Darker and glossier.
    if (city_wet > 0.001) {
        vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
        float sky = smoothstep(0.35, 0.8, wn.y);
        float splash = 1.0 - smoothstep(0.3, 1.6, lpos.y - box_lo.y);
        float wet = city_wet * max(sky, 0.6 * splash);
        ALBEDO *= 1.0 - 0.35 * wet;
        ROUGHNESS = mix(ROUGHNESS, 0.22, wet);
    }
    if (gone > 0.5) discard;
    // ghosted whole: about a quarter drawn, dithered -- never a hole
    if (occ > 0.5) {
        int i = int(mod(FRAGCOORD.x, 4.0)) + 4 * int(mod(FRAGCOORD.y, 4.0));
        if ((BAYER[i] + 0.5) / 16.0 > 0.28) discard;
    }
#ifdef GHOST
    ALPHA = ghost_alpha;
#endif
}
";
}
