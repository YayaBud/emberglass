using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The look as editable resources (implementation_plan Phase 7), in `res://world/look/`:
/// the four lightings (<see cref="LightPreset"/>: twilight = <see cref="Grade.L"/>, city,
/// snow, desert), the environment (`environment.tres`, the one <see cref="Grade.Build"/>
/// made; <see cref="Weather"/> still animates what it animates -- fog, exposure, sky by
/// region and hour -- and every other setting you change in it sticks), and the start
/// weather and clock (<see cref="WeatherSettings"/>). `--bake` writes them where missing
/// (`--rebake=look` rewrites them); the lighting study and tuning flags (`--light=`,
/// `--citylight=` ...) bypass them so their frames reproduce.
/// </summary>
public static class Look
{
    public const string Dir = "res://world/look/";
    private static string EnvPath => Dir + "environment.tres";
    private static string WeatherPath => Dir + "weather.tres";

    private static (string Name, System.Func<Grade.Lighting> Get, System.Action<Grade.Lighting> Set)[] Presets =>
    new (string, System.Func<Grade.Lighting>, System.Action<Grade.Lighting>)[]
    {
        ("twilight", () => Grade.L, l => Grade.L = l), ("city", () => Grade.CityL, l => Grade.CityL = l),
        ("snow", () => Grade.SnowL, l => Grade.SnowL = l), ("desert", () => Grade.DesertL, l => Grade.DesertL = l),
    };

    private static bool Rebake => Worldbuilder.Bake.Rebake.Contains("look") || Worldbuilder.Bake.Rebake.Contains("all");

    // ------------------------------------------------------------------ lightings

    private static LightPreset ToPreset(Grade.Lighting l)
    {
        var p = new LightPreset();
        foreach (var f in typeof(Grade.Lighting).GetFields()) typeof(LightPreset).GetProperty(f.Name)!.SetValue(p, f.GetValue(l));
        return p;
    }

    private static void FromPreset(LightPreset p, Grade.Lighting l)
    {
        foreach (var f in typeof(Grade.Lighting).GetFields()) f.SetValue(l, typeof(LightPreset).GetProperty(f.Name)!.GetValue(p));
    }

    private static string Fields(Grade.Lighting l) => string.Join("|", typeof(Grade.Lighting).GetFields().Select(f => $"{f.GetValue(l)}"));

    /// <summary>After World picked its lighting (and before the sky and sun are built): the
    /// edited presets, unless a lighting flag is tuning them.</summary>
    public static void Apply(bool flags)
    {
        if (flags) return;
        var n = 0;
        foreach (var (name, get, _) in Presets)
            if (ResourceLoader.Exists($"{Dir}{name}.tres") && ResourceLoader.Load($"{Dir}{name}.tres", "", ResourceLoader.CacheMode.Ignore) is LightPreset p)
            {
                FromPreset(p, get());
                n++;
            }
        if (n > 0) GD.Print($"look: {n} lighting presets from {Dir}");
    }

    /// <summary>The environment to use: the edited one, or null (then Grade.Build()).</summary>
    public static Godot.Environment? Environment(bool flags) =>
        !flags && ResourceLoader.Exists(EnvPath) ? (Godot.Environment)ResourceLoader.Load<Godot.Environment>(EnvPath, "", ResourceLoader.CacheMode.Ignore).Duplicate(true) : null;

    // ------------------------------------------------------------------ weather

    /// <summary>First in World._Ready, before the command line (which may override it).</summary>
    public static void ApplyWeather()
    {
        if (!ResourceLoader.Exists(WeatherPath) || ResourceLoader.Load(WeatherPath, "", ResourceLoader.CacheMode.Ignore) is not WeatherSettings w) return;
        (Weather.Mode, Clock.Minutes, Clock.Rate) = (w.Mode, w.StartMinutes, w.ClockRate);
        (Clouds.Cover, Clouds.ShaftStrength, Grade.LampScale) = (w.CloudCover, w.ShaftStrength, w.LampScale);
    }

    private static WeatherSettings CurrentWeather() => new()
    {
        Mode = Weather.Mode, StartMinutes = Clock.Minutes, ClockRate = Clock.Rate,
        CloudCover = Clouds.Cover, ShaftStrength = Clouds.ShaftStrength, LampScale = Grade.LampScale,
    };

    // ------------------------------------------------------------------ bake + check

    /// <summary>--bake: writes what is missing from the code's values, reads each back, and
    /// checks that an edit to a preset reaches the game's lighting.</summary>
    public static void Bake(bool flags)
    {
        if (flags) { GD.Print("look: a lighting flag is set; not baking the look"); return; }
        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(Dir));
        var wrote = new List<string>();
        foreach (var (name, get, _) in Presets)
        {
            var path = $"{Dir}{name}.tres";
            if (ResourceLoader.Exists(path) && !Rebake) continue;
            ResourceSaver.Save(ToPreset(get()), path);
            wrote.Add(name);
        }
        if (!ResourceLoader.Exists(EnvPath) || Rebake) { ResourceSaver.Save(Grade.Build(), EnvPath); wrote.Add("environment"); }
        if (!ResourceLoader.Exists(WeatherPath) || Rebake) { ResourceSaver.Save(CurrentWeather(), WeatherPath); wrote.Add("weather"); }
        if (wrote.Count == 0) return;

        // read back: every preset field, every plain environment setting, the weather
        var bad = new List<string>();
        foreach (var (name, get, _) in Presets)
        {
            var copy = new Grade.Lighting();
            FromPreset(ResourceLoader.Load<LightPreset>($"{Dir}{name}.tres", "", ResourceLoader.CacheMode.Ignore), copy);
            if (Fields(copy) != Fields(get())) bad.Add(name);
        }
        var built = Grade.Build();
        var loaded = Environment(false)!;
        var props = 0;
        foreach (var d in built.GetPropertyList())
        {
            var name = (string)d["name"];
            if (((PropertyUsageFlags)(int)d["usage"] & PropertyUsageFlags.Storage) == 0) continue;
            var a = built.Get(name);
            if (a.VariantType is Variant.Type.Object or Variant.Type.Nil) continue;
            props++;
            if (a.ToString() != loaded.Get(name).ToString()) bad.Add($"environment.{name}");
        }
        var w = ResourceLoader.Load<WeatherSettings>(WeatherPath, "", ResourceLoader.CacheMode.Ignore);
        if (w.Mode != Weather.Mode || w.StartMinutes != Clock.Minutes || w.CloudCover != Clouds.Cover) bad.Add("weather");

        // an edit: the city's sun +1 in its preset reaches Grade.CityL, and back
        var cityPath = $"{Dir}city.tres";
        var edited = ResourceLoader.Load<LightPreset>(cityPath, "", ResourceLoader.CacheMode.Ignore);
        var before = Grade.CityL.SunEnergy;
        edited.SunEnergy = before + 1f;
        FromPreset(edited, Grade.CityL);
        var after = Grade.CityL.SunEnergy;
        FromPreset(ResourceLoader.Load<LightPreset>(cityPath, "", ResourceLoader.CacheMode.Ignore), Grade.CityL);
        var ok = bad.Count == 0 && Mathf.IsEqualApprox(after, before + 1f) && Grade.CityL.SunEnergy == before;
        GD.Print($"look: wrote {string.Join(", ", wrote)} to {Dir}; read back 4 presets, {props} environment settings, weather: "
                 + $"{(bad.Count == 0 ? "identical" : "DIFF " + string.Join(", ", bad.Take(6)))}; city preset SunEnergy {before:F2} -> {after:F2} -> {Grade.CityL.SunEnergy:F2} -> {(ok ? "PASS" : "FAIL")}");
    }
}
