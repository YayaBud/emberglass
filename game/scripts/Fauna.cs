using System;
using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Animals as pixel-art sprites: they wander round a home, keep out of trunks
/// and posts, stay on their side of the waterline, and bolt from the player.
/// A site (the wood, the pond) configures one and hands it homes; this class
/// owns the behaviour and the drawing.
///
/// Drawing: one MultiMesh per species plus a sun-facing caster, frame and
/// facing in each instance's custom data (atlases from
/// `scripts/forge/foliage/animals.py`: a cell per frame, row 0 facing
/// screen-right, row 1 left). They move in `_Process`, so the MultiMesh nodes
/// opt out of physics interpolation (INVARIANTS: Traps).
///
/// Media: Land walks the ground and is pushed out of every blocker circle;
/// Swim floats on the water surface (ducks); Fish swims under it and now and
/// then jumps. A flier (robin, duck) takes to the air when it flees.
/// </summary>
public partial class Fauna : Node3D
{
    private const string Dir = "res://assets/fauna/";

    public enum Medium { Land, Swim, Fish }

    /// <summary>One species' behaviour. Radius is its body for trunk
    /// avoidance; Homing animals go back to their home after bolting (the
    /// pond's drinkers) instead of settling where they ran to.</summary>
    public readonly record struct Kind(string Sprite, float Walk, float Run, float Fear, float Roam,
                                       float Stride, float Radius, string Alt, bool Flies = false,
                                       Medium On = Medium.Land, bool Homing = false,
                                       bool Tame = false, bool Skittish = false, bool Pet = false);
    // Tame (dogs): never bolts; trots over when the player is near, sits by
    // them, and follows for a while after being petted. Skittish (cats): bolts
    // only from a player who is running at it. Pet: E beside it pets it (a
    // heart; a tame one then follows). User, 2026-09-26: "dogs cats ... that
    // are intractable".

    /// <summary>Clamp a goal into the site.</summary>
    public Func<Vector2, Vector2> Keep = p => p;
    /// <summary>May a land animal stand here (not in the water).</summary>
    public Func<Vector2, bool> Dry = _ => true;
    /// <summary>May a swimmer or a fish be here (deep enough).</summary>
    public Func<Vector2, bool> Deep = _ => false;
    /// <summary>The water surface, for swimmers and fish.</summary>
    public float Water = float.NaN;
    /// <summary>Land animals at rest turn to face this point (drinking).</summary>
    public Vector2? FaceIdle;
    /// <summary>Something besides the player they run from (the boat).</summary>
    public Func<Vector2?>? Threat;
    /// <summary>Something disturbed the water at (x, z) with this strength.</summary>
    public Action<Vector2, float>? Ripple;
    /// <summary>The height a land animal stands at (the city's streets, which
    /// ramp and bridge over the ground); null is the ground.</summary>
    public Func<Vector2, float>? Ground;

    private enum Mode { Idle, Walk, Alt, Flee, Jump }

    private sealed class Herd
    {
        public MultiMesh Face = null!, Shadow = null!;
        public readonly Dictionary<string, int> Frame = new();
        // written in place, handed over whole once a frame (Townsfolk.Put)
        public float[] FaceBuf = Array.Empty<float>(), ShadowBuf = Array.Empty<float>();
        public bool Dirty;
        /// <summary>Where and when one of a flock bolted: the alarm runs out from there
        /// at <see cref="AlarmSpeed"/> and lifts every bird it reaches.</summary>
        public Vector2 AlarmAt;
        public float AlarmT = -99f;
    }

    /// <summary>m/s an alarm spreads through a flock: a wave of take-offs, not all at once.</summary>
    private const float AlarmSpeed = 7f;

    private sealed class Beast
    {
        public Kind K;
        public Herd H = null!;
        public int Slot, Row, Id;
        public Vector2 P, Home, Goal;
        public Mode M;
        public float T, Travel, Lift, Stuck, Wet, Follow;
    }

    private readonly List<Beast> _beasts = new();
    private readonly List<Herd> _herds = new();
    private readonly Bodies _bodies = new();
    private readonly Dictionary<Vector2I, List<Vector3>> _block = new();
    private Random _rng = new(1);
    private Node3D _player = null!;
    private Basis _face, _sun;
    private Vector2 _right;
    private float _time;
    private Vector2 _last;
    private float _pspeed;
    private bool _offering, _settle;
    private static Shader? _shader;
    private static Godot.Collections.Dictionary? _manifest;

    public int Count => _beasts.Count;

    /// <summary>Every live Fauna, for `--faunacheck`. (FindChildren's type
    /// filter does not match C# script classes: it found none and the first
    /// check passed vacuously.)</summary>
    public static readonly List<Fauna> All = new();

    public void Bind(Node3D player, int seed)
    {
        _player = player;
        _rng = new Random(seed);
        All.Add(this);
        Bodies.All.Add(_bodies);
        _face = Basis.FromEuler(new Vector3(Mathf.DegToRad(-Foliage.TiltDeg), Mathf.DegToRad(CameraRig.BaseYaw), 0f));
        _sun = Basis.FromEuler(new Vector3(0f, Mathf.DegToRad(Grade.L.Yaw + 180f), 0f));
        var x = _face.X;
        _right = new Vector2(x.X, x.Z).Normalized();
    }

    /// <summary>A circle nothing on land walks through: a trunk, a post, a
    /// piece of a log.</summary>
    public override void _ExitTree()
    {
        All.Remove(this);
        Bodies.All.Remove(_bodies);
        if (_offering) Interact.Remove(Offer);
    }

    public void Block(Vector2 c, float r)
    {
        var k = Cell(c);
        if (!_block.TryGetValue(k, out var list)) _block[k] = list = new List<Vector3>();
        list.Add(new Vector3(c.X, c.Y, r));
        _settle = true;
    }

    /// <summary>Blockers came after the animals (every site adds its fences
    /// and props after `Add`): move anyone standing in one out, once. Found
    /// 2026-09-27: hens spawned on a fence row stood inside it until they
    /// walked (733 animal-frames); an every-frame push had hidden it.</summary>
    private void Settle()
    {
        _settle = false;
        foreach (var b in _beasts)
        {
            if (b.K.On != Medium.Land) continue;
            for (var i = 0; i < 4; i++)
            {
                Push(b.P, b.K.Radius - 0.05f, out var hit);
                if (!hit) break;
                var p = Push(b.P, b.K.Radius, out _);
                if (!Dry(p)) break;
                b.P = p;
            }
            if (!Fits(b.K, b.Home)) b.Home = b.P;
        }
    }

    /// <summary>A blow at `at` (<see cref="Impact.Shock"/>): everything within `r` bolts. A
    /// tame dog does not run from its friend.</summary>
    public void Scare(Vector2 at, float r)
    {
        foreach (var b in _beasts)
            if (!b.K.Tame && b.M is not (Mode.Flee or Mode.Jump) && (b.P - at).LengthSquared() < r * r)
                Bolt(b);
    }

    /// <summary>Into flight: fliers keep going a moment even once clear, and raise their
    /// flock's alarm.</summary>
    private void Bolt(Beast b)
    {
        b.M = Mode.Flee;
        b.T = b.K.Flies ? 1.4f + U() * 0.8f : 0f;
        if (b.K.Flies && _time - b.H.AlarmT > 3f) { b.H.AlarmAt = b.P; b.H.AlarmT = _time; }
    }

    /// <summary>A fence from `a` to `b`: blocker circles `r` wide, closer
    /// than their radius, so not even a hen slips between two (user,
    /// 2026-09-26: farm animals walked through the fences).</summary>
    public void BlockLine(Vector2 a, Vector2 b, float r)
    {
        var n = Mathf.Max(1, Mathf.CeilToInt((b - a).Length() / (r * 1.5f)));
        for (var i = 0; i <= n; i++) Block(a.Lerp(b, i / (float)n), r);
    }

    private static Vector2I Cell(Vector2 p) => new(Mathf.FloorToInt(p.X / 4f), Mathf.FloorToInt(p.Y / 4f));

    /// <summary>Move `p` out of every blocker it overlaps (radius `r`).
    /// Blockers are under 1.5 m, so the 3x3 neighbourhood of 4 m cells is
    /// enough.</summary>
    private Vector2 Push(Vector2 p, float r, out bool hit)
    {
        hit = false;
        for (var pass = 0; pass < 2; pass++)
        {
            var c0 = Cell(p);
            for (var i = -1; i <= 1; i++)
            for (var j = -1; j <= 1; j++)
            {
                if (!_block.TryGetValue(c0 + new Vector2I(i, j), out var list)) continue;
                foreach (var o in list)
                {
                    var c = new Vector2(o.X, o.Y);
                    var d = p - c;
                    var min = r + o.Z;
                    var l2 = d.LengthSquared();
                    if (l2 >= min * min) continue;
                    p = c + (l2 > 1e-8f ? d / Mathf.Sqrt(l2) : Vector2.Right) * min;
                    hit = true;
                }
            }
        }
        return p;
    }

    /// <summary>For `--faunacheck`: land animals on the ground standing
    /// inside a blocker (by more than 5 cm) or in the water, and swimmers or
    /// fish out of the deep. Must be 0.</summary>
    public int Violations()
    {
        var bad = 0;
        foreach (var b in _beasts)
        {
            if (b.Lift > 0.05f || b.M == Mode.Jump) continue;
            if (b.K.On == Medium.Land)
            {
                Push(b.P, b.K.Radius - 0.05f, out var hit);
                if (hit || !Dry(b.P)) bad++;
            }
            else if (!Deep(b.P)) bad++;
        }
        return bad;
    }

    /// <summary>For `--faunacheck`: blockers registered, metres walked by all
    /// animals -- a check where nothing moved proves nothing.</summary>
    /// <summary>Who is violating right now, for the check's report.</summary>
    public IEnumerable<string> Offenders()
    {
        foreach (var b in _beasts)
        {
            if (b.Lift > 0.05f || b.M == Mode.Jump) continue;
            var h = WorldGen.Height(b.P.X, b.P.Y);
            if (b.K.On == Medium.Land)
            {
                Push(b.P, b.K.Radius - 0.05f, out var hit);
                if (hit || !Dry(b.P)) yield return $"{b.K.Sprite} at {b.P} mode {b.M} blocked {hit} dry {Dry(b.P)} ground {h:F2}";
            }
            else if (!Deep(b.P)) yield return $"{b.K.Sprite} at {b.P} mode {b.M} ground {h:F2} water {Water:F2}";
        }
    }

    /// <summary>Small land animals within 0.5 m of a blocker's edge: the
    /// ones sheltering. For `--faunacheck`, sampled dry and in rain.</summary>
    public (int Near, int Of) Sheltered()
    {
        int near = 0, of = 0;
        foreach (var b in _beasts)
        {
            if (b.K.On != Medium.Land || b.K.Radius >= 0.35f || b.Lift > 0.05f) continue;
            of++;
            Push(b.P, b.K.Radius + 0.5f, out var hit);
            if (hit) near++;
        }
        return (near, of);
    }

    public (int Blockers, float Walked) Stats()
    {
        var n = 0;
        foreach (var l in _block.Values) n += l.Count;
        var w = 0f;
        foreach (var b in _beasts) w += b.Travel;
        return (n, w);
    }

    private bool Fits(Kind k, Vector2 p)
    {
        if (k.On != Medium.Land) return Deep(p);
        Push(p, k.Radius, out var hit);
        return !hit && Dry(p);
    }

    /// <summary>Add a species, one animal per home.</summary>
    public void Add(Kind k, IReadOnlyList<Vector2> homes)
    {
        homes = Bake.Homes(this, k, homes);   // a baked scene's herd (moved, added, removed homes)
        if (homes.Count == 0) return;
        _manifest ??= (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString(Dir + "manifest.json"));
        var info = (Godot.Collections.Dictionary)((Godot.Collections.Dictionary)_manifest["animals"])[k.Sprite];
        var m = (Godot.Collections.Array)info["metres"];
        var px = (Godot.Collections.Array)info["cell_px"];
        var frames = (Godot.Collections.Array)info["frames"];
        var size = new Vector2((float)m[0], (float)m[1]);
        var footM = (int)info["foot_px"] / (float)(int)px[1] * size.Y;
        var quad = new QuadMesh { Size = size, CenterOffset = new Vector3(0f, size.Y / 2f - footM, 0f) };

        _shader ??= new Shader { Code = Code };
        var img = Image.LoadFromFile(ProjectSettings.GlobalizePath(Dir + k.Sprite + ".png"));
        img.GenerateMipmaps();
        var mat = new ShaderMaterial { Shader = _shader };
        mat.SetShaderParameter("tex", ImageTexture.CreateFromImage(img));
        mat.SetShaderParameter("grid", new Vector2(frames.Count, 2));

        var herd = new Herd();
        for (var f = 0; f < frames.Count; f++) herd.Frame[(string)frames[f]] = f;
        if (k.Pet && !_offering)
        {
            Interact.Add(Offer);
            _offering = true;
        }
        herd.Face = Batch(k.Sprite, quad, mat, homes.Count, GeometryInstance3D.ShadowCastingSetting.Off);
        herd.Shadow = Batch(k.Sprite + "_shadow", quad, mat, homes.Count, GeometryInstance3D.ShadowCastingSetting.ShadowsOnly);
        herd.FaceBuf = new float[homes.Count * 16];
        herd.ShadowBuf = new float[homes.Count * 16];
        _herds.Add(herd);

        for (var i = 0; i < homes.Count; i++)
        {
            var home = k.On == Medium.Land ? Push(homes[i], k.Radius, out _) : homes[i];
            _beasts.Add(new Beast
            {
                K = k, H = herd, Slot = i, Id = _beasts.Count, P = home, Home = home, Goal = home,
                T = (float)_rng.NextDouble() * 4f, Row = _rng.Next(2),
            });
        }
    }

    private MultiMesh Batch(string name, Mesh quad, Material mat, int n, GeometryInstance3D.ShadowCastingSetting cast)
    {
        var mm = new MultiMesh
        {
            TransformFormat = MultiMesh.TransformFormatEnum.Transform3D,
            UseCustomData = true,
            Mesh = quad,
            InstanceCount = n,
        };
        AddChild(new MultiMeshInstance3D
        {
            Name = name, Multimesh = mm, MaterialOverride = mat, CastShadow = cast,
            PhysicsInterpolationMode = PhysicsInterpolationModeEnum.Off,
        });
        return mm;
    }

    private float U() => (float)_rng.NextDouble();

    private Vector2 Pick(Beast b)
    {
        // in rain the small ones make for the nearest trunk and sit under it
        if (Weather.Rain > 0.4f && b.K.On == Medium.Land && b.K.Radius < 0.35f && Shelter(b) is { } s) return s;
        for (var i = 0; i < 12; i++)
        {
            var t = U() * Mathf.Tau;
            var p = Keep(b.Home + new Vector2(Mathf.Cos(t), Mathf.Sin(t)) * b.K.Roam * Mathf.Sqrt(U()));
            if (Fits(b.K, p)) return p;
        }
        return b.Home;
    }

    /// <summary>A spot just outside the nearest blocker within 12 m.</summary>
    private Vector2? Shelter(Beast b)
    {
        var best = float.MaxValue;
        Vector2? at = null;
        var c0 = Cell(b.P);
        for (var i = -3; i <= 3; i++)
        for (var j = -3; j <= 3; j++)
        {
            if (!_block.TryGetValue(c0 + new Vector2I(i, j), out var list)) continue;
            foreach (var o in list)
            {
                var c = new Vector2(o.X, o.Y);
                var d = (b.P - c).Length();
                if (d > 12f || d >= best) continue;
                var spot = Keep(c + (d > 1e-3f ? (b.P - c) / d : Vector2.Right) * (o.Z + b.K.Radius + 0.15f));
                if (!Fits(b.K, spot)) continue;
                best = d;
                at = spot;
            }
        }
        return at;
    }

    public override void _Process(double delta)
    {
        if (_player == null) return;
        var dt = (float)delta;
        _time += dt;
        var pl = _player.GetGlobalTransformInterpolated().Origin;
        var me = new Vector2(pl.X, pl.Z);
        if (dt > 0f) _pspeed = Mathf.Lerp(_pspeed, (me - _last).Length() / dt, 0.3f);
        _last = me;
        if (_settle) Settle();
        _bodies.Clear();
        foreach (var b in _beasts)
            if (b.K.On == Medium.Land && b.Lift < 0.05f) _bodies.Add(b.P, b.K.Radius, b.Id);
        foreach (var b in _beasts) Step(b, me, dt);
        foreach (var h in _herds)
        {
            if (!h.Dirty) continue;
            h.Dirty = false;
            h.Face.Buffer = h.FaceBuf;
            h.Shadow.Buffer = h.ShadowBuf;
        }
    }

    private void Step(Beast b, Vector2 me, float dt)
    {
        var k = b.K;
        var you = me;
        // ponytail: past 110 m (Townsfolk.Near) nobody collides -- no one sees it
        var near = (b.P - you).LengthSquared() < 110f * 110f;
        if (Threat?.Invoke() is { } th && (b.P - th).LengthSquared() < (b.P - me).LengthSquared()) me = th;
        var away = b.P - me;
        var dist = away.Length();
        var scared = !k.Tame && dist < k.Fear && (!k.Skittish || _pspeed > PTune.WalkSpeed * 1.3f);
        // a flock's alarm reaches this bird: it goes up with the rest
        if (k.Flies && b.M is not (Mode.Flee or Mode.Jump) && b.Lift < 0.05f)
        {
            var since = _time - b.H.AlarmT;
            if (since < 3f && (b.P - b.H.AlarmAt).Length() < since * AlarmSpeed) scared = true;
        }
        if (b.M is not (Mode.Flee or Mode.Jump) && scared) Bolt(b);
        if (k.Tame)
        {
            // come to the player (to heel when following), then sit by them
            if (b.Follow > 0f) b.Follow -= dt;
            // it sits within heel + 0.5 m: inside the pet reach (2.2 m) when not
            // following. At + 0.6 with a 1.5 m heel it stopped ~2.1 m out, and
            // E never offered to pet it (2026-09-26 folk_pet capture).
            var heel = b.Follow > 0f ? 1.8f : 1.2f;
            if ((b.Follow > 0f || dist < 7f) && Keep(me) == me)
            {
                if (dist > heel + 0.5f && b.M != Mode.Walk) { b.Goal = me + away / Mathf.Max(dist, 0.01f) * heel; b.M = Mode.Walk; b.Stuck = 0f; }
                else if (b.M == Mode.Walk && dist > heel + 0.5f) b.Goal = me + away / Mathf.Max(dist, 0.01f) * heel;
                else if (dist <= heel + 0.5f && b.M == Mode.Walk) { b.M = Mode.Alt; b.T = 1.5f + U() * 2f; }
            }
        }

        var flying = k.Flies && b.Lift > 0.3f;
        var vel = Vector2.Zero;
        switch (b.M)
        {
            case Mode.Idle or Mode.Alt:
                // a duck left over land after fleeing goes straight back to the water
                if (k.On == Medium.Swim && !Deep(b.P)) b.T = 0f;
                if ((b.T -= dt) > 0f) break;
                // a jump carries a fish 1.3 m: only toward deep water, or it
                // lands in the shallows and strands (found by --faunacheck)
                var jt = U() * Mathf.Tau;
                var jd = new Vector2(Mathf.Cos(jt), Mathf.Sin(jt));
                if (k.On == Medium.Fish && U() < 0.35f && Deep(b.P + jd * 1.4f))
                {
                    b.Goal = jd;
                    b.M = Mode.Jump;
                    b.T = 0f;
                    Ripple?.Invoke(b.P, 1.4f);
                }
                else
                {
                    b.Goal = Pick(b);
                    b.M = Mode.Walk;
                    b.Stuck = 0f;
                }
                break;
            case Mode.Walk:
                var to = b.Goal - b.P;
                if (to.Length() < 0.3f || b.Stuck > 1.5f)
                {
                    b.M = U() < 0.6f ? Mode.Alt : Mode.Idle;
                    b.T = 2f + U() * 6f;
                }
                else vel = to.Normalized() * (flying || (k.Tame && b.Follow > 0f && dist > 4f) ? k.Run : k.Walk);
                break;
            case Mode.Flee:
                // (a bird raised by its flock's alarm flies its moment out even when clear)
                if (dist > k.Fear * 2.2f && (b.T -= dt) <= 0f)
                {
                    if (k.Flies && k.On == Medium.Land)
                    {
                        // a land bird circles back to its patch and settles there, as a
                        // flock of pigeons does, instead of dropping where it stopped
                        b.Goal = Pick(b);
                        b.M = Mode.Walk;
                        b.Stuck = 0f;
                        break;
                    }
                    b.M = Mode.Idle;
                    b.T = 1.5f + U() * 3f;
                    if (!k.Homing && k.On == Medium.Land) b.Home = Keep(b.P);
                }
                else vel = away / Mathf.Max(dist, 0.01f) * k.Run;
                break;
            case Mode.Jump:
                b.T += dt;
                vel = b.Goal * 1.4f;
                if (b.T >= 0.9f)
                {
                    b.M = Mode.Idle;
                    b.T = 3f + U() * 8f;
                    Ripple?.Invoke(b.P + vel * 0.1f, 1.4f);
                }
                break;
        }

        // Where it may go: land animals are pushed out of blockers and try
        // turning 50/100 degrees either way before giving up on a step, so a
        // trunk or the waterline is walked round, not into; swimmers and fish
        // stay in the deep. Fliers in the air go anywhere.
        var next = b.P + vel * dt;
        if (vel != Vector2.Zero && !flying && b.M != Mode.Jump)
        {
            var ok = false;
            foreach (var turn in Turns)
            {
                var v = vel.Rotated(turn) * dt;
                var c = b.P + v;
                if (k.On == Medium.Land)
                {
                    c = Push(c, k.Radius, out _);
                    // off the dry already (a home inside a blocker, pushed out onto
                    // the verge): any way back is allowed, as for a stranded swimmer
                    if ((!Dry(c) && Dry(b.P)) || (c - b.P).Length() < v.Length() * 0.3f) continue;
                    // people, other animals and the player are walked round like a
                    // trunk: a step that only slides back out of someone is no step
                    // (a dog behind a stander walked on the spot, 2026-09-27 folk_pet)
                    if (near)
                    {
                        var cb = Bodies.Out(Bodies.Push(c, k.Radius, _bodies, b.Id), you, k.Radius + Player.Radius);
                        if (cb != c)
                        {
                            // back out of the blockers, and refuse the step if a
                            // packed fence row still holds it (2 push passes do not
                            // always clear one: 681 animal-frames inside, 2026-09-27)
                            cb = Push(cb, k.Radius, out _);
                            Push(cb, k.Radius - 0.05f, out var still);
                            if (still || (!Dry(cb) && Dry(b.P)) || (cb - b.P).Dot(v) < v.LengthSquared() * 0.3f) continue;
                            c = cb;
                        }
                    }
                }
                else if (!Deep(c) && Deep(b.P)) continue;   // stranded: any way out is allowed
                next = c;
                ok = true;
                break;
            }
            if (!ok) next = b.P;
        }
        // shoved, when it is not walking: out of people, other animals and the
        // player (the player walking into a sitting dog moves it aside), then
        // back out of the blockers -- never into the water or off the street
        if (near && next == b.P && k.On == Medium.Land && !flying && b.M != Mode.Jump)
        {
            var s = Push(Bodies.Out(Bodies.Push(next, k.Radius, _bodies, b.Id), you, k.Radius + Player.Radius), k.Radius, out _);
            Push(s, k.Radius - 0.05f, out var still);
            if (!still && (Dry(s) || !Dry(next))) next = s;
        }
        var moved = (next - b.P).Length();
        if (b.M == Mode.Walk) b.Stuck = moved < k.Walk * dt * 0.3f ? b.Stuck + dt : 0f;
        var step = dt > 0f ? (next - b.P) / dt : Vector2.Zero;
        b.P = next;
        b.Travel += moved;

        // air: fliers rise when they flee, and a duck stays up until it is
        // back over deep water; taking off and landing both splash
        var wasUp = b.Lift > 0.05f;
        // a land bird over water (a gull that fled off the quay) stays up until it is over land again
        var want = k.Flies && (b.M == Mode.Flee || (k.On == Medium.Swim && !Deep(b.P)) || (k.On == Medium.Land && !Dry(b.P))
                               // flying home: stays up until it is over its landing spot
                               || (b.M == Mode.Walk && b.Lift > 0.05f && (b.Goal - b.P).LengthSquared() > 9f)) ? 5f : 0f;
        b.Lift = Mathf.MoveToward(b.Lift, want, 4f * dt);
        if (k.On == Medium.Swim && wasUp != b.Lift > 0.05f) Ripple?.Invoke(b.P, 1.0f);

        // ripples: a swimmer's wake, a fish's rise, a drinker's muzzle
        b.Wet += dt;
        if (k.On == Medium.Swim && b.Lift < 0.05f && moved > 0f && b.Wet > 0.45f) { Ripple?.Invoke(b.P, 0.45f); b.Wet = 0f; }
        else if (k.On == Medium.Fish && b.M != Mode.Jump && b.Wet > 1.6f) { Ripple?.Invoke(b.P, 0.12f); b.Wet = 0f; }
        else if (k.On == Medium.Land && b.M == Mode.Alt && FaceIdle is { } w && b.Wet > 1.8f)
        {
            Ripple?.Invoke(b.P + (w - b.P).Normalized() * 0.9f, 0.35f);
            b.Wet = 0f;
        }

        var sx = step.Dot(_right);
        if (Mathf.Abs(sx) > 0.05f) b.Row = sx > 0f ? 0 : 1;
        else if (moved == 0f && k.On == Medium.Land && FaceIdle is { } f) b.Row = (f - b.P).Dot(_right) > 0f ? 0 : 1;

        string fr;
        if (k.Flies && b.Lift > 0.05f) fr = ((int)(_time * 12f) & 1) == 0 ? "fly0" : "fly1";
        else if (b.M == Mode.Jump) fr = b.T < 0.3f ? "jump0" : b.T < 0.6f ? "jump1" : "jump2";
        else if (moved > 0f) fr = "walk" + ((int)(b.Travel / (k.Stride * (b.M == Mode.Flee ? 1.8f : 1f))) & 3);
        else fr = b.M == Mode.Alt ? k.Alt : "idle";

        if (moved == 0f && k.Pet && dist < 4f) b.Row = (me - b.P).Dot(_right) > 0f ? 0 : 1;
        var y = k.On switch
        {
            Medium.Land => Ground?.Invoke(b.P) ?? WorldGen.Height(b.P.X, b.P.Y),
            Medium.Swim => Water,
            _ => b.M == Mode.Jump ? Water - 0.15f + Mathf.Sin(Mathf.Pi * b.T / 0.9f) * 0.9f : Water - 0.4f,
        } + b.Lift;
        var at = new Vector3(b.P.X, y, b.P.Y);
        // wet land animals near the player drip from the belly
        if (k.On == Medium.Land && Weather.Damp > 0.2f && b.Lift < 0.05f && dist < 25f && U() < Weather.Damp * dt * 6f)
            Weather.Drip(at + new Vector3(_right.X, 0f, _right.Y) * (U() - 0.5f) * k.Radius * 2f + Vector3.Up * k.Radius * 1.6f,
                         Vector3.Down * 0.3f);
        var cell = new Color(b.H.Frame[fr], b.Row, 0f, 0f);
        Townsfolk.Put(b.H.FaceBuf, b.Slot, _face, at, cell);
        Townsfolk.Put(b.H.ShadowBuf, b.Slot, _sun, at, cell);
        b.H.Dirty = true;
    }

    /// <summary>Where each animal of one species stands (camtest frames one).</summary>
    /// <summary>Whether animal `ix` of one species is still following after a
    /// pet, for the harness.</summary>
    public bool Following(string sprite, int ix)
    {
        foreach (var b in _beasts)
            if (b.K.Sprite == sprite && ix-- == 0) return b.Follow > 0f;
        return false;
    }

    /// <summary>What each animal of one species is doing, for the harness.</summary>
    public IEnumerable<string> Doing(string sprite)
    {
        foreach (var b in _beasts)
            if (b.K.Sprite == sprite)
                yield return $"{b.M} pspeed {_pspeed:F1} dry {Dry(b.P)} stuck {b.Stuck:F1} to goal {(b.Goal - b.P).Length():F1} follow {b.Follow:F0}";
    }

    public IEnumerable<Vector3> Where(string sprite)
    {
        foreach (var b in _beasts)
            if (b.K.Sprite == sprite)
                yield return new Vector3(b.P.X, Ground?.Invoke(b.P) ?? WorldGen.Height(b.P.X, b.P.Y), b.P.Y);
    }

    /// <summary>This system's own pet offer, bypassing the closest-wins
    /// choice (the harness pets a dog even with a person nearer).</summary>
    public Interact.Offer? OfferFor(Vector2 me) => Offer(me);

    /// <summary>The nearest petable animal within reach, for the E key.</summary>
    private Interact.Offer? Offer(Vector2 me)
    {
        Beast? best = null;
        var bd = 2.2f;
        foreach (var b in _beasts)
        {
            if (!b.K.Pet || b.M == Mode.Flee || b.Lift > 0.05f) continue;
            var d = (b.P - me).Length();
            if (d < bd) { bd = d; best = b; }
        }
        if (best == null) return null;
        var who = best;
        var name = who.K.Sprite.Split('_')[0];
        return new Interact.Offer(bd + 0.3f, "E: pet the " + name, () => Pet(who));
    }

    private void Pet(Beast b)
    {
        b.M = Mode.Alt;
        b.T = 2.5f + U() * 2f;
        if (b.K.Tame) b.Follow = 25f;
        var y = Ground?.Invoke(b.P) ?? WorldGen.Height(b.P.X, b.P.Y);
        Townsfolk.Heart(this, new Vector3(b.P.X, y + b.K.Radius * 2.2f + 0.3f, b.P.Y));
    }

    private static readonly float[] Turns =
    {
        0f, Mathf.DegToRad(50f), Mathf.DegToRad(-50f), Mathf.DegToRad(100f), Mathf.DegToRad(-100f),
    };

    private const string Code = @"
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_disabled, cull_disabled, shadows_disabled;

uniform sampler2D tex : source_color, filter_nearest_mipmap;
uniform vec2 grid;
global uniform float wetness;   // Weather.Damp: soaked fur is darker, a touch cooler
varying flat vec2 cell;

void vertex() {
    cell = INSTANCE_CUSTOM.xy;
}

void fragment() {
    vec4 c = texture(tex, (cell + UV) / grid);
    ALBEDO = c.rgb * (1.0 - wetness * vec3(0.24, 0.22, 0.15));
    ALPHA = c.a;
    ALPHA_SCISSOR_THRESHOLD = 0.5;
    ROUGHNESS = 1.0;
}
";
}
