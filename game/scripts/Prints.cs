using Godot;

namespace Worldbuilder;

/// <summary>
/// What the feet leave (moved out of <see cref="Snow"/> on 2026-09-28, when prints stopped
/// being snow's alone: implementation_plan A4). An RG8 map, 48 m square, follows the player
/// in whole texels, so a print keeps its place on the ground.
///
/// * R, pressed IN: snow, sand, fen mud (<see cref="Surface"/>). Every 0.33 m walked on soft
///   ground stamps an oval 0.3 x 0.16 m, left and right foot in turn, as deep as the ground
///   is soft. What fills them is whatever the map lies in: falling snow (~60 s at full
///   fall), the dunes' wind (~150 s, faster in a gust), rain on the mud (~120 s at full rain).
/// * G, wet: for 6 s after the feet were in water (the pond, a puddle, the Fen), every step
///   leaves a wet print on any ground, fainter as the feet dry; each dries in ~8 s.
///
/// The ground shaders read the globals `prints` and `prints_rect` (Terrain: snow packs and
/// hollows, sand and mud darken and hollow, wet prints darken and shine). The grains kicked
/// up at each step -- snow, sand, mud -- come from here too.
/// </summary>
public partial class Prints : Node3D
{
    private const int Res = 512;
    private const float Span = 48f;
    private const float Texel = Span / Res;

    public static Prints? Live;
    /// <summary>Steps that pressed a print, and steps that left a wet one (the harness).</summary>
    public static int Stamps, WetStamps;

    private readonly byte[] _px = new byte[Res * Res * 2];
    private Image _img = null!;
    private ImageTexture _tex = null!;
    private Vector2I _origin;
    private bool _dirty, _anyWet;
    private float _uploadT, _fillT, _walked, _wetFeet;
    private int _foot;
    private Vector3 _last;
    private bool _hasLast;
    private Node3D _player = null!;
    private GpuParticles3D _kick = null!;

    private static readonly Color SnowGrain = new(0.95f, 0.97f, 1f);
    private static readonly Color SandGrain = new(0.84f, 0.70f, 0.47f);
    private static readonly Color MudGrain = new(0.20f, 0.16f, 0.11f);

    /// <summary>The globals the ground shaders read (declared in project.godot), at their start values.</summary>
    public static void Globals()
    {
        var blank = Image.CreateEmpty(1, 1, false, Image.Format.Rg8);
        RenderingServer.GlobalShaderParameterSet("prints",
                                                 ImageTexture.CreateFromImage(blank));
        RenderingServer.GlobalShaderParameterSet("prints_rect",
                                                 new Vector4(0f, 0f, Span, 1f / Res));
    }

    public void Build(Node3D player)
    {
        Live = this;
        _player = player;
        _img = Image.CreateFromData(Res, Res, false, Image.Format.Rg8, _px);
        _tex = ImageTexture.CreateFromImage(_img);
        RenderingServer.GlobalShaderParameterSet("prints", _tex);
        Recentre(new Vector2(player.GlobalPosition.X, player.GlobalPosition.Z), force: true);

        var grain = new StandardMaterial3D
        {
            Transparency = BaseMaterial3D.TransparencyEnum.AlphaScissor,
            VertexColorUseAsAlbedo = true,
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
            EmissionEnabled = true,
            Emission = new Color(0.1f, 0.1f, 0.11f),
            Roughness = 1f,
        };
        _kick = new GpuParticles3D
        {
            Name = "KickUp",
            Amount = 600,
            Lifetime = 0.7,
            LocalCoords = false,
            Emitting = false,   // EmitParticle only (INVARIANTS: not AmountRatio 0)
            ProcessMaterial = new ParticleProcessMaterial
            {
                Gravity = new Vector3(0f, -6f, 0f), Spread = 0f,
                DampingMin = 0.5f, DampingMax = 0.75f,
                ScaleMin = 0.7f, ScaleMax = 1.6f,
                CollisionMode = ParticleProcessMaterial.CollisionModeEnum.HideOnContact,
            },
            // two to three pixels at 52 texels/m
            DrawPass1 = new QuadMesh { Size = new Vector2(0.05f, 0.05f), Material = grain },
            VisibilityAabb = new Aabb(new Vector3(-60f, -30f, -60f), new Vector3(120f, 60f, 120f)),
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
        AddChild(_kick);
    }

    public override void _Process(double delta)
    {
        var dt = (float)delta;
        var p = _player.GetGlobalTransformInterpolated().Origin;
        Recentre(new Vector2(p.X, p.Z), force: false);
        Steps(p, dt);
        Fill(dt);
        _uploadT -= dt;
        if (_dirty && _uploadT <= 0f)
        {
            _img.SetData(Res, Res, false, Image.Format.Rg8, _px);
            _tex.Update(_img);
            _dirty = false;
            _uploadT = 1f / 30f;
        }
    }

    /// <summary>Keep the map round the player: when they are 12 m off its centre, shift it
    /// by whole texels (prints keep their place on the ground) and clear what comes in.</summary>
    private void Recentre(Vector2 at, bool force)
    {
        var want = new Vector2I(Mathf.RoundToInt(at.X / Texel) - Res / 2, Mathf.RoundToInt(at.Y / Texel) - Res / 2);
        var off = want - _origin;
        if (!force && Mathf.Abs(off.X) * Texel < 12f && Mathf.Abs(off.Y) * Texel < 12f) return;
        var old = (byte[])_px.Clone();
        System.Array.Clear(_px);
        if (!force)
            for (var y = 0; y < Res; y++)
            {
                var sy = y + off.Y;
                if (sy < 0 || sy >= Res) continue;
                for (var x = 0; x < Res; x++)
                {
                    var sx = x + off.X;
                    if (sx < 0 || sx >= Res) continue;
                    _px[(y * Res + x) * 2] = old[(sy * Res + sx) * 2];
                    _px[(y * Res + x) * 2 + 1] = old[(sy * Res + sx) * 2 + 1];
                }
            }
        _origin = want;
        _dirty = true;
        RenderingServer.GlobalShaderParameterSet("prints_rect",
            new Vector4(_origin.X * Texel, _origin.Y * Texel, Span, 1f / Res));
    }

    private void Steps(Vector3 p, float dt)
    {
        if (!_hasLast) { _last = p; _hasLast = true; return; }
        var d = new Vector2(p.X - _last.X, p.Z - _last.Z);
        _last = p;
        _wetFeet = Mathf.Max(0f, _wetFeet - dt);
        var ground = WorldGen.Height(p.X, p.Z);
        // on foot, on the ground (a teleport is not a step)
        if (Boat.Aboard || p.Y - ground > 0.35f || d.Length() > 2f) return;
        var g = Surface.At(p);
        var inWater = g.K == Surface.Kind.Shallows || Water.Underfoot(p);
        if (inWater) _wetFeet = 6f;
        _walked += d.Length();
        if (_walked < 0.33f || d.LengthSquared() < 1e-8f) return;
        _walked = 0f;
        var dir = d.Normalized();
        var side = new Vector2(-dir.Y, dir.X) * (_foot++ % 2 == 0 ? 0.13f : -0.13f);
        var at = new Vector2(p.X, p.Z) + side;
        var wet = inWater ? 0f : _wetFeet / 6f;
        if (g.Soft > 0.05f || wet > 0.05f) Stamp(at, dir, g.Soft, wet);
        if (g.Soft > 0.05f) Stamps++;
        if (wet > 0.05f) WetStamps++;

        // grains kicked up: more, and higher, the softer it is
        var (tone, n, lift) = g.K switch
        {
            Surface.Kind.Snow => (SnowGrain, 1 + (int)(g.Soft * 4f), 0.6f + g.Soft),
            Surface.Kind.Sand => (SandGrain, 1 + (int)(g.Soft * 3f), 0.5f),
            Surface.Kind.Mud => (MudGrain, 2, 0.8f),
            _ => (Colors.White, 0, 0f),
        };
        for (var i = 0; i < n; i++)
            Emit(new Vector3(at.X, ground + 0.05f, at.Y),
                 new Vector3(dir.X * 0.6f + (GD.Randf() - 0.5f) * 0.6f, 0.6f + GD.Randf() * lift,
                             dir.Y * 0.6f + (GD.Randf() - 0.5f) * 0.6f), tone);
    }

    private void Emit(Vector3 at, Vector3 v, Color tone) =>
        _kick.EmitParticle(new Transform3D(Basis.Identity, at), v, tone, tone,
            (uint)(GpuParticles3D.EmitFlags.Position | GpuParticles3D.EmitFlags.Velocity | GpuParticles3D.EmitFlags.Color));

    /// <summary>A blow landing (<see cref="Impact.Shock"/>): the soft ground bursts up.</summary>
    public void Burst(Vector3 at, float r)
    {
        var g = Surface.At(at);
        var tone = g.K switch { Surface.Kind.Snow => SnowGrain, Surface.Kind.Sand => SandGrain, Surface.Kind.Mud => MudGrain, _ => Colors.White };
        if (g.Soft < 0.05f) return;
        var ground = WorldGen.Height(at.X, at.Z);
        var n = (int)(24 + 48 * g.Soft);
        for (var i = 0; i < n; i++)
        {
            var a = GD.Randf() * Mathf.Tau;
            var out_ = new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a));
            Emit(new Vector3(at.X, ground + 0.05f, at.Z) + out_ * r * 0.3f * GD.Randf(),
                 out_ * (1.5f + GD.Randf() * 2.5f) + Vector3.Up * (1.8f + GD.Randf() * 2.4f), tone);
        }
        // and the shock presses a ring into it
        var c = new Vector2(at.X, at.Z);
        for (var k = 0; k < 12; k++)
        {
            var a = k * Mathf.Tau / 12f;
            var u = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
            Stamp(c + u * r * 0.45f, new Vector2(-u.Y, u.X), g.Soft * 0.8f, 0f);
        }
    }

    /// <summary>One print: an oval 0.3 m long, 0.16 m wide, along `dir`, `deep` into R and
    /// `wet` into G.</summary>
    private void Stamp(Vector2 at, Vector2 dir, float deep, float wet)
    {
        var cx = at.X / Texel - _origin.X;
        var cy = at.Y / Texel - _origin.Y;
        var vr = deep > 0.05f ? (byte)Mathf.Clamp(140f + 115f * deep, 0f, 255f) : (byte)0;
        var vg = (byte)Mathf.Clamp(255f * wet, 0f, 255f);
        const float lo = 0.15f / Texel, wi = 0.08f / Texel;
        var r = (int)Mathf.Ceil(lo) + 1;
        for (var y = -r; y <= r; y++)
        for (var x = -r; x <= r; x++)
        {
            var px = (int)cx + x;
            var py = (int)cy + y;
            if (px < 0 || py < 0 || px >= Res || py >= Res) continue;
            var o = new Vector2(px + 0.5f - cx, py + 0.5f - cy);
            var a = o.Dot(dir) / lo;
            var b = o.Dot(new Vector2(-dir.Y, dir.X)) / wi;
            if (a * a + b * b > 1f) continue;
            var k = (py * Res + px) * 2;
            if (_px[k] < vr) { _px[k] = vr; _dirty = true; }
            if (_px[k + 1] < vg) { _px[k + 1] = vg; _dirty = _anyWet = true; }
        }
    }

    /// <summary>Twice a second: the ground this map lies in fills the pressed prints back
    /// in (see the class note), and wet prints dry (~8 s).</summary>
    private void Fill(float dt)
    {
        _fillT += dt;
        if (_fillT < 0.5f) return;
        var p = _player.GlobalPosition;
        var fen = Biomes.WeightOf(Biome.Fen, new Vector2(p.X, p.Z), WorldGen.Seed);
        var rate = Mathf.Max(Snow.Falling / 60f,
                   Mathf.Max(Weather.DunesHere * (1f / 150f + Snow.Gust / 40f), Weather.Rain * fen / 120f));
        var subR = rate > 0.001f ? Mathf.Max(1, (int)(255f * rate * _fillT)) : 0;
        var subG = _anyWet ? Mathf.Max(1, (int)(255f * _fillT / 8f)) : 0;
        _fillT = 0f;
        if (subR <= 0 && subG <= 0) return;
        var wet = false;
        for (var i = 0; i < _px.Length; i += 2)
        {
            if (subR > 0 && _px[i] != 0) { _px[i] = (byte)Mathf.Max(0, _px[i] - subR); _dirty = true; }
            if (subG > 0 && _px[i + 1] != 0)
            {
                _px[i + 1] = (byte)Mathf.Max(0, _px[i + 1] - subG);
                _dirty = true;
                wet |= _px[i + 1] != 0;
            }
        }
        if (subG > 0) _anyWet = wet;
    }
}
