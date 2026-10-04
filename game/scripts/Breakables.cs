using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Things a blow breaks (implementation_plan A2): pots, jars, crates, barrels and hay bales
/// from the world kit (`scripts/forge/worldkit/`). The sites set them down while they build
/// (<see cref="Add"/>); <see cref="Build"/> then draws them as <see cref="Kit"/> draws its
/// assets -- one MultiMesh per asset per 20 m tile, the kit's pixel shaders -- each with a box
/// collider, so it stands in the way.
///
/// A swing (<see cref="Hit"/>) breaks what its arc reaches; the dive's shock
/// (<see cref="Smash"/>) breaks everything in its radius. A broken piece's instance shrinks to
/// nothing and its collider switches off; its debris flies as GPU particles that bounce on the
/// rain's height field (so no physics body is ever made), and now and then a coin drops. It
/// comes back after five minutes, once the player is 25 m away.
///
/// Nothing here casts a shadow: small clutter, and the cascades are the bill (memory).
/// </summary>
public partial class Breakables : Node3D
{
    /// <summary>Per asset: half-size of its body (collider and hit test; y up), the debris
    /// colour, how many bits, the chance of a coin.</summary>
    private static readonly Dictionary<string, (Vector3 Half, Color Tone, int Bits, float Coin)> Kinds = new()
    {
        ["Pot"] = (new Vector3(0.3f, 0.32f, 0.3f), new Color(0.74f, 0.38f, 0.22f), 14, 0.35f),
        ["Jar"] = (new Vector3(0.26f, 0.47f, 0.26f), new Color(0.74f, 0.38f, 0.22f), 16, 0.35f),
        ["Crate"] = (new Vector3(0.36f, 0.36f, 0.36f), new Color(0.46f, 0.30f, 0.17f), 16, 0.25f),
        ["Barrel"] = (new Vector3(0.33f, 0.45f, 0.33f), new Color(0.42f, 0.27f, 0.16f), 16, 0.2f),
        ["HayBale"] = (new Vector3(0.55f, 0.23f, 0.28f), new Color(0.80f, 0.66f, 0.36f), 22, 0.1f),
    };

    private sealed class Piece
    {
        public required string Asset;
        public required Vector3 Foot;
        public required float Yaw, Scale, Snow;
        public MultiMesh? Mm;
        public int I;
        public CollisionShape3D? Col;
        /// <summary>Seconds until it stands again; 0 = standing.</summary>
        public float Down;
    }

    private sealed class Coin
    {
        public Vector3 P, V;
        public float Age;
        public bool Landed;
    }

    private const float Cell = 4f;
    private const float Respawn = 300f;
    private const int MaxCoins = 48;

    private static readonly List<Piece> _pieces = new();
    private static readonly Dictionary<Vector2I, List<Piece>> _grid = new();
    private static Breakables? _live;

    /// <summary>Coins picked up (Phase C's HUD shows them), and pieces broken (the harness).</summary>
    public static int Coins, Broken;

    private readonly List<Coin> _coins = new();
    private Node3D _player = null!;
    private GpuParticles3D _bits = null!;
    private MultiMesh _coinMm = null!;
    private float _respawnT;

    public static int Count => _pieces.Count;

    /// <summary>Off under `--light=`: the lighting study's frames must reproduce.</summary>
    public static bool Enabled = true;

    /// <summary>Set one down on the ground at `at`. Call while the sites build: its foot
    /// clears the grass, and that registry closes when streaming starts.</summary>
    public static void Add(string asset, Vector2 at, float yaw, float scale = 1f)
    {
        if (!Enabled || Bake.Breakable(asset, at, yaw, scale)) return;
        if (!Kinds.TryGetValue(asset, out var k)) { GD.PushError($"breakables: no kind '{asset}'"); return; }
        var p = new Piece
        {
            Asset = asset, Foot = new Vector3(at.X, WorldGen.Height(at.X, at.Y), at.Y), Yaw = yaw, Scale = scale,
            // the Hoarfells' pieces carry snow caps (the kit's snow material)
            Snow = Mathf.Max(0f, Biomes.WeightOf(Biome.Snow, at, WorldGen.Seed) - 0.02f),
        };
        _pieces.Add(p);
        var key = new Vector2I(Mathf.FloorToInt(at.X / Cell), Mathf.FloorToInt(at.Y / Cell));
        if (!_grid.TryGetValue(key, out var l)) _grid[key] = l = new List<Piece>();
        l.Add(p);
        Grass.ClearDisc(at, Mathf.Max(k.Half.X, k.Half.Z) * scale * 0.8f, 0.5f);
    }

    /// <summary>Where each piece stands and how wide it is, for the animals to walk round.</summary>
    public static IEnumerable<(Vector2 At, float R)> Footprints()
    {
        foreach (var p in _pieces)
            yield return (new Vector2(p.Foot.X, p.Foot.Z), Mathf.Max(Kinds[p.Asset].Half.X, Kinds[p.Asset].Half.Z) * p.Scale);
    }

    public void Build(Node3D player)
    {
        _live = this;
        _player = player;
        var tiles = new Dictionary<(string, Vector2I), List<Piece>>();
        foreach (var p in _pieces)
        {
            var key = (p.Asset, new Vector2I(Mathf.FloorToInt(p.Foot.X / 20f), Mathf.FloorToInt(p.Foot.Z / 20f)));
            if (!tiles.TryGetValue(key, out var l)) tiles[key] = l = new List<Piece>();
            l.Add(p);
        }
        var body = new StaticBody3D { Name = "Solid" };
        AddChild(body);
        foreach (var ((asset, tile), list) in tiles)
        {
            var mm = new MultiMesh
            {
                TransformFormat = MultiMesh.TransformFormatEnum.Transform3D,
                UseCustomData = true,
                Mesh = Kit.MeshOf(asset),
                InstanceCount = list.Count,
            };
            var half = Kinds[asset].Half;
            for (var i = 0; i < list.Count; i++)
            {
                var p = list[i];
                p.Mm = mm;
                p.I = i;
                mm.SetInstanceTransform(i, Standing(p));
                mm.SetInstanceCustomData(i, new Color(p.Snow, 0f, 0f, 0f));
                p.Col = new CollisionShape3D
                {
                    Shape = new BoxShape3D { Size = half * 2f * p.Scale },
                    Transform = new Transform3D(new Basis(Vector3.Up, p.Yaw), p.Foot + Vector3.Up * half.Y * p.Scale),
                };
                body.AddChild(p.Col);
            }
            AddChild(new MultiMeshInstance3D
            {
                Name = $"{asset}_{tile.X}_{tile.Y}",
                Multimesh = mm,
                CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
                VisibilityRangeEnd = 70f,
            });
        }

        // debris: small blocks in the piece's colour, bouncing on the rain's height field
        // (Weather's RainField follows the player), shrinking away at the end
        var shrink = new Curve();
        shrink.AddPoint(new Vector2(0f, 1f));
        shrink.AddPoint(new Vector2(0.75f, 1f));
        shrink.AddPoint(new Vector2(1f, 0f));
        _bits = new GpuParticles3D
        {
            Name = "Debris",
            Amount = 700,
            Lifetime = 2.4,
            LocalCoords = false,
            Emitting = false,   // EmitParticle only (INVARIANTS: not AmountRatio 0)
            ProcessMaterial = new ParticleProcessMaterial
            {
                Gravity = new Vector3(0f, -16f, 0f),
                Spread = 0f,
                ScaleMin = 0.55f,
                ScaleMax = 1.35f,
                ScaleCurve = new CurveTexture { Curve = shrink },
                CollisionMode = ParticleProcessMaterial.CollisionModeEnum.Rigid,
                CollisionFriction = 0.7f,
                CollisionBounce = 0.25f,
            },
            // 4-5 pixels at 52 texels/m: chunks, not dust
            DrawPass1 = new BoxMesh
            {
                Size = new Vector3(0.09f, 0.07f, 0.08f),
                Material = new StandardMaterial3D { VertexColorUseAsAlbedo = true, Roughness = 1f },
            },
            VisibilityAabb = new Aabb(new Vector3(-60f, -30f, -60f), new Vector3(120f, 60f, 120f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
        AddChild(_bits);

        _coinMm = new MultiMesh
        {
            TransformFormat = MultiMesh.TransformFormatEnum.Transform3D,
            UseCustomData = true,
            Mesh = new QuadMesh { Size = new Vector2(0.22f, 0.22f) },
            InstanceCount = MaxCoins,
            VisibleInstanceCount = 0,
        };
        AddChild(new MultiMeshInstance3D
        {
            Name = "Coins",
            Multimesh = _coinMm,
            MaterialOverride = new ShaderMaterial { Shader = new Shader { Code = CoinCode } },
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            PhysicsInterpolationMode = PhysicsInterpolationModeEnum.Off,
            CustomAabb = new Aabb(new Vector3(-2000f, -200f, -2000f), new Vector3(4000f, 1000f, 4000f)),
        });
        GD.Print($"breakables: {_pieces.Count} pieces in {tiles.Count} batches");
    }

    private static Transform3D Standing(Piece p) =>
        new(new Basis(Vector3.Up, p.Yaw).Scaled(Vector3.One * p.Scale), p.Foot);

    private static IEnumerable<Piece> Near(Vector2 c, float r)
    {
        int x0 = Mathf.FloorToInt((c.X - r) / Cell), x1 = Mathf.FloorToInt((c.X + r) / Cell);
        int z0 = Mathf.FloorToInt((c.Y - r) / Cell), z1 = Mathf.FloorToInt((c.Y + r) / Cell);
        for (var z = z0; z <= z1; z++)
        for (var x = x0; x <= x1; x++)
            if (_grid.TryGetValue(new Vector2I(x, z), out var l))
                foreach (var p in l)
                    if (p.Down <= 0f) yield return p;
    }

    private static float Width(Piece p) => Mathf.Max(Kinds[p.Asset].Half.X, Kinds[p.Asset].Half.Z) * p.Scale;

    /// <summary>A swing: breaks what stands in the arc. True if anything broke.</summary>
    public static bool Hit(Vector3 from, Vector3 heading, float reach, float halfArc)
    {
        if (_live == null) return false;
        var f = new Vector2(from.X, from.Z);
        var h = new Vector2(heading.X, heading.Z).Normalized();
        var cos = Mathf.Cos(halfArc);
        var hit = new List<Piece>();
        foreach (var p in Near(f, reach + 1f))
        {
            var d = new Vector2(p.Foot.X, p.Foot.Z) - f;
            var len = d.Length();
            var w = Width(p);
            if (len > reach + w || Mathf.Abs(p.Foot.Y - from.Y) > 1.6f) continue;
            // inside the arc, or so close the blade cannot miss it
            if (len > w && d.Dot(h) < cos * len) continue;
            hit.Add(p);
        }
        foreach (var p in hit) _live.Break(p, h);
        return hit.Count > 0;
    }

    /// <summary>A shock: breaks everything within `r` of `at`, thrown outward.</summary>
    public static void Smash(Vector3 at, float r)
    {
        if (_live == null) return;
        var c = new Vector2(at.X, at.Z);
        var hit = new List<Piece>();
        foreach (var p in Near(c, r + 1f))
        {
            var d = new Vector2(p.Foot.X, p.Foot.Z) - c;
            if (d.Length() <= r + Width(p) && Mathf.Abs(p.Foot.Y - at.Y) < 2f) hit.Add(p);
        }
        foreach (var p in hit)
        {
            var d = new Vector2(p.Foot.X, p.Foot.Z) - c;
            _live.Break(p, d.LengthSquared() > 1e-4f ? d.Normalized() : Vector2.Right);
        }
    }

    private void Break(Piece p, Vector2 dir)
    {
        var k = Kinds[p.Asset];
        p.Down = Respawn;
        Broken++;
        p.Mm!.SetInstanceTransform(p.I, new Transform3D(Basis.Identity.Scaled(Vector3.One * 1e-4f), p.Foot));
        p.Col!.SetDeferred(CollisionShape3D.PropertyName.Disabled, true);
        var c = p.Foot + Vector3.Up * k.Half.Y * p.Scale;
        for (var i = 0; i < k.Bits; i++)
        {
            var at = c + new Vector3(GD.Randf() - 0.5f, GD.Randf() - 0.5f, GD.Randf() - 0.5f) * k.Half * 1.6f * p.Scale;
            var v = new Vector3((GD.Randf() - 0.5f) * 3f + dir.X * 2.4f, 2.5f + GD.Randf() * 3.5f,
                                (GD.Randf() - 0.5f) * 3f + dir.Y * 2.4f);
            var tone = k.Tone * (0.7f + 0.55f * GD.Randf());
            tone.A = 1f;
            _bits.EmitParticle(new Transform3D(Basis.Identity, at), v, tone, tone,
                (uint)(GpuParticles3D.EmitFlags.Position | GpuParticles3D.EmitFlags.Velocity | GpuParticles3D.EmitFlags.Color));
        }
        if (GD.Randf() < k.Coin && _coins.Count < MaxCoins)
            _coins.Add(new Coin { P = c, V = new Vector3(dir.X * 1.2f, 4.5f, dir.Y * 1.2f) });
    }

    public override void _Process(double delta)
    {
        var dt = (float)delta;
        var me = _player.GetGlobalTransformInterpolated().Origin;

        // back after five minutes, once nobody is looking (25 m)
        _respawnT += dt;
        if (_respawnT >= 1f)
        {
            foreach (var p in _pieces)
            {
                if (p.Down <= 0f) continue;
                p.Down -= _respawnT;
                if (p.Down > 0f) continue;
                if (new Vector2(p.Foot.X - me.X, p.Foot.Z - me.Z).Length() < 25f) { p.Down = 5f; continue; }
                p.Mm!.SetInstanceTransform(p.I, Standing(p));
                p.Col!.SetDeferred(CollisionShape3D.PropertyName.Disabled, false);
            }
            _respawnT = 0f;
        }

        // coins: thrown up, bounce, lie glinting; drawn to the player within 1.5 m
        var chest = me + Vector3.Up * 0.8f;
        for (var i = _coins.Count - 1; i >= 0; i--)
        {
            var c = _coins[i];
            c.Age += dt;
            var toMe = chest - c.P;
            if (toMe.Length() < 1.5f && c.Age > 0.4f)
            {
                c.P += toMe * (1f - Mathf.Exp(-14f * dt));
                if (toMe.Length() < 0.3f) { Coins++; _coins.RemoveAt(i); continue; }
            }
            else if (!c.Landed)
            {
                c.V.Y -= 14f * dt;
                c.P += c.V * dt;
                var ground = WorldGen.Height(c.P.X, c.P.Z) + 0.13f;
                if (c.P.Y < ground)
                {
                    c.P.Y = ground;
                    c.V = new Vector3(c.V.X * 0.5f, -c.V.Y * 0.4f, c.V.Z * 0.5f);
                    if (c.V.Y < 0.8f) c.Landed = true;
                }
            }
            if (c.Age > 90f) _coins.RemoveAt(i);
        }
        _coinMm.VisibleInstanceCount = _coins.Count;
        for (var i = 0; i < _coins.Count; i++)
        {
            _coinMm.SetInstanceTransform(i, new Transform3D(Basis.Identity, _coins[i].P));
            _coinMm.SetInstanceCustomData(i, new Color(i * 0.37f, 0f, 0f, 0f));
        }
    }

    /// <summary>A coin: a 10 x 10 pixel disc facing the camera, spinning (its width goes as
    /// cos), lit on its upper side with a bright rim. Unshaded, so it glints in any light.</summary>
    private const string CoinCode = @"
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled;
varying float spin;

void vertex() {
    // face the camera: its axes, the instance's position
    MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
    spin = cos(TIME * 5.0 + INSTANCE_CUSTOM.r * 6.283);
}

void fragment() {
    vec2 p = (floor(UV * 10.0) + 0.5) / 10.0 * 2.0 - 1.0;
    p.x /= max(abs(spin), 0.18);
    float r = length(p);
    if (r > 0.95) discard;
    vec3 gold = vec3(1.0, 0.78, 0.25);
    vec3 c = mix(gold * 0.6, gold, step(0.0, -p.y * 0.7 - p.x * 0.3));
    c = mix(c, vec3(1.0, 0.97, 0.78), step(0.6, r) * step(0.15, -p.y));
    ALBEDO = c;
}
";
}
