using Godot;

namespace Worldbuilder;

/// <summary>
/// The player: a capsule collider that moves, with the sprite rig drawing it and
/// a state machine deciding which strip plays.
///
/// The collider stays a capsule -- the figure is a picture, and a picture has no
/// useful collision shape. What the sprite does is decide what the player SEES,
/// and the two only have to agree about the feet.
///
/// Feel lives in `PTune`, not here: this file is the machine, that file is the
/// numbers. The rules that make the movement read as natural are all of the
/// "grace" kind -- coyote time, a buffered jump, a cancel window on the swing,
/// squash on the landing -- and each one exists because its absence is felt as
/// the character being unresponsive rather than as a missing feature.
/// </summary>
public partial class Player : CharacterBody3D
{
    private const float Height = 1.6f;
    public const float Radius = 0.35f;

    private SpriteRig _rig = null!;
    private CameraRig _cam = null!;
    private MeshInstance3D _shadow = null!;

    private PState _state = PState.Idle;
    private float _stateTime;
    private int _facing;
    private Vector3 _heading = Vector3.Forward;

    private float _coyote;
    private float _jumpBuffer;
    private float _attackBuffer;
    private float _dashCooldown;
    private float _airTime;
    private bool _airDashSpent;
    private bool _jumpHeld;
    private bool _chainQueued;
    private float _hitstop;
    private Vector2 _squash = Vector2.One;
    private Vector3 _lockedVelocity;
    /// <summary>This swing's blow has been dealt (once per swing, at PTune.SwingAt).</summary>
    private bool _swung;
    /// <summary>What the feet were last on, and how far the figure has settled into it.</summary>
    private Surface.Ground _ground = new(Surface.Kind.Firm, 0f, 1f, 1f, 0f);
    private float _sink;

    public bool Invulnerable { get; private set; }
    /// <summary>How far the figure has settled into mud, m (the harness reads it).</summary>
    public float Sink => _sink;

    /// <summary>The camera yaw movement is read against, held while a key is.</summary>
    private float? _ctrlYaw;
    private Vector2 _ctrlKey;

    // ---- scripted input, for headless verification --------------------------
    // The state machine reads the keyboard directly, which is right for a game
    // with no InputMap and wrong for a test: a headless run has no keyboard. The
    // demo timeline writes here instead, and every read below goes through the
    // two helpers rather than through Input.
    private bool _scripted;
    private Vector3 _driveWish;
    private bool _driveJump, _driveDash, _driveAttack, _driveDown;

    public void Drive(Vector3 wish, bool jump, bool dash, bool attack, bool down)
    {
        _scripted = true;
        _keys = null;
        if (jump && !_driveJump) _jumpBuffer = PTune.JumpBuffer;
        if (attack && !_driveAttack) _attackBuffer = 0.16f;
        _driveWish = wish;
        _driveJump = _jumpHeld = jump;
        _driveDash = dash;
        _driveAttack = attack;
        _driveDown = down;
    }

    /// <summary>Scripted WASD (x right, y down, as the keys read): unlike
    /// <see cref="Drive"/> it goes through the camera-relative mapping and the
    /// control-yaw latch, so a test can exercise them.</summary>
    public void DriveKeys(Vector2 keys)
    {
        Drive(Vector3.Zero, false, false, false, false);
        _keys = keys;
    }
    private Vector2? _keys;

    private bool Held(Key k) => _scripted
        ? k switch
        {
            Key.Shift => _driveDash,
            Key.S => _driveDown,
            _ => false,
        }
        : Input.IsPhysicalKeyPressed(k);

    public override void _Ready()
    {
        AddChild(new CollisionShape3D
        {
            Shape = new CapsuleShape3D { Height = Height, Radius = Radius },
            Position = new Vector3(0f, Height * 0.5f, 0f),
        });

        _rig = new SpriteRig { Name = "Rig" };
        AddChild(_rig);

        // The contact shadow. Every reference frame has one and it is doing more
        // work than it looks: without it a sprite standing on a slope has no
        // fixed point on the ground and appears to hover.
        _shadow = new MeshInstance3D
        {
            Name = "Shadow",
            Mesh = new QuadMesh { Size = new Vector2(0.9f, 0.9f) },
            Position = new Vector3(0f, 0.03f, 0f),
            Rotation = new Vector3(-Mathf.Pi * 0.5f, 0f, 0f),   // flat on the ground
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            MaterialOverride = new StandardMaterial3D
            {
                AlbedoColor = new Color(0f, 0f, 0f, 0.45f),
                Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
                BillboardMode = BaseMaterial3D.BillboardModeEnum.Disabled,
            },
        };
        AddChild(_shadow);

        FloorSnapLength = 0.6f;
    }

    public void Bind(CameraRig cam)
    {
        _cam = cam;
        _cam.LowDeg = _rig.LowDeg;
        _cam.TopDeg = _rig.TopDeg;
        _cam.SpriteWorldH = _rig.WorldH;
        _cam.SpritePx = _rig.SpritePx;
        _cam.Recompose();
        _rig.UseTop(_cam.TopSet);
        _rig.SetTilt(_cam.PitchRad, _cam.YawRad);
        // Face the camera on spawn. Left at Vector3.Forward the heading lands on
        // facing 3 and the player meets their own character back-on.
        _heading = new Vector3(Mathf.Sin(_cam.YawRad), 0f, Mathf.Cos(_cam.YawRad));
        _facing = _cam.FacingFor(_heading, 0);
        _rig.SetFacing(_facing);
    }

    // ----------------------------------------------------------------- input
    /// <summary>Riding something (the <see cref="Boat"/>): while set, the
    /// player is carried on this node and does not move itself; its input is
    /// read by the vehicle through <see cref="WishDir"/>.</summary>
    public Node3D? Seat;

    /// <summary>The camera-relative direction the player is asking for.</summary>
    public Vector3 WishDir => Wish();

    private Vector3 Wish()
    {
        if (_scripted && _keys == null) return _driveWish;
        if (CameraRig.Revealing && !_scripted) { _ctrlYaw = null; return Vector3.Zero; }

        var v = _keys ?? Vector2.Zero;
        if (!_scripted)
        {
            if (Input.IsPhysicalKeyPressed(Key.W)) v.Y -= 1f;
            if (Input.IsPhysicalKeyPressed(Key.S)) v.Y += 1f;
            if (Input.IsPhysicalKeyPressed(Key.A)) v.X -= 1f;
            if (Input.IsPhysicalKeyPressed(Key.D)) v.X += 1f;
        }
        if (v == Vector2.Zero) { _ctrlYaw = null; return Vector3.Zero; }
        v = v.Normalized();
        // Movement is relative to the camera. The camera turns to look down a
        // city street, so the yaw is LATCHED while a direction is held --
        // turning under a held key would curve the player's path. A new press,
        // or the keys turning more than 45 deg, takes the camera's yaw again.
        if (_ctrlYaw == null || Mathf.Abs(v.AngleTo(_ctrlKey)) > Mathf.DegToRad(46f))
        {
            _ctrlYaw = _cam?.YawRad ?? 0f;
            _ctrlKey = v;
        }
        var y = _ctrlYaw.Value;
        var fwd = new Vector3(-Mathf.Sin(y), 0f, -Mathf.Cos(y));
        var right = new Vector3(Mathf.Cos(y), 0f, -Mathf.Sin(y));
        return (right * v.X - fwd * v.Y).Normalized();
    }

    public override void _UnhandledInput(InputEvent e)
    {
        if (e is InputEventKey k && k.PhysicalKeycode == Key.Space)
        {
            if (k.Pressed && !k.Echo) _jumpBuffer = PTune.JumpBuffer;
            _jumpHeld = k.Pressed;
        }

        var attack = (e is InputEventKey { Pressed: true, Echo: false } ka
                      && ka.PhysicalKeycode == Key.J)
                     || (e is InputEventMouseButton
                         { Pressed: true, ButtonIndex: MouseButton.Left });
        if (attack) _attackBuffer = 0.16f;
    }

    // --------------------------------------------------------------- physics
    public override void _PhysicsProcess(double delta)
    {
        var dt = (float)delta;

        // Seated: the vehicle places us (Boat._PhysicsProcess); no own motion.
        // Sit still facing the bow -- left alone, whatever state we boarded in
        // (walk, run, fall) kept looping and the rower danced in the boat.
        if (Seat != null)
        {
            Velocity = Vector3.Zero;
            _hitstop = 0f;
            _squash = Vector2.One;
            _rig.SetSquash(1f, 1f);
            Enter(PState.Idle);
            var bow = Seat.GlobalBasis.X; // Boat: local +X is the bow
            _heading = new Vector3(bow.X, 0f, bow.Z).Normalized();
            if (_cam != null)
            {
                var f = _cam.FacingFor(_heading, _facing);
                if (f != _facing) { _facing = f; _rig.SetFacing(f); }
            }
            return;
        }

        // Hitstop freezes everything: the sprite, the motion and the clock. A
        // few frozen frames are what a hit reads as at this scale -- there is no
        // room in 48 px for an impact pose to do it alone.
        if (_hitstop > 0f)
        {
            _hitstop -= dt;
            Velocity = Vector3.Zero;
            return;
        }

        _stateTime += dt;
        _coyote -= dt;
        _jumpBuffer -= dt;
        _attackBuffer -= dt;
        _dashCooldown -= dt;

        var grounded = IsOnFloor();
        if (grounded) { _coyote = PTune.CoyoteTime; _airDashSpent = false; _ground = Surface.At(GlobalPosition); }

        var wish = Wish();
        Step(wish, grounded, dt);
        // After Step, not before: the landing branch reads how long the fall
        // was. Reset first, it was always 0 there and a hard landing never
        // registered (2026-09-24).
        _airTime = grounded ? 0f : _airTime + dt;

        var before = GlobalPosition;
        MoveAndSlide();

        // Wading stops at chest depth: the lake is 2.6 m deep and the figure
        // 1.85 m tall. Keep whichever axis of the move stays shallow, so the
        // player slides along the drop-off; out past it is the boat's water.
        var at = GlobalPosition;
        if (Water.TooDeep(at) && !Water.TooDeep(before))
        {
            if (!Water.TooDeep(at with { Z = before.Z })) GlobalPosition = at with { Z = before.Z };
            else if (!Water.TooDeep(at with { X = before.X })) GlobalPosition = at with { X = before.X };
            else GlobalPosition = before with { Y = at.Y };
        }

        // People are solid: step back out of anyone walked into (user,
        // 2026-09-26: people "pass through you"). ponytail: set directly, like
        // the wading fix above -- only our own walk can overlap them, and that
        // moves us away from any wall behind; MoveAndCollide stalls on ramps.
        var feet = new Vector2(GlobalPosition.X, GlobalPosition.Z);
        var clear = Bodies.Push(feet, Radius, null, -1, solid: true);
        if (clear != feet) GlobalPosition = new Vector3(clear.X, GlobalPosition.Y, clear.Y);

        // Chunks stream in one per frame, so the collider under the player can
        // briefly not exist. Without this the player falls through the hole and
        // never comes back. WorldGen.Height is the same function the mesh is
        // built from, so this floor IS the ground surface.
        var ground = WorldGen.Height(GlobalPosition.X, GlobalPosition.Z);
        if (GlobalPosition.Y < ground)
            GlobalPosition = GlobalPosition with { Y = ground };

        Draw(wish, dt);
    }

    private void Step(Vector3 wish, bool grounded, float dt)
    {
        var v = Velocity;

        switch (_state)
        {
            case PState.Dash:
            case PState.AirDash:
            {
                var t = _state == PState.Dash ? PTune.DashTime : PTune.AirDashTime;
                var s = _state == PState.Dash ? PTune.DashSpeed : PTune.AirDashSpeed;
                v = _heading * s;
                if (_state == PState.AirDash) v.Y = 0f;        // a flat air dash
                else v.Y = Mathf.Min(Velocity.Y, 0f);
                Invulnerable = _state == PState.Dash
                               && _stateTime >= PTune.IFrameStart
                               && _stateTime <= PTune.IFrameEnd;
                if (_stateTime >= t) { Invulnerable = false; Enter(grounded ? PState.Idle : PState.Fall); }
                break;
            }

            case PState.Dive:
                v = new Vector3(_heading.X * 2f, -PTune.DiveSpeed, _heading.Z * 2f);
                if (grounded)
                {
                    _hitstop = PTune.DiveHitstop;
                    _cam?.AddTrauma(0.4f);
                    // the landing is a shock the world feels (Impact): grass, water,
                    // animals, snow, anything breakable within DiveRadius
                    Impact.Shock(GlobalPosition, PTune.DiveRadius);
                    Enter(PState.DiveLand);
                    _squash = new Vector2(PTune.LandSquashX * 1.1f, PTune.LandSquashY * 0.9f);
                    v = Vector3.Zero;
                }
                break;

            case PState.Land:
            case PState.DiveLand:
                v.X = Mathf.MoveToward(v.X, 0f, PTune.RunSpeed / PTune.DecelTime * dt);
                v.Z = Mathf.MoveToward(v.Z, 0f, PTune.RunSpeed / PTune.DecelTime * dt);
                v.Y = grounded ? 0f : v.Y - PTune.Gravity * dt;
                // Cancellable: a landing that has to play out is what makes a
                // character feel like it is wading.
                if (_rig.Finished || _jumpBuffer > 0f || _attackBuffer > 0f
                    || wish != Vector3.Zero)
                    Enter(PState.Idle);
                break;

            case PState.Attack1:
            case PState.Attack2:
            case PState.Attack3:
            case PState.DashAttack:
            {
                // The swing drifts forward: a slash rooted to the spot reads as
                // a character swatting at the air.
                v.X = _heading.X * PTune.AttackDrift;
                v.Z = _heading.Z * PTune.AttackDrift;
                v.Y = grounded ? 0f : v.Y - PTune.Gravity * dt;

                if (_attackBuffer > 0f && _stateTime > 0.08f) _chainQueued = true;

                // the blade lands once, at the swing's hit frame; striking something
                // takes the hitstop (a swing through air does not)
                if (!_swung && _stateTime >= PTune.SwingAt)
                {
                    _swung = true;
                    var fin = _state == PState.Attack3;
                    if (Impact.Swing(GlobalPosition, _heading, fin ? PTune.FinisherReach : PTune.SwingReach,
                                     Mathf.DegToRad(fin ? 80f : 65f)))
                    {
                        _hitstop = PTune.Hitstop;
                        _cam?.AddTrauma(fin ? 0.3f : 0.18f);
                    }
                }

                // Dash cancels the recovery, never the wind-up.
                var frame = _stateTime * SpriteRig.Fps;
                if (_dashCooldown <= 0f && frame >= PTune.CancelFrame
                    && Held(Key.Shift) && wish != Vector3.Zero)
                {
                    _heading = wish;
                    StartDash(grounded);
                    break;
                }

                if (_rig.Finished)
                {
                    if (_chainQueued && _state != PState.Attack3
                        && _state != PState.DashAttack)
                    {
                        _chainQueued = false;
                        Enter(_state == PState.Attack1 ? PState.Attack2 : PState.Attack3);
                        if (wish != Vector3.Zero) _heading = wish;
                    }
                    else { _chainQueued = false; Enter(PState.Idle); }
                }
                break;
            }

            case PState.Hurt:
                v.X = Mathf.MoveToward(v.X, 0f, PTune.Knockback * dt * 4f);
                v.Z = Mathf.MoveToward(v.Z, 0f, PTune.Knockback * dt * 4f);
                v.Y = grounded ? 0f : v.Y - PTune.Gravity * dt;
                if (_stateTime >= PTune.HurtTime) Enter(grounded ? PState.Idle : PState.Fall);
                break;

            default:
            {
                // ---- free movement: Idle / Walk / Run / JumpRise / Fall -----
                var run = Held(Key.Shift) && _dashCooldown > 0f;
                // soft ground slows the walk, ice takes the grip (Surface)
                var target = wish * (run ? PTune.RunSpeed : PTune.WalkSpeed) * _ground.Speed;
                // a gust leans on the player in open country (Snow.Gust, scaled there by
                // Surface.Exposure): standing, they drift; walking into it is slower
                if (grounded && Snow.Gust > 0.25f)
                    target += new Vector3(Surface.WindDir.X, 0f, Surface.WindDir.Y) * (Snow.Gust * PTune.GustPush);
                var accel = wish == Vector3.Zero
                    ? PTune.RunSpeed / PTune.DecelTime
                    : PTune.RunSpeed / PTune.AccelTime;
                if (!grounded) accel *= PTune.AirAccelScale * PTune.AirControl;
                else accel *= _ground.Grip;
                if (grounded && wish == Vector3.Zero && _ground.Grip > 0.5f)
                {
                    // the stop eases out: ~95 % of the speed gone in StopTime (3 time
                    // constants). Not on ice (grip 0.07): its linear slide is tuned and
                    // verified (3.33 m, findings 2026-09-28); an exponential tail doubles it
                    var k = 1f - Mathf.Exp(-3f * dt * _ground.Grip / PTune.StopTime);
                    v.X = Mathf.Lerp(v.X, target.X, k);
                    v.Z = Mathf.Lerp(v.Z, target.Z, k);
                }
                else
                {
                    v.X = Mathf.MoveToward(v.X, target.X, accel * dt);
                    v.Z = Mathf.MoveToward(v.Z, target.Z, accel * dt);
                }

                if (grounded && _state != PState.JumpRise)
                    v.Y = Mathf.Min(v.Y, 0f);
                else
                    v.Y -= PTune.Gravity * dt;

                // Variable jump height: let go and the rise is cut.
                if (_state == PState.JumpRise && !_jumpHeld && v.Y > 0f)
                    v.Y *= PTune.JumpCut;

                // ---- transitions out of free movement ----------------------
                if (_attackBuffer > 0f)
                {
                    _attackBuffer = 0f;
                    if (!grounded && Held(Key.S))
                    {
                        Enter(PState.Dive);
                        break;
                    }
                    if (wish != Vector3.Zero) _heading = wish;
                    Enter(PState.Attack1);
                    break;
                }

                if (Held(Key.Shift) && _dashCooldown <= 0f
                    && wish != Vector3.Zero && (grounded || !_airDashSpent))
                {
                    _heading = wish;
                    StartDash(grounded);
                    break;
                }

                if (_jumpBuffer > 0f && _coyote > 0f)
                {
                    _jumpBuffer = 0f;
                    _coyote = 0f;
                    // settled into mud, the jump starts lower
                    v.Y = PTune.JumpSpeed * (1f - PTune.MudJumpLoss * Mathf.Clamp(_sink / 0.13f, 0f, 1f));
                    Enter(PState.JumpRise);
                    break;
                }

                if (!grounded)
                {
                    if (v.Y <= 0f && _state != PState.Fall) Enter(PState.Fall);
                }
                else if (_state is PState.Fall or PState.JumpRise)
                {
                    Enter(PState.Land);
                    _squash = new Vector2(PTune.LandSquashX, PTune.LandSquashY);
                    if (_airTime > PTune.HardLandFall) { _stateTime = -0.12f; _cam?.AddTrauma(0.3f); }
                }
                else
                {
                    // Walk against Run is decided by the INPUT, not by the
                    // speed. Classifying on speed made a full-speed walk (6.0
                    // against a 4.6 threshold) play the run cycle, so the
                    // character never once walked.
                    // With no key held, a slow drift (a gust, the end of a slide on ice)
                    // is still standing.
                    var speed = new Vector2(v.X, v.Z).Length();
                    var want = speed < 0.2f || (wish == Vector3.Zero && speed < 2.4f) ? PState.Idle
                        : run ? PState.Run : PState.Walk;
                    if (want != _state) Enter(want);
                }
                break;
            }
        }

        Velocity = v;
    }

    private void StartDash(bool grounded)
    {
        if (!grounded) _airDashSpent = true;
        _dashCooldown = PTune.DashCooldown;
        Enter(grounded ? PState.Dash : PState.AirDash);
    }

    private void Enter(PState s)
    {
        if (s == _state && !PTune.IsAttack(s)) return;
        _state = s;
        _stateTime = 0f;
        _swung = false;
        _rig.Play(PTune.Anim(s), _facing, true);
    }

    /// <summary>Per rendered frame: keep the picture facing a camera whose
    /// pitch may be blending, and swap to the bake nearer its angle. On the
    /// physics tick this would step at 60 Hz under a 120 Hz blend.</summary>
    public override void _Process(double delta)
    {
        if (_cam == null) return;
        if (_rig.IsTop != _cam.TopSet) _rig.UseTop(_cam.TopSet);
        _rig.SetTilt(_cam.PitchRad, _cam.YawRad);
    }

    // ------------------------------------------------------------------ draw
    private void Draw(Vector3 wish, float dt)
    {
        var move = new Vector3(Velocity.X, 0f, Velocity.Z);
        if (!PTune.Locked(_state) && wish != Vector3.Zero) _heading = wish;
        else if (move.LengthSquared() > 0.5f && !PTune.Locked(_state))
            _heading = move.Normalized();

        if (_cam != null)
        {
            var f = _cam.FacingFor(_heading, _facing);
            if (f != _facing) { _facing = f; _rig.SetFacing(f); }
        }

        _squash = _squash.Lerp(Vector2.One, 1f - Mathf.Exp(-PTune.SquashRecover * dt));
        _rig.SetSquash(_squash.X, _squash.Y);

        // settling into mud: all the way standing, a third walking, out at once in the
        // air. The ground hides the sunk feet.
        var moving = move.LengthSquared() > 0.25f;
        _sink = IsOnFloor()
            ? Mathf.MoveToward(_sink, _ground.Sink * (moving ? 0.35f : 1f), dt * 0.2f)
            : Mathf.MoveToward(_sink, 0f, dt * 1.5f);
        _rig.Position = Vector3.Down * _sink;

        // The shadow shrinks with height off the ground rather than vanishing:
        // it is the only cue for how high a jump is at this camera angle.
        var ground = WorldGen.Height(GlobalPosition.X, GlobalPosition.Z);
        var h = Mathf.Clamp(GlobalPosition.Y - ground, 0f, 4f);
        _shadow.Position = new Vector3(0f, ground - GlobalPosition.Y + 0.03f, 0f);
        var k = Mathf.Lerp(1f, 0.45f, h / 4f);
        _shadow.Scale = new Vector3(k, k, 1f);
    }

    /// <summary>Damage entry point. Nothing calls it yet -- there are no enemies
    /// in this project -- but the state exists so the i-frames on the dash mean
    /// something when one does.</summary>
    /// <summary>Debug: what the machine and the picture currently think.</summary>
    public string Report()
    {
        var ground = WorldGen.Height(GlobalPosition.X, GlobalPosition.Z);
        return $"state={_state} anim={PTune.Anim(_state)} facing={_facing} "
               + $"y={GlobalPosition.Y:F3} ground={ground:F3} dy={GlobalPosition.Y - ground:F3} "
               + $"floor={IsOnFloor()} vel={Velocity}";
    }

    public void Hurt(Vector3 from)
    {
        if (Invulnerable || _state == PState.Hurt) return;
        var away = (GlobalPosition - from) with { Y = 0f };
        if (away.LengthSquared() > 1e-4f)
            Velocity = away.Normalized() * PTune.Knockback + Vector3.Up * 2f;
        _hitstop = PTune.Hitstop;
        _cam?.AddTrauma(0.5f);
        Enter(PState.Hurt);
    }
}
