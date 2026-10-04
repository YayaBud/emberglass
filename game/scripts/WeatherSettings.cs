using Godot;

namespace Worldbuilder;

/// <summary>
/// The weather and clock the game starts with (`res://world/look/weather.tres`, applied by
/// <see cref="Look"/> before the command line, so `--weather=` and the study flags still win;
/// a saved game's clock and weather (user://save.json) still win over it too).
/// </summary>
[GlobalClass]
public partial class WeatherSettings : Resource
{
    /// <summary>"cycle" (rain comes and goes), "clear", "rain", "snow" -- <see cref="Weather.Mode"/>.</summary>
    [Export] public string Mode { get; set; } = "cycle";
    /// <summary>Minutes past midnight at the start (<see cref="Clock.Minutes"/>).</summary>
    [Export] public float StartMinutes { get; set; }
    /// <summary>Game minutes per real second (<see cref="Clock.Rate"/>).</summary>
    [Export] public float ClockRate { get; set; }
    /// <summary>Cloud cover 0-1 (<see cref="Clouds.Cover"/>).</summary>
    [Export] public float CloudCover { get; set; }
    /// <summary>The god-light shafts' strength (<see cref="Clouds.ShaftStrength"/>).</summary>
    [Export] public float ShaftStrength { get; set; }
    /// <summary>Every lamp's light, x (<see cref="Grade.LampScale"/>).</summary>
    [Export] public float LampScale { get; set; }
}
