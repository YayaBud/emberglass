using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// A lamp's flame: a warm point light that flickers, switches its shadow off
/// with distance, and switches itself off further out.
///
/// Ported from nanobanna's <c>FireLight</c> without the audio -- this project
/// has no sound layer yet.
///
/// The flicker is not decoration. A point light at constant energy reads as an
/// electric bulb, and a row of them reads as a car park. Three detuned sines,
/// phased by position, so no two lamps ever pulse in step.
/// </summary>
public partial class LampLight : OmniLight3D
{
    [Export] public float Strength { get; set; } = 2.4f;
    /// <summary>Beyond this the light is off entirely.</summary>
    [Export] public float CullRange { get; set; } = 60f;
    /// <summary>Inside this it may cast a shadow, if the budget allows.</summary>
    [Export] public float ShadowRange { get; set; } = 30f;

    /// <summary>Warm glass lamp (default) or open fire (brazier, hearth): a
    /// deeper colour and a livelier flicker.</summary>
    [Export] public bool Fire { get; set; }
    /// <summary>Reach in metres (9 for a street lamp; a wall lantern less).</summary>
    [Export] public float Reach { get; set; } = 9f;

    private float _t;
    private float _phase;

    // ------------------------------------------------------------------ auto cull
    // Lamps not under a site's own budget (Village has one): the city's
    // hundreds and the desert's braziers. Each is on only within CullRange of
    // the player, checked 5 times a second, so a city of ~500 lamps lights the
    // 20-40 round the frame and nothing else.
    private static readonly List<LampLight> _auto = new();
    private static float _autoT;

    /// <summary>Put this lamp under <see cref="Tick"/>'s distance cull.</summary>
    public LampLight Auto()
    {
        _auto.Add(this);
        // the far edge of the cull fades (camera distance) rather than pops;
        // only here, so the village's measured lamps are untouched
        DistanceFadeEnabled = true;
        DistanceFadeBegin = CullRange - 12f;
        DistanceFadeLength = 10f;
        Visible = false;
        SetProcess(false);
        return this;
    }

    public static int AutoCount => _auto.Count;
    /// <summary>Bench switch: every auto lamp off.</summary>
    public static bool AutoOff;

    /// <summary>Called every frame by World with the player's position.</summary>
    public static void Tick(Vector3 player, float dt)
    {
        if ((_autoT -= dt) > 0f) return;
        _autoT = 0.2f;
        for (var i = 0; i < _auto.Count; i++)
        {
            var l = _auto[i];
            if (!IsInstanceValid(l) || !l.IsInsideTree()) continue;
            l.Cull(AutoOff ? 1e9f : l.GlobalPosition.DistanceTo(player), false);
        }
    }

    public override void _ExitTree() => _auto.Remove(this);

    public override void _Ready()
    {
        _phase = (GlobalPosition.X * 12.9898f + GlobalPosition.Z * 78.233f) % Mathf.Tau;
        LightColor = Fire ? new Color(1f, 0.50f, 0.20f) : new Color(1f, 0.62f, 0.30f);
        OmniRange = Reach;
        OmniAttenuation = 1.6f;
        LightSpecular = 0.25f;
        ShadowEnabled = false;
        // Two hemispheres instead of six cube faces: a third of the shadow
        // passes, and at a lamp's 9 m range the seam is not visible.
        OmniShadowMode = ShadowMode.DualParaboloid;
    }

    public override void _Process(double delta)
    {
        _t += (float)delta;
        var f = Mathf.Sin(_t * 11.3f + _phase) * 0.52f
              + Mathf.Sin(_t * 17.7f + _phase * 2.1f) * 0.31f
              + Mathf.Sin(_t * 29.1f + _phase * 0.7f) * 0.17f;
        LightEnergy = Strength * Grade.L.Lamps * Grade.LampScale * (1f + f * (Fire ? 0.3f : 0.14f));
    }

    /// <summary>Called by the village's light budget with this lamp's distance
    /// to the player, and whether it is one of the nearest few allowed a shadow.
    /// Omni shadows are six-sided cubemaps; two of them is the ceiling this
    /// frame budget can carry.</summary>
    public void Cull(float distance, bool shadowAllowed)
    {
        var on = distance < CullRange;
        if (Visible != on)
        {
            Visible = on;
            SetProcess(on);
        }
        var shadow = on && shadowAllowed && distance < ShadowRange;
        if (ShadowEnabled != shadow) ShadowEnabled = shadow;
    }
}
