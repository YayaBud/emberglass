using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The Hoarfells asset kit (`scripts/forge/snowkit/snowkit.py` ->
/// `assets/models/snowkit/snowkit.glb`), after the user's snow asset sheet:
/// pines in five sizes and a sparse one, a dead tree, shrubs, rocks and
/// cliffs, an ice overhang, stairs, and the props.
///
/// Every asset is placed through <see cref="Place"/> as MultiMeshes tiled per
/// 20 m (a batch must be spatially small, INVARIANTS), with per-instance
/// custom data r = the snow it carries (region weight x load). The GLB names
/// its materials; each becomes a pixel shader on the 52 texels/m grid:
/// masonry, planks, bark, log rings, iron, ice, berries, needles with blocky
/// snow patches, fronds with snow tips, and snow that sinks into what it sits
/// on as the depth falls (UV2.y metres) and is not drawn once bare. Anything
/// between the camera and the player ghosts whole (ordered dither).
/// </summary>
public static class Kit
{
    // the Hoarfells kit, the Ashdunes kit (`scripts/forge/desertkit/`) and the world kit
    // (`scripts/forge/worldkit/`: breakables, the four new regions); asset names are unique
    // across them
    internal static readonly string[] Glbs =
    {
        "res://assets/models/snowkit/snowkit.glb", "res://assets/models/desertkit/desertkit.glb",
        "res://assets/models/worldkit/worldkit.glb",
    };
    private static Node3D[]? _srcs;
    private static readonly Dictionary<string, (Mesh Mesh, Aabb Box)> _assets = new();
    private static readonly Dictionary<string, Shader> _shaders = new();

    /// <summary>`B`: a full basis (tilt, non-uniform scale) from a baked scene; else Yaw and Scale.</summary>
    public readonly record struct Item(Vector3 Foot, float Yaw, float Scale, float Snow, Basis? B = null);

    /// <summary>Trees shed in gusts and cast; rocks cast and block; props
    /// neither cast nor block and have a shorter visibility range; a landmark
    /// (the castle in the mist) is never range-culled, casts nothing and has
    /// no collider -- it is scenery.</summary>
    public enum Kind { Tree, Rock, Prop, Landmark }

    public static Aabb Box(string asset) => Dressed(asset).Box;

    /// <summary>An asset's mesh with the kit's shaders on it, for batches drawn elsewhere
    /// (<see cref="Breakables"/>).</summary>
    public static Mesh MeshOf(string asset) => Dressed(asset).Mesh;

    /// <summary>Yaw that turns an asset's front (+Z in the game) toward `dir`.</summary>
    public static float Facing(Vector2 dir) => Mathf.Atan2(dir.X, dir.Y);

    /// <summary>Yaw that lays an asset's length (+X) along `dir`.</summary>
    public static float Along(Vector2 dir) => Mathf.Atan2(-dir.Y, dir.X);

    public static int Place(Node3D parent, string asset, List<Item> items, Kind kind, Snow? snow = null)
    {
        items = Bake.KitItems(asset, items, kind);
        if (items.Count == 0) return 0;
        var (mesh, box) = Dressed(asset);
        var tiles = new Dictionary<Vector2I, List<Item>>();
        foreach (var it in items)
        {
            var key = new Vector2I(Mathf.FloorToInt(it.Foot.X / 20f), Mathf.FloorToInt(it.Foot.Z / 20f));
            if (!tiles.TryGetValue(key, out var l)) tiles[key] = l = new List<Item>();
            l.Add(it);
        }
        var body = kind is Kind.Prop or Kind.Landmark ? null : new StaticBody3D { Name = asset + "_Solid" };
        if (body != null) parent.AddChild(body);
        foreach (var (tile, list) in tiles)
        {
            var mm = new MultiMesh
            {
                TransformFormat = MultiMesh.TransformFormatEnum.Transform3D,
                UseCustomData = true,
                Mesh = mesh,
                InstanceCount = list.Count,
            };
            for (var i = 0; i < list.Count; i++)
            {
                var it = list[i];
                // ponytail: the collider box below follows yaw and scale only, not an editor tilt
                var xf = new Transform3D(it.B ?? new Basis(Vector3.Up, it.Yaw).Scaled(Vector3.One * it.Scale), it.Foot);
                mm.SetInstanceTransform(i, xf);
                mm.SetInstanceCustomData(i, new Color(it.Snow, 0f, 0f, 0f));
                if (kind == Kind.Tree)
                    snow?.AddTree(mm, i, it.Foot, it.Snow, box.Size.Y * it.Scale, box.Size.X * it.Scale);
                if (body != null)
                {
                    // trees block at the trunk, rocks by their box
                    var size = kind == Kind.Tree ? new Vector3(0.7f, 2.4f, 0.7f) : box.Size * 0.92f;
                    var centre = kind == Kind.Tree ? new Vector3(0f, 1.2f, 0f) : box.GetCenter();
                    body.AddChild(new CollisionShape3D
                    {
                        Shape = new BoxShape3D { Size = size * it.Scale },
                        Transform = new Transform3D(new Basis(Vector3.Up, it.Yaw), it.Foot + new Basis(Vector3.Up, it.Yaw) * (centre * it.Scale)),
                    });
                }
            }
            parent.AddChild(new MultiMeshInstance3D
            {
                Name = $"{asset}_{tile.X}_{tile.Y}",
                Multimesh = mm,
                CastShadow = kind is Kind.Prop or Kind.Landmark ? GeometryInstance3D.ShadowCastingSetting.Off : GeometryInstance3D.ShadowCastingSetting.On,
                VisibilityRangeEnd = kind switch { Kind.Prop => 70f, Kind.Landmark => 0f, _ => 160f },
            });
        }
        return items.Count;
    }

    private static readonly Dictionary<string, string> _kitOf = new();

    /// <summary>The kit (GLB folder: snowkit, desertkit, worldkit) an asset comes from.</summary>
    internal static string KitOf(string name)
    {
        if (_kitOf.TryGetValue(name, out var k)) return k;
        _srcs ??= System.Array.ConvertAll(Glbs, g => GD.Load<PackedScene>(g).Instantiate<Node3D>());
        k = "";
        for (var i = 0; i < _srcs.Length && k == ""; i++)
            if (_srcs[i].FindChild(name, true, false) != null) k = Glbs[i].GetBaseDir().GetFile();
        return _kitOf[name] = k;
    }

    private static (Mesh Mesh, Aabb Box) Dressed(string name)
    {
        if (_assets.TryGetValue(name, out var a)) return a;
        _srcs ??= System.Array.ConvertAll(Glbs, g => GD.Load<PackedScene>(g).Instantiate<Node3D>());
        MeshInstance3D? mi = null;
        foreach (var src in _srcs)
            if ((mi = src.FindChild(name, true, false) as MeshInstance3D) != null) break;
        if (mi == null) throw new System.ArgumentException($"kit: no asset '{name}'");
        var mesh = (Mesh)mi.Mesh.Duplicate();
        var box = mesh.GetAabb();
        for (var s = 0; s < mesh.GetSurfaceCount(); s++)
            mesh.SurfaceSetMaterial(s, Mat(mesh.SurfaceGetMaterial(s)?.ResourceName ?? "stone", box));
        return _assets[name] = (mesh, box);
    }

    private static readonly Dictionary<string, Color> Albedo = new()
    {
        ["stone"] = new(0.44f, 0.46f, 0.54f), ["wood"] = new(0.42f, 0.27f, 0.16f), ["bark"] = new(0.33f, 0.22f, 0.14f),
        ["logend"] = new(0.66f, 0.50f, 0.32f), ["iron"] = new(0.14f, 0.14f, 0.15f), ["ice"] = new(0.50f, 0.70f, 0.95f),
        ["berry"] = new(0.72f, 0.08f, 0.10f), ["needles"] = new(0.18f, 0.33f, 0.23f), ["rim"] = new(0.11f, 0.21f, 0.15f),
        ["frond"] = new(0.22f, 0.38f, 0.27f), ["snow"] = new(0.86f, 0.90f, 0.96f),
        ["glass"] = new(1.0f, 0.72f, 0.38f), ["slate"] = new(0.22f, 0.24f, 0.30f),
        // the Ashdunes
        ["strata"] = new(0.80f, 0.55f, 0.36f), ["sandstone"] = new(0.80f, 0.64f, 0.44f), ["glyph"] = new(0.78f, 0.60f, 0.40f),
        ["adobe"] = new(0.76f, 0.58f, 0.40f), ["whitewash"] = new(0.90f, 0.86f, 0.78f), ["burlap"] = new(0.60f, 0.48f, 0.32f),
        ["cloth"] = new(0.72f, 0.18f, 0.12f), ["cloth2"] = new(0.16f, 0.34f, 0.56f), ["clay"] = new(0.74f, 0.38f, 0.22f),
        ["palmbark"] = new(0.44f, 0.32f, 0.22f), ["palm"] = new(0.32f, 0.48f, 0.20f), ["deadfrond"] = new(0.56f, 0.42f, 0.26f),
        ["dry"] = new(0.62f, 0.52f, 0.30f), ["cactus"] = new(0.28f, 0.46f, 0.26f), ["bloom"] = new(0.95f, 0.48f, 0.62f),
        ["dates"] = new(0.58f, 0.24f, 0.10f), ["bone"] = new(0.90f, 0.86f, 0.76f), ["rug"] = new(0.62f, 0.15f, 0.12f),
        ["gold"] = new(0.95f, 0.74f, 0.28f), ["fire"] = new(1.0f, 0.5f, 0.12f), ["sand"] = new(0.82f, 0.68f, 0.45f),
        ["shade"] = new(0.07f, 0.05f, 0.04f), ["drum"] = new(0.80f, 0.64f, 0.44f),
        // the world kit
        ["straw"] = new(0.78f, 0.64f, 0.34f), ["thatch"] = new(0.60f, 0.48f, 0.27f),
        ["earth"] = new(0.30f, 0.22f, 0.15f), ["leaf"] = new(0.25f, 0.46f, 0.20f),
    };

    /// <summary>Materials that share another's pixel shader under their own
    /// albedo.</summary>
    private static readonly Dictionary<string, string> Alias = new()
    {
        ["sandstone"] = "stone", ["whitewash"] = "adobe", ["burlap"] = "adobe", ["cloth2"] = "cloth",
        ["deadfrond"] = "palm", ["dry"] = "palm", ["dates"] = "berry", ["bloom"] = "berry",
        // column drums: dressed stone without the block courses (courses on a
        // round drum read as brick, tour 2026-09-23)
        ["drum"] = "adobe",
        // the world kit's lily pads: pixel needles in a pad green
        ["leaf"] = "rim",
    };

    private static ShaderMaterial Mat(string name, Aabb box)
    {
        if (!Albedo.ContainsKey(name)) name = "stone";
        var code = Alias.GetValueOrDefault(name, name);
        if (!_shaders.TryGetValue(code, out var sh))
            _shaders[code] = sh = new Shader
            {
                Code = Head + (code == "snow" ? SnowVert : Vert) + "void fragment() {\n    if (hides(FRAGCOORD.xy, occ, gone)) discard;\n    vec2 q = floor(UV * 52.0);\n"
                       + Frag[code] + "\n}\n",
            };
        var m = new ShaderMaterial { Shader = sh };
        m.SetShaderParameter("albedo", Albedo[name]);
        m.SetShaderParameter("ghost_size", new Vector2(Mathf.Max(box.Size.X, box.Size.Z), box.Size.Y));
        return m;
    }

    private const string Head = @"
shader_type spatial;
render_mode specular_disabled;
global uniform vec3 player_pos;
global uniform float snow_depth;
global uniform float lamp_gain;
uniform vec3 albedo : source_color;
uniform vec2 ghost_size = vec2(2.0, 3.0);
const int BAYER[16] = { 0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5 };
varying flat float occ;
varying flat float gone;
varying flat float amt;
varying vec3 wpos;

float h(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y);
}

// (occ, gone), as the foliage shader does it for sprites: this object covers
// the player on screen and stands nearer the camera; or it is at the lens
vec2 ghost(mat4 model, mat4 view, mat4 proj) {
    vec2 r = vec2(0.0);
    if (proj[3][3] < 0.5) {
        float s = length(model[0].xyz);
        vec3 c = (view * model * vec4(0.0, ghost_size.y * 0.5, 0.0, 1.0)).xyz;
        vec3 pv = (view * vec4(player_pos + vec3(0.0, 0.9, 0.0), 1.0)).xyz;
        vec2 pp = pv.xy * (c.z / pv.z);
        vec2 gap = abs(pp - c.xy) - ghost_size * s * vec2(0.4, 0.45);
        r.x = smoothstep(1.0, -0.3, max(gap.x, gap.y)) * smoothstep(0.5, 2.0, c.z - pv.z);
        r.y = smoothstep(9.0, 5.0, -c.z);
    }
    return r;
}

bool hides(vec2 frag, float o, float gn) {
    if (o + gn <= 0.001) return false;
    int i = (int(frag.y) % 4) * 4 + int(frag.x) % 4;
    return (1.0 - 0.75 * o) * (1.0 - gn) < (float(BAYER[i]) + 0.5) / 16.0;
}

// pixel needles: a few darker and lighter texels, shaded bands like boughs
vec3 needle(vec3 base, vec2 uv) {
    vec2 q = floor(uv * 52.0);
    float n = h(q);
    vec3 c = base * (n < 0.18 ? 0.72 : (n > 0.86 ? 1.32 : 1.0));
    return c * (1.0 - 0.16 * step(0.68, fract(uv.y * 3.5 + h(vec2(floor(q.x / 3.0), 1.0)) * 0.35)));
}

const vec3 SNOW = vec3(0.86, 0.90, 0.96);
";

    private const string Vert = @"
void vertex() {
    vec2 g = ghost(MODEL_MATRIX, VIEW_MATRIX, PROJECTION_MATRIX);
    occ = g.x;
    gone = g.y;
    amt = INSTANCE_CUSTOM.r * smoothstep(0.03, 0.75, snow_depth);
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
";

    // snow sinks into what it sits on as the depth falls (UV2.y metres)
    private const string SnowVert = @"
void vertex() {
    vec2 g = ghost(MODEL_MATRIX, VIEW_MATRIX, PROJECTION_MATRIX);
    occ = g.x;
    gone = g.y;
    amt = INSTANCE_CUSTOM.r * smoothstep(0.03, 0.75, snow_depth);
    VERTEX.y -= UV2.y * (1.0 - clamp(amt * 1.4, 0.0, 1.0));
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
";

    private static readonly Dictionary<string, string> Frag = new()
    {
        // stone: courses 0.3 m, blocks 0.46 m offset per course, dark mortar,
        // a tone per block; faces turned up catch a frost of snow
        ["stone"] = @"
    float row = floor(UV.y / 0.3);
    float x = UV.x + h(vec2(row, 2.0)) * 0.5;
    float col = floor(x / 0.46);
    float gap = max(step(fract(UV.y / 0.3), 0.09), step(fract(x / 0.46), 0.06));
    vec3 c = albedo * (0.8 + 0.34 * h(vec2(row, col))) * (0.9 + 0.2 * h(q));
    c = mix(c, albedo * 0.45, gap);
    vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
    c = mix(c, SNOW, smoothstep(0.6, 0.92, wn.y) * amt * 0.7);
    ALBEDO = c;
    ROUGHNESS = 0.95;",
        // wood: planks across u (0.17 m), grain streaks along v, dark seams
        ["wood"] = @"
    float plank = floor(UV.x / 0.17);
    float seam = step(fract(UV.x / 0.17), 0.08);
    vec3 c = albedo * (0.8 + 0.35 * h(vec2(plank, 1.0))) * (0.86 + 0.26 * h(vec2(q.x, floor(q.y / 6.0))));
    ALBEDO = mix(c, albedo * 0.4, seam);
    ROUGHNESS = 0.95;",
        ["bark"] = @"
    float s = h(vec2(floor(q.x / 2.0), 5.0));
    ALBEDO = albedo * (0.75 + 0.45 * s) * (h(q) < 0.08 ? 0.7 : 1.0);
    ROUGHNESS = 1.0;",
        ["logend"] = @"
    float r = length(UV);
    ALBEDO = albedo * (0.84 + 0.2 * step(0.5, fract(r * 16.0))) * (0.92 + 0.16 * h(q));
    ROUGHNESS = 0.95;",
        ["iron"] = @"
    ALBEDO = albedo * (0.8 + 0.3 * h(q));
    ROUGHNESS = 0.6;",
        // ice: white at the root, deep blue at the tip, lit from within a little
        ["ice"] = @"
    vec3 c = mix(vec3(0.84, 0.93, 1.0), vec3(0.24, 0.5, 0.86), clamp(UV.y, 0.0, 1.0)) * (0.9 + 0.15 * h(vec2(q.x, 0.0)));
    ALBEDO = c;
    EMISSION = c * 0.22;
    ROUGHNESS = 0.15;",
        ["berry"] = @"
    ALBEDO = albedo * (0.8 + 0.3 * h(q));
    EMISSION = albedo * 0.1;
    ROUGHNESS = 0.5;",
        // needles: big snow patches as the sheet paints them -- a smooth
        // field ~0.5 m across cut against a snow line that is heavy at each
        // tier's top and thins down it, the patch edges stepped in 3-texel
        // pixels. (12-texel random blocks read as sparse speckles.)
        ["needles"] = @"
    vec2 cq = floor(q / 3.0);
    float n = vn(cq * 0.115) * 0.8 + h(cq) * 0.2;
    float want = amt * (1.35 - UV2.x * 1.45);
    float sn = step(n, want);
    ALBEDO = mix(needle(albedo, UV), SNOW * (0.94 + 0.06 * h(q)), sn);
    EMISSION = albedo * 0.12 * (1.0 - sn);
    ROUGHNESS = mix(1.0, 0.85, sn);",
        ["rim"] = @"
    ALBEDO = needle(albedo, UV);
    EMISSION = albedo * 0.15;
    ROUGHNESS = 1.0;",
        ["frond"] = @"
    float sn = step(UV2.x, amt * 0.55 + (h(q) - 0.5) * 0.1);
    ALBEDO = mix(needle(albedo, UV), SNOW, sn);
    EMISSION = albedo * 0.12 * (1.0 - sn);
    ROUGHNESS = 1.0;",
        // warm lit panes, a cross of dark muntins every 0.2 m
        ["glass"] = @"
    vec2 f = fract(UV / 0.2);
    float bar = step(0.88, max(f.x, f.y));
    ALBEDO = mix(albedo, albedo * 0.2, bar);
    EMISSION = albedo * 3.2 * (1.0 - bar) * lamp_gain;
    ROUGHNESS = 0.4;",
        // slate cones: courses of shingles, frost on the up-facing faces
        ["slate"] = @"
    float row = floor(UV.y / 0.22);
    float x = UV.x + h(vec2(row, 4.0)) * 0.3;
    float gap = step(fract(UV.y / 0.22), 0.12);
    vec3 c = albedo * (0.8 + 0.3 * h(vec2(row, floor(x / 0.3))));
    c = mix(c, albedo * 0.5, gap);
    vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
    ALBEDO = mix(c, SNOW, smoothstep(0.3, 0.8, wn.y) * amt * 0.6);
    ROUGHNESS = 0.8;",
        ["snow"] = @"
    if (amt < 0.12) discard;
    vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
    ALBEDO = SNOW * (0.94 + 0.06 * h(q)) * (wn.y < -0.2 ? 0.8 : 1.0);
    ROUGHNESS = 0.85;",

        // ---- the Ashdunes
        // natural sandstone: layers ~0.42 m from WORLD height (so every rock
        // and the mesa share them), wobbling, each its own tone, the odd red
        // band, a dark seam under each, short vertical joints; sand dusts the
        // faces turned up
        ["strata"] = @"
    float y = floor((wpos.y + (vn(wpos.xz * 0.35) - 0.5) * 0.5) * 52.0) / 52.0;
    float band = floor(y / 0.42);
    vec3 c = albedo * (0.78 + 0.4 * h(vec2(band, 7.0)));
    c = mix(c, c * vec3(1.08, 0.84, 0.70), step(0.72, h(vec2(band, 9.0))));
    c *= 1.0 - 0.3 * step(fract(y / 0.42), 0.08);
    c *= 1.0 - 0.25 * step(0.96, h(vec2(floor(q.x / 4.0), band)));
    c *= 0.9 + 0.18 * h(q);
    vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
    ALBEDO = mix(c, vec3(0.82, 0.66, 0.44), smoothstep(0.55, 0.9, wn.y) * 0.75);
    ROUGHNESS = 0.95;",
        // cut blocks carved with rows of signs: 0.22 x 0.3 m cells, each a
        // few 3-texel marks, a plain course every 1.2 m
        ["glyph"] = @"
    vec2 cell = floor(UV / vec2(0.22, 0.3));
    vec2 in_c = floor(fract(UV / vec2(0.22, 0.3)) * vec2(11.0, 15.0));
    float inside = step(2.0, in_c.x) * step(in_c.x, 8.0) * step(2.0, in_c.y) * step(in_c.y, 12.0);
    float mark = step(0.55, h(cell * 7.0 + floor(in_c / 3.0))) * inside * step(0.26, fract(UV.y / 1.2));
    vec3 c = albedo * (0.85 + 0.2 * h(vec2(floor(UV.y / 1.2), 3.0))) * (0.92 + 0.14 * h(q));
    c *= 1.0 - 0.35 * step(fract(UV.y / 1.2), 0.03);
    ALBEDO = mix(c, albedo * 0.5, mark);
    ROUGHNESS = 0.95;",
        // plaster: broad soft blotches, a damp band at the foot of the walls,
        // short hairline cracks
        ["adobe"] = @"
    float b = vn(UV * 1.6) * 0.6 + vn(UV * 5.0) * 0.4;
    vec3 c = albedo * (0.86 + 0.24 * b) * (0.94 + 0.1 * h(q));
    vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
    c *= 1.0 - 0.16 * smoothstep(0.6, 0.0, UV.y) * step(abs(wn.y), 0.7);
    c = mix(c, albedo * 0.55, step(0.985, h(vec2(q.x, floor(q.y / 9.0)))));
    ALBEDO = c;
    ROUGHNESS = 1.0;",
        // striped canvas, stripes along u, the underside in its own shade
        ["cloth"] = @"
    float st = mod(floor(UV.x / 0.28), 2.0);
    vec3 c = mix(albedo, vec3(0.88, 0.80, 0.64), st) * (0.88 + 0.16 * vn(UV * 3.0)) * (0.94 + 0.08 * h(q));
    vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
    ALBEDO = c * (wn.y < -0.3 ? 0.75 : 1.0);
    EMISSION = c * 0.06;
    ROUGHNESS = 1.0;",
        // terracotta, two painted bands
        ["clay"] = @"
    float band = step(0.3, UV.y) * step(UV.y, 0.36) + step(0.56, UV.y) * step(UV.y, 0.6);
    vec3 c = albedo * (0.86 + 0.2 * vn(UV * 4.0)) * (0.93 + 0.12 * h(q));
    ALBEDO = mix(c, vec3(0.03, 0.015, 0.01), band);
    ROUGHNESS = 0.9;",
        // palm trunk: a dark ring at each segment's foot, a diagonal weave
        ["palmbark"] = @"
    float ring = step(UV.y, 0.07);
    float dia = step(0.5, fract(UV.x / 0.12 + UV.y * 2.0));
    ALBEDO = albedo * (0.8 + 0.3 * h(vec2(floor(q.x / 3.0), floor(q.y / 4.0)))) * (1.0 - 0.25 * ring) * (0.92 + 0.1 * dia);
    ROUGHNESS = 1.0;",
        // leaves: the blade cut into leaflets away from the midrib (UV2.y),
        // yellowing toward the tip (UV2.x 0)
        ["palm"] = @"
    if (UV2.y > 0.22 && fract(UV.y / 0.09 + UV2.y * 0.7) < 0.42) discard;
    vec3 c = needle(albedo, UV);
    ALBEDO = mix(c, vec3(0.58, 0.50, 0.24), smoothstep(0.35, 0.0, UV2.x) * 0.5);
    EMISSION = albedo * 0.12;
    ROUGHNESS = 1.0;",
        // faceted ribs from the mesh, spines as pale texels
        ["cactus"] = @"
    vec3 c = albedo * (0.85 + 0.25 * h(vec2(q.x, floor(q.y / 5.0))));
    ALBEDO = mix(c, vec3(0.92, 0.88, 0.70), step(0.965, h(q)));
    EMISSION = albedo * 0.08;
    ROUGHNESS = 0.8;",
        ["bone"] = @"
    ALBEDO = albedo * (0.9 + 0.12 * h(q)) * (h(q) < 0.05 ? 0.8 : 1.0);
    ROUGHNESS = 0.8;",
        // a border and a lattice of diamonds about UV 0 (the rug's centre)
        ["rug"] = @"
    vec2 p = abs(UV);
    float d = abs(fract(p.x * 2.2) - 0.5) + abs(fract(p.y * 2.2) - 0.5);
    vec3 c = mix(albedo, vec3(0.86, 0.72, 0.42), step(0.36, d) * step(d, 0.44));
    c = mix(c, vec3(0.015, 0.025, 0.09), clamp(step(1.12, p.x) + step(0.68, p.y), 0.0, 1.0));
    c = mix(c, vec3(0.86, 0.72, 0.42), step(1.2, p.x) * step(p.x, 1.23));
    ALBEDO = c * (0.9 + 0.15 * h(q));
    ROUGHNESS = 1.0;",
        ["gold"] = @"
    ALBEDO = albedo * (0.85 + 0.25 * h(q));
    EMISSION = albedo * 0.25;
    ROUGHNESS = 0.4;",
        // flames: white-yellow at the root to orange at the tips, flickering
        // in 2-texel columns
        ["fire"] = @"
    float f = h(vec2(floor(q.x / 2.0), floor(TIME * 10.0)));
    vec3 c = mix(vec3(1.0, 0.85, 0.35), albedo, clamp(UV.y * 2.0 + f * 0.3, 0.0, 1.0));
    ALBEDO = c;
    EMISSION = c * 3.0 * lamp_gain;
    ROUGHNESS = 1.0;",
        // drifted sand: faint ripples, grains
        ["sand"] = @"
    float rip = step(0.5, fract(UV.x * 3.2 + vn(UV * 2.0) * 1.5));
    ALBEDO = albedo * (0.92 + 0.08 * rip) * (0.95 + 0.08 * h(q)) * (h(q) < 0.04 ? 0.85 : 1.0);
    ROUGHNESS = 1.0;",
        ["shade"] = @"
    ALBEDO = albedo;
    ROUGHNESS = 1.0;",

        // ---- the world kit
        // straw: stalks in 1-texel columns 6 tall, the odd dark stalk, a faint band where
        // the bale was pressed
        ["straw"] = @"
    float st = h(vec2(q.x, floor(q.y / 6.0)));
    vec3 c = albedo * (0.82 + 0.3 * st) * (0.93 + 0.12 * h(q));
    c *= 1.0 - 0.22 * step(0.93, h(vec2(floor(q.x / 2.0), floor(q.y / 9.0) + 3.0)));
    ALBEDO = c;
    ROUGHNESS = 1.0;",
        // thatch: bundles in courses 0.18 m up the slope, strand streaks, a dark line under
        // each course
        ["thatch"] = @"
    float row = floor(UV.y / 0.18);
    vec3 c = albedo * (0.78 + 0.3 * h(vec2(q.x, row))) * (0.92 + 0.12 * h(q));
    c *= 1.0 - 0.3 * step(fract(UV.y / 0.18), 0.12);
    ALBEDO = c;
    ROUGHNESS = 1.0;",
        // earth: soil in soft blotches, turf patches on the faces turned up
        ["earth"] = @"
    float n = vn(UV * 1.8) * 0.6 + vn(UV * 6.0) * 0.4;
    vec3 c = albedo * (0.8 + 0.35 * n) * (0.92 + 0.12 * h(q));
    vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
    c = mix(c, vec3(0.20, 0.32, 0.12), step(0.6, vn(UV * 3.0 + 7.0)) * smoothstep(0.3, 0.8, wn.y));
    ALBEDO = c;
    ROUGHNESS = 1.0;",
    };
}
