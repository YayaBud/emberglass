using Godot;

namespace Worldbuilder;

/// <summary>
/// The HD-2D frame: a dusk key, a cool fill, warm haze, and a vignette.
///
/// This is aimed at the numbers the reference set measures at, not at taste --
/// mean luminance 0.30-0.40, at least 20 percent of pixels below 0.15 luma, and
/// saturation 0.45-0.52 (`memory.md`, from `hd2d_foundation_audit.md`). The
/// version of nanobanna that got measured sat at 0.494 / 0.7 percent / 0.309:
/// half again too bright, with essentially no shadow in the frame at all, and
/// that came from a recorded decision to raise ambient to 0.92 because a first
/// pass "felt cold". The first pass had been right.
///
/// Law 4 is the shape of it: the frame is dark and the bright material is
/// concentrated into small pools. Contrast does the work, and the eye goes to
/// the lit patch that matters.
/// </summary>
public static class Grade
{
    /// <summary>Clouds off with `--noclouds`, so the two can be benchmarked
    /// against each other rather than argued about.</summary>
    public static bool Clouds = true;

    /// <summary>Everything that says what time of day it is: sun, shadow fill,
    /// haze, sky, exposure and the lamps. The field defaults are the shipped
    /// dusk, matching the reference frame the look is aimed at: a low warm sun
    /// raking across the ground so the facets read, and a blue fill standing in
    /// for sky bounce.</summary>
    public sealed class Lighting
    {
        public float Elev = 14f, Yaw = -148f;
        public Color Sun = new(1.0f, 0.78f, 0.55f);
        public float SunEnergy = 3.8f;
        /// <summary>The sun's angular size in degrees. Above 0 a shadow softens
        /// with distance from its caster (PCSS). Its GPU cost is not measured.</summary>
        public float Soft;
        public Color Ambient = new(0.30f, 0.34f, 0.52f);
        public float AmbientEnergy = 0.32f;
        public Color Fill = new(0.42f, 0.52f, 0.78f);
        public float FillEnergy = 0.35f;
        public Color Fog = new(0.74f, 0.55f, 0.42f);
        /// <summary>The ground mist's colour (Post), blended per region like the fog.</summary>
        public Color Mist = new(0.95f, 0.86f, 0.90f);
        /// <summary>0 by default (user, 2026-09-29: "the fog is too much ... it should be
        /// seasonal, like winter or at night"): only the snow region keeps its mist.</summary>
        public float MistDensity = 0f;
        /// <summary>The Post curve's black point, blended per region like the mist.
        /// The default is the 2026-09-28 violet lift; the city's dusk (2026-09-30,
        /// the user's direction sheet) wants deep, near-neutral blacks.</summary>
        public Color Black = new(0.075f, 0.035f, 0.12f);
        /// <summary>Distance fog density (the far haze band).</summary>
        public float FogDen = 0.0009f;
        public float Exposure = 0.90f, Saturation = 0.88f;
        /// <summary>The grade's contrast (Environment adjustment): 1.30 was
        /// set once for every region; the city's own is lower (2026-09-27, it
        /// sharpened every texture edge: ground detail 0.0293 -> 0.0244 at 1.00).</summary>
        public float Contrast = 1.30f;
        /// <summary>Scales the lamp flames and the glowing windows together.</summary>
        public float Lamps = 1f;
        /// <summary>Renderer features the shipped frame does not use, for the
        /// study of what the references have that we lack. All off by default.</summary>
        public float VFog, Bloom;
        /// <summary>The sun's scattering into the volumetric fog: above 1 the
        /// cloud gaps (<see cref="Clouds"/>) read as shafts.</summary>
        public float SunFog = 1f;
        /// <summary>Share of windows lit (CityKit): all at dusk, a few by day.</summary>
        public float WindowsLit = 1f;
        public bool Ssil, Sdfgi, Grain;
        public string Tone = "filmic";
        /// <summary>How bright the character reads relative to the shipped
        /// frame; see <see cref="SpriteModulate"/>.</summary>
        public Color SpriteTint = new(1f, 1f, 1f);
        public Color SkyTop = new(0.10f, 0.15f, 0.34f), SkyHorizon = new(0.62f, 0.32f, 0.18f),
            GroundHorizon = new(0.30f, 0.22f, 0.20f), GroundBottom = new(0.07f, 0.06f, 0.08f),
            CloudLit = new(0.62f, 0.40f, 0.31f), CloudDark = new(0.16f, 0.12f, 0.19f);
    }

    /// <summary>The live lighting. `--light=` replaces it before the world is
    /// built (<see cref="Tune"/>); with no flag it is <see cref="Twilight"/>.
    /// `new Lighting()` is the earlier dusk (`--light=late`), kept as the base
    /// the study's other presets were measured from.</summary>
    public static Lighting L = Twilight();

    /// <summary>The shipped look since 2026-09-23 (lighting study, round 2):
    /// the sun low, weak and behind-left, so the lamps and windows are the
    /// light; bloom and a little volumetric fog so that light shows in the air;
    /// ACES. Each number moved the measured frame toward the reference band
    /// (`findings_results.md`). The sun sits at 11 deg, not the 8 that scored
    /// best: at 8 from yaw -120 its long diagonal shadows pulled more casters
    /// into the cascades and cost 0.76 ms of GPU against 0.39 at 11.</summary>
    public static Lighting Twilight() => new()
    {
        Elev = 11f, Yaw = -120f,
        Sun = Kelvin(3400f), SunEnergy = 2.0f,
        AmbientEnergy = 0.32f * 1.3f, FillEnergy = 0.35f * 1.3f,
        Exposure = 0.90f, Saturation = 0.78f,
        Lamps = 3.5f, Bloom = 0.6f, VFog = 0.0015f, Tone = "aces", FogDen = 0.0004f,   // was 0.0009 (user: less fog)
    };

    /// <summary>The twilight re-tuned WITH textured assets (lighting round 3,
    /// 2026-09-23): the same light with the sun swung to the left side. Behind
    /// the camera's left shoulder it lights the faces the camera sees, so the
    /// textures read -- backlit, a camera-facing wall measured L* 3-10 and its
    /// texture vanished -- while still throwing long shadows across the road.
    /// Spawn-view contrast 23.0 -> 33.1, the first to reach the references'
    /// 32-58. Used by `--kit` until the proof slice is signed off.</summary>
    public static Lighting TwilightKit()
    {
        var l = Twilight();
        l.Yaw = -45f;
        // 1.08 / 0.75, not the round's 1.0 / 0.78: over the 10 demo frames
        // those measured mean 0.282 and sat 0.524 against the audit's
        // 0.30-0.40 and 0.45-0.52.
        l.Exposure = 1.08f;
        l.Saturation = 0.75f;
        // The woods (918 sprite plants, their canopies and shadows) took the
        // frame to mean 0.18-0.21 and 57-60% dark. Between exposure 1.5 alone
        // and fill x1.6 at 1.25 (both measured back in band): fill x1.5 lifts
        // the forest floor without blowing the lamps, and exposure does the rest.
        l.AmbientEnergy *= 1.5f;
        l.FillEnergy *= 1.5f;
        l.Exposure = 1.35f;
        return l;
    }

    /// <summary>The Hoarfells' grade, blended in by the snow country's weight
    /// at the player (<see cref="Weather"/>): sun, fill, ambient, fog, haze,
    /// exposure, saturation, lamps and sky. Tuned by the snow lighting sweep
    /// (`scripts/forge/snow_sweep.py`, findings 2026-09-23); `--snowlight=`
    /// dials it like `--light=` dials the base.</summary>
    public static Lighting SnowLight() => new()
    {
        Elev = 16f, Yaw = -45f,
        Sun = Kelvin(4800f), SunEnergy = 1.2f,
        Ambient = new(0.42f, 0.48f, 0.62f), AmbientEnergy = 0.55f,
        Fill = new(0.55f, 0.62f, 0.86f), FillEnergy = 0.5f,
        Fog = new(0.56f, 0.60f, 0.70f), FogDen = 0.0035f, MistDensity = 0.22f,   // winter keeps its mist and haze
        Exposure = 1.05f, Saturation = 0.72f,
        Lamps = 5.5f, Bloom = 0.6f, VFog = 0.004f, Tone = "aces",
        SkyTop = new(0.16f, 0.20f, 0.32f), SkyHorizon = new(0.52f, 0.52f, 0.60f),
        GroundHorizon = new(0.40f, 0.42f, 0.48f), GroundBottom = new(0.10f, 0.10f, 0.14f),
        CloudLit = new(0.62f, 0.62f, 0.70f), CloudDark = new(0.22f, 0.24f, 0.32f),
    };

    /// <summary>The snow sweep's pick (round 2, 2026-09-23), as dials over
    /// <see cref="SnowLight"/>: `lantern_dusk` -- warm low key, blue shade,
    /// strong lanterns, amber haze. Measured closest to the reference on colour
    /// and contrast (bright b* -8.5 vs -11.7, sat 0.289 vs 0.309, contrast
    /// 48.7 vs 48.9); `combo_all` scored better overall only by being darker
    /// and read cyan (bright b* -0.1, split of the wrong sign) -- rejected.</summary>
    /// Rounds 3-5 (after the kit dressed the lamp walk; user: "just too much
    /// brightness"): lanterns 9 -> 3 (their pools blew out: bright b* went warm,
    /// contrast 86), exposure 0.85 -> 0.58, fog x1.6. Round 5 measured mean
    /// 0.331 vs the reference's 0.313, dark 23.8% vs 21.3%, score 16.70 (best).
    public const string SnowSwept = "exp:0.58,sun:0.8,k:3000,elev:10,yaw:-100,lamps:3,fogw:0.5,shade:blue,sat:0.85,fogd:1.6";

    public static Lighting SnowL = Swept("");

    private static Lighting Swept(string spec)
    {
        var keep = L;
        L = SnowLight();
        Tune(SnowSwept);
        if (spec != "") Tune(spec);
        var s = L;
        L = keep;
        return s;
    }

    /// <summary>The Ashdunes' grade, blended in by the dunes' weight at the
    /// player (<see cref="Weather"/>) as the snow grade is: a hot afternoon --
    /// the sun high behind the camera's left shoulder so the faces the camera
    /// sees are lit, a warm key (the user's "orange tint" in the snow), warm
    /// bounce off the sand, a dusty haze, a pale sky. Picked by eye, NOT swept
    /// or measured yet. `--desertlight=` dials it.</summary>
    public static Lighting DesertLight() => new()
    {
        Elev = 40f, Yaw = -60f,
        Sun = Kelvin(4300f), SunEnergy = 2.3f,
        Ambient = new(0.62f, 0.56f, 0.52f), AmbientEnergy = 0.45f,
        Fill = new(0.70f, 0.66f, 0.72f), FillEnergy = 0.35f,
        Fog = new(0.88f, 0.70f, 0.50f), FogDen = 0.0015f,   // was 0.004 (user, 2026-09-29: less fog)
        Exposure = 0.66f, Saturation = 0.9f,
        Lamps = 1f, Bloom = 0.4f, VFog = 0.002f, Tone = "aces",
        SkyTop = new(0.30f, 0.46f, 0.72f), SkyHorizon = new(0.90f, 0.78f, 0.60f),
        GroundHorizon = new(0.72f, 0.60f, 0.44f), GroundBottom = new(0.20f, 0.16f, 0.12f),
        CloudLit = new(1.0f, 0.95f, 0.88f), CloudDark = new(0.72f, 0.66f, 0.60f),
    };

    public static Lighting DesertL = DesertLight();

    public static void TuneDesert(string spec)
    {
        var keep = L;
        L = DesertLight();
        Tune(spec);
        DesertL = L;
        L = keep;
    }

    /// <summary>Emberglass's grade, blended in by the city's weight at the
    /// player (<see cref="Weather"/>) like the snow and desert ones: a golden
    /// afternoon after the user's Octopath II town frame (2026-09-24; day/night
    /// option C, per area). A warm key high enough for cloud shadows and shafts
    /// to read -- the twilight's weak sun shows neither -- from the camera's
    /// left shoulder at the base yaw, the side that measured best on textured
    /// walls, and the sun scattering hard into the fog for the beams
    /// (<see cref="Clouds"/>). 2026-09-27, after the user's four reference
    /// videos: the shade, haze and horizon are cool (`--gradesweep` c4; the warm
    /// ambient and amber haze had put 99 % of city pixels in warm hues); then
    /// on "do warm colours first then fix ground noise" the sun went 3900 ->
    /// 5000 K (`--looksweep`: city warm share 73 -> 42 %, lit stone still
    /// b* +14, warmer than any of the videos) and contrast 1.30 -> 1.00 (the
    /// ground-noise lever; shadow filter and atlas measured as nothing).
    /// 2026-09-29, the user: "it is all grey ... dead". Over the retoned honey
    /// stone, `--looksweep` passes 1-3 (findings): a 4300 K sun, AgX, saturation
    /// 1.05, a cool-lavender shade (all-warm made the shade b* +16, the 09-27
    /// "everything orange"), a light warm haze at 0.7 x the density, cream mist
    /// at 0.06 (0.22 drowned the middle distance), a clear blue sky over a gold
    /// horizon. Measured against the user's post video (pp_with): mean 0.423 /
    /// 0.446, lit sat 0.347 / 0.328, warm 85 / 84 %, shade b* +1.1 / -3.3.
    /// The full 13-view tour then read a touch dark and cool-lit (mean 0.374,
    /// lit b* 13.0): sun 4300 -> 4000 K and exposure 0.62 -> 0.68.
    /// Saturation 0.90 puts back what the flatter contrast took.
    /// `--citylight=` dials it.
    /// 2026-09-30, the user's city direction sheet ("this dense and this orangish
    /// and dark"): a sunset. `--looksweep` pass 4 (findings): d1 (AgX) and d4
    /// (ACES) at 3000 K, sun 16 deg, every window and lamp lit, near-neutral Post
    /// blacks; the user picked "between bottom left and top right" -- ACES for
    /// d4's depth, with d1's softer shade (fill x1.2) and a saturation between.</summary>
    public static Lighting CityLight() => new()
    {
        Elev = 16f, Yaw = -45f,
        // Soft 0.5, not 1.2: at 1.2 PCSS's blocker search against the cloud
        // caster 45 m up spiked frames to ~100 ms (p99 124 ms). 0.5 priced at
        // +0.64 ms, no spikes (2026-09-24), and gives the cloud edges a
        // penumbra of ~0.7 m.
        Sun = Kelvin(3000f), SunEnergy = 3.2f, Soft = 0.5f,
        // the shade 40 % toward the cool lavender (2026-09-30, "city life" plan, looksweep pass
        // 5 "p4"): b* +9.4 -> +7.7 on the 5 sweep spots, the sheet +3.5; warm share 99.4 ->
        // ~98.5 per view (was 0.47/0.42/0.50 and 0.61/0.55/0.66). p4 also cut the fill to x0.8;
        // in the tour that took the shaded views to 45-52 % dark pixels, so the energy stayed
        Ambient = new(0.434f, 0.42f, 0.556f), AmbientEnergy = 0.36f,
        Fill = new(0.574f, 0.554f, 0.732f), FillEnergy = 0.26f,
        // fog cut to a trace (user, 2026-09-29: "the fog is too much it is destroying
        // the game"): depth fog 0.00084 -> 0.0002, volumetric 0.0042 -> 0.0012 (a
        // little light in the air for the lamps and shafts), no mist; warm at dusk
        // violet, not orange (2026-09-30, part 2): the sheet's distance is purple, and the
        // orange haze put 99.5 % of the frame in warm hues
        Fog = new(0.66f, 0.54f, 0.68f), FogDen = 0.0004f,
        Mist = new(0.96f, 0.92f, 0.90f), MistDensity = 0f,
        Black = new(0.022f, 0.016f, 0.024f),
        Exposure = 0.70f, Saturation = 1.12f, Contrast = 1.00f,
        // lamps at the twilight's own level: they keep their luminance (Weather)
        // bloom 0.8 -> 0.5 (pass 5): tighter halos, the lamps read as pools, not haze
        Lamps = 4.5f, Bloom = 0.5f, VFog = 0.0012f, SunFog = 3f, WindowsLit = 1f, Tone = "aces",
        SkyTop = new(0.20f, 0.15f, 0.36f), SkyHorizon = new(0.98f, 0.58f, 0.30f),
        GroundHorizon = new(0.46f, 0.30f, 0.26f), GroundBottom = new(0.08f, 0.06f, 0.07f),
        CloudLit = new(1.0f, 0.64f, 0.40f), CloudDark = new(0.32f, 0.22f, 0.32f),
    };

    public static Lighting CityL = CityLight();

    /// <summary>Smooth texture filtering on the world (2026-09-30, user: "make the world look
    /// more smooth, it is very rough"): linear mipmapped anisotropic on the kit, the ground and
    /// the roads, instead of nearest. Sprites keep nearest. `--crisp` restores nearest.</summary>
    public static bool SmoothTex = true;

    /// <summary>A shader's nearest filters made linear when SmoothTex is on.</summary>
    public static string Filter(string code) => SmoothTex ? code.Replace("filter_nearest_mipmap_anisotropic", "filter_linear_mipmap_anisotropic") : code;

    public static void TuneCity(string spec)
    {
        var keep = L;
        L = CityLight();
        Tune(spec);
        CityL = L;
        L = keep;
    }

    /// <summary>Multiplies every lamp flame (<see cref="LampLight"/>): the
    /// region grades set it, so a lamp in the snow can burn brighter.</summary>
    public static float LampScale = 1f;

    /// <summary>`--snowlight=k:3000,lamps:8`: the dials of <see cref="Tune"/>
    /// over the shipped snow grade (<see cref="SnowSwept"/>).</summary>
    public static void TuneSnow(string spec) => SnowL = Swept(spec);

    /// <summary>The snow sheet's atmosphere and lighting row, as dials over
    /// <see cref="SnowSwept"/> (the shipped dusk): a clear day, an overcast,
    /// a snowfall (overcast, blue, and the weather on -- `fall:1`), a sunset
    /// glow. `--snowlook=name`. Picked by eye against the sheet's swatches,
    /// NOT swept or measured.</summary>
    public static readonly System.Collections.Generic.Dictionary<string, string> SnowLooks = new()
    {
        ["clear"] = "sky:clear,k:6200,sun:3.2,elev:32,yaw:-60,exp:0.72,lamps:0.8,fogd:0.35,shade:blue,sat:0.95,lift:1.2",
        ["overcast"] = "sky:overcast,k:6500,sun:0.35,exp:0.9,lamps:2,fogd:2.2,shade:grey,sat:0.6,lift:1.5",
        // (0.85 / fog 2.8 read as a white haze, mean 0.651 -- the sheet's
        // snowfall is dark blue-grey; this darker version is NOT yet captured)
        ["snowfall"] = "sky:overcast,k:7000,sun:0.3,exp:0.6,lamps:3,fogd:1.8,shade:blue,sat:0.7,lift:1.0,fall:1",
        ["sunset"] = "sky:sunset,k:2200,sun:3.6,elev:4,yaw:-110,exp:0.7,fogw:0.9,lamps:3,sat:1.0",
    };

    /// <summary>`sky:clear|overcast|sunset`: the sky gradient, clouds and
    /// haze colour together.</summary>
    private static void SkyLook(string name)
    {
        switch (name)
        {
            case "clear":
                L.SkyTop = new(0.22f, 0.38f, 0.66f); L.SkyHorizon = new(0.66f, 0.74f, 0.86f);
                L.GroundHorizon = new(0.60f, 0.64f, 0.72f); L.CloudLit = new(0.95f, 0.95f, 1.0f);
                L.CloudDark = new(0.55f, 0.60f, 0.70f); L.Fog = new(0.70f, 0.76f, 0.86f);
                break;
            case "overcast":
                L.SkyTop = new(0.42f, 0.44f, 0.50f); L.SkyHorizon = new(0.60f, 0.61f, 0.65f);
                L.GroundHorizon = new(0.50f, 0.50f, 0.54f); L.CloudLit = new(0.66f, 0.67f, 0.70f);
                L.CloudDark = new(0.45f, 0.46f, 0.50f); L.Fog = new(0.62f, 0.63f, 0.66f);
                break;
            case "sunset":
                L.SkyTop = new(0.18f, 0.16f, 0.34f); L.SkyHorizon = new(0.98f, 0.52f, 0.24f);
                L.GroundHorizon = new(0.55f, 0.30f, 0.25f); L.CloudLit = new(1.0f, 0.60f, 0.35f);
                L.CloudDark = new(0.35f, 0.20f, 0.30f); L.Fog = new(0.90f, 0.55f, 0.40f);
                break;
            default: GD.PushWarning($"--light: unknown sky '{name}'"); break;
        }
    }

    /// <summary>Sky contribution to ambient. It was 0.55 and that is what fills
    /// every shadow in with sky light until the frame has none left.</summary>
    public const float SkyContribution = 0.18f;

    /// <summary>The grade per camera mode; World blends between them with the
    /// camera. LOW is `L.Exposure` and `L.Saturation`, tuned against the low
    /// frame. TOP is re-measured against the top-down frame: same targets, a sun
    /// at 40 degrees instead of 14, and a ground plane that fills the picture.</summary>
    public const float TopExposure = 0.68f;
    public const float TopSaturation = 0.62f;

    /// <summary>`--light=golden,k:3000,lift:0.5`: a preset, then dials over it,
    /// left to right. The lighting study's harness (`light_study.py`).</summary>
    public static void Tune(string spec)
    {
        foreach (var tok in spec.Split(',', System.StringSplitOptions.RemoveEmptyEntries))
        {
            var kv = tok.Split(':', 2);
            if (kv.Length == 1) { L = Preset(tok); continue; }
            float F() => float.Parse(kv[1], System.Globalization.CultureInfo.InvariantCulture);
            switch (kv[0])
            {
                case "elev": L.Elev = F(); break;
                case "yaw": L.Yaw = F(); break;
                case "k": L.Sun = Kelvin(F()); break;
                case "sun": L.SunEnergy = F(); break;
                // Shadow depth: what fills the shadow side, scaled together.
                case "lift": L.AmbientEnergy *= F(); L.FillEnergy *= F(); break;
                case "shade": Shade(kv[1]); break;
                case "soft": L.Soft = F(); break;
                case "exp": L.Exposure = F(); break;
                case "sat": L.Saturation = F(); break;
                case "lamps": L.Lamps = F(); break;
                case "vfog": L.VFog = F(); break;
                case "sunfog": L.SunFog = F(); break;
                case "bloom": L.Bloom = F(); break;
                case "gi":
                    L.Ssil |= kv[1] is "ssil" or "both";
                    L.Sdfgi |= kv[1] is "sdfgi" or "both";
                    break;
                case "tone": L.Tone = kv[1]; break;
                case "grain": L.Grain = F() > 0f; break;
                case "tint": L.SpriteTint = new Color(F(), F(), F()); break;
                case "fogd": L.FogDen *= F(); break;
                // haze warmth: 0 keeps the fog colour, 1 is lamp-lit amber
                case "fogw": L.Fog = L.Fog.Lerp(new Color(0.86f, 0.62f, 0.42f), F()); break;
                case "amb": L.AmbientEnergy *= F(); break;
                case "fill": L.FillEnergy *= F(); break;
                case "sky": SkyLook(kv[1]); break;
                case "fall": break;   // snowfall on: read by World (--snowlook, --sweep)
                default: GD.PushWarning($"--light: unknown dial '{kv[0]}'"); break;
            }
        }
    }

    /// <summary>Times of day. Everything past `late` is a starting point from
    /// physics (sun height, colour temperature) and by eye (sky, haze, energy),
    /// NOT measured from a reference -- the study is what measures them.</summary>
    public static Lighting Preset(string name)
    {
        var l = new Lighting();
        switch (name)
        {
            case "late": break;   // the dusk shipped until 2026-09-23
            case "twilight": return Twilight();
            case "twilight_kit": return TwilightKit();
            case "golden":        // the sun on the horizon
                l.Elev = 5f; l.Sun = Kelvin(2600f); l.SunEnergy = 3.6f;
                l.Ambient = new(0.34f, 0.30f, 0.50f); l.AmbientEnergy = 0.30f;
                l.Fill = new(0.46f, 0.46f, 0.76f); l.FillEnergy = 0.30f;
                l.Fog = new(0.86f, 0.54f, 0.34f);
                l.SkyTop = new(0.16f, 0.15f, 0.36f); l.SkyHorizon = new(0.86f, 0.42f, 0.16f);
                l.CloudLit = new(0.86f, 0.46f, 0.26f); l.CloudDark = new(0.22f, 0.14f, 0.20f);
                break;
            case "afternoon":
                l.Elev = 32f; l.Sun = Kelvin(4800f); l.SunEnergy = 3.2f;
                l.Ambient = new(0.36f, 0.42f, 0.58f); l.AmbientEnergy = 0.40f;
                l.Fill = new(0.50f, 0.58f, 0.80f);
                l.Fog = new(0.72f, 0.68f, 0.64f);
                l.SkyTop = new(0.16f, 0.30f, 0.62f); l.SkyHorizon = new(0.66f, 0.60f, 0.52f);
                l.GroundHorizon = new(0.34f, 0.32f, 0.30f);
                l.CloudLit = new(0.88f, 0.84f, 0.78f); l.CloudDark = new(0.44f, 0.46f, 0.54f);
                l.Lamps = 0f;
                break;
            case "midday":
                l.Elev = 60f; l.Sun = Kelvin(5800f); l.SunEnergy = 3.0f;
                l.Ambient = new(0.40f, 0.46f, 0.60f); l.AmbientEnergy = 0.45f;
                l.Fill = new(0.52f, 0.60f, 0.80f); l.FillEnergy = 0.30f;
                l.Fog = new(0.68f, 0.74f, 0.82f);
                l.SkyTop = new(0.10f, 0.28f, 0.68f); l.SkyHorizon = new(0.62f, 0.72f, 0.86f);
                l.GroundHorizon = new(0.34f, 0.36f, 0.38f);
                l.CloudLit = new(0.96f, 0.96f, 0.96f); l.CloudDark = new(0.56f, 0.60f, 0.68f);
                l.Lamps = 0f;
                break;
            case "bluehour":      // the sun just gone: sky light and lamps
                l.Elev = 2f; l.Sun = Kelvin(2200f); l.SunEnergy = 0.8f;
                l.Ambient = new(0.28f, 0.34f, 0.62f); l.AmbientEnergy = 0.55f;
                l.Fill = new(0.40f, 0.50f, 0.86f); l.FillEnergy = 0.45f;
                l.Fog = new(0.40f, 0.40f, 0.58f);
                l.SkyTop = new(0.05f, 0.07f, 0.20f); l.SkyHorizon = new(0.56f, 0.30f, 0.30f);
                l.GroundHorizon = new(0.18f, 0.16f, 0.22f); l.GroundBottom = new(0.04f, 0.04f, 0.07f);
                l.CloudLit = new(0.46f, 0.30f, 0.36f); l.CloudDark = new(0.10f, 0.09f, 0.16f);
                l.Lamps = 1.8f;
                break;
            case "night":         // a moon, and the lamps doing the work
                l.Elev = 40f; l.Sun = new(0.62f, 0.74f, 1.0f); l.SunEnergy = 0.5f;
                l.Ambient = new(0.12f, 0.16f, 0.34f); l.AmbientEnergy = 0.50f;
                l.Fill = new(0.26f, 0.36f, 0.70f); l.FillEnergy = 0.25f;
                l.Fog = new(0.10f, 0.12f, 0.22f);
                l.SkyTop = new(0.01f, 0.02f, 0.06f); l.SkyHorizon = new(0.06f, 0.08f, 0.16f);
                l.GroundHorizon = new(0.04f, 0.04f, 0.06f); l.GroundBottom = new(0.01f, 0.01f, 0.02f);
                l.CloudLit = new(0.14f, 0.16f, 0.24f); l.CloudDark = new(0.03f, 0.03f, 0.06f);
                l.Lamps = 2.2f;
                break;
            case "overcast":      // no key light: the flat frame, for contrast
                l.Elev = 40f; l.Sun = new(0.92f, 0.94f, 1.0f); l.SunEnergy = 0.9f; l.Soft = 8f;
                l.Ambient = new(0.55f, 0.57f, 0.62f); l.AmbientEnergy = 0.95f;
                l.Fill = new(0.60f, 0.62f, 0.66f); l.FillEnergy = 0.30f;
                l.Fog = new(0.62f, 0.63f, 0.66f);
                l.SkyTop = new(0.42f, 0.44f, 0.48f); l.SkyHorizon = new(0.62f, 0.62f, 0.64f);
                l.GroundHorizon = new(0.36f, 0.36f, 0.38f);
                l.CloudLit = new(0.72f, 0.72f, 0.74f); l.CloudDark = new(0.46f, 0.47f, 0.50f);
                l.Lamps = 0f;
                break;
            default: GD.PushWarning($"--light: unknown preset '{name}'"); break;
        }
        return l;
    }

    /// <summary>Recolour the shadow side -- ambient and fill together -- at the
    /// luminance each already has, so this dial moves hue and nothing else.</summary>
    private static void Shade(string name)
    {
        Color a, f;
        switch (name)
        {
            case "blue": a = new(0.30f, 0.34f, 0.52f); f = new(0.42f, 0.52f, 0.78f); break;
            case "violet": a = new(0.44f, 0.30f, 0.62f); f = new(0.60f, 0.44f, 0.86f); break;
            case "teal": a = new(0.20f, 0.40f, 0.46f); f = new(0.32f, 0.60f, 0.70f); break;
            case "grey": a = new(0.36f, 0.36f, 0.36f); f = new(0.52f, 0.52f, 0.52f); break;
            case "warm": a = new(0.52f, 0.36f, 0.26f); f = new(0.78f, 0.56f, 0.40f); break;
            default: GD.PushWarning($"--light: unknown shade '{name}'"); return;
        }
        L.Ambient = AtLuma(a, Luma(L.Ambient));
        L.Fill = AtLuma(f, Luma(L.Fill));
    }

    private static float Luma(Color c) => 0.2126f * c.R + 0.7152f * c.G + 0.0722f * c.B;

    private static Color AtLuma(Color c, float y)
    {
        var s = y / Luma(c);
        return new Color(c.R * s, c.G * s, c.B * s);
    }

    /// <summary>Blackbody colour for a temperature in kelvin (1000-40000):
    /// Tanner Helland's curve fit, good to a few percent, which is all a grade
    /// dial needs.</summary>
    public static Color Kelvin(float k)
    {
        var t = k / 100f;
        var r = t <= 66f ? 255f : 329.698727446f * Mathf.Pow(t - 60f, -0.1332047592f);
        var g = t <= 66f
            ? 99.4708025861f * Mathf.Log(t) - 161.1195681661f
            : 288.1221695283f * Mathf.Pow(t - 60f, -0.0755148492f);
        var b = t >= 66f ? 255f : t <= 19f ? 0f : 138.5177312231f * Mathf.Log(t - 10f) - 305.0447927307f;
        return new Color(Mathf.Clamp(r, 0f, 255f) / 255f, Mathf.Clamp(g, 0f, 255f) / 255f,
                         Mathf.Clamp(b, 0f, 255f) / 255f);
    }

    /// <summary>The sky: the same dusk gradient as before, plus a drifting
    /// cloud band.
    ///
    /// A shader on the existing Sky node rather than geometry -- clouds that are
    /// quads have to be sorted, lit and streamed, and none of that buys anything
    /// for a band that is only ever seen above the horizon. This scrolls itself
    /// off TIME, casts nothing, and costs one material.
    ///
    /// It replaces ProceduralSkyMaterial, so the gradient is reproduced here by
    /// hand: the environment still samples this for ambient, and changing the
    /// gradient would move the measured numbers the grade was tuned to.
    /// </summary>
    private static ShaderMaterial CloudSky()
    {
        var shader = new Shader
        {
            Code = @"
shader_type sky;

uniform vec3 top = vec3(0.10, 0.15, 0.34);
uniform vec3 horizon = vec3(0.62, 0.32, 0.18);
uniform vec3 ground_horizon = vec3(0.30, 0.22, 0.20);
uniform vec3 ground_bottom = vec3(0.07, 0.06, 0.08);
uniform vec3 cloud_lit = vec3(0.62, 0.40, 0.31);
uniform vec3 cloud_dark = vec3(0.16, 0.12, 0.19);
uniform float speed = 0.018;
uniform float cover : hint_range(0.0, 1.0) = 0.26;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453);
}

// Value noise. Smooth-stepped so the cells do not show as diamonds.
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 3; i++) {
        v += a * noise(p);
        p *= 2.03;
        a *= 0.5;
    }
    return v;
}

void sky() {
    float up = EYEDIR.y;

    // The gradient, above and below the horizon.
    vec3 col = up >= 0.0
        ? mix(horizon, top, pow(clamp(up, 0.0, 1.0), 0.45))
        : mix(ground_horizon, ground_bottom, pow(clamp(-up, 0.0, 1.0), 0.35));

    if (up > 0.002) {
        // Project the view direction onto a flat plane overhead. Dividing by y
        // is what makes the band stretch toward the horizon instead of wrapping
        // round the dome like a hat.
        vec2 uv = EYEDIR.xz / (up + 0.22);
        uv += vec2(TIME * speed * 6.0, TIME * speed * 2.0);

        float d = fbm(uv * 2.6);
        float c = smoothstep(cover, cover + 0.22, d);

        // A second, slower layer so the edges churn instead of sliding as one
        // rigid sheet.
        float d2 = fbm(uv * 5.2 + vec2(TIME * speed * 2.0, 0.0));
        c *= 0.70 + 0.30 * smoothstep(0.25, 0.70, d2);

        // Fade out near the horizon, where uv blows up and the noise turns to
        // stripes, and again at the zenith so the band has a top edge.
        c *= smoothstep(0.01, 0.07, up);

        // No lighting: the shading is the noise itself, dark underside to lit
        // top. Nothing here reads the sun.
        vec3 cloud = mix(cloud_dark, cloud_lit, smoothstep(0.35, 0.85, d));
        col = mix(col, cloud, clamp(c, 0.0, 1.0) * 0.95);
    }

    COLOR = col;
}",
        };
        // The uniform defaults above are the shipped dusk; the live palette wins.
        var mat = new ShaderMaterial { Shader = shader };
        foreach (var (k, c) in new[]
                 {
                     ("top", L.SkyTop), ("horizon", L.SkyHorizon),
                     ("ground_horizon", L.GroundHorizon), ("ground_bottom", L.GroundBottom),
                     ("cloud_lit", L.CloudLit), ("cloud_dark", L.CloudDark),
                 })
            mat.SetShaderParameter(k, new Vector3(c.R, c.G, c.B));
        return mat;
    }

    public static Godot.Environment Build()
    {
        Material sky = Clouds
            ? CloudSky()
            : new ProceduralSkyMaterial
            {
                SkyTopColor = L.SkyTop,
                SkyHorizonColor = L.SkyHorizon,
                GroundHorizonColor = L.GroundHorizon,
                GroundBottomColor = L.GroundBottom,
                SunAngleMax = 22f,
                SunCurve = 0.18f,
            };

        var env = new Godot.Environment
        {
            BackgroundMode = Godot.Environment.BGMode.Sky,
            // Radiance at 128 and a real-time process mode: the sky animates, so
            // its radiance map is rebuilt every frame and it is the only part of
            // this that could cost anything. 128 is plenty for ambient off a
            // gradient with a cloud band on it.
            // The clouds are BACKGROUND ONLY. A realtime sky rebuilds its
            // radiance cubemap every frame, and measured against --noclouds that
            // was the entire cost of this feature: 5.6 ms against 4.0. Nothing
            // in this scene needs live sky reflection -- the ground is rough
            // vertex colour and the character is unshaded -- so ambient comes
            // from a fixed colour and the sky's radiance is generated once.
            Sky = new Sky
            {
                SkyMaterial = sky,
                RadianceSize = Sky.RadianceSizeEnum.Size128,
                ProcessMode = Sky.ProcessModeEnum.Incremental,
            },
            AmbientLightSource = Godot.Environment.AmbientSource.Color,
            AmbientLightColor = L.Ambient,
            AmbientLightEnergy = L.AmbientEnergy,

            // Fog hides the edge of the streamed ring and doubles as the far
            // atmosphere band (Law 7). Warm, because it is standing in for haze
            // lit by the same low sun.
            FogEnabled = true,
            FogLightColor = L.Fog,
            FogLightEnergy = 0.42f,
            FogDensity = L.FogDen,
            FogSkyAffect = 0.0f,
            FogAerialPerspective = 0.30f,

            // Small bright pools, not a bloom wash: a high threshold means only
            // genuinely bright material blooms.
            GlowEnabled = true,
            GlowIntensity = 0.55f,
            GlowBloom = 0.05f,
            GlowHdrThreshold = 1.05f,
            GlowBlendMode = Godot.Environment.GlowBlendModeEnum.Softlight,

            TonemapMode = Godot.Environment.ToneMapper.Filmic,
            TonemapExposure = L.Exposure,
            TonemapWhite = 4.0f,

            AdjustmentEnabled = true,
            // The references measure 0.43-0.56 saturation against our untextured
            // 0.31. Some of that gap is texture we do not have yet; this closes
            // the rest, and it is a grade, not a lie about the geometry.
            // 1.42 measured at 0.59 against a 0.45-0.52 target -- the dusk key
            // is already doing most of the colour, so the grade only has to
            // close what the missing ground textures leave.
            AdjustmentSaturation = L.Saturation,
            AdjustmentContrast = L.Contrast,
            AdjustmentBrightness = 1.02f,

            SsaoEnabled = true,
            SsaoRadius = 1.6f,
            SsaoIntensity = 1.6f,
        };

        // Study features, off unless a dial asks. Starting values, not tuned.
        if (L.VFog > 0f)
        {
            // Light in the air: the sun and every lamp scatter in it, and
            // forward scattering (anisotropy) makes a backlit sun glow through.
            env.VolumetricFogEnabled = true;
            env.VolumetricFogDensity = L.VFog;
            env.VolumetricFogAlbedo = L.Fog;
            env.VolumetricFogAnisotropy = 0.6f;
            env.VolumetricFogLength = 96f;
        }
        if (L.Ssil) { env.SsilEnabled = true; env.SsilRadius = 4f; env.SsilIntensity = 1.2f; }
        if (L.Sdfgi) { env.SdfgiEnabled = true; env.SdfgiUseOcclusion = true; }
        if (L.Bloom > 0f)
        {
            env.GlowBloom = 0.05f + 0.25f * L.Bloom;
            env.GlowHdrThreshold = 0.85f;
            env.GlowIntensity = 0.8f;
            env.GlowBlendMode = Godot.Environment.GlowBlendModeEnum.Screen;
        }
        env.TonemapMode = Tonemapper(L.Tone);
        return env;
    }

    /// <summary>A grade's tone mapper (Filmic unless it names ACES or AgX).</summary>
    public static Godot.Environment.ToneMapper Tonemapper(string tone) => tone switch
    {
        "aces" => Godot.Environment.ToneMapper.Aces,
        "agx" => Godot.Environment.ToneMapper.Agx,
        _ => Godot.Environment.ToneMapper.Filmic,
    };

    /// <summary>The character's colour multiplier. The figure is unshaded -- it
    /// carries the bake's own light -- so the scene's light never reaches it:
    /// raise the exposure or darken the frame and it glows. This divides the
    /// exposure back out (tint 1 = exactly the shipped figure at any exposure)
    /// and then applies the tint, so a darker scene can dim it with the world.</summary>
    public static Color SpriteModulate()
    {
        var k = 0.90f / L.Exposure;
        var t = L.SpriteTint;
        return new Color(t.R * k, t.G * k, t.B * k);
    }

    private static NoiseTexture2D? _grain;

    /// <summary>The texture proxy: a 64 px cellular grain, world-triplanar at
    /// about the sprite's texel density (Law 2), multiplied over a flat
    /// material. Stands in for the pixel-art textures the models do not have --
    /// it answers "what does texture do to the light", nothing more.</summary>
    public static void Grain(BaseMaterial3D m)
    {
        _grain ??= new NoiseTexture2D
        {
            Width = 64, Height = 64, Seamless = true,
            Noise = new FastNoiseLite
            {
                NoiseType = FastNoiseLite.NoiseTypeEnum.Cellular,
                Frequency = 0.09f,
                FractalType = FastNoiseLite.FractalTypeEnum.Fbm,
                FractalOctaves = 2,
            },
            ColorRamp = new Gradient
            {
                Offsets = new[] { 0f, 1f },
                Colors = new[] { new Color(0.70f, 0.68f, 0.66f), new Color(1f, 1f, 1f) },
            },
        };
        m.AlbedoTexture = _grain;
        m.Uv1Triplanar = true;
        m.Uv1WorldTriplanar = true;
        m.Uv1Scale = new Vector3(0.8f, 0.8f, 0.8f);
        m.TextureFilter = BaseMaterial3D.TextureFilterEnum.NearestWithMipmaps;
    }

    /// <summary>The tilt-shift band.
    ///
    /// Depth of field lives on CameraAttributesPractical in Godot 4, not on the
    /// Environment -- the Environment properties of the same name were removed.
    ///
    /// Shallow on purpose. Three shipped references disagree about how much blur
    /// belongs here: DQ3 cut it because the default made the frame hard to read,
    /// Triangle Strategy ships it behind a toggle, and SacriFire refuses depth
    /// blur outright on the grounds that blurring detailed pixel art wastes the
    /// work. This sits on DQ3's side of that argument, and it exists mainly to
    /// put the sharp band in the MIDDLE of the frame, which is the one part
    /// everyone agrees on (Law 5).
    /// </summary>
    public static CameraAttributesPractical Dof() => new()
    {
        DofBlurFarEnabled = true,
        DofBlurFarDistance = 55f,
        DofBlurFarTransition = 40f,
        DofBlurNearEnabled = true,
        DofBlurNearDistance = 6f,
        DofBlurNearTransition = 4f,
        DofBlurAmount = 0.06f,
    };

    /// <summary>The vignette, as a full-screen shader over everything.
    ///
    /// Every reference frame is framed dark at the edges and darker still at the
    /// bottom -- measured, edges 0.46-0.82 of frame mean and bottom 0.59-0.91,
    /// against nanobanna's 0.93 and 1.01. Until there is foreground geometry to
    /// do that job properly (occluder band, Law 7), this is what stops the frame
    /// reading as a flat field from edge to edge.
    /// </summary>
    public static CanvasLayer Vignette()
    {
        var shader = new Shader
        {
            Code = @"
shader_type canvas_item;
render_mode blend_mix;

uniform float strength : hint_range(0.0, 1.5) = 0.46;
uniform float bottom : hint_range(0.0, 1.5) = 0.26;
uniform vec3 tint = vec3(0.05, 0.04, 0.08);

void fragment() {
    vec2 d = SCREEN_UV - vec2(0.5);
    // Squared radius, weighted so the corners go first: a round vignette on a
    // 16:9 frame darkens the top and bottom of the picture instead of its sides.
    float r = dot(d * vec2(1.05, 1.35), d * vec2(1.05, 1.35));
    float v = smoothstep(0.16, 0.92, r) * strength;
    // Extra weight along the bottom edge, which is where the references put a
    // dark foreground.
    v += smoothstep(0.80, 1.0, SCREEN_UV.y) * bottom;
    COLOR = vec4(tint, clamp(v, 0.0, 0.70));
}",
        };

        var rect = new ColorRect
        {
            Name = "Vignette",
            Material = new ShaderMaterial { Shader = shader },
            MouseFilter = Control.MouseFilterEnum.Ignore,
        };
        rect.SetAnchorsPreset(Control.LayoutPreset.FullRect);

        var layer = new CanvasLayer { Name = "Grade", Layer = 100 };
        layer.AddChild(rect);
        return layer;
    }
}
