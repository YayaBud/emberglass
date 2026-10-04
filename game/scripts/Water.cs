using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Still water: the pond and the puddles, one shader for both.
///
/// Reflection is screen-space: the reflected ray is marched through the depth
/// buffer and, where it passes behind something on screen, that pixel is
/// what the water shows. At the locked, low camera almost everything a pond
/// reflects -- the far bank, trees, lamps, animals, the player -- stands above
/// it on screen, which is the case screen-space reflection gets right, and it
/// costs only the water's own pixels. A ray that leaves the top of the frame
/// takes the sky it left through. (A planar mirror camera would render the
/// whole scene, shadow cascades included, a second time.)
///
/// Under the surface: the screen behind, bent by the wave normal, darkened
/// by the depth of water it crosses (red goes first). Where the bed comes up
/// to the surface, broken foam. Waves are sampled on the 52 texels/m grid,
/// so the surface moves in pixels like everything else. Sun and lamp glints
/// come from a sharp specular in `light()`.
///
/// Ripples: a ring buffer of 16 (x, z, start, strength), shared by every
/// water material, fed by <see cref="Ripple"/> (animals, the player) and
/// uploaded once a frame by <see cref="Tick"/>.
/// </summary>
public static class Water
{
    private const int MaxRipples = 32;

    /// <summary>The boat for the wake: (x, z, forward x, forward z), and its
    /// speed in m/s. Set by <see cref="Boat"/> every tick.</summary>
    public static Vector4 Boat;
    public static float BoatSpeed;
    private static readonly Vector4[] _ripples = new Vector4[MaxRipples];
    private static int _next;
    private static float _now, _stepT;
    private static Vector3 _last;
    private static readonly List<ShaderMaterial> _mats = new();
    private static readonly List<(Vector2 C, float R)> _puddles = new();
    private static Shader? _shader;
    private static ShaderMaterial? _pond, _puddle;

    /// <summary>Is there pond water at this spot (set by <see cref="WaterSite"/>).</summary>
    public static bool PondBuilt;

    /// <summary>`--waterdebug`: colour each water pixel by what its
    /// reflection ray did (see the shader's `debug`).</summary>
    public static bool Debug;

    public static void Ripple(Vector2 at, float strength)
    {
        _ripples[_next] = new Vector4(at.X, at.Y, _now, strength);
        _next = (_next + 1) % MaxRipples;
    }

    /// <summary>Once a frame: the clock, the player's own wake, and the
    /// ripple buffer into every water material.</summary>
    public static void Tick(Vector3 player, float dt)
    {
        _now += dt;
        var speed = dt > 0f ? new Vector2(player.X - _last.X, player.Z - _last.Z).Length() / dt : 0f;
        _last = player;
        if (Wet(player))
        {
            _stepT += dt;
            var moving = speed > 0.5f;
            if (_stepT > (moving ? 0.3f : 1.6f))
            {
                Ripple(new Vector2(player.X, player.Z), moving ? 0.8f : 0.2f);
                _stepT = 0f;
            }
        }
        foreach (var m in _mats)
        {
            m.SetShaderParameter("now", _now);
            m.SetShaderParameter("ripples", _ripples);
            m.SetShaderParameter("rain", Weather.Rain);
            m.SetShaderParameter("wet", Weather.Wet);
            m.SetShaderParameter("boat", Boat);
            m.SetShaderParameter("boat_speed", BoatSpeed);
        }
    }

    /// <summary>Standing in water (for the player's soaking, the drag, the ripples): the
    /// pond, or the Fen's standing water. The pond test is only inside its basin -- it
    /// compared ANY ground with the pond's level, so the whole Fen, which lies below it,
    /// was chest-deep pond water and could not be walked into (found 2026-09-28).</summary>
    public static bool Wading(Vector3 p)
    {
        if (Worldbuilder.Boat.Aboard) return false;
        var h = WorldGen.Height(p.X, p.Z);
        // feet above the surface (a boardwalk, a bridge) are dry
        return (PondBuilt && InPond(p) && h < WorldGen.PondLevel && p.Y < WorldGen.PondLevel + 0.1f)
               || (h < WorldGen.FenWaterLevel && p.Y < WorldGen.FenWaterLevel + 0.1f);
    }

    /// <summary>Inside the pond's basin: the carve reaches 2.4 R, its water 1.3 R at most.</summary>
    private static bool InPond(Vector3 p) =>
        new Vector2(p.X - WorldGen.PondCentre.X, p.Z - WorldGen.PondCentre.Y).LengthSquared()
        < WorldGen.PondRadius * WorldGen.PondRadius * 2.56f;

    /// <summary>The feet are in water: the pond, or a puddle while it holds water
    /// (<see cref="Prints"/>: wet prints after).</summary>
    public static bool Underfoot(Vector3 p) => Wet(p);

    /// <summary>Deeper than a wading player's chest.</summary>
    public static bool TooDeep(Vector3 p)
    {
        var h = WorldGen.Height(p.X, p.Z);
        // only for feet down in it: a player on a Fen boardwalk walks over deep water
        return (PondBuilt && InPond(p) && h < WorldGen.PondLevel - 1.1f && p.Y < WorldGen.PondLevel - 0.2f)
               || (h < WorldGen.FenWaterLevel - 1.1f && p.Y < WorldGen.FenWaterLevel - 0.2f);
    }

    private static bool Wet(Vector3 p)
    {
        if (Wading(p)) return true;
        foreach (var (c, r) in _puddles)
            if (new Vector2(p.X - c.X, p.Z - c.Y).Length() < r * Weather.Wet * 0.9f) return true;
        return false;
    }

    private static ShaderMaterial Material(bool puddle)
    {
        _shader ??= new Shader { Code = Code };
        var m = new ShaderMaterial { Shader = _shader };
        m.SetShaderParameter("puddle", puddle ? 1f : 0f);
        if (Debug) m.SetShaderParameter("debug", 1);
        _mats.Add(m);
        return m;
    }

    /// <summary>The pond's surface: a fan following the wobbled shore at 1.2x
    /// its radius -- the level is only guaranteed under the natural ground
    /// out to that ring (<see cref="WorldGen.PondLevel"/>).</summary>
    public static MeshInstance3D Pond()
    {
        var c = WorldGen.PondCentre;
        var y = WorldGen.PondLevel;
        const int n = 72;
        var verts = new List<Vector3>();
        for (var i = 0; i < n; i++)
        {
            float t0 = i / (float)n * Mathf.Tau, t1 = (i + 1) / (float)n * Mathf.Tau;
            float r0 = WorldGen.PondShore(t0) * 1.2f, r1 = WorldGen.PondShore(t1) * 1.2f;
            verts.Add(new Vector3(c.X, y, c.Y));
            verts.Add(new Vector3(c.X + Mathf.Cos(t1) * r1, y, c.Y + Mathf.Sin(t1) * r1));
            verts.Add(new Vector3(c.X + Mathf.Cos(t0) * r0, y, c.Y + Mathf.Sin(t0) * r0));
        }
        PondBuilt = true;
        _pond ??= Material(false);
        return new MeshInstance3D
        {
            Name = "Pond", Mesh = Build(verts, null), MaterialOverride = _pond,
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
    }

    /// <summary>An oasis pool (<see cref="WorldGen.Oases"/>): a flat disc at
    /// `y` out to 1.3r, where the basin is back up to the ground; the terrain
    /// hides it past the shore. The pond's material: its look is all depth
    /// and screen reads, nothing tied to the pond's place.</summary>
    public static MeshInstance3D Pool(Vector2 c, float r, float y)
    {
        const int n = 48;
        var verts = new List<Vector3>();
        for (var i = 0; i < n; i++)
        {
            float t0 = i / (float)n * Mathf.Tau, t1 = (i + 1) / (float)n * Mathf.Tau;
            verts.Add(new Vector3(c.X, y, c.Y));
            verts.Add(new Vector3(c.X + Mathf.Cos(t1) * r * 1.3f, y, c.Y + Mathf.Sin(t1) * r * 1.3f));
            verts.Add(new Vector3(c.X + Mathf.Cos(t0) * r * 1.3f, y, c.Y + Mathf.Sin(t0) * r * 1.3f));
        }
        _pond ??= Material(false);
        return new MeshInstance3D
        {
            Name = "Oasis", Mesh = Build(verts, null), MaterialOverride = _pond,
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
    }

    /// <summary>A puddle `size` metres across at `c`: a small grid laid on
    /// the ground 3.5 cm up (it follows the facets; a flat quad would sink
    /// into one side of a slope). Its outline is cut in the shader.</summary>
    public static MeshInstance3D Puddle(Vector2 c, float nominal)
    {
        // room to grow in rain: the shader's `wet` decides how much shows
        var size = nominal * 1.6f;
        const int n = 6;
        var verts = new List<Vector3>();
        var uvs = new List<Vector2>();
        Vector3 At(int i, int j)
        {
            var x = c.X + (i / (float)n - 0.5f) * size;
            var z = c.Y + (j / (float)n - 0.5f) * size;
            // the highest ground within 0.4 m: the facets fold along diagonals
            // this grid does not share, and a grid laid on the exact heights
            // dipped under a fold and showed as a crescent (2026-09-23)
            var y = WorldGen.Height(x, z);
            foreach (var (ox, oz) in new[] { (0.4f, 0f), (-0.4f, 0f), (0f, 0.4f), (0f, -0.4f) })
                y = Mathf.Max(y, WorldGen.Height(x + ox, z + oz));
            return new Vector3(x, y + 0.03f, z);
        }
        for (var i = 0; i < n; i++)
        for (var j = 0; j < n; j++)
            foreach (var (di, dj) in new[] { (0, 0), (1, 0), (1, 1), (0, 0), (1, 1), (0, 1) })
            {
                verts.Add(At(i + di, j + dj));
                uvs.Add(new Vector2((i + di) / (float)n, (j + dj) / (float)n));
            }
        _puddles.Add((c, size * 0.5f));
        Grass.ClearDisc(c, size * 0.5f, 0.4f);
        _puddle ??= Material(true);
        return new MeshInstance3D
        {
            Name = "Puddle", Mesh = Build(verts, uvs), MaterialOverride = _puddle,
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
    }

    /// <summary>Any water surface given as triangles (the city's streams):
    /// the pond's material, flat normals. With `flow` (a world XZ direction
    /// per vertex) it is running water: waves and foam streaks travel
    /// downstream at ~1.6 m/s.</summary>
    public static MeshInstance3D Sheet(string name, List<Vector3> verts, List<Vector2>? flow = null)
    {
        _pond ??= Material(false);
        if (flow != null && _stream == null)
        {
            _stream = Material(false);
            _stream.SetShaderParameter("stream", 1f);
        }
        return new MeshInstance3D
        {
            Name = name, Mesh = Build(verts, flow), MaterialOverride = flow != null ? _stream! : _pond,
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
    }

    private static ShaderMaterial? _stream;

    private static ArrayMesh Build(List<Vector3> verts, List<Vector2>? uvs)
    {
        var arrays = new Godot.Collections.Array();
        arrays.Resize((int)Mesh.ArrayType.Max);
        arrays[(int)Mesh.ArrayType.Vertex] = verts.ToArray();
        var normals = new Vector3[verts.Count];
        System.Array.Fill(normals, Vector3.Up);
        arrays[(int)Mesh.ArrayType.Normal] = normals;
        if (uvs != null) arrays[(int)Mesh.ArrayType.TexUV] = uvs.ToArray();
        var mesh = new ArrayMesh();
        mesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, arrays);
        return mesh;
    }

    private const string Code = @"
shader_type spatial;
render_mode blend_mix, cull_disabled, depth_draw_opaque, fog_disabled, ambient_light_disabled;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
uniform float puddle = 0.0;
uniform float stream = 0.0;   // running water: UV holds the flow direction (world xz)
uniform float now = 0.0;
uniform float rain = 0.0;   // Weather.Rain: density of rain rings
uniform float wet = 0.6;    // Weather.Wet: how far a puddle has spread (0 = dried out)
uniform vec4 ripples[32];
uniform vec4 boat;          // x, z, forward x, forward z
uniform float boat_speed;
uniform vec3 deep : source_color = vec3(0.025, 0.07, 0.08);
uniform vec3 absorb = vec3(1.2, 0.5, 0.42);
uniform vec3 sky_fallback : source_color = vec3(0.42, 0.40, 0.50);
uniform float glint = 5.0;
uniform float glint_cap = 0.6;   // x light colour: keeps a low sun under the glow's blow-out
uniform int debug = 0;   // --waterdebug: green hit, red too-thick, blue left over sky, magenta ran out
const float TEXELS = 52.0;

// Surface slope (dh/dx, dh/dz) at p: three soft swells and the ripple rings.
// The boat's wake, as a height: the Kelvin V (arms at 19.5 degrees either
// side of the track, tan = 0.354, starting at the beam) and transverse waves
// inside it, wavelength 2 pi v^2 / g, all standing still in the boat's frame
// and dying away over ~15 m behind it.
float wake(vec2 p) {
    if (boat_speed < 0.05) return 0.0;
    vec2 d = p - boat.xy;
    vec2 f = boat.zw;
    float u = -dot(d, f);
    float v = dot(d, vec2(-f.y, f.x));
    if (u < -1.8 || u > 20.0) return 0.0;
    float uu = max(u, 0.0);
    float k = clamp(9.8 / max(boat_speed * boat_speed, 0.3), 2.5, 14.0);
    float arm = abs(v) - uu * 0.354 - 0.62;
    float h = exp(-arm * arm * 5.0) * sin(uu * k * 0.9 - abs(v) * 2.5);
    h += smoothstep(0.3, -0.6, arm) * 0.45 * sin(uu * k);
    // the bow pushes a bump of water ahead and round the hull
    h += exp(-dot(d - f * 1.7, d - f * 1.7) * 3.0) * 0.8;
    return h * min(boat_speed, 2.5) * 0.035 * exp(-uu * 0.15) * smoothstep(-1.8, -0.6, u);
}

float hash2(vec2 c) { return fract(sin(dot(c, vec2(127.1, 311.7))) * 43758.5453); }

// Which 2 cm cells may glint this instant (fragment -> light). A low sun's
// glitter path lit every texel of it at once: one white column the glow
// smeared into a blob over the bank (2026-09-23). Real glitter is sparks.
varying float sparkle;

vec2 slope(vec2 p, vec2 fl) {
    vec2 g = vec2(0.0);
    if (stream > 0.5) {
        // waves travelling downstream (~1.6 m/s), crossed by two oblique trains
        vec2 f = normalize(fl + vec2(1e-4));
        vec2 s = vec2(-f.y, f.x);
        g += f * 0.05 * cos(dot(p, f) * 3.1 - now * 5.0 + sin(dot(p, s) * 1.3) * 1.5);
        vec2 o1 = normalize(f * 0.6 + s * 0.8), o2 = normalize(f * 0.6 - s * 0.8);
        g += o1 * 0.03 * cos(dot(p, o1) * 5.3 - now * 6.5);
        g += o2 * 0.03 * cos(dot(p, o2) * 4.7 - now * 6.0);
    }
    g += vec2(0.8, 0.6) * 0.02 * cos(dot(vec2(0.8, 0.6), p) * 2.1 + now * 1.3);
    g += vec2(-0.5, 0.86) * 0.014 * cos(dot(vec2(-0.5, 0.86), p) * 3.7 + now * 1.9);
    g += vec2(0.3, -0.95) * 0.01 * cos(dot(vec2(0.3, -0.95), p) * 6.3 + now * 2.6);
    g *= 1.0 - 0.85 * puddle;
    for (int i = 0; i < 32; i++) {
        vec4 r = ripples[i];
        if (r.w <= 0.0) continue;
        float age = now - r.z;
        if (age < 0.0 || age > 3.5) continue;
        vec2 d = p - r.xy;
        float dist = length(d);
        float x = dist - age * 1.1;
        float env = exp(-x * x * 3.0) * (1.0 - age / 3.5) * r.w / (1.0 + dist * 1.2);
        g += d / max(dist, 1e-3) * cos(x * 16.0) * 0.35 * env;
    }
    // the boat's wake, by central difference
    if (boat_speed > 0.05) {
        float e = 0.06;
        g += vec2(wake(p + vec2(e, 0.0)) - wake(p - vec2(e, 0.0)),
                  wake(p + vec2(0.0, e)) - wake(p - vec2(0.0, e))) / (2.0 * e);
    }
    // rain: every 0.33 m cell takes a drop now and then (more cells the
    // harder it rains), each a thin ring spreading to ~0.4 m
    if (rain > 0.0) {
        vec2 cell = floor(p * 3.0);
        for (int i = -1; i <= 1; i++)
        for (int j = -1; j <= 1; j++) {
            vec2 c = cell + vec2(float(i), float(j));
            float h = hash2(c);
            if (h > rain * 0.85) continue;
            vec2 ctr = (c + vec2(hash2(c + 7.1), hash2(c + 3.3))) / 3.0;
            float t = fract(now * (0.7 + h * 0.6) + hash2(c + 1.9) * 13.0);
            vec2 d = p - ctr;
            float dist = length(d);
            float x = dist - t * 0.4;
            g += d / max(dist, 1e-3) * cos(x * 70.0) * 0.3 * exp(-x * x * 900.0) * (1.0 - t);
        }
    }
    return g;
}

vec3 view_at(vec2 uv, mat4 inv) {
    vec4 v = inv * vec4(uv * 2.0 - 1.0, texture(depth_tex, uv).r, 1.0);
    return v.xyz / v.w;
}

vec2 to_uv(vec3 q, mat4 proj) {
    vec4 c = proj * vec4(q, 1.0);
    return c.xy / c.w * 0.5 + 0.5;
}

void fragment() {
    vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec2 p = (floor(wp.xz * TEXELS) + 0.5) / TEXELS;

    // a puddle's outline: a noise-wobbled blob with a dark wet rim
    float rim = 0.0;
    if (puddle > 0.5) {
        float nz = sin(wp.x * 3.1 + sin(wp.z * 2.3)) * 0.5 + sin(wp.z * 4.3 + wp.x * 1.7) * 0.5;
        // the mesh is 1.6x the puddle's nominal size; `wet` 0.6 fills the
        // nominal outline, 1.0 the whole mesh, near 0 nothing is left
        float e = length(UV - 0.5) * 2.0 + nz * 0.18 * wet;
        float lim = wet;
        if (e > lim || lim < 0.04) discard;
        rim = smoothstep(lim * 0.72, lim * 0.9, e);
    }

    vec2 g = slope(p, UV);
    sparkle = step(0.6, hash2(floor(p * 26.0) + floor(now * 6.0) * 17.0));
    vec3 n = normalize((VIEW_MATRIX * vec4(normalize(vec3(-g.x, 1.0, -g.y)), 0.0)).xyz);
    vec3 v = normalize(-VERTEX);
    float fres = 0.02 + 0.98 * pow(1.0 - clamp(dot(n, v), 0.0, 1.0), 5.0);

    // under the surface
    vec3 bed = view_at(SCREEN_UV, INV_PROJECTION_MATRIX);
    float thick = max(VERTEX.z - bed.z, 0.0);
    vec2 ruv = SCREEN_UV + g * 0.25 * clamp(thick, 0.0, 1.0) * (1.0 - puddle);
    if (view_at(ruv, INV_PROJECTION_MATRIX).z > VERTEX.z) ruv = SCREEN_UV;
    vec3 under = textureLod(screen_tex, ruv, 0.0).rgb;
    float depth_m = wp.y - (INV_VIEW_MATRIX * vec4(bed, 1.0)).y;
    vec3 trans = exp(-absorb * thick * (1.0 - puddle));
    vec3 body = (under * trans + deep * (1.0 - trans)) * mix(1.0, 0.55, puddle);

    // reflection: march the reflected ray through the depth buffer
    vec3 rd = reflect(-v, n);
    vec3 refl = sky_fallback;
    vec3 pos = VERTEX + n * 0.02;
    float stp = 0.1;
    vec2 last = SCREEN_UV;
    vec3 dbg = vec3(0.3, 0.0, 0.3);
    for (int i = 0; i < 28; i++) {
        vec3 q = pos + rd * stp;
        vec2 uv = to_uv(q, PROJECTION_MATRIX);
        if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) break;
        float sz = view_at(uv, INV_PROJECTION_MATRIX).z;
        last = uv;
        if (q.z < sz) {
            if (sz - q.z < stp * 2.0 + 0.4) {
                vec3 a = pos, b = q;
                for (int j = 0; j < 4; j++) {
                    vec3 m = (a + b) * 0.5;
                    if (m.z < view_at(to_uv(m, PROJECTION_MATRIX), INV_PROJECTION_MATRIX).z) b = m; else a = m;
                }
                vec2 h = to_uv(b, PROJECTION_MATRIX);
                vec2 edge = min(h, 1.0 - h);
                float f = smoothstep(0.0, 0.06, min(edge.x, edge.y));
                refl = mix(sky_fallback, textureLod(screen_tex, h, 0.0).rgb, f);
                dbg = vec3(0.0, 0.3, 0.0);
                last = vec2(-1.0);
                break;
            }
            // Far behind a thin thing (a sprite is a paper quad): the ray
            // passes behind it, so keep going. Taking its colour here stretched
            // every animal on the far bank into a pillar (seen 2026-09-23).
            dbg = vec3(0.3, 0.0, 0.0);
        }
        pos = q;
        stp *= 1.16;
    }
    // left the frame (or ran out) over sky: take the sky it left through
    // left the frame or ran out of steps: take what is on screen where it
    // stopped -- sky, if it went out through the top
    if (last.x >= 0.0) {
        refl = textureLod(screen_tex, last, 0.0).rgb;
        if (view_at(last, INV_PROJECTION_MATRIX).z < -400.0) dbg = vec3(0.0, 0.0, 0.3);
    }

    float k = mix(fres, max(fres, 0.45), puddle) * (1.0 - rim);
    vec3 col = mix(body, refl, k);

    // broken foam where the bed meets the surface
    float speck = step(0.45, fract(sin(dot(floor(p * 26.0), vec2(12.9898, 78.233))) * 43758.5453));
    // A line a pixel or two wide, whatever the slope: a depth threshold
    // (< 7 cm) made a 3-5 m band on the lake's flat shelf, and foam lit only
    // by direct light went navy-black in the bank's shadow (2026-09-23).
    float fw = max(fwidth(depth_m), 1e-4);
    float foam = smoothstep(2.5 * fw, 0.5 * fw, depth_m) * speck * (1.0 - puddle);

    if (stream > 0.5) {
        // foam streaks drawn out along the current, drifting with it
        vec2 f = normalize(UV + vec2(1e-4));
        vec2 s = vec2(-f.y, f.x);
        // sparse, long and soft (first pass: step 0.9 at full strength read as
        // white noise on dark water, walk captures 2026-09-24 night)
        float st = step(0.965, hash2(floor(vec2((dot(p, f) - now * 1.6) * 0.6, dot(p, s) * 5.0))));
        foam = max(foam, st * 0.3);
    }
    ALBEDO = vec3(0.45, 0.5, 0.48) * foam * 0.5;
    EMISSION = mix(col, col * 0.7 + vec3(0.14, 0.14, 0.13), foam);
    NORMAL = n;
    ROUGHNESS = 0.06;
    SPECULAR = 0.5;
    ALPHA = 1.0;
    if (debug == 1) { EMISSION = dbg; ALBEDO = vec3(0.0); }
}

void light() {
    DIFFUSE_LIGHT += clamp(dot(NORMAL, LIGHT), 0.0, 1.0) * ATTENUATION * LIGHT_COLOR / PI;
    vec3 h = normalize(LIGHT + VIEW);
    float s = pow(clamp(dot(NORMAL, h), 0.0, 1.0), 400.0) * glint * ATTENUATION;
    SPECULAR_LIGHT += min(s, glint_cap) * sparkle * LIGHT_COLOR;
}
";
}
