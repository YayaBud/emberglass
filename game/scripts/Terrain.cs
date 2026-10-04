using Godot;

namespace Worldbuilder;

/// <summary>
/// One square of streamed ground: its mesh, its collision and its water.
///
/// A chunk is built entirely from <see cref="WorldGen"/>, which is a pure
/// function of position and seed, so a chunk that unloads and reloads comes
/// back byte-identical. That property is not a nicety — without it the world
/// reshuffles behind you every time you walk a circle, which is instantly
/// noticeable and impossible to un-see once it is.
///
/// The surface is FLAT SHADED: every quad gets its own vertices carrying that
/// quad's own face normal, so no normal is ever averaged across an edge. That
/// is what makes the ground read as faceted rather than as a smooth sheet, and
/// it is why the vertex count is four per quad instead of a shared grid.
///
/// Building a chunk is split into two halves that used to be one method:
/// <see cref="Generate"/> is pure CPU work — no Godot engine call at all — so
/// it can run on a worker thread, and <see cref="Build"/> is the handful of
/// engine calls (mesh upload, collider, node creation) that have to stay on
/// the main thread. <see cref="World"/> runs many <c>Generate</c> calls
/// concurrently and calls <c>Build</c> at most once per frame.
/// </summary>
public partial class Terrain : Node3D
{
    /// <summary>Edge length in world units.</summary>
    public const float Size = 96f;

    /// <summary>Quad size. Smaller is more facets and a linearly larger mesh.</summary>
    public const float Cell = 2.0f;

    public Vector2I Coord;

    /// <summary>Where the build time goes, split. Read by the bench.</summary>
    public static ulong MeshUsec, ColliderUsec;

    /// <summary>Microseconds spent in <see cref="Generate"/>, summed across
    /// every worker thread. Read by the bench to report generation cost per
    /// chunk separately from the main-thread build cost.</summary>
    public static long GenUsec;

    private static StandardMaterial3D? _ground;

    /// <summary>
    /// Shared across every chunk. One material means one pipeline state for the
    /// whole world's ground instead of one per chunk.
    /// </summary>
    private static Material Ground => _groundTex ??= Textured ? MakeTextured()
        : Grade.L.Grain ? (_ground ??= MakeGround()) : MakePlain();
    private static Material? _groundTex;

    /// <summary>The pixel-textured ground (grass, and a cobbled road with dirt
    /// margins) instead of flat vertex colour. On by default with the kit;
    /// `--nokit` turns it off.</summary>
    public static bool Textured = true;

    /// <summary>The textured ground. The road is decided PER PIXEL from the
    /// same segment <see cref="WorldGen.PathDistance"/> measures, snapped to
    /// the 52 texels/m grid so its edge is a crisp pixel boundary like the
    /// sprite's -- the vertex colour is one value per terrain triangle and
    /// would give the road a sawtooth of triangle edges. The grass takes the
    /// vertex colour as a tint relative to its own mean, so biome borders,
    /// rock on slopes and the per-facet jitter all survive. Nothing in the
    /// chunk data changes: `--meshhash` is unaffected.</summary>
    private static ShaderMaterial MakeTextured()
    {
        var m = new ShaderMaterial { Shader = new Shader { Code = Grade.Filter(GroundShader) } };
        // The HD set: 104 texels/m. The ground's foreground sits ~2x closer
        // than the player, where the 52/m tiles showed 3-pixel texels.
        foreach (var (key, surf) in new[] { ("grass", "grass_hd"), ("dirt", "dirt_hd"), ("cob", "cobble_hd") })
        {
            m.SetShaderParameter(key + "_a", TexLib.Map(surf, "albedo"));
            m.SetShaderParameter(key + "_n", TexLib.Map(surf, "normal"));
            m.SetShaderParameter(key + "_o", TexLib.Map(surf, "orm"));
            m.SetShaderParameter(key + "_rep", TexLib.Repeat(surf));
        }
        m.SetShaderParameter("grass_ref", TexLib.MeanLinear("grass_hd"));
        m.SetShaderParameter("path_from", WorldGen.PathFrom);
        m.SetShaderParameter("path_to", WorldGen.PathTo);
        m.SetShaderParameter("path_half", WorldGen.PathHalfWidth);
        m.SetShaderParameter("texels", TexLib.TexelsPerM);
        m.SetShaderParameter("grass_fade", new Vector3(Grass.FadeFrom, Grass.FadeTo, Grass.Enabled ? 0.38f : 0f));
        Trails(m);
        return m;
    }

    private static void Trails(ShaderMaterial m)
    {
        m.SetShaderParameter("trail_segs", WorldGen.Trails);
        m.SetShaderParameter("trail_n", WorldGen.Trails.Length);
        m.SetShaderParameter("ice_pools", WorldGen.IcePools);
        m.SetShaderParameter("ice_count", WorldGen.IcePools.Length);
        foreach (var (key, surf) in new[] { ("snow", "snow_hd"), ("packed", "snow_packed_hd"), ("under", "dirt_hd"),
                                            ("rock", "snowstone_hd"), ("ice", "ice_hd"),
                                            ("sand", "sand_hd"), ("crack", "cracked_hd"), ("drock", "dune_rock_hd") })
        {
            m.SetShaderParameter(key + "_a", TexLib.Map(surf, "albedo"));
            m.SetShaderParameter(key + "_n", TexLib.Map(surf, "normal"));
            m.SetShaderParameter(key + "_rep", TexLib.Repeat(surf));
        }
    }

    /// <summary>The untextured ground: the vertex colour, flat, as the
    /// StandardMaterial it replaces drew it (roughness 0.97, no specular,
    /// darkened 30% by wetness) -- plus the snow, where the vertex alpha says
    /// this is snow country. `wetness` is the global the textured ground
    /// already reads; <see cref="Damp"/> only drives the lighting-study
    /// StandardMaterial now.</summary>
    private static ShaderMaterial MakePlain()
    {
        var m = new ShaderMaterial { Shader = new Shader { Code = Grade.Filter(PlainShader) } };
        Trails(m);
        return m;
    }

    /// <summary>Snow on the ground, shared by both ground shaders.
    ///
    /// Coverage: the live depth (<see cref="Snow.Depth"/>, global
    /// `snow_depth`) x how much this is snow country (vertex alpha) x how flat
    /// the facet is (snow slides off steep ground and leaves rock), against a
    /// clumpy noise threshold -- so a thin fall lies in patches with the
    /// frozen ground between, and a deep one buries everything but the crags.
    /// The old trails (<see cref="WorldGen.Trails"/>) are packed, greyer
    /// snow with two rut lanes, worn through to the ground when the snow is
    /// thin. Live footprints come from the trail map round the player
    /// (`prints`, <see cref="Prints"/>): packed like a trail, and a hollow --
    /// the normal leans into each print, deeper the deeper the snow.
    /// Everything is on the 52 texels/m grid.</summary>
    private const string SnowGlsl = @"
global uniform float snow_depth;
// the prints map round the player (Prints): r pressed in, g wet
global uniform sampler2D prints;
global uniform vec4 prints_rect;    // x0, z0, span m, one texel in uv

vec2 print_uv(vec2 q) { return (q - prints_rect.xy) / prints_rect.z; }
bool print_in(vec2 uv) { return uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0; }
vec2 print_at(vec2 q) { vec2 uv = print_uv(q); return print_in(uv) ? texture(prints, uv).rg : vec2(0.0); }
// the pressed prints' slope, for leaning the normal into each hollow
vec2 print_grad(vec2 q) {
    vec2 uv = print_uv(q);
    if (!print_in(uv)) return vec2(0.0);
    float e = prints_rect.w;
    return vec2(texture(prints, uv + vec2(e, 0.0)).r - texture(prints, uv - vec2(e, 0.0)).r,
                texture(prints, uv + vec2(0.0, e)).r - texture(prints, uv - vec2(0.0, e)).r);
}
uniform vec4 trail_segs[32];
uniform vec4 ice_pools[4];
uniform int ice_count = 0;
uniform int trail_n = 0;
uniform sampler2D snow_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D snow_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D packed_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D packed_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform vec2 snow_rep = vec2(9.85);
uniform vec2 packed_rep = vec2(9.85);
// the ground under the snow, as the snow sheet's tiles
uniform sampler2D under_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D under_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D ice_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D ice_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform vec2 under_rep = vec2(9.85);
uniform vec2 rock_rep = vec2(10.15);
uniform vec2 ice_rep = vec2(9.85);

// The snow's thickness: the whole ground lifts with the depth (0.3 m at
// full), so feet, rock feet and fence posts sink into it. Region weight is
// per facet but changes by <0.01 between neighbours: no visible cracks.
float snow_lift(float region) { return snow_depth * smoothstep(0.02, 0.6, region) * 0.3; }

float s_hash(vec2 p) { return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453); }
float trail_dist(vec2 q) {
    float td = 1e4;
    for (int i = 0; i < trail_n; i++) {
        vec2 a = trail_segs[i].xy;
        vec2 ab = trail_segs[i].zw - a;
        float t = clamp(dot(q - a, ab) / dot(ab, ab), 0.0, 1.0);
        td = min(td, length(q - a - ab * t));
    }
    return td;
}
float s_noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(s_hash(i), s_hash(i + vec2(1.0, 0.0)), f.x),
               mix(s_hash(i + vec2(0.0, 1.0)), s_hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

vec3 smooth_n(vec2 uv2) { return vec3(uv2.x, sqrt(max(0.0, 1.0 - dot(uv2, uv2))), uv2.y); }

// gn: the SMOOTH world normal (UV2): cover and light follow the land, not
// the 2 m facets
float snow_ground(vec2 xz, float region, vec3 gn, inout vec3 alb, inout float rough, inout vec3 nv, inout vec3 nmap, mat4 view) {
    vec2 q = (floor(xz * 52.0) + 0.5) / 52.0;
    float flat_ = smoothstep(0.62, 0.93, gn.y);
    float depth = snow_depth * smoothstep(0.02, 0.6, region);

    // The ground under the snow, as the sheet's tiles: frozen dirt on the
    // level ('snow thin' / 'snow + dirt' where the cover breaks), snowy
    // stone where it steepens ('rocky snow' / 'cliff top'), ice in flat
    // hollows. It was one flat vertex colour.
    float steep = 1.0 - smoothstep(0.45, 0.72, gn.y);
    float land = smoothstep(0.02, 0.5, region);
    // rock at 2.2x the tile's scale (~0.9 m stones), its contrast eased
    // toward mid blue-grey: at 1x across a whole hillside it read as
    // paving, dark stones in white mortar (tour d96, 2026-09-23)
    vec2 rk = xz / (rock_rep * 2.2);
    vec3 rock = mix(texture(rock_a, rk).rgb, vec3(0.38, 0.40, 0.47), 0.35);
    vec3 under = mix(texture(under_a, xz / under_rep).rgb * vec3(0.72, 0.76, 0.86), rock, steep);
    vec3 under_nm = mix(texture(under_n, xz / under_rep).rgb, texture(rock_n, rk).rgb, steep);
    float icy = land * step(0.975, gn.y) * smoothstep(0.64, 0.68, s_noise(q * 0.07 + 31.0));
    // and the placed frozen pools, their shores wobbled
    for (int i = 0; i < ice_count; i++) {
        float e = length((q - ice_pools[i].xy) / ice_pools[i].zw) + (s_noise(q * 0.9) - 0.5) * 0.25;
        icy = max(icy, land * (1.0 - smoothstep(0.88, 1.0, e)));
    }
    under = mix(under, texture(ice_a, xz / ice_rep).rgb, icy);
    under_nm = mix(under_nm, texture(ice_n, xz / ice_rep).rgb, icy);
    alb = mix(alb, under, land);
    nmap = mix(nmap, under_nm, land);
    // (0.15 mirrored the amber sky and the ice's blue never showed)
    rough = mix(rough, 0.35, icy);

    float n = s_noise(q * 0.45) * 0.55 + s_noise(q * 2.2) * 0.3 + s_hash(floor(q * 6.0)) * 0.15;
    float cover = smoothstep(n - 0.03, n + 0.03, depth * (0.25 + 0.95 * flat_) * 1.3);
    // slopes: snow lies in streaks down the fall line (the sheet's slope tile)
    vec2 fall = normalize(gn.xz + vec2(1e-4));
    // (2.4 across read busy on the hills, tour 2026-09-23: wider, fewer)
    float streak = s_noise(vec2(dot(q, vec2(-fall.y, fall.x)) * 1.0, dot(q, fall) * 0.2));
    cover *= mix(1.0, smoothstep(0.35, 0.55, streak + depth * 0.35), smoothstep(0.95, 0.75, gn.y));
    // and on rock faces the streaks still lie: snow down the gullies
    cover = max(cover, smoothstep(0.55, 0.68, streak) * depth * 0.9 * steep);
    // the wind keeps the ice nearly bare
    cover *= 1.0 - icy * 0.85;

    float td = trail_dist(q);
    float edge = 1.2 + (s_noise(q * 0.25) - 0.5) * 0.9 + (s_hash(floor(q * 8.0)) - 0.5) * 0.25;
    float trail = 1.0 - smoothstep(edge - 0.35, edge + 0.15, td);
    float rut = trail * (1.0 - step(0.12, abs(td - 0.5)));

    float foot = print_at(q).r;
    vec2 g = print_grad(q);
    float packed = clamp(max(trail * 0.85 + rut * 0.15, foot), 0.0, 1.0);

    vec3 fresh = texture(snow_a, xz / snow_rep).rgb;
    // trodden, not tarred: the packed tile lightened toward fresh snow, the
    // ground showing through only where the snow is thin
    vec3 trod = mix(texture(packed_a, xz / packed_rep).rgb, fresh, 0.4);
    trod = mix(trod, alb * 1.3, 0.3 * (1.0 - depth));
    trod *= 1.0 - rut * 0.06;
    vec3 sn_n = mix(texture(snow_n, xz / snow_rep).rgb, texture(packed_n, xz / packed_rep).rgb, packed);
    cover *= 1.0 - trail * 0.5 * (1.0 - depth);
    alb = mix(alb, mix(fresh, trod, packed), cover);
    rough = mix(rough, 0.8, cover);
    nmap = mix(nmap, sn_n, cover);
    vec3 tilt = vec3(g.x, 0.0, g.y) * (1.5 + 3.0 * depth) * cover;
    nv = normalize(mix(nv, (view * vec4(gn, 0.0)).xyz, cover));
    nv = normalize(nv + (view * vec4(tilt, 0.0)).xyz);
    return cover;
}
";

    /// <summary>The Ashdunes' ground (Phase 5), where the vertex UV.x says
    /// this is desert: wind-rippled sand, cracked earth in the flat hollows,
    /// strata rock where it steepens (projected so its bands run level round
    /// the slope), caravan trails packed darker with rut lanes. Lit by the
    /// smooth normal on the sand: dunes are smooth, and the 2 m facets banded
    /// white snow the same way they would band sand.</summary>
    private const string DesertGlsl = @"
uniform sampler2D sand_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D crack_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D crack_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D drock_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D drock_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform vec2 sand_rep = vec2(9.85);
uniform vec2 crack_rep = vec2(9.85);
uniform vec2 drock_rep = vec2(9.85);

void desert_ground(vec2 xz, float wy, float region, vec3 gn, inout vec3 alb, inout float rough, inout vec3 nv, inout vec3 nmap, mat4 view) {
    vec2 q = (floor(xz * 52.0) + 0.5) / 52.0;
    float land = smoothstep(0.02, 0.5, region);
    float steep = 1.0 - smoothstep(0.55, 0.8, gn.y);
    vec3 c = texture(sand_a, xz / sand_rep).rgb;
    vec3 cn = texture(sand_n, xz / sand_rep).rgb;
    // rarer and softer than first shipped: at 0.62 and full strength the
    // 0.6 m plates covered whole scene floors (every dell is flat) and read
    // as paving (tour, 2026-09-23); none near the trails
    float td = trail_dist(q);
    float crack = step(0.975, gn.y) * smoothstep(0.7, 0.75, s_noise(q * 0.045 + 7.0)) * smoothstep(6.0, 12.0, td);
    c = mix(c, mix(texture(crack_a, xz / crack_rep).rgb, c, 0.35), crack);
    cn = mix(cn, texture(crack_n, xz / crack_rep).rgb, crack);
    vec2 contour = normalize(vec2(-gn.z, gn.x) + vec2(1e-4));
    vec2 ruv = vec2(dot(xz, contour), -wy) / drock_rep;
    c = mix(c, texture(drock_a, ruv).rgb, steep);
    cn = mix(cn, texture(drock_n, ruv).rgb, steep);
    float edge = 1.4 + (s_noise(q * 0.25) - 0.5) * 0.9;
    float trail = (1.0 - smoothstep(edge - 0.4, edge + 0.2, td)) * (1.0 - steep);
    float rut = trail * (1.0 - step(0.12, abs(td - 0.55)));
    c = mix(c, c * vec3(0.84, 0.79, 0.72), trail * 0.8) * (1.0 - rut * 0.1);
    cn = mix(cn, vec3(0.5, 0.5, 1.0), trail * 0.6);
    // prints pressed into the sand (Prints): darker, their walls leaning the normal. (At
    // 0.16 they were lost in the ripple stripes, physshots 2026-09-28.)
    c *= 1.0 - 0.38 * print_at(q).r * (1.0 - steep);
    vec2 pg = print_grad(q) * (1.0 - steep) * 1.8;
    alb = mix(alb, c, land);
    nmap = mix(nmap, cn, land);
    rough = mix(rough, 0.95, land);
    nv = normalize(mix(nv, (view * vec4(gn, 0.0)).xyz, land * (1.0 - steep)));
    nv = normalize(nv + (view * vec4(vec3(pg.x, 0.0, pg.y) * 2.2 * land, 0.0)).xyz);
}
";

    private const string PlainShader = @"
shader_type spatial;
render_mode specular_disabled;
global uniform float wetness;
varying vec3 wpos;
varying vec3 wn;
" + SnowGlsl + DesertGlsl + @"
void vertex() {
    if (COLOR.a > 0.001) VERTEX.y += snow_lift(COLOR.a);
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    wn = smooth_n(UV2);   // chunks are never rotated
    TANGENT = normalize(vec3(1.0, 0.0, 0.0) - NORMAL * NORMAL.x);
    BINORMAL = normalize(cross(NORMAL, TANGENT));
}

void fragment() {
    vec3 alb = COLOR.rgb * (1.0 - 0.3 * wetness);
    float rough = 0.97;
    vec3 nv = NORMAL;
    vec3 nm = vec3(0.5, 0.5, 1.0);
    if (COLOR.a > 0.001) snow_ground(wpos.xz, COLOR.a, wn, alb, rough, nv, nm, VIEW_MATRIX);
    if (UV.x > 0.001) desert_ground(wpos.xz, wpos.y, UV.x, wn, alb, rough, nv, nm, VIEW_MATRIX);
    NORMAL = nv;
    NORMAL_MAP = nm;
    ALBEDO = alb;
    ROUGHNESS = rough;
}
";

    private const string GroundShader = @"
shader_type spatial;
render_mode specular_disabled;

uniform sampler2D grass_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_o : filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D dirt_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D dirt_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D dirt_o : filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D cob_a : source_color, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D cob_n : hint_normal, filter_nearest_mipmap_anisotropic, repeat_enable;
uniform sampler2D cob_o : filter_nearest_mipmap_anisotropic, repeat_enable;
uniform vec2 grass_rep;
uniform vec2 dirt_rep;
uniform vec2 cob_rep;
uniform vec3 grass_ref;
uniform vec2 path_from;
uniform vec2 path_to;
uniform float path_half;
uniform float texels = 52.0;
// the ground under the grass tufts (Grass): darker where the blades stand, so
// the gaps between tufts read as depth, not bare floor; back to the tile past
// the blades' fade (grass_fade: from, to, strength)
uniform vec3 grass_fade = vec3(40.0, 58.0, 0.0);
global uniform float wetness;   // Weather.Damp

varying vec3 wpos;
varying vec3 wn;
" + SnowGlsl + DesertGlsl + @"

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

void vertex() {
    if (COLOR.a > 0.001) VERTEX.y += snow_lift(COLOR.a);
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    wn = smooth_n(UV2);
    // The tiles are projected on world XZ: u along +X, and image-up (the
    // normal map's +Y, OpenGL style) along -Z.
    TANGENT = normalize(vec3(1.0, 0.0, 0.0) - NORMAL * NORMAL.x);
    BINORMAL = normalize(cross(NORMAL, TANGENT));
}

void fragment() {
    vec2 xz = wpos.xz;
    // texel-snapped position: every edge below falls on the texel grid
    vec2 q = (floor(xz * texels) + 0.5) / texels;
    vec2 ab = path_to - path_from;
    float t = clamp(dot(q - path_from, ab) / dot(ab, ab), 0.0, 1.0);
    float d = length(q - (path_from + ab * t));
    float edge = path_half + (vnoise(q * 0.35) - 0.5) * 1.2;
    float ragged = (hash(floor(q * texels * 0.5)) - 0.5) * 0.22 + (vnoise(q * 2.5) - 0.5) * 0.35;
    float cob = step(d + ragged, edge - 0.75);
    float dirt = step(d + ragged, edge + 0.3) * (1.0 - cob);
    float grass = 1.0 - cob - dirt;

    vec3 tint = clamp(COLOR.rgb / grass_ref, vec3(0.35), vec3(2.2));
    vec3 ga = texture(grass_a, xz / grass_rep).rgb * tint;
    ga *= 1.0 - grass_fade.z * (1.0 - smoothstep(grass_fade.x, grass_fade.y, length(wpos - CAMERA_POSITION_WORLD)));
    vec3 da = texture(dirt_a, xz / dirt_rep).rgb;
    vec3 ca = texture(cob_a, xz / cob_rep).rgb;
    ALBEDO = ga * grass + da * dirt + ca * cob;

    vec3 n = texture(grass_n, xz / grass_rep).rgb * grass
           + texture(dirt_n, xz / dirt_rep).rgb * dirt
           + texture(cob_n, xz / cob_rep).rgb * cob;
    NORMAL_MAP = n;
    vec3 o = texture(grass_o, xz / grass_rep).rgb * grass
           + texture(dirt_o, xz / dirt_rep).rgb * dirt
           + texture(cob_o, xz / cob_rep).rgb * cob;
    AO = o.r;
    AO_LIGHT_AFFECT = 0.35;
    // wet: darker (water fills the pores), glossier -- cobbles most, since
    // stone sheds water and shines; grass least
    float w = wetness * (0.5 + 0.5 * cob + 0.2 * dirt);
    ALBEDO *= 1.0 - 0.38 * w;
    ROUGHNESS = mix(o.g, 0.22, w);
    // the Fen's mud (UV.y, Surface.Mud): the dirt tile gone dark and wet in patches,
    // glossy, and the prints pressed into it
    if (UV.y > 0.001) {
        float m = smoothstep(0.02, 0.6, UV.y);
        float patchy = smoothstep(0.42, 0.62, vnoise(q * 0.3) * 0.7 + vnoise(q * 1.7) * 0.3 + (m - 0.5) * 0.5);
        float k = patchy * m;
        ALBEDO = mix(ALBEDO, texture(dirt_a, xz / dirt_rep).rgb * vec3(0.44, 0.41, 0.36), k);
        ROUGHNESS = mix(ROUGHNESS, 0.3, k);
        NORMAL_MAP = mix(NORMAL_MAP, texture(dirt_n, xz / dirt_rep).rgb, k);
        ALBEDO *= 1.0 - 0.45 * print_at(q).r * k;
    }
    // wet prints (Prints g) on any ground, for a few seconds after water: dark and glossy
    float wetp = print_at(q).g;
    ALBEDO *= 1.0 - 0.5 * wetp;
    ROUGHNESS = mix(ROUGHNESS, 0.12, wetp);
    if (COLOR.a > 0.001) {
        vec3 alb = ALBEDO;
        float rough = ROUGHNESS;
        vec3 nv = NORMAL;
        vec3 nm = NORMAL_MAP;
        float cover = snow_ground(xz, COLOR.a, wn, alb, rough, nv, nm, VIEW_MATRIX);
        ALBEDO = alb;
        ROUGHNESS = rough;
        NORMAL = nv;
        NORMAL_MAP = nm;
        AO = mix(AO, 1.0, cover);
    }
    if (UV.x > 0.001) {
        vec3 alb = ALBEDO;
        float rough = ROUGHNESS;
        vec3 nv = NORMAL;
        vec3 nm = NORMAL_MAP;
        desert_ground(xz, wpos.y, UV.x, wn, alb, rough, nv, nm, VIEW_MATRIX);
        float land = smoothstep(0.02, 0.5, UV.x);
        ALBEDO = alb;
        ROUGHNESS = rough;
        NORMAL = nv;
        NORMAL_MAP = nm;
        AO = mix(AO, 1.0, land);
    }
}
";

    /// <summary>The untextured ground's share of the rain: darker when wet.
    /// (The textured ground reads the `wetness` global itself.)</summary>
    public static void Damp(float w)
    {
        if (_ground == null) return;
        var k = 1f - 0.3f * w;
        _ground.AlbedoColor = new Color(k, k, k);
    }

    private static StandardMaterial3D MakeGround()
    {
        var m = new StandardMaterial3D
        {
            VertexColorUseAsAlbedo = true,
            Roughness = 0.97f,
            Metallic = 0f,
            SpecularMode = BaseMaterial3D.SpecularModeEnum.Disabled,
        };
        if (Grade.L.Grain) Grade.Grain(m);   // lighting study only
        return m;
    }

    /// <summary>
    /// A chunk's CPU-side geometry: parallel arrays, one entry per vertex,
    /// three vertices per triangle (no shared/indexed vertices — see the flat
    /// shading note on the class). Produced by <see cref="Generate"/> off the
    /// main thread and handed to <see cref="Build"/>.
    /// </summary>
    public sealed class Data
    {
        public required Vector3[] Verts;
        public required Vector3[] Normals;
        public required Color[] Colors;
        /// <summary>Smooth ground normal's (x, z) per vertex -- the facets'
        /// own normals are flat. Snow is lit and laid by it: under white
        /// snow the 2 m facets each lit differently read as big light/dark
        /// bands (user, 2026-09-23: "different chunks of tiles").</summary>
        public required Vector2[] Smooth;
        /// <summary>Per vertex, x = how much this is desert (the ground
        /// shaders' sand, rock and cracked earth); y = the Fen's mud
        /// (<see cref="Surface.Mud"/>).</summary>
        public required Vector2[] Region;
        public required float Lowest;
    }

    /// <summary>
    /// Generate a chunk's geometry: the height grid, every triangle's
    /// vertices, normals and colours, and the lowest point (for water).
    ///
    /// Pure and thread-safe — it touches nothing but <see cref="WorldGen"/>,
    /// <see cref="Mathf"/> and struct math, no Godot engine API, no node, no
    /// resource — so <see cref="World"/> runs many of these concurrently on
    /// <c>Task.Run</c>. <see cref="WorldGen"/>'s biome-weight scratch is
    /// <c>[ThreadStatic]</c> for exactly this: without it, concurrent calls
    /// would stomp each other's scratch buffer.
    /// </summary>
    public static Data Generate(Vector2I coord)
    {
        var t0 = System.Diagnostics.Stopwatch.GetTimestamp();

        var min = new Vector2(coord.X * Size, coord.Y * Size);
        var n = Mathf.RoundToInt(Size / Cell);

        // The height grid is computed once, (n+1)^2 points, and every quad
        // reads its four corners out of it instead of calling WorldGen.Height
        // again. The old per-quad code called Height 4x per quad — 9,216
        // calls for 2,401 unique grid points — and that redundant evaluation
        // was most of a chunk's cost.
        var h = new float[(n + 1) * (n + 1)];
        for (var j = 0; j <= n; j++)
        for (var i = 0; i <= n; i++)
            h[j * (n + 1) + i] = WorldGen.Height(min.X + i * Cell, min.Y + j * Cell);

        var lowest = float.MaxValue;
        foreach (var v in h) lowest = Mathf.Min(lowest, v);

        // smooth normal per grid point, central differences (one-sided at the
        // chunk edge would seam: sample the heights just outside instead)
        Vector2 SmoothAt(int i, int j)
        {
            float H(int ii, int jj) => ii >= 0 && jj >= 0 && ii <= n && jj <= n
                ? h[jj * (n + 1) + ii]
                : WorldGen.Height(min.X + ii * Cell, min.Y + jj * Cell);
            var nn = new Vector3(-(H(i + 1, j) - H(i - 1, j)), 2f * Cell, -(H(i, j + 1) - H(i, j - 1))).Normalized();
            return new Vector2(nn.X, nn.Z);
        }
        var grid = new Vector2[(n + 1) * (n + 1)];
        for (var j = 0; j <= n; j++)
        for (var i = 0; i <= n; i++)
            grid[j * (n + 1) + i] = SmoothAt(i, j);
        var smooth = new Vector2[n * n * 6];
        var region = new Vector2[n * n * 6];

        var verts = new Vector3[n * n * 6];
        var normals = new Vector3[n * n * 6];
        var colors = new Color[n * n * 6];
        var vi = 0;

        for (var j = 0; j < n; j++)
        for (var i = 0; i < n; i++)
        {
            var x0 = min.X + i * Cell;
            var x1 = min.X + (i + 1) * Cell;
            var z0 = min.Y + j * Cell;
            var z1 = min.Y + (j + 1) * Cell;

            var a = new Vector3(x0, h[j * (n + 1) + i], z0);
            var b = new Vector3(x1, h[j * (n + 1) + i + 1], z0);
            var c = new Vector3(x1, h[(j + 1) * (n + 1) + i + 1], z1);
            var d = new Vector3(x0, h[(j + 1) * (n + 1) + i], z1);
            var sa = grid[j * (n + 1) + i];
            var sb = grid[j * (n + 1) + i + 1];
            var sc = grid[(j + 1) * (n + 1) + i + 1];
            var sd = grid[(j + 1) * (n + 1) + i];

            // The diagonal alternates in a checkerboard. A grid where every
            // quad splits the same way develops a visible corduroy running
            // across the whole world once the light is low.
            if (((i + j) & 1) == 0)
            {
                smooth[vi] = sa; smooth[vi + 1] = sb; smooth[vi + 2] = sc;
                Tri(verts, normals, colors, region, ref vi, a, b, c);
                smooth[vi] = sa; smooth[vi + 1] = sc; smooth[vi + 2] = sd;
                Tri(verts, normals, colors, region, ref vi, a, c, d);
            }
            else
            {
                smooth[vi] = sa; smooth[vi + 1] = sb; smooth[vi + 2] = sd;
                Tri(verts, normals, colors, region, ref vi, a, b, d);
                smooth[vi] = sb; smooth[vi + 1] = sc; smooth[vi + 2] = sd;
                Tri(verts, normals, colors, region, ref vi, b, c, d);
            }
        }

        var t1 = System.Diagnostics.Stopwatch.GetTimestamp();
        var us = (long)((t1 - t0) * 1_000_000.0 / System.Diagnostics.Stopwatch.Frequency);
        System.Threading.Interlocked.Add(ref GenUsec, us);

        return new Data { Verts = verts, Normals = normals, Colors = colors, Smooth = smooth, Region = region, Lowest = lowest };
    }

    /// <summary>
    /// Upload the mesh, build the collider and add any standing water.
    ///
    /// Main thread only — this is the part of building a chunk that has to
    /// touch the engine. Kept to mesh upload, collider construction and node
    /// creation: measured ~0.8 ms mesh + ~2.7 ms collider, against 45 ms for
    /// the whole synchronous build it replaced.
    /// </summary>
    public void Build(Data d)
    {
        var min = new Vector2(Coord.X * Size, Coord.Y * Size);

        var arrays = new Godot.Collections.Array();
        arrays.Resize((int)Mesh.ArrayType.Max);
        arrays[(int)Mesh.ArrayType.Vertex] = d.Verts;
        arrays[(int)Mesh.ArrayType.Normal] = d.Normals;
        arrays[(int)Mesh.ArrayType.Color] = d.Colors;
        arrays[(int)Mesh.ArrayType.TexUV2] = d.Smooth;
        arrays[(int)Mesh.ArrayType.TexUV] = d.Region;

        var mesh = new ArrayMesh();
        var tMesh = Time.GetTicksUsec();
        mesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, arrays);
        MeshUsec += Time.GetTicksUsec() - tMesh;
        mesh.SurfaceSetMaterial(0, Ground);

        AddChild(new MeshInstance3D
        {
            Name = "Ground",
            Mesh = mesh,
            GIMode = GeometryInstance3D.GIModeEnum.Static,
        });

        var body = new StaticBody3D { Name = "Solid" };
        var tCol = Time.GetTicksUsec();
        // ConcavePolygonShape3D.SetFaces builds straight from the CPU-side
        // vertex array. The old CreateTrimeshShape() instead read the mesh
        // back off the GPU (RenderingDevice buffer_get_data), a full GPU
        // stall measured at 5.6 ms per chunk idle and 128 ms with the GPU
        // busy — for data this method already has on the CPU.
        var shape = new ConcavePolygonShape3D();
        shape.SetFaces(d.Verts);
        ColliderUsec += Time.GetTicksUsec() - tCol;
        body.AddChild(new CollisionShape3D { Shape = shape });
        AddChild(body);

        // The Fen's standing water: the pond's shader (reflections, depth colour, ripples,
        // shore foam), not the flat alpha plane it was -- that read as lavender card at the
        // 8 deg camera (physshots 2026-09-28). Wound as the pond's fan is.
        if (d.Lowest <= WorldGen.FenWaterLevel)
        {
            var y = WorldGen.FenWaterLevel;
            Vector3 a = new(min.X, y, min.Y), b = new(min.X + Size, y, min.Y),
                    c = new(min.X + Size, y, min.Y + Size), e = new(min.X, y, min.Y + Size);
            AddChild(Worldbuilder.Water.Sheet("Water", new System.Collections.Generic.List<Vector3> { c, b, a, a, e, c }));
        }
    }

    /// <summary>
    /// One flat-shaded triangle: a single face normal and a single colour
    /// written to all three vertices, appended at index <paramref name="vi"/>.
    ///
    /// The colour is sampled at the CENTROID rather than per vertex. Sampling
    /// per vertex and letting the rasteriser interpolate would smooth the
    /// colour across the facet and undo the faceting the geometry just bought.
    /// </summary>
    private static void Tri(Vector3[] verts, Vector3[] normals, Color[] colors, Vector2[] region, ref int vi,
                             Vector3 p, Vector3 q, Vector3 r)
    {
        // The NORMAL is reversed; the winding is NOT. On the corner order the
        // call sites use, (r-p)x(q-p) points at -Y, so every face was lit from
        // underneath and the world rendered near black. But that ordering is
        // already correct for Godot's front-face test — reversing the vertex
        // order too made every quad back-facing and the ground vanished
        // entirely. Negate one, leave the other.
        var normal = (r - p).Cross(q - p).Normalized();
        var mid = (p + q + r) / 3f;
        var slope = 1f - normal.Y;
        var col = WorldGen.Albedo(mid.X, mid.Z, slope, out var desert, out var fen);
        // y = the Fen's mud (0 everywhere else, so no other chunk's data changes)
        region[vi] = region[vi + 1] = region[vi + 2] = new Vector2(desert, Surface.Mud(fen, mid.Y));

        verts[vi] = p; normals[vi] = normal; colors[vi] = col; vi++;
        verts[vi] = q; normals[vi] = normal; colors[vi] = col; vi++;
        verts[vi] = r; normals[vi] = normal; colors[vi] = col; vi++;
    }
}
