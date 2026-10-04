using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The HD-2D camera: pitch welded to the sprite bake, discrete zoom, and a yaw
/// that leaves its base only to look down a city street.
///
/// The base yaw is not a limitation being tolerated, it is the thing being
/// bought -- Octopath's director is explicit that a camera which cannot rotate
/// is what lets a map be built correct from exactly one bearing, and both games
/// in the reference set that gave it up (Octopath II, Triangle Strategy) say in
/// print what it cost them. Plants, animals, weather and the village kit are
/// authored against <see cref="BaseYaw"/>. The one exception (user, 2026-09-24):
/// inside Emberglass's wall, whose buildings are finished on all four sides, the
/// camera turns to look down the street the player is in -- at an 8 deg pitch
/// and ~20 m back the camera only sits inside a 6 m street within ~9 deg of its
/// axis, so the turn is a full one. The sprites follow: facing and tilt read
/// the live yaw.
///
/// The pitch equals the bake elevation for the same reason as before: these
/// sprites show their own top-of-helm, so they only sit on the ground at the
/// angle they were drawn from.
///
/// Everything else that moves the frame -- lead, peek, breathing, landmark
/// pull, the street's centreline -- moves the camera in its OWN IMAGE PLANE
/// (its right and up axes) and never along its view axis: the player's depth
/// from the lens stays the standoff, so one sprite texel stays one screen pixel.
/// Only the zoom ease crosses that line, and only between the two integer steps.
/// The street yaw pivots on the aim point, which keeps the standoff too.
/// </summary>
public partial class CameraRig : Node3D
{
    /// <summary>The frame the camera is composed for; the window upscales from
    /// it. 720 with a 96 px sprite puts the character at 13.3 percent of frame
    /// height -- dead centre of the references' 11-16 percent (Law 6) -- and
    /// makes one sprite texel exactly one screen pixel at the project's own
    /// 1280x720 render target.</summary>
    public const float NominalHeightPx = 720f;

    /// <summary>The bearing everything is authored against. Build-time quads
    /// (plants, animals) read this, never the live yaw.</summary>
    public const float BaseYaw = 45f;

    /// <summary>The live yaw in degrees, for code without a rig reference
    /// (the weather's particle boxes). Equals <see cref="BaseYaw"/> outside
    /// city streets.</summary>
    public static float LiveYaw { get; private set; } = BaseYaw;

    /// <summary>38, wider than the 30 this started at, and the pair with the
    /// 14-degree pitch. A horizon is in frame if and only if `pitch < halfFov`;
    /// 14 against 19 puts it comfortably inside, which is what makes buildings
    /// present their fronts instead of their roofs.</summary>
    public const float Fov = 38f;

    /// <summary>The two camera angles, taken from the two sprite bakes. The
    /// pitch sits on one or the other, and only passes between them during a
    /// blend.</summary>
    public float LowDeg { get; set; } = 8f;
    public float TopDeg { get; set; } = 38f;

    /// <summary>Seconds for a full low-to-top blend.</summary>
    [Export] public float BlendTime { get; set; } = 1.1f;

    /// <summary>The zone rule: given the player's position and whether the
    /// camera is currently low, should it be low? The hysteresis lives in the
    /// rule (an inner box to enter, an outer box to leave), so the camera cannot
    /// flip-flop on a boundary. Null means top-down everywhere.</summary>
    public System.Func<Vector3, bool, bool>? WantsLow { get; set; }

    /// <summary>The street under a world position: a road id, or -1 where the
    /// camera should hold its base yaw. Null: no street view anywhere.</summary>
    public System.Func<Vector3, int>? StreetId { get; set; }
    /// <summary>That road's axis at a world position: unit tangent and the
    /// nearest centreline point, both world XZ.</summary>
    public System.Func<Vector3, int, (Vector2 Dir, Vector2 Foot)>? StreetAxis { get; set; }

    private float _blend = 1f;   // 0 = low, 1 = top
    private bool _low;
    /// <summary>Sprite world height and its pixel height, from the manifest.
    /// Together they fix the standoff that makes one sprite texel exactly one
    /// screen pixel -- the check the audit failed at 0.863.</summary>
    [Export] public float SpriteWorldH { get; set; } = 1.85f;
    [Export] public int SpritePx { get; set; } = 48;

    /// <summary>x1 or x2 only at rest. A continuous zoom cannot hold
    /// texel:pixel at an integer, and a sprite minified by 1.37 shimmers
    /// whenever it moves. x1 puts one sprite texel on exactly one screen pixel
    /// at the project's 1280x720 target, with the character at 13.3 percent of
    /// frame height -- Law 6. x2 doubles both. Keys 1 and 2, eased over
    /// <see cref="ZoomTime"/>.</summary>
    [Export] public int Zoom { get; set; } = 1;
    private const float ZoomTime = 0.35f;

    /// <summary>How far ABOVE the player the camera aims, in world units.
    ///
    /// This does NOT control how much sky is in frame -- that is
    /// `(halfFov - pitch) / (2 * halfFov)` and nothing else, because translating
    /// a camera up leaves an infinite plane's horizon exactly where it was. It
    /// was raised to 2.2 for that reason and it did nothing; the pitch had to
    /// come down instead. What it does do is sit the character slightly below
    /// centre, which leaves room ahead of them.</summary>
    [Export] public float TargetHeight { get; set; } = 1.2f;

    // ---- follow: summer-cycle's chase split (position 4.5/s, height 3/s).
    // One rate of 9 did both before, and at 9.5 m/s it trailed the player by
    // v/9 = 1.06 m -- less room ahead than behind, the opposite of a lead.
    private const float FollowH = 4.5f, FollowV = 3f;
    // ---- lead (Keren's projected focus): v x 0.35 s, at most 3 m (~12 % of
    // the frame's width), smoothed at 2.5/s so a reversal swings the frame over
    // about a second (dual forward focus) instead of snapping. Ground-forward
    // lead maps onto the camera's up axis at half strength.
    private const float LeadTime = 0.35f, LeadMax = 3f, LeadRate = 2.5f, LeadUp = 0.5f;
    /// <summary>Platform snap (Mario World, via Keren): the frame follows the
    /// ground height only while grounded; in the air only past this band.</summary>
    private const float SnapBand = 2.5f;
    // ---- peek: right-drag or the right stick, up to 4 x 2.5 m, easing back
    // after 1.5 s of no input at 1.4/s (summer-cycle's LOOK_IDLE and rate).
    private static readonly Vector2 PeekMax = new(4f, 2.5f);
    private const float PeekPerPx = 0.02f, PeekStick = 8f, PeekIdle = 1.5f, PeekReturn = 1.4f;
    /// <summary>Idle breathing: two slow sines once the player has stood still
    /// for 2 s, ~2 px at x1. OFF: measured 2026-09-24 it doubled the idle
    /// frame's pixel churn (46.6 % of pixels moving > 8/255 in 1 s against
    /// 22.5 % without) -- a whole-frame crawl on nearest-filtered textures.
    /// `--breathe` turns it on for A/B.</summary>
    public static bool Breathe;
    /// <summary>Street view: yaw ease (a full 90 deg in about a second),
    /// junction and leaving holds, and how far the aim slides onto the street's
    /// centreline (nanobanna's StreetCamera, reference only).</summary>
    private const float YawRate = 2.2f, SwitchHold = 0.4f, LeaveHold = 0.6f, Centreline = 0.85f;
    /// <summary>All framing offsets together stay inside this, so the player
    /// never leaves the middle of a 24 m wide frame.</summary>
    private const float OffsetMax = 4.5f;
    // ---- shake (Eiserloh): trauma in [0,1], linear decay, shake = trauma^2,
    // rotational only -- translational shake in 3D is "VERY BAD".
    private const float TraumaDecay = 1.5f, ShakeHz = 12f;
    private static readonly Vector3 ShakeDeg = new(0.3f, 0.5f, 1.2f);   // pitch, yaw, roll at trauma 1

    /// <summary>A place the frame leans toward when the player is near: the
    /// feathered proximity between `Inner` and `Outer` times `Weight`, averaged
    /// with the player at weight 1 (Eiserloh's points of interest).</summary>
    public readonly record struct Interest(Vector3 At, float Inner, float Outer, float Weight);
    public static readonly List<Interest> Interests = new();
    private const float PullMax = 3f;

    public Camera3D Camera { get; private set; } = null!;
    private Node3D _target = null!;
    private Vector3 _at;
    private float _yaw = BaseYaw, _sign = 1f;
    private int _road = -1, _cand = -1;
    private float _candT, _leaveT, _streetW;
    private Vector2 _foot, _dir;
    private Vector3 _lead;
    private float _refY = float.NaN;
    private Vector2 _peek, _peekS;
    private float _peekT = 99f, _still, _breathW, _t, _trauma;
    private float _dCur = -1f, _dFrom, _zK = 1f;
    private int _zoomWas = 1;
    private readonly FastNoiseLite _noise = new() { NoiseType = FastNoiseLite.NoiseTypeEnum.Perlin, Frequency = 1f, Seed = 7 };
    private float _near0, _nearT0, _far0;

    /// <summary>Smoothstepped blend, 0 low to 1 top. The sun follows it.</summary>
    public float Blend => _blend * _blend * (3f - 2f * _blend);
    /// <summary>Which bake the character should show: the one whose angle the
    /// camera is nearer.</summary>
    public bool TopSet => _blend >= 0.5f;
    public float PitchRad => Mathf.DegToRad(PitchOverride ?? Mathf.Lerp(LowDeg, TopDeg, Blend));
    /// <summary>The live yaw without shake: sprite facing and tilt read this.</summary>
    public float YawRad => Mathf.DegToRad(_yaw);

    public void Track(Node3D target)
    {
        _target = target;
        var p = target.GlobalPosition;
        _refY = p.Y;
        _at = p + Vector3.Up * TargetHeight;
        _lead = Vector3.Zero;
        GlobalPosition = _at;
    }

    /// <summary>`--camsweep` only: hold the pitch (deg) and the standoff (m)
    /// here. Breaks the sprite bake's weld and texel:pixel on purpose -- it is
    /// a composition study, not play.</summary>
    public float? PitchOverride, StandoffOverride;

    /// <summary>The street the camera is committed to (-1: none). Tests read it.</summary>
    public int Road => _road;

    // ------------------------------------------------------------------ reveal
    // Camera plan Phase 5: on first entering a region the frame opens on its
    // landmark and eases back to the player -- at most 3 s, input held,
    // any key skips it. The aim point is what moves (a pan across the
    // ground); the yaw, pitch and standoff never change, so texel 1:1 holds
    // the whole way and no arc is needed. Plain play only (no command-line
    // flags): captures, benches and tests never see one.
    public static bool RevealsOn;
    /// <summary>A reveal is running: Player ignores its keys.</summary>
    public static bool Revealing;
    private Vector3 _revealFrom;
    private float _revealT = -1f, _revealDur;

    /// <summary>Open the frame on `landmark` (an aim point in the world) and
    /// ease to the player over `dur` seconds (clamped to 3).</summary>
    public void Reveal(Vector3 landmark, float dur = 2.6f)
    {
        _revealFrom = landmark;
        _revealDur = Mathf.Clamp(dur, 0.5f, 3f);
        _revealT = 0f;
        Revealing = true;
    }

    /// <summary>Add camera trauma (0..1): a hard landing, a hit.</summary>
    public void AddTrauma(float t) => _trauma = Mathf.Min(1f, _trauma + t);

    public override void _Ready()
    {
        // The rig repositions itself every rendered frame in _Process, not on
        // a physics tick. Physics interpolation would smooth it between ticks
        // it never moved on, dragging it a tick behind its own target.
        PhysicsInterpolationMode = PhysicsInterpolationModeEnum.Off;

        var dof = Grade.Dof();
        _near0 = dof.DofBlurNearDistance;
        _nearT0 = dof.DofBlurNearTransition;
        _far0 = dof.DofBlurFarDistance;
        Camera = new Camera3D
        {
            Name = "Camera",
            Fov = Fov,
            Far = 1400f,
            Current = true,
            Attributes = dof,
        };
        AddChild(Camera);
        _dCur = Standoff();
        Place(Vector3.Zero);
    }

    /// <summary>Distance at which `SpritePx` sprite pixels cover `SpritePx`
    /// screen pixels of a NominalHeightPx-tall frame, at zoom `z`.</summary>
    public float Standoff(int z = 0)
    {
        var visible = SpriteWorldH * NominalHeightPx / SpritePx / (z > 0 ? z : Zoom);
        return visible / (2f * Mathf.Tan(Mathf.DegToRad(Fov) * 0.5f));
    }

    /// <summary>Re-place the camera after the manifest's numbers arrive.
    ///
    /// `_Ready` runs before `Player.Bind` hands over the bake elevation and the
    /// sprite's pixel height, so the first Place() used the class defaults --
    /// 48 px against a real 96 -- and the composition came out at exactly half
    /// the intended zoom. Measured 12.2 percent of frame height where the maths
    /// said 26.7. Anything that writes those fields calls this.</summary>
    public void Recompose()
    {
        // Snap, no blend: a spawn inside the outskirts starts low.
        if (_target != null && WantsLow != null)
        {
            _low = WantsLow(_target.GlobalPosition, false);
            _blend = _low ? 0f : 1f;
        }
        _dCur = Standoff();
        _zK = 1f;
        Place(Vector3.Zero);
    }

    private void Place(Vector3 shake)
    {
        var p = PitchRad;
        var y = YawRad;
        var back = new Vector3(Mathf.Sin(y), 0f, Mathf.Cos(y));
        Camera.Position = back * (_dCur * Mathf.Cos(p)) + Vector3.Up * (_dCur * Mathf.Sin(p));
        Camera.Rotation = new Vector3(-p + shake.X, y + shake.Y, shake.Z);
    }

    public override void _UnhandledInput(InputEvent e)
    {
        if (e is InputEventMouseMotion m && (m.ButtonMask & MouseButtonMask.Right) != 0)
        {
            _peek = (_peek + new Vector2(m.Relative.X, -m.Relative.Y) * PeekPerPx).Clamp(-PeekMax, PeekMax);
            _peekT = 0f;
        }
    }

    public override void _Process(double delta)
    {
        if (_target == null) return;
        var dt = (float)delta;
        _t += dt;

        var body = _target as CharacterBody3D;
        // GetGlobalTransformInterpolated(), not GlobalPosition: GlobalPosition
        // only changes on a physics tick (60 Hz), so following it directly is
        // following a 60 Hz staircase under a faster display.
        var at = _target.GetGlobalTransformInterpolated().Origin;
        var grounded = body == null || body.IsOnFloor();
        var vel = body?.Velocity ?? Vector3.Zero;
        vel.Y = 0f;

        // Platform snap: a jump no longer bobs the whole frame.
        if (float.IsNaN(_refY) || grounded) _refY = at.Y;
        else if (at.Y > _refY + SnapBand) _refY = at.Y - SnapBand;
        else if (at.Y < _refY) _refY = at.Y;
        var P = new Vector3(at.X, _refY + TargetHeight, at.Z);

        Street(at, dt);
        LiveYaw = _yaw;

        if (WantsLow != null)
        {
            _low = WantsLow(_target.GlobalPosition, _low);
            _blend = Mathf.MoveToward(_blend, _low ? 0f : 1f, dt / BlendTime);
        }

        // The image plane at the current yaw and pitch, before shake.
        var basis = Basis.FromEuler(new Vector3(-PitchRad, YawRad, 0f));
        var r = basis.X;
        var u = basis.Y;
        var hf = new Vector3(-Mathf.Sin(YawRad), 0f, -Mathf.Cos(YawRad));

        // Lead, plus the follow's own trailing lag (v / rate) cancelled, so at
        // a steady run the player sits the whole lead behind centre.
        var want = vel * LeadTime;
        if (want.Length() > LeadMax) want = want.Normalized() * LeadMax;
        _lead = _lead.Lerp(want, 1f - Mathf.Exp(-LeadRate * dt));
        var off = new Vector2(_lead.Dot(r), _lead.Dot(hf) * LeadUp);
        // (the lag cancel is added after the OffsetMax cap: capped with the
        // framing, it ate the lead -- measured 5-8 % instead of 12 %)
        var lag = new Vector2(vel.Dot(r) / FollowH, vel.Dot(u) / FollowV);

        // In a street, the aim slides toward the centreline: a player hugging a
        // wall would otherwise point the lens into it.
        if (_streetW > 0f)
        {
            var n = new Vector3(-_dir.Y, 0f, _dir.X);
            var s = new Vector2(at.X - _foot.X, at.Z - _foot.Y).Dot(new Vector2(n.X, n.Z));
            off.X += (-Centreline * s * _streetW * n).Dot(r);
        }

        // Landmark pull.
        var pull = Pull(P);
        off += new Vector2(pull.Dot(r), pull.Dot(u));

        // Peek: the right stick, or right-drag (_UnhandledInput).
        var sx = Input.GetJoyAxis(0, JoyAxis.RightX);
        var sy = Input.GetJoyAxis(0, JoyAxis.RightY);
        if (Mathf.Abs(sx) > 0.2f || Mathf.Abs(sy) > 0.2f)
        {
            _peek = (_peek + new Vector2(sx, -sy) * PeekStick * dt).Clamp(-PeekMax, PeekMax);
            _peekT = 0f;
        }
        _peekT += dt;
        if (_peekT > PeekIdle) _peek *= Mathf.Exp(-PeekReturn * dt);
        _peekS = _peekS.Lerp(_peek, 1f - Mathf.Exp(-10f * dt));

        // Idle breathing: fades in over 1.5 s after 2 s still, out in ~0.3 s.
        _still = vel.LengthSquared() > 0.04f || !grounded ? 0f : _still + dt;
        var bw = Breathe && _still > 2f ? 1f : 0f;
        _breathW = Mathf.MoveToward(_breathW, bw, dt * (bw > 0f ? 1f / 1.5f : 3f));
        off += new Vector2(0.04f * Mathf.Sin(Mathf.Tau * _t / 9.1f), 0.03f * Mathf.Sin(Mathf.Tau * _t / 3.3f + 1.1f)) * _breathW;

        // Automatic framing is capped; the peek is the player's own input and
        // rides on top (capped with it, a landmark's pull ate 1.3 of a 3 m peek).
        off = off.LimitLength(OffsetMax) + _peekS + lag;

        // Follow in the image plane only. The previous aim is re-expressed
        // against the current player and basis; its depth part is dropped, so
        // the player's distance from the lens is exactly the standoff.
        var rel = _at - P;
        var x = rel.Dot(r);
        var y = rel.Dot(u);
        x = off.X + (x - off.X) * Mathf.Exp(-FollowH * dt);
        y = off.Y + (y - off.Y) * Mathf.Exp(-FollowV * dt);
        _at = P + r * x + u * y;
        GlobalPosition = _at;
        if (_revealT >= 0f)
        {
            // held on the landmark for 0.4 s, then a quintic ease to the aim
            _revealT += dt;
            var k = Mathf.Clamp((_revealT - 0.4f) / (_revealDur - 0.4f), 0f, 1f);
            var e = k * k * k * (k * (k * 6f - 15f) + 10f);
            GlobalPosition = _revealFrom.Lerp(_at, e);
            if (k >= 1f || (_revealT > 0.3f && Input.IsAnythingPressed()))
            {
                _revealT = -1f;
                Revealing = false;
                GlobalPosition = _at;
            }
        }

        // Zoom: keys 1 and 2, eased (quintic smootherstep, summer-cycle's).
        if (Input.IsPhysicalKeyPressed(Key.Key1)) Zoom = 1;
        if (Input.IsPhysicalKeyPressed(Key.Key2)) Zoom = 2;
        if (Zoom != _zoomWas) { _zoomWas = Zoom; _dFrom = _dCur; _zK = 0f; }
        if (StandoffOverride is { } so && !Mathf.IsEqualApprox(so, _dCur)) { _dCur = so; _zK = 0.999f; _dFrom = so; }
        if (_zK < 1f)
        {
            _zK = Mathf.Min(1f, _zK + dt / ZoomTime);
            var e = _zK * _zK * _zK * (_zK * (_zK * 6f - 15f) + 10f);
            _dCur = StandoffOverride ?? Mathf.Lerp(_dFrom, Standoff(), e);
            // The sharp band follows the player: at x1 these are exactly the
            // shipped Grade.Dof() numbers.
            if (Camera.Attributes is CameraAttributesPractical a)
            {
                var k = _dCur / Standoff(1);
                a.DofBlurNearDistance = _near0 * k;
                a.DofBlurNearTransition = _nearT0 * k;
                a.DofBlurFarDistance = _far0 + (_dCur - Standoff(1));
            }
        }

        // Shake.
        _trauma = Mathf.MoveToward(_trauma, 0f, TraumaDecay * dt);
        var sh = Vector3.Zero;
        if (_trauma > 0f)
        {
            var s2 = _trauma * _trauma;
            sh = new Vector3(_noise.GetNoise2D(_t * ShakeHz, 0f) * ShakeDeg.X,
                             _noise.GetNoise2D(_t * ShakeHz, 50f) * ShakeDeg.Y,
                             _noise.GetNoise2D(_t * ShakeHz, 100f) * ShakeDeg.Z)
                 // Perlin sits mostly inside +-0.5, so x2 makes ShakeDeg the peak
                 * (s2 * Mathf.Pi / 180f * 2f);
        }
        Place(sh);
    }

    /// <summary>Which street the camera looks down, with holds so a junction
    /// or a step onto the verge does not swing it, then the yaw eased toward
    /// that street's axis -- whichever of its two directions is the smaller
    /// turn, kept while on the same street so a curve never flips it.</summary>
    private void Street(Vector3 at, float dt)
    {
        var id = StreetId?.Invoke(at) ?? -1;
        if (id == _road) { _cand = -1; _candT = 0f; _leaveT = 0f; }
        else if (id < 0)
        {
            _cand = -1; _candT = 0f;
            _leaveT += dt;
            if (_leaveT >= LeaveHold) _road = -1;
        }
        else
        {
            _leaveT = 0f;
            if (id != _cand) { _cand = id; _candT = 0f; }
            _candT += dt;
            if (_candT >= SwitchHold)
            {
                _road = id;
                _cand = -1;
                _candT = 0f;
                // choose the direction now, and keep it on this street
                var (d, _) = StreetAxis!(at, _road);
                var a = Mathf.RadToDeg(Mathf.Atan2(-d.X, -d.Y));
                var da = Mathf.Abs(Mathf.Wrap(a - _yaw, -180f, 180f));
                var db = Mathf.Abs(Mathf.Wrap(a + 180f - _yaw, -180f, 180f));
                _sign = Mathf.Abs(da - db) < 1f
                    ? (Mathf.Abs(Mathf.Wrap(a - BaseYaw, -180f, 180f)) <= 90f ? 1f : -1f)
                    : da <= db ? 1f : -1f;
            }
        }

        var goal = BaseYaw;
        if (_road >= 0 && StreetAxis != null)
        {
            (_dir, _foot) = StreetAxis(at, _road);
            goal = Mathf.RadToDeg(Mathf.Atan2(-_dir.X * _sign, -_dir.Y * _sign));
        }
        _streetW = Mathf.MoveToward(_streetW, _road >= 0 ? 1f : 0f, dt * 2f);
        _yaw = Mathf.Wrap(_yaw + Mathf.Wrap(goal - _yaw, -180f, 180f) * (1f - Mathf.Exp(-YawRate * dt)), -180f, 180f);
    }

    private static Vector3 Pull(Vector3 p)
    {
        var sum = Vector3.Zero;
        var w = 0f;
        foreach (var i in Interests)
        {
            var d = i.At - p;
            var dist = d.Length();
            if (dist >= i.Outer) continue;
            var k = (1f - Mathf.SmoothStep(i.Inner, i.Outer, dist)) * i.Weight;
            sum += d * k;
            w += k;
        }
        return w <= 0f ? Vector3.Zero : (sum / (1f + w)).LimitLength(PullMax);
    }

    /// <summary>The 8 facing index for a world-space heading, seen from this
    /// camera. `current` and the hysteresis keep a heading sitting on a
    /// boundary from flickering between two sprites.</summary>
    public int FacingFor(Vector3 dir, int current)
    {
        if (dir.LengthSquared() < 1e-6f) return current;
        // Angle of travel in the camera's own frame. 0 = toward the camera (s).
        var a = Mathf.Atan2(dir.X, dir.Z) - YawRad;
        var deg = Mathf.PosMod(Mathf.RadToDeg(a), 360f);
        var idx = Mathf.PosMod(Mathf.RoundToInt(deg / 45f), 8);
        if (idx == current) return current;
        var centre = current * 45f;
        var off = Mathf.Abs(Mathf.Wrap(deg - centre, -180f, 180f));
        return off < 22.5f + PTune.FacingHysteresis ? current : idx;
    }

    /// <summary>`--camcheck`: the pure maths above, asserted. Street direction
    /// is the least turn and a tie keeps the base side; the landmark pull is
    /// zero outside its radius, points at the landmark inside, and is capped.</summary>
    public static int SelfCheck()
    {
        var fails = 0;
        void Check(bool ok, string what) { if (!ok) { fails++; GD.PrintErr("camcheck FAIL: " + what); } }

        // A street along world +X seen from yaw 45: looking along +X is yaw -90
        // (135 deg away), along -X is yaw 90 (45 away) -> the -X direction.
        var rig = new CameraRig();
        rig.StreetId = _ => 0;
        rig.StreetAxis = (_, _) => (new Vector2(1f, 0f), Vector2.Zero);
        for (var i = 0; i < 120; i++) rig.Street(Vector3.Zero, 1f / 60f);
        Check(Mathf.Abs(Mathf.Wrap(rig._yaw - 90f, -180f, 180f)) < 5f, $"street +X from 45 settles at 90 (got {rig._yaw:F1})");
        // Worst case, a street square to the base view (both ways 90 deg off):
        // the tie keeps the side nearer the base, and the yaw is within 9 deg
        // of the axis inside 1.2 s of committing.
        var r2 = new CameraRig { StreetId = _ => 0, StreetAxis = (_, _) => (new Vector2(0.70710678f, -0.70710678f), Vector2.Zero) };
        var hit = -1f;
        for (var i = 1; i <= 240 && hit < 0f; i++)
        {
            r2.Street(Vector3.Zero, 1f / 60f);
            if (r2._road >= 0 && Mathf.Abs(Mathf.Wrap(r2._yaw + 45f, -180f, 180f)) < 9f) hit = i / 60f;
        }
        Check(hit > 0f && hit - SwitchHold <= 1.2f, $"square street: within 9 deg of yaw -45 {hit - SwitchHold:F2} s after the hold");
        // A junction blip shorter than the hold does not switch.
        var r3 = new CameraRig { StreetAxis = (_, id) => (id == 0 ? new Vector2(1f, 0f) : new Vector2(0f, 1f), Vector2.Zero) };
        r3.StreetId = _ => 0;
        for (var i = 0; i < 60; i++) r3.Street(Vector3.Zero, 1f / 60f);
        r3.StreetId = _ => 1;
        for (var i = 0; i < 15; i++) r3.Street(Vector3.Zero, 1f / 60f);
        Check(r3._road == 0, "a 0.25 s blip onto another street does not switch");
        rig.Free(); r2.Free(); r3.Free();

        var live = new List<Interest>(Interests);
        Interests.Clear();
        Interests.Add(new Interest(new Vector3(10f, 0f, 0f), 2f, 20f, 0.3f));
        Check(Pull(new Vector3(40f, 0f, 0f)) == Vector3.Zero, "no pull outside the outer radius");
        var pl = Pull(Vector3.Zero);
        Check(pl.X > 0f && pl.Length() <= PullMax + 1e-4f, $"pull points at the landmark and is capped ({pl})");
        Interests.Clear();
        Interests.AddRange(live);

        GD.Print(fails == 0 ? "camcheck: PASS" : $"camcheck: FAIL ({fails})");
        return fails;
    }
}
