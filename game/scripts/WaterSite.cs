using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The water test site, on its own screen-left of the village (path space
/// a 5, b -85; ~85 m from the spawn): a pond dug into the ground by
/// <see cref="WorldGen.PondLevel"/>'s carve, reeds round every shore but the
/// camera's, trees and three lamps on the far bank for the water to reflect,
/// puddles on the bank, and the life: ducks that paddle, dabble and fly off,
/// koi that jump, does that come down to drink. Everything that touches the
/// water ripples it (<see cref="Water.Ripple"/>).
/// </summary>
public partial class WaterSite : Node3D
{
    private static readonly Vector3 F = new(-0.7071f, 0f, -0.7071f);
    private static readonly Vector3 R = new(0.7071f, 0f, -0.7071f);

    private static readonly Fauna.Kind Duck = new("duck", 0.5f, 6f, 6f, 7f, 0.12f, 0.2f, "dabble",
                                                  Flies: true, On: Fauna.Medium.Swim, Homing: true);
    private static readonly Fauna.Kind Koi = new("koi", 0.7f, 2.5f, 3f, 6f, 0.1f, 0.1f, "idle",
                                                 On: Fauna.Medium.Fish, Homing: true);
    private static readonly Fauna.Kind Drinker = new("doe", 0.8f, 7f, 10f, 1.5f, 0.34f, 0.45f, "graze", Homing: true);

    private readonly System.Random _rng = new(9090);
    private float U() => (float)_rng.NextDouble();

    private static Vector2 C => WorldGen.PondCentre;
    private static Vector2 Dir(float t) => new(Mathf.Cos(t), Mathf.Sin(t));
    /// <summary>How far toward the back of the frame a direction points (1 = straight away from the camera).</summary>
    private static float Back(Vector2 d) => d.X * F.X + d.Y * F.Z;

    public void Build(Node3D player, Village village)
    {
        var level = WorldGen.PondLevel;
        AddChild(Water.Pond());
        // Rain lands ON the water: the rain's heightfield only sees opaque
        // geometry, so without this the drops fell through the transparent
        // surface and splashed on the bed. A box whose top is the waterline;
        // over the banks the ground is higher and is hit first.
        var half = WorldGen.PondRadius * 1.2f;
        AddChild(new GpuParticlesCollisionBox3D
        {
            Name = "PondSurface",
            Size = new Vector3(half * 2f, 2f, half * 2f),
            Position = new Vector3(C.X, level - 1f, C.Y),
        });

        var spots = new List<Foliage.Spot>();
        void Plant(string kind, Vector2 at, float scale, bool shadow) =>
            spots.Add(new Foliage.Spot(kind, WorldGen.Snap(at), scale, shadow));

        // reeds on the shore, in clumps, leaving the camera's side open
        // (count scales with the shore: 160 at the 22 m pond)
        for (var i = 0; i < (int)(160 * WorldGen.PondRadius / 22f); i++)
        {
            var t = U() * Mathf.Tau;
            var d = Dir(t);
            if (Back(d) < -0.35f) continue;
            Plant("reed", C + d * WorldGen.PondShore(t) * (0.95f + U() * 0.2f), 0.8f + U() * 0.5f, false);
        }
        // the far bank: trees and bushes behind the water, for it to reflect
        for (var i = 0; i < 70; i++)
        {
            var t = U() * Mathf.Tau;
            var d = Dir(t);
            if (Back(d) < 0.1f) continue;
            var r = WorldGen.PondShore(t) * (1.45f + U() * 0.9f);
            var kind = U() < 0.25f ? "bush" : U() < 0.4f ? "vine_oak" : U() < 0.6f ? "oak" : U() < 0.8f ? "pine" : "birch";
            Plant(kind, C + d * r, 0.85f + U() * 0.4f, kind != "bush");
        }
        Wildwood.Tiled(this, spots);

        // lamps on the bank: two across the water, one at the side, so their
        // flames and pools of light fall on the surface
        var lamps = new List<Vector2>();
        foreach (var t in new[] { 0.55f, 1.0f, -0.2f })
        {
            // angle measured from the away-from-camera direction
            var away = Mathf.Atan2(F.Z, F.X);
            var a = away + t * 1.3f;
            var at = C + Dir(a) * (WorldGen.PondShore(a) * 1.3f);
            village.Lamp(at.X * F.X + at.Y * F.Z, at.X * R.X + at.Y * R.Z);
            lamps.Add(at);
        }
        // puddles on the near bank, by the camera side, under the side lamp's light
        foreach (var t in new[] { -2.4f, -2.9f, 2.6f })
        {
            var a = Mathf.Atan2(F.Z, F.X) + t;
            AddChild(Water.Puddle(C + Dir(a) * (WorldGen.PondShore(a) * 1.55f), 1.6f + U() * 1.0f));
        }

        // the boat: moored off the near bank, side-on to the camera, where the
        // player comes down to the water
        var toCam = Mathf.Atan2(-F.Z, -F.X);
        // (inshore as far as it floats with margin: the player wades out to
        // it, and wading stops at chest depth)
        var boatAt = C;
        for (var r = WorldGen.PondShore(toCam) * 0.95f; r > 0f; r -= 0.25f)
        {
            boatAt = C + Dir(toCam) * r;
            var ok = true;
            foreach (var o in new[] { R * 1.9f, R * -1.9f, F * 0.8f, F * -0.8f })
                ok &= WorldGen.Height(boatAt.X + o.X, boatAt.Y + o.Z) < level - 0.45f;
            if (ok) break;
        }
        var boat = new Boat { Name = "Boat" };
        AddChild(boat);
        boat.Build((Player)player, boatAt, Mathf.Atan2(-R.Z, R.X));

        // the ship: at anchor off the back-left bank, bow along the shore,
        // as close in as its 1.35 m draft allows -- first angle, from the
        // preferred one outward, where it and its anchor clear the bed
        Ship? ship = null;
        var awayA = Mathf.Atan2(F.Z, F.X);
        foreach (var da in new[] { -0.8f, -0.6f, -1.0f, -0.4f, -1.2f, -0.2f, -1.4f, 0f })
        {
            var a = awayA + da;
            var yaw = Mathf.Atan2(-Mathf.Cos(a), -Mathf.Sin(a));   // bow along the shore
            for (var r = WorldGen.PondShore(a) * 0.9f; r > WorldGen.PondShore(a) * 0.2f && ship == null; r -= 0.4f)
            {
                var at = C + Dir(a) * r;
                if (!Ship.Fits(at, yaw)) continue;
                ship = new Ship { Name = "Ship" };
                AddChild(ship);
                ship.Build(at, yaw);
            }
            if (ship != null) break;
        }
        if (ship == null) GD.PushWarning("watersite: no water deep enough for the ship");

        var fauna = new Fauna
        {
            Threat = () => Water.BoatSpeed > 0.2f ? new Vector2(Water.Boat.X, Water.Boat.Y) : null,
            Name = "Fauna",
            Water = level,
            FaceIdle = C,
            Keep = p => C + (p - C).LimitLength(WorldGen.PondRadius * 2.2f),
            Dry = p => WorldGen.Height(p.X, p.Y) > level + 0.05f,
            Deep = p => WorldGen.Height(p.X, p.Y) < level - 0.45f,
            Ripple = Water.Ripple,
        };
        AddChild(fauna);
        fauna.Bind(player, 9090);
        Wildwood.Blockers(fauna, spots);
        foreach (var l in lamps) fauna.Block(l, 0.25f);
        // the ship's hull, as circles down its length
        if (ship != null)
            foreach (var k in new[] { -0.36f, -0.18f, 0f, 0.18f, 0.36f })
                fauna.Block(ship.Pos + ship.Axis * k * Ship.Length, Ship.Beam * 0.6f);

        List<Vector2> InWater(int n)
        {
            var homes = new List<Vector2>();
            for (var i = 0; homes.Count < n && i < 400; i++)
            {
                var p = C + Dir(U() * Mathf.Tau) * WorldGen.PondRadius * Mathf.Sqrt(U());
                if (WorldGen.Height(p.X, p.Y) < level - 0.5f && ship?.Contact(p, 1.5f) == null) homes.Add(p);
            }
            return homes;
        }
        fauna.Add(Duck, InWater(5));
        fauna.Add(Koi, InWater(8));

        // drinkers: at the water's edge on the far and side banks, where the
        // ground first stands clear of the water
        var drink = new List<Vector2>();
        foreach (var t in new[] { 0.35f, -0.6f, 1.2f })
        {
            var a = Mathf.Atan2(F.Z, F.X) + t;
            var d = Dir(a);
            var r = WorldGen.PondShore(a) * 0.9f;
            while (WorldGen.Height(C.X + d.X * r, C.Y + d.Y * r) < level + 0.1f && r < WorldGen.PondRadius * 2f) r += 0.2f;
            drink.Add(C + d * (r + 0.3f));
        }
        fauna.Add(Drinker, drink);

        GD.Print($"watersite: level {level:F2}, {spots.Count} plants, {fauna.Count} animals, {lamps.Count} lamps, ship at {ship?.Pos.ToString() ?? "none"}");
    }
}
