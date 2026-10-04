using Godot;

namespace Worldbuilder;

/// <summary>The regions of the world. Order is the array order everywhere;
/// new ones are appended, never inserted.</summary>
public enum Biome
{
    /// <summary>Warm broadleaf woodland. The starting region and the village.</summary>
    Greenwood = 0,
    /// <summary>Open farmland and grass. Long sightlines, windmills, fences.</summary>
    Meadow = 1,
    /// <summary>Autumn forest. The transition band between the green west and the dry east.</summary>
    Emberwood = 2,
    /// <summary>Wet lowland. Dead stands, standing water, the deepest colour in the game.</summary>
    Fen = 3,
    /// <summary>Rock and pine, climbing to the castle bluff.</summary>
    Crags = 4,
    /// <summary>Sand, stone arches and the temple.</summary>
    Dunes = 5,
    /// <summary>Snowbound fells beyond the Crags. Snow is laid per pixel on
    /// top of the ground by <see cref="Snow"/>, not baked into its colour.</summary>
    Snow = 6,
}

/// <summary>
/// Where each region is, what its ground looks like, and how the borders blend.
///
/// The world is 1024 units square, centred on the origin, and it is ONE
/// continuous surface — not a set of rooms with loading between them. A region
/// is a weighted influence over that surface, so a player walking east out of
/// the Greenwood watches broadleaf give way to autumn and then to scrub over
/// about eighty metres, without ever crossing a line.
///
/// That blend is why <see cref="Weights"/> exists at all and why nothing in the
/// project switches on <see cref="Biome"/> alone except where a hard choice is
/// genuinely required (which enemy to spawn, which ambience to play).
///
/// **Centres are hand-placed, not generated.** A procedurally scattered set of
/// biome seeds gives an even, characterless quilt. These are laid out so that
/// the start is sheltered, the two settlements are far apart and in contrasting
/// regions, and the route between them passes through three kinds of country.
/// </summary>
public static class Biomes
{
    /// <summary>Half-extent of the world, world units. The map is 1024 square.</summary>
    public const float HalfWorld = 512f;

    /// <summary>Region centre, influence radius, and the ground it makes.</summary>
    public readonly record struct Region(
        Biome Kind,
        /// <summary>Shown to the player on entering. Not the enum name.</summary>
        string Name,
        /// <summary>One line under the title. Sets the mood, never the mechanics.</summary>
        string Flavour,
        Vector2 Centre,
        float Radius,
        /// <summary>Base elevation of the region's floor.</summary>
        float Base,
        /// <summary>Vertical scale of the region's large landform noise.</summary>
        float Relief,
        /// <summary>Horizontal scale of that noise. Small = broad, smooth land.</summary>
        float Grain,
        Color Ground,
        Color GroundAlt);

    /// <summary>
    /// Indexed by <see cref="Biome"/>. Do not reorder without fixing every
    /// caller that indexes a weight array.
    /// </summary>
    public static Region[] All =
    {
        // Greenwood — the start. Low relief so the opening hour is readable and
        // the player is never lost inside their own first ten minutes.
        new(Biome.Greenwood, "The Greenwood", "old oaks, and a road going west",
            new Vector2(0f, 0f), 210f,
            0f, 5.5f, 0.016f,
            new Color(0.088f, 0.150f, 0.062f), new Color(0.135f, 0.165f, 0.070f)),

        // Meadow — west. Nearly flat: this is where the eye gets to travel.
        new(Biome.Meadow, "Elder Meadows", "somebody still cuts this hay",
            new Vector2(-250f, -150f), 230f,
            -1.5f, 2.4f, 0.011f,
            new Color(0.160f, 0.205f, 0.078f), new Color(0.205f, 0.220f, 0.096f)),

        // Emberwood — east, the warm transition into the dry half of the map.
        new(Biome.Emberwood, "The Emberwood", "it has been autumn here a long time",
            new Vector2(230f, -210f), 200f,
            3f, 8.5f, 0.019f,
            new Color(0.150f, 0.115f, 0.055f), new Color(0.190f, 0.135f, 0.058f)),

        // Fen — south. Sits below everything else so water gathers in it.
        new(Biome.Fen, "Duskfen", "the water remembers what stood here",
            new Vector2(-90f, 300f), 180f,
            -6.5f, 2.0f, 0.014f,
            new Color(0.058f, 0.086f, 0.066f), new Color(0.070f, 0.076f, 0.054f)),

        // Crags — north-west, the highest ground. The castle stands on it.
        new(Biome.Crags, "Greyward Crags", "stone above, stone below",
            new Vector2(-260f, 250f), 215f,
            14f, 22f, 0.013f,
            // Cool grey, not neutral. A neutral albedo under a warm key and a
            // blue fill comes out warm, and the Crags rendered as a dusty tan
            // plateau indistinguishable from the Ashdunes at a glance. Tipping
            // the base blue lets the sun warm it back to grey instead of past it.
            new Color(0.108f, 0.110f, 0.122f), new Color(0.078f, 0.080f, 0.094f)),

        // Dunes — south-east. Big smooth landform, almost no small detail: sand
        // reads as sand because of what it does NOT have.
        new(Biome.Dunes, "The Ashdunes", "nothing is buried here by accident",
            new Vector2(280f, 270f), 235f,
            2f, 11f, 0.009f,
            new Color(0.400f, 0.310f, 0.165f), new Color(0.330f, 0.245f, 0.130f)),

        // Snow -- the far north-west corner, beyond the Crags: high rolling
        // fells. The colours are the ground UNDER the snow (frozen earth, grey
        // stone): how much of it shows is the ground shader's call, from the
        // live snow depth, so a thin fall leaves it patchy and a heavy one
        // buries it.
        new(Biome.Snow, "The Hoarfells", "the snow keeps what the road forgets",
            new Vector2(-430f, 430f), 150f,
            18f, 10f, 0.014f,
            new Color(0.120f, 0.112f, 0.105f), new Color(0.095f, 0.095f, 0.102f)),
    };

    public static int Count => All.Length;

    // ---- noise -------------------------------------------------------------
    // Shared with Terrain.cs by copy rather than by reference on purpose: this
    // one has to be callable as a pure static from anywhere, including from
    // placement code that runs before any node exists.

    public static float Hash(int x, int y, ulong seed)
    {
        unchecked
        {
            var h = (ulong)(x * 374761393L) ^ (ulong)(y * 668265263L) ^ (seed * 1442695040888963407UL);
            h = (h ^ (h >> 13)) * 1274126177UL;
            h ^= h >> 16;
            return (h & 0xFFFFFF) / (float)0xFFFFFF;
        }
    }

    public static float Value(float x, float y, ulong seed)
    {
        var xi = Mathf.FloorToInt(x);
        var yi = Mathf.FloorToInt(y);
        float xf = x - xi, yf = y - yi;
        var u = xf * xf * (3f - 2f * xf);
        var v = yf * yf * (3f - 2f * yf);
        return Mathf.Lerp(
            Mathf.Lerp(Hash(xi, yi, seed), Hash(xi + 1, yi, seed), u),
            Mathf.Lerp(Hash(xi, yi + 1, seed), Hash(xi + 1, yi + 1, seed), u), v);
    }

    public static float Fbm(float x, float y, ulong seed, int octaves = 4)
    {
        float sum = 0f, amp = 1f, norm = 0f, freq = 1f;
        for (var i = 0; i < octaves; i++)
        {
            sum += Value(x * freq, y * freq, seed + (ulong)i * 7919UL) * amp;
            norm += amp;
            amp *= 0.5f;
            freq *= 2.03f;
        }
        return sum / norm;
    }

    /// <summary>
    /// Blended influence of every region at a point, summing to 1.
    ///
    /// The sample point is domain-warped first. Without the warp the boundaries
    /// are the perpendicular bisectors between centres — straight lines, visible
    /// from the air and visible on the ground as a ruler-edge change of grass.
    /// Warping by a low-frequency noise makes them wander by twenty or thirty
    /// metres, which is all it takes for a border to read as geography.
    /// </summary>
    public static void Weights(Vector2 p, ulong seed, float[] into)
    {
        // 85 units of warp, not 210. At 210 a sample taken deep in the Ashdunes
        // could land a hundred metres inside the Greenwood's influence, and the
        // scatter -- which picks a region by weight and then a plant inside it --
        // put pine trees in the desert. The warp only has to be wide enough that
        // a border reads as geography rather than as a bisector; 85 is about
        // fifteen seconds of walking and does that without letting regions
        // reach into each other's interiors.
        var wx = p.X + (Fbm(p.X * 0.0045f, p.Y * 0.0045f, seed ^ 0xB10UL) - 0.5f) * 85f;
        var wy = p.Y + (Fbm(p.X * 0.0045f + 31.7f, p.Y * 0.0045f - 12.3f, seed ^ 0xB11UL) - 0.5f) * 85f;
        var w = new Vector2(wx, wy);

        var total = 0f;
        for (var i = 0; i < All.Length; i++)
        {
            var d = w.DistanceTo(All[i].Centre) / All[i].Radius;
            // Inverse power falloff. The exponent sets how wide the transition
            // band is: 4 gives roughly eighty metres of blend between adjacent
            // regions at these radii, which is about a fifteen-second walk.
            var k = 1f / (0.0001f + Mathf.Pow(Mathf.Max(d, 0.02f), 4f));
            into[i] = k;
            total += k;
        }
        for (var i = 0; i < All.Length; i++) into[i] /= total;
    }

    /// <summary>The single strongest region at a point. For hard choices only.</summary>
    public static Biome At(Vector2 p, ulong seed)
    {
        var w = new float[All.Length];
        Weights(p, seed, w);
        var best = 0;
        for (var i = 1; i < w.Length; i++) if (w[i] > w[best]) best = i;
        return All[best].Kind;
    }

    /// <summary>Strength of one region at a point, 0..1.</summary>
    public static float WeightOf(Biome b, Vector2 p, ulong seed)
    {
        var w = new float[All.Length];
        Weights(p, seed, w);
        return w[(int)b];
    }
}
