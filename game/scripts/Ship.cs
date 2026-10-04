using Godot;

namespace Worldbuilder;

/// <summary>
/// The ancient merchant ship on the lake (model: `scripts/forge/ship/ship.py`
/// -> `assets/models/ship/ship_cargo.glb`): 18 m over its posts, sail set.
/// It lies at anchor by the bow and moves as an anchored ship does: swings
/// slowly round its cable (weathervaning), surges on it, heaves, heels a
/// little to the wind in its sail, rocks when the rowing <see cref="Boat"/>
/// bumps it (<see cref="Contact"/>, <see cref="Bump"/>) and laps ripples off
/// its sides. The sail billows and flaps its foot (a vertex shader).
///
/// Surfaces the game has pixel textures for (`planks`, `timber`,
/// `fieldstone`) take the shared <see cref="TexLib"/> material; the model's
/// `SHADOW_` proxy alone casts (<see cref="Village.Proxy"/>). Local +X is the
/// bow, the origin on the waterline.
/// </summary>
public partial class Ship : AnimatableBody3D
{
    public const float Length = 16f, Beam = 5f, Draft = 1.35f;
    private const float Scope = 9f;   // anchor cable, bow to where it bites

    public static Ship? Current;
    /// <summary>Where it lies on the water (XZ) and which way its bow points.</summary>
    public Vector2 Pos => _pos;
    public Vector2 Axis => _axis;

    private float _level, _yaw0, _t, _rock, _heave, _lapT;
    private Vector2 _anchor, _pos, _axis;
    private MeshInstance3D _cable = null!;

    /// <summary>Half-beam at `lx` metres from amidships (the model's own curve).</summary>
    private static float HalfW(float lx)
    {
        var t = Mathf.Min(Mathf.Abs(lx) / (Length * 0.5f), 1f);
        return Beam * 0.5f * Mathf.Pow(1f - Mathf.Pow(t, 2.4f), 0.55f);
    }

    /// <summary>Lie at `at`, bow toward `yawRad`; the anchor goes down ahead.</summary>
    public void Build(Vector2 at, float yawRad)
    {
        Bake.Spot("ship_cargo", ref at, ref yawRad);
        _level = WorldGen.PondLevel;
        _yaw0 = yawRad;
        var ax = new Vector2(Mathf.Cos(yawRad), -Mathf.Sin(yawRad));
        _anchor = at + ax * (Length * 0.5f + Scope);
        Current = this;
        SyncToPhysics = true;
        PhysicsInterpolationMode = PhysicsInterpolationModeEnum.On;

        var model = GD.Load<PackedScene>("res://assets/models/ship/ship_cargo.glb").Instantiate<Node3D>();
        AddChild(model);
        Dress(model);
        Village.Proxy(model);

        foreach (var (x, len, w) in new[] { (0f, Length * 0.62f, Beam * 0.95f), (5.6f, 3.6f, Beam * 0.6f), (-5.6f, 3.6f, Beam * 0.6f) })
            AddChild(new CollisionShape3D
            {
                Shape = new BoxShape3D { Size = new Vector3(len, 2.9f, w) },
                Position = new Vector3(x, 0.1f, 0f),
            });

        _cable = new MeshInstance3D
        {
            Name = "Cable", TopLevel = true,
            Mesh = new BoxMesh { Size = new Vector3(0.06f, 0.06f, 1f) },
            MaterialOverride = new StandardMaterial3D { AlbedoColor = new Color(0.45f, 0.36f, 0.24f), Roughness = 1f },
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
        AddChild(_cable);
        Place();
    }

    private static ShaderMaterial? _sail;

    /// <summary>Textures by surface name, the sail shader, and a two-sided
    /// shadow proxy (the sail's proxy is a single sheet).</summary>
    internal static void Dress(Node n)
    {
        if (n is MeshInstance3D mi && mi.Mesh != null)
        {
            var shadow = mi.Name.ToString().StartsWith("SHADOW_");
            for (var s = 0; s < mi.Mesh.GetSurfaceCount(); s++)
            {
                var name = mi.Mesh.SurfaceGetMaterial(s)?.ResourceName ?? "";
                if (shadow) mi.SetSurfaceOverrideMaterial(s, new StandardMaterial3D { CullMode = BaseMaterial3D.CullModeEnum.Disabled });
                else if (name == "M_Sail") mi.SetSurfaceOverrideMaterial(s, _sail ??= new ShaderMaterial { Shader = new Shader { Code = SailCode } });
                else if (TexLib.Has(name)) mi.SetSurfaceOverrideMaterial(s, TexLib.Get(name));
            }
        }
        foreach (var c in n.GetChildren()) Dress(c);
    }

    public override void _PhysicsProcess(double delta)
    {
        var dt = (float)delta;
        _t += dt;
        _rock *= Mathf.Exp(-0.8f * dt);
        _heave *= Mathf.Exp(-1.5f * dt);
        Place();

        _lapT -= dt;
        if (_lapT <= 0f)
        {
            _lapT = 0.5f + GD.Randf() * 0.6f;
            var lx = (GD.Randf() - 0.5f) * Length * 0.9f;
            var s = GD.Randf() < 0.5f ? -1f : 1f;
            var side = new Vector2(-_axis.Y, _axis.X);
            Water.Ripple(_pos + _axis * lx + side * s * (HalfW(lx) + 0.15f), 0.15f + GD.Randf() * 0.15f);
        }
        _sail?.SetShaderParameter("gust", 0.5f + 0.3f * Mathf.Sin(_t * 0.21f) + 0.2f * Mathf.Sin(_t * 0.57f + 1f));
    }

    /// <summary>Round its anchor: the ship's heading wanders a few degrees
    /// (slow, because 18 m of hull turns slowly), the hull trails the cable
    /// from the anchor, and the cable stretches and slackens.</summary>
    private void Place()
    {
        var yaw = _yaw0 + 0.06f * Mathf.Sin(_t * 0.045f) + 0.015f * Mathf.Sin(_t * 0.17f + 1f);
        _axis = new Vector2(Mathf.Cos(yaw), -Mathf.Sin(yaw));
        var scope = Scope + 0.25f * Mathf.Sin(_t * 0.12f);
        _pos = _anchor - _axis * (Length * 0.5f + scope);
        var heave = 0.035f * Mathf.Sin(_t * 0.6f) - _heave;
        var heel = 0.02f + 0.008f * Mathf.Sin(_t * 0.21f) + _rock * Mathf.Sin(_t * 2.2f);
        var pitch = 0.006f * Mathf.Sin(_t * 0.45f + 0.7f);
        GlobalTransform = new Transform3D(Basis.FromEuler(new Vector3(heel, yaw, pitch), EulerOrder.Yxz),
                                          new Vector3(_pos.X, _level + heave, _pos.Y));

        // the cable from the bow down to the bed where the anchor holds
        var from = ToGlobal(new Vector3(Length * 0.5f + 0.3f, 1.6f, 0f));
        var to = WorldGen.Snap(_anchor);
        _cable.GlobalTransform = new Transform3D(Basis.Identity, (from + to) * 0.5f)
            .LookingAt(to, Vector3.Up).ScaledLocal(new Vector3(1f, 1f, (to - from).Length()));
    }

    /// <summary>World point `p` against the hull's waterline outline grown by
    /// `margin`: null outside, else the outline's outward normal there.</summary>
    public Vector2? Contact(Vector2 p, float margin = 0.1f)
    {
        var d = p - _pos;
        var side = new Vector2(-_axis.Y, _axis.X);
        float lx = d.Dot(_axis), lz = d.Dot(side);
        if (Mathf.Abs(lx) > Length * 0.5f + margin) return null;
        if (Mathf.Abs(lz) > HalfW(lx) + margin) return null;
        var slope = (HalfW(lx + 0.05f) - HalfW(lx - 0.05f)) / 0.1f;
        var n = new Vector2(-slope, lz < 0f ? -1f : 1f).Normalized();
        return _axis * n.X + side * n.Y;
    }

    /// <summary>Something struck the hull at `at` this hard (m/s). An 18 m
    /// ship barely notices a rowing boat: a small roll, a ripple.</summary>
    public void Bump(Vector2 at, float speed)
    {
        _rock = Mathf.Min(_rock + 0.004f * speed, 0.012f);
        _heave += 0.006f * speed;
        Water.Ripple(at, 0.5f + 0.4f * speed);
    }

    /// <summary>Does a ship at `at`, heading `yawRad`, float clear of the bed
    /// along its whole outline, with room to swing on its cable?</summary>
    public static bool Fits(Vector2 at, float yawRad)
    {
        var ax = new Vector2(Mathf.Cos(yawRad), -Mathf.Sin(yawRad));
        var sd = new Vector2(-ax.Y, ax.X);
        var need = WorldGen.PondLevel - Draft - 0.2f;
        for (var i = -4; i <= 4; i++)
        {
            var lx = i / 4f * (Length * 0.5f + 1.5f);
            for (var j = -1; j <= 1; j++)
            {
                var q = at + ax * lx + sd * (j * (HalfW(lx) + 1.5f));
                if (WorldGen.Height(q.X, q.Y) > need) return false;
            }
        }
        // and the anchor must reach water, not the bank
        var a = at + ax * (Length * 0.5f + Scope);
        return WorldGen.Height(a.X, a.Y) < WorldGen.PondLevel - 0.5f;
    }

    /// <summary>The set sail: canvas with sewn panels, dark brail lines down
    /// it, weathered toward the foot, glowing when the sun is behind it.
    /// UV (0,0) is the yard's port end, v runs down. The yard edge is held;
    /// below it the cloth breathes with the gusts and the foot flaps.
    /// Texels are snapped to the world's 52/m, like every other surface.</summary>
    private const string SailCode = @"
shader_type spatial;
render_mode cull_disabled, shadows_disabled;
uniform float gust = 0.6;
const vec2 SIZE = vec2(12.4, 7.4);   // metres, yard x drop

void vertex() {
    float hold = sin(3.14159 * UV.x);
    float free = UV.y * UV.y;
    float breathe = (gust - 0.6) * 0.9 * hold * sin(1.5708 * UV.y);
    float flap = sin(TIME * 3.1 + UV.x * 9.0) * 0.05 * free + sin(TIME * 1.7 + UV.x * 4.0 + UV.y * 3.0) * 0.06 * UV.y * hold;
    VERTEX.x += breathe + flap;
}

float h(vec2 c) { return fract(sin(dot(c, vec2(127.1, 311.7))) * 43758.5453); }

void fragment() {
    vec2 px = floor(UV * SIZE * 52.0);
    vec2 m = px / 52.0;                       // metres across, metres down
    vec3 canvas = vec3(0.86, 0.82, 0.70);
    // sewn cloths, ~0.6 m wide, each a slightly different bolt
    float cloth = floor(m.x / 0.62);
    canvas *= 0.93 + 0.07 * h(vec2(cloth, 3.0));
    float seam = step(mod(m.x, 0.62), 0.04);
    // brails: dark lines every 1.8 m, with a fairlead ring every 0.9 m down
    float br = step(abs(mod(m.x + 0.9, 1.8) - 0.9), 0.035);
    float ring = br * step(mod(m.y, 0.9), 0.08);
    // weathering: yellowed and grimed toward the foot, a few streaks
    float streak = h(vec2(floor(m.x / 0.25), 7.0));
    canvas = mix(canvas, vec3(0.74, 0.64, 0.46), smoothstep(0.35, 1.0, UV.y) * 0.5 + step(0.82, streak) * 0.12 * UV.y);
    canvas *= 1.0 - 0.06 * h(px);             // cloth tooth
    vec3 col = mix(canvas, canvas * 0.82, seam);
    col = mix(col, vec3(0.28, 0.21, 0.14), max(br * 0.85, ring));
    // a darker band at the foot and at the head (the boltrope)
    col = mix(col, vec3(0.45, 0.36, 0.24), step(0.975, UV.y) + step(UV.y, 0.015));
    ALBEDO = col;
    ROUGHNESS = 0.95;
    SPECULAR = 0.0;
    // Light it mostly by the sail's overall facing (the ship's +X): the mesh
    // is flat-shaded, and the rows under the yard tilt hard into the belly,
    // so their lighting stepped into a hard tan band across the head.
    vec3 fwd = normalize((VIEW_MATRIX * MODEL_MATRIX * vec4(1.0, 0.0, 0.0, 0.0)).xyz);
    // One side for every face: Godot flips NORMAL on the face you see from
    // behind, and the rows under the yard are seen from the other side than
    // the rest -- they took the sky light from the far side and banded.
    NORMAL = normalize(mix(fwd, NORMAL * (FRONT_FACING ? 1.0 : -1.0), 0.25));
}

// Thin canvas passes light: lit the same from either face, and never fully
// dark on the side turned from the sun. With one-sided lambert the columns
// turned away took only the blue sky ambient and streaked (2026-09-23). No
// shadows received: the model's flat SHADOW_ sail cut a hard band across the
// billowed one.
void light() {
    float n = abs(dot(NORMAL, LIGHT));
    DIFFUSE_LIGHT += mix(n, 1.0, 0.4) * ATTENUATION * LIGHT_COLOR / PI;
}
";
}
