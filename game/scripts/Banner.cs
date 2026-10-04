using Godot;

namespace Worldbuilder;

/// <summary>
/// The region's name as the player walks into it (implementation_plan B5): its title and its
/// one line of flavour (<see cref="Biomes.Region"/> -- "shown to the player on entering",
/// and until now shown nowhere), fading in at the top of the frame and out after four
/// seconds. A region counts as entered when it weighs 0.6 at the player's feet, so walking a
/// border does not flicker it. Hidden for captures (<see cref="Weather.Quiet"/>). Phase C adds
/// the region's danger under the flavour.
/// </summary>
public partial class Banner : CanvasLayer
{
    private Node3D _player = null!;
    private Label _title = null!, _line = null!;
    private int _in = -1;
    private float _t = 99f, _check;
    private readonly float[] _w = new float[Biomes.Count];

    /// <summary>A line under the flavour (Phase C: the danger), set per region.</summary>
    public static System.Func<Biome, string>? Extra;

    public void Bind(Node3D player)
    {
        _player = player;
        Layer = 5;
        var box = new VBoxContainer { AnchorLeft = 0f, AnchorRight = 1f, OffsetTop = 38f, Alignment = BoxContainer.AlignmentMode.Begin };
        _title = new Label { HorizontalAlignment = HorizontalAlignment.Center };
        _title.AddThemeFontSizeOverride("font_size", 34);
        _title.AddThemeColorOverride("font_color", new Color(1f, 0.93f, 0.8f));
        _title.AddThemeColorOverride("font_shadow_color", new Color(0.08f, 0.04f, 0.1f, 0.8f));
        _title.AddThemeConstantOverride("shadow_offset_x", 2);
        _title.AddThemeConstantOverride("shadow_offset_y", 2);
        _line = new Label { HorizontalAlignment = HorizontalAlignment.Center };
        _line.AddThemeFontSizeOverride("font_size", 17);
        _line.AddThemeColorOverride("font_color", new Color(0.92f, 0.88f, 0.84f));
        _line.AddThemeColorOverride("font_shadow_color", new Color(0.08f, 0.04f, 0.1f, 0.8f));
        box.AddChild(_title);
        box.AddChild(_line);
        AddChild(box);
        box.Modulate = new Color(1f, 1f, 1f, 0f);
    }

    public override void _Process(double delta)
    {
        if (_player == null) return;
        var dt = (float)delta;
        _t += dt;
        var box = (Control)GetChild(0);
        // in over 0.6 s, held, out over 1 s
        var a = _t < 0.6f ? _t / 0.6f : _t < 4f ? 1f : Mathf.Max(0f, 1f - (_t - 4f));
        box.Modulate = new Color(1f, 1f, 1f, Weather.Quiet ? 0f : a);
        _check -= dt;
        if (_check > 0f) return;
        _check = 0.5f;
        var p = _player.GlobalPosition;
        Biomes.Weights(new Vector2(p.X, p.Z), WorldGen.Seed, _w);
        for (var i = 0; i < _w.Length; i++)
        {
            if (_w[i] < 0.6f || i == _in) continue;
            var first = _in < 0;
            _in = i;
            if (first && _t > 90f) { _t = 99f; return; }   // the spawn's own region is not "entered"
            var r = Biomes.All[i];
            _title.Text = r.Name;
            _line.Text = r.Flavour + (Extra?.Invoke(r.Kind) is { Length: > 0 } x ? "\n" + x : "");
            _t = 0f;
            return;
        }
    }
}
