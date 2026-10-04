using Godot;

namespace Worldbuilder;

/// <summary>
/// What the player stands on, and what it does to the walk (implementation_plan A3).
///
/// Soft ground takes a print (<see cref="Prints"/>) and slows the walk: deep snow, the dunes'
/// sand off the packed trails, the Fen's mud. Ice keeps the speed and takes the grip, so a
/// stop becomes a slide. Shallow water drags. Standing in mud the figure settles in
/// (<see cref="Ground.Sink"/>) and jumps lower -- the Triangle Strategy split: crossing costs
/// speed, stopping costs more (study 2.6).
///
/// Main thread only: the weights go through one shared buffer.
/// </summary>
public static class Surface
{
    public enum Kind { Firm, Snow, Sand, Mud, Ice, Shallows }

    /// <summary>Soft: how deep a print goes (0..1). Speed scales the walk's target speed,
    /// Grip its acceleration (ice ~0.1), Sink how far a standing figure settles (m).</summary>
    public readonly record struct Ground(Kind K, float Soft, float Speed, float Grip, float Sink);

    /// <summary>The way the wind blows, world XZ: the grass shader's own `wd`.</summary>
    public static readonly Vector2 WindDir = new Vector2(0.87f, 0.49f).Normalized();

    private static readonly float[] _w = new float[Biomes.Count];

    /// <summary>Wind shelter by region (Biome order): woods shelter, open country does not.</summary>
    private static readonly float[] Open = { 0.3f, 1f, 0.3f, 0.55f, 1f, 0.75f, 1f };

    public static Ground At(Vector3 p)
    {
        var h = WorldGen.Height(p.X, p.Z);
        if (Water.Wading(p)) return new Ground(Kind.Shallows, 0f, 0.72f, 0.8f, 0f);
        var xz = new Vector2(p.X, p.Z);
        Biomes.Weights(xz, WorldGen.Seed, _w);
        var snow = _w[(int)Biome.Snow];
        // hard to start and hard to stop: from a walk the slide runs ~1.8 m (firm: 0.1)
        if (snow > 0.3f && OnIce(xz)) return new Ground(Kind.Ice, 0f, 1.06f, 0.07f, 0f);
        var sn = snow < 0.05f ? 0f : snow * Snow.Depth;
        var sand = _w[(int)Biome.Dunes];
        // the caravan trails are packed: a shallower print, a surer step
        sand = sand < 0.05f ? 0f : sand * (0.35f + 0.65f * Mathf.SmoothStep(1.2f, 2.6f, WorldGen.TrailDistance(p.X, p.Z)));
        var mud = Mud(_w[(int)Biome.Fen], h);
        if (sn >= sand && sn >= mud && sn > 0.05f) return new Ground(Kind.Snow, sn, 1f - 0.32f * sn, 1f - 0.15f * sn, 0f);
        if (sand >= mud && sand > 0.05f) return new Ground(Kind.Sand, sand * 0.8f, 1f - 0.14f * sand, 1f - 0.1f * sand, 0f);
        if (mud > 0.05f) return new Ground(Kind.Mud, mud, 1f - 0.36f * mud, 1f - 0.3f * mud, 0.13f * mud);
        return new Ground(Kind.Firm, 0f, 1f, 1f, 0f);
    }

    /// <summary>Mud: the Fen's low ground near its water, from the Fen's weight and the
    /// height. Pure, so the terrain workers draw it from the same number (vertex UV.y) and the
    /// feet sink where the ground looks wet.</summary>
    public static float Mud(float fen, float h) =>
        fen < 0.05f ? 0f : fen * (1f - Mathf.SmoothStep(WorldGen.FenWaterLevel + 0.4f, WorldGen.FenWaterLevel + 2.6f, h));

    private static bool OnIce(Vector2 q)
    {
        foreach (var i in WorldGen.IcePools)
            if (((q - new Vector2(i.X, i.Y)) / new Vector2(i.Z, i.W)).Length() < 0.92f) return true;
        return false;
    }

    /// <summary>How open the country is to the wind here, 0.3..1: the gusts' strength
    /// outside the Hoarfells.</summary>
    public static float Exposure(Vector2 xz)
    {
        Biomes.Weights(xz, WorldGen.Seed, _w);
        var e = 0f;
        for (var i = 0; i < _w.Length; i++) e += _w[i] * Open[i];
        return e;
    }
}
