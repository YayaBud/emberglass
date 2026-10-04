using Godot;

namespace Worldbuilder;

public enum PState
{
    Idle, Walk, Run, JumpRise, Fall, Land,
    Dash, AirDash, Dive, DiveLand,
    Attack1, Attack2, Attack3, DashAttack,
    Hurt,
}

/// <summary>
/// Every number that decides how the character feels, in one place, and the
/// mapping from a state to the strip that draws it.
///
/// These are starting values, tuned by playing. They are grouped by what they
/// do rather than by type, because the ones that have to agree with each other
/// -- coyote against buffer, dash window against its cooldown -- are useless
/// sitting in separate corners of a file.
/// </summary>
public static class PTune
{
    // ---- ground movement --------------------------------------------------
    public const float WalkSpeed = 6.0f;
    public const float RunSpeed = 9.5f;
    /// <summary>Stick magnitude above which Walk becomes Run. On a keyboard
    /// there is no analogue axis, so Shift is the switch instead.</summary>
    public const float RunThreshold = 0.7f;
    /// <summary>Seconds to reach full speed, and to come back to rest. Instant
    /// velocity is the single most common reason a character reads as weightless.</summary>
    public const float AccelTime = 0.12f;
    public const float DecelTime = 0.08f;       // the landing's skid
    /// <summary>Letting go on the ground: an ease-out, most of the speed at
    /// once and a short glide after (guide 4.1, AVOID 6: no abrupt halts).
    /// A starting target to A/B, not a rule.</summary>
    public const float StopTime = 0.16f;
    public const float AirAccelScale = 0.40f;   // 0.30 s to accelerate in air
    public const float AirControl = 0.55f;
    public const float TurnRate = 14f;          // rad/s the body swings to a new heading

    // ---- jump -------------------------------------------------------------
    public const float Gravity = 26f;
    public const float JumpSpeed = 8.2f;
    /// <summary>Releasing the button cuts the rise to this fraction. Without a
    /// variable jump there is one jump height and the player cannot aim.</summary>
    public const float JumpCut = 0.45f;
    /// <summary>Grace after walking off an edge, and grace for a button pressed
    /// before landing. Both 0.12 s. These two are why a jump that "should have
    /// worked" does.</summary>
    public const float CoyoteTime = 0.12f;
    public const float JumpBuffer = 0.12f;
    public const float HardLandFall = 1.0f;     // s airborne before the long landing

    // ---- dash -------------------------------------------------------------
    public const float DashSpeed = 17f;
    public const float DashTime = 0.22f;
    public const float DashCooldown = 0.55f;
    public const float IFrameStart = 0.10f;     // within the dash window
    public const float IFrameEnd = 0.20f;
    public const float AirDashTime = 0.18f;
    public const float AirDashSpeed = 15f;

    // ---- dive -------------------------------------------------------------
    public const float DiveSpeed = 18f;
    public const float DiveHitstop = 0.09f;
    public const float DiveRadius = 2.4f;

    // ---- attacks ----------------------------------------------------------
    /// <summary>The chain window, as a fraction of the action's own length. A
    /// press inside it queues the next hit; outside it the swing recovers and
    /// the chain drops.</summary>
    public const float ChainOpen = 0.45f;
    public const float ChainClose = 1.0f;
    /// <summary>Frame (of the action) from which a dash cancels the swing. The
    /// ANNO rule: a chain that cannot be cancelled into the dodge reads as
    /// commitment, one that can reads as fluid. 3 of 5, so the wind-up commits
    /// and the recovery does not.</summary>
    public const int CancelFrame = 3;
    public const float Hitstop = 0.06f;
    public const float AttackDrift = 2.2f;      // m/s the swing carries you forward
    /// <summary>When the blade lands (s into the swing), and how far it reaches: a sweep
    /// 65 deg either side, the finisher (hit 3) wider and longer.</summary>
    public const float SwingAt = 0.1f;
    public const float SwingReach = 1.6f, FinisherReach = 1.9f;

    // ---- the world pushing back -------------------------------------------
    /// <summary>m/s a full gust leans on a player standing in open country.</summary>
    public const float GustPush = 1.8f;
    /// <summary>A figure settled all the way into mud jumps this much lower.</summary>
    public const float MudJumpLoss = 0.3f;

    // ---- hurt -------------------------------------------------------------
    public const float HurtTime = 0.25f;
    public const float Knockback = 6f;

    // ---- read ------------------------------------------------------------
    /// <summary>Hysteresis on the 8-way facing quantiser, in degrees. Without
    /// it a stick held on a boundary flickers between two sprites.</summary>
    public const float FacingHysteresis = 5f;
    public const float LandSquashX = 1.12f;
    public const float LandSquashY = 0.88f;
    public const float SquashRecover = 9f;      // per second, back toward 1

    public static string Anim(PState s) => s switch
    {
        PState.Idle => "idle",
        PState.Walk => "walk",
        PState.Run => "run",
        PState.JumpRise => "jump_rise",
        PState.Fall => "fall",
        PState.Land => "land",
        PState.Dash => "dash",
        PState.AirDash => "air_dash",
        PState.Dive => "dive",
        PState.DiveLand => "land",
        PState.Attack1 => "attack_1",
        PState.Attack2 => "attack_2",
        PState.Attack3 => "attack_3",
        PState.DashAttack => "attack_1",
        PState.Hurt => "hurt",
        _ => "idle",
    };

    /// <summary>States that ignore the stick: the move is already committed.</summary>
    public static bool Locked(PState s) => s is PState.Dash or PState.AirDash
        or PState.Dive or PState.DiveLand or PState.Attack1 or PState.Attack2
        or PState.Attack3 or PState.DashAttack or PState.Hurt or PState.Land;

    public static bool IsAttack(PState s) => s is PState.Attack1 or PState.Attack2
        or PState.Attack3 or PState.DashAttack;
}
