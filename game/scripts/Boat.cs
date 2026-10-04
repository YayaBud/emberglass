using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// A rowing boat on the pond: a low-poly plank hull you can walk up to and
/// board (E), then row with WASD -- the boat turns toward the direction you
/// hold and pulls a stroke every 1.3 s, glides between strokes, drifts when
/// nobody rows, and bumps off the shore. `--boat=demo` seats the player and
/// rows a loop, for captures.
///
/// What it does to the water (<see cref="Water"/>): a Kelvin wake (the V at
/// 19.5 degrees plus transverse waves, drawn in the shader from the boat's
/// position, heading and speed); ripple rings at the stern while it moves, at
/// both blades on every catch, and on every bump; droplets off the blades on
/// the recovery. It floats: it heaves on the swell, the bow lifts with speed,
/// it leans into turns and rocks when someone climbs in. Ducks and fish flee
/// from it (<see cref="Fauna.Threat"/>).
///
/// Motion is kinematic (an AnimatableBody3D, so the player collides with it
/// standing in the water); a seated player is carried on <see cref="Seat"/>.
/// Local +X is the bow.
/// </summary>
public partial class Boat : AnimatableBody3D
{
    private const float Length = 3.4f, Beam = 1.24f, Stroke = 1.3f;

    public Node3D Seat { get; private set; } = null!;
    /// <summary>`--boat=demo`: board at once and row a loop round the pond.</summary>
    public static bool Demo;
    /// <summary>`--boat=ram`: the collision check. Rows into the ship, then
    /// the bank, and prints how far any hull probe got inside either.</summary>
    public static bool Ram;
    private float _worst, _oarJump, _lastSweep = -1.2f, _lastDip = 0.2f;
    private int _bumps;
    public static Boat? Current;

    private Player _player = null!;
    private float _level, _yaw, _omega, _phase, _t, _dip, _rock, _wakeT, _bowT, _bumpT;
    private Vector2 _pos, _vel;
    private bool _rowing, _ePrev, _caught;
    private Node3D _oarL = null!, _oarR = null!;
    private int _waypoint;
    private float _sweep = -1.2f, _dipA = 0.2f, _landT;
    private bool _canLand;

    private Vector2 Fwd => new(Mathf.Cos(_yaw), -Mathf.Sin(_yaw));
    private bool Seated => _player.Seat == Seat;

    /// <summary>The player is in the boat: afloat, not wading.</summary>
    public static bool Aboard => Current != null && Current.Seated;

    public void Build(Player player, Vector2 at, float yawRad)
    {
        Bake.Spot("boat", ref at, ref yawRad);
        _player = player;
        _level = WorldGen.PondLevel;
        _pos = at;
        _yaw = yawRad;
        Current = this;
        SyncToPhysics = true;
        PhysicsInterpolationMode = PhysicsInterpolationModeEnum.On;

        // Painted, not plank-textured: the dark plank texture on a side facing
        // the camera went black under the twilight key (a box, 2026-09-23).
        // Ochre-red below, a light wood top strake, darker wood inside.
        var paint = new StandardMaterial3D
        {
            VertexColorUseAsAlbedo = true,
            Roughness = 0.75f,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled,
        };
        AddChild(new MeshInstance3D { Name = "Hull", Mesh = Hull(), MaterialOverride = paint });

        var wood = new StandardMaterial3D { AlbedoColor = new Color(0.72f, 0.55f, 0.36f), Roughness = 0.8f };
        foreach (var x in new[] { -0.45f, 0.35f })
            AddChild(new MeshInstance3D
            {
                Name = "Thwart", MaterialOverride = wood,
                Mesh = new BoxMesh { Size = new Vector3(0.24f, 0.04f, Width(x / (Length / 2f)) * 2f - 0.06f) },
                Position = new Vector3(x, 0.14f, 0f),
            });
        _oarL = Oar(wood, -1f);
        _oarR = Oar(wood, 1f);

        // low: the near side hides the legs, so the figure sits IN the boat
        Seat = new Node3D { Name = "Seat", Position = new Vector3(-0.1f, -0.22f, 0f) };
        AddChild(Seat);
        AddChild(new CollisionShape3D
        {
            Shape = new BoxShape3D { Size = new Vector3(Length * 0.9f, 0.7f, Beam) },
            Position = new Vector3(0f, 0.1f, 0f),
        });
        Place();
    }

    private Node3D Oar(Material m, float side)
    {
        // pivot at the oarlock; the loom runs outboard along local +Z (side)
        var pivot = new Node3D { Name = side < 0 ? "OarL" : "OarR", Position = new Vector3(0.1f, 0.4f, side * Beam * 0.5f) };
        pivot.AddChild(new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(0.05f, 0.05f, 2.3f) }, MaterialOverride = m,
            Position = new Vector3(0f, 0f, side * 0.75f),
        });
        pivot.AddChild(new MeshInstance3D
        {
            Mesh = new BoxMesh { Size = new Vector3(0.16f, 0.03f, 0.5f) }, MaterialOverride = m,
            Position = new Vector3(0f, 0f, side * 1.75f),
        });
        AddChild(pivot);
        return pivot;
    }

    /// <summary>Half-beam at station t (-1 stern .. +1 bow): a fine bow, a
    /// transom stern.</summary>
    private static float Width(float t) =>
        Beam * 0.5f * Mathf.Sqrt(Mathf.Max(0f, 1f - (t > 0f ? t * t : 0.7f * t * t)));

    /// <summary>The hull, lofted from 9 stations of 7 points each, flat
    /// shaded (one normal per triangle, the kit's low-poly look), drawn two-
    /// sided so the inside shows; a transom closes the stern.</summary>
    private static ArrayMesh Hull()
    {
        const int ns = 9;
        float[] s = { -1f, -0.7f, -0.38f, 0f, 0.38f, 0.7f, 1f };
        var pts = new Vector3[ns, s.Length];
        for (var i = 0; i < ns; i++)
        {
            var t = -1f + 2f * i / (ns - 1);
            var w = Width(t);
            // a strong sheer and a rockered keel: side-on, it reads as a boat
            var gun = 0.36f + 0.2f * t * t + (t > 0f ? 0.08f * t * t * t : 0f);
            var keel = -0.16f + 0.3f * Mathf.Pow(Mathf.Abs(t), 2.5f);
            for (var j = 0; j < s.Length; j++)
                pts[i, j] = new Vector3(t * Length * 0.5f, keel + (gun - keel) * Mathf.Pow(Mathf.Abs(s[j]), 2.2f), s[j] * w);
        }
        var v = new List<Vector3>();
        var n = new List<Vector3>();
        var col = new List<Color>();
        var red = new Color(0.58f, 0.24f, 0.15f);
        var strake = new Color(0.78f, 0.62f, 0.42f);
        void Tri(Vector3 a, Vector3 b, Vector3 c, Color k)
        {
            var nn = (b - a).Cross(c - a);
            if (nn.LengthSquared() < 1e-10f) return;
            nn = nn.Normalized();
            // Godot's front face winds clockwise about its normal: a, c, b.
            // Wound a, b, c the outside read as a back face, its normal was
            // flipped inward, and the hull lit up when the sun was behind it.
            v.Add(a); v.Add(c); v.Add(b);
            n.Add(nn); n.Add(nn); n.Add(nn);
            col.Add(k); col.Add(k); col.Add(k);
        }
        for (var i = 0; i < ns - 1; i++)
        for (var j = 0; j < s.Length - 1; j++)
        {
            // the top row of panels either side is bare wood, the rest paint
            var k = j == 0 || j == s.Length - 2 ? strake : red;
            Tri(pts[i, j], pts[i + 1, j], pts[i + 1, j + 1], k);
            Tri(pts[i, j], pts[i + 1, j + 1], pts[i, j + 1], k);
        }
        for (var j = 1; j < s.Length - 1; j++)
            Tri(pts[0, 0], pts[0, j], pts[0, j + 1], red);
        var arrays = new Godot.Collections.Array();
        arrays.Resize((int)Mesh.ArrayType.Max);
        arrays[(int)Mesh.ArrayType.Vertex] = v.ToArray();
        arrays[(int)Mesh.ArrayType.Normal] = n.ToArray();
        arrays[(int)Mesh.ArrayType.Color] = col.ToArray();
        var mesh = new ArrayMesh();
        mesh.AddSurfaceFromArrays(Mesh.PrimitiveType.Triangles, arrays);
        return mesh;
    }

    private bool Floatable(Vector2 p) => WorldGen.Height(p.X, p.Y) < _level - 0.3f;

    public override void _PhysicsProcess(double delta)
    {
        var dt = (float)delta;
        _t += dt;

        // boarding: E near the boat; E again steps out beside it
        var e = Input.IsPhysicalKeyPressed(Key.E);
        var me = new Vector2(_player.GlobalPosition.X, _player.GlobalPosition.Z);
        var near = (me - _pos).Length() < 2.8f;
        if (Demo && !Seated && _t > 0.2f) Board();
        else if (e && !_ePrev)
        {
            if (Seated) Leave();
            else if (near) Board();
        }
        _ePrev = e;
        Weather.Hint = !Seated ? (near ? "E: board" : "")
                     : CanLand() ? "E: step out   WASD: row"
                     : "WASD: row   (row to the bank to step out)";

        // what the rower wants
        var wish = Vector2.Zero;
        if (Seated)
        {
            if (Ram)
            {
                var goal = (_bumps == 0 && _t < 45f) || Ship.Current == null
                    ? Ship.Current?.Pos ?? WorldGen.PondCentre
                    : WorldGen.PondCentre + new Vector2(0.7071f, 0.7071f) * WorldGen.PondRadius * 2f;   // the camera's bank
                wish = (goal - _pos).Normalized();
            }
            else if (Demo)
            {
                var r = WorldGen.PondRadius * 0.5f;
                var a = _waypoint * Mathf.Tau / 6f;
                var goal = WorldGen.PondCentre + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r;
                if ((goal - _pos).Length() < 3f) _waypoint = (_waypoint + 1) % 6;
                wish = (goal - _pos).Normalized();
            }
            else
            {
                var w3 = _player.WishDir;
                wish = new Vector2(w3.X, w3.Z);
            }
        }
        _rowing = wish.LengthSquared() > 0.01f;

        // steer: the oars turn the boat toward the wish; pull on the stroke
        if (_rowing)
        {
            var want = Mathf.Atan2(-wish.Y, wish.X);
            var diff = Mathf.Wrap(want - _yaw, -Mathf.Pi, Mathf.Pi);
            _omega += diff * 2.2f * dt;
            _phase += dt / Stroke;
            var p = _phase % 1f;
            if (p < 0.45f)
            {
                var along = Mathf.Max(0f, Mathf.Cos(diff));
                _vel += Fwd * 2.4f * along * dt;
                if (!_caught)
                {
                    _caught = true;
                    foreach (var tip in BladeTips()) Water.Ripple(tip, 0.9f);
                }
            }
            else
            {
                if (_caught)
                    foreach (var tip in BladeTips())
                        for (var k = 0; k < 3; k++)
                            Weather.Drip(new Vector3(tip.X, _level + 0.1f, tip.Y),
                                         new Vector3(GD.Randf() - 0.5f, 0.8f + GD.Randf(), GD.Randf() - 0.5f));
                _caught = false;
            }
        }
        else if (!Seated)
        {
            // an empty boat drifts on a breath of wind
            _vel += new Vector2(0.03f, 0.02f) * dt;
        }

        // water drag: long and slippery, stubborn sideways (the keel)
        var f = Fwd;
        var fwdV = _vel.Dot(f);
        var latV = _vel - f * fwdV;
        _vel = f * fwdV * Mathf.Exp(-0.35f * dt) + latV * Mathf.Exp(-3f * dt);
        _omega *= Mathf.Exp(-2f * dt);
        _yaw += _omega * dt;

        // the shore and the ship: bow, stern or beam touching -> the hull
        // slides along it. The velocity into it is cancelled with a small
        // rebound and the boat eases back out; it used to reverse outright,
        // which bounced it off every bank like a ball.
        var next = _pos + _vel * dt;
        var side = new Vector2(-f.Y, f.X);
        foreach (var o in new[] { f * 1.6f, -f * 1.6f, side * 0.6f, -side * 0.6f, (f + side * 0.4f) * 1.1f, (f - side * 0.4f) * 1.1f })
        {
            var q = next + o;
            Vector2 push;
            var ship = false;
            if (!Floatable(q))
            {
                var tn = WorldGen.Normal(q.X, q.Y);
                push = new Vector2(tn.X, tn.Z);
                push = push.LengthSquared() > 1e-6f ? push.Normalized() : (_pos - q).Normalized();
            }
            else if (Ship.Current?.Contact(q) is Vector2 bn) { push = bn; ship = true; }
            else continue;

            var into = -_vel.Dot(push);
            if (into > 0f) _vel += push * into * 1.25f;
            _vel *= 0.9f;
            // a glancing blow turns the boat away from what it hit
            // (+omega swings the bow from +x toward -z: hence the minus)
            _omega -= o.Cross(push) * 1.2f * dt;
            next = _pos + _vel * dt + push * 0.4f * dt;
            if (into > 0.25f && _bumpT <= 0f)
            {
                _rock += 0.03f + 0.04f * into;
                Water.Ripple(q, 0.4f + 0.6f * into);
                if (ship) Ship.Current!.Bump(q, into);
                _bumpT = 0.5f;
                if (Ram) { _bumps++; GD.Print($"boatcheck: bump {(ship ? "ship" : "bank")} at {into:F2} m/s"); }
            }
            break;
        }
        _pos = next;
        _bumpT -= dt;
        if (Ram) RamCheck();

        // its own ripples: a wake off the stern, a bow wave when it is quick
        var speed = _vel.Length();
        _wakeT -= dt;
        _bowT -= dt;
        if (speed > 0.25f && _wakeT <= 0f) { Water.Ripple(_pos - f * 1.6f, 0.25f + 0.35f * speed); _wakeT = 0.35f; }
        if (speed > 0.7f && _bowT <= 0f) { Water.Ripple(_pos + f * 1.7f, 0.3f * speed); _bowT = 0.5f; }
        Water.Boat = new Vector4(_pos.X, _pos.Y, f.X, f.Y);
        Water.BoatSpeed = speed;

        _dip = Mathf.MoveToward(_dip, Seated ? 0.06f : 0f, dt * 0.3f);
        _rock *= Mathf.Exp(-1.5f * dt);
        Place();
        Oars(dt);
        if (Seated)
        {
            _player.GlobalPosition = Seat.GlobalPosition;
        }
    }

    private void RamCheck()
    {
        var f = Fwd;
        var side = new Vector2(-f.Y, f.X);
        foreach (var o in new[] { f * 1.6f, -f * 1.6f, side * 0.6f, -side * 0.6f })
        {
            var q = _pos + o;
            // depth into the ship's hull, and height of ground past the
            // boat's own grounding line (level - 0.3)
            var into = 0f;
            for (var m = 0f; m > -1.5f && Ship.Current?.Contact(q, m - 0.05f) != null; m -= 0.05f) into = -m;
            _worst = Mathf.Max(_worst, Mathf.Max(into, WorldGen.Height(q.X, q.Y) - (_level - 0.3f)));
        }
        _oarJump = Mathf.Max(_oarJump, Mathf.Max(Mathf.Abs(_sweep - _lastSweep), Mathf.Abs(_dipA - _lastDip)));
        _lastSweep = _sweep; _lastDip = _dipA;
        if (Mathf.PosMod(_t, 2f) < GetPhysicsProcessDeltaTime())
            GD.Print($"boatcheck: t={_t:F1} pos={_pos} speed={_vel.Length():F2} bumps={_bumps} worst={_worst:F2} landing={Landing()?.ToString() ?? "none"} oarjump={_oarJump:F3}rad/tick sweep={_sweep:F2} dip={_dipA:F2}");
    }

    /// <summary>The boat's transform: yaw, then the float -- heave on the
    /// swell, bow up with speed, lean into the turn, rock after a boarding.</summary>
    private void Place()
    {
        var fwdSpeed = _vel.Dot(Fwd);
        var heave = 0.025f * Mathf.Sin(_t * 1.7f) - _dip + 0.01f * Mathf.Sin(_phase * Mathf.Tau);
        var pitch = 0.02f * Mathf.Sin(_t * 1.3f) + 0.025f * fwdSpeed + 0.015f * Mathf.Sin(_phase * Mathf.Tau);
        var roll = 0.025f * Mathf.Sin(_t * 1.1f + 1f) - _omega * 0.1f + _rock * Mathf.Sin(_t * 6f);
        var basis = Basis.FromEuler(new Vector3(roll, _yaw, pitch), EulerOrder.Yxz);
        GlobalTransform = new Transform3D(basis, new Vector3(_pos.X, _level + heave, _pos.Y));
    }

    /// <summary>Where the blades are now, from the oars themselves.</summary>
    private IEnumerable<Vector3> Blades()
    {
        yield return _oarL.ToGlobal(new Vector3(0f, 0f, -1.75f));
        yield return _oarR.ToGlobal(new Vector3(0f, 0f, 1.75f));
    }

    private IEnumerable<Vector2> BladeTips()
    {
        foreach (var b in Blades()) yield return new Vector2(b.X, b.Z);
    }

    /// <summary>Oars: sweep and dip, eased. The drive (first 45% of the
    /// stroke) swings the blades bow to stern IN the water; the recovery
    /// carries them back just clear of it. Every curve is continuous, and the
    /// angles follow it at a capped speed, so starting, stopping and the catch never jump.
    /// It used to: the dip flipped between two values at the catch (and had
    /// its sign backwards, blades up on the drive), and letting go of the
    /// keys snapped the oars straight to trailing. Positive dip = blade down;
    /// 0.26 rad puts the blade at the waterline from the 0.4 m oarlock.</summary>
    private void Oars(float dt)
    {
        float sweep, dip;
        if (_rowing)
        {
            var p = _phase % 1f;
            sweep = p < 0.45f
                ? 0.6f * Mathf.Cos(Mathf.Pi * p / 0.45f)
                : -0.6f * Mathf.Cos(Mathf.Pi * (p - 0.45f) / 0.55f);
            var inWater = Mathf.SmoothStep(0f, 0.16f, p) - Mathf.SmoothStep(0.33f, 0.45f, p);
            dip = Mathf.Lerp(-0.06f, 0.26f, inWater);
        }
        else { sweep = -1.2f; dip = 0.2f; }
        // capped angular speed, not an ease: an ease covers a fifth of a
        // 1.8 rad trailing-to-catch swing in its first tick (0.37 rad, seen
        // in --boat=ram). The stroke itself peaks at 3.2 rad/s sweep.
        _sweep = Mathf.MoveToward(_sweep, sweep, (_rowing ? 5f : 2f) * dt);
        _dipA = Mathf.MoveToward(_dipA, dip, 1.8f * dt);   // blades lower, not drop (user, 2026-09-23)
        _oarL.Rotation = new Vector3(-_dipA, -_sweep, 0f);
        _oarR.Rotation = new Vector3(_dipA, _sweep, 0f);
    }

    private void Board()
    {
        _player.Seat = Seat;
        _rock = 0.08f;
        Water.Ripple(_pos, 0.8f);
    }

    /// <summary>Where the rower can step out: the nearest spot within 6 m,
    /// round the boat, no deeper than the knee (0.4 m) -- they wade the rest.
    /// Stepping out 1.6 m to the side anywhere left them standing on the bed
    /// 1.2 m under; the boat itself grounds ~2 m short of the waterline.</summary>
    // the hint asks 4x a second: a miss in deep water is 144 terrain samples
    private bool CanLand()
    {
        if ((_landT -= (float)GetPhysicsProcessDeltaTime()) <= 0f) { _landT = 0.25f; _canLand = Landing() != null; }
        return _canLand;
    }

    private Vector2? Landing()
    {
        for (var r = 1.4f; r <= 6f; r += 0.4f)
            for (var i = 0; i < 12; i++)
            {
                var q = _pos + new Vector2(Mathf.Cos(i * Mathf.Tau / 12f), Mathf.Sin(i * Mathf.Tau / 12f)) * r;
                if (WorldGen.Height(q.X, q.Y) > _level - 0.4f && Ship.Current?.Contact(q, 0.4f) == null) return q;
            }
        return null;
    }

    private void Leave()
    {
        if (Landing() is not Vector2 spot) return;
        _player.Seat = null;
        _player.GlobalPosition = new Vector3(spot.X, WorldGen.Height(spot.X, spot.Y) + 0.1f, spot.Y);
        _player.ResetPhysicsInterpolation();
        _rock = 0.08f;
        Water.Ripple(spot, 0.8f);
    }
}
