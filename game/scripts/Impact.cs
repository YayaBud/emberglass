using Godot;

namespace Worldbuilder;

/// <summary>
/// What the player's blows do to the world (implementation_plan A1). The player knows nothing
/// about grass, animals or pots: it reports a blow here, and each system answers through its
/// own static hook.
///
/// * <see cref="Shock"/>: the dive's landing. Everything within the radius reacts -- the grass
///   flattens and a ring runs out through it (global `shock`), water rings, animals bolt,
///   loaded trees shed, snow and sand burst up, breakables break.
/// * <see cref="Swing"/>: a sword arc in front of the player at the swing's hit frame. Only
///   things that can be struck answer it (breakables; enemies in Phase C).
/// </summary>
public static class Impact
{
    /// <summary>The latest shock: x, z, radius, age in seconds (99 = none).</summary>
    private static Vector4 _shock = new(0f, 0f, 0f, 99f);

    /// <summary>Seconds since the last shock (99 = none yet).</summary>
    public static float ShockAge => _shock.W;

    /// <summary>The shader global. Registered before anything compiles (Weather.Globals).</summary>
    public static void Globals() =>
        RenderingServer.GlobalShaderParameterSet("shock", _shock);

    /// <summary>A blow landing at `at` with radius `r` (the dive: PTune.DiveRadius).</summary>
    public static void Shock(Vector3 at, float r)
    {
        _shock = new Vector4(at.X, at.Z, r, 0f);
        RenderingServer.GlobalShaderParameterSet("shock", _shock);
        var xz = new Vector2(at.X, at.Z);
        Water.Ripple(xz, 1.6f);
        foreach (var f in Fauna.All) f.Scare(xz, r * 2.2f);
        Snow.Live?.Shock(at, r);
        Prints.Live?.Burst(at, r);
        Breakables.Smash(at, r);
    }

    /// <summary>A swing from `from` along `heading`: `reach` metres out, `halfArc` radians
    /// either side. True if it struck anything (the swing then takes the hitstop).</summary>
    public static bool Swing(Vector3 from, Vector3 heading, float reach, float halfArc) =>
        Breakables.Hit(from, heading, reach, halfArc);

    /// <summary>Once a frame: the shock ages until it is spent.</summary>
    public static void Tick(float dt)
    {
        if (_shock.W > 3f) return;
        _shock.W += dt;
        RenderingServer.GlobalShaderParameterSet("shock", _shock);
    }
}
