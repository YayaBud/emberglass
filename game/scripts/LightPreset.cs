using Godot;

namespace Worldbuilder;

/// <summary>
/// One of <see cref="Grade"/>'s lightings as an editable resource
/// (`res://world/look/{twilight,city,snow,desert}.tres`, written by `--bake`, applied by
/// <see cref="Look"/>). The fields mirror <see cref="Grade.Lighting"/> one for one, by name.
/// </summary>
[GlobalClass]
public partial class LightPreset : Resource
{
    [ExportGroup("Sun")]
    [Export] public float Elev { get; set; }
    [Export] public float Yaw { get; set; }
    [Export] public Color Sun { get; set; }
    [Export] public float SunEnergy { get; set; }
    [Export] public float Soft { get; set; }
    [Export] public float SunFog { get; set; }
    [ExportGroup("Fill and ambient")]
    [Export] public Color Ambient { get; set; }
    [Export] public float AmbientEnergy { get; set; }
    [Export] public Color Fill { get; set; }
    [Export] public float FillEnergy { get; set; }
    [ExportGroup("Fog and mist")]
    [Export] public Color Fog { get; set; }
    [Export] public float FogDen { get; set; }
    [Export] public float VFog { get; set; }
    [Export] public Color Mist { get; set; }
    [Export] public float MistDensity { get; set; }
    [ExportGroup("Grade")]
    [Export] public Color Black { get; set; }
    [Export] public float Exposure { get; set; }
    [Export] public float Saturation { get; set; }
    [Export] public float Contrast { get; set; }
    [Export] public float Bloom { get; set; }
    [Export] public string Tone { get; set; } = "filmic";
    [Export] public bool Ssil { get; set; }
    [Export] public bool Sdfgi { get; set; }
    [Export] public bool Grain { get; set; }
    [ExportGroup("Lamps and sprites")]
    [Export] public float Lamps { get; set; }
    [Export] public float WindowsLit { get; set; }
    [Export] public Color SpriteTint { get; set; }
    [ExportGroup("Sky")]
    [Export] public Color SkyTop { get; set; }
    [Export] public Color SkyHorizon { get; set; }
    [Export] public Color GroundHorizon { get; set; }
    [Export] public Color GroundBottom { get; set; }
    [Export] public Color CloudLit { get; set; }
    [Export] public Color CloudDark { get; set; }
}
